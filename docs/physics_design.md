# Physics Design — No Full Physics Engine

## What wyby Provides

wyby includes **movement helpers and collision detection primitives**, not a
physics engine.  These are thin convenience functions that reduce boilerplate
in your game loop without hiding control flow.

| Module | What it does | What it does NOT do |
|--------|-------------|---------------------|
| `position` | Float x/y coordinates | No bounds enforcement, no constraints |
| `velocity` | Constant-speed movement (cells/sec) | No forces, no acceleration |
| `physics` | Batch Euler integration with optional gravity/friction | No continuous integration, no collision response |
| `collision` | AABB overlap detection | No spatial indexing, no response |
| `tile_collision` | Point/region solid queries on a boolean grid | No slopes, one-way platforms, or tile metadata |

### Gravity and Friction Are Approximations

The `update_velocities()` function applies gravity and friction using simple
forward-Euler integration:

```python
# Per entity, per tick:
velocity += gravity * dt          # acceleration
velocity *= friction ** dt        # exponential damping
position += velocity * dt         # movement
```

This is **not** a physically accurate simulation:

- **Euler integration accumulates error** at large timesteps.  Keep `dt`
  at 1/30 s or smaller for acceptable results.
- **Friction is exponential damping** (velocity-proportional drag), not
  Coulomb friction.  It models air resistance, not surface contact.
- **Gravity is applied before friction** in the same tick, which means
  terminal velocity is reached when `gravity * dt == (1 - friction**dt) * vel`.
- **No Verlet or RK4 integration** is available.  If you need higher-order
  integration, implement it in your scene's `update()` method.

### Collision Detection Has No Response

`AABB` and `aabb_overlap()` answer "do these two boxes overlap?" — nothing
more.  `TileMap` answers "is this tile solid?" — nothing more.

What collision response means and why wyby does not provide it:

- **Separation** — pushing overlapping entities apart so they no longer
  intersect.  Requires knowing penetration depth and direction.
- **Bouncing** — reflecting velocity on collision.  Requires restitution
  coefficients and contact normals.
- **Sliding** — allowing movement along a surface while blocking
  penetration.  Requires projecting velocity onto the collision surface.
- **Blocking** — preventing an entity from moving into a solid tile.
  The simplest response, but still game-specific (do you block, slide,
  teleport back, or take damage?).

All of these are the **game's responsibility**.  wyby's collision primitives
give you the detection; you write the response in your `Scene.update()`.

## Why No Physics Engine

Terminal games operate on a character-cell grid with tens to hundreds of
entities.  At this scale:

- **Explicit game-loop code is simpler.**  A 10-line `update()` method
  that calls `update_velocities()`, checks collisions, and applies your
  response logic is easier to understand and debug than configuring a
  physics engine.
- **Control flow is visible.**  You decide update order: move first, then
  collide, then respond.  There is no hidden physics step or solver
  iteration.
- **Terminal cells are not square.**  A typical cell is ~1:2 aspect ratio
  (width:height).  Physics engines assume uniform coordinate spaces.
  Adapting one to non-square cells adds complexity with no benefit for
  the kinds of games wyby targets.
- **Performance is not the bottleneck.**  O(n) velocity updates and O(n²)
  AABB pairwise checks are fast for n < 500.  Spatial indexing and
  broadphase acceleration structures are unnecessary overhead.

## What You Write Instead

A typical game loop with wyby's helpers:

```python
from wyby.physics import update_velocities, sync_positions
from wyby.collision import AABB, aabb_overlap

class GameplayScene(Scene):
    def update(self, dt: float) -> None:
        entities = self.get_entities()

        # 1. Apply velocity (with optional gravity and friction).
        update_velocities(entities, dt, gravity=(0, 98.0), friction=0.8)

        # 2. Snap float positions to grid.
        sync_positions(entities)

        # 3. Check collisions (game-specific response).
        player_box = AABB(player.x, player.y, 1, 1)
        for wall in walls:
            wall_box = AABB(wall.x, wall.y, wall.width, wall.height)
            if aabb_overlap(player_box, wall_box):
                self._push_out(player, wall_box)  # your response logic
```

This is intentionally explicit.  Every step is visible, every response is
yours to define.

## When wyby's Helpers Are Not Enough

If your game needs any of the following, use a dedicated physics library
(e.g. [pymunk](https://www.pymunk.org/), pybox2d) for simulation and wyby
only for rendering:

- Continuous collision detection (preventing tunnelling through thin walls)
- Rigid-body dynamics (mass, torque, angular velocity)
- Joints and constraints (springs, hinges, ropes)
- Contact solvers (stacking, resting contacts)
- Spatial indexing for large entity counts (quad-trees, spatial hashing)
- Deterministic physics replay

## Programmatic Access

The `PHYSICS_SCOPE` constant is available at the package root:

```python
from wyby import PHYSICS_SCOPE
print(PHYSICS_SCOPE)
```

This string summarizes what wyby provides and does not provide.  Use it in
`--help` output, error messages, or documentation generators.
