"""Tests for wyby.entity — simple Entity class with id, position, and tags."""

from __future__ import annotations

import pytest

from wyby.component import Component
from wyby.entity import Entity


# ---------------------------------------------------------------------------
# Construction and auto-id
# ---------------------------------------------------------------------------


class TestEntityConstruction:
    """Entity creation, default values, and auto-id assignment."""

    def test_default_position_is_origin(self) -> None:
        e = Entity()
        assert e.x == 0
        assert e.y == 0
        assert e.position == (0, 0)

    def test_explicit_position(self) -> None:
        e = Entity(5, 10)
        assert e.x == 5
        assert e.y == 10

    def test_auto_id_is_positive_int(self) -> None:
        e = Entity()
        assert isinstance(e.id, int)
        assert e.id >= 1

    def test_auto_ids_are_unique(self) -> None:
        e1 = Entity()
        e2 = Entity()
        assert e1.id != e2.id

    def test_auto_ids_are_monotonically_increasing(self) -> None:
        e1 = Entity()
        e2 = Entity()
        assert e2.id > e1.id

    def test_explicit_entity_id(self) -> None:
        e = Entity(entity_id=42)
        assert e.id == 42

    def test_explicit_entity_id_zero(self) -> None:
        e = Entity(entity_id=0)
        assert e.id == 0

    def test_negative_position_allowed(self) -> None:
        """Negative positions are valid (off-screen / scrolling viewport)."""
        e = Entity(-3, -7)
        assert e.x == -3
        assert e.y == -7

    def test_tags_from_constructor(self) -> None:
        e = Entity(tags=["enemy", "boss"])
        assert e.has_tag("enemy")
        assert e.has_tag("boss")

    def test_tags_deduplicated(self) -> None:
        e = Entity(tags=["enemy", "enemy", "enemy"])
        assert e.tags == frozenset({"enemy"})

    def test_no_tags_by_default(self) -> None:
        e = Entity()
        assert e.tags == frozenset()

    def test_repr_without_tags(self) -> None:
        e = Entity(3, 4, entity_id=99)
        assert repr(e) == "Entity(id=99, x=3, y=4)"

    def test_repr_with_tags(self) -> None:
        e = Entity(0, 0, tags=["wall"], entity_id=1)
        r = repr(e)
        assert "Entity(id=1" in r
        assert "wall" in r


# ---------------------------------------------------------------------------
# Type validation on construction
# ---------------------------------------------------------------------------


class TestEntityTypeValidation:
    """Entity rejects invalid types at construction time."""

    def test_x_must_be_int(self) -> None:
        with pytest.raises(TypeError, match="x must be an int"):
            Entity(1.5, 0)  # type: ignore[arg-type]

    def test_y_must_be_int(self) -> None:
        with pytest.raises(TypeError, match="y must be an int"):
            Entity(0, 2.0)  # type: ignore[arg-type]

    def test_x_rejects_bool(self) -> None:
        with pytest.raises(TypeError, match="x must be an int"):
            Entity(True, 0)  # type: ignore[arg-type]

    def test_y_rejects_bool(self) -> None:
        with pytest.raises(TypeError, match="y must be an int"):
            Entity(0, False)  # type: ignore[arg-type]

    def test_entity_id_must_be_int(self) -> None:
        with pytest.raises(TypeError, match="entity_id must be an int"):
            Entity(entity_id="abc")  # type: ignore[arg-type]

    def test_entity_id_rejects_bool(self) -> None:
        with pytest.raises(TypeError, match="entity_id must be an int"):
            Entity(entity_id=True)  # type: ignore[arg-type]

    def test_entity_id_rejects_negative(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            Entity(entity_id=-1)

    def test_tag_must_be_string(self) -> None:
        with pytest.raises(TypeError, match="tags must be strings"):
            Entity(tags=[123])  # type: ignore[list-item]

    def test_tag_must_be_nonempty(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            Entity(tags=[""])


# ---------------------------------------------------------------------------
# Position mutation
# ---------------------------------------------------------------------------


class TestEntityPosition:
    """Position getters, setters, and the move() method."""

    def test_set_x(self) -> None:
        e = Entity()
        e.x = 10
        assert e.x == 10

    def test_set_y(self) -> None:
        e = Entity()
        e.y = 20
        assert e.y == 20

    def test_set_position_tuple(self) -> None:
        e = Entity()
        e.position = (5, 15)
        assert e.x == 5
        assert e.y == 15
        assert e.position == (5, 15)

    def test_position_rejects_non_tuple(self) -> None:
        e = Entity()
        with pytest.raises(TypeError, match="tuple"):
            e.position = [1, 2]  # type: ignore[assignment]

    def test_position_rejects_wrong_length(self) -> None:
        e = Entity()
        with pytest.raises(TypeError, match="tuple"):
            e.position = (1, 2, 3)  # type: ignore[assignment]

    def test_position_rejects_non_int_x(self) -> None:
        e = Entity()
        with pytest.raises(TypeError, match="position x must be an int"):
            e.position = (1.0, 2)  # type: ignore[assignment]

    def test_position_rejects_non_int_y(self) -> None:
        e = Entity()
        with pytest.raises(TypeError, match="position y must be an int"):
            e.position = (1, 2.0)  # type: ignore[assignment]

    def test_x_setter_rejects_float(self) -> None:
        e = Entity()
        with pytest.raises(TypeError, match="x must be an int"):
            e.x = 1.5  # type: ignore[assignment]

    def test_y_setter_rejects_bool(self) -> None:
        e = Entity()
        with pytest.raises(TypeError, match="y must be an int"):
            e.y = True  # type: ignore[assignment]

    def test_move_positive(self) -> None:
        e = Entity(5, 10)
        e.move(3, -2)
        assert e.position == (8, 8)

    def test_move_zero(self) -> None:
        e = Entity(5, 10)
        e.move(0, 0)
        assert e.position == (5, 10)

    def test_move_to_negative(self) -> None:
        e = Entity(1, 1)
        e.move(-5, -5)
        assert e.position == (-4, -4)

    def test_move_rejects_float_dx(self) -> None:
        e = Entity()
        with pytest.raises(TypeError, match="dx must be an int"):
            e.move(1.0, 0)  # type: ignore[arg-type]

    def test_move_rejects_float_dy(self) -> None:
        e = Entity()
        with pytest.raises(TypeError, match="dy must be an int"):
            e.move(0, 1.0)  # type: ignore[arg-type]

    def test_move_rejects_bool_dx(self) -> None:
        e = Entity()
        with pytest.raises(TypeError, match="dx must be an int"):
            e.move(True, 0)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------


class TestEntityTags:
    """Tag add/remove/query operations."""

    def test_add_tag(self) -> None:
        e = Entity()
        e.add_tag("enemy")
        assert e.has_tag("enemy")

    def test_add_tag_idempotent(self) -> None:
        e = Entity()
        e.add_tag("enemy")
        e.add_tag("enemy")
        assert e.tags == frozenset({"enemy"})

    def test_remove_tag(self) -> None:
        e = Entity(tags=["enemy"])
        e.remove_tag("enemy")
        assert not e.has_tag("enemy")

    def test_remove_tag_not_found(self) -> None:
        e = Entity()
        with pytest.raises(KeyError):
            e.remove_tag("nonexistent")

    def test_has_tag_false(self) -> None:
        e = Entity()
        assert not e.has_tag("anything")

    def test_tags_returns_frozenset(self) -> None:
        e = Entity(tags=["a", "b"])
        t = e.tags
        assert isinstance(t, frozenset)

    def test_add_tag_rejects_non_string(self) -> None:
        e = Entity()
        with pytest.raises(TypeError, match="tag must be a string"):
            e.add_tag(123)  # type: ignore[arg-type]

    def test_add_tag_rejects_empty(self) -> None:
        e = Entity()
        with pytest.raises(ValueError, match="non-empty"):
            e.add_tag("")

    def test_multiple_tags(self) -> None:
        e = Entity(tags=["enemy", "boss", "undead"])
        assert e.tags == frozenset({"enemy", "boss", "undead"})


# ---------------------------------------------------------------------------
# Equality and hashing
# ---------------------------------------------------------------------------


class TestEntityEquality:
    """Equality is based on id alone."""

    def test_same_id_equal(self) -> None:
        e1 = Entity(0, 0, entity_id=100)
        e2 = Entity(5, 5, entity_id=100)
        assert e1 == e2

    def test_different_id_not_equal(self) -> None:
        e1 = Entity(0, 0, entity_id=200)
        e2 = Entity(0, 0, entity_id=201)
        assert e1 != e2

    def test_not_equal_to_non_entity(self) -> None:
        e = Entity(entity_id=300)
        assert e != "not an entity"
        assert e != 300

    def test_hashable(self) -> None:
        e = Entity(entity_id=400)
        s = {e}
        assert e in s

    def test_same_id_same_hash(self) -> None:
        e1 = Entity(entity_id=500)
        e2 = Entity(entity_id=500)
        assert hash(e1) == hash(e2)

    def test_usable_in_dict(self) -> None:
        e = Entity(entity_id=600)
        d = {e: "value"}
        assert d[e] == "value"


# ---------------------------------------------------------------------------
# Id is read-only
# ---------------------------------------------------------------------------


class TestEntityIdReadOnly:
    """The id property has no setter."""

    def test_id_cannot_be_set(self) -> None:
        e = Entity()
        with pytest.raises(AttributeError):
            e.id = 999  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Component helpers
# ---------------------------------------------------------------------------


class _Health(Component):
    """Concrete component for testing add/remove."""

    def __init__(self, hp: int = 100) -> None:
        super().__init__()
        self.hp = hp
        self.attach_calls: list[int] = []
        self.detach_calls: list[int] = []

    def on_attach(self, entity: Entity) -> None:
        self.attach_calls.append(entity.id)

    def on_detach(self, entity: Entity) -> None:
        self.detach_calls.append(entity.id)


class _Velocity(Component):
    """Second component type for multi-component tests."""

    def __init__(self, vx: float = 0.0, vy: float = 0.0) -> None:
        super().__init__()
        self.vx = vx
        self.vy = vy


class _AdvancedHealth(_Health):
    """Subclass of _Health — keyed separately (exact class match)."""
    pass


# ---------------------------------------------------------------------------
# add_component
# ---------------------------------------------------------------------------


class TestAddComponent:
    """Entity.add_component attaches a component and calls on_attach."""

    def test_add_sets_entity_back_reference(self) -> None:
        e = Entity(entity_id=1)
        h = _Health()
        e.add_component(h)
        assert h.entity is e

    def test_add_calls_on_attach(self) -> None:
        e = Entity(entity_id=2)
        h = _Health()
        e.add_component(h)
        assert h.attach_calls == [2]

    def test_add_multiple_component_types(self) -> None:
        e = Entity(entity_id=3)
        h = _Health()
        v = _Velocity(1.0, 2.0)
        e.add_component(h)
        e.add_component(v)
        assert h.entity is e
        assert v.entity is e

    def test_add_subclass_and_base_are_separate(self) -> None:
        """AdvancedHealth and Health are distinct types — both can be added."""
        e = Entity(entity_id=4)
        h = _Health()
        ah = _AdvancedHealth()
        e.add_component(h)
        e.add_component(ah)
        assert h.entity is e
        assert ah.entity is e

    def test_add_duplicate_type_raises_value_error(self) -> None:
        e = Entity(entity_id=5)
        e.add_component(_Health(50))
        with pytest.raises(ValueError, match="already has"):
            e.add_component(_Health(75))

    def test_add_already_attached_raises_runtime_error(self) -> None:
        e1 = Entity(entity_id=6)
        e2 = Entity(entity_id=7)
        h = _Health()
        e1.add_component(h)
        with pytest.raises(RuntimeError, match="already attached"):
            e2.add_component(h)

    def test_add_non_component_raises_type_error(self) -> None:
        e = Entity(entity_id=8)
        with pytest.raises(TypeError, match="must be a Component instance"):
            e.add_component("not a component")  # type: ignore[arg-type]

    def test_add_non_component_dict_raises_type_error(self) -> None:
        e = Entity(entity_id=9)
        with pytest.raises(TypeError, match="must be a Component instance"):
            e.add_component({"hp": 100})  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# remove_component
# ---------------------------------------------------------------------------


class TestRemoveComponent:
    """Entity.remove_component detaches a component and calls on_detach."""

    def test_remove_clears_entity_back_reference(self) -> None:
        e = Entity(entity_id=10)
        h = _Health()
        e.add_component(h)
        e.remove_component(_Health)
        assert h.entity is None

    def test_remove_calls_on_detach(self) -> None:
        e = Entity(entity_id=11)
        h = _Health()
        e.add_component(h)
        e.remove_component(_Health)
        assert h.detach_calls == [11]

    def test_remove_returns_the_component(self) -> None:
        e = Entity(entity_id=12)
        h = _Health(42)
        e.add_component(h)
        removed = e.remove_component(_Health)
        assert removed is h
        assert removed.hp == 42

    def test_remove_nonexistent_raises_key_error(self) -> None:
        e = Entity(entity_id=13)
        with pytest.raises(KeyError, match="no.*_Health"):
            e.remove_component(_Health)

    def test_remove_wrong_type_raises_type_error(self) -> None:
        e = Entity(entity_id=14)
        with pytest.raises(TypeError, match="must be a Component subclass"):
            e.remove_component("Health")  # type: ignore[arg-type]

    def test_remove_non_subclass_raises_type_error(self) -> None:
        e = Entity(entity_id=15)
        with pytest.raises(TypeError, match="must be a Component subclass"):
            e.remove_component(int)  # type: ignore[arg-type]

    def test_remove_only_target_type(self) -> None:
        """Removing one type leaves others untouched."""
        e = Entity(entity_id=16)
        h = _Health()
        v = _Velocity()
        e.add_component(h)
        e.add_component(v)
        e.remove_component(_Health)
        assert h.entity is None
        assert v.entity is e

    def test_removed_component_can_be_reattached(self) -> None:
        """After removal, the component can be added to another entity."""
        e1 = Entity(entity_id=17)
        e2 = Entity(entity_id=18)
        h = _Health()
        e1.add_component(h)
        e1.remove_component(_Health)
        e2.add_component(h)
        assert h.entity is e2
        assert h.attach_calls == [17, 18]

    def test_on_detach_entity_still_set(self) -> None:
        """During on_detach, component.entity still points to the entity."""
        entity_during_detach = []

        class _Spy(Component):
            def on_detach(self, entity: Entity) -> None:
                entity_during_detach.append(self.entity)

        e = Entity(entity_id=19)
        s = _Spy()
        e.add_component(s)
        e.remove_component(_Spy)
        assert entity_during_detach == [e]
        # After on_detach completes, entity is cleared.
        assert s.entity is None

    def test_remove_base_does_not_find_subclass(self) -> None:
        """Exact class match — removing Health won't find AdvancedHealth."""
        e = Entity(entity_id=20)
        e.add_component(_AdvancedHealth())
        with pytest.raises(KeyError):
            e.remove_component(_Health)


# ---------------------------------------------------------------------------
# update
# ---------------------------------------------------------------------------


class _Counter(Component):
    """Component that counts update calls and records dt values."""

    def __init__(self) -> None:
        super().__init__()
        self.call_count = 0
        self.dt_values: list[float] = []

    def update(self, dt: float) -> None:
        self.call_count += 1
        self.dt_values.append(dt)


class _Exploding(Component):
    """Component whose update raises an exception."""

    def update(self, dt: float) -> None:
        raise RuntimeError("boom")


class TestEntityUpdate:
    """Entity.update(dt) delegates to all attached component updates."""

    def test_update_calls_component_update(self) -> None:
        e = Entity(entity_id=700)
        c = _Counter()
        e.add_component(c)

        e.update(1 / 30)

        assert c.call_count == 1
        assert c.dt_values == [pytest.approx(1 / 30)]

    def test_update_passes_dt_to_all_components(self) -> None:
        e = Entity(entity_id=701)
        c1 = _Counter()
        # Use distinct types so both can attach.

        class _Counter2(_Counter):
            pass

        c2 = _Counter2()
        e.add_component(c1)
        e.add_component(c2)

        e.update(0.5)

        assert c1.dt_values == [0.5]
        assert c2.dt_values == [0.5]

    def test_update_with_no_components_is_noop(self) -> None:
        """No error when entity has no components."""
        e = Entity(entity_id=702)
        e.update(1.0)  # Should not raise.

    def test_update_accumulates_across_ticks(self) -> None:
        e = Entity(entity_id=703)
        c = _Counter()
        e.add_component(c)

        for _ in range(10):
            e.update(1 / 30)

        assert c.call_count == 10

    def test_update_exception_propagates(self) -> None:
        """A component exception stops the update and propagates."""
        e = Entity(entity_id=704)
        e.add_component(_Exploding())
        with pytest.raises(RuntimeError, match="boom"):
            e.update(1.0)

    def test_update_exception_stops_remaining_components(self) -> None:
        """Components after the failing one are not updated."""
        e = Entity(entity_id=705)
        before = _Counter()
        exploding = _Exploding()

        class _CounterAfter(_Counter):
            pass

        after = _CounterAfter()

        e.add_component(before)
        e.add_component(exploding)
        e.add_component(after)

        with pytest.raises(RuntimeError, match="boom"):
            e.update(1.0)

        # The component before the exception was updated.
        assert before.call_count == 1
        # The component after was not reached.
        assert after.call_count == 0

    def test_update_safe_during_component_removal(self) -> None:
        """Removing a component during update does not raise RuntimeError.

        Caveat: the removed component may still be updated in the
        current tick because iteration uses a snapshot taken before
        the update loop begins.
        """
        class _SelfRemover(Component):
            def __init__(self) -> None:
                super().__init__()
                self.updated = False

            def update(self, dt: float) -> None:
                self.updated = True
                if self.entity is not None:
                    self.entity.remove_component(type(self))

        e = Entity(entity_id=706)
        remover = _SelfRemover()
        c = _Counter()
        e.add_component(remover)
        e.add_component(c)

        # Should not raise RuntimeError from dict mutation.
        e.update(1.0)

        assert remover.updated
        assert c.call_count == 1

    def test_update_with_real_velocity_and_position(self) -> None:
        """Integration: Entity.update drives Velocity which moves Position."""
        from wyby.position import Position
        from wyby.velocity import Velocity

        e = Entity(0, 0, entity_id=707)
        pos = Position(0.0, 0.0)
        vel = Velocity(10.0, 5.0)
        e.add_component(pos)
        e.add_component(vel)

        e.update(0.1)

        assert pos.x == pytest.approx(1.0)
        assert pos.y == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# get_component
# ---------------------------------------------------------------------------


class TestGetComponent:
    """Entity.get_component returns the component or None."""

    def test_get_attached_component(self) -> None:
        e = Entity(entity_id=900)
        h = _Health(50)
        e.add_component(h)
        assert e.get_component(_Health) is h

    def test_get_returns_none_when_absent(self) -> None:
        e = Entity(entity_id=901)
        assert e.get_component(_Health) is None

    def test_get_exact_class_only(self) -> None:
        """get_component(Health) does not return AdvancedHealth."""
        e = Entity(entity_id=902)
        ah = _AdvancedHealth()
        e.add_component(ah)
        assert e.get_component(_Health) is None
        assert e.get_component(_AdvancedHealth) is ah

    def test_get_multiple_types(self) -> None:
        e = Entity(entity_id=903)
        h = _Health()
        v = _Velocity(1.0, 2.0)
        e.add_component(h)
        e.add_component(v)
        assert e.get_component(_Health) is h
        assert e.get_component(_Velocity) is v

    def test_get_after_remove_returns_none(self) -> None:
        e = Entity(entity_id=904)
        e.add_component(_Health())
        e.remove_component(_Health)
        assert e.get_component(_Health) is None

    def test_get_non_component_type_raises_type_error(self) -> None:
        e = Entity(entity_id=905)
        with pytest.raises(TypeError, match="must be a Component subclass"):
            e.get_component(str)  # type: ignore[arg-type]

    def test_get_non_type_raises_type_error(self) -> None:
        e = Entity(entity_id=906)
        with pytest.raises(TypeError, match="must be a Component subclass"):
            e.get_component("Health")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# has_component
# ---------------------------------------------------------------------------


class TestHasComponent:
    """Entity.has_component checks for component presence."""

    def test_has_returns_true_when_attached(self) -> None:
        e = Entity(entity_id=910)
        e.add_component(_Health())
        assert e.has_component(_Health) is True

    def test_has_returns_false_when_absent(self) -> None:
        e = Entity(entity_id=911)
        assert e.has_component(_Health) is False

    def test_has_exact_class_only(self) -> None:
        """has_component(Health) is False when only AdvancedHealth is attached."""
        e = Entity(entity_id=912)
        e.add_component(_AdvancedHealth())
        assert e.has_component(_Health) is False
        assert e.has_component(_AdvancedHealth) is True

    def test_has_after_remove(self) -> None:
        e = Entity(entity_id=913)
        e.add_component(_Health())
        e.remove_component(_Health)
        assert e.has_component(_Health) is False

    def test_has_non_component_type_raises_type_error(self) -> None:
        e = Entity(entity_id=914)
        with pytest.raises(TypeError, match="must be a Component subclass"):
            e.has_component(int)  # type: ignore[arg-type]

    def test_has_non_type_raises_type_error(self) -> None:
        e = Entity(entity_id=915)
        with pytest.raises(TypeError, match="must be a Component subclass"):
            e.has_component(42)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Import from package root
# ---------------------------------------------------------------------------


class TestEntityImport:
    """Entity is accessible from the wyby package root."""

    def test_import_from_wyby(self) -> None:
        from wyby import Entity as E
        assert E is Entity
