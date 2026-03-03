"""Tests for graceful shutdown on exceptions.

The engine's _shutdown() method tears down the scene stack (firing
on_exit hooks) and flushes the event queue whenever run() exits —
whether via stop(), KeyboardInterrupt, QuitSignal, or an unhandled
exception from game code.
"""

from __future__ import annotations

import logging

import pytest

from wyby.app import Engine, QuitSignal
from wyby.event import Event
from wyby.scene import Scene


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class DummyScene(Scene):
    """Minimal scene that tracks lifecycle hook calls."""

    def __init__(self) -> None:
        super().__init__()
        self.entered = False
        self.exited = False
        self.update_count = 0

    def update(self, dt: float) -> None:
        self.update_count += 1

    def render(self) -> None:
        pass

    def on_enter(self) -> None:
        self.entered = True

    def on_exit(self) -> None:
        self.exited = True


class ExplodingExitScene(Scene):
    """Scene whose on_exit() raises an exception."""

    def __init__(self) -> None:
        super().__init__()
        self.exited_called = False

    def update(self, dt: float) -> None:
        pass

    def render(self) -> None:
        pass

    def on_exit(self) -> None:
        self.exited_called = True
        raise RuntimeError("exit hook exploded")


class CrashingScene(Scene):
    """Scene whose update() raises an unhandled exception."""

    def update(self, dt: float) -> None:
        raise ValueError("game logic bug")

    def render(self) -> None:
        pass


class DummyEvent(Event):
    """Minimal event for testing queue state."""


# ---------------------------------------------------------------------------
# Scene exit hooks fire on normal stop
# ---------------------------------------------------------------------------


class TestShutdownOnStop:
    """Scenes should receive on_exit during shutdown via stop()."""

    def test_single_scene_gets_exit_hook(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        engine = Engine()
        scene = DummyScene()
        engine.scenes.push(scene)

        call_count = 0
        original_tick = Engine._tick

        def tick_then_stop(self_: Engine) -> None:
            nonlocal call_count
            original_tick(self_)
            call_count += 1
            if call_count >= 1:
                self_.stop()

        monkeypatch.setattr(Engine, "_tick", tick_then_stop)
        engine.run(loop=True)

        assert scene.exited is True

    def test_multiple_scenes_all_get_exit_hooks(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        engine = Engine()
        scenes = [DummyScene(), DummyScene(), DummyScene()]
        for s in scenes:
            engine.scenes.push(s)

        def stop_immediately(self_: Engine) -> None:
            self_.stop()

        monkeypatch.setattr(Engine, "_tick", stop_immediately)
        engine.run(loop=True)

        for i, s in enumerate(scenes):
            assert s.exited is True, f"scene[{i}] did not receive on_exit"

    def test_exit_hooks_fire_top_to_bottom(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        engine = Engine()
        exit_order: list[str] = []

        class TrackedScene(Scene):
            def __init__(self, name: str) -> None:
                super().__init__()
                self.name = name

            def update(self, dt: float) -> None:
                pass

            def render(self) -> None:
                pass

            def on_exit(self) -> None:
                exit_order.append(self.name)

        engine.scenes.push(TrackedScene("bottom"))
        engine.scenes.push(TrackedScene("middle"))
        engine.scenes.push(TrackedScene("top"))

        def stop_immediately(self_: Engine) -> None:
            self_.stop()

        monkeypatch.setattr(Engine, "_tick", stop_immediately)
        engine.run(loop=True)

        assert exit_order == ["top", "middle", "bottom"]


# ---------------------------------------------------------------------------
# Scene exit hooks fire on KeyboardInterrupt
# ---------------------------------------------------------------------------


class TestShutdownOnKeyboardInterrupt:
    """Scenes should be cleaned up when Ctrl+C is pressed."""

    def test_scene_gets_exit_on_interrupt(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        engine = Engine()
        scene = DummyScene()
        engine.scenes.push(scene)

        def raise_interrupt(self_: Engine) -> None:
            raise KeyboardInterrupt

        monkeypatch.setattr(Engine, "_tick", raise_interrupt)
        engine.run(loop=True)

        assert scene.exited is True

    def test_scene_stack_empty_after_interrupt(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        engine = Engine()
        engine.scenes.push(DummyScene())
        engine.scenes.push(DummyScene())

        def raise_interrupt(self_: Engine) -> None:
            raise KeyboardInterrupt

        monkeypatch.setattr(Engine, "_tick", raise_interrupt)
        engine.run(loop=True)

        assert engine.scenes.is_empty


# ---------------------------------------------------------------------------
# Scene exit hooks fire on QuitSignal
# ---------------------------------------------------------------------------


class TestShutdownOnQuitSignal:
    """Scenes should be cleaned up when QuitSignal is raised."""

    def test_scene_gets_exit_on_quit_signal(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        engine = Engine()
        scene = DummyScene()
        engine.scenes.push(scene)

        def raise_quit(self_: Engine) -> None:
            raise QuitSignal("done")

        monkeypatch.setattr(Engine, "_tick", raise_quit)
        engine.run(loop=True)

        assert scene.exited is True


# ---------------------------------------------------------------------------
# Scene exit hooks fire on unhandled exceptions
# ---------------------------------------------------------------------------


class TestShutdownOnUnhandledException:
    """Unhandled exceptions should trigger cleanup and then re-raise."""

    def test_scene_gets_exit_on_game_exception(self) -> None:
        engine = Engine()
        scene = DummyScene()
        engine.scenes.push(scene)
        engine.scenes.push(CrashingScene())

        with pytest.raises(ValueError, match="game logic bug"):
            engine.run(loop=False)

        assert scene.exited is True

    def test_exception_propagates_after_cleanup(self) -> None:
        engine = Engine()
        engine.scenes.push(CrashingScene())

        with pytest.raises(ValueError, match="game logic bug"):
            engine.run(loop=False)

    def test_running_is_false_after_exception(self) -> None:
        engine = Engine()
        engine.scenes.push(CrashingScene())

        with pytest.raises(ValueError):
            engine.run(loop=False)

        assert engine.running is False

    def test_scene_stack_empty_after_exception(self) -> None:
        engine = Engine()
        engine.scenes.push(DummyScene())
        engine.scenes.push(CrashingScene())

        with pytest.raises(ValueError):
            engine.run(loop=False)

        assert engine.scenes.is_empty

    def test_multiple_scenes_cleaned_on_exception(self) -> None:
        engine = Engine()
        scenes = [DummyScene(), DummyScene()]
        for s in scenes:
            engine.scenes.push(s)
        engine.scenes.push(CrashingScene())

        with pytest.raises(ValueError):
            engine.run(loop=False)

        for i, s in enumerate(scenes):
            assert s.exited is True, f"scene[{i}] not cleaned up"


# ---------------------------------------------------------------------------
# Defensive cleanup: exception in exit hook
# ---------------------------------------------------------------------------


class TestShutdownWithBuggyExitHook:
    """A buggy exit hook should not prevent other scenes from cleaning up."""

    def test_remaining_scenes_cleaned_after_exit_hook_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        engine = Engine()
        bottom = DummyScene()
        engine.scenes.push(bottom)
        engine.scenes.push(ExplodingExitScene())  # middle — will explode
        top = DummyScene()
        engine.scenes.push(top)

        def stop_immediately(self_: Engine) -> None:
            self_.stop()

        monkeypatch.setattr(Engine, "_tick", stop_immediately)
        engine.run(loop=True)

        assert top.exited is True
        assert bottom.exited is True

    def test_buggy_exit_hook_logs_warning(
        self,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        engine = Engine()
        engine.scenes.push(DummyScene())
        engine.scenes.push(ExplodingExitScene())

        def stop_immediately(self_: Engine) -> None:
            self_.stop()

        monkeypatch.setattr(Engine, "_tick", stop_immediately)
        with caplog.at_level(logging.WARNING, logger="wyby.app"):
            engine.run(loop=True)

        warning_msgs = [
            r.message for r in caplog.records if r.levelno >= logging.WARNING
        ]
        assert any("exit hook" in m.lower() for m in warning_msgs)

    def test_scene_stack_empty_despite_exit_hook_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        engine = Engine()
        engine.scenes.push(DummyScene())
        engine.scenes.push(ExplodingExitScene())
        engine.scenes.push(DummyScene())

        def stop_immediately(self_: Engine) -> None:
            self_.stop()

        monkeypatch.setattr(Engine, "_tick", stop_immediately)
        engine.run(loop=True)

        assert engine.scenes.is_empty

    def test_exploding_exit_called(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify the exploding scene's on_exit was actually called."""
        engine = Engine()
        exploding = ExplodingExitScene()
        engine.scenes.push(exploding)

        def stop_immediately(self_: Engine) -> None:
            self_.stop()

        monkeypatch.setattr(Engine, "_tick", stop_immediately)
        engine.run(loop=True)

        assert exploding.exited_called is True


# ---------------------------------------------------------------------------
# Event queue is flushed on shutdown
# ---------------------------------------------------------------------------


class TestShutdownClearsEventQueue:
    """The event queue should be empty after shutdown."""

    def test_events_cleared_on_normal_stop(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        engine = Engine()

        def post_then_stop(self_: Engine) -> None:
            self_.events.post(DummyEvent())
            self_.events.post(DummyEvent())
            self_.stop()

        monkeypatch.setattr(Engine, "_tick", post_then_stop)
        engine.run(loop=True)

        assert engine.events.is_empty

    def test_events_cleared_on_exception(self) -> None:
        engine = Engine()
        engine.events.post(DummyEvent())
        engine.scenes.push(CrashingScene())

        with pytest.raises(ValueError):
            engine.run(loop=False)

        assert engine.events.is_empty

    def test_events_cleared_on_quit_signal(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        engine = Engine()
        engine.events.post(DummyEvent())

        def raise_quit(self_: Engine) -> None:
            raise QuitSignal()

        monkeypatch.setattr(Engine, "_tick", raise_quit)
        engine.run(loop=True)

        assert engine.events.is_empty


# ---------------------------------------------------------------------------
# Shutdown with empty scene stack
# ---------------------------------------------------------------------------


class TestShutdownEmptyStack:
    """Shutdown with no scenes should be a clean no-op."""

    def test_empty_stack_no_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        engine = Engine()
        assert engine.scenes.is_empty

        def stop_immediately(self_: Engine) -> None:
            self_.stop()

        monkeypatch.setattr(Engine, "_tick", stop_immediately)
        engine.run(loop=True)

        assert engine.running is False

    def test_empty_stack_on_exception(self) -> None:
        engine = Engine()

        def raise_error(self_: Engine) -> None:
            raise RuntimeError("boom")

        # Monkeypatch _tick to raise without scenes
        Engine_tick_original = Engine._tick
        try:
            Engine._tick = raise_error  # type: ignore[assignment]
            with pytest.raises(RuntimeError, match="boom"):
                engine.run(loop=False)
        finally:
            Engine._tick = Engine_tick_original  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Shutdown is idempotent
# ---------------------------------------------------------------------------


class TestShutdownIdempotent:
    """Calling _shutdown() multiple times should be safe."""

    def test_double_shutdown_no_error(self) -> None:
        engine = Engine()
        scene = DummyScene()
        engine.scenes.push(scene)

        engine._shutdown()
        assert scene.exited is True

        # Second call — stack and queue already empty, should be a no-op.
        engine._shutdown()
        assert engine.scenes.is_empty


# ---------------------------------------------------------------------------
# Exit callback hooks also fire during shutdown
# ---------------------------------------------------------------------------


class TestShutdownFiresCallbackHooks:
    """Registered exit callbacks should fire during shutdown."""

    def test_exit_callback_fires(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        engine = Engine()
        scene = DummyScene()
        callback_called = False

        def my_callback() -> None:
            nonlocal callback_called
            callback_called = True

        scene.add_exit_hook(my_callback)
        engine.scenes.push(scene)

        def stop_immediately(self_: Engine) -> None:
            self_.stop()

        monkeypatch.setattr(Engine, "_tick", stop_immediately)
        engine.run(loop=True)

        assert callback_called is True


# ---------------------------------------------------------------------------
# Shutdown logging
# ---------------------------------------------------------------------------


class TestShutdownLogging:
    """Shutdown should emit appropriate log messages."""

    def test_shutdown_logs_cleanup_start(
        self,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        engine = Engine()

        def stop_immediately(self_: Engine) -> None:
            self_.stop()

        monkeypatch.setattr(Engine, "_tick", stop_immediately)
        with caplog.at_level(logging.DEBUG, logger="wyby.app"):
            engine.run(loop=True)

        messages = [r.message for r in caplog.records]
        assert any("shutdown" in m.lower() for m in messages)

    def test_shutdown_logs_completion(
        self,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        engine = Engine()

        def stop_immediately(self_: Engine) -> None:
            self_.stop()

        monkeypatch.setattr(Engine, "_tick", stop_immediately)
        with caplog.at_level(logging.DEBUG, logger="wyby.app"):
            engine.run(loop=True)

        messages = [r.message for r in caplog.records]
        assert any("shutdown complete" in m.lower() for m in messages)


# ---------------------------------------------------------------------------
# Single-tick mode also gets graceful shutdown
# ---------------------------------------------------------------------------


class TestShutdownSingleTickMode:
    """loop=False should also trigger graceful shutdown."""

    def test_scene_exit_fires_in_single_tick(self) -> None:
        engine = Engine()
        scene = DummyScene()
        engine.scenes.push(scene)

        engine.run(loop=False)

        assert scene.exited is True

    def test_scene_stack_empty_after_single_tick(self) -> None:
        engine = Engine()
        engine.scenes.push(DummyScene())

        engine.run(loop=False)

        assert engine.scenes.is_empty
