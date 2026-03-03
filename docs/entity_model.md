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
