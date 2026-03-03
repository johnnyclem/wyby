"""Tests documenting wyby's deliberate absence of an ECS systems layer.

wyby provides entities and components but deliberately has no "systems"
— no System base class, no automatic update scheduling, no system
registration, and no framework-managed execution order.  These tests
codify that design decision as verifiable behaviour so it is not
accidentally introduced or expected.

See docs/entity_model.md § "No Systems — What That Means" for rationale.
"""

from __future__ import annotations

import pytest

from wyby.component import Component
from wyby.entity import Entity
from wyby.scene import Scene


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _Counter(Component):
    """Component that counts update calls."""

    def __init__(self) -> None:
        super().__init__()
        self.call_count = 0

    def update(self, dt: float) -> None:
        self.call_count += 1


class _CounterB(_Counter):
    """Second counter type (components are keyed by exact class)."""
    pass


class _MinimalScene(Scene):
    """Concrete scene with no-op render for testing."""

    def update(self, dt: float) -> None:
        pass

    def render(self) -> None:
        pass


# ---------------------------------------------------------------------------
# No System class exists
# ---------------------------------------------------------------------------


class TestNoSystemClass:
    """wyby deliberately provides no System base class."""

    def test_no_system_in_wyby_package(self) -> None:
        """There is no 'System' exported from the wyby package."""
        import wyby
        assert not hasattr(wyby, "System")

    def test_no_system_module(self) -> None:
        """There is no wyby.system module."""
        with pytest.raises(ModuleNotFoundError):
            import wyby.system  # type: ignore[import-not-found]  # noqa: F401


# ---------------------------------------------------------------------------
# No automatic component updates
# ---------------------------------------------------------------------------


class TestNoAutomaticUpdates:
    """Components are not updated automatically — explicit calls required."""

    def test_attaching_component_does_not_call_update(self) -> None:
        """Adding a component to an entity does not trigger update()."""
        e = Entity(entity_id=5000)
        c = _Counter()
        e.add_component(c)
        assert c.call_count == 0

    def test_adding_entity_to_scene_does_not_update_components(self) -> None:
        """Registering an entity with a scene does not trigger updates."""
        scene = _MinimalScene()
        e = Entity(entity_id=5001)
        c = _Counter()
        e.add_component(c)
        scene.add_entity(e)
        assert c.call_count == 0

    def test_scene_update_does_not_auto_iterate_entities(self) -> None:
        """Scene.update() does not automatically call entity.update().

        The base Scene does not iterate entities — the subclass must
        implement explicit update logic.
        """
        scene = _MinimalScene()
        e = Entity(entity_id=5002)
        c = _Counter()
        e.add_component(c)
        scene.add_entity(e)

        scene.update(1 / 30)

        # Component was never updated because _MinimalScene.update is a no-op.
        assert c.call_count == 0

    def test_explicit_entity_update_calls_components(self) -> None:
        """You must call entity.update(dt) yourself."""
        e = Entity(entity_id=5003)
        c = _Counter()
        e.add_component(c)

        e.update(1 / 30)

        assert c.call_count == 1


# ---------------------------------------------------------------------------
# No system registration on scenes
# ---------------------------------------------------------------------------


class TestNoSystemRegistration:
    """Scenes have no system registration or management API."""

    def test_scene_has_no_register_system(self) -> None:
        scene = _MinimalScene()
        assert not hasattr(scene, "register_system")

    def test_scene_has_no_add_system(self) -> None:
        scene = _MinimalScene()
        assert not hasattr(scene, "add_system")

    def test_scene_has_no_systems_attribute(self) -> None:
        scene = _MinimalScene()
        assert not hasattr(scene, "systems")

    def test_scene_has_no_remove_system(self) -> None:
        scene = _MinimalScene()
        assert not hasattr(scene, "remove_system")


# ---------------------------------------------------------------------------
# Update order is attachment order, not a system graph
# ---------------------------------------------------------------------------


class TestUpdateOrderIsAttachmentOrder:
    """Component update order follows dict insertion order, not a system graph."""

    def test_update_order_matches_attachment_order(self) -> None:
        """Components update in the order they were attached."""
        order: list[str] = []

        class _First(Component):
            def update(self, dt: float) -> None:
                order.append("first")

        class _Second(Component):
            def update(self, dt: float) -> None:
                order.append("second")

        class _Third(Component):
            def update(self, dt: float) -> None:
                order.append("third")

        e = Entity(entity_id=5010)
        e.add_component(_First())
        e.add_component(_Second())
        e.add_component(_Third())

        e.update(1 / 30)

        assert order == ["first", "second", "third"]

    def test_no_priority_or_ordering_attribute(self) -> None:
        """Components have no priority field — order is implicit."""
        c = Component()
        assert not hasattr(c, "priority")
        assert not hasattr(c, "order")


# ---------------------------------------------------------------------------
# No global entity registry / world
# ---------------------------------------------------------------------------


class TestNoGlobalRegistry:
    """There is no World object or global entity registry."""

    def test_no_world_in_wyby(self) -> None:
        import wyby
        assert not hasattr(wyby, "World")

    def test_no_world_module(self) -> None:
        with pytest.raises(ModuleNotFoundError):
            import wyby.world  # type: ignore[import-not-found]  # noqa: F401

    def test_entities_belong_to_scenes_not_global(self) -> None:
        """An entity can be in multiple scenes — there is no global owner."""
        scene_a = _MinimalScene()
        scene_b = _MinimalScene()
        e = Entity(entity_id=5020)

        scene_a.add_entity(e)
        scene_b.add_entity(e)

        assert e in scene_a.entities
        assert e in scene_b.entities


# ---------------------------------------------------------------------------
# Manual "system" pattern works
# ---------------------------------------------------------------------------


class TestManualSystemPattern:
    """The intended pattern: explicit loops in scene.update()."""

    def test_manual_iteration_in_scene_update(self) -> None:
        """A scene subclass can manually iterate and update entities."""

        class _GameScene(Scene):
            def update(self, dt: float) -> None:
                for entity in self.get_entities_by_component(_Counter):
                    entity.update(dt)

            def render(self) -> None:
                pass

        scene = _GameScene()
        e1 = Entity(entity_id=5030)
        e2 = Entity(entity_id=5031)
        c1 = _Counter()
        c2 = _Counter()
        e1.add_component(c1)
        e2.add_component(c2)
        scene.add_entity(e1)
        scene.add_entity(e2)

        scene.update(1 / 30)

        assert c1.call_count == 1
        assert c2.call_count == 1

    def test_selective_update_by_tag(self) -> None:
        """Games can selectively update subsets of entities."""

        class _SelectiveScene(Scene):
            def update(self, dt: float) -> None:
                # Only update entities tagged "active".
                for entity in self.get_entities_by_tag("active"):
                    entity.update(dt)

            def render(self) -> None:
                pass

        scene = _SelectiveScene()
        active = Entity(entity_id=5040, tags=["active"])
        paused = Entity(entity_id=5041, tags=["paused"])
        c_active = _Counter()
        c_paused = _Counter()
        active.add_component(c_active)
        paused.add_component(c_paused)
        scene.add_entity(active)
        scene.add_entity(paused)

        scene.update(1 / 30)

        assert c_active.call_count == 1
        assert c_paused.call_count == 0  # Not updated — not tagged "active".
