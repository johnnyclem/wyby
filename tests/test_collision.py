"""Tests for collision detection."""

import pytest

from runetui.collision import AABB, apply_velocity, check_aabb_collision
from runetui.components import Position, Velocity
from runetui.entity import Entity


class TestAABB:
    def test_properties(self):
        box = AABB(x=1, y=2, width=3, height=4)
        assert box.right == 4
        assert box.bottom == 6

    def test_overlaps(self):
        a = AABB(0, 0, 2, 2)
        b = AABB(1, 1, 2, 2)
        assert a.overlaps(b) is True

    def test_no_overlap(self):
        a = AABB(0, 0, 1, 1)
        b = AABB(5, 5, 1, 1)
        assert a.overlaps(b) is False

    def test_edge_touching_no_overlap(self):
        a = AABB(0, 0, 1, 1)
        b = AABB(1, 0, 1, 1)
        assert a.overlaps(b) is False  # edges touching = no overlap

    def test_from_entity(self):
        e = Entity(x=5.0, y=3.0)
        box = AABB.from_entity(e, 2.0, 2.0)
        assert box.x == 5.0
        assert box.y == 3.0
        assert box.width == 2.0


class TestCheckCollision:
    def test_colliding_entities(self):
        a = Entity(x=0, y=0)
        b = Entity(x=0.5, y=0.5)
        assert check_aabb_collision(a, b) is True

    def test_non_colliding_entities(self):
        a = Entity(x=0, y=0)
        b = Entity(x=10, y=10)
        assert check_aabb_collision(a, b) is False


class TestApplyVelocity:
    def test_basic_movement(self):
        e = Entity(x=0, y=0)
        e.add_component(Velocity(vx=10, vy=5))
        apply_velocity(e, dt=0.1)
        assert abs(e.position.x - 1.0) < 0.001
        assert abs(e.position.y - 0.5) < 0.001

    def test_gravity(self):
        e = Entity(x=0, y=0)
        e.add_component(Velocity(vx=0, vy=0))
        apply_velocity(e, dt=1.0, gravity=10.0)
        vel = e.get_component(Velocity)
        assert vel.vy == 10.0

    def test_friction(self):
        e = Entity(x=0, y=0)
        e.add_component(Velocity(vx=10, vy=0))
        apply_velocity(e, dt=1.0, friction=0.5)
        vel = e.get_component(Velocity)
        assert vel.vx == 5.0  # 10 * (1 - 0.5 * 1.0)
