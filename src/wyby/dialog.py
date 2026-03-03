"""Dialog widget — a bordered panel with title, body text, and buttons.

This module provides a :class:`Dialog` widget for presenting modal-style
prompts to the player: confirmations ("Really quit?"), informational
messages ("You found a key!"), or choices ("Save and quit / Keep playing").

A Dialog is a composite :class:`~wyby.widget.Widget` that draws:

1. A box-drawing border (``─│┌┐└┘``) filling its width × height.
2. A title string centred on the top border row.
3. A body text line inside the bordered area.
4. A row of :class:`~wyby.button.Button` children along the bottom.

Usage::

    from wyby.dialog import Dialog
    from wyby.button import Button
    from wyby.grid import CellBuffer

    def on_yes() -> None:
        print("Confirmed!")

    dlg = Dialog(
        title="Confirm",
        body="Are you sure?",
        x=10, y=5, width=30, height=7,
    )
    dlg.add_button("Yes", on_click=on_yes)
    dlg.add_button("No", on_click=lambda: None)

    buf = CellBuffer(80, 24)
    dlg.draw(buf)

    # Route events (keyboard / mouse) to the dialog:
    consumed = dlg.handle_event(some_event)

Caveats:
    - **This is a stub.**  The Dialog widget provides basic border
      drawing, title, body text, and button hosting.  It does **not**
      implement advanced features such as word-wrap, scrollable body
      content, automatic sizing, animation, or a built-in "modal"
      input-blocking layer.  These may be added in future iterations.
    - **No modal input blocking.**  The dialog does not intercept or
      swallow events that fall outside its bounds.  To get true modal
      behaviour (blocking clicks on widgets behind the dialog), the
      scene or UI manager must stop routing events to other widgets
      while the dialog is visible.  Alternatively, push a dedicated
      dialog scene onto the :class:`~wyby.scene.SceneStack`.
    - **Body text is a single line.**  The ``body`` string is drawn
      on a single row inside the dialog.  Text that exceeds the inner
      width is silently clipped by :class:`~wyby.grid.CellBuffer`.
      Multi-line body content is not supported — use multiple Dialog
      widgets, compose your own layout, or wait for a future rich-text
      widget.
    - **Title is truncated, not wrapped.**  If the title string is
      wider than the inner border (``width - 4``), it is truncated to
      fit.  No ellipsis is appended.
    - **Button layout is left-aligned.**  Buttons are placed left to
      right inside the dialog's bottom row area with 1 cell of spacing.
      There is no centre-align or right-align option for buttons.  To
      customise button placement, position them manually as children
      instead of using :meth:`add_button`.
    - **Border uses ASCII-range box-drawing characters.**  The border
      uses Unicode box-drawing characters (``─│┌┐└┘``) which display
      correctly on most modern terminals.  Legacy terminals that lack
      box-drawing support will render fallback glyphs.  There is no
      ASCII-only fallback mode.
    - **No background fill.**  The dialog draws its border and text
      content but does **not** fill the interior with a background
      colour.  Whatever was previously in the CellBuffer behind the
      dialog will show through.  To get an opaque dialog, fill the
      interior cells manually before drawing, or draw a filled
      rectangle into the buffer at the dialog's position.
    - **Focus cycling is manual.**  The dialog does not implement
      Tab/Shift-Tab focus cycling between its buttons.  The caller
      (scene or :class:`~wyby.focus.FocusManager`) is responsible for
      managing focus among the dialog's children.  The dialog's own
      ``focused`` flag is independent of its children's focus state.
    - **Children are not clipped to the border.**  Buttons or other
      child widgets added to the dialog can draw outside the bordered
      area.  CellBuffer's silent clipping prevents buffer overflows,
      but the visual result may be unexpected.
    - **Single-threaded.**  Like all wyby widgets, Dialog must be
      created, modified, and drawn on the game loop thread.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable

from wyby.button import Button
from wyby.widget import Widget

if TYPE_CHECKING:
    from wyby.event import Event
    from wyby.grid import CellBuffer

_logger = logging.getLogger(__name__)

# Box-drawing characters for the dialog border.
_BORDER_TOP_LEFT = "┌"
_BORDER_TOP_RIGHT = "┐"
_BORDER_BOTTOM_LEFT = "└"
_BORDER_BOTTOM_RIGHT = "┘"
_BORDER_HORIZONTAL = "─"
_BORDER_VERTICAL = "│"

# Minimum dialog dimensions to fit border + 1 interior column/row.
_MIN_WIDTH = 4   # │ + 1 content col + │ + margin
_MIN_HEIGHT = 3  # top border + 1 content row + bottom border

# Spacing between buttons in the button row.
_BUTTON_SPACING = 1


class Dialog(Widget):
    """A bordered dialog box with title, body text, and action buttons.

    The dialog draws a box-drawing border, an optional title centred
    on the top edge, a single-line body message, and hosts
    :class:`~wyby.button.Button` children for user interaction.

    Args:
        title: Text displayed on the top border.  May be empty.
        body: Single-line message displayed inside the dialog.  May
            be empty.
        x: Column position of the dialog's top-left corner.
        y: Row position of the dialog's top-left corner.
        width: Total width including borders.  Clamped to a minimum
            of 4 to fit the border and at least one interior column.
        height: Total height including borders.  Clamped to a minimum
            of 3 to fit top border, one content row, and bottom border.

    Raises:
        TypeError: If *title* or *body* is not a string.

    Caveats:
        - Dimensions smaller than the minimum (4×3) are silently
          clamped.  The caller is not warned.
        - The title and body are **not** stored as child widgets.
          They are drawn directly by :meth:`draw`.  Only buttons
          added via :meth:`add_button` are children in the widget
          hierarchy.
    """

    __slots__ = ("_title", "_body", "_buttons")

    def __init__(
        self,
        title: str = "",
        body: str = "",
        x: int = 0,
        y: int = 0,
        width: int = 30,
        height: int = 7,
        *,
        z_index: int = 0,
    ) -> None:
        if not isinstance(title, str):
            msg = f"title must be a str, got {type(title).__name__}"
            raise TypeError(msg)
        if not isinstance(body, str):
            msg = f"body must be a str, got {type(body).__name__}"
            raise TypeError(msg)

        # Enforce minimum size for a usable dialog.
        width = max(width, _MIN_WIDTH)
        height = max(height, _MIN_HEIGHT)

        super().__init__(x=x, y=y, width=width, height=height, z_index=z_index)

        self._title = title
        self._body = body
        self._buttons: list[Button] = []

    # -- Properties ---------------------------------------------------------

    @property
    def title(self) -> str:
        """The dialog's title text, displayed on the top border.

        Caveat:
            Changing the title does not resize the dialog.  If the
            new title is wider than the interior, it will be truncated.
        """
        return self._title

    @title.setter
    def title(self, value: str) -> None:
        if not isinstance(value, str):
            msg = f"title must be a str, got {type(value).__name__}"
            raise TypeError(msg)
        self._title = value

    @property
    def body(self) -> str:
        """The dialog's body text, displayed inside the bordered area.

        Caveat:
            Changing the body does not resize the dialog.  Text wider
            than the interior is silently clipped by CellBuffer.
        """
        return self._body

    @body.setter
    def body(self, value: str) -> None:
        if not isinstance(value, str):
            msg = f"body must be a str, got {type(value).__name__}"
            raise TypeError(msg)
        self._body = value

    @property
    def buttons(self) -> list[Button]:
        """Read-only copy of the dialog's buttons.

        Use :meth:`add_button` and :meth:`remove_button` to modify.
        """
        return list(self._buttons)

    # -- Button management --------------------------------------------------

    def add_button(
        self,
        label: str,
        on_click: Callable[[], object] | None = None,
    ) -> Button:
        """Create and add a :class:`~wyby.button.Button` to the dialog.

        The button is added as a child widget and positioned inside the
        dialog by :meth:`_layout_buttons` (called during :meth:`draw`).

        Args:
            label: Button label text.
            on_click: Callback invoked when the button is activated.

        Returns:
            The newly created :class:`~wyby.button.Button`.

        Caveats:
            - Buttons that overflow the dialog width are still drawn
              (CellBuffer clips silently) but extend outside the border.
            - The button's position is overwritten each frame by
              ``_layout_buttons``.  Setting ``x``/``y`` manually on
              a button added via this method has no lasting effect.
        """
        btn = Button(label, on_click=on_click)
        self._buttons.append(btn)
        self.add_child(btn)
        _logger.debug(
            "Dialog %r: added button %r (now %d buttons)",
            self._title, label, len(self._buttons),
        )
        return btn

    def remove_button(self, button: Button) -> None:
        """Remove a button previously added via :meth:`add_button`.

        Args:
            button: The button to remove.

        Raises:
            ValueError: If *button* is not in this dialog's button list.
        """
        try:
            self._buttons.remove(button)
        except ValueError:
            msg = f"{button!r} is not a button of this dialog"
            raise ValueError(msg) from None
        self.remove_child(button)
        _logger.debug(
            "Dialog %r: removed button %r (now %d buttons)",
            self._title, button.label, len(self._buttons),
        )

    # -- Internal layout ----------------------------------------------------

    def _layout_buttons(self) -> None:
        """Position buttons left-to-right inside the dialog's bottom area.

        Buttons are placed on the row just above the bottom border
        (``self.y + self.height - 2``), starting one cell inside the
        left border (``self.x + 1``), with ``_BUTTON_SPACING`` cells
        between them.

        Caveat:
            Only called during :meth:`draw`.  If you query button
            positions between draws, they may be stale.
        """
        cursor_x = self._x + 1  # 1 cell inside left border
        btn_y = self._y + self._height - 2  # row above bottom border

        for i, btn in enumerate(self._buttons):
            if not btn.visible:
                continue
            if i > 0:
                cursor_x += _BUTTON_SPACING
            btn.x = cursor_x
            btn.y = btn_y
            cursor_x += btn.width

    # -- Drawing ------------------------------------------------------------

    def draw(self, buffer: CellBuffer) -> None:
        """Render the dialog border, title, body, and buttons into *buffer*.

        Drawing order:

        1. Box-drawing border (corners, horizontal edges, vertical edges).
        2. Title text centred on the top border row.
        3. Body text on the first interior row.
        4. Button children (positioned by ``_layout_buttons``).

        Skips drawing if ``self.visible`` is ``False``.

        Caveats:
            - The interior is **not** cleared or filled.  Pre-existing
              buffer content shows through between the border, title,
              body, and buttons.  To get an opaque dialog, fill the
              interior region of the buffer before calling this method.
            - Partially off-screen dialogs clip silently.  No error is
              raised if the dialog extends beyond buffer bounds.
            - Drawing performance scales with dialog perimeter (border
              cells) plus children.  Very large dialogs on very small
              terminals are wasteful but harmless.
        """
        if not self.visible:
            return

        x, y, w, h = self._x, self._y, self._width, self._height

        # -- Border --
        # Top row: ┌──...──┐
        buffer.put_text(x, y, _BORDER_TOP_LEFT)
        for col in range(1, w - 1):
            buffer.put_text(x + col, y, _BORDER_HORIZONTAL)
        buffer.put_text(x + w - 1, y, _BORDER_TOP_RIGHT)

        # Bottom row: └──...──┘
        buffer.put_text(x, y + h - 1, _BORDER_BOTTOM_LEFT)
        for col in range(1, w - 1):
            buffer.put_text(x + col, y + h - 1, _BORDER_HORIZONTAL)
        buffer.put_text(x + w - 1, y + h - 1, _BORDER_BOTTOM_RIGHT)

        # Side edges: │ on each interior row.
        for row in range(1, h - 1):
            buffer.put_text(x, y + row, _BORDER_VERTICAL)
            buffer.put_text(x + w - 1, y + row, _BORDER_VERTICAL)

        # -- Title (centred on top border row) --
        if self._title:
            inner_width = w - 2  # space between corner chars
            display_title = self._title[:inner_width]  # truncate if needed
            # Centre within the inner width, offset by 1 for left border.
            offset = (inner_width - len(display_title)) // 2
            buffer.put_text(x + 1 + offset, y, display_title, bold=True)

        # -- Body text (first interior row) --
        if self._body:
            # Draw body on row y+1, column x+1 (inside border).
            buffer.put_text(x + 1, y + 1, self._body)

        # -- Buttons --
        self._layout_buttons()
        for btn in self._buttons:
            if btn.visible:
                btn.draw(buffer)

    # -- Event handling -----------------------------------------------------

    def handle_event(self, event: Event) -> bool:
        """Route events to child buttons in reverse order.

        Buttons are checked back-to-front (last-added = topmost) so
        that overlapping buttons behave consistently with draw order.

        Mouse events that hit the dialog's border/interior area (but
        not a button) are consumed to prevent click-through to widgets
        behind the dialog.

        Keyboard events are delegated to buttons only.  The dialog
        itself does not respond to keyboard input.

        Returns:
            ``True`` if the event was consumed, ``False`` otherwise.

        Caveats:
            - Only buttons added via :meth:`add_button` receive events.
              Other children added via :meth:`add_child` directly are
              **not** checked by this method.
            - Mouse consumption is geometric only — the dialog does
              not know if it is visually occluded by another widget.
              The scene must route events in z-order for correct
              layering.
        """
        # Let buttons handle first (reverse order = last added first).
        for btn in reversed(self._buttons):
            if btn.visible and btn.handle_event(event):
                return True

        # Consume mouse presses inside the dialog bounds to prevent
        # click-through.  Import here to avoid circular imports.
        from wyby.input import MouseEvent

        if isinstance(event, MouseEvent):
            if event.action == "press" and self.contains_point(event.x, event.y):
                _logger.debug(
                    "Dialog %r consumed click at (%d, %d) — no button hit",
                    self._title, event.x, event.y,
                )
                return True

        return False

    # -- Repr ---------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"Dialog("
            f"title={self._title!r}, "
            f"x={self._x}, y={self._y}, "
            f"w={self._width}, h={self._height}, "
            f"buttons={len(self._buttons)}"
            f")"
        )
