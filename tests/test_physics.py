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
# update_velocities — gravity
# ---------------------------------------------------------------------------


class TestGravity:
    """Gravity optional parameter on update_velocities."""

    def test_gravity_accelerates_velocity(self) -> None:
        """Gravity adds (gx*dt, gy*dt) to velocity each tick."""
        e = _make_entity(0.0, 0.0, 0.0, 0.0, entity_id=3000)
        update_velocities([e], 1.0, gravity=(0.0, 10.0))

        vel = e.get_component(Velocity)
        # After 1 second: vy = 0 + 10*1 = 10
        assert vel.vy == pytest.approx(10.0)
        assert vel.vx == pytest.approx(0.0)

    def test_gravity_accumulates_over_ticks(self) -> None:
        """Velocity grows each tick under constant gravity."""
        e = _make_entity(0.0, 0.0, 0.0, 0.0, entity_id=3001)
        for _ in range(10):
            update_velocities([e], 0.1, gravity=(0.0, 10.0))

        vel = e.get_component(Velocity)
        # After 10 ticks of 0.1s: vy = 10 * 10 * 0.1 = 10.0
        assert vel.vy == pytest.approx(10.0)

    def test_gravity_affects_position(self) -> None:
        """Position changes by the updated velocity, not the old velocity."""
        e = _make_entity(0.0, 0.0, 0.0, 0.0, entity_id=3002)
        update_velocities([e], 1.0, gravity=(0.0, 10.0))

        pos = e.get_component(Position)
        # v += 10*1=10, then p += 10*1=10
        assert pos.y == pytest.approx(10.0)

    def test_horizontal_gravity(self) -> None:
        e = _make_entity(0.0, 0.0, 0.0, 0.0, entity_id=3003)
        update_velocities([e], 0.5, gravity=(20.0, 0.0))

        vel = e.get_component(Velocity)
        assert vel.vx == pytest.approx(10.0)  # 20 * 0.5
        pos = e.get_component(Position)
        assert pos.x == pytest.approx(5.0)  # 10 * 0.5

    def test_gravity_none_is_default(self) -> None:
        """No gravity when gravity=None (the default)."""
        e = _make_entity(0.0, 0.0, 5.0, 0.0, entity_id=3004)
        update_velocities([e], 1.0)

        vel = e.get_component(Velocity)
        assert vel.vx == pytest.approx(5.0)  # unchanged
        assert vel.vy == pytest.approx(0.0)  # unchanged

    def test_gravity_with_existing_velocity(self) -> None:
        """Gravity adds to existing velocity, doesn't replace it."""
        e = _make_entity(0.0, 0.0, 10.0, 5.0, entity_id=3005)
        update_velocities([e], 1.0, gravity=(0.0, 10.0))

        vel = e.get_component(Velocity)
        assert vel.vx == pytest.approx(10.0)  # no horizontal gravity
        assert vel.vy == pytest.approx(15.0)  # 5 + 10*1

    def test_negative_gravity(self) -> None:
        """Negative gravity (e.g. buoyancy) decelerates downward velocity."""
        e = _make_entity(0.0, 0.0, 0.0, 10.0, entity_id=3006)
        update_velocities([e], 1.0, gravity=(0.0, -5.0))

        vel = e.get_component(Velocity)
        assert vel.vy == pytest.approx(5.0)  # 10 + (-5)*1

    def test_gravity_skips_destroyed(self) -> None:
        e = _make_entity(0.0, 0.0, 0.0, 0.0, entity_id=3007)
        e.destroy()
        count = update_velocities([e], 1.0, gravity=(0.0, 10.0))
        assert count == 0

    def test_gravity_rejects_non_tuple(self) -> None:
        with pytest.raises(TypeError, match="gravity must be a .* tuple"):
            update_velocities([], 1.0, gravity=[0.0, 10.0])

    def test_gravity_rejects_wrong_length(self) -> None:
        with pytest.raises(TypeError, match="gravity must be a .* tuple"):
            update_velocities([], 1.0, gravity=(1.0,))

    def test_gravity_rejects_bool_component(self) -> None:
        with pytest.raises(TypeError, match="gravity.*must be a number"):
            update_velocities([], 1.0, gravity=(True, 0.0))

    def test_gravity_rejects_string_component(self) -> None:
        with pytest.raises(TypeError, match="gravity.*must be a number"):
            update_velocities([], 1.0, gravity=(0.0, "10"))

    def test_gravity_rejects_nan(self) -> None:
        with pytest.raises(ValueError, match="gravity.*must be finite"):
            update_velocities([], 1.0, gravity=(math.nan, 0.0))

    def test_gravity_rejects_inf(self) -> None:
        with pytest.raises(ValueError, match="gravity.*must be finite"):
            update_velocities([], 1.0, gravity=(0.0, math.inf))

    def test_gravity_zero_dt(self) -> None:
        """Gravity with dt=0 does nothing (g*0 = 0)."""
        e = _make_entity(0.0, 0.0, 0.0, 0.0, entity_id=3008)
        update_velocities([e], 0.0, gravity=(0.0, 100.0))

        vel = e.get_component(Velocity)
        assert vel.vy == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# update_velocities — friction
# ---------------------------------------------------------------------------


class TestFriction:
    """Friction optional parameter on update_velocities."""

    def test_friction_damps_velocity(self) -> None:
        """Friction reduces velocity each tick."""
        e = _make_entity(0.0, 0.0, 100.0, 0.0, entity_id=4000)
        update_velocities([e], 1.0, friction=0.5)

        vel = e.get_component(Velocity)
        # After 1 second with friction=0.5: vx = 100 * 0.5^1 = 50
        assert vel.vx == pytest.approx(50.0)

    def test_friction_frame_rate_independent(self) -> None:
        """Two half-second ticks produce the same result as one full second."""
        e1 = _make_entity(0.0, 0.0, 100.0, 0.0, entity_id=4001)
        update_velocities([e1], 1.0, friction=0.5)

        e2 = _make_entity(0.0, 0.0, 100.0, 0.0, entity_id=4002)
        update_velocities([e2], 0.5, friction=0.5)
        update_velocities([e2], 0.5, friction=0.5)

        vel1 = e1.get_component(Velocity)
        vel2 = e2.get_component(Velocity)
        assert vel1.vx == pytest.approx(vel2.vx, rel=1e-9)

    def test_friction_one_no_damping(self) -> None:
        """friction=1.0 means no friction (retain 100% of velocity)."""
        e = _make_entity(0.0, 0.0, 42.0, 0.0, entity_id=4003)
        update_velocities([e], 1.0, friction=1.0)

        vel = e.get_component(Velocity)
        assert vel.vx == pytest.approx(42.0)

    def test_friction_zero_instant_stop(self) -> None:
        """friction=0.0 stops velocity instantly (for dt > 0)."""
        e = _make_entity(0.0, 0.0, 100.0, 50.0, entity_id=4004)
        update_velocities([e], 0.1, friction=0.0)

        vel = e.get_component(Velocity)
        assert vel.vx == pytest.approx(0.0)
        assert vel.vy == pytest.approx(0.0)

    def test_friction_applies_to_both_axes(self) -> None:
        e = _make_entity(0.0, 0.0, 80.0, -60.0, entity_id=4005)
        update_velocities([e], 1.0, friction=0.5)

        vel = e.get_component(Velocity)
        assert vel.vx == pytest.approx(40.0)
        assert vel.vy == pytest.approx(-30.0)

    def test_friction_none_is_default(self) -> None:
        """No friction when friction=None (the default)."""
        e = _make_entity(0.0, 0.0, 10.0, 0.0, entity_id=4006)
        update_velocities([e], 1.0)

        vel = e.get_component(Velocity)
        assert vel.vx == pytest.approx(10.0)  # unchanged

    def test_friction_rejects_negative(self) -> None:
        with pytest.raises(ValueError, match="friction must be between 0 and 1"):
            update_velocities([], 1.0, friction=-0.1)

    def test_friction_rejects_greater_than_one(self) -> None:
        with pytest.raises(ValueError, match="friction must be between 0 and 1"):
            update_velocities([], 1.0, friction=1.1)

    def test_friction_rejects_bool(self) -> None:
        with pytest.raises(TypeError, match="friction must be a number"):
            update_velocities([], 1.0, friction=True)

    def test_friction_rejects_string(self) -> None:
        with pytest.raises(TypeError, match="friction must be a number"):
            update_velocities([], 1.0, friction="0.5")

    def test_friction_rejects_nan(self) -> None:
        with pytest.raises(ValueError, match="friction must be finite"):
            update_velocities([], 1.0, friction=math.nan)

    def test_friction_rejects_inf(self) -> None:
        with pytest.raises(ValueError, match="friction must be finite"):
            update_velocities([], 1.0, friction=math.inf)

    def test_friction_with_zero_dt(self) -> None:
        """friction^0 = 1, so no damping when dt=0."""
        e = _make_entity(0.0, 0.0, 100.0, 0.0, entity_id=4007)
        update_velocities([e], 0.0, friction=0.5)

        vel = e.get_component(Velocity)
        assert vel.vx == pytest.approx(100.0)

    def test_friction_skips_destroyed(self) -> None:
        e = _make_entity(0.0, 0.0, 100.0, 0.0, entity_id=4008)
        e.destroy()
        count = update_velocities([e], 1.0, friction=0.5)
        assert count == 0


# ---------------------------------------------------------------------------
# update_velocities — gravity + friction combined
# ---------------------------------------------------------------------------


class TestGravityAndFriction:
    """Gravity and friction used together."""

    def test_gravity_then_friction_order(self) -> None:
        """Gravity is applied before friction in the same tick."""
        e = _make_entity(0.0, 0.0, 0.0, 0.0, entity_id=5000)
        update_velocities([e], 1.0, gravity=(0.0, 100.0), friction=0.5)

        vel = e.get_component(Velocity)
        # Step 1: vy += 100 * 1 = 100
        # Step 2: vy *= 0.5^1 = 50
        # Step 3: position += 50 * 1 = 50
        assert vel.vy == pytest.approx(50.0)
        pos = e.get_component(Position)
        assert pos.y == pytest.approx(50.0)

    def test_terminal_velocity(self) -> None:
        """Under constant gravity + friction, velocity approaches a limit."""
        e = _make_entity(0.0, 0.0, 0.0, 0.0, entity_id=5001)

        # Run many ticks to approach terminal velocity.
        for _ in range(1000):
            update_velocities([e], 1 / 30, gravity=(0.0, 100.0), friction=0.5)

        vel = e.get_component(Velocity)
        # Velocity should stabilize (not grow unbounded).
        vy_a = vel.vy
        for _ in range(100):
            update_velocities([e], 1 / 30, gravity=(0.0, 100.0), friction=0.5)
        vy_b = vel.vy

        # After many ticks, velocity should barely change (terminal velocity).
        assert abs(vy_b - vy_a) < 0.01

    def test_gravity_and_friction_with_multiple_entities(self) -> None:
        a = _make_entity(0.0, 0.0, 10.0, 0.0, entity_id=5002)
        b = _make_entity(0.0, 0.0, 0.0, 20.0, entity_id=5003)
        count = update_velocities(
            [a, b], 1.0, gravity=(0.0, 5.0), friction=0.9,
        )
        assert count == 2

        vel_a = a.get_component(Velocity)
        vel_b = b.get_component(Velocity)
        # a: vx=10*0.9=9, vy=5*0.9=4.5
        assert vel_a.vx == pytest.approx(9.0)
        assert vel_a.vy == pytest.approx(4.5)
        # b: vx=0, vy=(20+5)*0.9=22.5
        assert vel_b.vy == pytest.approx(22.5)

    def test_full_pipeline_with_gravity_friction(self) -> None:
        """update_velocities (gravity+friction) then sync_positions."""
        e = _make_entity(0.0, 0.0, 0.0, 0.0, entity_id=5004)
        entities = [e]

        update_velocities(entities, 1.0, gravity=(0.0, 10.0), friction=1.0)
        sync_positions(entities)

        # friction=1 → no damping, so vy=10 after gravity, pos.y=10
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
