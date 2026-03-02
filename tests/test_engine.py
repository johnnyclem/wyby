"""Tests for the Engine class and EngineConfig."""

import pytest

from runetui.engine import Engine, EngineConfig
from runetui.events import Event, EventType, KeyEvent
from runetui.renderer import Renderer
from runetui.scene import Scene


class StubScene(Scene):
    """Minimal scene for testing."""

    def __init__(self):
        super().__init__()
        self.events_received = []
        self.update_count = 0
        self.render_count = 0
        self.entered = False
        self.exited = False

    def on_enter(self):
        self.entered = True

    def on_exit(self):
        self.exited = True

    def handle_event(self, event):
        self.events_received.append(event)

    def update(self, dt):
        self.update_count += 1

    def render(self, renderer):
        self.render_count += 1


class TestEngineConfig:
    def test_defaults(self):
        config = EngineConfig()
        assert config.title == "RuneTUI Game"
        assert config.width == 80
        assert config.height == 24
        assert config.target_fps == 30
        assert config.debug is False
        assert "ESCAPE" in config.quit_keys

    def test_custom_values(self):
        config = EngineConfig(title="Test", width=40, height=12, debug=True)
        assert config.title == "Test"
        assert config.width == 40
        assert config.height == 12
        assert config.debug is True


class TestEngine:
    def test_init(self):
        engine = Engine(EngineConfig(width=40, height=12))
        assert engine.config.width == 40
        assert engine.config.height == 12
        assert engine.current_scene is None

    def test_push_scene(self):
        engine = Engine()
        scene = StubScene()
        engine.push_scene(scene)
        assert engine.current_scene is scene
        assert scene.entered is True
        assert scene.engine is engine

    def test_pop_scene(self):
        engine = Engine()
        scene1 = StubScene()
        scene2 = StubScene()
        engine.push_scene(scene1)
        engine.push_scene(scene2)

        assert scene1.exited is True  # exited when scene2 was pushed
        scene1.exited = False  # reset

        popped = engine.pop_scene()
        assert popped is scene2
        assert scene2.exited is True
        assert engine.current_scene is scene1
        assert scene1.entered is True  # re-entered

    def test_replace_scene(self):
        engine = Engine()
        scene1 = StubScene()
        scene2 = StubScene()
        engine.push_scene(scene1)
        engine.replace_scene(scene2)

        assert scene1.exited is True
        assert scene2.entered is True
        assert engine.current_scene is scene2

    def test_pop_empty_stack(self):
        engine = Engine()
        result = engine.pop_scene()
        assert result is None

    def test_run_without_scenes_does_not_crash(self):
        engine = Engine()
        engine.run()  # should return immediately

    def test_stop(self):
        engine = Engine()
        engine._running = True
        engine.stop()
        assert engine._running is False

    def test_process_quit_event(self):
        engine = Engine()
        scene = StubScene()
        engine.push_scene(scene)
        engine._running = True
        engine.event_queue.push(Event(event_type=EventType.QUIT))
        engine._process_events()
        assert engine._running is False

    def test_process_quit_key(self):
        engine = Engine()
        scene = StubScene()
        engine.push_scene(scene)
        engine._running = True
        engine.event_queue.push(KeyEvent(key="ESCAPE"))
        engine._process_events()
        assert engine._running is False

    def test_events_routed_to_scene(self):
        engine = Engine()
        scene = StubScene()
        engine.push_scene(scene)
        engine._running = True
        event = KeyEvent(key="a")
        engine.event_queue.push(event)
        engine._process_events()
        assert len(scene.events_received) == 1
        assert scene.events_received[0].key == "a"
