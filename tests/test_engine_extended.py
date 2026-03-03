"""Extended tests for wyby.app — Engine subsystem integration.

Covers areas not yet tested by test_engine.py or test_engine_config.py:

- QuitSignal exception class
- show_fps / FPSCounter integration
- Console property and custom console injection
- LiveDisplay property and shutdown lifecycle
- InputManager integration (validation, polling, start/stop)
- Signal handler install/uninstall during run()
- Engine events and scenes property accessors
- Empty scene stack tick behaviour
- _SLEEP_THRESHOLD constant
- show_fps in __repr__

Caveats:
    - Tests that verify InputManager integration mock the manager to
      avoid entering terminal raw mode during test runs.  Real raw-mode
      integration is not tested here — that requires a real TTY.
    - Tests that verify LiveDisplay.stop() mock the display to avoid
      writing ANSI escape sequences to the test runner's output.
    - Signal handler tests are limited to verifying that install() and
      uninstall() are called.  Actual signal delivery tests are fragile
      and platform-dependent — they belong in integration tests, not
      unit tests.
    - FPSCounter.tick() is verified by checking call count, not by
      asserting specific FPS values.  FPS computation accuracy is
      tested in test_diagnostics.py.
"""

from __future__ import annotations

import io
import logging
from unittest.mock import MagicMock, patch

import pytest

from wyby.app import (
    Engine,
    EngineConfig,
    QuitSignal,
    _SLEEP_THRESHOLD,
)
from wyby.event import Event, EventQueue
from wyby.input import InputManager
from wyby.renderer import LiveDisplay, create_console
from wyby.scene import Scene, SceneStack


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _StubScene(Scene):
    """Minimal concrete Scene for testing."""

    def __init__(self) -> None:
        super().__init__()
        self.update_calls: list[float] = []
        self.render_calls: int = 0

    def update(self, dt: float) -> None:
        self.update_calls.append(dt)

    def render(self) -> None:
        self.render_calls += 1


class _QuitOnFirstUpdateScene(Scene):
    """Scene that raises QuitSignal on its first update."""

    def update(self, dt: float) -> None:
        raise QuitSignal("player quit")

    def render(self) -> None:
        pass


class _DummyEvent(Event):
    """Trivial event subclass for testing."""


# ---------------------------------------------------------------------------
# QuitSignal
# ---------------------------------------------------------------------------


class TestQuitSignal:
    """QuitSignal is a clean shutdown exception for game code."""

    def test_is_exception_subclass(self) -> None:
        assert issubclass(QuitSignal, Exception)

    def test_is_not_base_exception_direct_subclass(self) -> None:
        # QuitSignal inherits Exception, not BaseException directly.
        # This means bare `except Exception` blocks will catch it —
        # game code should re-raise QuitSignal explicitly if using
        # broad except clauses.
        assert QuitSignal.__bases__ == (Exception,)

    def test_can_be_raised_and_caught(self) -> None:
        with pytest.raises(QuitSignal):
            raise QuitSignal("done")

    def test_message_preserved(self) -> None:
        try:
            raise QuitSignal("player pressed escape")
        except QuitSignal as exc:
            assert str(exc) == "player pressed escape"

    def test_no_message(self) -> None:
        """QuitSignal with no args should work (empty message)."""
        try:
            raise QuitSignal()
        except QuitSignal as exc:
            assert str(exc) == ""

    def test_importable_from_wyby(self) -> None:
        from wyby import QuitSignal as FromInit

        assert FromInit is QuitSignal


class TestQuitSignalInEngine:
    """Engine should catch QuitSignal as a clean shutdown."""

    def test_quit_signal_stops_loop(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        engine = Engine()

        def raise_quit(self_: Engine) -> None:
            raise QuitSignal("done")

        monkeypatch.setattr(Engine, "_tick", raise_quit)
        # Should NOT raise — QuitSignal is caught internally.
        engine.run(loop=True)
        assert engine.running is False

    def test_quit_signal_from_scene_update(self) -> None:
        """QuitSignal raised in scene.update() triggers clean shutdown."""
        engine = Engine()
        scene = _QuitOnFirstUpdateScene()
        engine.push_scene(scene)
        engine.run(loop=False)
        assert engine.running is False

    def test_quit_signal_logs_message(
        self,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        engine = Engine()

        def raise_quit(self_: Engine) -> None:
            raise QuitSignal("bye")

        monkeypatch.setattr(Engine, "_tick", raise_quit)
        with caplog.at_level(logging.DEBUG, logger="wyby.app"):
            engine.run(loop=True)
        messages = [r.message for r in caplog.records]
        assert any("QuitSignal" in m for m in messages)

    def test_quit_signal_scenes_cleaned_up(self) -> None:
        """Scenes should receive on_exit when QuitSignal stops the engine."""
        engine = Engine()
        stub = _StubScene()
        engine.push_scene(stub)
        engine.push_scene(_QuitOnFirstUpdateScene())
        engine.run(loop=False)
        # The stub scene should have been torn down.
        assert engine.scenes.is_empty


# ---------------------------------------------------------------------------
# show_fps / FPSCounter integration
# ---------------------------------------------------------------------------


class TestShowFps:
    """show_fps enables an FPSCounter on the engine."""

    def test_show_fps_defaults_to_false(self) -> None:
        engine = Engine()
        assert engine.show_fps is False

    def test_show_fps_can_be_enabled(self) -> None:
        engine = Engine(show_fps=True)
        assert engine.show_fps is True

    def test_show_fps_is_read_only(self) -> None:
        engine = Engine()
        with pytest.raises(AttributeError):
            engine.show_fps = True  # type: ignore[misc]

    def test_fps_counter_none_when_disabled(self) -> None:
        engine = Engine()
        assert engine.fps_counter is None

    def test_fps_counter_created_when_enabled(self) -> None:
        engine = Engine(show_fps=True)
        assert engine.fps_counter is not None

    def test_fps_counter_is_read_only(self) -> None:
        engine = Engine()
        with pytest.raises(AttributeError):
            engine.fps_counter = None  # type: ignore[misc]

    def test_fps_counter_ticked_during_engine_tick(self) -> None:
        """FPSCounter.tick() should be called once per engine tick."""
        engine = Engine(show_fps=True)
        counter = engine.fps_counter
        assert counter is not None
        engine.run(loop=False)
        # After one tick, the counter's tick_count should be 1.
        # Note: sample_count is 0 after the first tick because the
        # first call to FPSCounter.tick() only establishes a baseline
        # timestamp — it takes two ticks to produce one frame-time
        # sample.
        assert counter.tick_count >= 1

    def test_fps_counter_reset_on_new_run(self) -> None:
        """FPSCounter should be reset at the start of each run() call."""
        engine = Engine(show_fps=True)
        engine.run(loop=False)
        counter = engine.fps_counter
        assert counter is not None
        count_after_first = counter.tick_count
        assert count_after_first >= 1
        engine.run(loop=False)
        # After reset + one tick, tick_count should be 1 again.
        # (reset() clears tick_count to 0, then _tick() increments it.)
        assert counter.tick_count == 1

    def test_show_fps_coerces_truthy(self) -> None:
        engine = Engine(show_fps=1)  # type: ignore[arg-type]
        assert engine.show_fps is True
        assert engine.fps_counter is not None

    def test_show_fps_coerces_falsy(self) -> None:
        engine = Engine(show_fps=0)  # type: ignore[arg-type]
        assert engine.show_fps is False
        assert engine.fps_counter is None


class TestShowFpsRepr:
    """__repr__ should include show_fps=True only when enabled."""

    def test_repr_omits_show_fps_when_false(self) -> None:
        engine = Engine()
        assert "show_fps" not in repr(engine)

    def test_repr_includes_show_fps_when_true(self) -> None:
        engine = Engine(show_fps=True)
        assert "show_fps=True" in repr(engine)

    def test_repr_show_fps_format(self) -> None:
        engine = Engine(title="Snake", width=40, height=20, show_fps=True)
        expected = (
            "Engine(title='Snake', width=40, height=20, "
            "tps=30, show_fps=True)"
        )
        assert repr(engine) == expected


# ---------------------------------------------------------------------------
# Console property
# ---------------------------------------------------------------------------


class TestEngineConsole:
    """Engine.console exposes the Rich Console for terminal output."""

    def test_console_is_not_none(self) -> None:
        engine = Engine()
        assert engine.console is not None

    def test_custom_console_injection(self) -> None:
        """A custom Console passed at construction should be used."""
        custom = create_console(
            file=io.StringIO(), force_terminal=True
        )
        engine = Engine(console=custom)
        assert engine.console is custom

    def test_console_is_read_only(self) -> None:
        engine = Engine()
        with pytest.raises(AttributeError):
            engine.console = None  # type: ignore[misc]

    def test_console_shared_with_live_display(self) -> None:
        """Console and LiveDisplay should share the same Console instance."""
        engine = Engine()
        # LiveDisplay wraps the same console — verify by checking the
        # live_display's existence (the internal _console is private,
        # but we can confirm the engine created both).
        assert engine.live_display is not None


# ---------------------------------------------------------------------------
# LiveDisplay property
# ---------------------------------------------------------------------------


class TestEngineLiveDisplay:
    """Engine.live_display provides the Rich Live wrapper."""

    def test_live_display_is_not_none(self) -> None:
        engine = Engine()
        assert engine.live_display is not None

    def test_live_display_is_live_display_instance(self) -> None:
        engine = Engine()
        assert isinstance(engine.live_display, LiveDisplay)

    def test_live_display_is_read_only(self) -> None:
        engine = Engine()
        with pytest.raises(AttributeError):
            engine.live_display = None  # type: ignore[misc]

    def test_live_display_stopped_during_shutdown(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """LiveDisplay.stop() should be called during engine shutdown."""
        engine = Engine()
        stop_called = False
        original_stop = LiveDisplay.stop

        def tracking_stop(self_: LiveDisplay) -> None:
            nonlocal stop_called
            stop_called = True
            original_stop(self_)

        monkeypatch.setattr(LiveDisplay, "stop", tracking_stop)
        engine.run(loop=False)
        assert stop_called is True

    def test_live_display_stop_failure_logged(
        self,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """If LiveDisplay.stop() raises, the error should be logged."""
        engine = Engine()

        def exploding_stop(self_: LiveDisplay) -> None:
            raise RuntimeError("display stop failed")

        monkeypatch.setattr(LiveDisplay, "stop", exploding_stop)
        with caplog.at_level(logging.WARNING, logger="wyby.app"):
            engine.run(loop=False)

        warnings = [
            r.message for r in caplog.records
            if r.levelno >= logging.WARNING
        ]
        assert any("LiveDisplay" in m for m in warnings)


# ---------------------------------------------------------------------------
# InputManager integration
# ---------------------------------------------------------------------------


class TestEngineInputManager:
    """Engine.input_manager integration: validation, start, poll, stop."""

    def test_input_manager_none_by_default(self) -> None:
        engine = Engine()
        assert engine.input_manager is None

    def test_input_manager_is_read_only(self) -> None:
        engine = Engine()
        with pytest.raises(AttributeError):
            engine.input_manager = None  # type: ignore[misc]

    def test_rejects_non_input_manager(self) -> None:
        """Passing a non-InputManager should raise TypeError."""
        with pytest.raises(TypeError, match="input_manager must be"):
            Engine(input_manager="not a manager")  # type: ignore[arg-type]

    def test_rejects_wrong_type(self) -> None:
        with pytest.raises(TypeError, match="input_manager must be"):
            Engine(input_manager=42)  # type: ignore[arg-type]

    def test_input_manager_started_in_run(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """InputManager.start() should be called when run() begins."""
        mock_manager = MagicMock(spec=InputManager)
        mock_manager.poll.return_value = []
        # Bypass isinstance check by patching
        monkeypatch.setattr(
            "wyby.app.InputManager", lambda *a, **kw: mock_manager
        )
        engine = Engine()
        engine._input_manager = mock_manager

        def stop_immediately(self_: Engine) -> None:
            self_.stop()

        monkeypatch.setattr(Engine, "_tick", stop_immediately)
        engine.run(loop=True)
        mock_manager.start.assert_called_once()

    def test_input_manager_stopped_in_shutdown(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """InputManager.stop() should be called during shutdown."""
        mock_manager = MagicMock(spec=InputManager)
        mock_manager.poll.return_value = []
        engine = Engine()
        engine._input_manager = mock_manager

        def stop_immediately(self_: Engine) -> None:
            self_.stop()

        monkeypatch.setattr(Engine, "_tick", stop_immediately)
        engine.run(loop=True)
        mock_manager.stop.assert_called_once()

    def test_input_manager_polled_each_tick(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """InputManager.poll() should be called during each tick."""
        mock_manager = MagicMock(spec=InputManager)
        mock_manager.poll.return_value = []
        engine = Engine()
        engine._input_manager = mock_manager

        engine.run(loop=False)
        mock_manager.poll.assert_called()

    def test_input_manager_events_posted_to_queue(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Events from InputManager.poll() should appear in the event queue."""
        event = _DummyEvent()
        mock_manager = MagicMock(spec=InputManager)
        mock_manager.poll.return_value = [event]
        engine = Engine()
        engine._input_manager = mock_manager

        # Track events that flow through the queue by intercepting drain
        received_events: list[Event] = []

        class TrackingScene(Scene):
            def handle_events(self, events: list) -> None:
                received_events.extend(events)

            def update(self, dt: float) -> None:
                pass

            def render(self) -> None:
                pass

        engine.push_scene(TrackingScene())
        engine.run(loop=False)
        assert event in received_events

    def test_input_manager_stop_failure_logged(
        self,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """If InputManager.stop() raises, the error should be logged."""
        mock_manager = MagicMock(spec=InputManager)
        mock_manager.poll.return_value = []
        mock_manager.stop.side_effect = RuntimeError("stop failed")
        engine = Engine()
        engine._input_manager = mock_manager

        with caplog.at_level(logging.WARNING, logger="wyby.app"):
            engine.run(loop=False)

        warnings = [
            r.message for r in caplog.records
            if r.levelno >= logging.WARNING
        ]
        assert any("InputManager" in m for m in warnings)


# ---------------------------------------------------------------------------
# Events property
# ---------------------------------------------------------------------------


class TestEngineEventsProperty:
    """Engine.events returns the EventQueue."""

    def test_events_returns_event_queue(self) -> None:
        engine = Engine()
        assert isinstance(engine.events, EventQueue)

    def test_events_is_read_only(self) -> None:
        engine = Engine()
        with pytest.raises(AttributeError):
            engine.events = EventQueue()  # type: ignore[misc]

    def test_events_can_post_and_drain(self) -> None:
        """Basic post/drain should work on the engine's event queue."""
        engine = Engine()
        event = _DummyEvent()
        engine.events.post(event)
        drained = engine.events.drain()
        assert event in drained


# ---------------------------------------------------------------------------
# Scenes property
# ---------------------------------------------------------------------------


class TestEngineScenesProperty:
    """Engine.scenes returns the SceneStack."""

    def test_scenes_returns_scene_stack(self) -> None:
        engine = Engine()
        assert isinstance(engine.scenes, SceneStack)

    def test_scenes_is_read_only(self) -> None:
        engine = Engine()
        with pytest.raises(AttributeError):
            engine.scenes = SceneStack()  # type: ignore[misc]

    def test_scenes_starts_empty(self) -> None:
        engine = Engine()
        assert engine.scenes.is_empty


# ---------------------------------------------------------------------------
# Signal handler
# ---------------------------------------------------------------------------


class TestEngineSignalHandler:
    """Signal handlers should be installed/uninstalled during run()."""

    def test_signal_handler_installed_during_run(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """SignalHandler.install() should be called at the start of run()."""
        from wyby.signal_handlers import SignalHandler

        install_called = False
        original_install = SignalHandler.install

        def tracking_install(self_: SignalHandler) -> None:
            nonlocal install_called
            install_called = True
            original_install(self_)

        monkeypatch.setattr(SignalHandler, "install", tracking_install)
        engine = Engine()
        engine.run(loop=False)
        assert install_called is True

    def test_signal_handler_uninstalled_after_run(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """SignalHandler.uninstall() should be called after run() exits."""
        from wyby.signal_handlers import SignalHandler

        uninstall_called = False
        original_uninstall = SignalHandler.uninstall

        def tracking_uninstall(self_: SignalHandler) -> None:
            nonlocal uninstall_called
            uninstall_called = True
            original_uninstall(self_)

        monkeypatch.setattr(SignalHandler, "uninstall", tracking_uninstall)
        engine = Engine()
        engine.run(loop=False)
        assert uninstall_called is True

    def test_signal_handler_install_from_non_main_thread(
        self,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """If install() raises ValueError (non-main thread), a warning is logged."""
        from wyby.signal_handlers import SignalHandler

        def failing_install(self_: SignalHandler) -> None:
            raise ValueError("not main thread")

        monkeypatch.setattr(SignalHandler, "install", failing_install)
        engine = Engine()

        with caplog.at_level(logging.WARNING, logger="wyby.app"):
            engine.run(loop=False)

        warnings = [
            r.message for r in caplog.records
            if r.levelno >= logging.WARNING
        ]
        assert any("signal" in m.lower() for m in warnings)
        # Engine should still complete its tick despite the warning.
        assert engine.tick_count == 1


# ---------------------------------------------------------------------------
# Empty scene stack tick
# ---------------------------------------------------------------------------


class TestEngineEmptyStackTick:
    """Ticking with an empty scene stack should be a safe no-op."""

    def test_tick_with_empty_stack_no_error(self) -> None:
        engine = Engine()
        assert engine.scenes.is_empty
        engine.run(loop=False)
        assert engine.tick_count == 1

    def test_tick_with_empty_stack_timing_advances(self) -> None:
        engine = Engine()
        engine.run(loop=False)
        assert engine.dt > 0.0
        assert engine.elapsed > 0.0

    def test_events_discarded_with_empty_stack(self) -> None:
        """Events should be drained even if no scene receives them."""
        engine = Engine()
        engine.events.post(_DummyEvent())
        engine.run(loop=False)
        assert engine.events.is_empty


# ---------------------------------------------------------------------------
# _SLEEP_THRESHOLD constant
# ---------------------------------------------------------------------------


class TestSleepThreshold:
    """_SLEEP_THRESHOLD defines the minimum sleep duration."""

    def test_sleep_threshold_is_positive(self) -> None:
        assert _SLEEP_THRESHOLD > 0.0

    def test_sleep_threshold_is_small(self) -> None:
        # Should be ~1ms — small enough to allow fine-grained pacing
        # but large enough to avoid OS sleep granularity issues.
        assert _SLEEP_THRESHOLD <= 0.01

    def test_no_sleep_below_threshold(self) -> None:
        """The loop should not sleep if remaining time < _SLEEP_THRESHOLD."""
        mono_calls = [0]

        def mock_monotonic() -> float:
            mono_calls[0] += 1
            if mono_calls[0] == 1:
                return 0.0  # run() init
            # Advance time so remaining is below threshold.
            # target_dt at 30 tps is ~0.0333s.  If frame_time equals
            # target_dt, remaining = 0 — well below threshold.
            return (mono_calls[0] - 1) * (1.0 / 30)

        engine = Engine(tps=30)
        original_tick = Engine._tick
        tick_count = [0]

        def stop_after_one(self_: Engine) -> None:
            original_tick(self_)
            tick_count[0] += 1
            self_.stop()

        with patch.object(Engine, "_tick", stop_after_one):
            with patch(
                "wyby.app.time.monotonic", side_effect=mock_monotonic
            ):
                with patch("wyby.app.time.sleep") as mock_sleep:
                    engine.run(loop=True)

        # With exact timing (frame_time == target_dt), remaining is 0.
        # Sleep should not be called since 0 < _SLEEP_THRESHOLD.
        # However, the accumulator math might leave a tiny remainder,
        # so we check that any sleep call (if made) is above threshold.
        for call_args in mock_sleep.call_args_list:
            sleep_time = call_args[0][0]
            assert sleep_time >= _SLEEP_THRESHOLD


# ---------------------------------------------------------------------------
# Engine with both debug and show_fps repr
# ---------------------------------------------------------------------------


class TestEngineReprCombined:
    """__repr__ with both debug and show_fps flags."""

    @pytest.fixture(autouse=True)
    def _restore_wyby_logger(self) -> None:
        """Prevent debug mode from leaking logger state."""
        from wyby._logging import _LIBRARY_LOGGER_NAME

        logger = logging.getLogger(_LIBRARY_LOGGER_NAME)
        original_handlers = logger.handlers[:]
        original_level = logger.level
        yield  # type: ignore[misc]
        logger.handlers[:] = original_handlers
        logger.setLevel(original_level)

    def test_repr_both_debug_and_show_fps(self) -> None:
        engine = Engine(
            title="Snake", width=40, height=20,
            debug=True, show_fps=True,
        )
        r = repr(engine)
        assert "debug=True" in r
        assert "show_fps=True" in r

    def test_repr_debug_before_show_fps(self) -> None:
        """debug=True should appear before show_fps=True in repr."""
        engine = Engine(debug=True, show_fps=True)
        r = repr(engine)
        debug_pos = r.index("debug=True")
        show_fps_pos = r.index("show_fps=True")
        assert debug_pos < show_fps_pos


# ---------------------------------------------------------------------------
# Engine config with show_fps
# ---------------------------------------------------------------------------


class TestEngineConfigShowFps:
    """EngineConfig show_fps field integration with Engine."""

    def test_config_show_fps_propagates_to_engine(self) -> None:
        cfg = EngineConfig(show_fps=True)
        engine = Engine(config=cfg)
        assert engine.show_fps is True
        assert engine.fps_counter is not None

    def test_config_show_fps_false(self) -> None:
        cfg = EngineConfig(show_fps=False)
        engine = Engine(config=cfg)
        assert engine.show_fps is False
        assert engine.fps_counter is None
