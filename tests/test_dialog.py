"""Tests for wyby.dialog — Dialog widget with border, title, body, and buttons."""

from __future__ import annotations

import pytest

from wyby.button import Button
from wyby.dialog import Dialog
from wyby.event import Event
from wyby.grid import CellBuffer
from wyby.input import KeyEvent, MouseEvent
from wyby.widget import Widget


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestDialogConstruction:
    """Dialog creation and default state."""

    def test_default_position(self) -> None:
        dlg = Dialog()
        assert dlg.x == 0
        assert dlg.y == 0

    def test_custom_position(self) -> None:
        dlg = Dialog(x=5, y=10)
        assert dlg.x == 5
        assert dlg.y == 10

    def test_default_size(self) -> None:
        dlg = Dialog()
        assert dlg.width == 30
        assert dlg.height == 7

    def test_custom_size(self) -> None:
        dlg = Dialog(width=40, height=10)
        assert dlg.width == 40
        assert dlg.height == 10

    def test_default_title_empty(self) -> None:
        dlg = Dialog()
        assert dlg.title == ""

    def test_custom_title(self) -> None:
        dlg = Dialog(title="Confirm")
        assert dlg.title == "Confirm"

    def test_default_body_empty(self) -> None:
        dlg = Dialog()
        assert dlg.body == ""

    def test_custom_body(self) -> None:
        dlg = Dialog(body="Are you sure?")
        assert dlg.body == "Are you sure?"

    def test_default_visible(self) -> None:
        dlg = Dialog()
        assert dlg.visible is True

    def test_default_not_focused(self) -> None:
        dlg = Dialog()
        assert dlg.focused is False

    def test_no_buttons_initially(self) -> None:
        dlg = Dialog()
        assert dlg.buttons == []

    def test_is_a_widget(self) -> None:
        dlg = Dialog()
        assert isinstance(dlg, Widget)

    def test_z_index_default(self) -> None:
        dlg = Dialog()
        assert dlg.z_index == 0

    def test_z_index_custom(self) -> None:
        dlg = Dialog(z_index=10)
        assert dlg.z_index == 10


# ---------------------------------------------------------------------------
# Minimum size clamping
# ---------------------------------------------------------------------------


class TestDialogMinSize:
    """Minimum dimensions are enforced."""

    def test_width_clamped_to_minimum(self) -> None:
        dlg = Dialog(width=2)
        assert dlg.width >= 4

    def test_height_clamped_to_minimum(self) -> None:
        dlg = Dialog(height=1)
        assert dlg.height >= 3

    def test_minimum_width_exact(self) -> None:
        dlg = Dialog(width=4)
        assert dlg.width == 4

    def test_minimum_height_exact(self) -> None:
        dlg = Dialog(height=3)
        assert dlg.height == 3


# ---------------------------------------------------------------------------
# Type validation
# ---------------------------------------------------------------------------


class TestDialogTypeValidation:
    """Type checking on constructor arguments."""

    def test_title_rejects_non_string(self) -> None:
        with pytest.raises(TypeError, match="title must be a str"):
            Dialog(title=123)  # type: ignore[arg-type]

    def test_title_rejects_none(self) -> None:
        with pytest.raises(TypeError, match="title must be a str"):
            Dialog(title=None)  # type: ignore[arg-type]

    def test_body_rejects_non_string(self) -> None:
        with pytest.raises(TypeError, match="body must be a str"):
            Dialog(body=123)  # type: ignore[arg-type]

    def test_body_rejects_none(self) -> None:
        with pytest.raises(TypeError, match="body must be a str"):
            Dialog(body=None)  # type: ignore[arg-type]

    def test_x_rejects_float(self) -> None:
        with pytest.raises(TypeError, match="x must be an int"):
            Dialog(x=1.5)  # type: ignore[arg-type]

    def test_y_rejects_float(self) -> None:
        with pytest.raises(TypeError, match="y must be an int"):
            Dialog(y=1.5)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Title property
# ---------------------------------------------------------------------------


class TestDialogTitle:
    """Title property getter and setter."""

    def test_set_title(self) -> None:
        dlg = Dialog(title="Old")
        dlg.title = "New"
        assert dlg.title == "New"

    def test_set_title_empty(self) -> None:
        dlg = Dialog(title="Something")
        dlg.title = ""
        assert dlg.title == ""

    def test_set_title_rejects_non_string(self) -> None:
        dlg = Dialog()
        with pytest.raises(TypeError, match="title must be a str"):
            dlg.title = 42  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Body property
# ---------------------------------------------------------------------------


class TestDialogBody:
    """Body property getter and setter."""

    def test_set_body(self) -> None:
        dlg = Dialog(body="Old text")
        dlg.body = "New text"
        assert dlg.body == "New text"

    def test_set_body_empty(self) -> None:
        dlg = Dialog(body="Something")
        dlg.body = ""
        assert dlg.body == ""

    def test_set_body_rejects_non_string(self) -> None:
        dlg = Dialog()
        with pytest.raises(TypeError, match="body must be a str"):
            dlg.body = 42  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Button management
# ---------------------------------------------------------------------------


class TestDialogButtons:
    """Adding and removing buttons."""

    def test_add_button_returns_button(self) -> None:
        dlg = Dialog()
        btn = dlg.add_button("OK")
        assert isinstance(btn, Button)
        assert btn.label == "OK"

    def test_add_button_appears_in_buttons_list(self) -> None:
        dlg = Dialog()
        btn = dlg.add_button("OK")
        assert btn in dlg.buttons

    def test_add_button_is_child(self) -> None:
        dlg = Dialog()
        btn = dlg.add_button("OK")
        assert btn in dlg.children

    def test_add_button_with_callback(self) -> None:
        calls: list[str] = []
        dlg = Dialog()
        btn = dlg.add_button("OK", on_click=lambda: calls.append("clicked"))
        assert btn.on_click is not None

    def test_add_multiple_buttons(self) -> None:
        dlg = Dialog()
        btn1 = dlg.add_button("Yes")
        btn2 = dlg.add_button("No")
        assert len(dlg.buttons) == 2
        assert btn1 in dlg.buttons
        assert btn2 in dlg.buttons

    def test_remove_button(self) -> None:
        dlg = Dialog()
        btn = dlg.add_button("OK")
        dlg.remove_button(btn)
        assert btn not in dlg.buttons
        assert btn not in dlg.children

    def test_remove_button_not_found_raises(self) -> None:
        dlg = Dialog()
        btn = Button("Orphan")
        with pytest.raises(ValueError, match="is not a button"):
            dlg.remove_button(btn)

    def test_buttons_returns_copy(self) -> None:
        """Mutating the returned list does not affect the dialog."""
        dlg = Dialog()
        dlg.add_button("OK")
        buttons = dlg.buttons
        buttons.clear()
        assert len(dlg.buttons) == 1


# ---------------------------------------------------------------------------
# Drawing — border
# ---------------------------------------------------------------------------


class TestDialogDrawBorder:
    """Dialog border rendering into CellBuffer."""

    def test_draws_top_left_corner(self) -> None:
        buf = CellBuffer(40, 10)
        dlg = Dialog(x=0, y=0, width=10, height=5)
        dlg.draw(buf)
        assert buf.get(0, 0).char == "┌"

    def test_draws_top_right_corner(self) -> None:
        buf = CellBuffer(40, 10)
        dlg = Dialog(x=0, y=0, width=10, height=5)
        dlg.draw(buf)
        assert buf.get(9, 0).char == "┐"

    def test_draws_bottom_left_corner(self) -> None:
        buf = CellBuffer(40, 10)
        dlg = Dialog(x=0, y=0, width=10, height=5)
        dlg.draw(buf)
        assert buf.get(0, 4).char == "└"

    def test_draws_bottom_right_corner(self) -> None:
        buf = CellBuffer(40, 10)
        dlg = Dialog(x=0, y=0, width=10, height=5)
        dlg.draw(buf)
        assert buf.get(9, 4).char == "┘"

    def test_draws_top_horizontal_border(self) -> None:
        buf = CellBuffer(40, 10)
        dlg = Dialog(x=0, y=0, width=10, height=5)
        dlg.draw(buf)
        for col in range(1, 9):
            assert buf.get(col, 0).char == "─"

    def test_draws_bottom_horizontal_border(self) -> None:
        buf = CellBuffer(40, 10)
        dlg = Dialog(x=0, y=0, width=10, height=5)
        dlg.draw(buf)
        for col in range(1, 9):
            assert buf.get(col, 4).char == "─"

    def test_draws_left_vertical_border(self) -> None:
        buf = CellBuffer(40, 10)
        dlg = Dialog(x=0, y=0, width=10, height=5)
        dlg.draw(buf)
        for row in range(1, 4):
            assert buf.get(0, row).char == "│"

    def test_draws_right_vertical_border(self) -> None:
        buf = CellBuffer(40, 10)
        dlg = Dialog(x=0, y=0, width=10, height=5)
        dlg.draw(buf)
        for row in range(1, 4):
            assert buf.get(9, row).char == "│"

    def test_draws_at_offset_position(self) -> None:
        buf = CellBuffer(40, 10)
        dlg = Dialog(x=5, y=2, width=10, height=5)
        dlg.draw(buf)
        assert buf.get(5, 2).char == "┌"
        assert buf.get(14, 2).char == "┐"
        assert buf.get(5, 6).char == "└"
        assert buf.get(14, 6).char == "┘"

    def test_skips_draw_when_invisible(self) -> None:
        buf = CellBuffer(40, 10)
        dlg = Dialog(x=0, y=0, width=10, height=5)
        dlg.visible = False
        dlg.draw(buf)
        assert buf.get(0, 0).char == " "

    def test_clips_silently_at_buffer_edge(self) -> None:
        """Drawing beyond buffer bounds does not raise."""
        buf = CellBuffer(5, 3)
        dlg = Dialog(x=0, y=0, width=20, height=10)
        dlg.draw(buf)  # Should not raise


# ---------------------------------------------------------------------------
# Drawing — title
# ---------------------------------------------------------------------------


class TestDialogDrawTitle:
    """Title rendering on the top border."""

    def test_title_is_drawn(self) -> None:
        buf = CellBuffer(40, 10)
        dlg = Dialog(title="Hi", x=0, y=0, width=20, height=5)
        dlg.draw(buf)
        # Title is centred on the top row.  Inner width = 18 chars.
        # "Hi" (len 2) → offset = (18 - 2) // 2 = 8 → drawn at col 9
        assert buf.get(9, 0).char == "H"
        assert buf.get(10, 0).char == "i"

    def test_title_is_bold(self) -> None:
        buf = CellBuffer(40, 10)
        dlg = Dialog(title="Hi", x=0, y=0, width=20, height=5)
        dlg.draw(buf)
        assert buf.get(9, 0).bold is True
        assert buf.get(10, 0).bold is True

    def test_empty_title_not_drawn(self) -> None:
        buf = CellBuffer(40, 10)
        dlg = Dialog(title="", x=0, y=0, width=10, height=5)
        dlg.draw(buf)
        # Middle of top border should be horizontal line, not text.
        assert buf.get(5, 0).char == "─"

    def test_title_truncated_when_too_long(self) -> None:
        buf = CellBuffer(40, 10)
        # width=6 → inner width = 4.  Title "ABCDEF" should truncate to "ABCD".
        dlg = Dialog(title="ABCDEF", x=0, y=0, width=6, height=5)
        dlg.draw(buf)
        # Offset = (4 - 4) // 2 = 0 → drawn at col 1
        assert buf.get(1, 0).char == "A"
        assert buf.get(2, 0).char == "B"
        assert buf.get(3, 0).char == "C"
        assert buf.get(4, 0).char == "D"


# ---------------------------------------------------------------------------
# Drawing — body
# ---------------------------------------------------------------------------


class TestDialogDrawBody:
    """Body text rendering inside the dialog."""

    def test_body_is_drawn(self) -> None:
        buf = CellBuffer(40, 10)
        dlg = Dialog(body="Hello", x=0, y=0, width=20, height=5)
        dlg.draw(buf)
        # Body drawn at (1, 1) — inside the border.
        assert buf.get(1, 1).char == "H"
        assert buf.get(2, 1).char == "e"
        assert buf.get(3, 1).char == "l"
        assert buf.get(4, 1).char == "l"
        assert buf.get(5, 1).char == "o"

    def test_empty_body_not_drawn(self) -> None:
        buf = CellBuffer(40, 10)
        dlg = Dialog(body="", x=0, y=0, width=10, height=5)
        dlg.draw(buf)
        # Interior row should remain blank.
        assert buf.get(1, 1).char == " "


# ---------------------------------------------------------------------------
# Drawing — buttons
# ---------------------------------------------------------------------------


class TestDialogDrawButtons:
    """Button rendering inside the dialog."""

    def test_button_is_drawn(self) -> None:
        buf = CellBuffer(40, 10)
        dlg = Dialog(x=0, y=0, width=20, height=5)
        dlg.add_button("OK")
        dlg.draw(buf)
        # Button at row y+h-2 = 3 (above bottom border), col 1 (inside left border).
        # Button renders as "[ OK ]" starting at (1, 3).
        assert buf.get(1, 3).char == "["
        assert buf.get(2, 3).char == " "
        assert buf.get(3, 3).char == "O"
        assert buf.get(4, 3).char == "K"
        assert buf.get(5, 3).char == " "
        assert buf.get(6, 3).char == "]"

    def test_multiple_buttons_laid_out(self) -> None:
        buf = CellBuffer(40, 10)
        dlg = Dialog(x=0, y=0, width=30, height=5)
        dlg.add_button("Yes")
        dlg.add_button("No")
        dlg.draw(buf)
        # First button "[ Yes ]" at col 1, row 3.
        assert buf.get(1, 3).char == "["
        # "Yes" = width 7, spacing 1, so "[ No ]" starts at col 1+7+1 = 9.
        assert buf.get(9, 3).char == "["

    def test_invisible_button_not_drawn(self) -> None:
        buf = CellBuffer(40, 10)
        dlg = Dialog(x=0, y=0, width=20, height=5)
        btn = dlg.add_button("OK")
        btn.visible = False
        dlg.draw(buf)
        # Button row should remain empty.
        assert buf.get(1, 3).char == " "


# ---------------------------------------------------------------------------
# Mouse event handling
# ---------------------------------------------------------------------------


class TestDialogMouseEvents:
    """Mouse event routing and consumption."""

    def test_click_on_button_triggers_callback(self) -> None:
        calls: list[str] = []
        dlg = Dialog(x=0, y=0, width=20, height=5)
        dlg.add_button("OK", on_click=lambda: calls.append("clicked"))
        # Draw to set button positions.
        buf = CellBuffer(40, 10)
        dlg.draw(buf)
        # Click on the button area (row 3, col 3 = inside "[ OK ]").
        event = MouseEvent(x=3, y=3, button="left", action="press")
        result = dlg.handle_event(event)
        assert result is True
        assert calls == ["clicked"]

    def test_click_inside_border_consumed(self) -> None:
        """Clicks inside the dialog but not on a button are consumed."""
        dlg = Dialog(x=0, y=0, width=20, height=5)
        event = MouseEvent(x=5, y=1, button="left", action="press")
        result = dlg.handle_event(event)
        assert result is True

    def test_click_outside_dialog_not_consumed(self) -> None:
        dlg = Dialog(x=0, y=0, width=20, height=5)
        event = MouseEvent(x=25, y=1, button="left", action="press")
        result = dlg.handle_event(event)
        assert result is False

    def test_mouse_move_inside_not_consumed(self) -> None:
        """Only press events are consumed, not move/release."""
        dlg = Dialog(x=0, y=0, width=20, height=5)
        event = MouseEvent(x=5, y=1, button="none", action="move")
        result = dlg.handle_event(event)
        assert result is False


# ---------------------------------------------------------------------------
# Keyboard event handling
# ---------------------------------------------------------------------------


class TestDialogKeyboardEvents:
    """Keyboard event routing to focused buttons."""

    def test_enter_on_focused_button(self) -> None:
        calls: list[str] = []
        dlg = Dialog(x=0, y=0, width=20, height=5)
        btn = dlg.add_button("OK", on_click=lambda: calls.append("clicked"))
        btn.focused = True
        event = KeyEvent(key="enter")
        result = dlg.handle_event(event)
        assert result is True
        assert calls == ["clicked"]

    def test_key_not_consumed_without_focused_button(self) -> None:
        dlg = Dialog(x=0, y=0, width=20, height=5)
        dlg.add_button("OK")
        event = KeyEvent(key="enter")
        result = dlg.handle_event(event)
        assert result is False

    def test_unrecognized_event_not_consumed(self) -> None:
        dlg = Dialog(x=0, y=0, width=20, height=5)
        event = Event()
        result = dlg.handle_event(event)
        assert result is False


# ---------------------------------------------------------------------------
# Repr
# ---------------------------------------------------------------------------


class TestDialogRepr:
    """String representation."""

    def test_repr_basic(self) -> None:
        dlg = Dialog(title="Test", x=1, y=2, width=30, height=7)
        r = repr(dlg)
        assert "Dialog(" in r
        assert "title='Test'" in r
        assert "x=1" in r
        assert "y=2" in r

    def test_repr_shows_button_count(self) -> None:
        dlg = Dialog()
        dlg.add_button("OK")
        dlg.add_button("Cancel")
        assert "buttons=2" in repr(dlg)


# ---------------------------------------------------------------------------
# Import from package root
# ---------------------------------------------------------------------------


class TestDialogImport:
    """Dialog is accessible from the wyby package root."""

    def test_import_from_wyby(self) -> None:
        from wyby import Dialog as D
        assert D is Dialog
