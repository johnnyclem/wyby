"""Tests for wyby.diagnostics — FPSCounter class."""

from __future__ import annotations

import pytest

from wyby.diagnostics import (
    FPSCounter,
    _DEFAULT_WINDOW_SIZE,
    _MAX_WINDOW_SIZE,
    _MIN_WINDOW_SIZE,
)


# ---------------------------------------------------------------------------
# Construction defaults
# ---------------------------------------------------------------------------


class TestFPSCounterDefaults:
    """FPSCounter() with no arguments should use sensible defaults."""

    def test_default_window_size(self) -> None:
        counter = FPSCounter()
        assert counter.window_size == _DEFAULT_WINDOW_SIZE

    def test_default_window_size_is_60(self) -> None:
        assert _DEFAULT_WINDOW_SIZE == 60

    def test_initial_fps_is_zero(self) -> None:
        counter = FPSCounter()
        assert counter.fps == 0.0

    def test_initial_frame_time_is_zero(self) -> None:
        counter = FPSCounter()
        assert counter.frame_time_ms == 0.0

    def test_initial_avg_frame_time_is_zero(self) -> None:
        counter = FPSCounter()
        assert counter.avg_frame_time_ms == 0.0

    def test_initial_min_fps_is_zero(self) -> None:
        counter = FPSCounter()
        assert counter.min_fps == 0.0

    def test_initial_max_fps_is_zero(self) -> None:
        counter = FPSCounter()
        assert counter.max_fps == 0.0

    def test_initial_sample_count_is_zero(self) -> None:
        counter = FPSCounter()
        assert counter.sample_count == 0

    def test_initial_tick_count_is_zero(self) -> None:
        counter = FPSCounter()
        assert counter.tick_count == 0


# ---------------------------------------------------------------------------
# Custom construction
# ---------------------------------------------------------------------------


class TestFPSCounterCustomInit:
    """FPSCounter() with explicit window_size."""

    def test_custom_window_size(self) -> None:
        counter = FPSCounter(window_size=10)
        assert counter.window_size == 10

    def test_window_size_min(self) -> None:
        counter = FPSCounter(window_size=_MIN_WINDOW_SIZE)
        assert counter.window_size == _MIN_WINDOW_SIZE

    def test_window_size_max(self) -> None:
        counter = FPSCounter(window_size=_MAX_WINDOW_SIZE)
        assert counter.window_size == _MAX_WINDOW_SIZE


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class TestFPSCounterValidation:
    """Invalid arguments should raise clear errors."""

    def test_window_size_not_int_raises_type_error(self) -> None:
        with pytest.raises(TypeError, match="window_size must be an int"):
            FPSCounter(window_size=10.0)  # type: ignore[arg-type]

    def test_window_size_bool_raises_type_error(self) -> None:
        with pytest.raises(TypeError, match="window_size must be an int"):
            FPSCounter(window_size=True)  # type: ignore[arg-type]

    def test_window_size_string_raises_type_error(self) -> None:
        with pytest.raises(TypeError, match="window_size must be an int"):
            FPSCounter(window_size="60")  # type: ignore[arg-type]

    def test_window_size_zero_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="window_size must be between"):
            FPSCounter(window_size=0)

    def test_window_size_negative_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="window_size must be between"):
            FPSCounter(window_size=-1)

    def test_window_size_too_large_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="window_size must be between"):
            FPSCounter(window_size=_MAX_WINDOW_SIZE + 1)


# ---------------------------------------------------------------------------
# Tick recording
# ---------------------------------------------------------------------------


class TestFPSCounterTick:
    """tick() should record timestamps and compute frame durations."""

    def test_first_tick_establishes_baseline(self) -> None:
        counter = FPSCounter()
        counter.tick(1.0)
        # First tick only sets the baseline, no sample yet.
        assert counter.tick_count == 1
        assert counter.sample_count == 0
        assert counter.fps == 0.0

    def test_second_tick_produces_first_sample(self) -> None:
        counter = FPSCounter()
        counter.tick(1.0)
        counter.tick(1.1)  # 100ms interval
        assert counter.tick_count == 2
        assert counter.sample_count == 1

    def test_fps_from_uniform_ticks(self) -> None:
        """Uniform 33ms intervals should produce ~30 FPS."""
        counter = FPSCounter(window_size=10)
        dt = 1.0 / 30.0  # ~33.33ms
        t = 0.0
        for _ in range(11):  # 1 baseline + 10 samples
            counter.tick(t)
            t += dt
        assert counter.sample_count == 10
        assert abs(counter.fps - 30.0) < 0.1

    def test_frame_time_ms(self) -> None:
        counter = FPSCounter()
        counter.tick(1.0)
        counter.tick(1.05)  # 50ms
        assert abs(counter.frame_time_ms - 50.0) < 0.01

    def test_avg_frame_time_ms(self) -> None:
        counter = FPSCounter(window_size=10)
        counter.tick(0.0)
        counter.tick(0.050)  # 50ms
        counter.tick(0.080)  # 30ms
        # Average of 50ms and 30ms = 40ms
        assert abs(counter.avg_frame_time_ms - 40.0) < 0.01

    def test_min_fps_from_longest_frame(self) -> None:
        counter = FPSCounter(window_size=10)
        counter.tick(0.0)
        counter.tick(0.010)  # 10ms -> 100 FPS
        counter.tick(0.110)  # 100ms -> 10 FPS  (longest)
        assert abs(counter.min_fps - 10.0) < 0.1

    def test_max_fps_from_shortest_frame(self) -> None:
        counter = FPSCounter(window_size=10)
        counter.tick(0.0)
        counter.tick(0.010)  # 10ms -> 100 FPS  (shortest)
        counter.tick(0.110)  # 100ms -> 10 FPS
        assert abs(counter.max_fps - 100.0) < 0.1

    def test_tick_count_tracks_all_calls(self) -> None:
        counter = FPSCounter()
        for i in range(5):
            counter.tick(float(i))
        assert counter.tick_count == 5


# ---------------------------------------------------------------------------
# Rolling window behavior
# ---------------------------------------------------------------------------


class TestFPSCounterRollingWindow:
    """The deque should evict old samples when the window is full."""

    def test_samples_capped_at_window_size(self) -> None:
        counter = FPSCounter(window_size=3)
        # 1 baseline + 5 more = 5 samples, but only 3 retained
        for i in range(6):
            counter.tick(float(i) * 0.033)
        assert counter.sample_count == 3

    def test_old_samples_evicted(self) -> None:
        """After filling, FPS should reflect only recent samples."""
        counter = FPSCounter(window_size=3)
        # Baseline
        counter.tick(0.0)
        # 3 slow ticks at 100ms each (10 FPS)
        counter.tick(0.1)
        counter.tick(0.2)
        counter.tick(0.3)
        assert abs(counter.fps - 10.0) < 0.1

        # Now 3 fast ticks at 10ms each (100 FPS)
        counter.tick(0.310)
        counter.tick(0.320)
        counter.tick(0.330)
        # Window should now contain only the 10ms samples
        assert abs(counter.fps - 100.0) < 0.1


# ---------------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------------


class TestFPSCounterReset:
    """reset() should clear all state."""

    def test_reset_clears_fps(self) -> None:
        counter = FPSCounter(window_size=10)
        counter.tick(0.0)
        counter.tick(0.033)
        assert counter.fps > 0
        counter.reset()
        assert counter.fps == 0.0

    def test_reset_clears_sample_count(self) -> None:
        counter = FPSCounter()
        counter.tick(0.0)
        counter.tick(0.033)
        counter.reset()
        assert counter.sample_count == 0

    def test_reset_clears_tick_count(self) -> None:
        counter = FPSCounter()
        counter.tick(0.0)
        counter.tick(0.033)
        counter.reset()
        assert counter.tick_count == 0

    def test_reset_clears_frame_time(self) -> None:
        counter = FPSCounter()
        counter.tick(0.0)
        counter.tick(0.033)
        counter.reset()
        assert counter.frame_time_ms == 0.0

    def test_ticks_after_reset_work(self) -> None:
        """After reset, counter should behave as freshly constructed."""
        counter = FPSCounter(window_size=10)
        counter.tick(0.0)
        counter.tick(0.033)
        counter.reset()
        # Re-establish baseline and record new samples
        counter.tick(1.0)
        counter.tick(1.05)  # 50ms -> 20 FPS
        assert counter.sample_count == 1
        assert abs(counter.fps - 20.0) < 0.1


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestFPSCounterEdgeCases:
    """Edge cases and degenerate inputs."""

    def test_zero_dt_does_not_crash(self) -> None:
        """Two ticks at the exact same timestamp."""
        counter = FPSCounter()
        counter.tick(1.0)
        counter.tick(1.0)
        # dt=0 means fps would be infinite; should return 0.0 safely
        assert counter.fps == 0.0

    def test_window_size_one(self) -> None:
        """Smallest possible window — purely instantaneous FPS."""
        counter = FPSCounter(window_size=1)
        counter.tick(0.0)
        counter.tick(0.050)
        assert abs(counter.fps - 20.0) < 0.1
        counter.tick(0.060)
        # Only the latest 10ms sample is retained
        assert abs(counter.fps - 100.0) < 0.1

    def test_repr(self) -> None:
        counter = FPSCounter(window_size=10)
        r = repr(counter)
        assert "FPSCounter" in r
        assert "window_size=10" in r
        assert "fps=" in r


# ---------------------------------------------------------------------------
# Engine integration — show_fps parameter
# ---------------------------------------------------------------------------


class TestEngineShowFPS:
    """Engine's show_fps parameter and fps_counter property."""

    def test_show_fps_default_is_false(self) -> None:
        from wyby.app import Engine
        engine = Engine()
        assert engine.show_fps is False

    def test_show_fps_false_gives_none_counter(self) -> None:
        from wyby.app import Engine
        engine = Engine(show_fps=False)
        assert engine.fps_counter is None

    def test_show_fps_true_creates_counter(self) -> None:
        from wyby.app import Engine
        engine = Engine(show_fps=True)
        assert engine.fps_counter is not None
        assert isinstance(engine.fps_counter, FPSCounter)

    def test_counter_updated_after_ticks(self) -> None:
        from wyby.app import Engine
        engine = Engine(show_fps=True)
        # Run a few single-tick iterations
        engine.run(loop=False)
        engine.run(loop=False)
        engine.run(loop=False)
        counter = engine.fps_counter
        assert counter is not None
        # Each run(loop=False) resets then does 1 tick,
        # so the counter gets reset each time.
        # After the last run: 1 tick recorded (baseline only).
        assert counter.tick_count == 1

    def test_counter_accumulates_in_loop_mode(self) -> None:
        """In loop mode, the counter should accumulate multiple ticks."""
        import threading
        from wyby.app import Engine

        engine = Engine(show_fps=True, tps=60)

        def stop_after_delay():
            import time
            time.sleep(0.15)
            engine.stop()

        t = threading.Thread(target=stop_after_delay)
        t.start()
        engine.run(loop=True)
        t.join()

        counter = engine.fps_counter
        assert counter is not None
        # Should have recorded multiple ticks
        assert counter.tick_count > 1

    def test_repr_includes_show_fps(self) -> None:
        from wyby.app import Engine
        engine = Engine(show_fps=True)
        assert "show_fps=True" in repr(engine)

    def test_repr_omits_show_fps_when_false(self) -> None:
        from wyby.app import Engine
        engine = Engine(show_fps=False)
        assert "show_fps" not in repr(engine)


# ---------------------------------------------------------------------------
# Package-level export
# ---------------------------------------------------------------------------


class TestFPSCounterExport:
    """FPSCounter should be importable from the top-level package."""

    def test_importable_from_wyby(self) -> None:
        from wyby import FPSCounter as FC
        assert FC is FPSCounter

    def test_in_all(self) -> None:
        import wyby
        assert "FPSCounter" in wyby.__all__
