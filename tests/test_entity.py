"""Tests for wyby.entity — simple Entity class with id, position, and tags."""

from __future__ import annotations

import pytest

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
# Import from package root
# ---------------------------------------------------------------------------


class TestEntityImport:
    """Entity is accessible from the wyby package root."""

    def test_import_from_wyby(self) -> None:
        from wyby import Entity as E
        assert E is Entity
