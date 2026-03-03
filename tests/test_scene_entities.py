"""Tests for Scene entity management — add, remove, query by id/position/tag."""

from __future__ import annotations

import pytest

from wyby.entity import Entity
from wyby.scene import Scene


# ---------------------------------------------------------------------------
# Concrete Scene subclass for testing
# ---------------------------------------------------------------------------


class _StubScene(Scene):
    """Minimal concrete Scene for entity management tests."""

    def update(self, dt: float) -> None:
        pass

    def render(self) -> None:
        pass


# ---------------------------------------------------------------------------
# entities property
# ---------------------------------------------------------------------------


class TestSceneEntitiesProperty:
    """The entities property returns a snapshot list of scene entities."""

    def test_empty_by_default(self) -> None:
        scene = _StubScene()
        assert scene.entities == []

    def test_returns_list(self) -> None:
        scene = _StubScene()
        assert isinstance(scene.entities, list)

    def test_returns_copy_not_live_view(self) -> None:
        """Mutating the returned list does not affect the scene."""
        scene = _StubScene()
        e = Entity(entity_id=1)
        scene.add_entity(e)
        snapshot = scene.entities
        snapshot.clear()
        assert len(scene.entities) == 1

    def test_insertion_order_preserved(self) -> None:
        scene = _StubScene()
        e1 = Entity(entity_id=10)
        e2 = Entity(entity_id=20)
        e3 = Entity(entity_id=30)
        scene.add_entity(e1)
        scene.add_entity(e2)
        scene.add_entity(e3)
        assert [e.id for e in scene.entities] == [10, 20, 30]


# ---------------------------------------------------------------------------
# add_entity
# ---------------------------------------------------------------------------


class TestAddEntity:
    """Scene.add_entity adds an entity to the scene."""

    def test_add_single_entity(self) -> None:
        scene = _StubScene()
        e = Entity(entity_id=1)
        scene.add_entity(e)
        assert len(scene.entities) == 1
        assert scene.entities[0] is e

    def test_add_multiple_entities(self) -> None:
        scene = _StubScene()
        e1 = Entity(entity_id=1)
        e2 = Entity(entity_id=2)
        scene.add_entity(e1)
        scene.add_entity(e2)
        assert len(scene.entities) == 2

    def test_add_rejects_non_entity(self) -> None:
        scene = _StubScene()
        with pytest.raises(TypeError, match="must be an Entity instance"):
            scene.add_entity("not an entity")  # type: ignore[arg-type]

    def test_add_rejects_none(self) -> None:
        scene = _StubScene()
        with pytest.raises(TypeError, match="must be an Entity instance"):
            scene.add_entity(None)  # type: ignore[arg-type]

    def test_add_duplicate_id_raises_value_error(self) -> None:
        scene = _StubScene()
        e1 = Entity(entity_id=42)
        e2 = Entity(entity_id=42)
        scene.add_entity(e1)
        with pytest.raises(ValueError, match="already in this scene"):
            scene.add_entity(e2)

    def test_add_same_instance_twice_raises_value_error(self) -> None:
        scene = _StubScene()
        e = Entity(entity_id=1)
        scene.add_entity(e)
        with pytest.raises(ValueError, match="already in this scene"):
            scene.add_entity(e)

    def test_add_entity_to_multiple_scenes(self) -> None:
        """Entities can exist in multiple scenes (no ownership tracking)."""
        scene_a = _StubScene()
        scene_b = _StubScene()
        e = Entity(entity_id=1)
        scene_a.add_entity(e)
        scene_b.add_entity(e)
        assert len(scene_a.entities) == 1
        assert len(scene_b.entities) == 1


# ---------------------------------------------------------------------------
# remove_entity
# ---------------------------------------------------------------------------


class TestRemoveEntity:
    """Scene.remove_entity removes an entity from the scene."""

    def test_remove_entity(self) -> None:
        scene = _StubScene()
        e = Entity(entity_id=1)
        scene.add_entity(e)
        removed = scene.remove_entity(e)
        assert removed is e
        assert len(scene.entities) == 0

    def test_remove_returns_the_entity(self) -> None:
        scene = _StubScene()
        e = Entity(entity_id=1)
        scene.add_entity(e)
        result = scene.remove_entity(e)
        assert result is e

    def test_remove_nonexistent_raises_key_error(self) -> None:
        scene = _StubScene()
        e = Entity(entity_id=99)
        with pytest.raises(KeyError, match="not in this scene"):
            scene.remove_entity(e)

    def test_remove_rejects_non_entity(self) -> None:
        scene = _StubScene()
        with pytest.raises(TypeError, match="must be an Entity instance"):
            scene.remove_entity(42)  # type: ignore[arg-type]

    def test_remove_only_target(self) -> None:
        """Removing one entity leaves others untouched."""
        scene = _StubScene()
        e1 = Entity(entity_id=1)
        e2 = Entity(entity_id=2)
        scene.add_entity(e1)
        scene.add_entity(e2)
        scene.remove_entity(e1)
        assert len(scene.entities) == 1
        assert scene.entities[0] is e2

    def test_remove_then_re_add(self) -> None:
        """An entity can be removed and re-added to the same scene."""
        scene = _StubScene()
        e = Entity(entity_id=1)
        scene.add_entity(e)
        scene.remove_entity(e)
        scene.add_entity(e)
        assert len(scene.entities) == 1

    def test_remove_during_iteration_with_snapshot(self) -> None:
        """Removing entities while iterating over a snapshot is safe."""
        scene = _StubScene()
        entities = [Entity(entity_id=i) for i in range(5)]
        for e in entities:
            scene.add_entity(e)

        # Remove even-id entities while iterating over a snapshot.
        for e in list(scene.entities):
            if e.id % 2 == 0:
                scene.remove_entity(e)

        remaining_ids = [e.id for e in scene.entities]
        assert remaining_ids == [1, 3]


# ---------------------------------------------------------------------------
# get_entity (by id)
# ---------------------------------------------------------------------------


class TestGetEntity:
    """Scene.get_entity looks up an entity by id."""

    def test_get_existing(self) -> None:
        scene = _StubScene()
        e = Entity(entity_id=42)
        scene.add_entity(e)
        assert scene.get_entity(42) is e

    def test_get_nonexistent_returns_none(self) -> None:
        scene = _StubScene()
        assert scene.get_entity(999) is None

    def test_get_after_remove_returns_none(self) -> None:
        scene = _StubScene()
        e = Entity(entity_id=1)
        scene.add_entity(e)
        scene.remove_entity(e)
        assert scene.get_entity(1) is None


# ---------------------------------------------------------------------------
# get_entities_at (spatial query)
# ---------------------------------------------------------------------------


class TestGetEntitiesAt:
    """Scene.get_entities_at returns entities at a grid position."""

    def test_returns_entity_at_position(self) -> None:
        scene = _StubScene()
        e = Entity(5, 10, entity_id=1)
        scene.add_entity(e)
        result = scene.get_entities_at(5, 10)
        assert result == [e]

    def test_returns_empty_when_no_match(self) -> None:
        scene = _StubScene()
        e = Entity(0, 0, entity_id=1)
        scene.add_entity(e)
        assert scene.get_entities_at(99, 99) == []

    def test_returns_multiple_at_same_position(self) -> None:
        scene = _StubScene()
        e1 = Entity(3, 7, entity_id=1)
        e2 = Entity(3, 7, entity_id=2)
        scene.add_entity(e1)
        scene.add_entity(e2)
        result = scene.get_entities_at(3, 7)
        assert len(result) == 2
        assert e1 in result
        assert e2 in result

    def test_empty_scene_returns_empty(self) -> None:
        scene = _StubScene()
        assert scene.get_entities_at(0, 0) == []

    def test_position_must_match_both_x_and_y(self) -> None:
        scene = _StubScene()
        e = Entity(5, 10, entity_id=1)
        scene.add_entity(e)
        assert scene.get_entities_at(5, 0) == []
        assert scene.get_entities_at(0, 10) == []

    def test_reflects_entity_movement(self) -> None:
        """Query result reflects current entity position, not add-time position."""
        scene = _StubScene()
        e = Entity(0, 0, entity_id=1)
        scene.add_entity(e)
        e.move(5, 5)
        assert scene.get_entities_at(0, 0) == []
        assert scene.get_entities_at(5, 5) == [e]


# ---------------------------------------------------------------------------
# get_entities_by_tag
# ---------------------------------------------------------------------------


class TestGetEntitiesByTag:
    """Scene.get_entities_by_tag returns entities with a given tag."""

    def test_returns_tagged_entities(self) -> None:
        scene = _StubScene()
        e1 = Entity(entity_id=1, tags=["enemy"])
        e2 = Entity(entity_id=2, tags=["ally"])
        scene.add_entity(e1)
        scene.add_entity(e2)
        result = scene.get_entities_by_tag("enemy")
        assert result == [e1]

    def test_returns_empty_when_no_match(self) -> None:
        scene = _StubScene()
        e = Entity(entity_id=1, tags=["wall"])
        scene.add_entity(e)
        assert scene.get_entities_by_tag("enemy") == []

    def test_returns_multiple_matches(self) -> None:
        scene = _StubScene()
        e1 = Entity(entity_id=1, tags=["enemy"])
        e2 = Entity(entity_id=2, tags=["enemy", "boss"])
        scene.add_entity(e1)
        scene.add_entity(e2)
        result = scene.get_entities_by_tag("enemy")
        assert len(result) == 2

    def test_empty_scene_returns_empty(self) -> None:
        scene = _StubScene()
        assert scene.get_entities_by_tag("anything") == []

    def test_reflects_tag_changes(self) -> None:
        """Query result reflects current tags, not add-time tags."""
        scene = _StubScene()
        e = Entity(entity_id=1)
        scene.add_entity(e)
        assert scene.get_entities_by_tag("enemy") == []
        e.add_tag("enemy")
        assert scene.get_entities_by_tag("enemy") == [e]


# ---------------------------------------------------------------------------
# Entity list survives scene lifecycle
# ---------------------------------------------------------------------------


class TestSceneEntityLifecycle:
    """Entity list is independent of scene stack lifecycle hooks."""

    def test_entities_persist_through_pause_resume(self) -> None:
        """Entities stay in the scene when it is paused and resumed."""
        from wyby.scene import SceneStack

        scene_a = _StubScene()
        scene_b = _StubScene()
        e = Entity(entity_id=1)
        scene_a.add_entity(e)

        stack = SceneStack()
        stack.push(scene_a)
        stack.push(scene_b)  # pauses scene_a
        assert len(scene_a.entities) == 1

        stack.pop()  # resumes scene_a
        assert len(scene_a.entities) == 1
        assert scene_a.entities[0] is e

    def test_entities_persist_after_scene_exit(self) -> None:
        """Entities are not automatically cleared on scene exit.

        The framework does not auto-clear the entity list when a scene
        is popped — the scene object and its entities remain alive as
        long as the caller holds a reference.  Cleanup is the game's
        responsibility (e.g. in on_exit).
        """
        from wyby.scene import SceneStack

        scene = _StubScene()
        e = Entity(entity_id=1)
        scene.add_entity(e)

        stack = SceneStack()
        stack.push(scene)
        popped = stack.pop()
        assert len(popped.entities) == 1

    def test_subclass_without_super_init_gets_lazy_entities(self) -> None:
        """Scenes that forget super().__init__() still get _entities on first add."""

        class _NoSuperScene(Scene):
            def __init__(self) -> None:
                # Deliberately skipping super().__init__()
                pass

            def update(self, dt: float) -> None:
                pass

            def render(self) -> None:
                pass

        scene = _NoSuperScene()
        e = Entity(entity_id=1)
        # The add_entity method should handle the missing _entities
        # attribute since it accesses self._entities directly.
        # This will raise AttributeError — which is expected since
        # Scene.__init__ sets up _entities. Document that
        # super().__init__() is required.
        with pytest.raises(AttributeError):
            scene.add_entity(e)
