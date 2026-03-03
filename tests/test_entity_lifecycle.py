"""Tests for entity lifecycle — creation through destruction and scene integration.

This module exercises the full entity lifecycle:
    create → configure (tags, components) → add to scene → use (update, move)
    → destroy → remove from scene

It documents behavioural caveats at each lifecycle stage, particularly around
post-destroy semantics and scene interaction.

Caveats tested here:
    - **No dead-entity guards.**  Entity does not prevent operations after
      ``destroy()``.  You can still add components, tags, move, and call
      ``update()`` on a destroyed entity.  The ``alive`` flag is purely
      advisory — the game must check it.  This is a deliberate design
      choice: keeping the entity model simple avoids per-method checks
      and keeps the hot path (update/render) fast.
    - **destroy() does not remove from scene.**  Calling ``entity.destroy()``
      only cleans up the entity's own state (components, tags, alive flag).
      The game must separately call ``scene.remove_entity(entity)`` to
      remove it from the scene's entity collection.
    - **Scenes accept destroyed entities.**  ``scene.add_entity()`` does
      not check ``entity.alive``.  A destroyed entity can be added to a
      scene and will appear in queries.  This is the game's responsibility
      to avoid.
    - **Component reuse after destroy.**  Components detached by
      ``destroy()`` can be re-attached to new entities.
"""

from __future__ import annotations

import pytest

from wyby.component import Component
from wyby.entity import Entity
from wyby.scene import Scene, SceneStack


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


class _StubScene(Scene):
    """Minimal concrete Scene for lifecycle tests."""

    def update(self, dt: float) -> None:
        pass

    def render(self) -> None:
        pass


class _Health(Component):
    """Concrete component that tracks lifecycle hook calls."""

    def __init__(self, hp: int = 100) -> None:
        super().__init__()
        self.hp = hp
        self.attach_calls: list[int] = []
        self.detach_calls: list[int] = []
        self.update_calls: list[float] = []

    def on_attach(self, entity: Entity) -> None:
        self.attach_calls.append(entity.id)

    def on_detach(self, entity: Entity) -> None:
        self.detach_calls.append(entity.id)

    def update(self, dt: float) -> None:
        self.update_calls.append(dt)


class _Velocity(Component):
    """Second component type for multi-component lifecycle tests."""

    def __init__(self, vx: float = 0.0, vy: float = 0.0) -> None:
        super().__init__()
        self.vx = vx
        self.vy = vy
        self.detach_calls: list[int] = []

    def on_detach(self, entity: Entity) -> None:
        self.detach_calls.append(entity.id)


# ---------------------------------------------------------------------------
# Full lifecycle flow
# ---------------------------------------------------------------------------


class TestFullLifecycleFlow:
    """End-to-end entity lifecycle: create → configure → scene → use → destroy."""

    def test_create_configure_use_destroy(self) -> None:
        """Complete lifecycle from creation to destruction."""
        # 1. Create
        e = Entity(5, 10, entity_id=1000, tags=["enemy"])
        assert e.alive is True
        assert e.position == (5, 10)
        assert e.has_tag("enemy")

        # 2. Configure — add components
        health = _Health(50)
        e.add_component(health)
        assert health.entity is e
        assert health.attach_calls == [1000]

        # 3. Add to scene
        scene = _StubScene()
        scene.add_entity(e)
        assert scene.get_entity(1000) is e

        # 4. Use — update and move
        e.update(1 / 30)
        assert len(health.update_calls) == 1
        e.move(1, -1)
        assert e.position == (6, 9)

        # 5. Destroy
        e.destroy()
        assert e.alive is False
        assert health.entity is None
        assert health.detach_calls == [1000]
        assert e.has_component(_Health) is False
        assert e.tags == frozenset()

        # 6. Caveat: entity is still in the scene after destroy().
        #    The game must explicitly call scene.remove_entity().
        assert scene.get_entity(1000) is e

        # 7. Remove from scene
        scene.remove_entity(e)
        assert scene.get_entity(1000) is None
        assert len(scene.entities) == 0

    def test_lifecycle_with_multiple_components(self) -> None:
        """Lifecycle exercises all components through attach → update → destroy."""
        e = Entity(entity_id=1001)
        h = _Health(100)
        v = _Velocity(1.0, 2.0)
        e.add_component(h)
        e.add_component(v)

        # Both components attached
        assert h.entity is e
        assert v.entity is e

        # Update drives all components
        e.update(0.5)
        assert h.update_calls == [0.5]

        # Destroy detaches all
        e.destroy()
        assert h.entity is None
        assert v.entity is None
        assert h.detach_calls == [1001]
        assert v.detach_calls == [1001]

    def test_lifecycle_with_scene_stack(self) -> None:
        """Entity survives scene pause/resume within a SceneStack."""
        scene_a = _StubScene()
        scene_b = _StubScene()
        e = Entity(entity_id=1002, tags=["player"])
        h = _Health()
        e.add_component(h)
        scene_a.add_entity(e)

        stack = SceneStack()
        stack.push(scene_a)

        # Push another scene — scene_a is paused but entity persists
        stack.push(scene_b)
        assert scene_a.get_entity(1002) is e
        assert e.alive is True

        # Pop — scene_a resumes, entity still there
        stack.pop()
        assert scene_a.get_entity(1002) is e
        assert e.has_component(_Health)

        # Now destroy and clean up
        e.destroy()
        scene_a.remove_entity(e)
        assert len(scene_a.entities) == 0


# ---------------------------------------------------------------------------
# Post-destroy behaviour
# ---------------------------------------------------------------------------


class TestPostDestroyBehaviour:
    """Operations on a destroyed entity.

    Caveat: Entity has no dead-entity guards.  All mutating operations
    still work after destroy().  The ``alive`` flag is purely advisory —
    the game must check it before operating on entities.  This keeps the
    entity model simple and avoids per-method overhead.
    """

    def test_id_position_readable_after_destroy(self) -> None:
        """Destroyed entity's id and position remain accessible."""
        e = Entity(7, 14, entity_id=1100)
        e.destroy()
        assert e.id == 1100
        assert e.x == 7
        assert e.y == 14
        assert e.position == (7, 14)

    def test_move_after_destroy(self) -> None:
        """Caveat: move() still works on a destroyed entity."""
        e = Entity(0, 0, entity_id=1101)
        e.destroy()
        # No guard — move succeeds.
        e.move(3, 4)
        assert e.position == (3, 4)

    def test_add_tag_after_destroy(self) -> None:
        """Caveat: tags can be added after destroy (tags were cleared)."""
        e = Entity(entity_id=1102, tags=["enemy"])
        e.destroy()
        assert e.tags == frozenset()
        # No guard — tag operations work on dead entities.
        e.add_tag("ghost")
        assert e.has_tag("ghost")

    def test_add_component_after_destroy(self) -> None:
        """Caveat: components can be added to a destroyed entity."""
        e = Entity(entity_id=1103)
        e.destroy()
        # No guard — component can be added to a dead entity.
        h = _Health()
        e.add_component(h)
        assert h.entity is e
        assert e.has_component(_Health)

    def test_update_after_destroy(self) -> None:
        """Caveat: update() still drives components on a destroyed entity."""
        e = Entity(entity_id=1104)
        e.destroy()
        h = _Health()
        e.add_component(h)
        e.update(1.0)
        assert h.update_calls == [1.0]

    def test_destroy_idempotent_even_with_new_components(self) -> None:
        """Second destroy() is a no-op even if components were re-added."""
        e = Entity(entity_id=1105)
        h1 = _Health()
        e.add_component(h1)
        e.destroy()
        assert h1.detach_calls == [1105]

        # Re-add a component to the dead entity, then destroy again.
        # Caveat: destroy() checks alive first; since alive is already
        # False, the second call is a no-op — the new component is NOT
        # detached.
        h2 = _Health()
        e.add_component(h2)
        e.destroy()  # no-op
        assert h2.detach_calls == []  # on_detach was NOT called
        assert h2.entity is e  # still attached

    def test_repr_after_destroy(self) -> None:
        """repr still works on a destroyed entity."""
        e = Entity(1, 2, entity_id=1106)
        e.destroy()
        r = repr(e)
        assert "Entity(id=1106" in r

    def test_equality_after_destroy(self) -> None:
        """Destroyed entity maintains equality semantics (based on id)."""
        e1 = Entity(entity_id=1107)
        e2 = Entity(entity_id=1107)
        e1.destroy()
        assert e1 == e2
        assert hash(e1) == hash(e2)

    def test_hashable_after_destroy(self) -> None:
        """Destroyed entity can still be used as dict key or set member."""
        e = Entity(entity_id=1108)
        s = {e}
        d = {e: "value"}
        e.destroy()
        assert e in s
        assert d[e] == "value"


# ---------------------------------------------------------------------------
# Entity lifecycle and scene interaction
# ---------------------------------------------------------------------------


class TestEntityLifecycleWithScene:
    """How entity lifecycle interacts with scene entity management."""

    def test_destroy_does_not_remove_from_scene(self) -> None:
        """Caveat: destroy() is entity-only cleanup; scene removal is separate.

        This is the most important lifecycle caveat.  Games must call
        scene.remove_entity() after destroy(), or implement a "dead
        entity sweep" in their update loop.
        """
        scene = _StubScene()
        e = Entity(entity_id=1200)
        scene.add_entity(e)

        e.destroy()

        # Entity is destroyed but still in the scene.
        assert e.alive is False
        assert scene.get_entity(1200) is e
        assert e in scene.entities

    def test_destroyed_entity_appears_in_spatial_query(self) -> None:
        """Caveat: scene queries don't filter by alive status."""
        scene = _StubScene()
        e = Entity(3, 7, entity_id=1201)
        scene.add_entity(e)
        e.destroy()

        # Spatial query still finds the destroyed entity.
        result = scene.get_entities_at(3, 7)
        assert e in result

    def test_destroyed_entity_loses_tags_so_tag_query_misses(self) -> None:
        """destroy() clears tags, so tag queries stop matching."""
        scene = _StubScene()
        e = Entity(entity_id=1202, tags=["enemy"])
        scene.add_entity(e)
        assert scene.get_entities_by_tag("enemy") == [e]

        e.destroy()
        # Tags were cleared by destroy(), so tag query no longer matches.
        assert scene.get_entities_by_tag("enemy") == []

    def test_destroyed_entity_loses_components_so_component_query_misses(self) -> None:
        """destroy() detaches components, so component queries stop matching."""
        scene = _StubScene()
        e = Entity(entity_id=1203)
        e.add_component(_Health())
        scene.add_entity(e)
        assert scene.get_entities_by_component(_Health) == [e]

        e.destroy()
        # Components were detached by destroy(), so component query
        # no longer matches.
        assert scene.get_entities_by_component(_Health) == []

    def test_scene_accepts_destroyed_entity(self) -> None:
        """Caveat: add_entity() does not check alive status.

        A destroyed entity can be added to a scene.  The framework
        does not enforce this — the game must avoid it.
        """
        scene = _StubScene()
        e = Entity(entity_id=1204)
        e.destroy()
        # No guard — scene accepts it.
        scene.add_entity(e)
        assert scene.get_entity(1204) is e

    def test_dead_entity_sweep_pattern(self) -> None:
        """Demonstrates the recommended pattern for removing dead entities.

        Since there is no automatic dead-entity sweep, the game must
        iterate over a snapshot and remove destroyed entities manually.
        """
        scene = _StubScene()
        entities = [Entity(entity_id=i) for i in range(1210, 1215)]
        for e in entities:
            scene.add_entity(e)

        # Destroy some entities
        entities[0].destroy()
        entities[2].destroy()
        entities[4].destroy()

        # Sweep: remove dead entities (iterate over snapshot)
        for e in list(scene.entities):
            if not e.alive:
                scene.remove_entity(e)

        remaining = scene.entities
        assert len(remaining) == 2
        assert all(e.alive for e in remaining)
        assert [e.id for e in remaining] == [1211, 1213]

    def test_destroy_entity_in_multiple_scenes(self) -> None:
        """Caveat: entity in multiple scenes must be removed from each.

        destroy() doesn't know about scenes, so the game must remove
        the entity from every scene it's in.
        """
        scene_a = _StubScene()
        scene_b = _StubScene()
        e = Entity(entity_id=1220)
        scene_a.add_entity(e)
        scene_b.add_entity(e)

        e.destroy()

        # Still in both scenes until explicitly removed.
        assert scene_a.get_entity(1220) is e
        assert scene_b.get_entity(1220) is e

        scene_a.remove_entity(e)
        scene_b.remove_entity(e)
        assert scene_a.get_entity(1220) is None
        assert scene_b.get_entity(1220) is None


# ---------------------------------------------------------------------------
# Component lifecycle through entity lifecycle
# ---------------------------------------------------------------------------


class TestComponentLifecycleThroughEntity:
    """Component attach/detach hooks through entity create/destroy."""

    def test_component_attach_and_detach_hooks_called(self) -> None:
        """Full component lifecycle: attach → use → detach via destroy."""
        e = Entity(entity_id=1300)
        h = _Health(50)

        # Attach
        e.add_component(h)
        assert h.attach_calls == [1300]
        assert h.entity is e

        # Use
        e.update(0.1)
        assert h.update_calls == [0.1]

        # Destroy triggers detach
        e.destroy()
        assert h.detach_calls == [1300]
        assert h.entity is None

    def test_component_reuse_after_entity_destroy(self) -> None:
        """Components detached by destroy() can be re-attached to new entities."""
        e1 = Entity(entity_id=1301)
        e2 = Entity(entity_id=1302)
        h = _Health()

        e1.add_component(h)
        e1.destroy()

        # Component is now detached — can be re-used.
        assert h.entity is None
        e2.add_component(h)
        assert h.entity is e2
        assert h.attach_calls == [1301, 1302]
        assert h.detach_calls == [1301]

    def test_component_detach_order_during_destroy(self) -> None:
        """Components are detached in attachment order during destroy()."""
        detach_order: list[str] = []

        class _A(Component):
            def on_detach(self, entity: Entity) -> None:
                detach_order.append("A")

        class _B(Component):
            def on_detach(self, entity: Entity) -> None:
                detach_order.append("B")

        class _C(Component):
            def on_detach(self, entity: Entity) -> None:
                detach_order.append("C")

        e = Entity(entity_id=1303)
        e.add_component(_A())
        e.add_component(_B())
        e.add_component(_C())
        e.destroy()

        # Detach order matches attachment order (dict insertion order).
        assert detach_order == ["A", "B", "C"]

    def test_on_detach_sees_entity_during_destroy(self) -> None:
        """During on_detach in destroy(), component.entity is still set."""
        entity_during_detach: list[Entity | None] = []

        class _Spy(Component):
            def on_detach(self, entity: Entity) -> None:
                entity_during_detach.append(self.entity)

        e = Entity(entity_id=1304)
        spy = _Spy()
        e.add_component(spy)
        e.destroy()

        # During on_detach, self.entity was still the entity.
        assert entity_during_detach == [e]
        # After destroy completes, it's cleared.
        assert spy.entity is None

    def test_manual_remove_then_destroy(self) -> None:
        """Manually removing a component before destroy — destroy skips it."""
        e = Entity(entity_id=1305)
        h = _Health()
        v = _Velocity()
        e.add_component(h)
        e.add_component(v)

        # Manually remove health
        e.remove_component(_Health)
        assert h.detach_calls == [1305]
        assert h.entity is None

        # Destroy detaches only the remaining component (velocity)
        e.destroy()
        assert v.detach_calls == [1305]
        assert v.entity is None
        # Health was not detached again
        assert h.detach_calls == [1305]


# ---------------------------------------------------------------------------
# Multi-entity lifecycle
# ---------------------------------------------------------------------------


class TestMultiEntityLifecycle:
    """Lifecycle operations across multiple entities."""

    def test_batch_destroy(self) -> None:
        """Destroying multiple entities in sequence."""
        entities = [Entity(entity_id=i) for i in range(1400, 1405)]
        for e in entities:
            e.add_component(_Health())

        for e in entities:
            e.destroy()

        assert all(not e.alive for e in entities)

    def test_destroy_during_iteration_with_snapshot(self) -> None:
        """Safe to destroy entities while iterating a snapshot of scene entities.

        This is the recommended pattern: iterate over list(scene.entities),
        destroy matching entities, then sweep dead ones.
        """
        scene = _StubScene()
        entities = [Entity(entity_id=i, tags=["mortal"]) for i in range(1410, 1415)]
        for e in entities:
            scene.add_entity(e)

        # Destroy entities with even ids during iteration
        for e in list(scene.entities):
            if e.id % 2 == 0:
                e.destroy()

        # Sweep dead entities
        for e in list(scene.entities):
            if not e.alive:
                scene.remove_entity(e)

        remaining = scene.entities
        assert len(remaining) == 2
        assert [e.id for e in remaining] == [1411, 1413]

    def test_entity_ids_not_recycled_after_destroy(self) -> None:
        """Caveat: destroying entities does not recycle their ids.

        The auto-incrementing counter never rewinds.  New entities
        always get fresh ids.  For typical games this is fine; for
        extremely long-running programs, the counter grows without
        bound but never overflows (Python ints have arbitrary precision).
        """
        e1 = Entity()
        id1 = e1.id
        e1.destroy()

        e2 = Entity()
        # New entity gets a higher id, not the destroyed one's id.
        assert e2.id > id1

    def test_destroyed_entity_remains_valid_python_object(self) -> None:
        """Caveat: destroyed entity is still a valid Python object.

        Code holding a reference to a destroyed entity can still read
        its id, position, and call methods.  Always check ``alive``
        before using an entity reference that might be stale.
        """
        e = Entity(3, 7, entity_id=1430, tags=["boss"])
        e.add_component(_Health(200))
        ref = e  # Keep a reference

        e.destroy()

        # All reads still work
        assert ref.id == 1430
        assert ref.x == 3
        assert ref.y == 7
        assert ref.alive is False
        assert ref.tags == frozenset()
        assert ref.has_component(_Health) is False

    def test_create_many_destroy_all_no_leak(self) -> None:
        """Creating and destroying many entities does not leak components."""
        scene = _StubScene()
        for i in range(100):
            e = Entity(entity_id=1500 + i)
            e.add_component(_Health(i))
            scene.add_entity(e)

        # Destroy all
        for e in list(scene.entities):
            e.destroy()
            scene.remove_entity(e)

        assert len(scene.entities) == 0


# ---------------------------------------------------------------------------
# Alive flag semantics
# ---------------------------------------------------------------------------


class TestAliveFlag:
    """The alive property and its advisory nature."""

    def test_alive_true_on_creation(self) -> None:
        e = Entity(entity_id=1600)
        assert e.alive is True

    def test_alive_false_after_destroy(self) -> None:
        e = Entity(entity_id=1601)
        e.destroy()
        assert e.alive is False

    def test_alive_not_settable(self) -> None:
        """The alive property has no setter — only destroy() can change it."""
        e = Entity(entity_id=1602)
        with pytest.raises(AttributeError):
            e.alive = False  # type: ignore[misc]

    def test_alive_is_bool(self) -> None:
        e = Entity(entity_id=1603)
        assert e.alive is True  # identity check, not just truthiness
        e.destroy()
        assert e.alive is False  # identity check


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestLifecycleEdgeCases:
    """Edge cases in entity lifecycle."""

    def test_destroy_entity_with_no_components_or_tags(self) -> None:
        """Destroying a bare entity is safe."""
        e = Entity(entity_id=1700)
        e.destroy()
        assert e.alive is False
        assert e.tags == frozenset()

    def test_destroy_twice_is_safe(self) -> None:
        """Double-destroy is idempotent and does not raise."""
        e = Entity(entity_id=1701)
        h = _Health()
        e.add_component(h)
        e.destroy()
        e.destroy()
        assert e.alive is False
        # on_detach was called only once
        assert h.detach_calls == [1701]

    def test_remove_component_then_destroy(self) -> None:
        """Removing a component before destroy — destroy doesn't re-detach it."""
        e = Entity(entity_id=1702)
        h = _Health()
        e.add_component(h)
        removed = e.remove_component(_Health)
        assert removed is h
        assert h.detach_calls == [1702]

        e.destroy()
        # on_detach was NOT called again by destroy
        assert h.detach_calls == [1702]

    def test_destroy_during_component_update(self) -> None:
        """Destroying an entity from within a component's update().

        Caveat: because entity.update() iterates over a snapshot of
        components, destroying the entity mid-update detaches all
        components (clearing the dict), but the snapshot iteration
        continues — remaining components in the snapshot will still
        have their update() called even though they are now detached.
        """
        class _SelfDestroyer(Component):
            def __init__(self) -> None:
                super().__init__()
                self.updated = False

            def update(self, dt: float) -> None:
                self.updated = True
                if self.entity is not None:
                    self.entity.destroy()

        e = Entity(entity_id=1703)
        destroyer = _SelfDestroyer()
        trailing = _Health()
        e.add_component(destroyer)
        e.add_component(trailing)

        # Should not raise — snapshot iteration is safe.
        e.update(1.0)

        assert destroyer.updated
        assert e.alive is False
        # Trailing component still got update() called because the
        # snapshot was taken before the destroy.
        assert len(trailing.update_calls) == 1

    def test_add_to_scene_remove_add_again(self) -> None:
        """Entity can be removed and re-added to the same scene."""
        scene = _StubScene()
        e = Entity(entity_id=1704)
        scene.add_entity(e)
        scene.remove_entity(e)
        # Can re-add after removal
        scene.add_entity(e)
        assert scene.get_entity(1704) is e

    def test_entity_position_after_destroy_and_move(self) -> None:
        """Position is still mutable after destroy."""
        e = Entity(0, 0, entity_id=1705)
        e.destroy()
        e.position = (10, 20)
        assert e.position == (10, 20)
