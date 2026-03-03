"""Tests for the Engine main loop structure: input-update-render.

These tests verify that Engine._tick() correctly executes the three
phases (drain events, update active scene, render active scene) and
that the Engine exposes its EventQueue and SceneStack.
"""

from __future__ import annotations

import pytest

from wyby.app import Engine, QuitSignal
from wyby.event import Event, EventQueue
from wyby.scene import Scene, SceneStack


# ---------------------------------------------------------------------------
# Concrete Scene for testing
# ---------------------------------------------------------------------------


class StubScene(Scene):
    """Minimal concrete Scene that records calls for assertions."""

    def __init__(self) -> None:
        super().__init__()
        self.update_calls: list[float] = []
        self.render_calls: int = 0

    def update(self, dt: float) -> None:
        self.update_calls.append(dt)

    def render(self) -> None:
        self.render_calls += 1


# ---------------------------------------------------------------------------
# Engine owns EventQueue and SceneStack
# ---------------------------------------------------------------------------


class TestEngineOwnsSubsystems:
    """Engine should create and expose an EventQueue and SceneStack."""

    def test_events_property_returns_event_queue(self) -> None:
        engine = Engine()
        assert isinstance(engine.events, EventQueue)

    def test_scenes_property_returns_scene_stack(self) -> None:
        engine = Engine()
        assert isinstance(engine.scenes, SceneStack)

    def test_events_is_same_instance_across_accesses(self) -> None:
        engine = Engine()
        assert engine.events is engine.events

    def test_scenes_is_same_instance_across_accesses(self) -> None:
        engine = Engine()
        assert engine.scenes is engine.scenes

    def test_events_is_read_only(self) -> None:
        engine = Engine()
        with pytest.raises(AttributeError):
            engine.events = EventQueue()  # type: ignore[misc]

    def test_scenes_is_read_only(self) -> None:
        engine = Engine()
        with pytest.raises(AttributeError):
            engine.scenes = SceneStack()  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Tick calls scene update and render
# ---------------------------------------------------------------------------


class TestTickCallsScene:
    """_tick() should call update(dt) and render() on the active scene."""

    def test_update_called_with_target_dt(self) -> None:
        engine = Engine(tps=30)
        scene = StubScene()
        engine.scenes.push(scene)
        engine.run(loop=False)
        assert len(scene.update_calls) == 1
        assert scene.update_calls[0] == pytest.approx(1.0 / 30)

    def test_render_called_once_per_tick(self) -> None:
        engine = Engine()
        scene = StubScene()
        engine.scenes.push(scene)
        engine.run(loop=False)
        assert scene.render_calls == 1

    def test_update_called_before_render(self) -> None:
        """update() must execute before render() each tick."""
        engine = Engine()
        call_order: list[str] = []

        class OrderTrackingScene(Scene):
            def update(self, dt: float) -> None:
                call_order.append("update")

            def render(self) -> None:
                call_order.append("render")

        scene = OrderTrackingScene()
        engine.scenes.push(scene)
        engine.run(loop=False)
        assert call_order == ["update", "render"]

    def test_multiple_ticks_call_scene_each_time(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        engine = Engine(tps=30)
        scene = StubScene()
        engine.scenes.push(scene)

        original_tick = Engine._tick
        tick_count = [0]

        def counting_tick(self_: Engine) -> None:
            original_tick(self_)
            tick_count[0] += 1
            if tick_count[0] >= 3:
                self_.stop()

        monkeypatch.setattr(Engine, "_tick", counting_tick)
        engine.run(loop=True)

        assert len(scene.update_calls) == 3
        assert scene.render_calls == 3


# ---------------------------------------------------------------------------
# Empty scene stack
# ---------------------------------------------------------------------------


class TestTickEmptyStack:
    """Tick should be a no-op (no crash) when the scene stack is empty."""

    def test_single_tick_no_scene(self) -> None:
        engine = Engine()
        # No scene pushed — should not raise.
        engine.run(loop=False)
        assert engine.tick_count == 1

    def test_timing_still_advances_with_empty_stack(self) -> None:
        engine = Engine(tps=30)
        engine.run(loop=False)
        assert engine.dt == pytest.approx(1.0 / 30)
        assert engine.elapsed == pytest.approx(1.0 / 30)
        assert engine.tick_count == 1


# ---------------------------------------------------------------------------
# Event queue draining
# ---------------------------------------------------------------------------


class TestTickDrainsEvents:
    """The input phase should drain the event queue each tick."""

    def test_events_drained_during_tick(self) -> None:
        engine = Engine()
        evt = Event()
        engine.events.post(evt)
        assert len(engine.events) == 1
        engine.run(loop=False)
        assert engine.events.is_empty

    def test_multiple_events_drained(self) -> None:
        engine = Engine()
        for _ in range(5):
            engine.events.post(Event())
        assert len(engine.events) == 5
        engine.run(loop=False)
        assert engine.events.is_empty

    def test_events_drained_before_update(self) -> None:
        """Events should be drained before scene.update() is called."""
        engine = Engine()
        queue_len_during_update: list[int] = []

        class SpyScene(Scene):
            def update(self_, dt: float) -> None:
                queue_len_during_update.append(len(engine.events))

            def render(self_) -> None:
                pass

        engine.events.post(Event())
        engine.scenes.push(SpyScene())
        engine.run(loop=False)
        # The queue should have been drained before update() was called.
        assert queue_len_during_update == [0]

    def test_events_posted_during_update_survive(self) -> None:
        """Events posted during update() should not be drained this tick."""
        engine = Engine()

        class PostingScene(Scene):
            def update(self_, dt: float) -> None:
                engine.events.post(Event())

            def render(self_) -> None:
                pass

        engine.scenes.push(PostingScene())
        engine.run(loop=False)
        # The event posted during update() should still be in the queue.
        assert len(engine.events) == 1


# ---------------------------------------------------------------------------
# QuitSignal from scene update
# ---------------------------------------------------------------------------


class TestQuitSignalFromScene:
    """QuitSignal raised in scene.update() should stop the engine cleanly."""

    def test_quit_signal_from_update(self) -> None:
        engine = Engine()

        class QuittingScene(Scene):
            def update(self, dt: float) -> None:
                raise QuitSignal("done")

            def render(self) -> None:
                pass

        engine.scenes.push(QuittingScene())
        engine.run(loop=True)
        assert engine.running is False

    def test_quit_signal_prevents_render(self) -> None:
        """If update() raises QuitSignal, render() should not be called."""
        engine = Engine()
        render_called = [False]

        class QuittingScene(Scene):
            def update(self, dt: float) -> None:
                raise QuitSignal()

            def render(self) -> None:
                render_called[0] = True

        engine.scenes.push(QuittingScene())
        engine.run(loop=False)
        # QuitSignal propagates up from _tick, so render is skipped.
        assert render_called[0] is False


# ---------------------------------------------------------------------------
# Scene stack interaction during tick
# ---------------------------------------------------------------------------


class TestSceneStackDuringTick:
    """Scene stack mutations during update() take effect next tick."""

    def test_push_during_update_renders_original(self) -> None:
        """If update() pushes a new scene, the original scene still renders."""
        engine = Engine()
        rendered_scenes: list[str] = []

        class SceneA(Scene):
            def __init__(self_) -> None:
                super().__init__()
                self_.pushed = False

            def update(self_, dt: float) -> None:
                if not self_.pushed:
                    self_.pushed = True
                    engine.scenes.push(SceneB())

            def render(self_) -> None:
                rendered_scenes.append("A")

        class SceneB(Scene):
            def update(self_, dt: float) -> None:
                engine.stop()

            def render(self_) -> None:
                rendered_scenes.append("B")

        engine.scenes.push(SceneA())
        engine.run(loop=False)
        # SceneA was the active scene when tick started, so it renders.
        assert rendered_scenes == ["A"]

    def test_new_scene_active_next_tick(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A scene pushed during update() becomes active on the next tick."""
        engine = Engine()
        updated_scenes: list[str] = []

        class SceneA(Scene):
            def __init__(self_) -> None:
                super().__init__()
                self_.pushed = False

            def update(self_, dt: float) -> None:
                updated_scenes.append("A")
                if not self_.pushed:
                    self_.pushed = True
                    engine.scenes.push(SceneB())

            def render(self_) -> None:
                pass

        class SceneB(Scene):
            def update(self_, dt: float) -> None:
                updated_scenes.append("B")
                engine.stop()

            def render(self_) -> None:
                pass

        engine.scenes.push(SceneA())

        original_tick = Engine._tick
        tick_count = [0]

        def counting_tick(self_: Engine) -> None:
            original_tick(self_)
            tick_count[0] += 1
            if tick_count[0] >= 3:
                self_.stop()

        monkeypatch.setattr(Engine, "_tick", counting_tick)
        engine.run(loop=True)

        # First tick: SceneA updates (and pushes SceneB).
        # Second tick: SceneB updates (and stops).
        assert updated_scenes == ["A", "B"]


# ---------------------------------------------------------------------------
# Only top scene is updated/rendered
# ---------------------------------------------------------------------------


class TestOnlyTopSceneActive:
    """Only the top scene on the stack should receive update/render."""

    def test_bottom_scene_not_updated(self) -> None:
        engine = Engine()
        bottom = StubScene()
        top = StubScene()
        engine.scenes.push(bottom)
        engine.scenes.push(top)
        engine.run(loop=False)
        assert len(bottom.update_calls) == 0
        assert bottom.render_calls == 0

    def test_top_scene_updated_and_rendered(self) -> None:
        engine = Engine()
        bottom = StubScene()
        top = StubScene()
        engine.scenes.push(bottom)
        engine.scenes.push(top)
        engine.run(loop=False)
        assert len(top.update_calls) == 1
        assert top.render_calls == 1
