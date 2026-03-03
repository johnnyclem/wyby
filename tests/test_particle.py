"""Tests for wyby.particle — lightweight particle positions."""

from __future__ import annotations

import math

import pytest

from wyby.particle import Particle, update_particles


# ---------------------------------------------------------------------------
# Particle construction
# ---------------------------------------------------------------------------


class TestParticleConstruction:
    """Particle creation and default values."""

    def test_defaults(self) -> None:
        p = Particle()
        assert p.x == 0.0
        assert p.y == 0.0
        assert p.vx == 0.0
        assert p.vy == 0.0
        assert p.lifetime == 1.0
        assert p.age == 0.0
        assert p.alive is True

    def test_custom_position(self) -> None:
        p = Particle(3.5, 7.2)
        assert p.x == 3.5
        assert p.y == 7.2

    def test_custom_velocity(self) -> None:
        p = Particle(0.0, 0.0, vx=5.0, vy=-3.0)
        assert p.vx == 5.0
        assert p.vy == -3.0

    def test_custom_lifetime(self) -> None:
        p = Particle(lifetime=2.5)
        assert p.lifetime == 2.5

    def test_ints_stored_as_floats(self) -> None:
        p = Particle(3, 4, vx=1, vy=2, lifetime=5)
        assert isinstance(p.x, float)
        assert isinstance(p.y, float)
        assert isinstance(p.vx, float)
        assert isinstance(p.vy, float)
        assert isinstance(p.lifetime, float)

    def test_negative_position_allowed(self) -> None:
        p = Particle(-10.0, -20.0)
        assert p.x == -10.0
        assert p.y == -20.0

    def test_negative_velocity_allowed(self) -> None:
        p = Particle(vx=-5.0, vy=-3.0)
        assert p.vx == -5.0
        assert p.vy == -3.0

    def test_xy_tuple(self) -> None:
        p = Particle(1.5, 2.5)
        assert p.xy == (1.5, 2.5)

    def test_progress_starts_at_zero(self) -> None:
        p = Particle()
        assert p.progress == 0.0


# ---------------------------------------------------------------------------
# Particle validation
# ---------------------------------------------------------------------------


class TestParticleValidation:
    """Input validation on construction."""

    def test_rejects_bool_x(self) -> None:
        with pytest.raises(TypeError, match="x must be a number"):
            Particle(True, 0.0)

    def test_rejects_bool_y(self) -> None:
        with pytest.raises(TypeError, match="y must be a number"):
            Particle(0.0, False)

    def test_rejects_string_x(self) -> None:
        with pytest.raises(TypeError, match="x must be a number"):
            Particle("5", 0.0)

    def test_rejects_string_vx(self) -> None:
        with pytest.raises(TypeError, match="vx must be a number"):
            Particle(vx="fast")

    def test_rejects_none_vy(self) -> None:
        with pytest.raises(TypeError, match="vy must be a number"):
            Particle(vy=None)

    def test_rejects_bool_lifetime(self) -> None:
        with pytest.raises(TypeError, match="lifetime must be a number"):
            Particle(lifetime=True)

    def test_rejects_zero_lifetime(self) -> None:
        with pytest.raises(ValueError, match="lifetime must be positive"):
            Particle(lifetime=0.0)

    def test_rejects_negative_lifetime(self) -> None:
        with pytest.raises(ValueError, match="lifetime must be positive"):
            Particle(lifetime=-1.0)

    def test_rejects_nan_x(self) -> None:
        with pytest.raises(ValueError, match="x must be finite"):
            Particle(math.nan, 0.0)

    def test_rejects_inf_y(self) -> None:
        with pytest.raises(ValueError, match="y must be finite"):
            Particle(0.0, math.inf)

    def test_rejects_nan_lifetime(self) -> None:
        with pytest.raises(ValueError, match="lifetime must be finite"):
            Particle(lifetime=math.nan)

    def test_rejects_inf_vx(self) -> None:
        with pytest.raises(ValueError, match="vx must be finite"):
            Particle(vx=math.inf)


# ---------------------------------------------------------------------------
# Particle property setters
# ---------------------------------------------------------------------------


class TestParticleSetters:
    """Property setters with validation."""

    def test_set_x(self) -> None:
        p = Particle()
        p.x = 5.0
        assert p.x == 5.0

    def test_set_y(self) -> None:
        p = Particle()
        p.y = -3.0
        assert p.y == -3.0

    def test_set_vx(self) -> None:
        p = Particle()
        p.vx = 10.0
        assert p.vx == 10.0

    def test_set_vy(self) -> None:
        p = Particle()
        p.vy = -7.5
        assert p.vy == -7.5

    def test_set_x_from_int(self) -> None:
        p = Particle()
        p.x = 3
        assert p.x == 3.0
        assert isinstance(p.x, float)

    def test_set_x_rejects_bool(self) -> None:
        p = Particle()
        with pytest.raises(TypeError, match="x must be a number"):
            p.x = True

    def test_set_y_rejects_string(self) -> None:
        p = Particle()
        with pytest.raises(TypeError, match="y must be a number"):
            p.y = "5"

    def test_set_vx_rejects_none(self) -> None:
        p = Particle()
        with pytest.raises(TypeError, match="vx must be a number"):
            p.vx = None

    def test_set_vy_rejects_bool(self) -> None:
        p = Particle()
        with pytest.raises(TypeError, match="vy must be a number"):
            p.vy = False


# ---------------------------------------------------------------------------
# Particle kill and lifecycle
# ---------------------------------------------------------------------------


class TestParticleLifecycle:
    """Kill, alive, and progress."""

    def test_kill(self) -> None:
        p = Particle()
        assert p.alive is True
        p.kill()
        assert p.alive is False

    def test_kill_idempotent(self) -> None:
        p = Particle()
        p.kill()
        p.kill()  # no error
        assert p.alive is False

    def test_progress_at_half_life(self) -> None:
        p = Particle(lifetime=2.0)
        # Simulate age manually via update_particles.
        update_particles([p], 1.0)
        assert p.progress == pytest.approx(0.5)

    def test_progress_clamped_at_one(self) -> None:
        p = Particle(lifetime=0.5)
        update_particles([p], 1.0)  # age=1.0 > lifetime=0.5
        assert p.progress == 1.0
        assert p.alive is False

    def test_repr_alive(self) -> None:
        p = Particle(1.0, 2.0, vx=3.0, vy=4.0, lifetime=5.0)
        r = repr(p)
        assert "alive" in r
        assert "1.0" in r
        assert "2.0" in r

    def test_repr_dead(self) -> None:
        p = Particle()
        p.kill()
        assert "dead" in repr(p)


# ---------------------------------------------------------------------------
# update_particles — basic movement
# ---------------------------------------------------------------------------


class TestUpdateParticles:
    """Batch particle position updates."""

    def test_single_particle_movement(self) -> None:
        p = Particle(0.0, 0.0, vx=10.0, vy=5.0, lifetime=2.0)
        count = update_particles([p], 0.1)

        assert p.x == pytest.approx(1.0)
        assert p.y == pytest.approx(0.5)
        assert count == 1

    def test_multiple_particles(self) -> None:
        a = Particle(0.0, 0.0, vx=10.0, vy=0.0, lifetime=5.0)
        b = Particle(5.0, 5.0, vx=0.0, vy=-3.0, lifetime=5.0)
        count = update_particles([a, b], 1.0)

        assert a.x == pytest.approx(10.0)
        assert b.y == pytest.approx(2.0)
        assert count == 2

    def test_skips_dead_particles(self) -> None:
        alive = Particle(0.0, 0.0, vx=10.0, vy=0.0, lifetime=5.0)
        dead = Particle(0.0, 0.0, vx=10.0, vy=0.0, lifetime=5.0)
        dead.kill()

        count = update_particles([alive, dead], 1.0)
        assert count == 1
        assert alive.x == pytest.approx(10.0)
        assert dead.x == 0.0  # unchanged

    def test_empty_list(self) -> None:
        count = update_particles([], 1.0)
        assert count == 0

    def test_zero_dt(self) -> None:
        p = Particle(3.0, 4.0, vx=10.0, vy=10.0, lifetime=2.0)
        update_particles([p], 0.0)

        assert p.x == pytest.approx(3.0)
        assert p.y == pytest.approx(4.0)
        assert p.age == pytest.approx(0.0)

    def test_accumulation_over_ticks(self) -> None:
        p = Particle(0.0, 0.0, vx=30.0, vy=0.0, lifetime=5.0)
        for _ in range(30):
            update_particles([p], 1 / 30)

        assert p.x == pytest.approx(30.0)

    def test_negative_dt_allowed(self) -> None:
        p = Particle(10.0, 10.0, vx=5.0, vy=5.0, lifetime=5.0)
        update_particles([p], -1.0)

        assert p.x == pytest.approx(5.0)
        assert p.y == pytest.approx(5.0)

    def test_accepts_generator(self) -> None:
        p = Particle(0.0, 0.0, vx=10.0, vy=0.0, lifetime=5.0)

        def gen():
            yield p

        count = update_particles(gen(), 1.0)
        assert count == 1
        assert p.x == pytest.approx(10.0)


# ---------------------------------------------------------------------------
# update_particles — aging and death
# ---------------------------------------------------------------------------


class TestParticleAging:
    """Particle aging and automatic death."""

    def test_age_increments(self) -> None:
        p = Particle(lifetime=2.0)
        update_particles([p], 0.5)
        assert p.age == pytest.approx(0.5)

    def test_dies_at_lifetime(self) -> None:
        p = Particle(lifetime=1.0)
        update_particles([p], 1.0)
        assert p.alive is False
        assert p.age == pytest.approx(1.0)

    def test_dies_when_age_exceeds_lifetime(self) -> None:
        p = Particle(lifetime=0.5)
        update_particles([p], 1.0)
        assert p.alive is False

    def test_alive_before_lifetime(self) -> None:
        p = Particle(lifetime=1.0)
        update_particles([p], 0.9)
        assert p.alive is True

    def test_position_updated_on_death_tick(self) -> None:
        """The particle moves on the tick it dies (final update)."""
        p = Particle(0.0, 0.0, vx=10.0, vy=0.0, lifetime=1.0)
        update_particles([p], 1.0)
        assert p.alive is False
        assert p.x == pytest.approx(10.0)  # moved before dying

    def test_dead_particle_not_updated_next_tick(self) -> None:
        """Once dead, further ticks skip the particle."""
        p = Particle(0.0, 0.0, vx=10.0, vy=0.0, lifetime=1.0)
        update_particles([p], 1.0)  # dies here
        assert p.alive is False

        update_particles([p], 1.0)  # should be skipped
        assert p.x == pytest.approx(10.0)  # unchanged


# ---------------------------------------------------------------------------
# update_particles — gravity
# ---------------------------------------------------------------------------


class TestParticleGravity:
    """Gravity optional parameter on update_particles."""

    def test_gravity_accelerates_velocity(self) -> None:
        p = Particle(0.0, 0.0, vx=0.0, vy=0.0, lifetime=5.0)
        update_particles([p], 1.0, gravity=(0.0, 10.0))

        assert p.vy == pytest.approx(10.0)
        assert p.vx == pytest.approx(0.0)

    def test_gravity_affects_position(self) -> None:
        p = Particle(0.0, 0.0, vx=0.0, vy=0.0, lifetime=5.0)
        update_particles([p], 1.0, gravity=(0.0, 10.0))

        # v += 10*1=10, then p += 10*1=10
        assert p.y == pytest.approx(10.0)

    def test_horizontal_gravity(self) -> None:
        p = Particle(0.0, 0.0, lifetime=5.0)
        update_particles([p], 0.5, gravity=(20.0, 0.0))

        assert p.vx == pytest.approx(10.0)  # 20 * 0.5
        assert p.x == pytest.approx(5.0)    # 10 * 0.5

    def test_gravity_accumulates(self) -> None:
        p = Particle(0.0, 0.0, lifetime=5.0)
        for _ in range(10):
            update_particles([p], 0.1, gravity=(0.0, 10.0))

        assert p.vy == pytest.approx(10.0)  # 10 * 10 * 0.1

    def test_gravity_none_is_default(self) -> None:
        p = Particle(0.0, 0.0, vx=5.0, lifetime=5.0)
        update_particles([p], 1.0)
        assert p.vx == pytest.approx(5.0)  # unchanged by gravity

    def test_gravity_with_existing_velocity(self) -> None:
        p = Particle(0.0, 0.0, vx=10.0, vy=5.0, lifetime=5.0)
        update_particles([p], 1.0, gravity=(0.0, 10.0))

        assert p.vx == pytest.approx(10.0)  # no horizontal gravity
        assert p.vy == pytest.approx(15.0)  # 5 + 10*1

    def test_gravity_skips_dead(self) -> None:
        p = Particle(0.0, 0.0, lifetime=5.0)
        p.kill()
        count = update_particles([p], 1.0, gravity=(0.0, 10.0))
        assert count == 0


# ---------------------------------------------------------------------------
# update_particles — dt validation
# ---------------------------------------------------------------------------


class TestUpdateParticlesValidation:
    """Input validation on update_particles."""

    def test_rejects_bool_dt(self) -> None:
        with pytest.raises(TypeError, match="dt must be a number"):
            update_particles([], True)

    def test_rejects_string_dt(self) -> None:
        with pytest.raises(TypeError, match="dt must be a number"):
            update_particles([], "0.1")

    def test_rejects_none_dt(self) -> None:
        with pytest.raises(TypeError, match="dt must be a number"):
            update_particles([], None)

    def test_rejects_nan_dt(self) -> None:
        with pytest.raises(ValueError, match="dt must be finite"):
            update_particles([], math.nan)

    def test_rejects_inf_dt(self) -> None:
        with pytest.raises(ValueError, match="dt must be finite"):
            update_particles([], math.inf)

    def test_gravity_rejects_non_tuple(self) -> None:
        with pytest.raises(TypeError, match="gravity must be a .* tuple"):
            update_particles([], 1.0, gravity=[0.0, 10.0])

    def test_gravity_rejects_wrong_length(self) -> None:
        with pytest.raises(TypeError, match="gravity must be a .* tuple"):
            update_particles([], 1.0, gravity=(1.0,))

    def test_gravity_rejects_bool_component(self) -> None:
        with pytest.raises(TypeError, match="gravity.*must be a number"):
            update_particles([], 1.0, gravity=(True, 0.0))

    def test_gravity_rejects_nan(self) -> None:
        with pytest.raises(ValueError, match="gravity.*must be finite"):
            update_particles([], 1.0, gravity=(math.nan, 0.0))

    def test_gravity_rejects_inf(self) -> None:
        with pytest.raises(ValueError, match="gravity.*must be finite"):
            update_particles([], 1.0, gravity=(0.0, math.inf))


# ---------------------------------------------------------------------------
# Import from package root
# ---------------------------------------------------------------------------


class TestParticleImport:
    """Particle classes are accessible from the wyby package root."""

    def test_import_particle(self) -> None:
        from wyby import Particle as P
        assert P is Particle

    def test_import_update_particles(self) -> None:
        from wyby import update_particles as up
        assert up is update_particles
