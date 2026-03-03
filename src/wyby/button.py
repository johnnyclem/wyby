"""Button widget with click handler for terminal UI overlays.

This module provides a :class:`Button` widget that renders a clickable
text label into a :class:`~wyby.grid.CellBuffer` and invokes a callback
when activated.  Activation can happen via mouse click (left button
press inside bounds) or keyboard (Enter/Space while focused).

Usage::

    from wyby.button import Button
    from wyby.grid import CellBuffer

    def on_start() -> None:
        print("Game started!")

    btn = Button("Start", x=5, y=10, on_click=on_start)

    # In your game loop:
    buf = CellBuffer(80, 24)
    btn.draw(buf)

    # Route events to the button:
    consumed = btn.handle_event(some_event)

Caveats:
    - **Click detection is purely geometric.**  ``handle_event`` checks
      whether a :class:`~wyby.input.MouseEvent` falls inside the
      button's bounding box via :meth:`~wyby.widget.Widget.contains_point`.
      There is no hit-testing against the visual content — if the button
      is occluded by another widget drawn later, the button will still
      consume the click.  The caller (scene or UI manager) must route
      events in the correct order to handle overlapping widgets.
    - **No debounce or repeat protection.**  Every qualifying event
      triggers the callback.  If the terminal sends rapid-fire events
      (e.g., key repeat on Enter), the callback fires for each one.
      Game code should implement its own debounce if needed.
    - **Callback exceptions propagate.**  If ``on_click`` raises, the
      exception propagates to the caller of ``handle_event``.  The
      button does not catch or suppress callback errors.  This is
      intentional — swallowing exceptions silently would make debugging
      harder.
    - **No visual press/release animation.**  The button does not render
      a "pressed" state on mouse-down.  Terminal rendering at typical
      frame rates (15–30 FPS) makes sub-frame press animations
      unreliable.  If you need press feedback, manage a ``pressed``
      state in your callback and check it in ``draw()``.
    - **Mouse support requires opt-in.**  Mouse events are only
      generated when the :class:`~wyby.input.InputManager` has mouse
      mode enabled.  Without mouse mode, the button can only be
      activated via keyboard (Enter/Space while focused).
    - **Label is not automatically sized.**  The button's ``width`` is
      calculated from the label text length plus padding at construction
      time.  If you change the label later via the ``label`` property,
      the width is updated automatically, but the button does not
      reflow or notify its parent of the size change.
    - **Single-line only.**  The label is rendered on a single row.
      Multi-line button labels are not supported.  The ``height`` is
      fixed at 1 row.
    - **No disabled state.**  To prevent activation, either set
      ``visible = False``, remove the button from the event routing
      chain, or set ``on_click = None`` (which causes clicks to be
      consumed but ignored).
    - **Wide characters in labels** (CJK, fullwidth) are supported
      via CellBuffer's ``put_text``, but the width calculation uses
      Python's ``len()`` plus padding, which does not account for
      double-width characters.  Use :func:`wyby.unicode.string_width`
      for accurate width if your label contains wide characters.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable

from wyby.widget import Widget

if TYPE_CHECKING:
    from wyby.event import Event
    from wyby.grid import CellBuffer

_logger = logging.getLogger(__name__)

# Horizontal padding on each side of the label text (in columns).
_HORIZONTAL_PADDING = 1


class Button(Widget):
    """A clickable button widget with a text label and callback.

    The button renders as ``[ label ]`` — the label text with one cell
    of padding on each side, enclosed in brackets.  It responds to
    left mouse clicks inside its bounds and Enter/Space key presses
    when focused.

    Args:
        label: The text to display on the button.  Must be a non-empty
            string.
        x: Column position of the button's top-left corner.
        y: Row position of the button's top-left corner.
        on_click: Callback invoked when the button is activated.
            May be ``None`` to create a button with no action (clicks
            are still consumed).  The callback takes no arguments.

    Raises:
        TypeError: If *label* is not a string or *on_click* is not
            callable/None.
        ValueError: If *label* is empty.

    Caveats:
        - Width is computed as ``len(label) + 2 * padding + 2`` (for
          the bracket characters).  This uses ``len()``, not terminal
          display width.  For labels with wide characters (CJK), the
          visual width will exceed the widget's logical width.  Use
          :func:`wyby.unicode.string_width` and set ``width`` manually
          if needed.
        - Height is always 1.  Passing a different height to the base
          class is not supported; it will be overridden.
    """

    __slots__ = ("_label", "_on_click")

    def __init__(
        self,
        label: str,
        x: int = 0,
        y: int = 0,
        on_click: Callable[[], object] | None = None,
    ) -> None:
        if not isinstance(label, str):
            msg = f"label must be a str, got {type(label).__name__}"
            raise TypeError(msg)
        if not label:
            msg = "label must not be empty"
            raise ValueError(msg)
        if on_click is not None and not callable(on_click):
            msg = f"on_click must be callable or None, got {type(on_click).__name__}"
            raise TypeError(msg)

        # Width: [ + padding + label + padding + ]
        width = len(label) + 2 * _HORIZONTAL_PADDING + 2
        super().__init__(x=x, y=y, width=width, height=1)

        self._label = label
        self._on_click = on_click

    # -- Properties ---------------------------------------------------------

    @property
    def label(self) -> str:
        """The button's display text.

        Setting this updates the button's width to fit the new label.
        """
        return self._label

    @label.setter
    def label(self, value: str) -> None:
        if not isinstance(value, str):
            msg = f"label must be a str, got {type(value).__name__}"
            raise TypeError(msg)
        if not value:
            msg = "label must not be empty"
            raise ValueError(msg)
        self._label = value
        self.width = len(value) + 2 * _HORIZONTAL_PADDING + 2

    @property
    def on_click(self) -> Callable[[], object] | None:
        """The callback invoked when the button is activated.

        Set to ``None`` to make the button inert (it still consumes
        events, but takes no action).
        """
        return self._on_click

    @on_click.setter
    def on_click(self, value: Callable[[], object] | None) -> None:
        if value is not None and not callable(value):
            msg = f"on_click must be callable or None, got {type(value).__name__}"
            raise TypeError(msg)
        self._on_click = value

    # -- Drawing ------------------------------------------------------------

    def draw(self, buffer: CellBuffer) -> None:
        """Render the button into *buffer*.

        Draws the label with bracket delimiters: ``[ label ]``.
        When focused, uses bold styling for visual feedback.

        Skips drawing if ``self.visible`` is ``False``.

        Caveats:
            - Drawing relies on CellBuffer's silent clipping for
              out-of-bounds writes.  A button positioned partially
              off-screen will be truncated without error.
            - Focus styling (bold) is the only visual distinction.
              There is no color change or border — keep terminal
              color accessibility in mind.
        """
        if not self.visible:
            return
        # Build display string: [ label ]
        text = "[" + " " * _HORIZONTAL_PADDING + self._label + " " * _HORIZONTAL_PADDING + "]"
        buffer.put_text(self._x, self._y, text, bold=self._focused)

    # -- Event handling -----------------------------------------------------

    def handle_event(self, event: Event) -> bool:
        """Process an input event, activating the button if appropriate.

        Activation triggers:
            - **Mouse:** A :class:`~wyby.input.MouseEvent` with
              ``button="left"`` and ``action="press"`` whose
              coordinates fall inside the button's bounds.
            - **Keyboard:** A :class:`~wyby.input.KeyEvent` with
              ``key="enter"`` or ``key="space"`` while the button
              is focused.

        Returns ``True`` if the event was consumed, ``False`` otherwise.

        Caveats:
            - Mouse clicks are consumed (return ``True``) even if
              ``on_click`` is ``None``.  This prevents click-through
              to widgets behind the button.
            - Keyboard activation requires ``self.focused`` to be
              ``True``.  Unfocused buttons ignore key events entirely.
            - The callback is called synchronously.  Long-running
              callbacks will block the game loop.
        """
        # Avoid circular import — check by class name since input.py
        # imports Event from event.py and we only need type inspection.
        from wyby.input import KeyEvent, MouseEvent

        if isinstance(event, MouseEvent):
            if event.button == "left" and event.action == "press":
                if self.contains_point(event.x, event.y):
                    _logger.debug("Button %r clicked at (%d, %d)", self._label, event.x, event.y)
                    if self._on_click is not None:
                        self._on_click()
                    return True
            return False

        if isinstance(event, KeyEvent):
            if self._focused and event.key in ("enter", "space"):
                _logger.debug("Button %r activated via key %r", self._label, event.key)
                if self._on_click is not None:
                    self._on_click()
                return True
            return False

        return False

    # -- Repr ---------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"Button("
            f"label={self._label!r}, "
            f"x={self._x}, y={self._y}, "
            f"w={self._width}, h={self._height}"
            f"{', visible=False' if not self._visible else ''}"
            f"{', focused' if self._focused else ''}"
            f")"
        )
