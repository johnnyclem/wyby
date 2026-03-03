"""Tests for wyby.position — Position component for sub-cell entity positioning."""

from __future__ import annotations

import pytest

from wyby.entity import Entity
from wyby.position import Position


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestPositionConstruction:
    """Position creation and default values."""

    def test_default_is_origin(self) -> None:
        p = Position()
        assert p.x == 0.0
        assert p.y == 0.0

    def test_explicit_float_coords(self) -> None:
        p = Position(3.5, 7.2)
        assert p.x == 3.5
        assert p.y == 7.2

    def test_int_coords_stored_as_float(self) -> None:
        p = Position(3, 4)
        assert p.x == 3.0
        assert p.y == 4.0
        assert isinstance(p.x, float)
        assert isinstance(p.y, float)

    def test_negative_coords(self) -> None:
        p = Position(-1.5, -2.0)
        assert p.x == -1.5
        assert p.y == -2.0

    def test_rejects_bool_x(self) -> None:
        with pytest.raises(TypeError, match="x must be a number"):
            Position(True, 0.0)

    def test_rejects_bool_y(self) -> None:
        with pytest.raises(TypeError, match="y must be a number"):
            Position(0.0, False)

    def test_rejects_string_x(self) -> None:
        with pytest.raises(TypeError, match="x must be a number"):
            Position("3", 0.0)  # type: ignore[arg-type]

    def test_rejects_string_y(self) -> None:
        with pytest.raises(TypeError, match="y must be a number"):
            Position(0.0, "4")  # type: ignore[arg-type]

    def test_rejects_none_x(self) -> None:
        with pytest.raises(TypeError, match="x must be a number"):
            Position(None, 0.0)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Properties and setters
# ---------------------------------------------------------------------------


class TestPositionProperties:
    """x, y, and xy property access."""

    def test_set_x(self) -> None:
        p = Position()
        p.x = 5.5
        assert p.x == 5.5

    def test_set_y(self) -> None:
        p = Position()
        p.y = -3.0
        assert p.y == -3.0

    def test_set_x_with_int(self) -> None:
        p = Position()
        p.x = 10
        assert p.x == 10.0
        assert isinstance(p.x, float)

    def test_set_x_rejects_bool(self) -> None:
        p = Position()
        with pytest.raises(TypeError, match="x must be a number"):
            p.x = True  # type: ignore[assignment]

    def test_set_y_rejects_string(self) -> None:
        p = Position()
        with pytest.raises(TypeError, match="y must be a number"):
            p.y = "bad"  # type: ignore[assignment]

    def test_xy_tuple(self) -> None:
        p = Position(1.0, 2.0)
        assert p.xy == (1.0, 2.0)

    def test_set_xy(self) -> None:
        p = Position()
        p.xy = (3.0, 4.0)
        assert p.x == 3.0
        assert p.y == 4.0

    def test_set_xy_with_ints(self) -> None:
        p = Position()
        p.xy = (3, 4)
        assert p.x == 3.0
        assert p.y == 4.0

    def test_set_xy_rejects_non_tuple(self) -> None:
        p = Position()
        with pytest.raises(TypeError, match="xy must be a .* tuple"):
            p.xy = [1.0, 2.0]  # type: ignore[assignment]

    def test_set_xy_rejects_wrong_length(self) -> None:
        p = Position()
        with pytest.raises(TypeError, match="xy must be a .* tuple"):
            p.xy = (1.0, 2.0, 3.0)  # type: ignore[assignment]

    def test_set_xy_rejects_bool_in_tuple(self) -> None:
        p = Position()
        with pytest.raises(TypeError, match="x must be a number"):
            p.xy = (True, 0.0)  # type: ignore[assignment]

    def test_xy_returns_new_tuple_each_call(self) -> None:
        p = Position(1.0, 2.0)
        t1 = p.xy
        t2 = p.xy
        assert t1 == t2
        # Identity not guaranteed, but values are equal.


# ---------------------------------------------------------------------------
# Entity attachment
# ---------------------------------------------------------------------------


class TestPositionAttachment:
    """Position component attaches to entities via standard mechanism."""

    def test_attach_to_entity(self) -> None:
        e = Entity(entity_id=100)
        pos = Position(5.0, 10.0)
        e.add_component(pos)
        assert pos.entity is e

    def test_detach_from_entity(self) -> None:
        e = Entity(entity_id=101)
        pos = Position(5.0, 10.0)
        e.add_component(pos)
        removed = e.remove_component(Position)
        assert removed is pos
        assert pos.entity is None

    def test_one_position_per_entity(self) -> None:
        e = Entity(entity_id=102)
        e.add_component(Position(1.0, 2.0))
        with pytest.raises(ValueError, match="already has a"):
            e.add_component(Position(3.0, 4.0))


# ---------------------------------------------------------------------------
# Repr
# ---------------------------------------------------------------------------


class TestPositionRepr:
    """Position __repr__ output."""

    def test_repr_detached(self) -> None:
        p = Position(1.5, 2.5)
        assert repr(p) == "Position(x=1.5, y=2.5, detached)"

    def test_repr_attached(self) -> None:
        e = Entity(entity_id=50)
        p = Position(3.0, 4.0)
        e.add_component(p)
        assert repr(p) == "Position(x=3.0, y=4.0, entity_id=50)"


# ---------------------------------------------------------------------------
# Import from package root
# ---------------------------------------------------------------------------


class TestPositionImport:
    """Position is accessible from the wyby package root."""

    def test_import_from_wyby(self) -> None:
        from wyby import Position as P
        assert P is Position
