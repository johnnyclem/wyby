"""Tests for wyby.velocity — Velocity component for entity movement."""

from __future__ import annotations

import pytest

from wyby.entity import Entity
from wyby.position import Position
from wyby.velocity import Velocity


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestVelocityConstruction:
    """Velocity creation and default values."""

    def test_default_is_zero(self) -> None:
        v = Velocity()
        assert v.vx == 0.0
        assert v.vy == 0.0

    def test_explicit_float_values(self) -> None:
        v = Velocity(3.5, -2.0)
        assert v.vx == 3.5
        assert v.vy == -2.0

    def test_int_values_stored_as_float(self) -> None:
        v = Velocity(5, 10)
        assert v.vx == 5.0
        assert v.vy == 10.0
        assert isinstance(v.vx, float)
        assert isinstance(v.vy, float)

    def test_rejects_bool_vx(self) -> None:
        with pytest.raises(TypeError, match="vx must be a number"):
            Velocity(True, 0.0)

    def test_rejects_bool_vy(self) -> None:
        with pytest.raises(TypeError, match="vy must be a number"):
            Velocity(0.0, False)

    def test_rejects_string_vx(self) -> None:
        with pytest.raises(TypeError, match="vx must be a number"):
            Velocity("fast", 0.0)  # type: ignore[arg-type]

    def test_rejects_none_vy(self) -> None:
        with pytest.raises(TypeError, match="vy must be a number"):
            Velocity(0.0, None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Properties and setters
# ---------------------------------------------------------------------------


class TestVelocityProperties:
    """vx and vy property access."""

    def test_set_vx(self) -> None:
        v = Velocity()
        v.vx = 10.0
        assert v.vx == 10.0

    def test_set_vy(self) -> None:
        v = Velocity()
        v.vy = -5.5
        assert v.vy == -5.5

    def test_set_vx_with_int(self) -> None:
        v = Velocity()
        v.vx = 7
        assert v.vx == 7.0
        assert isinstance(v.vx, float)

    def test_set_vx_rejects_bool(self) -> None:
        v = Velocity()
        with pytest.raises(TypeError, match="vx must be a number"):
            v.vx = True  # type: ignore[assignment]

    def test_set_vy_rejects_string(self) -> None:
        v = Velocity()
        with pytest.raises(TypeError, match="vy must be a number"):
            v.vy = "bad"  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Update — applying velocity to position
# ---------------------------------------------------------------------------


class TestVelocityUpdate:
    """update(dt) applies velocity to the entity's Position component."""

    def test_update_moves_position(self) -> None:
        e = Entity(entity_id=200)
        pos = Position(0.0, 0.0)
        vel = Velocity(10.0, 5.0)
        e.add_component(pos)
        e.add_component(vel)

        vel.update(0.1)  # 0.1 seconds

        assert pos.x == pytest.approx(1.0)
        assert pos.y == pytest.approx(0.5)

    def test_update_accumulates(self) -> None:
        e = Entity(entity_id=201)
        pos = Position(0.0, 0.0)
        vel = Velocity(30.0, 0.0)
        e.add_component(pos)
        e.add_component(vel)

        # 30 ticks at 1/30s each = 1 second = 30 cells
        for _ in range(30):
            vel.update(1 / 30)

        assert pos.x == pytest.approx(30.0)
        assert pos.y == pytest.approx(0.0)

    def test_update_negative_velocity(self) -> None:
        e = Entity(entity_id=202)
        pos = Position(10.0, 10.0)
        vel = Velocity(-5.0, -3.0)
        e.add_component(pos)
        e.add_component(vel)

        vel.update(1.0)  # 1 second

        assert pos.x == pytest.approx(5.0)
        assert pos.y == pytest.approx(7.0)

    def test_update_zero_velocity_no_change(self) -> None:
        e = Entity(entity_id=203)
        pos = Position(5.0, 5.0)
        vel = Velocity(0.0, 0.0)
        e.add_component(pos)
        e.add_component(vel)

        vel.update(1.0)

        assert pos.x == 5.0
        assert pos.y == 5.0

    def test_update_without_position_is_noop(self) -> None:
        """Velocity.update does nothing if entity has no Position component."""
        e = Entity(entity_id=204)
        vel = Velocity(10.0, 10.0)
        e.add_component(vel)

        # Should not raise — silently ignored.
        vel.update(1.0)

    def test_update_when_detached_is_noop(self) -> None:
        """Velocity.update does nothing if not attached to any entity."""
        vel = Velocity(10.0, 10.0)
        assert vel.entity is None

        # Should not raise — silently ignored.
        vel.update(1.0)

    def test_update_does_not_modify_entity_xy(self) -> None:
        """Velocity updates Position component, not Entity.x/Entity.y."""
        e = Entity(0, 0, entity_id=205)
        pos = Position(0.0, 0.0)
        vel = Velocity(10.0, 10.0)
        e.add_component(pos)
        e.add_component(vel)

        vel.update(1.0)

        # Position component moved, but Entity.x/y unchanged.
        assert pos.x == pytest.approx(10.0)
        assert pos.y == pytest.approx(10.0)
        assert e.x == 0
        assert e.y == 0


# ---------------------------------------------------------------------------
# Entity attachment
# ---------------------------------------------------------------------------


class TestVelocityAttachment:
    """Velocity component attaches to entities via standard mechanism."""

    def test_attach_to_entity(self) -> None:
        e = Entity(entity_id=300)
        vel = Velocity(1.0, 2.0)
        e.add_component(vel)
        assert vel.entity is e

    def test_detach_from_entity(self) -> None:
        e = Entity(entity_id=301)
        vel = Velocity(1.0, 2.0)
        e.add_component(vel)
        removed = e.remove_component(Velocity)
        assert removed is vel
        assert vel.entity is None

    def test_one_velocity_per_entity(self) -> None:
        e = Entity(entity_id=302)
        e.add_component(Velocity(1.0, 0.0))
        with pytest.raises(ValueError, match="already has a"):
            e.add_component(Velocity(0.0, 1.0))

    def test_position_and_velocity_coexist(self) -> None:
        """An entity can have both Position and Velocity attached."""
        e = Entity(entity_id=303)
        pos = Position(0.0, 0.0)
        vel = Velocity(1.0, 1.0)
        e.add_component(pos)
        e.add_component(vel)
        assert pos.entity is e
        assert vel.entity is e


# ---------------------------------------------------------------------------
# Repr
# ---------------------------------------------------------------------------


class TestVelocityRepr:
    """Velocity __repr__ output."""

    def test_repr_detached(self) -> None:
        v = Velocity(1.0, -2.5)
        assert repr(v) == "Velocity(vx=1.0, vy=-2.5, detached)"

    def test_repr_attached(self) -> None:
        e = Entity(entity_id=60)
        v = Velocity(3.0, 4.0)
        e.add_component(v)
        assert repr(v) == "Velocity(vx=3.0, vy=4.0, entity_id=60)"


# ---------------------------------------------------------------------------
# Import from package root
# ---------------------------------------------------------------------------


class TestVelocityImport:
    """Velocity is accessible from the wyby package root."""

    def test_import_from_wyby(self) -> None:
        from wyby import Velocity as V
        assert V is Velocity
