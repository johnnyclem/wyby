"""Basic layout containers for positioning child widgets.

This module provides :class:`HBox` and :class:`VBox` — simple layout
containers that position their children horizontally or vertically
within a rectangular region.  They are :class:`~wyby.widget.Widget`
subclasses, so they compose naturally with the existing widget system.

Layout containers **set the x/y positions** of their children when
:meth:`apply_layout` is called (or automatically before each
:meth:`draw`).  Children retain their own width and height — the
container does not resize them.

Usage::

    from wyby.layout import HBox, VBox, Alignment
    from wyby.button import Button
    from wyby.grid import CellBuffer

    row = HBox(x=0, y=0, width=40, height=3, spacing=2)
    row.add_child(Button("OK", on_click=lambda: None))
    row.add_child(Button("Cancel", on_click=lambda: None))

    buf = CellBuffer(80, 24)
    row.draw(buf)  # positions children then draws them

Caveats:
    - **Not a flex layout.**  Children are placed sequentially along the
      main axis.  There is no flex-grow, flex-shrink, flex-wrap, or
      proportional sizing.  Children that overflow the container's bounds
      are still drawn (CellBuffer clips silently) but will visually
      extend outside the container.
    - **No automatic container sizing.**  The container's ``width`` and
      ``height`` must be set explicitly.  There is no "shrink-to-fit"
      or "grow-to-content" behaviour.  If you need the container to
      match its contents, compute the size manually and set it.
    - **Children are not clipped to the container.**  A child widget can
      draw outside the container's bounds.  CellBuffer's silent clipping
      prevents writes outside the buffer, but there is no per-container
      clip rectangle.
    - **Layout is recomputed on every draw.**  :meth:`apply_layout` is
      called at the start of each :meth:`draw` call.  For static UIs
      this is wasteful but harmless.  For dynamic UIs (widgets added/
      removed each frame), it ensures positions are always correct.  If
      performance is critical, call ``apply_layout()`` once after setup
      and set ``auto_layout = False``.
    - **Cross-axis alignment is basic.**  ``align`` controls positioning
      on the cross axis (vertical for HBox, horizontal for VBox).
      ``START`` places children at the container's origin, ``CENTER``
      centres them, ``END`` places them at the far edge.  There is no
      per-child alignment override.
    - **Padding is uniform.**  ``padding`` adds equal space on all four
      sides of the container's interior.  There is no per-side padding
      (top/right/bottom/left).
    - **Single-threaded.**  Layout mutation (adding/removing children,
      changing spacing/padding/alignment) is not thread-safe.  All
      layout operations must happen on the game loop thread.
    - **Z-index is inherited from Widget.**  Layout containers have their
      own ``z_index`` for overlay sorting, independent of child z-order.
      Children are drawn in list order within the container; z-index only
      matters when the container is composited with other overlays.
"""

from __future__ import annotations

import enum
import logging
from typing import TYPE_CHECKING

from wyby.widget import Widget

if TYPE_CHECKING:
    from wyby.event import Event
    from wyby.grid import CellBuffer

_logger = logging.getLogger(__name__)


class Alignment(enum.Enum):
    """Cross-axis alignment for layout containers.

    Determines where children are positioned on the axis perpendicular
    to the layout direction:

    - For :class:`HBox` (horizontal layout), alignment controls the
      **vertical** position of children within the container.
    - For :class:`VBox` (vertical layout), alignment controls the
      **horizontal** position of children within the container.

    Values:
        START: Align to the top (HBox) or left (VBox) edge.
        CENTER: Centre on the cross axis.
        END: Align to the bottom (HBox) or right (VBox) edge.

    Caveat:
        Alignment uses integer division for centering, so odd-pixel
        remainders are truncated (shifted toward START).  This is
        inherent to cell-based positioning — there is no sub-cell
        precision.
    """

    START = "start"
    CENTER = "center"
    END = "end"


class HBox(Widget):
    """Horizontal layout container — children are placed left to right.

    Positions children sequentially along the x-axis within the
    container's bounds, respecting ``padding`` and ``spacing``.

    Args:
        x: Column position of the container's top-left corner.
        y: Row position of the container's top-left corner.
        width: Width of the container in columns.
        height: Height of the container in rows.
        spacing: Number of columns between adjacent children.
            Default 0 (children are packed tightly).
        padding: Number of cells of inner padding on all sides.
            Default 0.
        align: Cross-axis (vertical) alignment of children within
            the container.  Default :attr:`Alignment.START`.
        auto_layout: Whether to call :meth:`apply_layout` automatically
            at the start of each :meth:`draw`.  Default ``True``.
            Set to ``False`` for manual layout control.
        z_index: Stacking order for overlay compositing.

    Caveats:
        - Children are placed in :meth:`add_child` order.  There is
          no reordering, sorting, or priority mechanism.
        - If children overflow the container width (total child widths
          + spacing + padding > container width), the excess children
          are still positioned but will extend past the right edge.
          No wrapping occurs.
        - Spacing is only added **between** children, not before the
          first or after the last.
    """

    __slots__ = ("_spacing", "_padding", "_align", "_auto_layout")

    def __init__(
        self,
        x: int = 0,
        y: int = 0,
        width: int = 1,
        height: int = 1,
        *,
        spacing: int = 0,
        padding: int = 0,
        align: Alignment = Alignment.START,
        auto_layout: bool = True,
        z_index: int = 0,
    ) -> None:
        if not isinstance(spacing, int) or isinstance(spacing, bool):
            msg = f"spacing must be an int, got {type(spacing).__name__}"
            raise TypeError(msg)
        if not isinstance(padding, int) or isinstance(padding, bool):
            msg = f"padding must be an int, got {type(padding).__name__}"
            raise TypeError(msg)
        if not isinstance(align, Alignment):
            msg = f"align must be an Alignment, got {type(align).__name__}"
            raise TypeError(msg)
        if spacing < 0:
            msg = f"spacing must be >= 0, got {spacing}"
            raise ValueError(msg)
        if padding < 0:
            msg = f"padding must be >= 0, got {padding}"
            raise ValueError(msg)

        super().__init__(x=x, y=y, width=width, height=height, z_index=z_index)
        self._spacing = spacing
        self._padding = padding
        self._align = align
        self._auto_layout = bool(auto_layout)

    # -- Properties ---------------------------------------------------------

    @property
    def spacing(self) -> int:
        """Number of columns between adjacent children."""
        return self._spacing

    @spacing.setter
    def spacing(self, value: int) -> None:
        if not isinstance(value, int) or isinstance(value, bool):
            msg = f"spacing must be an int, got {type(value).__name__}"
            raise TypeError(msg)
        if value < 0:
            msg = f"spacing must be >= 0, got {value}"
            raise ValueError(msg)
        self._spacing = value

    @property
    def padding(self) -> int:
        """Number of cells of inner padding on all sides."""
        return self._padding

    @padding.setter
    def padding(self, value: int) -> None:
        if not isinstance(value, int) or isinstance(value, bool):
            msg = f"padding must be an int, got {type(value).__name__}"
            raise TypeError(msg)
        if value < 0:
            msg = f"padding must be >= 0, got {value}"
            raise ValueError(msg)
        self._padding = value

    @property
    def align(self) -> Alignment:
        """Cross-axis (vertical) alignment of children."""
        return self._align

    @align.setter
    def align(self, value: Alignment) -> None:
        if not isinstance(value, Alignment):
            msg = f"align must be an Alignment, got {type(value).__name__}"
            raise TypeError(msg)
        self._align = value

    @property
    def auto_layout(self) -> bool:
        """Whether layout is recomputed automatically on each draw."""
        return self._auto_layout

    @auto_layout.setter
    def auto_layout(self, value: bool) -> None:
        self._auto_layout = bool(value)

    # -- Layout computation -------------------------------------------------

    def apply_layout(self) -> None:
        """Position children left-to-right within the container.

        Sets each child's ``x`` and ``y`` based on the container's
        position, padding, spacing, and cross-axis alignment.  Children
        retain their own width and height.

        This is called automatically at the start of :meth:`draw` when
        ``auto_layout`` is ``True``.  Call it manually after modifying
        children or layout properties if ``auto_layout`` is ``False``.

        Caveat:
            Only positions **visible** children.  Invisible children are
            skipped and do not consume space in the layout.  This means
            hiding a child shifts subsequent children leftward.  If you
            want invisible children to reserve space, manage positioning
            manually.
        """
        cursor_x = self._x + self._padding
        inner_height = self._height - 2 * self._padding
        first = True

        for child in self._children:
            if not child.visible:
                continue

            if not first:
                cursor_x += self._spacing
            first = False

            # Cross-axis alignment (vertical).
            child.x = cursor_x
            if self._align == Alignment.START:
                child.y = self._y + self._padding
            elif self._align == Alignment.CENTER:
                child.y = self._y + self._padding + (inner_height - child.height) // 2
            else:  # END
                child.y = self._y + self._padding + inner_height - child.height

            cursor_x += child.width

    # -- Drawing ------------------------------------------------------------

    def draw(self, buffer: CellBuffer) -> None:
        """Apply layout and draw all visible children.

        Calls :meth:`apply_layout` (if ``auto_layout`` is ``True``),
        then iterates children in order and calls ``draw()`` on each
        visible child.

        Skips entirely if ``self.visible`` is ``False``.

        Caveat:
            The container itself draws nothing — it is invisible.  Only
            children produce visual output.  If you need a background or
            border, subclass and draw them before calling
            ``super().draw(buffer)``.
        """
        if not self.visible:
            return
        if self._auto_layout:
            self.apply_layout()
        for child in self._children:
            if child.visible:
                child.draw(buffer)

    # -- Event handling -----------------------------------------------------

    def handle_event(self, event: Event) -> bool:
        """Route event to children in reverse order (topmost first).

        Iterates children back-to-front (last child = topmost in draw
        order) and calls ``handle_event`` on each.  Returns ``True``
        as soon as any child consumes the event.

        Caveat:
            This is a simple linear scan, not z-order aware.  Children
            are checked in reverse insertion order.  For overlapping
            children, the last-added child gets first chance to handle
            the event.
        """
        for child in reversed(self._children):
            if child.visible and child.handle_event(event):
                return True
        return False

    # -- Repr ---------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"HBox("
            f"x={self._x}, y={self._y}, "
            f"w={self._width}, h={self._height}, "
            f"spacing={self._spacing}, padding={self._padding}, "
            f"children={len(self._children)}"
            f")"
        )


class VBox(Widget):
    """Vertical layout container — children are placed top to bottom.

    Positions children sequentially along the y-axis within the
    container's bounds, respecting ``padding`` and ``spacing``.

    Args:
        x: Column position of the container's top-left corner.
        y: Row position of the container's top-left corner.
        width: Width of the container in columns.
        height: Height of the container in rows.
        spacing: Number of rows between adjacent children.
            Default 0 (children are packed tightly).
        padding: Number of cells of inner padding on all sides.
            Default 0.
        align: Cross-axis (horizontal) alignment of children within
            the container.  Default :attr:`Alignment.START`.
        auto_layout: Whether to call :meth:`apply_layout` automatically
            at the start of each :meth:`draw`.  Default ``True``.
            Set to ``False`` for manual layout control.
        z_index: Stacking order for overlay compositing.

    Caveats:
        - Children are placed in :meth:`add_child` order.  There is
          no reordering, sorting, or priority mechanism.
        - If children overflow the container height (total child heights
          + spacing + padding > container height), the excess children
          are still positioned but will extend past the bottom edge.
          No wrapping occurs.
        - Spacing is only added **between** children, not before the
          first or after the last.
    """

    __slots__ = ("_spacing", "_padding", "_align", "_auto_layout")

    def __init__(
        self,
        x: int = 0,
        y: int = 0,
        width: int = 1,
        height: int = 1,
        *,
        spacing: int = 0,
        padding: int = 0,
        align: Alignment = Alignment.START,
        auto_layout: bool = True,
        z_index: int = 0,
    ) -> None:
        if not isinstance(spacing, int) or isinstance(spacing, bool):
            msg = f"spacing must be an int, got {type(spacing).__name__}"
            raise TypeError(msg)
        if not isinstance(padding, int) or isinstance(padding, bool):
            msg = f"padding must be an int, got {type(padding).__name__}"
            raise TypeError(msg)
        if not isinstance(align, Alignment):
            msg = f"align must be an Alignment, got {type(align).__name__}"
            raise TypeError(msg)
        if spacing < 0:
            msg = f"spacing must be >= 0, got {spacing}"
            raise ValueError(msg)
        if padding < 0:
            msg = f"padding must be >= 0, got {padding}"
            raise ValueError(msg)

        super().__init__(x=x, y=y, width=width, height=height, z_index=z_index)
        self._spacing = spacing
        self._padding = padding
        self._align = align
        self._auto_layout = bool(auto_layout)

    # -- Properties ---------------------------------------------------------

    @property
    def spacing(self) -> int:
        """Number of rows between adjacent children."""
        return self._spacing

    @spacing.setter
    def spacing(self, value: int) -> None:
        if not isinstance(value, int) or isinstance(value, bool):
            msg = f"spacing must be an int, got {type(value).__name__}"
            raise TypeError(msg)
        if value < 0:
            msg = f"spacing must be >= 0, got {value}"
            raise ValueError(msg)
        self._spacing = value

    @property
    def padding(self) -> int:
        """Number of cells of inner padding on all sides."""
        return self._padding

    @padding.setter
    def padding(self, value: int) -> None:
        if not isinstance(value, int) or isinstance(value, bool):
            msg = f"padding must be an int, got {type(value).__name__}"
            raise TypeError(msg)
        if value < 0:
            msg = f"padding must be >= 0, got {value}"
            raise ValueError(msg)
        self._padding = value

    @property
    def align(self) -> Alignment:
        """Cross-axis (horizontal) alignment of children."""
        return self._align

    @align.setter
    def align(self, value: Alignment) -> None:
        if not isinstance(value, Alignment):
            msg = f"align must be an Alignment, got {type(value).__name__}"
            raise TypeError(msg)
        self._align = value

    @property
    def auto_layout(self) -> bool:
        """Whether layout is recomputed automatically on each draw."""
        return self._auto_layout

    @auto_layout.setter
    def auto_layout(self, value: bool) -> None:
        self._auto_layout = bool(value)

    # -- Layout computation -------------------------------------------------

    def apply_layout(self) -> None:
        """Position children top-to-bottom within the container.

        Sets each child's ``x`` and ``y`` based on the container's
        position, padding, spacing, and cross-axis alignment.  Children
        retain their own width and height.

        This is called automatically at the start of :meth:`draw` when
        ``auto_layout`` is ``True``.  Call it manually after modifying
        children or layout properties if ``auto_layout`` is ``False``.

        Caveat:
            Only positions **visible** children.  Invisible children are
            skipped and do not consume space in the layout.  This means
            hiding a child shifts subsequent children upward.  If you
            want invisible children to reserve space, manage positioning
            manually.
        """
        cursor_y = self._y + self._padding
        inner_width = self._width - 2 * self._padding
        first = True

        for child in self._children:
            if not child.visible:
                continue

            if not first:
                cursor_y += self._spacing
            first = False

            # Cross-axis alignment (horizontal).
            child.y = cursor_y
            if self._align == Alignment.START:
                child.x = self._x + self._padding
            elif self._align == Alignment.CENTER:
                child.x = self._x + self._padding + (inner_width - child.width) // 2
            else:  # END
                child.x = self._x + self._padding + inner_width - child.width

            cursor_y += child.height

    # -- Drawing ------------------------------------------------------------

    def draw(self, buffer: CellBuffer) -> None:
        """Apply layout and draw all visible children.

        Calls :meth:`apply_layout` (if ``auto_layout`` is ``True``),
        then iterates children in order and calls ``draw()`` on each
        visible child.

        Skips entirely if ``self.visible`` is ``False``.

        Caveat:
            The container itself draws nothing — it is invisible.  Only
            children produce visual output.  If you need a background or
            border, subclass and draw them before calling
            ``super().draw(buffer)``.
        """
        if not self.visible:
            return
        if self._auto_layout:
            self.apply_layout()
        for child in self._children:
            if child.visible:
                child.draw(buffer)

    # -- Event handling -----------------------------------------------------

    def handle_event(self, event: Event) -> bool:
        """Route event to children in reverse order (topmost first).

        Iterates children back-to-front (last child = topmost in draw
        order) and calls ``handle_event`` on each.  Returns ``True``
        as soon as any child consumes the event.

        Caveat:
            This is a simple linear scan, not z-order aware.  Children
            are checked in reverse insertion order.  For overlapping
            children, the last-added child gets first chance to handle
            the event.
        """
        for child in reversed(self._children):
            if child.visible and child.handle_event(event):
                return True
        return False

    # -- Repr ---------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"VBox("
            f"x={self._x}, y={self._y}, "
            f"w={self._width}, h={self._height}, "
            f"spacing={self._spacing}, padding={self._padding}, "
            f"children={len(self._children)}"
            f")"
        )
