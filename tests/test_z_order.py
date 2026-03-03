"""Tests for document z-order: UI widgets render on top of game content.

This module tests the z_index property on Widget, z-sorted overlay
drawing in Renderer, and z-order-aware hit-testing in FocusManager.
"""

from __future__ import annotations

import io

import pytest
from rich.console import Console

from wyby.event import Event
from wyby.focus import FocusManager
from wyby.grid import CellBuffer
from wyby.input import MouseEvent
from wyby.renderer import Renderer
from wyby.widget import Widget


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class StubWidget(Widget):
    """Minimal widget that writes a single marker character at (x, y)."""

    def __init__(
        self,
        x: int = 0,
        y: int = 0,
        width: int = 1,
        height: int = 1,
        marker: str = "X",
        *,
        z_index: int = 0,
    ) -> None:
        super().__init__(x=x, y=y, width=width, height=height, z_index=z_index)
        self.marker = marker
        self.draw_count = 0
        self.events_received: list[Event] = []

    def draw(self, buffer: CellBuffer) -> None:
        if not self.visible:
            return
        self.draw_count += 1
        buffer.put_text(self.x, self.y, self.marker)

    def handle_event(self, event: Event) -> bool:
        self.events_received.append(event)
        return True


def _make_renderer() -> Renderer:
    console = Console(file=io.StringIO(), force_terminal=True)
    return Renderer(console=console)


# ===========================================================================
# Widget z_index property
# ===========================================================================


class TestWidgetZIndex:
    """Widget.z_index construction, getting, and setting."""

    def test_default_z_index_is_zero(self) -> None:
        w = StubWidget()
        assert w.z_index == 0

    def test_constructor_z_index(self) -> None:
        w = StubWidget(z_index=5)
        assert w.z_index == 5

    def test_negative_z_index(self) -> None:
        w = StubWidget(z_index=-10)
        assert w.z_index == -10

    def test_set_z_index(self) -> None:
        w = StubWidget()
        w.z_index = 42
        assert w.z_index == 42

    def test_set_z_index_negative(self) -> None:
        w = StubWidget()
        w.z_index = -5
        assert w.z_index == -5

    def test_z_index_rejects_float(self) -> None:
        with pytest.raises(TypeError, match="z_index must be an int"):
            StubWidget(z_index=1.5)  # type: ignore[arg-type]

    def test_z_index_rejects_bool(self) -> None:
        with pytest.raises(TypeError, match="z_index must be an int"):
            StubWidget(z_index=True)  # type: ignore[arg-type]

    def test_set_z_index_rejects_string(self) -> None:
        w = StubWidget()
        with pytest.raises(TypeError, match="z_index must be an int"):
            w.z_index = "high"  # type: ignore[assignment]

    def test_set_z_index_rejects_bool(self) -> None:
        w = StubWidget()
        with pytest.raises(TypeError, match="z_index must be an int"):
            w.z_index = False  # type: ignore[assignment]

    def test_repr_omits_zero_z_index(self) -> None:
        w = StubWidget(x=0, y=0)
        assert "z=" not in repr(w)

    def test_repr_shows_nonzero_z_index(self) -> None:
        w = StubWidget(x=0, y=0, z_index=3)
        assert "z=3" in repr(w)

    def test_repr_shows_negative_z_index(self) -> None:
        w = StubWidget(x=0, y=0, z_index=-1)
        assert "z=-1" in repr(w)


# ===========================================================================
# Renderer overlay z-order
# ===========================================================================


class TestRendererZOrder:
    """Renderer.present() draws overlays sorted by z_index."""

    def test_higher_z_index_draws_on_top(self) -> None:
        """Widget with higher z_index overwrites widget with lower z_index
        at the same cell position."""
        renderer = _make_renderer()
        # Register "behind" widget first (z_index=0), "front" second (z_index=10).
        behind = StubWidget(x=0, y=0, marker="B", z_index=0)
        front = StubWidget(x=0, y=0, marker="F", z_index=10)
        renderer.add_overlay(behind)
        renderer.add_overlay(front)

        buf = CellBuffer(10, 5)
        with renderer:
            renderer.present(buf)

        cell = buf.get(0, 0)
        assert cell is not None
        assert cell.char == "F"

    def test_higher_z_index_wins_regardless_of_registration_order(self) -> None:
        """Even when the high-z widget is registered first, it still
        draws on top because z_index takes priority."""
        renderer = _make_renderer()
        # Register high-z first, low-z second.
        front = StubWidget(x=0, y=0, marker="F", z_index=10)
        behind = StubWidget(x=0, y=0, marker="B", z_index=0)
        renderer.add_overlay(front)
        renderer.add_overlay(behind)

        buf = CellBuffer(10, 5)
        with renderer:
            renderer.present(buf)

        cell = buf.get(0, 0)
        assert cell is not None
        assert cell.char == "F"

    def test_equal_z_index_uses_registration_order(self) -> None:
        """Widgets with the same z_index use registration order:
        last-added draws on top (stable sort)."""
        renderer = _make_renderer()
        first = StubWidget(x=0, y=0, marker="A", z_index=0)
        second = StubWidget(x=0, y=0, marker="B", z_index=0)
        renderer.add_overlay(first)
        renderer.add_overlay(second)

        buf = CellBuffer(10, 5)
        with renderer:
            renderer.present(buf)

        cell = buf.get(0, 0)
        assert cell is not None
        assert cell.char == "B"

    def test_negative_z_index_draws_behind(self) -> None:
        """A widget with negative z_index draws before (behind) a
        widget with z_index=0."""
        renderer = _make_renderer()
        background = StubWidget(x=0, y=0, marker="G", z_index=-5)
        foreground = StubWidget(x=0, y=0, marker="U", z_index=0)
        renderer.add_overlay(background)
        renderer.add_overlay(foreground)

        buf = CellBuffer(10, 5)
        with renderer:
            renderer.present(buf)

        cell = buf.get(0, 0)
        assert cell is not None
        assert cell.char == "U"

    def test_three_layers_z_order(self) -> None:
        """Three overlays at different z_index values draw in correct order."""
        renderer = _make_renderer()
        low = StubWidget(x=0, y=0, marker="L", z_index=0)
        mid = StubWidget(x=0, y=0, marker="M", z_index=5)
        high = StubWidget(x=0, y=0, marker="H", z_index=10)
        # Register in scrambled order.
        renderer.add_overlay(high)
        renderer.add_overlay(low)
        renderer.add_overlay(mid)

        buf = CellBuffer(10, 5)
        with renderer:
            renderer.present(buf)

        cell = buf.get(0, 0)
        assert cell is not None
        assert cell.char == "H"
        # All three should have been drawn.
        assert low.draw_count == 1
        assert mid.draw_count == 1
        assert high.draw_count == 1

    def test_dynamic_z_index_change(self) -> None:
        """Changing z_index between frames updates draw order."""
        renderer = _make_renderer()
        a = StubWidget(x=0, y=0, marker="A", z_index=0)
        b = StubWidget(x=0, y=0, marker="B", z_index=10)
        renderer.add_overlay(a)
        renderer.add_overlay(b)

        buf = CellBuffer(10, 5)
        with renderer:
            renderer.present(buf)
            cell = buf.get(0, 0)
            assert cell is not None
            assert cell.char == "B"  # B on top (z=10)

            # Swap z-order: now A on top.
            a.z_index = 20
            buf.clear()
            renderer.present(buf)
            cell = buf.get(0, 0)
            assert cell is not None
            assert cell.char == "A"

    def test_hidden_widget_skipped_regardless_of_z(self) -> None:
        """A hidden widget with high z_index is not drawn."""
        renderer = _make_renderer()
        visible = StubWidget(x=0, y=0, marker="V", z_index=0)
        hidden = StubWidget(x=0, y=0, marker="H", z_index=100)
        hidden.visible = False
        renderer.add_overlay(visible)
        renderer.add_overlay(hidden)

        buf = CellBuffer(10, 5)
        with renderer:
            renderer.present(buf)

        cell = buf.get(0, 0)
        assert cell is not None
        assert cell.char == "V"
        assert hidden.draw_count == 0


# ===========================================================================
# FocusManager z-order hit-testing
# ===========================================================================


class TestFocusManagerZOrder:
    """FocusManager routes clicks to the topmost widget by z_index."""

    def test_click_hits_higher_z_index_widget(self) -> None:
        """Click at overlapping position goes to higher z_index widget."""
        bottom = StubWidget(x=0, y=0, width=20, height=5, marker="B", z_index=0)
        top = StubWidget(x=0, y=0, width=20, height=5, marker="T", z_index=10)
        fm = FocusManager(widgets=[bottom, top])

        event = MouseEvent(x=5, y=2, button="left", action="press")
        consumed = fm.dispatch(event)

        assert consumed is True
        assert fm.focused_widget is top
        assert event in top.events_received
        assert event not in bottom.events_received

    def test_higher_z_wins_regardless_of_registration(self) -> None:
        """Even when the high-z widget is registered first, it still
        gets the click."""
        top = StubWidget(x=0, y=0, width=20, height=5, marker="T", z_index=10)
        bottom = StubWidget(x=0, y=0, width=20, height=5, marker="B", z_index=0)
        # Register high-z first.
        fm = FocusManager(widgets=[top, bottom])

        event = MouseEvent(x=5, y=2, button="left", action="press")
        consumed = fm.dispatch(event)

        assert consumed is True
        assert fm.focused_widget is top

    def test_equal_z_index_uses_registration_order(self) -> None:
        """With same z_index, last-added gets the click (registration tiebreaker)."""
        first = StubWidget(x=0, y=0, width=20, height=5, marker="1", z_index=0)
        second = StubWidget(x=0, y=0, width=20, height=5, marker="2", z_index=0)
        fm = FocusManager(widgets=[first, second])

        event = MouseEvent(x=5, y=2, button="left", action="press")
        consumed = fm.dispatch(event)

        assert consumed is True
        assert fm.focused_widget is second

    def test_widget_at_respects_z_index(self) -> None:
        """widget_at returns the widget with highest z_index at a point."""
        bottom = StubWidget(x=0, y=0, width=20, height=5, marker="B", z_index=0)
        top = StubWidget(x=0, y=0, width=20, height=5, marker="T", z_index=5)
        fm = FocusManager(widgets=[bottom, top])

        assert fm.widget_at(5, 2) is top

    def test_widget_at_respects_z_index_reversed_registration(self) -> None:
        """widget_at returns high-z widget even if it was registered first."""
        top = StubWidget(x=0, y=0, width=20, height=5, marker="T", z_index=5)
        bottom = StubWidget(x=0, y=0, width=20, height=5, marker="B", z_index=0)
        fm = FocusManager(widgets=[top, bottom])

        assert fm.widget_at(5, 2) is top

    def test_click_on_lower_widget_outside_upper_bounds(self) -> None:
        """Click outside the high-z widget's bounds hits the low-z widget."""
        bottom = StubWidget(x=0, y=0, width=20, height=10, marker="B", z_index=0)
        top = StubWidget(x=5, y=5, width=5, height=3, marker="T", z_index=10)
        fm = FocusManager(widgets=[bottom, top])

        # Click at (1, 1) — only inside bottom.
        event = MouseEvent(x=1, y=1, button="left", action="press")
        consumed = fm.dispatch(event)

        assert consumed is True
        assert fm.focused_widget is bottom

    def test_invisible_high_z_skipped(self) -> None:
        """An invisible widget with high z_index is skipped during hit-testing."""
        bottom = StubWidget(x=0, y=0, width=20, height=5, marker="B", z_index=0)
        top = StubWidget(x=0, y=0, width=20, height=5, marker="T", z_index=10)
        top.visible = False
        fm = FocusManager(widgets=[bottom, top])

        event = MouseEvent(x=5, y=2, button="left", action="press")
        consumed = fm.dispatch(event)

        assert consumed is True
        assert fm.focused_widget is bottom

    def test_dynamic_z_index_change_for_hit_testing(self) -> None:
        """Changing z_index between dispatches updates hit-test order."""
        a = StubWidget(x=0, y=0, width=20, height=5, marker="A", z_index=0)
        b = StubWidget(x=0, y=0, width=20, height=5, marker="B", z_index=10)
        fm = FocusManager(widgets=[a, b])

        # B is on top initially.
        event1 = MouseEvent(x=5, y=2, button="left", action="press")
        fm.dispatch(event1)
        assert fm.focused_widget is b

        # Swap: A gets higher z.
        a.z_index = 20
        event2 = MouseEvent(x=5, y=2, button="left", action="press")
        fm.dispatch(event2)
        assert fm.focused_widget is a

    def test_negative_z_index_below_zero(self) -> None:
        """Widget with negative z_index is behind z_index=0 widget."""
        behind = StubWidget(x=0, y=0, width=20, height=5, marker="G", z_index=-5)
        normal = StubWidget(x=0, y=0, width=20, height=5, marker="N", z_index=0)
        fm = FocusManager(widgets=[behind, normal])

        event = MouseEvent(x=5, y=2, button="left", action="press")
        fm.dispatch(event)
        assert fm.focused_widget is normal


# ===========================================================================
# Integration: Renderer + FocusManager z-order consistency
# ===========================================================================


class TestZOrderIntegration:
    """Renderer draw order and FocusManager hit-test order are consistent."""

    def test_renderer_and_focus_agree_on_topmost(self) -> None:
        """The widget drawn on top is the same widget that receives clicks.

        This verifies that the z-order sort in both systems produces
        the same result — the widget the user *sees* on top is the
        widget that *responds* to their click.
        """
        renderer = _make_renderer()
        fm = FocusManager()

        game_hud = StubWidget(x=0, y=0, width=10, height=5, marker="H", z_index=0)
        popup = StubWidget(x=0, y=0, width=10, height=5, marker="P", z_index=10)

        renderer.add_overlay(game_hud)
        renderer.add_overlay(popup)
        fm.add(game_hud)
        fm.add(popup)

        # Draw.
        buf = CellBuffer(10, 5)
        with renderer:
            renderer.present(buf)
        cell = buf.get(0, 0)
        assert cell is not None
        drawn_on_top = cell.char

        # Click.
        event = MouseEvent(x=0, y=0, button="left", action="press")
        fm.dispatch(event)
        clicked_widget = fm.focused_widget

        # Both should agree: popup is on top.
        assert drawn_on_top == "P"
        assert clicked_widget is popup
