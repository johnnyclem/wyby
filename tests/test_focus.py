"""Tests for wyby.focus — FocusManager mouse focus and click routing."""

from __future__ import annotations

import pytest

from wyby.button import Button
from wyby.event import Event
from wyby.focus import FocusManager
from wyby.grid import CellBuffer
from wyby.input import KeyEvent, MouseEvent
from wyby.widget import Widget


# -- Helpers ----------------------------------------------------------------

class DummyWidget(Widget):
    """Minimal concrete Widget for testing."""

    def __init__(self, x: int = 0, y: int = 0, width: int = 10, height: int = 1) -> None:
        super().__init__(x=x, y=y, width=width, height=height)
        self.events_received: list[Event] = []

    def draw(self, buffer: CellBuffer) -> None:
        pass

    def handle_event(self, event: Event) -> bool:
        self.events_received.append(event)
        return True


class NonConsumingWidget(Widget):
    """Widget that never consumes events."""

    def __init__(self, x: int = 0, y: int = 0, width: int = 10, height: int = 1) -> None:
        super().__init__(x=x, y=y, width=width, height=height)

    def draw(self, buffer: CellBuffer) -> None:
        pass

    def handle_event(self, event: Event) -> bool:
        return False


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestFocusManagerConstruction:
    """FocusManager creation and initial state."""

    def test_empty_by_default(self) -> None:
        fm = FocusManager()
        assert len(fm) == 0
        assert fm.focused_widget is None

    def test_initial_widgets(self) -> None:
        a = DummyWidget()
        b = DummyWidget()
        fm = FocusManager(widgets=[a, b])
        assert len(fm) == 2
        assert fm.widgets == [a, b]

    def test_no_initial_focus(self) -> None:
        a = DummyWidget()
        fm = FocusManager(widgets=[a])
        assert fm.focused_widget is None
        assert a.focused is False


# ---------------------------------------------------------------------------
# Widget registration
# ---------------------------------------------------------------------------


class TestFocusManagerAdd:
    """Adding and removing widgets."""

    def test_add_widget(self) -> None:
        fm = FocusManager()
        w = DummyWidget()
        fm.add(w)
        assert w in fm
        assert len(fm) == 1

    def test_add_duplicate_is_noop(self) -> None:
        fm = FocusManager()
        w = DummyWidget()
        fm.add(w)
        fm.add(w)
        assert len(fm) == 1

    def test_add_rejects_non_widget(self) -> None:
        fm = FocusManager()
        with pytest.raises(TypeError, match="widget must be a Widget"):
            fm.add("not a widget")  # type: ignore[arg-type]

    def test_remove_widget(self) -> None:
        fm = FocusManager()
        w = DummyWidget()
        fm.add(w)
        fm.remove(w)
        assert w not in fm
        assert len(fm) == 0

    def test_remove_unknown_raises(self) -> None:
        fm = FocusManager()
        w = DummyWidget()
        with pytest.raises(ValueError, match="not managed"):
            fm.remove(w)

    def test_remove_focused_clears_focus(self) -> None:
        fm = FocusManager()
        w = DummyWidget()
        fm.add(w)
        fm.set_focus(w)
        assert fm.focused_widget is w
        fm.remove(w)
        assert fm.focused_widget is None
        assert w.focused is False

    def test_remove_unfocused_preserves_focus(self) -> None:
        fm = FocusManager()
        a = DummyWidget()
        b = DummyWidget()
        fm.add(a)
        fm.add(b)
        fm.set_focus(a)
        fm.remove(b)
        assert fm.focused_widget is a

    def test_clear_removes_all(self) -> None:
        a = DummyWidget()
        b = DummyWidget()
        fm = FocusManager(widgets=[a, b])
        fm.set_focus(a)
        fm.clear()
        assert len(fm) == 0
        assert fm.focused_widget is None
        assert a.focused is False

    def test_widgets_returns_copy(self) -> None:
        fm = FocusManager()
        w = DummyWidget()
        fm.add(w)
        copy = fm.widgets
        copy.append(DummyWidget())
        assert len(fm) == 1  # Internal list unaffected


# ---------------------------------------------------------------------------
# Focus management
# ---------------------------------------------------------------------------


class TestFocusManagerSetFocus:
    """Explicit focus management via set_focus."""

    def test_set_focus(self) -> None:
        fm = FocusManager()
        w = DummyWidget()
        fm.add(w)
        fm.set_focus(w)
        assert fm.focused_widget is w
        assert w.focused is True

    def test_set_focus_blurs_previous(self) -> None:
        fm = FocusManager()
        a = DummyWidget()
        b = DummyWidget()
        fm.add(a)
        fm.add(b)
        fm.set_focus(a)
        fm.set_focus(b)
        assert a.focused is False
        assert b.focused is True
        assert fm.focused_widget is b

    def test_set_focus_none_clears(self) -> None:
        fm = FocusManager()
        w = DummyWidget()
        fm.add(w)
        fm.set_focus(w)
        fm.set_focus(None)
        assert fm.focused_widget is None
        assert w.focused is False

    def test_set_focus_same_widget_is_noop(self) -> None:
        fm = FocusManager()
        w = DummyWidget()
        fm.add(w)
        fm.set_focus(w)
        # Setting the same widget again should not trigger on_blur/on_focus
        fm.set_focus(w)
        assert fm.focused_widget is w
        assert w.focused is True

    def test_set_focus_unmanaged_raises(self) -> None:
        fm = FocusManager()
        w = DummyWidget()
        with pytest.raises(ValueError, match="not managed"):
            fm.set_focus(w)


# ---------------------------------------------------------------------------
# Tab cycling
# ---------------------------------------------------------------------------


class TestFocusManagerCycling:
    """Focus cycling via focus_next / focus_prev."""

    def test_focus_next_from_none(self) -> None:
        a = DummyWidget()
        b = DummyWidget()
        fm = FocusManager(widgets=[a, b])
        result = fm.focus_next()
        assert result is a
        assert fm.focused_widget is a

    def test_focus_next_cycles(self) -> None:
        a = DummyWidget()
        b = DummyWidget()
        c = DummyWidget()
        fm = FocusManager(widgets=[a, b, c])
        fm.set_focus(a)
        assert fm.focus_next() is b
        assert fm.focus_next() is c
        assert fm.focus_next() is a  # Wraps around

    def test_focus_prev_from_none(self) -> None:
        a = DummyWidget()
        b = DummyWidget()
        fm = FocusManager(widgets=[a, b])
        result = fm.focus_prev()
        assert result is b  # Last widget
        assert fm.focused_widget is b

    def test_focus_prev_cycles(self) -> None:
        a = DummyWidget()
        b = DummyWidget()
        c = DummyWidget()
        fm = FocusManager(widgets=[a, b, c])
        fm.set_focus(a)
        assert fm.focus_prev() is c  # Wraps backward
        assert fm.focus_prev() is b
        assert fm.focus_prev() is a

    def test_focus_next_skips_invisible(self) -> None:
        a = DummyWidget()
        b = DummyWidget()
        c = DummyWidget()
        b.visible = False
        fm = FocusManager(widgets=[a, b, c])
        fm.set_focus(a)
        result = fm.focus_next()
        assert result is c  # Skipped b

    def test_focus_prev_skips_invisible(self) -> None:
        a = DummyWidget()
        b = DummyWidget()
        c = DummyWidget()
        b.visible = False
        fm = FocusManager(widgets=[a, b, c])
        fm.set_focus(c)
        result = fm.focus_prev()
        assert result is a  # Skipped b

    def test_focus_next_all_invisible_clears(self) -> None:
        a = DummyWidget()
        a.visible = False
        fm = FocusManager(widgets=[a])
        result = fm.focus_next()
        assert result is None
        assert fm.focused_widget is None

    def test_focus_next_empty_returns_none(self) -> None:
        fm = FocusManager()
        result = fm.focus_next()
        assert result is None

    def test_focus_next_single_widget_stays(self) -> None:
        a = DummyWidget()
        fm = FocusManager(widgets=[a])
        fm.set_focus(a)
        result = fm.focus_next()
        assert result is a  # Wraps to self


# ---------------------------------------------------------------------------
# Mouse click dispatch (click-to-focus + routing)
# ---------------------------------------------------------------------------


class TestFocusManagerMouseClick:
    """Mouse press event dispatch with hit-testing."""

    def test_click_on_widget_focuses_and_dispatches(self) -> None:
        w = DummyWidget(x=5, y=3, width=10, height=1)
        fm = FocusManager(widgets=[w])
        event = MouseEvent(x=7, y=3, button="left", action="press")
        consumed = fm.dispatch(event)
        assert consumed is True
        assert fm.focused_widget is w
        assert w.focused is True
        assert event in w.events_received

    def test_click_on_empty_space_clears_focus(self) -> None:
        w = DummyWidget(x=5, y=3, width=10, height=1)
        fm = FocusManager(widgets=[w])
        fm.set_focus(w)
        event = MouseEvent(x=50, y=50, button="left", action="press")
        consumed = fm.dispatch(event)
        assert consumed is False
        assert fm.focused_widget is None
        assert w.focused is False

    def test_click_topmost_widget_in_overlap(self) -> None:
        """When widgets overlap, the topmost (last-added) gets the click."""
        bottom = DummyWidget(x=0, y=0, width=20, height=5)
        top = DummyWidget(x=5, y=2, width=10, height=3)
        fm = FocusManager(widgets=[bottom, top])
        # Click at (7, 3) — inside both widgets
        event = MouseEvent(x=7, y=3, button="left", action="press")
        consumed = fm.dispatch(event)
        assert consumed is True
        assert fm.focused_widget is top
        assert event in top.events_received
        assert event not in bottom.events_received

    def test_click_on_bottom_widget_outside_top(self) -> None:
        """Click lands on the bottom widget outside the top widget's bounds."""
        bottom = DummyWidget(x=0, y=0, width=20, height=5)
        top = DummyWidget(x=5, y=2, width=10, height=3)
        fm = FocusManager(widgets=[bottom, top])
        # Click at (1, 1) — only inside bottom
        event = MouseEvent(x=1, y=1, button="left", action="press")
        consumed = fm.dispatch(event)
        assert consumed is True
        assert fm.focused_widget is bottom
        assert event in bottom.events_received

    def test_click_skips_invisible_widget(self) -> None:
        bottom = DummyWidget(x=0, y=0, width=20, height=5)
        top = DummyWidget(x=0, y=0, width=20, height=5)
        top.visible = False
        fm = FocusManager(widgets=[bottom, top])
        event = MouseEvent(x=5, y=2, button="left", action="press")
        consumed = fm.dispatch(event)
        assert consumed is True
        assert fm.focused_widget is bottom

    def test_right_click_dispatches_to_focused(self) -> None:
        """Non-press mouse events go to the focused widget."""
        w = DummyWidget(x=0, y=0, width=10, height=1)
        fm = FocusManager(widgets=[w])
        fm.set_focus(w)
        # Right-click press is still a press event — should hit-test
        event = MouseEvent(x=5, y=0, button="right", action="press")
        consumed = fm.dispatch(event)
        assert consumed is True
        assert event in w.events_received

    def test_mouse_release_goes_to_focused(self) -> None:
        """Mouse release events route to focused widget, not hit-tested."""
        a = DummyWidget(x=0, y=0, width=10, height=1)
        b = DummyWidget(x=0, y=1, width=10, height=1)
        fm = FocusManager(widgets=[a, b])
        fm.set_focus(a)
        # Release at b's position — should still go to focused (a)
        event = MouseEvent(x=5, y=1, button="left", action="release")
        consumed = fm.dispatch(event)
        assert consumed is True
        assert event in a.events_received
        assert event not in b.events_received

    def test_mouse_move_goes_to_focused(self) -> None:
        w = DummyWidget(x=0, y=0, width=10, height=1)
        fm = FocusManager(widgets=[w])
        fm.set_focus(w)
        event = MouseEvent(x=50, y=50, button="none", action="move")
        consumed = fm.dispatch(event)
        assert consumed is True
        assert event in w.events_received

    def test_scroll_goes_to_focused(self) -> None:
        w = DummyWidget(x=0, y=0, width=10, height=1)
        fm = FocusManager(widgets=[w])
        fm.set_focus(w)
        event = MouseEvent(x=5, y=0, button="scroll_up", action="scroll")
        consumed = fm.dispatch(event)
        assert consumed is True
        assert event in w.events_received

    def test_mouse_release_no_focus_returns_false(self) -> None:
        fm = FocusManager()
        event = MouseEvent(x=5, y=5, button="left", action="release")
        assert fm.dispatch(event) is False


# ---------------------------------------------------------------------------
# Keyboard event dispatch
# ---------------------------------------------------------------------------


class TestFocusManagerKeyboard:
    """Keyboard event routing to focused widget."""

    def test_key_event_goes_to_focused(self) -> None:
        w = DummyWidget(x=0, y=0, width=10, height=1)
        fm = FocusManager(widgets=[w])
        fm.set_focus(w)
        event = KeyEvent(key="enter")
        consumed = fm.dispatch(event)
        assert consumed is True
        assert event in w.events_received

    def test_key_event_no_focus_returns_false(self) -> None:
        w = DummyWidget(x=0, y=0, width=10, height=1)
        fm = FocusManager(widgets=[w])
        event = KeyEvent(key="enter")
        consumed = fm.dispatch(event)
        assert consumed is False

    def test_key_event_not_consumed_returns_false(self) -> None:
        w = NonConsumingWidget(x=0, y=0, width=10, height=1)
        fm = FocusManager(widgets=[w])
        fm.set_focus(w)
        event = KeyEvent(key="a")
        consumed = fm.dispatch(event)
        assert consumed is False


# ---------------------------------------------------------------------------
# Integration with Button widget
# ---------------------------------------------------------------------------


class TestFocusManagerWithButton:
    """End-to-end tests with real Button widgets."""

    def test_click_button_triggers_callback(self) -> None:
        calls: list[str] = []
        btn = Button("OK", x=0, y=0, on_click=lambda: calls.append("ok"))
        fm = FocusManager(widgets=[btn])
        event = MouseEvent(x=2, y=0, button="left", action="press")
        consumed = fm.dispatch(event)
        assert consumed is True
        assert calls == ["ok"]
        assert fm.focused_widget is btn

    def test_click_focuses_button_then_keyboard_activates(self) -> None:
        """Click to focus, then Enter to activate."""
        calls: list[str] = []
        btn = Button("OK", x=0, y=0, on_click=lambda: calls.append("ok"))
        fm = FocusManager(widgets=[btn])
        # Click to focus
        click = MouseEvent(x=2, y=0, button="left", action="press")
        fm.dispatch(click)
        assert fm.focused_widget is btn
        calls.clear()  # Clear the click activation
        # Now keyboard activate
        key = KeyEvent(key="enter")
        consumed = fm.dispatch(key)
        assert consumed is True
        assert calls == ["ok"]

    def test_overlapping_buttons_topmost_gets_click(self) -> None:
        calls: list[str] = []
        btn_back = Button("Back", x=0, y=0, on_click=lambda: calls.append("back"))
        btn_front = Button("Front", x=0, y=0, on_click=lambda: calls.append("front"))
        fm = FocusManager(widgets=[btn_back, btn_front])
        event = MouseEvent(x=2, y=0, button="left", action="press")
        fm.dispatch(event)
        assert calls == ["front"]
        assert fm.focused_widget is btn_front

    def test_tab_cycle_between_buttons(self) -> None:
        btn_a = Button("A", x=0, y=0)
        btn_b = Button("B", x=0, y=1)
        btn_c = Button("C", x=0, y=2)
        fm = FocusManager(widgets=[btn_a, btn_b, btn_c])
        assert fm.focus_next() is btn_a
        assert btn_a.focused is True
        assert fm.focus_next() is btn_b
        assert btn_a.focused is False
        assert btn_b.focused is True
        assert fm.focus_next() is btn_c
        assert fm.focus_next() is btn_a  # Wrap


# ---------------------------------------------------------------------------
# widget_at introspection
# ---------------------------------------------------------------------------


class TestFocusManagerWidgetAt:
    """Hit-testing via widget_at."""

    def test_widget_at_hit(self) -> None:
        w = DummyWidget(x=5, y=3, width=10, height=2)
        fm = FocusManager(widgets=[w])
        assert fm.widget_at(7, 4) is w

    def test_widget_at_miss(self) -> None:
        w = DummyWidget(x=5, y=3, width=10, height=2)
        fm = FocusManager(widgets=[w])
        assert fm.widget_at(50, 50) is None

    def test_widget_at_returns_topmost(self) -> None:
        bottom = DummyWidget(x=0, y=0, width=20, height=5)
        top = DummyWidget(x=0, y=0, width=20, height=5)
        fm = FocusManager(widgets=[bottom, top])
        assert fm.widget_at(5, 2) is top

    def test_widget_at_skips_invisible(self) -> None:
        bottom = DummyWidget(x=0, y=0, width=20, height=5)
        top = DummyWidget(x=0, y=0, width=20, height=5)
        top.visible = False
        fm = FocusManager(widgets=[bottom, top])
        assert fm.widget_at(5, 2) is bottom

    def test_widget_at_empty(self) -> None:
        fm = FocusManager()
        assert fm.widget_at(0, 0) is None


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestFocusManagerEdgeCases:
    """Edge cases and boundary conditions."""

    def test_dispatch_unknown_event_type(self) -> None:
        """Non-mouse, non-key events go to focused widget."""
        w = DummyWidget(x=0, y=0, width=10, height=1)
        fm = FocusManager(widgets=[w])
        fm.set_focus(w)
        event = Event()  # Base event, not Key or Mouse
        consumed = fm.dispatch(event)
        assert consumed is True
        assert event in w.events_received

    def test_dispatch_no_widgets_returns_false(self) -> None:
        fm = FocusManager()
        event = MouseEvent(x=0, y=0, button="left", action="press")
        assert fm.dispatch(event) is False

    def test_click_moves_focus_between_widgets(self) -> None:
        a = DummyWidget(x=0, y=0, width=10, height=1)
        b = DummyWidget(x=0, y=1, width=10, height=1)
        fm = FocusManager(widgets=[a, b])
        # Click a
        fm.dispatch(MouseEvent(x=5, y=0, button="left", action="press"))
        assert fm.focused_widget is a
        assert a.focused is True
        assert b.focused is False
        # Click b
        fm.dispatch(MouseEvent(x=5, y=1, button="left", action="press"))
        assert fm.focused_widget is b
        assert a.focused is False
        assert b.focused is True

    def test_callback_exception_propagates(self) -> None:
        def bad_callback() -> None:
            raise RuntimeError("boom")

        btn = Button("Bad", x=0, y=0, on_click=bad_callback)
        fm = FocusManager(widgets=[btn])
        event = MouseEvent(x=2, y=0, button="left", action="press")
        with pytest.raises(RuntimeError, match="boom"):
            fm.dispatch(event)

    def test_contains_operator(self) -> None:
        w = DummyWidget()
        fm = FocusManager()
        assert w not in fm
        fm.add(w)
        assert w in fm

    def test_repr(self) -> None:
        fm = FocusManager()
        assert "FocusManager" in repr(fm)
        assert "widgets=0" in repr(fm)
        assert "focused=None" in repr(fm)

    def test_repr_with_focus(self) -> None:
        w = DummyWidget()
        fm = FocusManager(widgets=[w])
        fm.set_focus(w)
        r = repr(fm)
        assert "widgets=1" in r
        assert "DummyWidget" in r


# ---------------------------------------------------------------------------
# Import from package root
# ---------------------------------------------------------------------------


class TestFocusManagerImport:
    """FocusManager is accessible from the wyby package root."""

    def test_import_from_wyby(self) -> None:
        from wyby import FocusManager as FM
        assert FM is FocusManager
