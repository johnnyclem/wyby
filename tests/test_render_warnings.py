"""Tests for wyby.render_warnings — render-cost estimation and flicker advisories."""

from __future__ import annotations

import logging

import pytest

from wyby.render_warnings import (
    HEAVY_CELL_LIMIT,
    LIGHT_CELL_LIMIT,
    MODERATE_CELL_LIMIT,
    RenderCost,
    check_emoji_warning,
    check_flicker_risk,
    estimate_render_cost,
    log_emoji_warning,
    log_render_cost,
)


# ---------------------------------------------------------------------------
# RenderCost enum
# ---------------------------------------------------------------------------


class TestRenderCost:
    """Tests for the RenderCost enum ordering and comparison."""

    def test_ordering(self) -> None:
        assert RenderCost.LIGHT < RenderCost.MODERATE
        assert RenderCost.MODERATE < RenderCost.HEAVY
        assert RenderCost.HEAVY < RenderCost.EXTREME

    def test_ge(self) -> None:
        assert RenderCost.HEAVY >= RenderCost.MODERATE
        assert RenderCost.HEAVY >= RenderCost.HEAVY
        assert not (RenderCost.LIGHT >= RenderCost.MODERATE)

    def test_le(self) -> None:
        assert RenderCost.LIGHT <= RenderCost.MODERATE
        assert RenderCost.LIGHT <= RenderCost.LIGHT
        assert not (RenderCost.HEAVY <= RenderCost.MODERATE)

    def test_gt(self) -> None:
        assert RenderCost.EXTREME > RenderCost.HEAVY
        assert not (RenderCost.LIGHT > RenderCost.LIGHT)

    def test_lt(self) -> None:
        assert RenderCost.LIGHT < RenderCost.HEAVY
        assert not (RenderCost.HEAVY < RenderCost.HEAVY)

    def test_comparison_with_non_rendercost_returns_not_implemented(
        self,
    ) -> None:
        assert RenderCost.LIGHT.__ge__(42) is NotImplemented
        assert RenderCost.LIGHT.__gt__(42) is NotImplemented
        assert RenderCost.LIGHT.__le__(42) is NotImplemented
        assert RenderCost.LIGHT.__lt__(42) is NotImplemented

    def test_values(self) -> None:
        assert RenderCost.LIGHT.value == 0
        assert RenderCost.MODERATE.value == 1
        assert RenderCost.HEAVY.value == 2
        assert RenderCost.EXTREME.value == 3


# ---------------------------------------------------------------------------
# Threshold constants
# ---------------------------------------------------------------------------


class TestThresholdConstants:
    """Tests for threshold constant values and ordering."""

    def test_thresholds_are_positive(self) -> None:
        assert LIGHT_CELL_LIMIT > 0
        assert MODERATE_CELL_LIMIT > 0
        assert HEAVY_CELL_LIMIT > 0

    def test_thresholds_are_ordered(self) -> None:
        assert LIGHT_CELL_LIMIT < MODERATE_CELL_LIMIT < HEAVY_CELL_LIMIT


# ---------------------------------------------------------------------------
# estimate_render_cost
# ---------------------------------------------------------------------------


class TestEstimateRenderCost:
    """Tests for estimate_render_cost()."""

    def test_small_grid_is_light(self) -> None:
        """A 40x24 grid (960 cells) should be LIGHT."""
        assert estimate_render_cost(40, 24) == RenderCost.LIGHT

    def test_standard_80x24_is_light(self) -> None:
        """80x24 = 1920 cells, just under the LIGHT limit."""
        assert estimate_render_cost(80, 24) == RenderCost.LIGHT

    def test_moderate_grid(self) -> None:
        """A grid with cells between LIGHT and MODERATE limits."""
        # 50x50 = 2500, which is > LIGHT_CELL_LIMIT and < MODERATE_CELL_LIMIT
        assert estimate_render_cost(50, 50) == RenderCost.MODERATE

    def test_120x40_is_moderate(self) -> None:
        """120x40 = 4800 cells = exactly MODERATE_CELL_LIMIT boundary."""
        # At exactly the limit, it should be HEAVY (>= boundary).
        cost = estimate_render_cost(120, 40)
        assert cost == RenderCost.HEAVY

    def test_heavy_grid(self) -> None:
        """A grid in the HEAVY range."""
        # 150x50 = 7500 cells, in HEAVY range
        assert estimate_render_cost(150, 50) == RenderCost.HEAVY

    def test_200x60_is_extreme(self) -> None:
        """200x60 = 12000 cells = exactly at the HEAVY limit boundary."""
        cost = estimate_render_cost(200, 60)
        assert cost == RenderCost.EXTREME

    def test_very_large_grid_is_extreme(self) -> None:
        """A 500x500 grid should be EXTREME."""
        assert estimate_render_cost(500, 500) == RenderCost.EXTREME

    def test_styled_fraction_zero_always_light(self) -> None:
        """All-default cells should always be LIGHT regardless of size."""
        assert estimate_render_cost(500, 500, styled_fraction=0.0) == RenderCost.LIGHT

    def test_styled_fraction_reduces_cost(self) -> None:
        """Low styled_fraction should reduce cost category."""
        # 200x60 = 12000 cells is EXTREME at 100% styling.
        # At 10% styling, effective = 1200, which is LIGHT.
        assert estimate_render_cost(200, 60, styled_fraction=0.1) == RenderCost.LIGHT

    def test_styled_fraction_partial(self) -> None:
        """50% styling on a large grid should reduce cost."""
        # 200x60 = 12000 cells, 50% = 6000 effective -> HEAVY
        assert estimate_render_cost(200, 60, styled_fraction=0.5) == RenderCost.HEAVY

    def test_minimum_dimensions(self) -> None:
        """1x1 grid should be LIGHT."""
        assert estimate_render_cost(1, 1) == RenderCost.LIGHT

    def test_rejects_zero_width(self) -> None:
        with pytest.raises(ValueError, match="width must be >= 1"):
            estimate_render_cost(0, 10)

    def test_rejects_zero_height(self) -> None:
        with pytest.raises(ValueError, match="height must be >= 1"):
            estimate_render_cost(10, 0)

    def test_rejects_negative_width(self) -> None:
        with pytest.raises(ValueError, match="width must be >= 1"):
            estimate_render_cost(-5, 10)

    def test_rejects_negative_height(self) -> None:
        with pytest.raises(ValueError, match="height must be >= 1"):
            estimate_render_cost(10, -5)

    def test_rejects_styled_fraction_below_zero(self) -> None:
        with pytest.raises(ValueError, match="styled_fraction"):
            estimate_render_cost(80, 24, styled_fraction=-0.1)

    def test_rejects_styled_fraction_above_one(self) -> None:
        with pytest.raises(ValueError, match="styled_fraction"):
            estimate_render_cost(80, 24, styled_fraction=1.1)

    def test_styled_fraction_one_is_accepted(self) -> None:
        """styled_fraction=1.0 (boundary) should be accepted."""
        estimate_render_cost(80, 24, styled_fraction=1.0)

    def test_styled_fraction_zero_is_accepted(self) -> None:
        """styled_fraction=0.0 (boundary) should be accepted."""
        estimate_render_cost(80, 24, styled_fraction=0.0)


# ---------------------------------------------------------------------------
# check_flicker_risk
# ---------------------------------------------------------------------------


class TestCheckFlickerRisk:
    """Tests for check_flicker_risk()."""

    def test_returns_none_for_light(self) -> None:
        assert check_flicker_risk(40, 24) is None

    def test_returns_none_for_moderate(self) -> None:
        assert check_flicker_risk(50, 50) is None

    def test_returns_warning_for_heavy(self) -> None:
        warning = check_flicker_risk(150, 50)
        assert warning is not None
        assert "HEAVY" in warning
        assert "FPSCounter" in warning

    def test_returns_warning_for_extreme(self) -> None:
        warning = check_flicker_risk(500, 500)
        assert warning is not None
        assert "EXTREME" in warning

    def test_heavy_warning_mentions_grid_size(self) -> None:
        warning = check_flicker_risk(150, 50)
        assert warning is not None
        assert "150x50" in warning

    def test_extreme_warning_mentions_cell_count(self) -> None:
        warning = check_flicker_risk(500, 500)
        assert warning is not None
        assert "250,000" in warning

    def test_styled_fraction_can_reduce_to_none(self) -> None:
        """Low styling on a heavy grid should return no warning."""
        assert check_flicker_risk(200, 60, styled_fraction=0.1) is None


# ---------------------------------------------------------------------------
# log_render_cost
# ---------------------------------------------------------------------------


class TestLogRenderCost:
    """Tests for log_render_cost()."""

    def test_returns_cost_category(self) -> None:
        cost = log_render_cost(80, 24)
        assert cost == RenderCost.LIGHT

    def test_logs_debug_for_light(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.DEBUG, logger="wyby.render_warnings"):
            log_render_cost(40, 24)
        assert any("LIGHT" in r.message for r in caplog.records)

    def test_logs_debug_for_moderate(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.DEBUG, logger="wyby.render_warnings"):
            log_render_cost(50, 50)
        assert any("MODERATE" in r.message for r in caplog.records)

    def test_logs_warning_for_heavy(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.WARNING, logger="wyby.render_warnings"):
            log_render_cost(150, 50)
        assert any(r.levelno == logging.WARNING for r in caplog.records)
        assert any("HEAVY" in r.message for r in caplog.records)

    def test_logs_warning_for_extreme(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.WARNING, logger="wyby.render_warnings"):
            log_render_cost(500, 500)
        assert any(r.levelno == logging.WARNING for r in caplog.records)
        assert any("EXTREME" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# Renderer integration
# ---------------------------------------------------------------------------


class TestRendererFlickerWarningIntegration:
    """Tests that Renderer.start() logs render-cost warnings."""

    def test_renderer_start_logs_cost(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Renderer.start() should log render cost at startup."""
        import io

        from rich.console import Console

        from wyby.renderer import Renderer

        console = Console(
            file=io.StringIO(), force_terminal=True, width=80, height=24
        )
        renderer = Renderer(console=console)
        with caplog.at_level(logging.DEBUG, logger="wyby.render_warnings"):
            renderer.start()
            try:
                # Should have logged a render-cost message.
                cost_messages = [
                    r for r in caplog.records
                    if "wyby.render_warnings" in r.name
                ]
                assert len(cost_messages) >= 1
            finally:
                renderer.stop()

    def test_renderer_start_warns_for_large_console(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Renderer with a large console should log a WARNING."""
        import io

        from rich.console import Console

        from wyby.renderer import Renderer

        # 200x200 = 40,000 cells -> EXTREME
        console = Console(
            file=io.StringIO(), force_terminal=True, width=200, height=200
        )
        renderer = Renderer(console=console)
        with caplog.at_level(logging.WARNING, logger="wyby.render_warnings"):
            renderer.start()
            try:
                warnings = [
                    r for r in caplog.records
                    if r.levelno == logging.WARNING
                    and "wyby.render_warnings" in r.name
                ]
                assert len(warnings) >= 1
                assert "EXTREME" in warnings[0].message
            finally:
                renderer.stop()


# ---------------------------------------------------------------------------
# Package exports
# ---------------------------------------------------------------------------


class TestPackageExports:
    """Tests for render_warnings availability in the public API."""

    def test_render_cost_importable(self) -> None:
        from wyby import RenderCost as RC  # noqa: N811
        assert RC is RenderCost

    def test_estimate_render_cost_importable(self) -> None:
        from wyby import estimate_render_cost as erc
        assert erc is estimate_render_cost

    def test_check_flicker_risk_importable(self) -> None:
        from wyby import check_flicker_risk as cfr
        assert cfr is check_flicker_risk

    def test_log_render_cost_importable(self) -> None:
        from wyby import log_render_cost as lrc
        assert lrc is log_render_cost

    def test_render_cost_in_all(self) -> None:
        import wyby
        assert "RenderCost" in wyby.__all__

    def test_estimate_render_cost_in_all(self) -> None:
        import wyby
        assert "estimate_render_cost" in wyby.__all__

    def test_check_flicker_risk_in_all(self) -> None:
        import wyby
        assert "check_flicker_risk" in wyby.__all__

    def test_log_render_cost_in_all(self) -> None:
        import wyby
        assert "log_render_cost" in wyby.__all__

    def test_check_emoji_warning_importable(self) -> None:
        from wyby import check_emoji_warning as cew
        assert cew is check_emoji_warning

    def test_log_emoji_warning_importable(self) -> None:
        from wyby import log_emoji_warning as lew
        assert lew is log_emoji_warning

    def test_check_emoji_warning_in_all(self) -> None:
        import wyby
        assert "check_emoji_warning" in wyby.__all__

    def test_log_emoji_warning_in_all(self) -> None:
        import wyby
        assert "log_emoji_warning" in wyby.__all__

    def test_contains_emoji_in_all(self) -> None:
        import wyby
        assert "contains_emoji" in wyby.__all__


# ---------------------------------------------------------------------------
# check_emoji_warning
# ---------------------------------------------------------------------------


class TestCheckEmojiWarning:
    """Tests for check_emoji_warning()."""

    def test_returns_none_for_plain_ascii(self) -> None:
        assert check_emoji_warning("Hello, world!") is None

    def test_returns_none_for_empty_string(self) -> None:
        assert check_emoji_warning("") is None

    def test_returns_none_for_box_drawing(self) -> None:
        assert check_emoji_warning("┌──┐│└┘") is None

    def test_returns_none_for_cjk(self) -> None:
        assert check_emoji_warning("中文") is None

    def test_returns_warning_for_emoji(self) -> None:
        warning = check_emoji_warning("Hello 🌍")
        assert warning is not None

    def test_warning_mentions_width_disagreement(self) -> None:
        warning = check_emoji_warning("🌍")
        assert warning is not None
        assert "width" in warning.lower()

    def test_warning_mentions_multi_codepoint(self) -> None:
        warning = check_emoji_warning("🌍")
        assert warning is not None
        assert "multi-codepoint" in warning.lower()

    def test_warning_mentions_alternatives(self) -> None:
        """Warning should suggest safer alternatives."""
        warning = check_emoji_warning("🌍")
        assert warning is not None
        assert "box-drawing" in warning.lower()

    def test_warning_for_face_emoji(self) -> None:
        assert check_emoji_warning("😀") is not None

    def test_warning_for_flag_emoji(self) -> None:
        assert check_emoji_warning("\U0001F1FA\U0001F1F8") is not None

    def test_warning_for_vs16(self) -> None:
        assert check_emoji_warning("#\uFE0F") is not None


# ---------------------------------------------------------------------------
# log_emoji_warning
# ---------------------------------------------------------------------------


class TestLogEmojiWarning:
    """Tests for log_emoji_warning()."""

    def test_returns_false_for_clean_text(self) -> None:
        assert log_emoji_warning("Hello") is False

    def test_returns_true_for_emoji(self) -> None:
        assert log_emoji_warning("Hello 🌍") is True

    def test_logs_warning_for_emoji(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.WARNING, logger="wyby.render_warnings"):
            log_emoji_warning("Hello 🌍")
        assert any(r.levelno == logging.WARNING for r in caplog.records)
        assert any("emoji" in r.message.lower() for r in caplog.records)

    def test_logs_debug_for_clean_text(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.DEBUG, logger="wyby.render_warnings"):
            log_emoji_warning("Hello")
        debug_records = [
            r for r in caplog.records if r.levelno == logging.DEBUG
        ]
        assert len(debug_records) >= 1
        assert any("no emoji" in r.message.lower() for r in debug_records)
