"""Tests for wyby.button — Button widget with click handler."""

from __future__ import annotations

import pytest

from wyby.button import Button
from wyby.event import Event
from wyby.grid import CellBuffer
from wyby.input import KeyEvent, MouseEvent


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestButtonConstruction:
    """Button creation and default state."""

    def test_default_position(self) -> None:
        btn = Button("OK")
        assert btn.x == 0
        assert btn.y == 0

    def test_custom_position(self) -> None:
        btn = Button("OK", x=5, y=10)
        assert btn.x == 5
        assert btn.y == 10

    def test_width_includes_label_padding_and_brackets(self) -> None:
        # "OK" -> "[ OK ]" = 6 chars
        btn = Button("OK")
        assert btn.width == 6

    def test_width_longer_label(self) -> None:
        # "Start Game" -> "[ Start Game ]" = 14 chars
        btn = Button("Start Game")
        assert btn.width == 14

    def test_height_is_one(self) -> None:
        btn = Button("OK")
        assert btn.height == 1

    def test_default_visible(self) -> None:
        btn = Button("OK")
        assert btn.visible is True

    def test_default_not_focused(self) -> None:
        btn = Button("OK")
        assert btn.focused is False

    def test_default_no_callback(self) -> None:
        btn = Button("OK")
        assert btn.on_click is None

    def test_with_callback(self) -> None:
        def handler() -> None:
            pass
        btn = Button("OK", on_click=handler)
        assert btn.on_click is handler

    def test_label_stored(self) -> None:
        btn = Button("Start")
        assert btn.label == "Start"


# ---------------------------------------------------------------------------
# Type validation
# ---------------------------------------------------------------------------


class TestButtonTypeValidation:
    """Type checking on constructor arguments."""

    def test_label_rejects_non_string(self) -> None:
        with pytest.raises(TypeError, match="label must be a str"):
            Button(123)  # type: ignore[arg-type]

    def test_label_rejects_none(self) -> None:
        with pytest.raises(TypeError, match="label must be a str"):
            Button(None)  # type: ignore[arg-type]

    def test_label_rejects_empty(self) -> None:
        with pytest.raises(ValueError, match="label must not be empty"):
            Button("")

    def test_on_click_rejects_non_callable(self) -> None:
        with pytest.raises(TypeError, match="on_click must be callable"):
            Button("OK", on_click="not_callable")  # type: ignore[arg-type]

    def test_x_rejects_float(self) -> None:
        with pytest.raises(TypeError, match="x must be an int"):
            Button("OK", x=1.5)  # type: ignore[arg-type]

    def test_y_rejects_float(self) -> None:
        with pytest.raises(TypeError, match="y must be an int"):
            Button("OK", y=1.5)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Label property
# ---------------------------------------------------------------------------


class TestButtonLabel:
    """Label property getter and setter."""

    def test_set_label(self) -> None:
        btn = Button("OK")
        btn.label = "Cancel"
        assert btn.label == "Cancel"

    def test_set_label_updates_width(self) -> None:
        btn = Button("OK")  # width = 6
        btn.label = "Start Game"  # width should become 14
        assert btn.width == 14

    def test_set_label_rejects_non_string(self) -> None:
        btn = Button("OK")
        with pytest.raises(TypeError, match="label must be a str"):
            btn.label = 42  # type: ignore[assignment]

    def test_set_label_rejects_empty(self) -> None:
        btn = Button("OK")
        with pytest.raises(ValueError, match="label must not be empty"):
            btn.label = ""


# ---------------------------------------------------------------------------
# on_click property
# ---------------------------------------------------------------------------


class TestButtonOnClick:
    """on_click callback property."""

    def test_set_on_click(self) -> None:
        btn = Button("OK")
        calls: list[str] = []
        btn.on_click = lambda: calls.append("clicked")
        assert btn.on_click is not None

    def test_set_on_click_none(self) -> None:
        btn = Button("OK", on_click=lambda: None)
        btn.on_click = None
        assert btn.on_click is None

    def test_set_on_click_rejects_non_callable(self) -> None:
        btn = Button("OK")
        with pytest.raises(TypeError, match="on_click must be callable"):
            btn.on_click = 42  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Drawing
# ---------------------------------------------------------------------------


class TestButtonDraw:
    """Button rendering into CellBuffer."""

    def test_draws_label_with_brackets(self) -> None:
        buf = CellBuffer(20, 5)
        btn = Button("OK", x=0, y=0)
        btn.draw(buf)
        # Expected: "[ OK ]"
        assert buf.get(0, 0).char == "["
        assert buf.get(1, 0).char == " "
        assert buf.get(2, 0).char == "O"
        assert buf.get(3, 0).char == "K"
        assert buf.get(4, 0).char == " "
        assert buf.get(5, 0).char == "]"

    def test_draws_at_position(self) -> None:
        buf = CellBuffer(20, 10)
        btn = Button("Go", x=3, y=2)
        btn.draw(buf)
        assert buf.get(3, 2).char == "["
        assert buf.get(4, 2).char == " "
        assert buf.get(5, 2).char == "G"
        assert buf.get(6, 2).char == "o"

    def test_skips_draw_when_invisible(self) -> None:
        buf = CellBuffer(20, 5)
        btn = Button("OK", x=0, y=0)
        btn.visible = False
        btn.draw(buf)
        # Buffer should remain blank
        assert buf.get(0, 0).char == " "
        assert buf.get(1, 0).char == " "

    def test_draws_bold_when_focused(self) -> None:
        buf = CellBuffer(20, 5)
        btn = Button("OK", x=0, y=0)
        btn.focused = True
        btn.draw(buf)
        # Check that the cell is bold
        assert buf.get(0, 0).bold is True
        assert buf.get(2, 0).bold is True

    def test_draws_not_bold_when_unfocused(self) -> None:
        buf = CellBuffer(20, 5)
        btn = Button("OK", x=0, y=0)
        btn.draw(buf)
        assert buf.get(0, 0).bold is False

    def test_clips_silently_at_buffer_edge(self) -> None:
        """Drawing beyond buffer bounds does not raise."""
        buf = CellBuffer(3, 1)
        btn = Button("LongLabel", x=0, y=0)
        btn.draw(buf)  # Should not raise


# ---------------------------------------------------------------------------
# Mouse click handling
# ---------------------------------------------------------------------------


class TestButtonMouseClick:
    """Mouse event handling for button clicks."""

    def test_left_click_inside_triggers_callback(self) -> None:
        calls: list[str] = []
        btn = Button("OK", x=0, y=0, on_click=lambda: calls.append("clicked"))
        event = MouseEvent(x=2, y=0, button="left", action="press")
        result = btn.handle_event(event)
        assert result is True
        assert calls == ["clicked"]

    def test_left_click_outside_ignored(self) -> None:
        calls: list[str] = []
        btn = Button("OK", x=0, y=0, on_click=lambda: calls.append("clicked"))
        event = MouseEvent(x=20, y=0, button="left", action="press")
        result = btn.handle_event(event)
        assert result is False
        assert calls == []

    def test_right_click_inside_ignored(self) -> None:
        calls: list[str] = []
        btn = Button("OK", x=0, y=0, on_click=lambda: calls.append("clicked"))
        event = MouseEvent(x=2, y=0, button="right", action="press")
        result = btn.handle_event(event)
        assert result is False
        assert calls == []

    def test_left_release_inside_ignored(self) -> None:
        """Only press events trigger the button, not release."""
        calls: list[str] = []
        btn = Button("OK", x=0, y=0, on_click=lambda: calls.append("clicked"))
        event = MouseEvent(x=2, y=0, button="left", action="release")
        result = btn.handle_event(event)
        assert result is False
        assert calls == []

    def test_click_consumed_even_without_callback(self) -> None:
        """Clicks inside the button are consumed even if on_click is None."""
        btn = Button("OK", x=0, y=0)
        event = MouseEvent(x=2, y=0, button="left", action="press")
        result = btn.handle_event(event)
        assert result is True

    def test_click_at_left_edge(self) -> None:
        calls: list[str] = []
        btn = Button("OK", x=5, y=3, on_click=lambda: calls.append("clicked"))
        event = MouseEvent(x=5, y=3, button="left", action="press")
        result = btn.handle_event(event)
        assert result is True
        assert calls == ["clicked"]

    def test_click_at_right_edge_exclusive(self) -> None:
        """Right edge is exclusive (standard half-open interval)."""
        calls: list[str] = []
        # "OK" -> width=6, so x range is [5, 11)
        btn = Button("OK", x=5, y=3, on_click=lambda: calls.append("clicked"))
        event = MouseEvent(x=11, y=3, button="left", action="press")
        result = btn.handle_event(event)
        assert result is False
        assert calls == []

    def test_click_just_inside_right_edge(self) -> None:
        calls: list[str] = []
        # "OK" -> width=6, x range [5, 11), so x=10 is inside
        btn = Button("OK", x=5, y=3, on_click=lambda: calls.append("clicked"))
        event = MouseEvent(x=10, y=3, button="left", action="press")
        result = btn.handle_event(event)
        assert result is True
        assert calls == ["clicked"]

    def test_scroll_event_ignored(self) -> None:
        calls: list[str] = []
        btn = Button("OK", x=0, y=0, on_click=lambda: calls.append("clicked"))
        event = MouseEvent(x=2, y=0, button="scroll_up", action="scroll")
        result = btn.handle_event(event)
        assert result is False
        assert calls == []

    def test_mouse_move_ignored(self) -> None:
        calls: list[str] = []
        btn = Button("OK", x=0, y=0, on_click=lambda: calls.append("clicked"))
        event = MouseEvent(x=2, y=0, button="none", action="move")
        result = btn.handle_event(event)
        assert result is False
        assert calls == []


# ---------------------------------------------------------------------------
# Keyboard activation
# ---------------------------------------------------------------------------


class TestButtonKeyboard:
    """Keyboard event handling for button activation."""

    def test_enter_when_focused_triggers_callback(self) -> None:
        calls: list[str] = []
        btn = Button("OK", on_click=lambda: calls.append("clicked"))
        btn.focused = True
        event = KeyEvent(key="enter")
        result = btn.handle_event(event)
        assert result is True
        assert calls == ["clicked"]

    def test_space_when_focused_triggers_callback(self) -> None:
        calls: list[str] = []
        btn = Button("OK", on_click=lambda: calls.append("clicked"))
        btn.focused = True
        event = KeyEvent(key="space")
        result = btn.handle_event(event)
        assert result is True
        assert calls == ["clicked"]

    def test_enter_when_not_focused_ignored(self) -> None:
        calls: list[str] = []
        btn = Button("OK", on_click=lambda: calls.append("clicked"))
        event = KeyEvent(key="enter")
        result = btn.handle_event(event)
        assert result is False
        assert calls == []

    def test_space_when_not_focused_ignored(self) -> None:
        calls: list[str] = []
        btn = Button("OK", on_click=lambda: calls.append("clicked"))
        event = KeyEvent(key="space")
        result = btn.handle_event(event)
        assert result is False
        assert calls == []

    def test_other_key_when_focused_ignored(self) -> None:
        calls: list[str] = []
        btn = Button("OK", on_click=lambda: calls.append("clicked"))
        btn.focused = True
        event = KeyEvent(key="a")
        result = btn.handle_event(event)
        assert result is False
        assert calls == []

    def test_key_consumed_even_without_callback(self) -> None:
        """Enter/Space while focused is consumed even if on_click is None."""
        btn = Button("OK")
        btn.focused = True
        event = KeyEvent(key="enter")
        result = btn.handle_event(event)
        assert result is True

    def test_ctrl_enter_when_focused_triggers(self) -> None:
        """Ctrl modifier does not prevent activation."""
        calls: list[str] = []
        btn = Button("OK", on_click=lambda: calls.append("clicked"))
        btn.focused = True
        event = KeyEvent(key="enter", ctrl=True)
        result = btn.handle_event(event)
        assert result is True
        assert calls == ["clicked"]


# ---------------------------------------------------------------------------
# Unrecognized events
# ---------------------------------------------------------------------------


class TestButtonUnrecognizedEvents:
    """Events that are neither mouse nor key."""

    def test_base_event_returns_false(self) -> None:
        btn = Button("OK", on_click=lambda: None)
        btn.focused = True
        event = Event()
        result = btn.handle_event(event)
        assert result is False


# ---------------------------------------------------------------------------
# Callback behavior
# ---------------------------------------------------------------------------


class TestButtonCallback:
    """Callback invocation behavior."""

    def test_callback_exception_propagates(self) -> None:
        def bad_callback() -> None:
            raise RuntimeError("oops")

        btn = Button("OK", on_click=bad_callback)
        btn.focused = True
        event = KeyEvent(key="enter")
        with pytest.raises(RuntimeError, match="oops"):
            btn.handle_event(event)

    def test_multiple_clicks_fire_multiple_times(self) -> None:
        calls: list[str] = []
        btn = Button("OK", x=0, y=0, on_click=lambda: calls.append("clicked"))
        event = MouseEvent(x=2, y=0, button="left", action="press")
        btn.handle_event(event)
        btn.handle_event(event)
        btn.handle_event(event)
        assert len(calls) == 3


# ---------------------------------------------------------------------------
# Repr
# ---------------------------------------------------------------------------


class TestButtonRepr:
    """String representation."""

    def test_repr_basic(self) -> None:
        btn = Button("OK", x=1, y=2)
        assert repr(btn) == "Button(label='OK', x=1, y=2, w=6, h=1)"

    def test_repr_invisible(self) -> None:
        btn = Button("OK")
        btn.visible = False
        assert "visible=False" in repr(btn)

    def test_repr_focused(self) -> None:
        btn = Button("OK")
        btn.focused = True
        assert "focused" in repr(btn)


# ---------------------------------------------------------------------------
# Widget hierarchy
# ---------------------------------------------------------------------------


class TestButtonHierarchy:
    """Button participates in widget parent/child hierarchy."""

    def test_button_is_a_widget(self) -> None:
        from wyby.widget import Widget
        btn = Button("OK")
        assert isinstance(btn, Widget)

    def test_button_can_be_child(self) -> None:
        from wyby.widget import Widget

        class Panel(Widget):
            def draw(self, buffer: CellBuffer) -> None:
                pass

        panel = Panel(x=0, y=0, width=40, height=10)
        btn = Button("OK", x=5, y=3)
        panel.add_child(btn)
        assert btn.parent is panel
        assert btn in panel.children


# ---------------------------------------------------------------------------
# Import from package root
# ---------------------------------------------------------------------------


class TestButtonImport:
    """Button is accessible from the wyby package root."""

    def test_import_from_wyby(self) -> None:
        from wyby import Button as B
        assert B is Button
