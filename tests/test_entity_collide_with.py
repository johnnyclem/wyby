"""Tests for Entity.collide_with — AABB overlap between entities."""

from __future__ import annotations

import pytest

from wyby.entity import Entity


# ---------------------------------------------------------------------------
# Basic overlap / no-overlap
# ---------------------------------------------------------------------------


class TestCollideWithBasic:
    """Default 1x1 bounding boxes: entities collide only at same cell."""

    def test_same_position_collides(self) -> None:
        a = Entity(5, 5, entity_id=9000)
        b = Entity(5, 5, entity_id=9001)
        assert a.collide_with(b)

    def test_different_positions_no_collision(self) -> None:
        a = Entity(0, 0, entity_id=9010)
        b = Entity(1, 0, entity_id=9011)
        assert not a.collide_with(b)

    def test_adjacent_no_collision_default(self) -> None:
        """Adjacent 1x1 entities do not collide (no shared cell)."""
        a = Entity(3, 3, entity_id=9020)
        b = Entity(4, 3, entity_id=9021)
        assert not a.collide_with(b)

    def test_diagonal_no_collision_default(self) -> None:
        a = Entity(0, 0, entity_id=9030)
        b = Entity(1, 1, entity_id=9031)
        assert not a.collide_with(b)

    def test_symmetry(self) -> None:
        """a.collide_with(b) == b.collide_with(a)."""
        a = Entity(2, 2, entity_id=9040)
        b = Entity(2, 2, entity_id=9041)
        assert a.collide_with(b)
        assert b.collide_with(a)


# ---------------------------------------------------------------------------
# Custom bounding box sizes
# ---------------------------------------------------------------------------


class TestCollideWithCustomSizes:
    """Entities with multi-cell bounding boxes."""

    def test_larger_self_overlaps_nearby(self) -> None:
        a = Entity(0, 0, entity_id=9100)
        b = Entity(2, 0, entity_id=9101)
        # a is 3 wide, b is 1 wide at x=2 => overlap at column 2
        assert a.collide_with(b, self_width=3, self_height=1)

    def test_larger_other_overlaps_nearby(self) -> None:
        a = Entity(2, 0, entity_id=9110)
        b = Entity(0, 0, entity_id=9111)
        assert a.collide_with(b, other_width=3, other_height=1)

    def test_both_large_overlap(self) -> None:
        a = Entity(0, 0, entity_id=9120)
        b = Entity(3, 3, entity_id=9121)
        assert a.collide_with(
            b,
            self_width=4,
            self_height=4,
            other_width=2,
            other_height=2,
        )

    def test_both_large_no_overlap(self) -> None:
        a = Entity(0, 0, entity_id=9130)
        b = Entity(5, 0, entity_id=9131)
        assert not a.collide_with(
            b, self_width=3, self_height=3, other_width=2, other_height=2
        )

    def test_edge_touching_overlaps(self) -> None:
        """Boxes sharing an edge overlap (consistent with aabb_overlap)."""
        a = Entity(0, 0, entity_id=9140)
        b = Entity(2, 0, entity_id=9141)
        # a spans columns 0,1 (width=2), b starts at column 2
        # right=0+2=2, b.x=2 => 2 <= 2, no overlap (exclusive bound)
        assert not a.collide_with(b, self_width=2, self_height=1)

    def test_overlapping_by_one_cell(self) -> None:
        a = Entity(0, 0, entity_id=9150)
        b = Entity(2, 0, entity_id=9151)
        # a spans columns 0,1,2 (width=3), b at column 2 => overlap
        assert a.collide_with(b, self_width=3, self_height=1)

    def test_zero_width_never_overlaps(self) -> None:
        a = Entity(5, 5, entity_id=9160)
        b = Entity(5, 5, entity_id=9161)
        assert not a.collide_with(b, self_width=0)

    def test_zero_height_never_overlaps(self) -> None:
        a = Entity(5, 5, entity_id=9170)
        b = Entity(5, 5, entity_id=9171)
        assert not a.collide_with(b, self_height=0)


# ---------------------------------------------------------------------------
# Self-collision
# ---------------------------------------------------------------------------


class TestCollideWithSelf:
    """An entity colliding with itself."""

    def test_self_collision_returns_true(self) -> None:
        e = Entity(3, 3, entity_id=9200)
        assert e.collide_with(e)

    def test_self_collision_destroyed_returns_false(self) -> None:
        e = Entity(3, 3, entity_id=9210)
        e.destroy()
        assert not e.collide_with(e)


# ---------------------------------------------------------------------------
# Destroyed entities
# ---------------------------------------------------------------------------


class TestCollideWithDestroyed:
    """Destroyed entities never collide."""

    def test_self_destroyed(self) -> None:
        a = Entity(5, 5, entity_id=9300)
        b = Entity(5, 5, entity_id=9301)
        a.destroy()
        assert not a.collide_with(b)

    def test_other_destroyed(self) -> None:
        a = Entity(5, 5, entity_id=9310)
        b = Entity(5, 5, entity_id=9311)
        b.destroy()
        assert not a.collide_with(b)

    def test_both_destroyed(self) -> None:
        a = Entity(5, 5, entity_id=9320)
        b = Entity(5, 5, entity_id=9321)
        a.destroy()
        b.destroy()
        assert not a.collide_with(b)


# ---------------------------------------------------------------------------
# Negative and large coordinates
# ---------------------------------------------------------------------------


class TestCollideWithEdgeCases:
    """Negative positions, origin, and large coordinates."""

    def test_negative_positions_collide(self) -> None:
        a = Entity(-3, -3, entity_id=9400)
        b = Entity(-3, -3, entity_id=9401)
        assert a.collide_with(b)

    def test_negative_positions_no_collision(self) -> None:
        a = Entity(-3, -3, entity_id=9410)
        b = Entity(-1, -1, entity_id=9411)
        assert not a.collide_with(b)

    def test_mixed_sign_overlap(self) -> None:
        """Bounding box crosses the origin."""
        a = Entity(-1, -1, entity_id=9420)
        b = Entity(0, 0, entity_id=9421)
        # a with width=2 spans columns -1,0 => overlaps b at 0
        assert a.collide_with(b, self_width=2, self_height=2)

    def test_large_coordinates(self) -> None:
        a = Entity(10000, 20000, entity_id=9430)
        b = Entity(10000, 20000, entity_id=9431)
        assert a.collide_with(b)


# ---------------------------------------------------------------------------
# Type validation
# ---------------------------------------------------------------------------


class TestCollideWithTypeErrors:
    """Invalid argument types raise TypeError."""

    def test_other_not_entity(self) -> None:
        a = Entity(0, 0, entity_id=9500)
        with pytest.raises(TypeError, match="other must be an Entity"):
            a.collide_with("not an entity")  # type: ignore[arg-type]

    def test_other_none(self) -> None:
        a = Entity(0, 0, entity_id=9510)
        with pytest.raises(TypeError, match="other must be an Entity"):
            a.collide_with(None)  # type: ignore[arg-type]

    def test_other_int(self) -> None:
        a = Entity(0, 0, entity_id=9520)
        with pytest.raises(TypeError, match="other must be an Entity"):
            a.collide_with(42)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Symmetry with custom sizes
# ---------------------------------------------------------------------------


class TestCollideWithSymmetry:
    """Overlap result is symmetric when sizes are swapped correctly."""

    def test_asymmetric_sizes_both_directions(self) -> None:
        a = Entity(0, 0, entity_id=9600)
        b = Entity(2, 0, entity_id=9601)
        forward = a.collide_with(
            b, self_width=3, self_height=1, other_width=1, other_height=1
        )
        reverse = b.collide_with(
            a, self_width=1, self_height=1, other_width=3, other_height=1
        )
        assert forward == reverse
