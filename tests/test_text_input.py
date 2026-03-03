"""Tests for wyby.text_input — TextInput widget with focus-gated input."""

from __future__ import annotations

import pytest

from wyby.event import Event
from wyby.focus import FocusManager
from wyby.grid import CellBuffer
from wyby.input import KeyEvent, MouseEvent
from wyby.text_input import TextInput


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestTextInputConstruction:
    """TextInput creation and initial state."""

    def test_default_state(self) -> None:
        ti = TextInput()
        assert ti.text == ""
        assert ti.cursor == 0
        assert ti.width == 20
        assert ti.height == 1
        assert ti.focused is False
        assert ti.visible is True

    def test_custom_position(self) -> None:
        ti = TextInput(x=5, y=10)
        assert ti.x == 5
        assert ti.y == 10

    def test_custom_width(self) -> None:
        ti = TextInput(width=30)
        assert ti.width == 30

    def test_max_length(self) -> None:
        ti = TextInput(max_length=10)
        assert ti.max_length == 10

    def test_max_length_none(self) -> None:
        ti = TextInput(max_length=None)
        assert ti.max_length is None

    def test_max_length_zero(self) -> None:
        ti = TextInput(max_length=0)
        assert ti.max_length == 0

    def test_max_length_rejects_float(self) -> None:
        with pytest.raises(TypeError, match="max_length must be an int"):
            TextInput(max_length=5.0)  # type: ignore[arg-type]

    def test_max_length_rejects_bool(self) -> None:
        with pytest.raises(TypeError, match="max_length must be an int"):
            TextInput(max_length=True)  # type: ignore[arg-type]

    def test_max_length_rejects_negative(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            TextInput(max_length=-1)

    def test_on_submit_callable(self) -> None:
        ti = TextInput(on_submit=lambda s: None)
        assert ti.on_submit is not None

    def test_on_submit_none(self) -> None:
        ti = TextInput(on_submit=None)
        assert ti.on_submit is None

    def test_on_submit_rejects_non_callable(self) -> None:
        with pytest.raises(TypeError, match="on_submit must be callable"):
            TextInput(on_submit="not callable")  # type: ignore[arg-type]

    def test_on_change_callable(self) -> None:
        ti = TextInput(on_change=lambda s: None)
        assert ti.on_change is not None

    def test_on_change_rejects_non_callable(self) -> None:
        with pytest.raises(TypeError, match="on_change must be callable"):
            TextInput(on_change=42)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Text property
# ---------------------------------------------------------------------------


class TestTextInputTextProperty:
    """Text property get/set and cursor clamping."""

    def test_set_text(self) -> None:
        ti = TextInput()
        ti.text = "hello"
        assert ti.text == "hello"
        assert ti.cursor == 0

    def test_set_text_clamps_cursor(self) -> None:
        """Cursor is clamped when text is shortened."""
        ti = TextInput()
        ti.text = "hello"
        # Move cursor to end by typing characters while focused
        ti._cursor = 5
        ti.text = "hi"
        assert ti.cursor == 2  # Clamped to len("hi")

    def test_set_text_rejects_non_string(self) -> None:
        ti = TextInput()
        with pytest.raises(TypeError, match="text must be a str"):
            ti.text = 42  # type: ignore[assignment]

    def test_set_text_triggers_on_change(self) -> None:
        changes: list[str] = []
        ti = TextInput(on_change=lambda s: changes.append(s))
        ti.text = "new"
        assert changes == ["new"]

    def test_set_text_same_value_no_change(self) -> None:
        """Setting text to the same value does not trigger on_change."""
        changes: list[str] = []
        ti = TextInput(on_change=lambda s: changes.append(s))
        ti.text = ""  # Same as initial
        assert changes == []

    def test_set_text_bypasses_max_length(self) -> None:
        """Programmatic text assignment ignores max_length."""
        ti = TextInput(max_length=3)
        ti.text = "hello world"
        assert ti.text == "hello world"


# ---------------------------------------------------------------------------
# Focus-gated keyboard input — the core feature
# ---------------------------------------------------------------------------


class TestTextInputFocusGating:
    """Keyboard events are only processed when focused.

    This is the defining behaviour of focus-gated input handling.
    When the widget is not focused, all KeyEvents must return False
    (not consumed) to allow other widgets or the scene to handle them.
    """

    def test_unfocused_ignores_character(self) -> None:
        """Typing a character while unfocused is ignored."""
        ti = TextInput()
        assert ti.focused is False
        event = KeyEvent(key="a")
        consumed = ti.handle_event(event)
        assert consumed is False
        assert ti.text == ""

    def test_unfocused_ignores_enter(self) -> None:
        ti = TextInput()
        event = KeyEvent(key="enter")
        consumed = ti.handle_event(event)
        assert consumed is False

    def test_unfocused_ignores_backspace(self) -> None:
        ti = TextInput()
        ti.text = "hello"
        ti._cursor = 5
        event = KeyEvent(key="backspace")
        consumed = ti.handle_event(event)
        assert consumed is False
        assert ti.text == "hello"  # Unchanged

    def test_unfocused_ignores_arrow_keys(self) -> None:
        ti = TextInput()
        for key in ("left", "right", "home", "end"):
            consumed = ti.handle_event(KeyEvent(key=key))
            assert consumed is False

    def test_focused_accepts_character(self) -> None:
        """Typing a character while focused inserts it."""
        ti = TextInput()
        ti.focused = True
        event = KeyEvent(key="a")
        consumed = ti.handle_event(event)
        assert consumed is True
        assert ti.text == "a"
        assert ti.cursor == 1

    def test_focus_then_unfocus_stops_accepting(self) -> None:
        """Focus is checked on each event, not just at construction."""
        ti = TextInput()
        ti.focused = True
        ti.handle_event(KeyEvent(key="a"))
        assert ti.text == "a"

        ti.focused = False
        consumed = ti.handle_event(KeyEvent(key="b"))
        assert consumed is False
        assert ti.text == "a"  # No "b" added


# ---------------------------------------------------------------------------
# Character insertion
# ---------------------------------------------------------------------------


class TestTextInputCharacterInsertion:
    """Typing characters into a focused TextInput."""

    def _make_focused(self, **kwargs: object) -> TextInput:
        ti = TextInput(**kwargs)  # type: ignore[arg-type]
        ti.focused = True
        return ti

    def test_type_single_character(self) -> None:
        ti = self._make_focused()
        ti.handle_event(KeyEvent(key="h"))
        assert ti.text == "h"
        assert ti.cursor == 1

    def test_type_multiple_characters(self) -> None:
        ti = self._make_focused()
        for ch in "hello":
            ti.handle_event(KeyEvent(key=ch))
        assert ti.text == "hello"
        assert ti.cursor == 5

    def test_type_space(self) -> None:
        ti = self._make_focused()
        ti.handle_event(KeyEvent(key="h"))
        ti.handle_event(KeyEvent(key="i"))
        ti.handle_event(KeyEvent(key="space"))
        assert ti.text == "hi "
        assert ti.cursor == 3

    def test_insert_at_cursor_position(self) -> None:
        """Characters are inserted at the cursor, not appended."""
        ti = self._make_focused()
        ti.text = "hllo"
        ti._cursor = 1  # Between "h" and "l"
        ti.handle_event(KeyEvent(key="e"))
        assert ti.text == "hello"
        assert ti.cursor == 2

    def test_insert_at_beginning(self) -> None:
        ti = self._make_focused()
        ti.text = "ello"
        ti._cursor = 0
        ti.handle_event(KeyEvent(key="h"))
        assert ti.text == "hello"
        assert ti.cursor == 1

    def test_max_length_blocks_insertion(self) -> None:
        """Characters are rejected when text reaches max_length."""
        ti = self._make_focused(max_length=3)
        for ch in "abc":
            ti.handle_event(KeyEvent(key=ch))
        assert ti.text == "abc"
        # Try to type a 4th character — consumed but not inserted.
        consumed = ti.handle_event(KeyEvent(key="d"))
        assert consumed is True
        assert ti.text == "abc"

    def test_max_length_blocks_space_insertion(self) -> None:
        ti = self._make_focused(max_length=2)
        ti.handle_event(KeyEvent(key="a"))
        ti.handle_event(KeyEvent(key="b"))
        consumed = ti.handle_event(KeyEvent(key="space"))
        assert consumed is True
        assert ti.text == "ab"

    def test_max_length_zero_blocks_all(self) -> None:
        ti = self._make_focused(max_length=0)
        consumed = ti.handle_event(KeyEvent(key="a"))
        assert consumed is True
        assert ti.text == ""

    def test_on_change_fires_on_insert(self) -> None:
        changes: list[str] = []
        ti = self._make_focused(on_change=lambda s: changes.append(s))
        ti.handle_event(KeyEvent(key="x"))
        assert changes == ["x"]

    def test_on_change_fires_for_space(self) -> None:
        changes: list[str] = []
        ti = self._make_focused(on_change=lambda s: changes.append(s))
        ti.handle_event(KeyEvent(key="space"))
        assert changes == [" "]


# ---------------------------------------------------------------------------
# Deletion
# ---------------------------------------------------------------------------


class TestTextInputDeletion:
    """Backspace and delete key handling."""

    def _make_focused(self, text: str = "", cursor: int = 0) -> TextInput:
        ti = TextInput()
        ti.focused = True
        ti.text = text
        ti._cursor = cursor
        return ti

    def test_backspace_deletes_before_cursor(self) -> None:
        ti = self._make_focused(text="hello", cursor=5)
        ti.handle_event(KeyEvent(key="backspace"))
        assert ti.text == "hell"
        assert ti.cursor == 4

    def test_backspace_at_beginning_is_noop(self) -> None:
        """Backspace at position 0 consumes but does nothing."""
        ti = self._make_focused(text="hello", cursor=0)
        consumed = ti.handle_event(KeyEvent(key="backspace"))
        assert consumed is True
        assert ti.text == "hello"
        assert ti.cursor == 0

    def test_backspace_in_middle(self) -> None:
        ti = self._make_focused(text="hello", cursor=3)
        ti.handle_event(KeyEvent(key="backspace"))
        assert ti.text == "helo"
        assert ti.cursor == 2

    def test_delete_key_deletes_after_cursor(self) -> None:
        ti = self._make_focused(text="hello", cursor=0)
        ti.handle_event(KeyEvent(key="delete"))
        assert ti.text == "ello"
        assert ti.cursor == 0

    def test_delete_at_end_is_noop(self) -> None:
        """Delete at end of text consumes but does nothing."""
        ti = self._make_focused(text="hello", cursor=5)
        consumed = ti.handle_event(KeyEvent(key="delete"))
        assert consumed is True
        assert ti.text == "hello"

    def test_delete_in_middle(self) -> None:
        ti = self._make_focused(text="hello", cursor=2)
        ti.handle_event(KeyEvent(key="delete"))
        assert ti.text == "helo"
        assert ti.cursor == 2

    def test_on_change_fires_on_backspace(self) -> None:
        changes: list[str] = []
        ti = TextInput(on_change=lambda s: changes.append(s))
        ti.focused = True
        ti._text = "ab"
        ti._cursor = 2
        ti.handle_event(KeyEvent(key="backspace"))
        assert changes == ["a"]

    def test_on_change_fires_on_delete(self) -> None:
        changes: list[str] = []
        ti = TextInput(on_change=lambda s: changes.append(s))
        ti.focused = True
        ti._text = "ab"
        ti._cursor = 0
        ti.handle_event(KeyEvent(key="delete"))
        assert changes == ["b"]

    def test_backspace_noop_does_not_fire_on_change(self) -> None:
        """Backspace at position 0 does not trigger on_change."""
        changes: list[str] = []
        ti = TextInput(on_change=lambda s: changes.append(s))
        ti.focused = True
        ti._text = "a"
        ti._cursor = 0
        ti.handle_event(KeyEvent(key="backspace"))
        assert changes == []


# ---------------------------------------------------------------------------
# Cursor movement
# ---------------------------------------------------------------------------


class TestTextInputCursorMovement:
    """Arrow key and home/end cursor navigation."""

    def _make_focused(self, text: str = "", cursor: int = 0) -> TextInput:
        ti = TextInput()
        ti.focused = True
        ti.text = text
        ti._cursor = cursor
        return ti

    def test_left_moves_cursor(self) -> None:
        ti = self._make_focused(text="hello", cursor=3)
        ti.handle_event(KeyEvent(key="left"))
        assert ti.cursor == 2

    def test_left_at_zero_stays(self) -> None:
        ti = self._make_focused(text="hello", cursor=0)
        consumed = ti.handle_event(KeyEvent(key="left"))
        assert consumed is True  # Consumed even though cursor didn't move
        assert ti.cursor == 0

    def test_right_moves_cursor(self) -> None:
        ti = self._make_focused(text="hello", cursor=2)
        ti.handle_event(KeyEvent(key="right"))
        assert ti.cursor == 3

    def test_right_at_end_stays(self) -> None:
        ti = self._make_focused(text="hello", cursor=5)
        consumed = ti.handle_event(KeyEvent(key="right"))
        assert consumed is True
        assert ti.cursor == 5

    def test_home_moves_to_start(self) -> None:
        ti = self._make_focused(text="hello", cursor=3)
        ti.handle_event(KeyEvent(key="home"))
        assert ti.cursor == 0

    def test_end_moves_to_end(self) -> None:
        ti = self._make_focused(text="hello", cursor=1)
        ti.handle_event(KeyEvent(key="end"))
        assert ti.cursor == 5

    def test_home_at_start_consumes(self) -> None:
        ti = self._make_focused(text="hello", cursor=0)
        consumed = ti.handle_event(KeyEvent(key="home"))
        assert consumed is True

    def test_end_at_end_consumes(self) -> None:
        ti = self._make_focused(text="hello", cursor=5)
        consumed = ti.handle_event(KeyEvent(key="end"))
        assert consumed is True


# ---------------------------------------------------------------------------
# Submit
# ---------------------------------------------------------------------------


class TestTextInputSubmit:
    """Enter key triggers on_submit callback."""

    def test_enter_calls_on_submit(self) -> None:
        submissions: list[str] = []
        ti = TextInput(on_submit=lambda s: submissions.append(s))
        ti.focused = True
        ti.text = "hello"
        consumed = ti.handle_event(KeyEvent(key="enter"))
        assert consumed is True
        assert submissions == ["hello"]

    def test_enter_without_callback(self) -> None:
        """Enter is consumed even without on_submit."""
        ti = TextInput(on_submit=None)
        ti.focused = True
        consumed = ti.handle_event(KeyEvent(key="enter"))
        assert consumed is True

    def test_enter_does_not_modify_text(self) -> None:
        ti = TextInput()
        ti.focused = True
        ti.text = "hello"
        ti.handle_event(KeyEvent(key="enter"))
        assert ti.text == "hello"

    def test_submit_callback_exception_propagates(self) -> None:
        def bad_submit(text: str) -> None:
            raise RuntimeError("submit error")

        ti = TextInput(on_submit=bad_submit)
        ti.focused = True
        with pytest.raises(RuntimeError, match="submit error"):
            ti.handle_event(KeyEvent(key="enter"))


# ---------------------------------------------------------------------------
# Mouse events
# ---------------------------------------------------------------------------


class TestTextInputMouse:
    """Mouse event handling for click-to-focus support."""

    def test_click_inside_consumes(self) -> None:
        """Left-click inside bounds is consumed for click-to-focus."""
        ti = TextInput(x=5, y=3, width=20)
        event = MouseEvent(x=10, y=3, button="left", action="press")
        consumed = ti.handle_event(event)
        assert consumed is True

    def test_click_outside_not_consumed(self) -> None:
        ti = TextInput(x=5, y=3, width=20)
        event = MouseEvent(x=50, y=50, button="left", action="press")
        consumed = ti.handle_event(event)
        assert consumed is False

    def test_right_click_not_consumed(self) -> None:
        ti = TextInput(x=5, y=3, width=20)
        event = MouseEvent(x=10, y=3, button="right", action="press")
        consumed = ti.handle_event(event)
        assert consumed is False

    def test_mouse_release_not_consumed(self) -> None:
        ti = TextInput(x=5, y=3, width=20)
        event = MouseEvent(x=10, y=3, button="left", action="release")
        consumed = ti.handle_event(event)
        assert consumed is False

    def test_mouse_move_not_consumed(self) -> None:
        ti = TextInput(x=5, y=3, width=20)
        event = MouseEvent(x=10, y=3, button="none", action="move")
        consumed = ti.handle_event(event)
        assert consumed is False


# ---------------------------------------------------------------------------
# Key passthrough (tab, ctrl, unrecognised)
# ---------------------------------------------------------------------------


class TestTextInputKeyPassthrough:
    """Keys that should NOT be consumed even when focused."""

    def test_tab_not_consumed(self) -> None:
        """Tab passes through for FocusManager tab cycling."""
        ti = TextInput()
        ti.focused = True
        consumed = ti.handle_event(KeyEvent(key="tab"))
        assert consumed is False

    def test_ctrl_key_not_consumed(self) -> None:
        """Ctrl+key combos pass through for scene shortcuts."""
        ti = TextInput()
        ti.focused = True
        consumed = ti.handle_event(KeyEvent(key="a", ctrl=True))
        assert consumed is False

    def test_escape_not_consumed(self) -> None:
        """Escape passes through (multi-character key name)."""
        ti = TextInput()
        ti.focused = True
        consumed = ti.handle_event(KeyEvent(key="escape"))
        assert consumed is False

    def test_function_key_not_consumed(self) -> None:
        """Unrecognised keys (e.g., function keys) pass through."""
        ti = TextInput()
        ti.focused = True
        consumed = ti.handle_event(KeyEvent(key="pageup"))
        assert consumed is False

    def test_base_event_not_consumed(self) -> None:
        """Non-Key, non-Mouse Event is not consumed."""
        ti = TextInput()
        ti.focused = True
        consumed = ti.handle_event(Event())
        assert consumed is False


# ---------------------------------------------------------------------------
# Drawing
# ---------------------------------------------------------------------------


class TestTextInputDraw:
    """Drawing the text field into a CellBuffer."""

    def test_draw_empty(self) -> None:
        buf = CellBuffer(30, 5)
        ti = TextInput(x=0, y=0, width=10)
        ti.draw(buf)
        # Should draw spaces (blank field)
        cell = buf.get(0, 0)
        assert cell is not None
        assert cell.char == " "

    def test_draw_with_text(self) -> None:
        buf = CellBuffer(30, 5)
        ti = TextInput(x=0, y=0, width=10)
        ti.text = "hello"
        ti.draw(buf)
        cell = buf.get(0, 0)
        assert cell is not None
        assert cell.char == "h"
        cell4 = buf.get(4, 0)
        assert cell4 is not None
        assert cell4.char == "o"

    def test_draw_truncates_long_text(self) -> None:
        buf = CellBuffer(30, 5)
        ti = TextInput(x=0, y=0, width=5)
        ti.text = "hello world"
        ti.draw(buf)
        # Only "hello" visible in 5-column width
        cell4 = buf.get(4, 0)
        assert cell4 is not None
        assert cell4.char == "o"
        # Position 5 should not have 'w' from " world"
        cell5 = buf.get(5, 0)
        assert cell5 is not None
        assert cell5.char == " "  # Default buffer content

    def test_draw_invisible_skips(self) -> None:
        buf = CellBuffer(30, 5)
        ti = TextInput(x=0, y=0, width=10)
        ti.text = "hello"
        ti.visible = False
        ti.draw(buf)
        cell = buf.get(0, 0)
        assert cell is not None
        assert cell.char == " "  # Not drawn


# ---------------------------------------------------------------------------
# FocusManager integration
# ---------------------------------------------------------------------------


class TestTextInputFocusManagerIntegration:
    """End-to-end tests with FocusManager for click-to-focus and dispatch.

    These tests verify that TextInput works correctly with the
    FocusManager's focus lifecycle: click to focus, type while focused,
    click away to blur, tab cycling between fields.
    """

    def test_click_to_focus_then_type(self) -> None:
        """Click on the text input to focus, then type characters."""
        ti = TextInput(x=0, y=0, width=20)
        fm = FocusManager(widgets=[ti])

        # Click to focus
        click = MouseEvent(x=5, y=0, button="left", action="press")
        fm.dispatch(click)
        assert fm.focused_widget is ti
        assert ti.focused is True

        # Type a character
        key = KeyEvent(key="a")
        consumed = fm.dispatch(key)
        assert consumed is True
        assert ti.text == "a"

    def test_click_away_unfocuses(self) -> None:
        """Clicking empty space clears focus and stops accepting input."""
        ti = TextInput(x=0, y=0, width=20)
        fm = FocusManager(widgets=[ti])

        # Focus via click
        fm.dispatch(MouseEvent(x=5, y=0, button="left", action="press"))
        assert ti.focused is True

        # Click empty space
        fm.dispatch(MouseEvent(x=50, y=50, button="left", action="press"))
        assert ti.focused is False

        # Typing should not work
        consumed = fm.dispatch(KeyEvent(key="a"))
        assert consumed is False
        assert ti.text == ""

    def test_tab_cycles_between_text_inputs(self) -> None:
        """Tab cycling moves focus between multiple TextInput widgets."""
        ti1 = TextInput(x=0, y=0, width=20)
        ti2 = TextInput(x=0, y=1, width=20)
        fm = FocusManager(widgets=[ti1, ti2])

        # Focus first
        fm.focus_next()
        assert fm.focused_widget is ti1
        assert ti1.focused is True

        # Type in first
        fm.dispatch(KeyEvent(key="a"))
        assert ti1.text == "a"

        # Tab to second
        fm.focus_next()
        assert fm.focused_widget is ti2
        assert ti1.focused is False
        assert ti2.focused is True

        # Type in second
        fm.dispatch(KeyEvent(key="b"))
        assert ti2.text == "b"
        assert ti1.text == "a"  # First unchanged

    def test_click_focuses_one_unfocuses_other(self) -> None:
        """Clicking one TextInput focuses it and blurs the other."""
        ti1 = TextInput(x=0, y=0, width=20)
        ti2 = TextInput(x=0, y=1, width=20)
        fm = FocusManager(widgets=[ti1, ti2])

        # Click first
        fm.dispatch(MouseEvent(x=5, y=0, button="left", action="press"))
        assert ti1.focused is True
        assert ti2.focused is False

        fm.dispatch(KeyEvent(key="x"))
        assert ti1.text == "x"

        # Click second
        fm.dispatch(MouseEvent(x=5, y=1, button="left", action="press"))
        assert ti1.focused is False
        assert ti2.focused is True

        fm.dispatch(KeyEvent(key="y"))
        assert ti1.text == "x"  # Unchanged
        assert ti2.text == "y"

    def test_mixed_widgets_button_and_text_input(self) -> None:
        """TextInput and Button coexist with correct focus routing."""
        from wyby.button import Button

        clicks: list[str] = []
        btn = Button("OK", x=0, y=0, on_click=lambda: clicks.append("ok"))
        ti = TextInput(x=0, y=1, width=20)
        fm = FocusManager(widgets=[btn, ti])

        # Click TextInput
        fm.dispatch(MouseEvent(x=5, y=1, button="left", action="press"))
        assert fm.focused_widget is ti

        # Type
        fm.dispatch(KeyEvent(key="h"))
        fm.dispatch(KeyEvent(key="i"))
        assert ti.text == "hi"

        # Click Button
        fm.dispatch(MouseEvent(x=2, y=0, button="left", action="press"))
        assert fm.focused_widget is btn
        assert clicks == ["ok"]

        # Typing now should not affect TextInput (Button consumes enter/space
        # when focused, but 'z' is not handled by Button so it returns False).
        fm.dispatch(KeyEvent(key="z"))
        assert ti.text == "hi"  # Unchanged

    def test_keyboard_does_not_reach_unfocused_text_input(self) -> None:
        """With no focus, keyboard events are not dispatched to any widget."""
        ti = TextInput(x=0, y=0, width=20)
        fm = FocusManager(widgets=[ti])
        # No focus set
        consumed = fm.dispatch(KeyEvent(key="a"))
        assert consumed is False
        assert ti.text == ""

    def test_submit_while_focused_via_focus_manager(self) -> None:
        """Enter key triggers on_submit when focused through FocusManager."""
        submissions: list[str] = []
        ti = TextInput(x=0, y=0, width=20, on_submit=lambda s: submissions.append(s))
        fm = FocusManager(widgets=[ti])

        # Focus and type
        fm.dispatch(MouseEvent(x=5, y=0, button="left", action="press"))
        for ch in "hello":
            fm.dispatch(KeyEvent(key=ch))

        # Submit
        fm.dispatch(KeyEvent(key="enter"))
        assert submissions == ["hello"]


# ---------------------------------------------------------------------------
# Focus lifecycle hooks
# ---------------------------------------------------------------------------


class TestTextInputFocusLifecycle:
    """on_focus/on_blur are called correctly during focus transitions."""

    def test_on_focus_called(self) -> None:
        ti = TextInput()
        ti.focused = True
        assert ti.focused is True

    def test_on_blur_called(self) -> None:
        ti = TextInput()
        ti.focused = True
        ti.focused = False
        assert ti.focused is False

    def test_focus_manager_triggers_lifecycle(self) -> None:
        """FocusManager correctly triggers focus/blur on TextInput."""
        ti1 = TextInput(x=0, y=0, width=10)
        ti2 = TextInput(x=0, y=1, width=10)
        fm = FocusManager(widgets=[ti1, ti2])

        fm.set_focus(ti1)
        assert ti1.focused is True
        assert ti2.focused is False

        fm.set_focus(ti2)
        assert ti1.focused is False
        assert ti2.focused is True

        fm.set_focus(None)
        assert ti1.focused is False
        assert ti2.focused is False


# ---------------------------------------------------------------------------
# Repr
# ---------------------------------------------------------------------------


class TestTextInputRepr:
    """String representation."""

    def test_repr_basic(self) -> None:
        ti = TextInput(x=1, y=2, width=15)
        r = repr(ti)
        assert "TextInput(" in r
        assert "x=1" in r
        assert "y=2" in r
        assert "w=15" in r
        assert "text=''" in r

    def test_repr_with_text(self) -> None:
        ti = TextInput()
        ti.text = "hello"
        assert "text='hello'" in repr(ti)

    def test_repr_with_max_length(self) -> None:
        ti = TextInput(max_length=10)
        assert "max_length=10" in repr(ti)

    def test_repr_focused(self) -> None:
        ti = TextInput()
        ti.focused = True
        assert "focused" in repr(ti)

    def test_repr_invisible(self) -> None:
        ti = TextInput()
        ti.visible = False
        assert "visible=False" in repr(ti)


# ---------------------------------------------------------------------------
# Import from package root
# ---------------------------------------------------------------------------


class TestTextInputImport:
    """TextInput is accessible from the wyby package root."""

    def test_import_from_wyby(self) -> None:
        from wyby import TextInput as TI
        assert TI is TextInput
