"""Lightweight particle positions for visual effects.

Provides a :class:`Particle` container and a batch :func:`update_particles`
helper for advancing particle state each tick.

Particles are intentionally simpler than entities — they carry their own
position and velocity as plain floats (no components, no tags, no id
counter) so that hundreds can exist without the overhead of the full
Entity + Component model.

Usage::

    from wyby.particle import Particle, update_particles

    # Create particles with position and velocity.
    sparks = [
        Particle(10.0, 5.0, vx=3.0, vy=-8.0, lifetime=0.5),
        Particle(10.5, 5.0, vx=-2.0, vy=-7.0, lifetime=0.4),
    ]

    # Each tick in your game loop:
    alive_count = update_particles(sparks, dt=1 / 30)

    # Remove dead particles periodically:
    sparks = [p for p in sparks if p.alive]

Caveats:
    - **Not entities.**  Particles do not have an :attr:`id`, tags,
      components, or any of the :class:`~wyby.entity.Entity` machinery.
      They are plain data containers.  If you need collision detection,
      spatial queries, or component attachment, use Entity instead.
    - **No automatic cleanup.**  Dead particles (``alive is False``)
      remain in your list until you filter them out.  There is no
      built-in particle-pool or object-recycling mechanism.
    - **No rendering integration.**  Particles store position only.
      Rendering (choosing a glyph, style, or colour per particle) is
      the game's responsibility.  A common pattern is to iterate alive
      particles and write directly to a :class:`~wyby.grid.CellBuffer`.
    - **No spatial indexing.**  Iterating all particles is O(n).  For
      typical terminal games (hundreds of particles) this is fine.
    - **Float precision.**  Coordinates are Python floats (64-bit IEEE
      754).  The same precision caveats as
      :class:`~wyby.position.Position` apply.
    - **Thread safety.**  Particle creation and mutation are not
      thread-safe.  The game loop is expected to be single-threaded.
    - **Euler integration only.**  :func:`update_particles` uses simple
      forward-Euler integration (``pos += vel * dt``).  This is
      adequate for visual effects at small fixed timesteps but
      accumulates error at large dt values.
"""

from __future__ import annotations

import logging
import math
from typing import Iterable

_logger = logging.getLogger(__name__)


class Particle:
    """A lightweight particle with position, velocity, and lifetime.

    Particles are cheaper than entities — no id counter, no component
    dict, no tag set.  Use them for visual effects (sparks, smoke,
    explosions) where you need many short-lived objects.

    Args:
        x: Initial horizontal position (float).  Defaults to ``0.0``.
        y: Initial vertical position (float).  Defaults to ``0.0``.
        vx: Horizontal velocity in cells per second.  Positive = rightward.
            Defaults to ``0.0``.
        vy: Vertical velocity in cells per second.  Positive = downward
            (terminal y-axis convention).  Defaults to ``0.0``.
        lifetime: Maximum age in seconds before the particle dies.
            Must be positive.  Defaults to ``1.0``.

    Raises:
        TypeError: If any numeric argument is not an int or float,
            or is a bool.
        ValueError: If *lifetime* is not positive, or if any argument
            is NaN or infinite.

    Caveats:
        - **Booleans are rejected.**  ``True``/``False`` are not accepted
          even though ``bool`` is a subclass of ``int`` in Python.
        - **Terminal grids use (0, 0) as top-left**, with x increasing
          rightward and y increasing downward.  Positive ``vy`` moves
          the particle down the screen.
        - **No bounds enforcement.**  Coordinates can be negative or
          exceed the grid dimensions.  Off-screen particle culling is
          the game's responsibility.
        - **Lifetime starts at zero.**  The :attr:`age` attribute begins
          at ``0.0`` and increments each tick via :func:`update_particles`.
          When ``age >= lifetime``, :attr:`alive` becomes ``False``.
    """

    __slots__ = ("_x", "_y", "_vx", "_vy", "_age", "_lifetime", "_alive")

    def __init__(
        self,
        x: float = 0.0,
        y: float = 0.0,
        *,
        vx: float = 0.0,
        vy: float = 0.0,
        lifetime: float = 1.0,
    ) -> None:
        # Validate all numeric arguments.
        for name, val in (
            ("x", x), ("y", y), ("vx", vx), ("vy", vy), ("lifetime", lifetime),
        ):
            if isinstance(val, bool) or not isinstance(val, (int, float)):
                raise TypeError(
                    f"{name} must be a number (int or float), "
                    f"got {type(val).__name__}"
                )
            if math.isnan(val) or math.isinf(val):
                raise ValueError(f"{name} must be finite, got {val}")

        if lifetime <= 0.0:
            raise ValueError(
                f"lifetime must be positive, got {lifetime}"
            )

        self._x = float(x)
        self._y = float(y)
        self._vx = float(vx)
        self._vy = float(vy)
        self._age = 0.0
        self._lifetime = float(lifetime)
        self._alive = True

    # -- Position properties ---------------------------------------------------

    @property
    def x(self) -> float:
        """Horizontal position."""
        return self._x

    @x.setter
    def x(self, value: float) -> None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(
                f"x must be a number (int or float), "
                f"got {type(value).__name__}"
            )
        self._x = float(value)

    @property
    def y(self) -> float:
        """Vertical position."""
        return self._y

    @y.setter
    def y(self, value: float) -> None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(
                f"y must be a number (int or float), "
                f"got {type(value).__name__}"
            )
        self._y = float(value)

    @property
    def xy(self) -> tuple[float, float]:
        """The ``(x, y)`` position as a tuple.

        Caveats:
            - Returns a new tuple each call.  Do not rely on identity
              (``is``) comparisons between tuples.
        """
        return (self._x, self._y)

    # -- Velocity properties ---------------------------------------------------

    @property
    def vx(self) -> float:
        """Horizontal velocity in cells per second."""
        return self._vx

    @vx.setter
    def vx(self, value: float) -> None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(
                f"vx must be a number (int or float), "
                f"got {type(value).__name__}"
            )
        self._vx = float(value)

    @property
    def vy(self) -> float:
        """Vertical velocity in cells per second."""
        return self._vy

    @vy.setter
    def vy(self, value: float) -> None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(
                f"vy must be a number (int or float), "
                f"got {type(value).__name__}"
            )
        self._vy = float(value)

    # -- Lifetime properties ---------------------------------------------------

    @property
    def age(self) -> float:
        """Seconds elapsed since creation.  Read-only."""
        return self._age

    @property
    def lifetime(self) -> float:
        """Maximum age in seconds.  Read-only after construction."""
        return self._lifetime

    @property
    def alive(self) -> bool:
        """Whether this particle is still alive.

        Returns ``False`` once :attr:`age` reaches :attr:`lifetime` or
        after :meth:`kill` is called.
        """
        return self._alive

    @property
    def progress(self) -> float:
        """Normalised age in ``[0.0, 1.0]``.

        ``0.0`` at birth, ``1.0`` at (or after) death.  Useful for
        interpolating alpha, colour, or size over the particle's life.

        Caveats:
            - Clamped to ``1.0`` — never exceeds it even if the particle
              has been dead for multiple ticks before being cleaned up.
        """
        if self._lifetime <= 0.0:
            return 1.0
        return min(self._age / self._lifetime, 1.0)

    def kill(self) -> None:
        """Immediately mark this particle as dead.

        Idempotent — calling ``kill()`` on an already-dead particle is
        a no-op.
        """
        self._alive = False

    def __repr__(self) -> str:
        state = "alive" if self._alive else "dead"
        return (
            f"Particle(x={self._x}, y={self._y}, "
            f"vx={self._vx}, vy={self._vy}, "
            f"age={self._age:.3f}/{self._lifetime:.3f}, {state})"
        )


def update_particles(
    particles: Iterable[Particle],
    dt: float,
    *,
    gravity: tuple[float, float] | None = None,
) -> int:
    """Advance all particles by one tick.

    For each alive particle:

    1. **Gravity** (if provided): adds ``(gx * dt, gy * dt)`` to velocity.
    2. **Position update**: adds ``(vx * dt, vy * dt)`` to position.
    3. **Aging**: increments :attr:`~Particle.age` by *dt*.
    4. **Death check**: if ``age >= lifetime``, marks the particle as dead.

    Args:
        particles: Iterable of particles to process.  Dead particles are
            skipped.  The iterable may contain a mix of alive and dead
            particles.
        dt: Time elapsed since the last tick, in seconds.  Should be a
            fixed timestep (e.g. ``1/30``) for deterministic results.
        gravity: Optional ``(gx, gy)`` acceleration in cells/sec².
            Applied to velocity before the position update.  Positive
            ``gy`` accelerates downward.  Default ``None`` (no gravity).

    Returns:
        The number of particles that were alive and updated this tick.
        (Particles that *became* dead during this tick are included in
        the count — they received their final position update.)

    Raises:
        TypeError: If *dt* is not a number, or *gravity* is malformed.
        ValueError: If *dt* is NaN or infinite, or *gravity* contains
            NaN/infinite values.

    Caveats:
        - **Dead particles are skipped**, not removed.  The caller must
          filter dead particles from the list separately.
        - **Euler integration.**  ``pos += vel * dt`` accumulates error
          at large dt.  Keep dt small (≤ 1/15 s) for smooth results.
        - **No collision detection.**  Particles pass through everything.
          If you need particles that interact with the world, use
          entities with the collision module instead.
        - **Negative dt is allowed** (moves particles backward in time)
          but **aging still adds dt**, which means negative dt would
          *decrease* age.  This is intentional for time-reversal effects
          but may cause ``age < 0`` — the particle will not die until
          age reaches lifetime again.
        - **Gravity mutates velocity in place.**  Velocity accumulates
          across ticks — a particle under constant gravity accelerates.
        - **O(n) per call** where n is the number of particles.
    """
    # -- Validate dt -----------------------------------------------------------
    if isinstance(dt, bool) or not isinstance(dt, (int, float)):
        raise TypeError(
            f"dt must be a number (int or float), got {type(dt).__name__}"
        )
    if math.isnan(dt) or math.isinf(dt):
        raise ValueError(f"dt must be finite, got {dt}")

    # -- Validate gravity ------------------------------------------------------
    if gravity is not None:
        if not isinstance(gravity, tuple) or len(gravity) != 2:
            raise TypeError(
                "gravity must be a (gx, gy) tuple of two numbers"
            )
        gx, gy = gravity
        if isinstance(gx, bool) or not isinstance(gx, (int, float)):
            raise TypeError(
                f"gravity[0] must be a number (int or float), "
                f"got {type(gx).__name__}"
            )
        if isinstance(gy, bool) or not isinstance(gy, (int, float)):
            raise TypeError(
                f"gravity[1] must be a number (int or float), "
                f"got {type(gy).__name__}"
            )
        if math.isnan(gx) or math.isinf(gx):
            raise ValueError(f"gravity[0] must be finite, got {gx}")
        if math.isnan(gy) or math.isinf(gy):
            raise ValueError(f"gravity[1] must be finite, got {gy}")

    # -- Update particles ------------------------------------------------------
    count = 0
    for p in particles:
        if not p._alive:
            continue

        # 1. Gravity: accelerate velocity.
        if gravity is not None:
            p._vx += gravity[0] * dt
            p._vy += gravity[1] * dt

        # 2. Position update: move.
        p._x += p._vx * dt
        p._y += p._vy * dt

        # 3. Age the particle.
        p._age += dt

        # 4. Death check.
        if p._age >= p._lifetime:
            p._alive = False

        count += 1

    return count
