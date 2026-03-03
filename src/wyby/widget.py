"""Widget base class for terminal UI overlays.

This module provides the :class:`Widget` abstract base class for building
UI elements (buttons, health bars, dialogs, labels) that render on top of
the game world.  Widgets draw themselves into a :class:`~wyby.grid.CellBuffer`
at a specified position and size, and can receive input events for
interactive behaviour.

Widgets are **not** components.  They exist outside the entity/component
model and are instead owned by scenes or a dedicated UI layer.  A scene
(or overlay manager) is responsible for calling :meth:`Widget.draw` each
frame and routing input events via :meth:`Widget.handle_event`.

The widget model is intentionally minimal.  wyby is **not** trying to
replicate Textual's full widget/event/CSS system.  The goal is a thin
abstraction over CellBuffer drawing that provides:

- Consistent position/size tracking
- Focus state for input routing
- Visibility toggling
- A parent/child hierarchy for composite widgets (panels containing
  buttons, dialogs containing labels, etc.)

Usage::

    from wyby.widget import Widget
    from wyby.grid import CellBuffer

    class Label(Widget):
        def __init__(self, text: str, x: int, y: int) -> None:
            super().__init__(x=x, y=y, width=len(text), height=1)
            self._text = text

        def draw(self, buffer: CellBuffer) -> None:
            if not self.visible:
                return
            buffer.put_text(self.x, self.y, self._text)

Caveats:
    - **Not a full widget toolkit.**  There is no layout engine, no CSS,
      no flexbox, no automatic sizing.  Widgets are positioned and sized
      explicitly in cell coordinates.  A basic layout helper may be added
      later (see T100), but it will not approach the sophistication of
      Textual or tkinter.
    - **No automatic redraw.**  Widgets do not track dirty state or
      trigger repaints.  The scene or game loop must call ``draw()`` on
      every visible widget each frame.  This matches wyby's explicit
      rendering philosophy — the game loop controls when and what is
      drawn.
    - **Z-order is opt-in.**  Each widget has a ``z_index`` property
      (default 0) that determines visual stacking when managed by
      :class:`~wyby.renderer.Renderer` overlays or
      :class:`~wyby.focus.FocusManager` hit-testing.  Higher z_index
      values render on top of lower ones.  Widgets with equal z_index
      fall back to registration order (last-added = topmost).  The
      z_index is **not** used by ``draw()`` directly — it is the
      responsibility of the overlay/focus system to sort by z_index
      before iterating widgets.
    - **Coordinate system.**  Widget ``x``/``y`` are in buffer-space
      (top-left origin, column/row).  There is no local-to-global
      coordinate transform for nested widgets — children must offset
      their own coordinates relative to their parent.  This keeps the
      model simple but means deeply nested hierarchies require manual
      coordinate math.
    - **No event bubbling.**  Events do not propagate up the widget
      tree automatically.  ``handle_event`` on a parent must explicitly
      delegate to children.  This avoids the complexity of event
      capture/bubble phases but requires more manual wiring.
    - **Focus is advisory.**  The ``focused`` flag is managed by game
      code.  There is no automatic tab-order, no focus manager, and no
      built-in keyboard navigation between widgets.  The scene is
      responsible for tracking which widget has focus and setting the
      flag accordingly.
    - **Terminal cell constraints apply.**  Widget content is subject
      to the same terminal limitations as everything else in wyby:
      ~1:2 cell aspect ratio, no sub-cell positioning, unreliable emoji
      rendering, and font-dependent glyph widths.  See
      :mod:`wyby.grid` and :mod:`wyby.unicode` caveats.
    - **Single-threaded.**  Widget mutation (adding/removing children,
      changing position, toggling visibility) is not thread-safe.
      All widget operations must happen on the game loop thread.
    - **Children are not clipped.**  A child widget can draw outside
      its parent's bounds.  CellBuffer's silent clipping prevents
      writes outside the buffer, but there is no per-widget clip rect.
      This may be addressed in a future version.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from wyby.event import Event
    from wyby.grid import CellBuffer

_logger = logging.getLogger(__name__)

# Minimum and maximum widget dimensions.  Zero-size widgets are not
# useful and negative dimensions are nonsensical.  The upper bound
# matches CellBuffer's _MAX_DIMENSION to prevent widgets that cannot
# possibly fit in any buffer.
_MIN_DIMENSION = 1
_MAX_DIMENSION = 1000


class Widget(ABC):
    """Abstract base class for all UI widgets.

    Subclass this to create concrete widgets (labels, buttons, health
    bars, dialogs).  At minimum, override :meth:`draw` to render the
    widget's visual content into a :class:`~wyby.grid.CellBuffer`.

    Args:
        x: Column position of the widget's top-left corner in
            buffer coordinates.
        y: Row position of the widget's top-left corner in
            buffer coordinates.
        width: Width of the widget in columns.  Clamped to
            [1, 1000].
        height: Height of the widget in rows.  Clamped to
            [1, 1000].

    Raises:
        TypeError: If *x*, *y*, *width*, or *height* are not integers.

    Caveats:
        - Position (``x``, ``y``) can be negative.  This allows
          widgets to be partially off-screen (CellBuffer clips
          silently).  However, no special handling is done for
          negative positions — the widget simply draws at those
          coordinates and relies on CellBuffer clipping.
        - ``width`` and ``height`` are clamped, not validated.
          Passing ``width=0`` silently becomes ``width=1``.  This
          prevents zero-size widgets but may surprise callers who
          expect a ``ValueError``.
        - The base class does not allocate a ``__dict__``.  Subclasses
          that need custom attributes should either define their own
          ``__slots__`` or omit it (Python will add ``__dict__``
          automatically).
    """

    __slots__ = (
        "_x", "_y", "_width", "_height",
        "_visible", "_focused", "_parent", "_children",
        "_z_index",
    )

    def __init__(
        self,
        x: int = 0,
        y: int = 0,
        width: int = 1,
        height: int = 1,
        *,
        z_index: int = 0,
    ) -> None:
        if not isinstance(x, int) or isinstance(x, bool):
            msg = f"x must be an int, got {type(x).__name__}"
            raise TypeError(msg)
        if not isinstance(y, int) or isinstance(y, bool):
            msg = f"y must be an int, got {type(y).__name__}"
            raise TypeError(msg)
        if not isinstance(width, int) or isinstance(width, bool):
            msg = f"width must be an int, got {type(width).__name__}"
            raise TypeError(msg)
        if not isinstance(height, int) or isinstance(height, bool):
            msg = f"height must be an int, got {type(height).__name__}"
            raise TypeError(msg)
        if not isinstance(z_index, int) or isinstance(z_index, bool):
            msg = f"z_index must be an int, got {type(z_index).__name__}"
            raise TypeError(msg)

        self._x = x
        self._y = y
        self._width = max(_MIN_DIMENSION, min(width, _MAX_DIMENSION))
        self._height = max(_MIN_DIMENSION, min(height, _MAX_DIMENSION))
        self._z_index = z_index
        self._visible: bool = True
        self._focused: bool = False
        self._parent: Widget | None = None
        self._children: list[Widget] = []

    # -- Position properties ------------------------------------------------

    @property
    def x(self) -> int:
        """Column position of the widget's top-left corner."""
        return self._x

    @x.setter
    def x(self, value: int) -> None:
        if not isinstance(value, int) or isinstance(value, bool):
            msg = f"x must be an int, got {type(value).__name__}"
            raise TypeError(msg)
        self._x = value

    @property
    def y(self) -> int:
        """Row position of the widget's top-left corner."""
        return self._y

    @y.setter
    def y(self, value: int) -> None:
        if not isinstance(value, int) or isinstance(value, bool):
            msg = f"y must be an int, got {type(value).__name__}"
            raise TypeError(msg)
        self._y = value

    # -- Size properties ----------------------------------------------------

    @property
    def width(self) -> int:
        """Width of the widget in columns."""
        return self._width

    @width.setter
    def width(self, value: int) -> None:
        if not isinstance(value, int) or isinstance(value, bool):
            msg = f"width must be an int, got {type(value).__name__}"
            raise TypeError(msg)
        self._width = max(_MIN_DIMENSION, min(value, _MAX_DIMENSION))

    @property
    def height(self) -> int:
        """Height of the widget in rows."""
        return self._height

    @height.setter
    def height(self, value: int) -> None:
        if not isinstance(value, int) or isinstance(value, bool):
            msg = f"height must be an int, got {type(value).__name__}"
            raise TypeError(msg)
        self._height = max(_MIN_DIMENSION, min(value, _MAX_DIMENSION))

    # -- Z-order ------------------------------------------------------------

    @property
    def z_index(self) -> int:
        """Stacking order for overlay draw and hit-test sorting.

        Higher values render on top of lower values.  When two widgets
        share the same ``z_index``, the system that manages them
        (e.g., :class:`~wyby.renderer.Renderer` overlays or
        :class:`~wyby.focus.FocusManager`) uses registration order as
        the tiebreaker (last-added = topmost).

        Negative values are allowed.  There are no reserved ranges,
        but a common convention is:

        - ``z_index < 0`` — behind most game content
        - ``z_index == 0`` — default (game-level UI)
        - ``z_index > 0`` — above normal UI (tooltips, modals, popups)

        Caveat:
            Changing ``z_index`` does **not** trigger an automatic
            re-sort in the Renderer or FocusManager.  The sort happens
            each frame during :meth:`~wyby.renderer.Renderer.present`
            and each event during
            :meth:`~wyby.focus.FocusManager.dispatch`, so the new
            value takes effect on the next frame/event.
        """
        return self._z_index

    @z_index.setter
    def z_index(self, value: int) -> None:
        if not isinstance(value, int) or isinstance(value, bool):
            msg = f"z_index must be an int, got {type(value).__name__}"
            raise TypeError(msg)
        self._z_index = value

    # -- Visibility ---------------------------------------------------------

    @property
    def visible(self) -> bool:
        """Whether the widget should be drawn.

        When ``False``, the widget's :meth:`draw` method should skip
        rendering.  The base class does not enforce this — subclasses
        must check ``self.visible`` at the start of ``draw()`` and
        return early if ``False``.

        Caveat:
            Hiding a parent does **not** automatically hide children.
            If you want hierarchical visibility, check
            ``self.parent.visible`` (or walk up the tree) in your
            ``draw()`` override.
        """
        return self._visible

    @visible.setter
    def visible(self, value: bool) -> None:
        self._visible = bool(value)

    # -- Focus --------------------------------------------------------------

    @property
    def focused(self) -> bool:
        """Whether this widget currently has input focus.

        Focus is advisory — it does not automatically route events.
        The scene or UI manager is responsible for:

        1. Setting ``focused = True`` on the active widget.
        2. Setting ``focused = False`` on the previously focused widget.
        3. Calling :meth:`on_focus` and :meth:`on_blur` as appropriate.
        4. Routing input events to the focused widget.

        Caveat:
            Multiple widgets can have ``focused = True``
            simultaneously — there is no enforcement of single-focus.
            This is by design (e.g., a text input and a toolbar can
            both be "focused" in different input contexts), but it
            means the caller must manage focus consistently.
        """
        return self._focused

    @focused.setter
    def focused(self, value: bool) -> None:
        old = self._focused
        self._focused = bool(value)
        if old != self._focused:
            if self._focused:
                self.on_focus()
            else:
                self.on_blur()

    # -- Parent/child hierarchy ---------------------------------------------

    @property
    def parent(self) -> Widget | None:
        """The parent widget, or ``None`` if this is a root widget.

        Set internally by :meth:`add_child` / :meth:`remove_child`.
        Do not set ``_parent`` directly.
        """
        return self._parent

    @property
    def children(self) -> list[Widget]:
        """Read-only view of child widgets.

        Returns a shallow copy to prevent external mutation of the
        internal list.  Use :meth:`add_child` and :meth:`remove_child`
        to modify the hierarchy.

        Caveat:
            This returns a **copy** every call.  In tight loops,
            cache the result or iterate over ``_children`` directly
            in subclass code (internal use only).
        """
        return list(self._children)

    def add_child(self, child: Widget) -> None:
        """Add a child widget to this widget.

        The child's ``_parent`` is set to this widget.  If the child
        already has a parent, it is removed from the old parent first.

        Args:
            child: The widget to add as a child.

        Raises:
            TypeError: If *child* is not a :class:`Widget` instance.
            ValueError: If *child* is this widget (self-parenting).

        Caveats:
            - A widget can only have one parent.  Adding a child that
              is already parented elsewhere silently re-parents it.
            - Circular hierarchies (A → B → A) are **not** detected.
              Creating a cycle will cause infinite loops in any code
              that walks the widget tree.  This is the caller's
              responsibility to avoid.
            - Adding a child does not change its position.  The child
              retains its buffer-space coordinates.  The caller must
              update ``child.x`` / ``child.y`` if the child should be
              positioned relative to this widget.
        """
        if not isinstance(child, Widget):
            msg = f"child must be a Widget, got {type(child).__name__}"
            raise TypeError(msg)
        if child is self:
            msg = "a widget cannot be its own child"
            raise ValueError(msg)
        # Re-parent if already attached elsewhere.
        if child._parent is not None:
            child._parent.remove_child(child)
        child._parent = self
        self._children.append(child)
        _logger.debug(
            "Added child %r to %r (now %d children)",
            child, self, len(self._children),
        )

    def remove_child(self, child: Widget) -> None:
        """Remove a child widget from this widget.

        Args:
            child: The widget to remove.

        Raises:
            ValueError: If *child* is not a child of this widget.
        """
        try:
            self._children.remove(child)
        except ValueError:
            msg = f"{child!r} is not a child of {self!r}"
            raise ValueError(msg) from None
        child._parent = None
        _logger.debug(
            "Removed child %r from %r (now %d children)",
            child, self, len(self._children),
        )

    # -- Bounds checking ----------------------------------------------------

    def contains_point(self, px: int, py: int) -> bool:
        """Return whether the point (*px*, *py*) is inside this widget's bounds.

        Uses the widget's ``x``, ``y``, ``width``, and ``height`` for
        a simple axis-aligned bounding box test.

        Caveat:
            This is a geometric check only — it does not account for
            visibility, focus, or whether the widget is occluded by
            another widget drawn on top of it.
        """
        return (
            self._x <= px < self._x + self._width
            and self._y <= py < self._y + self._height
        )

    # -- Abstract methods ---------------------------------------------------

    @abstractmethod
    def draw(self, buffer: CellBuffer) -> None:
        """Render this widget into the given cell buffer.

        Subclasses must implement this to write their visual content
        into *buffer* using ``buffer.put()``, ``buffer.put_text()``,
        or ``buffer.draw_text()``.

        Args:
            buffer: The cell buffer to draw into.  The widget should
                draw at its own ``(x, y)`` position within the buffer.

        Caveats:
            - Subclasses should check ``self.visible`` and return
              early if ``False``.  The base class does not enforce
              this.
            - Drawing outside the buffer bounds is safe (CellBuffer
              clips silently) but wasteful.  Subclasses should avoid
              drawing when they know they are fully off-screen.
            - This method is called every frame.  Keep it fast.
              Avoid allocations and complex logic in ``draw()``.
            - Children are **not** drawn automatically.  If your
              widget has children, iterate ``self._children`` and
              call ``child.draw(buffer)`` on each.
        """

    # -- Event handling -----------------------------------------------------

    def handle_event(self, event: Event) -> bool:
        """Process an input event.

        Override in subclasses to respond to keyboard or mouse input.
        Return ``True`` if the event was consumed (handled), ``False``
        if it should be passed to other widgets or the scene.

        The default implementation returns ``False`` (event not
        consumed).

        Args:
            event: The event to process.

        Returns:
            ``True`` if the event was consumed, ``False`` otherwise.

        Caveats:
            - Events are **not** automatically routed to children.
              If your widget has focusable children, override this
              method to delegate events to the appropriate child.
            - The return value is advisory.  The caller (scene or
              UI manager) decides whether to respect the "consumed"
              signal.  There is no framework-enforced event
              consumption mechanism.
            - This method may be called even when the widget is not
              focused.  Check ``self.focused`` if you only want to
              respond when focused.
        """
        return False

    # -- Focus lifecycle hooks ----------------------------------------------

    def on_focus(self) -> None:
        """Called when this widget gains focus.

        Override in subclasses to update visual state (e.g., draw a
        highlight border) or start accepting input.

        The default implementation does nothing.

        Caveat:
            This is called by the ``focused`` property setter when
            the value changes from ``False`` to ``True``.  It is
            **not** called if ``focused`` is set to ``True`` when
            it is already ``True``.
        """

    def on_blur(self) -> None:
        """Called when this widget loses focus.

        Override in subclasses to update visual state (e.g., remove
        a highlight border) or stop accepting input.

        The default implementation does nothing.

        Caveat:
            This is called by the ``focused`` property setter when
            the value changes from ``True`` to ``False``.  It is
            **not** called if ``focused`` is set to ``False`` when
            it is already ``False``.
        """

    # -- Repr ---------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}("
            f"x={self._x}, y={self._y}, "
            f"w={self._width}, h={self._height}"
            f"{f', z={self._z_index}' if self._z_index != 0 else ''}"
            f"{', visible=False' if not self._visible else ''}"
            f"{', focused' if self._focused else ''}"
            f")"
        )
