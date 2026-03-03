"""Single-line text input widget with focus-gated keyboard handling.

This module provides a :class:`TextInput` widget that accepts keyboard
input only when focused.  It renders a single-line editable text field
into a :class:`~wyby.grid.CellBuffer` and supports cursor movement,
character insertion, deletion, and a submit callback.

The ``TextInput`` is the canonical example of **focus-gated input
handling** in wyby.  Unlike :class:`~wyby.button.Button` (which
responds to mouse clicks regardless of focus), ``TextInput`` ignores
all keyboard events unless ``self.focused`` is ``True``.  This ensures
that only the active text field receives typed characters when multiple
input widgets are on screen.

Usage::

    from wyby.text_input import TextInput
    from wyby.focus import FocusManager
    from wyby.grid import CellBuffer

    def on_submit(text: str) -> None:
        print(f"Submitted: {text}")

    field = TextInput(x=5, y=10, width=20, on_submit=on_submit)

    fm = FocusManager()
    fm.add(field)

    # In your event loop:
    for event in events:
        fm.dispatch(event)  # Routes events, manages focus

    # In your render loop:
    buf = CellBuffer(80, 24)
    field.draw(buf)

Caveats:
    - **Focus is required for keyboard input.**  The widget returns
      ``False`` (event not consumed) for all :class:`~wyby.input.KeyEvent`
      instances unless ``self.focused`` is ``True``.  This is by design
      — the :class:`~wyby.focus.FocusManager` or scene must set focus
      before the widget will accept typed characters.  Without focus
      management, the widget appears unresponsive to keyboard input.
    - **Mouse clicks consume but do not type.**  A left-button press
      inside the widget's bounds returns ``True`` (consumed) to support
      click-to-focus via :class:`~wyby.focus.FocusManager`, but does
      not insert text or move the cursor.  Click-to-position-cursor is
      not implemented.
    - **Single-line only.**  There is no line wrapping, vertical
      scrolling, or multi-line support.  The Enter key triggers the
      ``on_submit`` callback rather than inserting a newline.
    - **No horizontal scrolling.**  Text that exceeds the widget's
      ``width`` is truncated in the display.  The internal text buffer
      can hold more characters than are visible, but the user cannot
      see or interact with the hidden portion.  A future version may
      add viewport scrolling.
    - **No clipboard support.**  There is no paste (Ctrl+V), cut
      (Ctrl+X), or copy (Ctrl+C) functionality.  Terminal clipboard
      access is not standardised and varies across platforms and
      terminal emulators.
    - **No undo/redo.**  There is no edit history or Ctrl+Z support.
    - **No selection.**  There is no text selection (Shift+Arrow) or
      select-all (Ctrl+A).  These features require a selection model
      that is out of scope for v0.1.
    - **Cursor position is logical, not visual.**  The ``cursor``
      property tracks the index into the Python string, not the
      terminal column.  For ASCII text these are identical, but for
      wide characters (CJK, emoji) the visual cursor position may
      differ from the logical index.  See
      :func:`wyby.unicode.string_width` for display width calculation.
    - **No IME support.**  Input Method Editor composition (for CJK
      languages) is not supported.  The widget processes raw
      :class:`~wyby.input.KeyEvent` objects, which represent
      already-committed characters.
    - **Callback exceptions propagate.**  If ``on_submit`` or
      ``on_change`` raises, the exception propagates to the caller.
      The widget does not catch or suppress callback errors.
    - **Single-threaded.**  Widget mutation is not thread-safe.
      All operations must happen on the game loop thread.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable

from wyby.widget import Widget

if TYPE_CHECKING:
    from wyby.event import Event
    from wyby.grid import CellBuffer

_logger = logging.getLogger(__name__)


class TextInput(Widget):
    """A single-line text input widget with focus-gated keyboard handling.

    The widget displays editable text and a cursor indicator.  Keyboard
    input is only accepted when ``self.focused`` is ``True``, making
    this widget the canonical example of focus-dependent input handling
    in wyby.

    Args:
        x: Column position of the widget's top-left corner.
        y: Row position of the widget's top-left corner.
        width: Display width in columns.  Minimum 3 (to show at least
            one character plus borders).  Clamped by the base class.
        max_length: Maximum number of characters allowed in the text
            buffer.  ``None`` means unlimited (up to memory).  When
            set, typed characters are silently rejected once the limit
            is reached.
        on_submit: Callback invoked when Enter is pressed while
            focused.  Receives the current text as its argument.
            May be ``None``.
        on_change: Callback invoked whenever the text content changes
            (character typed, deleted, or text set programmatically via
            the ``text`` property).  Receives the new text as its
            argument.  May be ``None``.

    Raises:
        TypeError: If *max_length* is not an int or ``None``, or if
            callbacks are not callable.

    Caveats:
        - Width is the **display** width, not the text capacity.
          The internal text buffer can hold more characters than fit
          on screen.  Only ``max_length`` limits the buffer size.
        - Height is always 1.  The base class will clamp any other
          value.
        - The widget does **not** draw a border or box.  It renders
          the text content directly at ``(x, y)``.  Wrap it in a
          :class:`~wyby.dialog.Dialog` or custom container if you
          need a visual frame.
    """

    __slots__ = (
        "_text", "_cursor", "_max_length",
        "_on_submit", "_on_change",
    )

    def __init__(
        self,
        x: int = 0,
        y: int = 0,
        width: int = 20,
        *,
        max_length: int | None = None,
        on_submit: Callable[[str], object] | None = None,
        on_change: Callable[[str], object] | None = None,
    ) -> None:
        if max_length is not None:
            if not isinstance(max_length, int) or isinstance(max_length, bool):
                msg = f"max_length must be an int or None, got {type(max_length).__name__}"
                raise TypeError(msg)
            if max_length < 0:
                msg = f"max_length must be non-negative, got {max_length}"
                raise ValueError(msg)
        if on_submit is not None and not callable(on_submit):
            msg = f"on_submit must be callable or None, got {type(on_submit).__name__}"
            raise TypeError(msg)
        if on_change is not None and not callable(on_change):
            msg = f"on_change must be callable or None, got {type(on_change).__name__}"
            raise TypeError(msg)

        super().__init__(x=x, y=y, width=width, height=1)

        self._text: str = ""
        self._cursor: int = 0
        self._max_length = max_length
        self._on_submit = on_submit
        self._on_change = on_change

    # -- Properties ---------------------------------------------------------

    @property
    def text(self) -> str:
        """The current text content.

        Setting this replaces the entire text buffer and clamps the
        cursor to the new length.  Triggers ``on_change`` if set.

        Caveat:
            Setting ``text`` does **not** enforce ``max_length``.
            Programmatic assignment bypasses the limit — only keyboard
            input is gated.  This allows pre-populating the field with
            a value that exceeds the typing limit if needed.
        """
        return self._text

    @text.setter
    def text(self, value: str) -> None:
        if not isinstance(value, str):
            msg = f"text must be a str, got {type(value).__name__}"
            raise TypeError(msg)
        old = self._text
        self._text = value
        # Clamp cursor to valid range after text change.
        self._cursor = min(self._cursor, len(value))
        if old != value and self._on_change is not None:
            self._on_change(value)

    @property
    def cursor(self) -> int:
        """The cursor position (index into the text string).

        The cursor sits *between* characters: position 0 is before the
        first character, position ``len(text)`` is after the last.

        Caveat:
            This is a logical index, not a visual column.  For wide
            characters (CJK), the visual position differs from the
            index.
        """
        return self._cursor

    @property
    def max_length(self) -> int | None:
        """Maximum character count, or ``None`` for unlimited."""
        return self._max_length

    @property
    def on_submit(self) -> Callable[[str], object] | None:
        """Callback invoked on Enter key press."""
        return self._on_submit

    @on_submit.setter
    def on_submit(self, value: Callable[[str], object] | None) -> None:
        if value is not None and not callable(value):
            msg = f"on_submit must be callable or None, got {type(value).__name__}"
            raise TypeError(msg)
        self._on_submit = value

    @property
    def on_change(self) -> Callable[[str], object] | None:
        """Callback invoked when text content changes."""
        return self._on_change

    @on_change.setter
    def on_change(self, value: Callable[[str], object] | None) -> None:
        if value is not None and not callable(value):
            msg = f"on_change must be callable or None, got {type(value).__name__}"
            raise TypeError(msg)
        self._on_change = value

    # -- Drawing ------------------------------------------------------------

    def draw(self, buffer: CellBuffer) -> None:
        """Render the text field into *buffer*.

        Draws the text content starting at ``(x, y)``.  When focused,
        uses bold styling to indicate the active field.  Text is
        truncated to fit within ``width``.

        Skips drawing if ``self.visible`` is ``False``.

        Caveats:
            - The cursor is **not** visually rendered.  Terminal cursor
              management is handled by the :class:`~wyby.renderer.Renderer`,
              not by individual widgets.  The ``cursor`` property provides
              the logical position for any external cursor rendering.
            - Empty fields display as blank space (no placeholder text
              in this version).
            - Text longer than ``width`` is truncated from the right.
              No ellipsis or scroll indicator is shown.
        """
        if not self.visible:
            return
        # Truncate display text to widget width.
        display = self._text[:self._width]
        # Pad with spaces to fill the widget width (clears old content).
        display = display.ljust(self._width)
        buffer.put_text(self._x, self._y, display, bold=self._focused)

    # -- Event handling -----------------------------------------------------

    def handle_event(self, event: Event) -> bool:
        """Process an input event with focus-gated keyboard handling.

        **Mouse events:** A left-button press inside the widget's
        bounds returns ``True`` (consumed) to support click-to-focus
        via :class:`~wyby.focus.FocusManager`.  All other mouse events
        return ``False``.

        **Keyboard events (focus required):** When ``self.focused`` is
        ``True``, the widget processes:

        - Printable characters — inserted at the cursor position
        - ``space`` — inserts a space at the cursor position
        - ``backspace`` — deletes the character before the cursor
        - ``delete`` — deletes the character after the cursor
        - ``left`` / ``right`` — moves the cursor
        - ``home`` / ``end`` — moves the cursor to start/end
        - ``enter`` — triggers ``on_submit`` callback

        When ``self.focused`` is ``False``, all keyboard events return
        ``False`` (not consumed).  This is the core focus-gating
        behaviour.

        Returns:
            ``True`` if the event was consumed, ``False`` otherwise.

        Caveats:
            - **Focus is required for keyboard input.**  Unfocused
              widgets silently ignore all key events.  This prevents
              "phantom typing" when multiple text inputs are on screen.
            - Navigation keys (``left``, ``right``, ``home``, ``end``)
              return ``True`` even if the cursor doesn't move (e.g.,
              pressing ``left`` at position 0).  This prevents the
              event from propagating to other widgets when the user
              is clearly interacting with this field.
            - ``backspace`` at position 0 and ``delete`` at the end
              of the text return ``True`` (consumed) but do nothing.
              This matches standard text field behaviour.
            - ``max_length`` enforcement: typed characters are silently
              rejected (event consumed, no insertion) when the text
              has reached the limit.
            - Ctrl+key combinations are not consumed (return ``False``)
              to allow the scene or focus manager to handle shortcuts
              like Ctrl+C.  The one exception is that Ctrl+letter
              events with ``ctrl=True`` are explicitly skipped.
            - Tab is not consumed — it should be handled by the
              :class:`~wyby.focus.FocusManager` for tab cycling.
        """
        from wyby.input import KeyEvent, MouseEvent

        # Mouse: consume left-press inside bounds for click-to-focus.
        if isinstance(event, MouseEvent):
            if event.button == "left" and event.action == "press":
                if self.contains_point(event.x, event.y):
                    return True
            return False

        if not isinstance(event, KeyEvent):
            return False

        # Focus gate: ignore all keyboard input when not focused.
        # This is the defining behaviour of a focus-gated widget.
        if not self._focused:
            return False

        # Tab is not consumed — allow FocusManager to handle tab cycling.
        if event.key == "tab":
            return False

        # Ctrl+key combinations are passed through to allow scene-level
        # shortcuts (Ctrl+C, Ctrl+S, etc.) to work even when a text
        # input has focus.
        if event.ctrl:
            return False

        # -- Submit --
        if event.key == "enter":
            if self._on_submit is not None:
                self._on_submit(self._text)
            return True

        # -- Deletion --
        if event.key == "backspace":
            if self._cursor > 0:
                old = self._text
                self._text = self._text[:self._cursor - 1] + self._text[self._cursor:]
                self._cursor -= 1
                if old != self._text and self._on_change is not None:
                    self._on_change(self._text)
            return True

        if event.key == "delete":
            if self._cursor < len(self._text):
                old = self._text
                self._text = self._text[:self._cursor] + self._text[self._cursor + 1:]
                if old != self._text and self._on_change is not None:
                    self._on_change(self._text)
            return True

        # -- Cursor movement --
        if event.key == "left":
            if self._cursor > 0:
                self._cursor -= 1
            return True

        if event.key == "right":
            if self._cursor < len(self._text):
                self._cursor += 1
            return True

        if event.key == "home":
            self._cursor = 0
            return True

        if event.key == "end":
            self._cursor = len(self._text)
            return True

        # -- Character insertion --
        if event.key == "space":
            if self._max_length is not None and len(self._text) >= self._max_length:
                return True
            self._text = self._text[:self._cursor] + " " + self._text[self._cursor:]
            self._cursor += 1
            if self._on_change is not None:
                self._on_change(self._text)
            return True

        # Single printable characters (len == 1, not a control key name).
        if len(event.key) == 1:
            if self._max_length is not None and len(self._text) >= self._max_length:
                return True
            self._text = self._text[:self._cursor] + event.key + self._text[self._cursor:]
            self._cursor += 1
            if self._on_change is not None:
                self._on_change(self._text)
            return True

        # Unrecognised key (e.g., function keys, escape) — not consumed.
        return False

    # -- Repr ---------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"TextInput("
            f"x={self._x}, y={self._y}, "
            f"w={self._width}, "
            f"text={self._text!r}"
            f"{f', max_length={self._max_length}' if self._max_length is not None else ''}"
            f"{', visible=False' if not self._visible else ''}"
            f"{', focused' if self._focused else ''}"
            f")"
        )
