"""Mouse focus management and click routing for widget overlays.

This module provides a :class:`FocusManager` that tracks which widget has
input focus and routes mouse/keyboard events to the correct widget based
on z-order-aware hit-testing.

The focus manager bridges the gap between the advisory ``focused`` flag on
:class:`~wyby.widget.Widget` and the scene's event dispatch loop.  Without
it, game code must manually check ``contains_point`` on every widget in the
correct order and manage focus transitions by hand.  The ``FocusManager``
automates this with a simple ``dispatch(event)`` call.

Usage::

    from wyby.focus import FocusManager
    from wyby.button import Button

    btn_a = Button("Start", x=5, y=10, on_click=start_game)
    btn_b = Button("Quit", x=5, y=12, on_click=quit_game)

    fm = FocusManager()
    fm.add(btn_a)
    fm.add(btn_b)

    # In your event loop:
    for event in events:
        consumed = fm.dispatch(event)
        if not consumed:
            # Event was not handled by any widget — let the scene handle it.
            scene.handle_event(event)

Caveats:
    - **Z-order uses widget z_index.**  Hit-testing sorts widgets by
      :attr:`~wyby.widget.Widget.z_index` (highest = topmost).  Within
      the same ``z_index``, registration order is the tiebreaker
      (last-added = topmost).  Changing a widget's ``z_index`` takes
      effect on the next :meth:`~FocusManager.dispatch` call.
    - **Hit-testing is geometric, not visual.**  The manager uses each
      widget's bounding box (:meth:`~wyby.widget.Widget.contains_point`)
      to determine which widget was clicked.  If a widget's visual content
      does not fill its bounding box (e.g., a round button in a rectangular
      bounds), clicks on the transparent area still register.  Conversely,
      if a widget draws outside its bounds, those pixels are not clickable.
    - **Single focus only.**  The manager enforces that at most one widget
      has ``focused = True`` at a time.  Setting focus on a widget
      automatically blurs the previously focused one.  This differs from
      the base :class:`~wyby.widget.Widget` which allows multiple widgets
      to be focused simultaneously.  If you need multi-focus (e.g.,
      independent focus contexts for keyboard and mouse), manage focus
      manually instead of using this class.
    - **Click-to-focus only.**  Focus changes happen when a mouse press
      lands on a widget.  There is no hover-to-focus, no automatic
      keyboard focus cycling on mouse move, and no focus-follows-mouse
      mode.  Tab/Shift-Tab cycling is supported via :meth:`focus_next` /
      :meth:`focus_prev`, but the caller must bind these to keys manually.
    - **Invisible widgets are skipped.**  Widgets with ``visible = False``
      are not hit-tested and cannot receive focus via click.  They can
      still be focused programmatically via :meth:`set_focus`.
    - **Not coupled to the renderer.**  The focus manager operates on a
      list of widgets independently of :class:`~wyby.renderer.Renderer`
      overlays.  The caller must ensure that the same widgets are
      registered as both overlays (for drawing) and focus-managed widgets
      (for input).  Adding a widget to one does not add it to the other.
    - **Single-threaded.**  All methods must be called from the game loop
      thread.  No locking is performed.
    - **Mouse coordinates must match CellBuffer space.**  The
      :class:`~wyby.input.MouseEvent` ``x``/``y`` values are 0-based
      terminal coordinates.  If your widgets are drawn into a sub-region
      of the terminal (e.g., a viewport with an offset), you must adjust
      coordinates before dispatching.
    - **Terminal mouse support varies.**  Mouse events are only available
      when the :class:`~wyby.input.InputManager` has mouse mode enabled.
      Not all terminals support mouse reporting — see
      :class:`~wyby.input.MouseEvent` for compatibility details.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from wyby.event import Event
    from wyby.input import MouseEvent
    from wyby.widget import Widget

_logger = logging.getLogger(__name__)


class FocusManager:
    """Manages widget focus and routes input events by z-order.

    Widgets are stored in registration order.  For hit-testing, widgets
    are sorted by :attr:`~wyby.widget.Widget.z_index` (highest first).
    Within the same ``z_index``, later-added widgets are considered
    topmost.  This ensures that the visually front-most widget receives
    the click.

    Args:
        widgets: Optional initial sequence of widgets to manage.
            Added in iteration order (first = backmost, last = topmost).

    Caveats:
        - Adding the same widget twice is a no-op (silently ignored).
        - The manager does not own widgets — removing a widget from the
          manager does not destroy it or affect its parent/child hierarchy.
        - Focus state is managed via the widget's ``focused`` property,
          which triggers ``on_focus()``/``on_blur()`` callbacks.  If those
          callbacks raise, the exception propagates to the caller.
    """

    __slots__ = ("_widgets", "_focused")

    def __init__(self, widgets: list[Widget] | None = None) -> None:
        self._widgets: list[Widget] = []
        self._focused: Widget | None = None
        if widgets:
            for w in widgets:
                self.add(w)

    # -- Widget registration ------------------------------------------------

    @property
    def widgets(self) -> list[Widget]:
        """Read-only copy of managed widgets in z-order (back to front)."""
        return list(self._widgets)

    @property
    def focused_widget(self) -> Widget | None:
        """The currently focused widget, or ``None`` if no widget has focus."""
        return self._focused

    def add(self, widget: Widget) -> None:
        """Register a widget for focus management.

        The widget is appended to the end of the list (topmost z-order).
        If the widget is already registered, this is a no-op.

        Args:
            widget: The widget to register.

        Raises:
            TypeError: If *widget* is not a :class:`~wyby.widget.Widget`.
        """
        from wyby.widget import Widget

        if not isinstance(widget, Widget):
            msg = f"widget must be a Widget, got {type(widget).__name__}"
            raise TypeError(msg)
        if widget in self._widgets:
            return
        self._widgets.append(widget)
        _logger.debug("FocusManager: added %r (now %d widgets)", widget, len(self._widgets))

    def remove(self, widget: Widget) -> None:
        """Unregister a widget from focus management.

        If the removed widget was focused, focus is cleared (no widget
        is focused afterward).

        Args:
            widget: The widget to remove.

        Raises:
            ValueError: If *widget* is not currently managed.
        """
        try:
            self._widgets.remove(widget)
        except ValueError:
            msg = f"{widget!r} is not managed by this FocusManager"
            raise ValueError(msg) from None
        if self._focused is widget:
            widget.focused = False
            self._focused = None
        _logger.debug("FocusManager: removed %r (now %d widgets)", widget, len(self._widgets))

    def clear(self) -> None:
        """Remove all widgets and clear focus."""
        if self._focused is not None:
            self._focused.focused = False
            self._focused = None
        self._widgets.clear()

    # -- Focus management ---------------------------------------------------

    def set_focus(self, widget: Widget | None) -> None:
        """Set focus to *widget*, or clear focus if ``None``.

        If *widget* is not ``None``, it must be a registered widget.
        The previously focused widget (if any) is blurred.

        Args:
            widget: The widget to focus, or ``None`` to clear focus.

        Raises:
            ValueError: If *widget* is not ``None`` and not registered.
        """
        if widget is not None and widget not in self._widgets:
            msg = f"{widget!r} is not managed by this FocusManager"
            raise ValueError(msg)
        if widget is self._focused:
            return
        if self._focused is not None:
            self._focused.focused = False
        self._focused = widget
        if widget is not None:
            widget.focused = True

    def focus_next(self) -> Widget | None:
        """Move focus to the next visible widget in tab order.

        Tab order follows registration order (index 0 → N-1).  Wraps
        around from the last widget to the first.  Skips invisible
        widgets.

        Returns:
            The newly focused widget, or ``None`` if no visible widgets
            exist.

        Caveats:
            - If no widget is currently focused, focuses the first
              visible widget.
            - If all widgets are invisible, clears focus and returns
              ``None``.
        """
        return self._cycle_focus(forward=True)

    def focus_prev(self) -> Widget | None:
        """Move focus to the previous visible widget in tab order.

        Wraps around from the first widget to the last.  Skips invisible
        widgets.

        Returns:
            The newly focused widget, or ``None`` if no visible widgets
            exist.
        """
        return self._cycle_focus(forward=False)

    def _cycle_focus(self, *, forward: bool) -> Widget | None:
        """Cycle focus forward or backward through visible widgets."""
        visible = [w for w in self._widgets if w.visible]
        if not visible:
            self.set_focus(None)
            return None

        if self._focused is None or self._focused not in visible:
            # No current focus — pick the first (forward) or last (backward).
            target = visible[0] if forward else visible[-1]
            self.set_focus(target)
            return target

        idx = visible.index(self._focused)
        step = 1 if forward else -1
        next_idx = (idx + step) % len(visible)
        target = visible[next_idx]
        self.set_focus(target)
        return target

    # -- Z-order helpers ----------------------------------------------------

    def _iter_topmost_first(self) -> list[Widget]:
        """Return widgets sorted topmost-first for hit-testing.

        Sort by z_index descending.  Within the same z_index, reverse
        registration order (last-added = topmost).  Uses a stable sort
        on ``(−z_index, −registration_index)`` so that higher z_index
        and later registration both win.
        """
        # enumerate gives registration index.  We negate both keys so
        # that a normal ascending sort yields descending on both axes.
        return [
            w for _, w in sorted(
                enumerate(self._widgets),
                key=lambda pair: (-pair[1].z_index, -pair[0]),
            )
        ]

    # -- Event dispatch -----------------------------------------------------

    def dispatch(self, event: Event) -> bool:
        """Route an input event to the appropriate widget.

        For mouse press events, performs z-order hit-testing (back-to-front)
        to find the topmost visible widget under the cursor.  If found:

        1. Focus is moved to that widget (blurring the previous one).
        2. The event is dispatched to the widget's ``handle_event``.

        If no widget is hit, focus is cleared (click on empty space
        unfocuses the current widget).

        For all other events (key events, mouse release/move/scroll),
        the event is dispatched to the currently focused widget.

        Args:
            event: The event to dispatch.

        Returns:
            ``True`` if the event was consumed by a widget, ``False``
            otherwise (no widget handled it).

        Caveats:
            - Mouse press events that hit a widget are dispatched to that
              widget regardless of whether it was previously focused.
              The widget receives the event *after* its ``focused`` flag
              is set to ``True``.
            - Mouse press events that hit empty space clear focus but
              return ``False`` (not consumed).  The caller can use this
              to implement "click on background" behaviour.
            - Non-press mouse events (release, move, scroll) are routed
              to the focused widget, not to the widget under the cursor.
              This means drag events stay with the widget that was clicked,
              even if the cursor moves outside its bounds.  This is
              standard focus-based routing, but it means hover effects
              require custom logic.
            - Key events are only dispatched to the focused widget.  If
              no widget is focused, key events return ``False``.
            - If a widget's ``handle_event`` raises, the exception
              propagates to the caller.
        """
        from wyby.input import MouseEvent

        if isinstance(event, MouseEvent) and event.action == "press":
            return self._dispatch_mouse_press(event)

        # All other events go to the focused widget.
        if self._focused is not None:
            return self._focused.handle_event(event)

        return False

    def _dispatch_mouse_press(self, event: MouseEvent) -> bool:
        """Handle a mouse press by hit-testing in z-order (topmost first).

        Widgets are sorted by z_index descending; within the same
        z_index, later-registered widgets are tested first (reverse
        registration order).  This matches the visual draw order so
        the widget that *appears* on top gets the click.
        """
        for widget in self._iter_topmost_first():
            if not widget.visible:
                continue
            if widget.contains_point(event.x, event.y):
                self.set_focus(widget)
                return widget.handle_event(event)

        # Click on empty space — clear focus.
        self.set_focus(None)
        return False

    # -- Introspection ------------------------------------------------------

    def widget_at(self, x: int, y: int) -> Widget | None:
        """Return the topmost visible widget at (*x*, *y*), or ``None``.

        Uses the same z-order-aware hit-testing as :meth:`dispatch`:
        highest ``z_index`` first, then reverse registration order
        within the same ``z_index``.

        Caveats:
            - This is a geometric check only.  See module-level caveats
              about bounding-box hit-testing.
        """
        for widget in self._iter_topmost_first():
            if widget.visible and widget.contains_point(x, y):
                return widget
        return None

    def __len__(self) -> int:
        """Return the number of managed widgets."""
        return len(self._widgets)

    def __contains__(self, widget: Widget) -> bool:
        """Return whether *widget* is managed by this focus manager."""
        return widget in self._widgets

    def __repr__(self) -> str:
        focused_repr = repr(self._focused) if self._focused else "None"
        return (
            f"FocusManager(widgets={len(self._widgets)}, "
            f"focused={focused_repr})"
        )
