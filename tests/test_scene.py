"""Tests for Scene management."""

import pytest

from runetui.components import Position
from runetui.entity import Entity
from runetui.events import Event, EventType, KeyEvent
from runetui.renderer import Renderer
from runetui.scene import Scene


class ConcreteScene(Scene):
    def __init__(self):
        super().__init__()
        self.handled_events = []
        self.updated = False

    def handle_event(self, event):
        self.handled_events.append(event)

    def update(self, dt):
        self.updated = True

    def render(self, renderer):
        renderer.draw_text(0, 0, "scene")


class TestScene:
    def test_add_entity(self):
        scene = ConcreteScene()
        e = Entity(x=1, y=2)
        scene.add_entity(e)
        assert e in scene.entities

    def test_remove_dead_entities(self):
        scene = ConcreteScene()
        e1 = Entity()
        e2 = Entity()
        scene.add_entity(e1)
        scene.add_entity(e2)
        e1.destroy()
        scene.remove_dead_entities()
        assert e1 not in scene.entities
        assert e2 in scene.entities

    def test_get_entities_with(self):
        scene = ConcreteScene()
        e = Entity(x=0, y=0)
        scene.add_entity(e)
        result = scene.get_entities_with(Position)
        assert e in result

    def test_lifecycle_hooks(self):
        scene = ConcreteScene()
        # Default implementations should not raise
        scene.on_enter()
        scene.on_exit()
        scene.on_resize(80, 24)
