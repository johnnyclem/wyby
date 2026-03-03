"""Tests for wyby.component — Component base class for entity composition."""

from __future__ import annotations

import pytest

from wyby.component import Component
from wyby.entity import Entity


# ---------------------------------------------------------------------------
# Helpers — concrete subclasses for testing
# ---------------------------------------------------------------------------


class Health(Component):
    """A simple concrete component for testing."""

    def __init__(self, hp: int = 100) -> None:
        super().__init__()
        self.hp = hp
        self.max_hp = hp
        self.update_count = 0

    def update(self, dt: float) -> None:
        self.update_count += 1

    def on_attach(self, entity: Entity) -> None:
        self.attached_to_id = entity.id

    def on_detach(self, entity: Entity) -> None:
        self.detached_from_id = entity.id


class Velocity(Component):
    """Another concrete component to test multiple component types."""

    def __init__(self, vx: float = 0.0, vy: float = 0.0) -> None:
        super().__init__()
        self.vx = vx
        self.vy = vy


class EmptyComponent(Component):
    """A component with no overrides — tests default behaviour."""
    pass


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestComponentConstruction:
    """Component creation and default state."""

    def test_bare_component_has_no_entity(self) -> None:
        c = Component()
        assert c.entity is None

    def test_subclass_has_no_entity(self) -> None:
        h = Health(50)
        assert h.entity is None

    def test_subclass_preserves_custom_attrs(self) -> None:
        h = Health(75)
        assert h.hp == 75
        assert h.max_hp == 75

    def test_repr_when_detached(self) -> None:
        c = Component()
        assert repr(c) == "Component(detached)"

    def test_repr_subclass_when_detached(self) -> None:
        h = Health()
        assert repr(h) == "Health(detached)"


# ---------------------------------------------------------------------------
# Entity property
# ---------------------------------------------------------------------------


class TestComponentEntity:
    """The entity back-reference property."""

    def test_entity_is_none_by_default(self) -> None:
        c = Component()
        assert c.entity is None

    def test_entity_set_via_internal_attr(self) -> None:
        """The _entity attr is set by the attachment mechanism."""
        c = Component()
        e = Entity(entity_id=42)
        c._entity = e
        assert c.entity is e

    def test_entity_is_read_only_property(self) -> None:
        """The entity property has no setter."""
        c = Component()
        with pytest.raises(AttributeError):
            c.entity = Entity()  # type: ignore[misc]

    def test_repr_when_attached(self) -> None:
        c = Component()
        c._entity = Entity(entity_id=99)
        assert repr(c) == "Component(entity_id=99)"

    def test_repr_subclass_when_attached(self) -> None:
        h = Health()
        h._entity = Entity(entity_id=7)
        assert repr(h) == "Health(entity_id=7)"


# ---------------------------------------------------------------------------
# Lifecycle hooks
# ---------------------------------------------------------------------------


class TestComponentLifecycle:
    """on_attach and on_detach lifecycle hooks."""

    def test_on_attach_receives_entity(self) -> None:
        h = Health()
        e = Entity(entity_id=10)
        h._entity = e
        h.on_attach(e)
        assert h.attached_to_id == 10

    def test_on_detach_receives_entity(self) -> None:
        h = Health()
        e = Entity(entity_id=20)
        h._entity = e
        h.on_detach(e)
        assert h.detached_from_id == 20

    def test_default_on_attach_does_nothing(self) -> None:
        """Base Component.on_attach is a no-op — should not raise."""
        c = Component()
        e = Entity()
        c.on_attach(e)  # Should not raise

    def test_default_on_detach_does_nothing(self) -> None:
        """Base Component.on_detach is a no-op — should not raise."""
        c = Component()
        e = Entity()
        c.on_detach(e)  # Should not raise

    def test_empty_subclass_lifecycle_does_not_raise(self) -> None:
        """Subclass with no overrides inherits no-op lifecycle."""
        c = EmptyComponent()
        e = Entity()
        c.on_attach(e)
        c.on_detach(e)


# ---------------------------------------------------------------------------
# Update hook
# ---------------------------------------------------------------------------


class TestComponentUpdate:
    """The update(dt) per-tick hook."""

    def test_update_is_called(self) -> None:
        h = Health()
        assert h.update_count == 0
        h.update(1 / 30)
        assert h.update_count == 1

    def test_update_called_multiple_times(self) -> None:
        h = Health()
        for _ in range(10):
            h.update(1 / 30)
        assert h.update_count == 10

    def test_default_update_does_nothing(self) -> None:
        """Base Component.update is a no-op — should not raise."""
        c = Component()
        c.update(0.033)  # Should not raise

    def test_update_works_when_detached(self) -> None:
        """update() does not require an entity — works while detached."""
        h = Health()
        assert h.entity is None
        h.update(0.1)  # Should not raise
        assert h.update_count == 1

    def test_empty_subclass_update_does_not_raise(self) -> None:
        """Subclass with no overrides inherits no-op update."""
        c = EmptyComponent()
        c.update(0.5)  # Should not raise


# ---------------------------------------------------------------------------
# Subclass identity
# ---------------------------------------------------------------------------


class TestComponentIdentity:
    """Component subclasses are distinct types."""

    def test_different_subclasses_are_different_types(self) -> None:
        h = Health()
        v = Velocity()
        assert type(h) is not type(v)

    def test_subclass_is_instance_of_component(self) -> None:
        h = Health()
        assert isinstance(h, Component)

    def test_nested_subclass_is_instance_of_component(self) -> None:
        class AdvancedHealth(Health):
            pass
        ah = AdvancedHealth()
        assert isinstance(ah, Component)
        assert isinstance(ah, Health)

    def test_nested_subclass_is_distinct_type(self) -> None:
        """AdvancedHealth is not Health — component keying uses exact class."""
        class AdvancedHealth(Health):
            pass
        assert AdvancedHealth is not Health


# ---------------------------------------------------------------------------
# Slots
# ---------------------------------------------------------------------------


class TestComponentSlots:
    """Component uses __slots__ for memory efficiency."""

    def test_base_component_uses_slots(self) -> None:
        assert "__slots__" in Component.__dict__
        assert "_entity" in Component.__slots__

    def test_base_component_no_dict(self) -> None:
        """Base Component should not have __dict__ (slots only)."""
        c = Component()
        assert not hasattr(c, "__dict__")

    def test_subclass_can_add_dict(self) -> None:
        """Subclasses without __slots__ get a __dict__ — that's fine."""
        h = Health()
        # Health doesn't define __slots__, so it gets __dict__
        assert hasattr(h, "__dict__")


# ---------------------------------------------------------------------------
# Import from package root
# ---------------------------------------------------------------------------


class TestComponentImport:
    """Component is accessible from the wyby package root."""

    def test_import_from_wyby(self) -> None:
        from wyby import Component as C
        assert C is Component
