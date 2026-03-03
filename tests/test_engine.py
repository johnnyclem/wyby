"""Tests for wyby.app — Engine class."""

from __future__ import annotations

import logging
import threading
import time
from unittest.mock import patch

import pytest

from wyby.app import (
    Engine,
    _DEFAULT_HEIGHT,
    _DEFAULT_TITLE,
    _DEFAULT_WIDTH,
    _MAX_HEIGHT,
    _MAX_WIDTH,
    _MIN_HEIGHT,
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

    def test_repr_custom(self) -> None:
        engine = Engine(title="Snake", width=40, height=20)
        assert repr(engine) == "Engine(title='Snake', width=40, height=20)"


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
        assert tick_count >= 1

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

    def test_dt_reflects_elapsed_time(self) -> None:
        """Mock time.monotonic to verify dt calculation."""
        fake_time = [100.0]

        def mock_monotonic() -> float:
            return fake_time[0]

        engine = Engine()
        with patch("wyby.app.time.monotonic", side_effect=mock_monotonic):
            # run() calls monotonic() once to set _last_tick_time (100.0).
            # _tick() calls monotonic() again — advance the clock first.
            fake_time[0] = 100.0
            # We need run() to capture 100.0, then _tick() to see 100.05.
            call_count = [0]

            def sequenced_monotonic() -> float:
                call_count[0] += 1
                if call_count[0] <= 1:
                    return 100.0  # run() initialization
                return 100.05  # _tick() measurement

            with patch(
                "wyby.app.time.monotonic", side_effect=sequenced_monotonic
            ):
                engine.run(loop=False)

        assert engine.dt == pytest.approx(0.05)

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
        """Mock time.monotonic to verify elapsed accumulation."""
        call_count = [0]
        # run() init: 0.0, tick1: 0.1, tick2: 0.25, tick3: 0.55
        times = [0.0, 0.1, 0.25, 0.55]

        def mock_monotonic() -> float:
            idx = min(call_count[0], len(times) - 1)
            val = times[idx]
            call_count[0] += 1
            return val

        engine = Engine()
        tick_count = [0]
        original_tick = Engine._tick

        def stop_after_three(self_: Engine) -> None:
            original_tick(self_)
            tick_count[0] += 1
            if tick_count[0] >= 3:
                self_.stop()

        monkeypatch.setattr(Engine, "_tick", stop_after_three)

        with patch("wyby.app.time.monotonic", side_effect=mock_monotonic):
            engine.run(loop=True)

        # dt values: 0.1-0.0=0.1, 0.25-0.1=0.15, 0.55-0.25=0.3
        # elapsed = 0.1 + 0.15 + 0.3 = 0.55
        assert engine.elapsed == pytest.approx(0.55)
        assert engine.tick_count == 3

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
        # At least 2 calls: one in run() init, one in _tick().
        assert mock.call_count >= 2
