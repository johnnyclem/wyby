"""Entity container and spatial queries.

This module will provide a simple entity model — not a full
Entity Component System (ECS). Entities are Python objects with
position, appearance (character + style), and optional tags/groups
for querying.

Caveats:
    - **Not yet implemented.** This module is a placeholder establishing
      the package structure. See SCOPE.md for the intended design.
    - This is deliberately minimal: no archetype storage, no bitset
      component masks, no system scheduling. If your game outgrows this,
      you can bring in ``esper`` or another ECS library and use wyby
      only for rendering.
    - The entity model's job is to answer: "what is at position (x, y)?"
      and "give me all entities tagged 'enemy'." It does not handle
      physics, collision detection, or pathfinding.
    - Spatial query performance is O(n) over all entities. For games
      with hundreds of entities this is fine; for thousands, a spatial
      index would be needed but is not provided in v0.1.
"""
