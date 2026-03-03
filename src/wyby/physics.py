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
"""

from __future__ import annotations

import math
from typing import Iterable

from wyby.entity import Entity
from wyby.position import Position
from wyby.velocity import Velocity


def update_velocities(entities: Iterable[Entity], dt: float) -> int:
    """Apply velocity to position for every entity that has both components.

    For each entity in *entities*, if it has both a
    :class:`~wyby.velocity.Velocity` and a
    :class:`~wyby.position.Position` component, calls
    ``velocity.update(dt)`` to add ``(vx * dt, vy * dt)`` to the
    position.

    Args:
        entities: Iterable of entities to process.  May contain entities
            without Velocity or Position — those are silently skipped.
        dt: Time elapsed since the last tick, in seconds.  Should be a
            fixed timestep (e.g. ``1/30``) for deterministic results.

    Returns:
        The number of entities that were actually updated (i.e., had
        both Velocity and Position components and were alive).

    Raises:
        TypeError: If *dt* is not a number (int or float), or is a bool.

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
        - **Mutates position in place.**  The Position component's
          ``x`` and ``y`` are modified directly.  If you need the
          previous position (e.g., for collision response), save it
          before calling this function.
    """
    if isinstance(dt, bool) or not isinstance(dt, (int, float)):
        raise TypeError(
            f"dt must be a number (int or float), got {type(dt).__name__}"
        )
    if math.isnan(dt) or math.isinf(dt):
        raise ValueError(f"dt must be finite, got {dt}")
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
