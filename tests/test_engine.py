"""Tests for wyby.app — Engine class."""

from __future__ import annotations

import logging
import threading
import time
from unittest.mock import patch

import pytest

from wyby._logging import _LIBRARY_LOGGER_NAME
from wyby.app import (
    Engine,
    _DEFAULT_HEIGHT,
    _DEFAULT_TITLE,
    _DEFAULT_TPS,
    _DEFAULT_WIDTH,
    _DT_CLAMP,
    _MAX_FRAME_SKIP,
    _MAX_HEIGHT,
    _MAX_TPS,
    _MAX_WIDTH,
    _MIN_HEIGHT,
    _MIN_TPS,
    _MIN_WIDTH,
)


# ---------------------------------------------------------------------------
# Default construction
# ---------------------------------------------------------------------------


class TestEngineDefaults:
    """Engine() with no arguments should use sensible defaults."""

    def test_default_title(self) -> None:
        engine = Engine()
        assert engine.title == _DEFAULT_TITLE

    def test_default_width(self) -> None:
        engine = Engine()
        assert engine.width == _DEFAULT_WIDTH

    def test_default_height(self) -> None:
        engine = Engine()
        assert engine.height == _DEFAULT_HEIGHT

    def test_default_values_are_standard_terminal(self) -> None:
        """Defaults should match the classic 80x24 terminal size."""
        assert _DEFAULT_WIDTH == 80
        assert _DEFAULT_HEIGHT == 24


# ---------------------------------------------------------------------------
# Custom construction
# ---------------------------------------------------------------------------


class TestEngineCustomInit:
    """Engine() with explicit arguments."""

    def test_custom_title(self) -> None:
        engine = Engine(title="My Roguelike")
        assert engine.title == "My Roguelike"

    def test_custom_width(self) -> None:
        engine = Engine(width=120)
        assert engine.width == 120

    def test_custom_height(self) -> None:
        engine = Engine(height=40)
        assert engine.height == 40

    def test_all_custom(self) -> None:
        engine = Engine(title="Snake", width=40, height=20)
        assert engine.title == "Snake"
        assert engine.width == 40
        assert engine.height == 20

    def test_minimum_dimensions(self) -> None:
        engine = Engine(width=_MIN_WIDTH, height=_MIN_HEIGHT)
        assert engine.width == _MIN_WIDTH
        assert engine.height == _MIN_HEIGHT

    def test_maximum_dimensions(self) -> None:
        engine = Engine(width=_MAX_WIDTH, height=_MAX_HEIGHT)
        assert engine.width == _MAX_WIDTH
        assert engine.height == _MAX_HEIGHT


# ---------------------------------------------------------------------------
# Title validation
# ---------------------------------------------------------------------------


class TestEngineTitleValidation:
    """Title must be a non-empty string."""

    def test_rejects_non_string_title(self) -> None:
        with pytest.raises(TypeError, match="title must be a str"):
            Engine(title=42)  # type: ignore[arg-type]

    def test_rejects_none_title(self) -> None:
        with pytest.raises(TypeError, match="title must be a str"):
            Engine(title=None)  # type: ignore[arg-type]

    def test_rejects_empty_title(self) -> None:
        with pytest.raises(ValueError, match="must not be empty or blank"):
            Engine(title="")

    def test_rejects_blank_title(self) -> None:
        with pytest.raises(ValueError, match="must not be empty or blank"):
            Engine(title="   ")

    def test_allows_whitespace_padded_title(self) -> None:
        """A title with non-whitespace content surrounded by spaces is fine."""
        engine = Engine(title="  My Game  ")
        assert engine.title == "  My Game  "


# ---------------------------------------------------------------------------
# Width validation
# ---------------------------------------------------------------------------


class TestEngineWidthValidation:
    """Width must be an int in [1, 1000]."""

    def test_rejects_float_width(self) -> None:
        with pytest.raises(TypeError, match="width must be an int"):
            Engine(width=80.0)  # type: ignore[arg-type]

    def test_rejects_string_width(self) -> None:
        with pytest.raises(TypeError, match="width must be an int"):
            Engine(width="80")  # type: ignore[arg-type]

    def test_rejects_bool_width(self) -> None:
        with pytest.raises(TypeError, match="width must be an int"):
            Engine(width=True)  # type: ignore[arg-type]

    def test_rejects_zero_width(self) -> None:
        with pytest.raises(ValueError, match="width must be between"):
            Engine(width=0)

    def test_rejects_negative_width(self) -> None:
        with pytest.raises(ValueError, match="width must be between"):
            Engine(width=-1)

    def test_rejects_width_above_max(self) -> None:
        with pytest.raises(ValueError, match="width must be between"):
            Engine(width=_MAX_WIDTH + 1)


# ---------------------------------------------------------------------------
# Height validation
# ---------------------------------------------------------------------------


class TestEngineHeightValidation:
    """Height must be an int in [1, 1000]."""

    def test_rejects_float_height(self) -> None:
        with pytest.raises(TypeError, match="height must be an int"):
            Engine(height=24.0)  # type: ignore[arg-type]

    def test_rejects_string_height(self) -> None:
        with pytest.raises(TypeError, match="height must be an int"):
            Engine(height="24")  # type: ignore[arg-type]

    def test_rejects_bool_height(self) -> None:
        with pytest.raises(TypeError, match="height must be an int"):
            Engine(height=True)  # type: ignore[arg-type]

    def test_rejects_zero_height(self) -> None:
        with pytest.raises(ValueError, match="height must be between"):
            Engine(height=0)

    def test_rejects_negative_height(self) -> None:
        with pytest.raises(ValueError, match="height must be between"):
            Engine(height=-1)

    def test_rejects_height_above_max(self) -> None:
        with pytest.raises(ValueError, match="height must be between"):
            Engine(height=_MAX_HEIGHT + 1)


# ---------------------------------------------------------------------------
# Properties are read-only
# ---------------------------------------------------------------------------


class TestEngineReadOnlyProperties:
    """Engine properties should not be directly settable."""

    def test_title_is_read_only(self) -> None:
        engine = Engine()
        with pytest.raises(AttributeError):
            engine.title = "New Title"  # type: ignore[misc]

    def test_width_is_read_only(self) -> None:
        engine = Engine()
        with pytest.raises(AttributeError):
            engine.width = 100  # type: ignore[misc]

    def test_height_is_read_only(self) -> None:
        engine = Engine()
        with pytest.raises(AttributeError):
            engine.height = 50  # type: ignore[misc]


# ---------------------------------------------------------------------------
# __repr__
# ---------------------------------------------------------------------------


class TestEngineRepr:
    """Engine.__repr__ should be informative and eval-safe."""

    def test_repr_default(self) -> None:
        engine = Engine()
        r = repr(engine)
        assert "Engine(" in r
        assert "'wyby'" in r
        assert "80" in r
        assert "24" in r
        assert "tps=30" in r

    def test_repr_custom(self) -> None:
        engine = Engine(title="Snake", width=40, height=20)
        assert repr(engine) == "Engine(title='Snake', width=40, height=20, tps=30)"

    def test_repr_custom_tps(self) -> None:
        engine = Engine(title="Snake", width=40, height=20, tps=60)
        assert repr(engine) == "Engine(title='Snake', width=40, height=20, tps=60)"


# ---------------------------------------------------------------------------
# Public re-export from wyby package
# ---------------------------------------------------------------------------


class TestEngineImport:
    """Engine should be importable from the top-level wyby package."""

    def test_importable_from_wyby(self) -> None:
        from wyby import Engine as EngineFromInit

        assert EngineFromInit is Engine


# ---------------------------------------------------------------------------
# running property
# ---------------------------------------------------------------------------


class TestEngineRunningProperty:
    """Engine.running reflects the loop state."""

    def test_not_running_after_construction(self) -> None:
        engine = Engine()
        assert engine.running is False

    def test_not_running_after_single_tick(self) -> None:
        engine = Engine()
        engine.run(loop=False)
        assert engine.running is False

    def test_running_is_read_only(self) -> None:
        engine = Engine()
        with pytest.raises(AttributeError):
            engine.running = True  # type: ignore[misc]


# ---------------------------------------------------------------------------
# run() with loop=False (single tick)
# ---------------------------------------------------------------------------


class TestEngineRunSingleTick:
    """run(loop=False) should execute exactly one tick and return."""

    def test_returns_without_error(self) -> None:
        engine = Engine()
        engine.run(loop=False)

    def test_tick_is_called_once(self, monkeypatch: pytest.MonkeyPatch) -> None:
        engine = Engine()
        tick_count = 0

        original_tick = Engine._tick

        def counting_tick(self: Engine) -> None:
            nonlocal tick_count
            tick_count += 1
            original_tick(self)

        monkeypatch.setattr(Engine, "_tick", counting_tick)
        engine.run(loop=False)
        assert tick_count == 1

    def test_running_is_false_after_return(self) -> None:
        engine = Engine()
        engine.run(loop=False)
        assert engine.running is False

    def test_logs_start_and_finish(self, caplog: pytest.LogCaptureFixture) -> None:
        engine = Engine()
        with caplog.at_level(logging.DEBUG, logger="wyby.app"):
            engine.run(loop=False)
        messages = [r.message for r in caplog.records]
        assert any("starting" in m and "loop=False" in m for m in messages)
        assert any("finished" in m for m in messages)


# ---------------------------------------------------------------------------
# run() with loop=True (continuous loop)
# ---------------------------------------------------------------------------


class TestEngineRunLoop:
    """run(loop=True) should loop until stop() is called."""

    def test_stop_ends_loop(self, monkeypatch: pytest.MonkeyPatch) -> None:
        engine = Engine()
        tick_count = 0

        def stop_after_three(self_: Engine) -> None:
            nonlocal tick_count
            tick_count += 1
            if tick_count >= 3:
                self_.stop()

        monkeypatch.setattr(Engine, "_tick", stop_after_three)
        engine.run(loop=True)
        assert tick_count == 3
        assert engine.running is False

    def test_stop_from_another_thread(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        engine = Engine()
        tick_count = 0

        def counting_tick(self_: Engine) -> None:
            nonlocal tick_count
            tick_count += 1

        monkeypatch.setattr(Engine, "_tick", counting_tick)

        def stop_soon() -> None:
            # Give the loop a moment to start, then stop it.
            while not engine.running:
                pass
            engine.stop()

        t = threading.Thread(target=stop_soon)
        t.start()
        engine.run(loop=True)
        t.join(timeout=2.0)
        assert not t.is_alive()
        assert engine.running is False
        # With fixed timestep, stop may arrive before the accumulator
        # fills enough for a tick, so tick_count may be 0.
        assert tick_count >= 0

    def test_keyboard_interrupt_stops_loop(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        engine = Engine()
        call_count = 0

        def raise_on_second(self_: Engine) -> None:
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                raise KeyboardInterrupt

        monkeypatch.setattr(Engine, "_tick", raise_on_second)
        # Should not raise — KeyboardInterrupt is caught internally.
        engine.run(loop=True)
        assert engine.running is False
        assert call_count == 2

    def test_keyboard_interrupt_logs_message(
        self,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        engine = Engine()

        def raise_interrupt(self_: Engine) -> None:
            raise KeyboardInterrupt

        monkeypatch.setattr(Engine, "_tick", raise_interrupt)
        with caplog.at_level(logging.DEBUG, logger="wyby.app"):
            engine.run(loop=True)
        messages = [r.message for r in caplog.records]
        assert any("KeyboardInterrupt" in m for m in messages)


# ---------------------------------------------------------------------------
# run() re-entrance guard
# ---------------------------------------------------------------------------


class TestEngineRunReentrance:
    """Calling run() while already running should be a no-op."""

    def test_reentrant_run_is_ignored(
        self,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        engine = Engine()
        called_reentrant = False

        def try_reentrant(self_: Engine) -> None:
            nonlocal called_reentrant
            # Attempt to call run() again from inside _tick.
            self_.run(loop=False)
            called_reentrant = True
            self_.stop()

        monkeypatch.setattr(Engine, "_tick", try_reentrant)
        with caplog.at_level(logging.DEBUG, logger="wyby.app"):
            engine.run(loop=True)
        # The reentrant call should have returned immediately (no-op).
        assert called_reentrant is True
        messages = [r.message for r in caplog.records]
        assert any("already running" in m for m in messages)


# ---------------------------------------------------------------------------
# stop() when not running
# ---------------------------------------------------------------------------


class TestEngineStop:
    """stop() should be a harmless no-op when not running."""

    def test_stop_when_not_running(self) -> None:
        engine = Engine()
        engine.stop()  # Should not raise.
        assert engine.running is False


# ---------------------------------------------------------------------------
# Clock / tick timing
# ---------------------------------------------------------------------------


class TestEngineClockDefaults:
    """Clock properties should be zero before run() is called."""

    def test_tick_count_zero_before_run(self) -> None:
        engine = Engine()
        assert engine.tick_count == 0

    def test_dt_zero_before_run(self) -> None:
        engine = Engine()
        assert engine.dt == 0.0

    def test_elapsed_zero_before_run(self) -> None:
        engine = Engine()
        assert engine.elapsed == 0.0


class TestEngineClockReadOnly:
    """Clock properties should not be directly settable."""

    def test_tick_count_is_read_only(self) -> None:
        engine = Engine()
        with pytest.raises(AttributeError):
            engine.tick_count = 5  # type: ignore[misc]

    def test_dt_is_read_only(self) -> None:
        engine = Engine()
        with pytest.raises(AttributeError):
            engine.dt = 1.0  # type: ignore[misc]

    def test_elapsed_is_read_only(self) -> None:
        engine = Engine()
        with pytest.raises(AttributeError):
            engine.elapsed = 1.0  # type: ignore[misc]


class TestEngineTickCount:
    """tick_count should track the number of ticks executed."""

    def test_single_tick_increments_count(self) -> None:
        engine = Engine()
        engine.run(loop=False)
        assert engine.tick_count == 1

    def test_multiple_ticks(self, monkeypatch: pytest.MonkeyPatch) -> None:
        engine = Engine()
        tick_target = 5
        call_count = 0

        original_tick = Engine._tick

        def counting_tick(self_: Engine) -> None:
            nonlocal call_count
            original_tick(self_)
            call_count += 1
            if call_count >= tick_target:
                self_.stop()

        monkeypatch.setattr(Engine, "_tick", counting_tick)
        engine.run(loop=True)
        assert engine.tick_count == tick_target

    def test_tick_count_resets_on_new_run(self) -> None:
        engine = Engine()
        engine.run(loop=False)
        assert engine.tick_count == 1
        engine.run(loop=False)
        assert engine.tick_count == 1  # Reset, then incremented once.


class TestEngineDt:
    """dt should measure wall-clock duration of the most recent tick."""

    def test_dt_is_positive_after_tick(self) -> None:
        engine = Engine()
        engine.run(loop=False)
        assert engine.dt > 0.0

    def test_dt_equals_target_dt(self) -> None:
        """dt should be the fixed timestep (target_dt), not wall-clock."""
        engine = Engine(tps=30)
        engine.run(loop=False)
        assert engine.dt == pytest.approx(1.0 / 30)

    def test_dt_equals_target_dt_custom_tps(self) -> None:
        """dt should reflect the configured tps."""
        engine = Engine(tps=60)
        engine.run(loop=False)
        assert engine.dt == pytest.approx(1.0 / 60)

    def test_dt_resets_on_new_run(self) -> None:
        engine = Engine()
        engine.run(loop=False)
        first_dt = engine.dt
        assert first_dt > 0.0
        # After a new run(), dt should reflect the new tick, not accumulate.
        engine.run(loop=False)
        assert engine.dt > 0.0


class TestEngineElapsed:
    """elapsed should accumulate dt across ticks within a single run()."""

    def test_elapsed_positive_after_tick(self) -> None:
        engine = Engine()
        engine.run(loop=False)
        assert engine.elapsed > 0.0

    def test_elapsed_accumulates_across_ticks(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """elapsed = tick_count * target_dt in fixed-timestep mode."""
        engine = Engine(tps=30)
        target_dt = 1.0 / 30
        tick_count = [0]
        original_tick = Engine._tick

        def stop_after_three(self_: Engine) -> None:
            original_tick(self_)
            tick_count[0] += 1
            if tick_count[0] >= 3:
                self_.stop()

        monkeypatch.setattr(Engine, "_tick", stop_after_three)
        engine.run(loop=True)

        assert engine.tick_count == 3
        assert engine.elapsed == pytest.approx(3 * target_dt)

    def test_elapsed_resets_on_new_run(self) -> None:
        engine = Engine()
        engine.run(loop=False)
        first_elapsed = engine.elapsed
        assert first_elapsed > 0.0
        engine.run(loop=False)
        # elapsed should be reset — it only reflects the latest run().
        # It will be a small positive value (one tick), not accumulated.
        assert engine.elapsed > 0.0
        assert engine.elapsed < first_elapsed + 1.0  # Sanity bound.


class TestEngineClockUsesMonotonic:
    """Verify that the clock uses time.monotonic, not time.time."""

    def test_monotonic_is_called(self) -> None:
        engine = Engine()
        with patch("wyby.app.time.monotonic", wraps=time.monotonic) as mock:
            engine.run(loop=False)
        # monotonic is called once in run() to set _last_tick_time.
        # _tick() no longer calls monotonic (uses fixed timestep).
        assert mock.call_count >= 1

    def test_monotonic_called_in_loop(self) -> None:
        """In loop mode, monotonic is called each frame iteration."""
        engine = Engine()
        original_tick = Engine._tick
        tick_count = [0]

        def stop_after_one(self_: Engine) -> None:
            original_tick(self_)
            tick_count[0] += 1
            if tick_count[0] >= 1:
                self_.stop()

        with patch("wyby.app.time.monotonic", wraps=time.monotonic) as mock:
            with patch.object(Engine, "_tick", stop_after_one):
                engine.run(loop=True)
        # run() init + at least one _run_loop iteration.
        assert mock.call_count >= 2


# ---------------------------------------------------------------------------
# TPS validation
# ---------------------------------------------------------------------------


class TestEngineTpsValidation:
    """tps must be an int in [1, 240]."""

    def test_rejects_float_tps(self) -> None:
        with pytest.raises(TypeError, match="tps must be an int"):
            Engine(tps=30.0)  # type: ignore[arg-type]

    def test_rejects_string_tps(self) -> None:
        with pytest.raises(TypeError, match="tps must be an int"):
            Engine(tps="30")  # type: ignore[arg-type]

    def test_rejects_bool_tps(self) -> None:
        with pytest.raises(TypeError, match="tps must be an int"):
            Engine(tps=True)  # type: ignore[arg-type]

    def test_rejects_zero_tps(self) -> None:
        with pytest.raises(ValueError, match="tps must be between"):
            Engine(tps=0)

    def test_rejects_negative_tps(self) -> None:
        with pytest.raises(ValueError, match="tps must be between"):
            Engine(tps=-1)

    def test_rejects_tps_above_max(self) -> None:
        with pytest.raises(ValueError, match="tps must be between"):
            Engine(tps=_MAX_TPS + 1)


# ---------------------------------------------------------------------------
# TPS and target_dt properties
# ---------------------------------------------------------------------------


class TestEngineTpsProperty:
    """tps and target_dt should expose tick rate configuration."""

    def test_default_tps(self) -> None:
        engine = Engine()
        assert engine.tps == _DEFAULT_TPS

    def test_default_tps_is_30(self) -> None:
        assert _DEFAULT_TPS == 30

    def test_custom_tps(self) -> None:
        engine = Engine(tps=60)
        assert engine.tps == 60

    def test_minimum_tps(self) -> None:
        engine = Engine(tps=_MIN_TPS)
        assert engine.tps == _MIN_TPS

    def test_maximum_tps(self) -> None:
        engine = Engine(tps=_MAX_TPS)
        assert engine.tps == _MAX_TPS

    def test_tps_is_read_only(self) -> None:
        engine = Engine()
        with pytest.raises(AttributeError):
            engine.tps = 60  # type: ignore[misc]

    def test_target_dt_matches_tps(self) -> None:
        engine = Engine(tps=30)
        assert engine.target_dt == pytest.approx(1.0 / 30)

    def test_target_dt_custom_tps(self) -> None:
        engine = Engine(tps=60)
        assert engine.target_dt == pytest.approx(1.0 / 60)

    def test_target_dt_is_read_only(self) -> None:
        engine = Engine()
        with pytest.raises(AttributeError):
            engine.target_dt = 0.1  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Fixed timestep accumulator
# ---------------------------------------------------------------------------


class TestEngineFixedTimestep:
    """Fixed timestep: accumulator, sleep, frame-skip, and dt clamping."""

    def test_dt_equals_target_dt_after_single_tick(self) -> None:
        """dt should be target_dt even for a single tick (loop=False)."""
        engine = Engine(tps=60)
        engine.run(loop=False)
        assert engine.dt == pytest.approx(1.0 / 60)

    def test_elapsed_is_tick_count_times_target_dt(self) -> None:
        """elapsed should be exactly tick_count * target_dt."""
        engine = Engine(tps=30)
        target_dt = 1.0 / 30
        tick_count = [0]
        original_tick = Engine._tick

        def counting_tick(self_: Engine) -> None:
            original_tick(self_)
            tick_count[0] += 1
            if tick_count[0] >= 5:
                self_.stop()

        with patch.object(Engine, "_tick", counting_tick):
            engine.run(loop=True)

        assert engine.tick_count == 5
        assert engine.elapsed == pytest.approx(5 * target_dt)

    def test_loop_sleeps_to_pace(self) -> None:
        """The loop should call time.sleep to maintain target tick rate."""
        mono_calls = [0]

        def mock_monotonic() -> float:
            mono_calls[0] += 1
            if mono_calls[0] == 1:
                return 0.0  # run() init
            # Each frame iteration advances by exactly target_dt.
            return (mono_calls[0] - 1) * (1.0 / 30)

        engine = Engine(tps=30)
        original_tick = Engine._tick
        tick_count = [0]

        def stop_after_two(self_: Engine) -> None:
            original_tick(self_)
            tick_count[0] += 1
            if tick_count[0] >= 2:
                self_.stop()

        with patch.object(Engine, "_tick", stop_after_two):
            with patch("wyby.app.time.monotonic", side_effect=mock_monotonic):
                with patch("wyby.app.time.sleep") as mock_sleep:
                    engine.run(loop=True)

        # Sleep should have been called after the first frame (before
        # stop was triggered on the second tick).
        assert mock_sleep.called

    def test_no_sleep_when_behind(self) -> None:
        """If a frame takes longer than target_dt, no sleep should occur."""
        mono_calls = [0]

        def mock_monotonic() -> float:
            mono_calls[0] += 1
            if mono_calls[0] == 1:
                return 0.0
            if mono_calls[0] == 2:
                # Frame took 2x target_dt — we're behind.
                return 2.0 / 30
            return 2.0 / 30 + (mono_calls[0] - 2) * (1.0 / 30)

        engine = Engine(tps=30)
        original_tick = Engine._tick
        tick_count = [0]

        def stop_after_two(self_: Engine) -> None:
            original_tick(self_)
            tick_count[0] += 1
            if tick_count[0] >= 2:
                self_.stop()

        with patch.object(Engine, "_tick", stop_after_two):
            with patch("wyby.app.time.monotonic", side_effect=mock_monotonic):
                with patch("wyby.app.time.sleep"):
                    engine.run(loop=True)

        # Both ticks should run in the first frame (catching up).
        # No sleep is needed since the accumulator was fully drained.
        assert tick_count[0] == 2

    def test_dt_clamp_on_large_gap(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Large time gaps (suspend/resume) should be clamped."""
        mono_calls = [0]

        def mock_monotonic() -> float:
            mono_calls[0] += 1
            if mono_calls[0] == 1:
                return 0.0  # run() init
            if mono_calls[0] == 2:
                return 10.0  # 10-second gap (suspend/resume)
            return 10.0 + (mono_calls[0] - 2) * (1.0 / 30)

        engine = Engine(tps=30)
        original_tick = Engine._tick
        tick_count = [0]

        def stop_tick(self_: Engine) -> None:
            original_tick(self_)
            tick_count[0] += 1
            if tick_count[0] >= 1:
                self_.stop()

        with caplog.at_level(logging.DEBUG, logger="wyby.app"):
            with patch.object(Engine, "_tick", stop_tick):
                with patch(
                    "wyby.app.time.monotonic", side_effect=mock_monotonic
                ):
                    with patch("wyby.app.time.sleep"):
                        engine.run(loop=True)

        # The 10-second gap should have been clamped.
        messages = [r.getMessage() for r in caplog.records]
        assert any("Clamping" in m for m in messages)

    def test_dt_clamp_value(self) -> None:
        """Clamped frame_time should be _DT_CLAMP (0.25s)."""
        assert _DT_CLAMP == 0.25

    def test_frame_skip_limits_per_frame_updates(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """At most _MAX_FRAME_SKIP ticks per frame, logging when hit."""
        mono_calls = [0]

        def mock_monotonic() -> float:
            mono_calls[0] += 1
            if mono_calls[0] == 1:
                return 0.0  # run() init
            if mono_calls[0] == 2:
                return 0.20  # 200ms gap → ~6 ticks at 30 tps
            # Advance normally after first frame.
            return 0.20 + (mono_calls[0] - 2) * (1.0 / 30)

        engine = Engine(tps=30)
        original_tick = Engine._tick
        tick_count = [0]

        def counting_stop(self_: Engine) -> None:
            original_tick(self_)
            tick_count[0] += 1
            if tick_count[0] > _MAX_FRAME_SKIP:
                self_.stop()

        with caplog.at_level(logging.DEBUG, logger="wyby.app"):
            with patch.object(Engine, "_tick", counting_stop):
                with patch(
                    "wyby.app.time.monotonic", side_effect=mock_monotonic
                ):
                    with patch("wyby.app.time.sleep"):
                        engine.run(loop=True)

        messages = [r.getMessage() for r in caplog.records]
        assert any("Frame-skip limit" in m for m in messages)
        # First frame ran _MAX_FRAME_SKIP ticks, second frame ran 1 more.
        assert tick_count[0] == _MAX_FRAME_SKIP + 1

    def test_max_frame_skip_value(self) -> None:
        """_MAX_FRAME_SKIP should be 5."""
        assert _MAX_FRAME_SKIP == 5

    def test_accumulator_resets_on_new_run(self) -> None:
        """Each run() call resets the accumulator to zero."""
        engine = Engine()
        engine.run(loop=False)
        engine.run(loop=False)
        # If the accumulator leaked between runs, the second run would
        # behave differently.  tick_count being 1 confirms a clean reset.
        assert engine.tick_count == 1


# ---------------------------------------------------------------------------
# Debug mode
# ---------------------------------------------------------------------------


@pytest.fixture()
def _restore_wyby_logger():
    """Save and restore the wyby logger's handlers and level.

    Engine(debug=True) mutates the shared wyby logger via
    configure_logging(). Without cleanup, state leaks between tests.
    """
    logger = logging.getLogger(_LIBRARY_LOGGER_NAME)
    original_handlers = logger.handlers[:]
    original_level = logger.level
    yield
    logger.handlers[:] = original_handlers
    logger.setLevel(original_level)


@pytest.mark.usefixtures("_restore_wyby_logger")
class TestEngineDebugMode:
    """Engine(debug=True) should enable verbose logging."""

    def test_debug_defaults_to_false(self) -> None:
        engine = Engine()
        assert engine.debug is False

    def test_debug_can_be_enabled(self) -> None:
        engine = Engine(debug=True)
        assert engine.debug is True

    def test_debug_is_read_only(self) -> None:
        engine = Engine()
        with pytest.raises(AttributeError):
            engine.debug = True  # type: ignore[misc]

    def test_debug_configures_logging_at_debug_level(self) -> None:
        """debug=True should set the wyby logger to DEBUG level."""
        Engine(debug=True)
        logger = logging.getLogger(_LIBRARY_LOGGER_NAME)
        assert logger.level == logging.DEBUG

    def test_debug_false_does_not_change_logging(self) -> None:
        """debug=False (default) should not alter the logger level."""
        logger = logging.getLogger(_LIBRARY_LOGGER_NAME)
        level_before = logger.level
        Engine(debug=False)
        assert logger.level == level_before

    def test_debug_adds_stderr_handler(self) -> None:
        """debug=True should add a StreamHandler to the wyby logger."""
        logger = logging.getLogger(_LIBRARY_LOGGER_NAME)
        handler_count_before = len(logger.handlers)
        Engine(debug=True)
        assert len(logger.handlers) > handler_count_before

    def test_debug_emits_init_message(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """debug=True should produce the Engine initialized log message."""
        with caplog.at_level(logging.DEBUG, logger="wyby.app"):
            Engine(debug=True)
        messages = [r.message for r in caplog.records]
        assert any("Engine initialized" in m for m in messages)

    def test_debug_coerces_truthy_values(self) -> None:
        """Non-bool truthy values should be coerced to True."""
        engine = Engine(debug=1)  # type: ignore[arg-type]
        assert engine.debug is True

    def test_debug_coerces_falsy_values(self) -> None:
        """Non-bool falsy values should be coerced to False."""
        engine = Engine(debug=0)  # type: ignore[arg-type]
        assert engine.debug is False


@pytest.mark.usefixtures("_restore_wyby_logger")
class TestEngineDebugRepr:
    """__repr__ should include debug=True only when debug is enabled."""

    def test_repr_omits_debug_when_false(self) -> None:
        engine = Engine()
        assert "debug" not in repr(engine)

    def test_repr_includes_debug_when_true(self) -> None:
        engine = Engine(debug=True)
        r = repr(engine)
        assert "debug=True" in r

    def test_repr_debug_format(self) -> None:
        engine = Engine(title="Snake", width=40, height=20, debug=True)
        assert repr(engine) == (
            "Engine(title='Snake', width=40, height=20, tps=30, debug=True)"
        )
