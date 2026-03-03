"""Tests for wyby.diagnostics.RenderTimer and Renderer integration."""

from __future__ import annotations

import io

import pytest
from rich.console import Console
from rich.text import Text

from wyby.diagnostics import (
    RenderTimer,
    _DEFAULT_WINDOW_SIZE,
    _MAX_WINDOW_SIZE,
    _MIN_WINDOW_SIZE,
)
from wyby.renderer import Renderer


# ---------------------------------------------------------------------------
# RenderTimer — construction defaults
# ---------------------------------------------------------------------------


class TestRenderTimerDefaults:
    """RenderTimer() with no arguments should use sensible defaults."""

    def test_default_window_size(self) -> None:
        timer = RenderTimer()
        assert timer.window_size == _DEFAULT_WINDOW_SIZE

    def test_initial_last_render_ms_is_zero(self) -> None:
        timer = RenderTimer()
        assert timer.last_render_ms == 0.0

    def test_initial_avg_render_ms_is_zero(self) -> None:
        timer = RenderTimer()
        assert timer.avg_render_ms == 0.0

    def test_initial_min_render_ms_is_zero(self) -> None:
        timer = RenderTimer()
        assert timer.min_render_ms == 0.0

    def test_initial_max_render_ms_is_zero(self) -> None:
        timer = RenderTimer()
        assert timer.max_render_ms == 0.0

    def test_initial_sample_count_is_zero(self) -> None:
        timer = RenderTimer()
        assert timer.sample_count == 0

    def test_initial_total_renders_is_zero(self) -> None:
        timer = RenderTimer()
        assert timer.total_renders == 0


# ---------------------------------------------------------------------------
# RenderTimer — custom construction
# ---------------------------------------------------------------------------


class TestRenderTimerCustomInit:
    """RenderTimer() with explicit window_size."""

    def test_custom_window_size(self) -> None:
        timer = RenderTimer(window_size=10)
        assert timer.window_size == 10

    def test_window_size_min(self) -> None:
        timer = RenderTimer(window_size=_MIN_WINDOW_SIZE)
        assert timer.window_size == _MIN_WINDOW_SIZE

    def test_window_size_max(self) -> None:
        timer = RenderTimer(window_size=_MAX_WINDOW_SIZE)
        assert timer.window_size == _MAX_WINDOW_SIZE


# ---------------------------------------------------------------------------
# RenderTimer — validation
# ---------------------------------------------------------------------------


class TestRenderTimerValidation:
    """Invalid arguments should raise clear errors."""

    def test_window_size_not_int_raises_type_error(self) -> None:
        with pytest.raises(TypeError, match="window_size must be an int"):
            RenderTimer(window_size=10.0)  # type: ignore[arg-type]

    def test_window_size_bool_raises_type_error(self) -> None:
        with pytest.raises(TypeError, match="window_size must be an int"):
            RenderTimer(window_size=True)  # type: ignore[arg-type]

    def test_window_size_string_raises_type_error(self) -> None:
        with pytest.raises(TypeError, match="window_size must be an int"):
            RenderTimer(window_size="60")  # type: ignore[arg-type]

    def test_window_size_zero_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="window_size must be between"):
            RenderTimer(window_size=0)

    def test_window_size_negative_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="window_size must be between"):
            RenderTimer(window_size=-1)

    def test_window_size_too_large_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="window_size must be between"):
            RenderTimer(window_size=_MAX_WINDOW_SIZE + 1)


# ---------------------------------------------------------------------------
# RenderTimer — record and statistics
# ---------------------------------------------------------------------------


class TestRenderTimerRecord:
    """record() should store durations and compute statistics."""

    def test_single_record(self) -> None:
        timer = RenderTimer(window_size=10)
        timer.record(0.010)  # 10ms
        assert timer.sample_count == 1
        assert timer.total_renders == 1
        assert abs(timer.last_render_ms - 10.0) < 0.01

    def test_avg_from_multiple_records(self) -> None:
        timer = RenderTimer(window_size=10)
        timer.record(0.010)  # 10ms
        timer.record(0.030)  # 30ms
        # Average of 10ms and 30ms = 20ms
        assert abs(timer.avg_render_ms - 20.0) < 0.01

    def test_min_render_ms(self) -> None:
        timer = RenderTimer(window_size=10)
        timer.record(0.030)  # 30ms
        timer.record(0.010)  # 10ms (shortest)
        timer.record(0.020)  # 20ms
        assert abs(timer.min_render_ms - 10.0) < 0.01

    def test_max_render_ms(self) -> None:
        timer = RenderTimer(window_size=10)
        timer.record(0.010)  # 10ms
        timer.record(0.050)  # 50ms (longest)
        timer.record(0.020)  # 20ms
        assert abs(timer.max_render_ms - 50.0) < 0.01

    def test_last_render_ms_is_most_recent(self) -> None:
        timer = RenderTimer(window_size=10)
        timer.record(0.010)
        timer.record(0.050)
        timer.record(0.025)
        assert abs(timer.last_render_ms - 25.0) < 0.01

    def test_total_renders_tracks_all_calls(self) -> None:
        timer = RenderTimer(window_size=10)
        for i in range(5):
            timer.record(0.01 * (i + 1))
        assert timer.total_renders == 5


# ---------------------------------------------------------------------------
# RenderTimer — rolling window behavior
# ---------------------------------------------------------------------------


class TestRenderTimerRollingWindow:
    """The deque should evict old samples when the window is full."""

    def test_samples_capped_at_window_size(self) -> None:
        timer = RenderTimer(window_size=3)
        for i in range(6):
            timer.record(0.01 * (i + 1))
        assert timer.sample_count == 3

    def test_old_samples_evicted(self) -> None:
        """After filling, stats should reflect only recent samples."""
        timer = RenderTimer(window_size=3)
        # 3 slow renders at 50ms
        timer.record(0.050)
        timer.record(0.050)
        timer.record(0.050)
        assert abs(timer.avg_render_ms - 50.0) < 0.01

        # 3 fast renders at 5ms
        timer.record(0.005)
        timer.record(0.005)
        timer.record(0.005)
        # Window should now contain only the 5ms samples
        assert abs(timer.avg_render_ms - 5.0) < 0.01

    def test_total_renders_counts_all_including_evicted(self) -> None:
        timer = RenderTimer(window_size=3)
        for _ in range(10):
            timer.record(0.010)
        assert timer.sample_count == 3
        assert timer.total_renders == 10


# ---------------------------------------------------------------------------
# RenderTimer — reset
# ---------------------------------------------------------------------------


class TestRenderTimerReset:
    """reset() should clear all state."""

    def test_reset_clears_last_render_ms(self) -> None:
        timer = RenderTimer(window_size=10)
        timer.record(0.033)
        timer.reset()
        assert timer.last_render_ms == 0.0

    def test_reset_clears_avg_render_ms(self) -> None:
        timer = RenderTimer(window_size=10)
        timer.record(0.033)
        timer.reset()
        assert timer.avg_render_ms == 0.0

    def test_reset_clears_sample_count(self) -> None:
        timer = RenderTimer(window_size=10)
        timer.record(0.033)
        timer.reset()
        assert timer.sample_count == 0

    def test_reset_clears_total_renders(self) -> None:
        timer = RenderTimer(window_size=10)
        timer.record(0.033)
        timer.reset()
        assert timer.total_renders == 0

    def test_records_after_reset_work(self) -> None:
        """After reset, timer should behave as freshly constructed."""
        timer = RenderTimer(window_size=10)
        timer.record(0.033)
        timer.reset()
        timer.record(0.050)  # 50ms
        assert timer.sample_count == 1
        assert abs(timer.last_render_ms - 50.0) < 0.01


# ---------------------------------------------------------------------------
# RenderTimer — edge cases
# ---------------------------------------------------------------------------


class TestRenderTimerEdgeCases:
    """Edge cases and degenerate inputs."""

    def test_zero_duration_does_not_crash(self) -> None:
        timer = RenderTimer()
        timer.record(0.0)
        assert timer.last_render_ms == 0.0
        assert timer.avg_render_ms == 0.0

    def test_window_size_one(self) -> None:
        """Smallest possible window — purely instantaneous measurement."""
        timer = RenderTimer(window_size=1)
        timer.record(0.010)
        assert abs(timer.last_render_ms - 10.0) < 0.01
        timer.record(0.050)
        # Only the latest sample is retained
        assert abs(timer.last_render_ms - 50.0) < 0.01
        assert timer.sample_count == 1

    def test_repr(self) -> None:
        timer = RenderTimer(window_size=10)
        r = repr(timer)
        assert "RenderTimer" in r
        assert "window_size=10" in r
        assert "avg_ms=" in r


# ---------------------------------------------------------------------------
# Renderer integration — render_timer property
# ---------------------------------------------------------------------------


class TestRendererRenderTimer:
    """Renderer should expose a RenderTimer that tracks present() calls."""

    @staticmethod
    def _make_renderer() -> Renderer:
        console = Console(file=io.StringIO(), force_terminal=True)
        return Renderer(console=console)

    def test_renderer_has_render_timer(self) -> None:
        renderer = self._make_renderer()
        assert isinstance(renderer.render_timer, RenderTimer)

    def test_render_timer_empty_before_present(self) -> None:
        renderer = self._make_renderer()
        assert renderer.render_timer.total_renders == 0
        assert renderer.render_timer.last_render_ms == 0.0

    def test_present_records_timing(self) -> None:
        renderer = self._make_renderer()
        with renderer:
            renderer.present(Text("hello"))
            assert renderer.render_timer.total_renders == 1
            assert renderer.render_timer.last_render_ms > 0.0

    def test_multiple_presents_accumulate(self) -> None:
        renderer = self._make_renderer()
        with renderer:
            for i in range(5):
                renderer.present(Text(f"Frame {i}"))
            assert renderer.render_timer.total_renders == 5
            assert renderer.render_timer.sample_count == 5

    def test_present_when_stopped_does_not_record(self) -> None:
        renderer = self._make_renderer()
        renderer.present(Text("hello"))  # Not started — no-op
        assert renderer.render_timer.total_renders == 0

    def test_start_resets_render_timer(self) -> None:
        """Starting a fresh cycle resets the render timer."""
        renderer = self._make_renderer()
        renderer.start()
        renderer.present(Text("frame 1"))
        assert renderer.render_timer.total_renders == 1
        renderer.stop()
        renderer.start()
        try:
            assert renderer.render_timer.total_renders == 0
            assert renderer.render_timer.last_render_ms == 0.0
        finally:
            renderer.stop()

    def test_render_timer_avg_is_positive(self) -> None:
        renderer = self._make_renderer()
        with renderer:
            for _ in range(10):
                renderer.present(Text("x" * 80))
            assert renderer.render_timer.avg_render_ms > 0.0

    def test_render_timer_min_max_consistent(self) -> None:
        renderer = self._make_renderer()
        with renderer:
            for _ in range(10):
                renderer.present(Text("frame"))
            timer = renderer.render_timer
            assert timer.min_render_ms <= timer.avg_render_ms
            assert timer.avg_render_ms <= timer.max_render_ms

    def test_clear_buffer_does_not_record_timing(self) -> None:
        """clear_buffer() is not a present() call — no timing recorded."""
        renderer = self._make_renderer()
        with renderer:
            renderer.clear_buffer()
            assert renderer.render_timer.total_renders == 0


# ---------------------------------------------------------------------------
# Package-level export
# ---------------------------------------------------------------------------


class TestRenderTimerExport:
    """RenderTimer should be importable from the top-level package."""

    def test_importable_from_wyby(self) -> None:
        from wyby import RenderTimer as RT

        assert RT is RenderTimer

    def test_in_all(self) -> None:
        import wyby

        assert "RenderTimer" in wyby.__all__
