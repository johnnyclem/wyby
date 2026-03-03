"""Tests for wyby.physics — batch velocity update and position sync helpers."""

from __future__ import annotations

import math

import pytest

from wyby.entity import Entity
from wyby.physics import sync_positions, update_velocities
from wyby.position import Position
from wyby.velocity import Velocity


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_entity(
    x: float,
    y: float,
    vx: float,
    vy: float,
    *,
    entity_id: int,
) -> Entity:
    """Create an Entity with Position and Velocity components."""
    e = Entity(int(x), int(y), entity_id=entity_id)
    e.add_component(Position(x, y))
    e.add_component(Velocity(vx, vy))
    return e


# ---------------------------------------------------------------------------
# update_velocities
# ---------------------------------------------------------------------------


class TestUpdateVelocities:
    """Batch velocity application across entities."""

    def test_single_entity(self) -> None:
        e = _make_entity(0.0, 0.0, 10.0, 5.0, entity_id=1000)
        count = update_velocities([e], 0.1)
        pos = e.get_component(Position)
        assert pos.x == pytest.approx(1.0)
        assert pos.y == pytest.approx(0.5)
        assert count == 1

    def test_multiple_entities(self) -> None:
        a = _make_entity(0.0, 0.0, 10.0, 0.0, entity_id=1001)
        b = _make_entity(5.0, 5.0, 0.0, -3.0, entity_id=1002)
        count = update_velocities([a, b], 1.0)

        pos_a = a.get_component(Position)
        pos_b = b.get_component(Position)
        assert pos_a.x == pytest.approx(10.0)
        assert pos_b.y == pytest.approx(2.0)
        assert count == 2

    def test_skips_entity_without_velocity(self) -> None:
        e = Entity(0, 0, entity_id=1003)
        e.add_component(Position(0.0, 0.0))
        count = update_velocities([e], 1.0)

        pos = e.get_component(Position)
        assert pos.x == 0.0
        assert pos.y == 0.0
        assert count == 0

    def test_skips_entity_without_position(self) -> None:
        e = Entity(0, 0, entity_id=1004)
        e.add_component(Velocity(10.0, 10.0))
        count = update_velocities([e], 1.0)
        assert count == 0

    def test_skips_entity_without_any_components(self) -> None:
        e = Entity(0, 0, entity_id=1005)
        count = update_velocities([e], 1.0)
        assert count == 0

    def test_skips_destroyed_entity(self) -> None:
        e = _make_entity(0.0, 0.0, 10.0, 10.0, entity_id=1006)
        e.destroy()
        count = update_velocities([e], 1.0)
        assert count == 0

    def test_mixed_entities(self) -> None:
        """Mix of valid, no-velocity, and destroyed entities."""
        valid = _make_entity(0.0, 0.0, 5.0, 0.0, entity_id=1007)
        no_vel = Entity(0, 0, entity_id=1008)
        no_vel.add_component(Position(0.0, 0.0))
        destroyed = _make_entity(0.0, 0.0, 5.0, 0.0, entity_id=1009)
        destroyed.destroy()

        count = update_velocities([valid, no_vel, destroyed], 1.0)
        assert count == 1

        pos = valid.get_component(Position)
        assert pos.x == pytest.approx(5.0)

    def test_empty_entity_list(self) -> None:
        count = update_velocities([], 1.0)
        assert count == 0

    def test_zero_dt(self) -> None:
        e = _make_entity(3.0, 4.0, 10.0, 10.0, entity_id=1010)
        count = update_velocities([e], 0.0)

        pos = e.get_component(Position)
        assert pos.x == pytest.approx(3.0)
        assert pos.y == pytest.approx(4.0)
        assert count == 1

    def test_negative_dt_allowed(self) -> None:
        e = _make_entity(10.0, 10.0, 5.0, 5.0, entity_id=1011)
        count = update_velocities([e], -1.0)

        pos = e.get_component(Position)
        assert pos.x == pytest.approx(5.0)
        assert pos.y == pytest.approx(5.0)
        assert count == 1

    def test_accumulation_over_multiple_ticks(self) -> None:
        e = _make_entity(0.0, 0.0, 30.0, 0.0, entity_id=1012)
        for _ in range(30):
            update_velocities([e], 1 / 30)

        pos = e.get_component(Position)
        assert pos.x == pytest.approx(30.0)

    def test_does_not_modify_entity_xy(self) -> None:
        e = _make_entity(0.0, 0.0, 10.0, 10.0, entity_id=1013)
        update_velocities([e], 1.0)
        assert e.x == 0
        assert e.y == 0

    def test_rejects_bool_dt(self) -> None:
        with pytest.raises(TypeError, match="dt must be a number"):
            update_velocities([], True)

    def test_rejects_string_dt(self) -> None:
        with pytest.raises(TypeError, match="dt must be a number"):
            update_velocities([], "0.1")

    def test_rejects_none_dt(self) -> None:
        with pytest.raises(TypeError, match="dt must be a number"):
            update_velocities([], None)

    def test_rejects_nan_dt(self) -> None:
        with pytest.raises(ValueError, match="dt must be finite"):
            update_velocities([], math.nan)

    def test_rejects_inf_dt(self) -> None:
        with pytest.raises(ValueError, match="dt must be finite"):
            update_velocities([], math.inf)

    def test_rejects_negative_inf_dt(self) -> None:
        with pytest.raises(ValueError, match="dt must be finite"):
            update_velocities([], -math.inf)

    def test_accepts_generator(self) -> None:
        """Accepts any iterable, not just lists."""
        e = _make_entity(0.0, 0.0, 10.0, 0.0, entity_id=1014)

        def gen():
            yield e

        count = update_velocities(gen(), 1.0)
        assert count == 1

        pos = e.get_component(Position)
        assert pos.x == pytest.approx(10.0)


# ---------------------------------------------------------------------------
# sync_positions
# ---------------------------------------------------------------------------


class TestSyncPositions:
    """Snapping float Position back to Entity.x/y."""

    def test_basic_sync(self) -> None:
        e = Entity(0, 0, entity_id=2000)
        e.add_component(Position(3.7, 8.2))
        count = sync_positions([e])

        assert e.x == 3
        assert e.y == 8
        assert count == 1

    def test_truncation_not_rounding(self) -> None:
        """int() truncates toward zero, does not round."""
        e = Entity(0, 0, entity_id=2001)
        e.add_component(Position(2.9, -0.7))
        sync_positions([e])

        assert e.x == 2  # truncated, not rounded to 3
        assert e.y == 0  # int(-0.7) = 0 (truncation toward zero)

    def test_negative_position(self) -> None:
        e = Entity(0, 0, entity_id=2002)
        e.add_component(Position(-3.5, -7.9))
        sync_positions([e])

        assert e.x == -3  # int(-3.5) = -3
        assert e.y == -7  # int(-7.9) = -7

    def test_exact_integers_unchanged(self) -> None:
        e = Entity(0, 0, entity_id=2003)
        e.add_component(Position(5.0, 10.0))
        sync_positions([e])

        assert e.x == 5
        assert e.y == 10

    def test_skips_entity_without_position(self) -> None:
        e = Entity(5, 5, entity_id=2004)
        count = sync_positions([e])

        assert e.x == 5  # unchanged
        assert e.y == 5
        assert count == 0

    def test_skips_destroyed_entity(self) -> None:
        e = Entity(0, 0, entity_id=2005)
        e.add_component(Position(10.0, 10.0))
        e.destroy()
        count = sync_positions([e])
        assert count == 0

    def test_multiple_entities(self) -> None:
        a = Entity(0, 0, entity_id=2006)
        a.add_component(Position(1.5, 2.5))
        b = Entity(0, 0, entity_id=2007)
        b.add_component(Position(7.9, 3.1))

        count = sync_positions([a, b])
        assert a.x == 1
        assert a.y == 2
        assert b.x == 7
        assert b.y == 3
        assert count == 2

    def test_empty_entity_list(self) -> None:
        count = sync_positions([])
        assert count == 0

    def test_full_pipeline(self) -> None:
        """update_velocities then sync_positions — the typical game loop."""
        e = _make_entity(0.0, 0.0, 15.0, 10.0, entity_id=2008)
        entities = [e]

        update_velocities(entities, 1.0)
        sync_positions(entities)

        pos = e.get_component(Position)
        assert pos.x == pytest.approx(15.0)
        assert pos.y == pytest.approx(10.0)
        assert e.x == 15
        assert e.y == 10


# ---------------------------------------------------------------------------
# Import from package root
# ---------------------------------------------------------------------------


class TestPhysicsImport:
    """Physics helpers are accessible from the wyby package root."""

    def test_import_update_velocities(self) -> None:
        from wyby import update_velocities as uv
        assert uv is update_velocities

    def test_import_sync_positions(self) -> None:
        from wyby import sync_positions as sp
        assert sp is sync_positions
