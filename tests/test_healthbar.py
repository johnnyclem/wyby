"""Tests for wyby.healthbar — HealthBar widget for terminal UI overlays."""

from __future__ import annotations

import pytest

from wyby.grid import CellBuffer
from wyby.healthbar import (
    EMPTY_CHAR,
    FILLED_CHAR,
    HealthBar,
)


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestHealthBarConstruction:
    """HealthBar creation and default state."""

    def test_default_values(self) -> None:
        bar = HealthBar()
        assert bar.current == 100
        assert bar.maximum == 100
        assert bar.bar_width == 20
        assert bar.show_label is True
        assert bar.label_prefix == "HP"

    def test_custom_values(self) -> None:
        bar = HealthBar(current=50, maximum=200, bar_width=30)
        assert bar.current == 50
        assert bar.maximum == 200
        assert bar.bar_width == 30

    def test_custom_position(self) -> None:
        bar = HealthBar(x=5, y=10)
        assert bar.x == 5
        assert bar.y == 10

    def test_height_is_one(self) -> None:
        bar = HealthBar()
        assert bar.height == 1

    def test_default_visible(self) -> None:
        bar = HealthBar()
        assert bar.visible is True

    def test_default_not_focused(self) -> None:
        bar = HealthBar()
        assert bar.focused is False

    def test_current_clamped_to_maximum(self) -> None:
        bar = HealthBar(current=150, maximum=100)
        assert bar.current == 100

    def test_current_clamped_to_zero(self) -> None:
        bar = HealthBar(current=-10, maximum=100)
        assert bar.current == 0

    def test_bar_width_clamped_to_minimum(self) -> None:
        bar = HealthBar(bar_width=0)
        assert bar.bar_width == 1

    def test_bar_width_clamped_to_maximum(self) -> None:
        bar = HealthBar(bar_width=5000)
        assert bar.bar_width == 1000

    def test_custom_label_prefix(self) -> None:
        bar = HealthBar(label_prefix="MP")
        assert bar.label_prefix == "MP"

    def test_show_label_false(self) -> None:
        bar = HealthBar(show_label=False)
        assert bar.show_label is False


# ---------------------------------------------------------------------------
# Type validation
# ---------------------------------------------------------------------------


class TestHealthBarTypeValidation:
    """Type checking on constructor arguments."""

    def test_current_rejects_float(self) -> None:
        with pytest.raises(TypeError, match="current must be an int"):
            HealthBar(current=50.5)  # type: ignore[arg-type]

    def test_current_rejects_bool(self) -> None:
        with pytest.raises(TypeError, match="current must be an int"):
            HealthBar(current=True)  # type: ignore[arg-type]

    def test_maximum_rejects_float(self) -> None:
        with pytest.raises(TypeError, match="maximum must be an int"):
            HealthBar(maximum=100.0)  # type: ignore[arg-type]

    def test_maximum_rejects_bool(self) -> None:
        with pytest.raises(TypeError, match="maximum must be an int"):
            HealthBar(maximum=False)  # type: ignore[arg-type]

    def test_bar_width_rejects_float(self) -> None:
        with pytest.raises(TypeError, match="bar_width must be an int"):
            HealthBar(bar_width=10.0)  # type: ignore[arg-type]

    def test_bar_width_rejects_bool(self) -> None:
        with pytest.raises(TypeError, match="bar_width must be an int"):
            HealthBar(bar_width=True)  # type: ignore[arg-type]

    def test_label_prefix_rejects_int(self) -> None:
        with pytest.raises(TypeError, match="label_prefix must be a str"):
            HealthBar(label_prefix=42)  # type: ignore[arg-type]

    def test_maximum_rejects_zero(self) -> None:
        with pytest.raises(ValueError, match="maximum must be >= 1"):
            HealthBar(maximum=0)

    def test_maximum_rejects_negative(self) -> None:
        with pytest.raises(ValueError, match="maximum must be >= 1"):
            HealthBar(maximum=-5)

    def test_x_rejects_float(self) -> None:
        with pytest.raises(TypeError, match="x must be an int"):
            HealthBar(x=1.5)  # type: ignore[arg-type]

    def test_y_rejects_float(self) -> None:
        with pytest.raises(TypeError, match="y must be an int"):
            HealthBar(y=1.5)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Property setters
# ---------------------------------------------------------------------------


class TestHealthBarProperties:
    """Property getter/setter behavior."""

    def test_set_current(self) -> None:
        bar = HealthBar()
        bar.current = 50
        assert bar.current == 50

    def test_set_current_clamps_to_max(self) -> None:
        bar = HealthBar(maximum=100)
        bar.current = 150
        assert bar.current == 100

    def test_set_current_clamps_to_zero(self) -> None:
        bar = HealthBar()
        bar.current = -10
        assert bar.current == 0

    def test_set_current_rejects_float(self) -> None:
        bar = HealthBar()
        with pytest.raises(TypeError, match="current must be an int"):
            bar.current = 50.0  # type: ignore[assignment]

    def test_set_current_rejects_bool(self) -> None:
        bar = HealthBar()
        with pytest.raises(TypeError, match="current must be an int"):
            bar.current = True  # type: ignore[assignment]

    def test_set_maximum(self) -> None:
        bar = HealthBar()
        bar.maximum = 200
        assert bar.maximum == 200

    def test_set_maximum_reclamps_current(self) -> None:
        bar = HealthBar(current=100, maximum=100)
        bar.maximum = 50
        assert bar.current == 50

    def test_set_maximum_rejects_zero(self) -> None:
        bar = HealthBar()
        with pytest.raises(ValueError, match="maximum must be >= 1"):
            bar.maximum = 0

    def test_set_maximum_rejects_float(self) -> None:
        bar = HealthBar()
        with pytest.raises(TypeError, match="maximum must be an int"):
            bar.maximum = 100.0  # type: ignore[assignment]

    def test_set_bar_width(self) -> None:
        bar = HealthBar()
        bar.bar_width = 30
        assert bar.bar_width == 30

    def test_set_bar_width_clamps_min(self) -> None:
        bar = HealthBar()
        bar.bar_width = 0
        assert bar.bar_width == 1

    def test_set_bar_width_clamps_max(self) -> None:
        bar = HealthBar()
        bar.bar_width = 5000
        assert bar.bar_width == 1000

    def test_set_bar_width_rejects_float(self) -> None:
        bar = HealthBar()
        with pytest.raises(TypeError, match="bar_width must be an int"):
            bar.bar_width = 10.0  # type: ignore[assignment]

    def test_set_show_label(self) -> None:
        bar = HealthBar(show_label=True)
        bar.show_label = False
        assert bar.show_label is False

    def test_set_label_prefix(self) -> None:
        bar = HealthBar()
        bar.label_prefix = "MP"
        assert bar.label_prefix == "MP"

    def test_set_label_prefix_rejects_int(self) -> None:
        bar = HealthBar()
        with pytest.raises(TypeError, match="label_prefix must be a str"):
            bar.label_prefix = 42  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Percentage
# ---------------------------------------------------------------------------


class TestHealthBarPercentage:
    """Fill percentage calculation."""

    def test_full_health(self) -> None:
        bar = HealthBar(current=100, maximum=100)
        assert bar.percentage == 1.0

    def test_zero_health(self) -> None:
        bar = HealthBar(current=0, maximum=100)
        assert bar.percentage == 0.0

    def test_half_health(self) -> None:
        bar = HealthBar(current=50, maximum=100)
        assert bar.percentage == 0.5

    def test_quarter_health(self) -> None:
        bar = HealthBar(current=25, maximum=100)
        assert bar.percentage == 0.25

    def test_fractional_percentage(self) -> None:
        bar = HealthBar(current=1, maximum=3)
        assert abs(bar.percentage - 1 / 3) < 1e-9


# ---------------------------------------------------------------------------
# Colour selection
# ---------------------------------------------------------------------------


class TestHealthBarColor:
    """Bar colour based on fill percentage."""

    def test_full_health_is_green(self) -> None:
        bar = HealthBar(current=100, maximum=100)
        assert bar._bar_color() == "green"

    def test_above_half_is_green(self) -> None:
        bar = HealthBar(current=51, maximum=100)
        assert bar._bar_color() == "green"

    def test_exactly_half_is_yellow(self) -> None:
        bar = HealthBar(current=50, maximum=100)
        assert bar._bar_color() == "yellow"

    def test_between_quarter_and_half_is_yellow(self) -> None:
        bar = HealthBar(current=30, maximum=100)
        assert bar._bar_color() == "yellow"

    def test_exactly_quarter_is_yellow(self) -> None:
        bar = HealthBar(current=25, maximum=100)
        assert bar._bar_color() == "yellow"

    def test_below_quarter_is_red(self) -> None:
        bar = HealthBar(current=24, maximum=100)
        assert bar._bar_color() == "red"

    def test_zero_health_is_red(self) -> None:
        bar = HealthBar(current=0, maximum=100)
        assert bar._bar_color() == "red"


# ---------------------------------------------------------------------------
# Drawing
# ---------------------------------------------------------------------------


class TestHealthBarDraw:
    """HealthBar rendering into CellBuffer."""

    def test_draws_filled_and_empty(self) -> None:
        bar = HealthBar(current=50, maximum=100, x=0, y=0, bar_width=10, show_label=False)
        buf = CellBuffer(20, 3)
        bar.draw(buf)
        # 50% of 10 = 5 filled, 5 empty
        for col in range(5):
            cell = buf.get(col, 0)
            assert cell is not None
            assert cell.char == FILLED_CHAR
        for col in range(5, 10):
            cell = buf.get(col, 0)
            assert cell is not None
            assert cell.char == EMPTY_CHAR

    def test_draws_full_bar(self) -> None:
        bar = HealthBar(current=100, maximum=100, x=0, y=0, bar_width=10, show_label=False)
        buf = CellBuffer(20, 3)
        bar.draw(buf)
        for col in range(10):
            cell = buf.get(col, 0)
            assert cell is not None
            assert cell.char == FILLED_CHAR

    def test_draws_empty_bar(self) -> None:
        bar = HealthBar(current=0, maximum=100, x=0, y=0, bar_width=10, show_label=False)
        buf = CellBuffer(20, 3)
        bar.draw(buf)
        for col in range(10):
            cell = buf.get(col, 0)
            assert cell is not None
            assert cell.char == EMPTY_CHAR

    def test_draws_at_position(self) -> None:
        bar = HealthBar(current=100, maximum=100, x=5, y=2, bar_width=5, show_label=False)
        buf = CellBuffer(20, 5)
        bar.draw(buf)
        cell = buf.get(5, 2)
        assert cell is not None
        assert cell.char == FILLED_CHAR
        # Position before bar should be blank.
        cell_before = buf.get(4, 2)
        assert cell_before is not None
        assert cell_before.char == " "

    def test_skips_draw_when_invisible(self) -> None:
        bar = HealthBar(current=100, maximum=100, x=0, y=0, bar_width=10, show_label=False)
        bar.visible = False
        buf = CellBuffer(20, 3)
        bar.draw(buf)
        cell = buf.get(0, 0)
        assert cell is not None
        assert cell.char == " "

    def test_draws_label_when_enabled(self) -> None:
        bar = HealthBar(current=75, maximum=100, x=0, y=0, bar_width=10, show_label=True)
        buf = CellBuffer(40, 3)
        bar.draw(buf)
        # Label should start with "HP: 75/100"
        cell_h = buf.get(0, 0)
        cell_p = buf.get(1, 0)
        assert cell_h is not None and cell_h.char == "H"
        assert cell_p is not None and cell_p.char == "P"

    def test_no_label_when_disabled(self) -> None:
        bar = HealthBar(current=100, maximum=100, x=0, y=0, bar_width=10, show_label=False)
        buf = CellBuffer(20, 3)
        bar.draw(buf)
        # First cell should be the bar, not a label character.
        cell = buf.get(0, 0)
        assert cell is not None
        assert cell.char == FILLED_CHAR

    def test_filled_color_is_green_at_full(self) -> None:
        bar = HealthBar(current=100, maximum=100, x=0, y=0, bar_width=10, show_label=False)
        buf = CellBuffer(20, 3)
        bar.draw(buf)
        cell = buf.get(0, 0)
        assert cell is not None
        assert cell.fg == "green"

    def test_filled_color_is_red_at_low(self) -> None:
        bar = HealthBar(current=10, maximum=100, x=0, y=0, bar_width=10, show_label=False)
        buf = CellBuffer(20, 3)
        bar.draw(buf)
        cell = buf.get(0, 0)
        assert cell is not None
        assert cell.fg == "red"

    def test_empty_portion_is_dim(self) -> None:
        bar = HealthBar(current=50, maximum=100, x=0, y=0, bar_width=10, show_label=False)
        buf = CellBuffer(20, 3)
        bar.draw(buf)
        # Empty portion starts at column 5.
        cell = buf.get(5, 0)
        assert cell is not None
        assert cell.dim is True

    def test_clips_silently_at_buffer_edge(self) -> None:
        """Drawing beyond buffer bounds does not raise."""
        buf = CellBuffer(3, 1)
        bar = HealthBar(current=100, maximum=100, x=0, y=0, bar_width=20, show_label=False)
        bar.draw(buf)  # Should not raise

    def test_focused_draws_bold(self) -> None:
        bar = HealthBar(current=100, maximum=100, x=0, y=0, bar_width=10, show_label=False)
        bar.focused = True
        buf = CellBuffer(20, 3)
        bar.draw(buf)
        cell = buf.get(0, 0)
        assert cell is not None
        assert cell.bold is True


# ---------------------------------------------------------------------------
# Widget width
# ---------------------------------------------------------------------------


class TestHealthBarWidth:
    """Widget width computation."""

    def test_width_without_label(self) -> None:
        bar = HealthBar(bar_width=20, show_label=False)
        assert bar.width == 20

    def test_width_with_label(self) -> None:
        # Label: "HP: 100/100" = 11 chars, gap = 1, bar = 20 -> 32
        bar = HealthBar(current=100, maximum=100, bar_width=20, show_label=True)
        assert bar.width == 11 + 1 + 20

    def test_width_updates_on_current_change(self) -> None:
        bar = HealthBar(current=100, maximum=100, bar_width=20, show_label=True)
        old_width = bar.width
        bar.current = 9  # "HP: 9/100" = 9 chars -> different width
        assert bar.width != old_width

    def test_width_updates_on_bar_width_change(self) -> None:
        bar = HealthBar(bar_width=20, show_label=False)
        bar.bar_width = 30
        assert bar.width == 30

    def test_width_updates_on_show_label_toggle(self) -> None:
        bar = HealthBar(bar_width=20, show_label=True)
        width_with_label = bar.width
        bar.show_label = False
        assert bar.width < width_with_label

    def test_width_updates_on_label_prefix_change(self) -> None:
        bar = HealthBar(bar_width=20, show_label=True, label_prefix="HP")
        width_hp = bar.width
        bar.label_prefix = "MANA"
        assert bar.width > width_hp


# ---------------------------------------------------------------------------
# Repr
# ---------------------------------------------------------------------------


class TestHealthBarRepr:
    """String representation."""

    def test_repr_basic(self) -> None:
        bar = HealthBar(current=75, maximum=100, x=1, y=2, bar_width=20)
        assert repr(bar) == "HealthBar(75/100, x=1, y=2, bar_width=20)"

    def test_repr_invisible(self) -> None:
        bar = HealthBar()
        bar.visible = False
        assert "visible=False" in repr(bar)

    def test_repr_focused(self) -> None:
        bar = HealthBar()
        bar.focused = True
        assert "focused" in repr(bar)


# ---------------------------------------------------------------------------
# Widget hierarchy
# ---------------------------------------------------------------------------


class TestHealthBarHierarchy:
    """HealthBar participates in widget parent/child hierarchy."""

    def test_healthbar_is_a_widget(self) -> None:
        from wyby.widget import Widget
        bar = HealthBar()
        assert isinstance(bar, Widget)

    def test_healthbar_can_be_child(self) -> None:
        from wyby.widget import Widget

        class Panel(Widget):
            def draw(self, buffer: CellBuffer) -> None:
                pass

        panel = Panel(x=0, y=0, width=40, height=10)
        bar = HealthBar(x=5, y=3)
        panel.add_child(bar)
        assert bar.parent is panel
        assert bar in panel.children


# ---------------------------------------------------------------------------
# Import from package root
# ---------------------------------------------------------------------------


class TestHealthBarImport:
    """HealthBar is accessible from the wyby package root."""

    def test_import_from_wyby(self) -> None:
        from wyby import HealthBar as HB
        assert HB is HealthBar
