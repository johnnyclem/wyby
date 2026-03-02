"""Tests for the Entity and Component system."""

import pytest

from runetui.components import Component, Position, Velocity
from runetui.entity import Entity


class TestPosition:
    def test_defaults(self):
        pos = Position()
        assert pos.x == 0.0
        assert pos.y == 0.0

    def test_custom(self):
        pos = Position(x=5.0, y=10.0)
        assert pos.x == 5.0
        assert pos.y == 10.0


class TestVelocity:
    def test_defaults(self):
        vel = Velocity()
        assert vel.vx == 0.0
        assert vel.vy == 0.0


class TestEntity:
    def test_creation(self):
        e = Entity(x=3.0, y=4.0)
        assert e.position.x == 3.0
        assert e.position.y == 4.0
        assert e.alive is True

    def test_unique_ids(self):
        e1 = Entity()
        e2 = Entity()
        assert e1.id != e2.id

    def test_add_component(self):
        e = Entity()
        vel = Velocity(vx=1.0, vy=2.0)
        e.add_component(vel)
        assert e.get_component(Velocity) is vel

    def test_remove_component(self):
        e = Entity()
        vel = Velocity(vx=1.0)
        e.add_component(vel)
        removed = e.remove_component(Velocity)
        assert removed is vel
        assert e.get_component(Velocity) is None

    def test_has_component(self):
        e = Entity()
        assert e.has_component(Position) is True
        assert e.has_component(Velocity) is False

    def test_update_applies_velocity(self):
        e = Entity(x=0.0, y=0.0)
        e.add_component(Velocity(vx=10.0, vy=5.0))
        e.update(0.1)
        assert abs(e.position.x - 1.0) < 0.001
        assert abs(e.position.y - 0.5) < 0.001

    def test_update_without_velocity(self):
        e = Entity(x=5.0, y=5.0)
        e.update(0.1)
        assert e.position.x == 5.0
        assert e.position.y == 5.0

    def test_destroy(self):
        e = Entity()
        assert e.alive is True
        e.destroy()
        assert e.alive is False

    def test_replace_component(self):
        e = Entity()
        e.add_component(Position(x=1.0, y=1.0))
        e.add_component(Position(x=9.0, y=9.0))
        assert e.position.x == 9.0
