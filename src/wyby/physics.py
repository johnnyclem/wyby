"""Scene-level physics helpers for batch velocity updates.

Provides functions that iterate over collections of entities, applying
velocity to position and optionally snapping float positions back to
the entity's integer grid coordinates.

These are convenience functions for the most common physics pattern in
a game loop — they replace the manual ``for entity in entities: ...``
boilerplate that every scene would otherwise duplicate.

Usage::

    from wyby.entity import Entity
    from wyby.position import Position
    from wyby.velocity import Velocity
    from wyby.physics import update_velocities, sync_positions

    # In your Scene.update(dt):
    entities = [player, enemy_a, enemy_b]
    update_velocities(entities, dt)   # apply velocity → position
    sync_positions(entities)          # snap Position → Entity.x/y

    # With gravity and friction:
    update_velocities(
        entities, dt,
        gravity=(0.0, 98.0),  # downward gravity (cells/sec²)
        friction=0.8,         # retain 80% of velocity per second
    )

Caveats:
    - **Not automatic.**  These functions are never called by the engine.
      You must call them explicitly in your :meth:`~wyby.scene.Scene.update`
      override.  This is by design — it gives you full control over update
      ordering (e.g., apply velocity, then check collisions, then sync).
    - **Skips entities without the required components.**  An entity
      missing :class:`~wyby.velocity.Velocity` or
      :class:`~wyby.position.Position` is silently skipped (no error).
      This allows heterogeneous entity lists (e.g., walls with no
      velocity alongside moving enemies).
    - **No collision detection.**  Velocity is applied unconditionally.
      Call collision checks *after* ``update_velocities`` if needed.
    - **O(n) per call** where n is the number of entities.  No spatial
      indexing or early-out optimizations.  For typical games (hundreds
      of entities) this is fine.
    - **Destroyed entities are skipped.**  If ``entity.alive`` is
      ``False``, the entity is ignored.
    - **Not a real physics engine.**  Gravity and friction are simple
      per-tick approximations, not continuous integration.  For small
      timesteps (1/30 s or smaller) the results are good enough for
      terminal games.  For large or variable timesteps, consider a
      proper integrator.
"""

from __future__ import annotations

import math
from typing import Iterable

from wyby.entity import Entity
from wyby.position import Position
from wyby.velocity import Velocity

# ---------------------------------------------------------------------------
# Physics scope documentation
# ---------------------------------------------------------------------------

#: Human-readable summary of what wyby provides and does not provide for
#: physics.  Importable as ``wyby.PHYSICS_SCOPE`` for programmatic access
#: (e.g. displaying to users or including in --help output).
#:
#: wyby is NOT a physics engine.  The helpers in this module are thin
#: convenience wrappers over explicit per-entity loops.  They exist to
#: reduce boilerplate, not to simulate physics accurately.
PHYSICS_SCOPE: str = """\
wyby does NOT include a physics engine.

What wyby provides:
  - Position component     — float x/y coordinates (no constraints, no bounds)
  - Velocity component     — constant-speed movement in cells/sec (no forces)
  - update_velocities()    — batch Euler integration: v += gravity*dt,
                             v *= friction**dt, pos += v*dt
  - sync_positions()       — snap float Position to integer Entity.x/y
  - AABB collision         — overlap test for axis-aligned bounding boxes
  - TileMap collision      — point/region solid queries on a boolean grid

What wyby does NOT provide:
  - Continuous collision detection (tunnelling through thin walls is possible)
  - Collision response (separation, bouncing, sliding — game's responsibility)
  - Rigid-body dynamics, joints, constraints, or contact solvers
  - Spatial indexing (broad-phase acceleration structures)
  - Verlet or RK4 integration (Euler only, error accumulates at large dt)
  - Rotational physics, angular velocity, or torque
  - Mass, density, restitution, or material properties

Design rationale:
  Terminal games typically involve tens to hundreds of entities on a
  character-cell grid.  At this scale, explicit game-loop code that calls
  update_velocities(), checks collisions, and applies response is simpler
  and more debuggable than a general-purpose physics engine.  The helpers
  here eliminate the boilerplate (iterating entities, skipping dead ones,
  applying dt) without hiding the control flow.

  If your game needs real physics, use a dedicated library (e.g. pymunk,
  Box2D via pybox2d) for simulation and wyby only for rendering.
"""


def update_velocities(
    entities: Iterable[Entity],
    dt: float,
    *,
    gravity: tuple[float, float] | None = None,
    friction: float | None = None,
) -> int:
    """Apply velocity to position for every entity that has both components.

    For each entity in *entities*, if it has both a
    :class:`~wyby.velocity.Velocity` and a
    :class:`~wyby.position.Position` component:

    1. **Gravity** (if provided): adds ``(gx * dt, gy * dt)`` to velocity.
    2. **Friction** (if provided): multiplies velocity by ``friction ** dt``.
    3. **Position update**: adds ``(vx * dt, vy * dt)`` to position.

    Args:
        entities: Iterable of entities to process.  May contain entities
            without Velocity or Position — those are silently skipped.
        dt: Time elapsed since the last tick, in seconds.  Should be a
            fixed timestep (e.g. ``1/30``) for deterministic results.
        gravity: Optional ``(gx, gy)`` acceleration in cells/sec².
            Applied to velocity before the position update.  Positive
            ``gy`` accelerates downward (terminal y-axis points down).
            Default ``None`` (no gravity).
        friction: Optional velocity damping factor, in the range
            ``[0, 1]``.  Represents the fraction of velocity retained
            after one second.  Applied as ``vel *= friction ** dt`` for
            frame-rate independence.  ``1.0`` = no friction,
            ``0.0`` = instant stop.  Default ``None`` (no friction).

    Returns:
        The number of entities that were actually updated (i.e., had
        both Velocity and Position components and were alive).

    Raises:
        TypeError: If *dt* is not a number (int or float), or is a bool.
            Also raised if *gravity* is not a 2-tuple of numbers, or if
            *friction* is not a number.
        ValueError: If *dt* is NaN or infinite, or if *friction* is
            outside the range ``[0, 1]``.

    Caveats:
        - **dt validation.**  Passing a negative *dt* is allowed (moves
          entities backward) but passing non-numeric types raises
          :class:`TypeError`.  A *dt* of zero is allowed but is a no-op
          for all entities.
        - **NaN / Inf.**  ``math.nan`` and ``math.inf`` are rejected
          with :class:`ValueError` because they would corrupt position
          data irreversibly.
        - **Iteration order.**  Entities are processed in iteration
          order.  If the iterable is a list, entities are updated in
          list order.  No sorting or prioritization is applied.
        - **Mutates velocity in place.**  When *gravity* or *friction*
          are supplied, the Velocity component's ``vx`` and ``vy`` are
          modified directly.  This is intentional — velocity accumulates
          across ticks, so an entity under constant gravity accelerates.
        - **Mutates position in place.**  The Position component's
          ``x`` and ``y`` are modified directly.  If you need the
          previous position (e.g., for collision response), save it
          before calling this function.
        - **Euler integration.**  Gravity uses simple forward-Euler
          integration (``v += a * dt``, then ``p += v * dt``).  This is
          standard for fixed-timestep game loops but accumulates error
          over very large dt values.  Keep dt small (≤ 1/15 s).
        - **Friction is exponential damping.**  ``friction ** dt``
          ensures frame-rate independence: halving the timestep and
          doubling the ticks produces the same result (within float
          precision).  This is *not* Coulomb friction — it's velocity-
          proportional drag, similar to air resistance.
        - **Gravity before friction.**  Gravity is applied first, then
          friction damps the resulting velocity.  This means an entity
          under constant gravity with friction will reach a terminal
          velocity where ``gravity * dt == (1 - friction ** dt) * vel``.
        - **Friction with negative dt.**  ``friction ** (-dt)``
          *amplifies* velocity, which is almost certainly not what you
          want.  Avoid combining friction with negative dt.
    """
    # -- Validate dt -------------------------------------------------------
    if isinstance(dt, bool) or not isinstance(dt, (int, float)):
        raise TypeError(
            f"dt must be a number (int or float), got {type(dt).__name__}"
        )
    if math.isnan(dt) or math.isinf(dt):
        raise ValueError(f"dt must be finite, got {dt}")

    # -- Validate gravity --------------------------------------------------
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

    # -- Validate friction -------------------------------------------------
    friction_factor: float | None = None
    if friction is not None:
        if isinstance(friction, bool) or not isinstance(
            friction, (int, float)
        ):
            raise TypeError(
                f"friction must be a number (int or float), "
                f"got {type(friction).__name__}"
            )
        if math.isnan(friction) or math.isinf(friction):
            raise ValueError(f"friction must be finite, got {friction}")
        if friction < 0.0 or friction > 1.0:
            raise ValueError(
                f"friction must be between 0 and 1 (inclusive), "
                f"got {friction}"
            )
        # Pre-compute the per-tick damping factor for frame-rate independence.
        # friction=0.8 at dt=1/30 → factor ≈ 0.9926 (small damping per tick).
        friction_factor = friction ** dt

    # -- Apply to entities -------------------------------------------------
    count = 0
    for entity in entities:
        if not entity.alive:
            continue
        vel = entity.get_component(Velocity)
        if vel is None:
            continue
        pos = entity.get_component(Position)
        if pos is None:
            continue

        # 1. Gravity: accelerate velocity (v += a * dt).
        if gravity is not None:
            vel._vx += gravity[0] * dt
            vel._vy += gravity[1] * dt

        # 2. Friction: damp velocity (v *= friction^dt).
        if friction_factor is not None:
            vel._vx *= friction_factor
            vel._vy *= friction_factor

        # 3. Position update: move (p += v * dt).
        vel.update(dt)
        count += 1
    return count


def sync_positions(entities: Iterable[Entity]) -> int:
    """Snap each entity's grid position to its Position component.

    For each entity that has a :class:`~wyby.position.Position`
    component, sets ``entity.x = int(pos.x)`` and
    ``entity.y = int(pos.y)``, synchronizing the integer grid
    coordinates with the float position.

    This is typically called once per frame *after*
    :func:`update_velocities` so that the renderer (which uses
    ``entity.x`` / ``entity.y``) sees the updated positions.

    Args:
        entities: Iterable of entities to process.  Entities without
            a Position component are silently skipped.

    Returns:
        The number of entities whose grid positions were synced.

    Caveats:
        - **Truncation, not rounding.**  Uses ``int()`` which truncates
          toward zero (``int(2.9)`` → ``2``, ``int(-0.7)`` → ``0``).
          This matches Python's ``int()`` semantics.  If you need
          rounding, sync positions manually with ``round()``.
        - **One-way sync.**  This copies Position → Entity.  It does
          *not* update Position from Entity.  If you modify ``entity.x``
          directly, the Position component is unaffected.
        - **Destroyed entities are skipped.**  If ``entity.alive`` is
          ``False``, the entity is ignored.
    """
    count = 0
    for entity in entities:
        if not entity.alive:
            continue
        pos = entity.get_component(Position)
        if pos is None:
            continue
        entity.x = int(pos.x)
        entity.y = int(pos.y)
        count += 1
    return count
