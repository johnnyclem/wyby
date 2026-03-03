# Entity Model — Design Rationale

## Why wyby Does Not Use a Full ECS

wyby's entity model is **simple composition** — entities hold components
keyed by type, and game logic queries or updates them directly. This is a
deliberate choice, not a missing feature.

A full Entity Component System (ECS) typically provides:

- **Archetype storage** — components packed in contiguous arrays for cache
  efficiency
- **Bitset component masks** — fast O(1) checks for component presence
  across all entities
- **System scheduling** — automatic iteration over entities matching a
  component query (e.g. "all entities with Position and Velocity")
- **World-level queries** — `world.query(Position, Velocity)` returns all
  matching entities

wyby provides **none of these**. Instead:

- Components are stored in a plain `dict` keyed by class on each entity.
- There is no global entity registry or world object.
- Scenes own their entities; queries are the game's responsibility.
- Update order depends on component attachment order, not a system graph.

### Why This Is Fine for Terminal Games

Terminal games typically have tens to hundreds of entities, not tens of
thousands. At this scale:

- O(n) iteration over entities is fast enough (microseconds, not
  milliseconds).
- Cache locality from archetype storage provides no measurable benefit.
- The cognitive overhead of ECS concepts (archetypes, system ordering,
  component registration) is not justified.
- Python's object model already handles composition naturally — a dict of
  components on an entity is idiomatic Python.

### When Simple Composition Is Not Enough

You may outgrow wyby's entity model if:

- You have thousands of entities and need to query "all entities with
  components A and B" frequently per frame.
- You need deterministic system ordering enforced by the framework.
- Component data must be tightly packed for performance-critical inner
  loops.
- You want automatic dependency tracking between systems.

## Migrating to a Full ECS (Optional)

If your game outgrows simple composition, you can adopt a Python ECS
library (e.g. [`esper`](https://github.com/benmoran56/esper)) alongside
wyby. The migration path:

1. **Keep wyby for rendering.** The renderer reads from a cell buffer,
   not from entities directly. Your ECS world produces state; wyby
   displays it.

2. **Move component data to the ECS world.** Instead of
   `entity.add_component(Position(...))`, register Position as an esper
   component and use `world.create_entity(Position(...))`.

3. **Replace entity.update() with ECS systems.** Instead of calling
   `entity.update(dt)` which iterates attached components, define esper
   Processor classes that query and update component data globally.

4. **wyby's Entity becomes a rendering handle.** You may keep a minimal
   wyby Entity for grid position and tags (used by the renderer) while
   the ECS world owns the authoritative game state.

This is an incremental migration — you do not need to rewrite your entire
game at once.

## No Systems — What That Means

In a full ECS, **systems** are functions (or classes) that iterate over all
entities matching a component query and apply logic globally.  For example,
a ``MovementSystem`` would query every entity with ``Position`` and
``Velocity`` components and update their positions each tick.  The ECS
framework typically manages system registration, execution order, and
dependency resolution.

wyby has **no systems layer**.  There is no ``System`` base class, no
``register_system()`` method, no automatic iteration over entities by
component type, and no framework-managed execution order.

### What You Do Instead

Game logic lives in your scene's ``update(dt)`` method (or in component
``update(dt)`` hooks called from there).  You write explicit loops:

```python
class GameplayScene(Scene):
    def update(self, dt: float) -> None:
        # Manual "system" — iterate entities with Velocity and update them.
        for entity in self.get_entities_by_component(Velocity):
            entity.update(dt)

        # Another manual "system" — check for collisions.
        for entity in self.get_entities_by_tag("projectile"):
            self._check_collision(entity)
```

This is intentionally explicit.  You control:

- **Which entities update** — skip dead entities, pause specific groups,
  apply selective logic.
- **Execution order** — movement before collision, AI before animation,
  etc.  The order is whatever you write in ``update()``.
- **Error handling** — catch or propagate exceptions per-entity as needed.

### Caveats

- **No automatic component updates.**  Attaching a component to an entity
  does not cause it to be updated each tick.  You must call
  ``entity.update(dt)`` or individual ``component.update(dt)`` explicitly
  from your game loop or scene.
- **No system scheduling or ordering.**  There is no dependency graph
  between "systems" because there are no systems.  If your movement logic
  must run before your collision logic, write them in that order.
- **No multi-component queries.**  ``Scene.get_entities_by_component()``
  filters by a single component type.  There is no
  ``query(Position, Velocity)`` that returns entities with both.  Use
  ``has_component()`` in a loop for multi-component filtering.
- **No global entity registry.**  Entities belong to scenes.  There is no
  ``World`` object that tracks all entities across all scenes.  If you
  need cross-scene queries, you must implement that yourself.
- **Update order within an entity** depends on component attachment order
  (Python dict insertion order).  There is no per-component priority or
  topological sort.

### Why This Is Enough

For terminal games with tens to hundreds of entities, explicit loops in
``scene.update()`` are clear, debuggable, and fast enough.  The overhead
of a system scheduler (registration API, query caching, dependency
resolution) is not justified at this scale.  If your game grows to need
thousands of entities with complex system interdependencies, see the
migration guidance below.

## Public API for Component Queries

The Entity class provides these methods for working with components:

| Method | Description |
|--------|-------------|
| `add_component(c)` | Attach a component instance |
| `remove_component(Type)` | Detach and return by type |
| `get_component(Type)` | Get component or `None` |
| `has_component(Type)` | Check if component is attached |
| `update(dt)` | Delegate update to all components |

All queries use **exact class matching** — `get_component(Health)` will
not return an `AdvancedHealth` subclass. This keeps the model simple and
predictable. If you need polymorphic queries, iterate `_components`
directly or implement your own lookup.
