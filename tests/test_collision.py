"""Tests for wyby.collision — AABB collision detection."""

from __future__ import annotations

import pytest

from wyby.collision import AABB, aabb_overlap


# ── AABB construction ────────────────────────────────────────────────

class TestAABBInit:
    """AABB construction and validation."""

    def test_basic_construction(self):
        box = AABB(1, 2, 3, 4)
        assert box.x == 1
        assert box.y == 2
        assert box.width == 3
        assert box.height == 4

    def test_zero_size(self):
        box = AABB(0, 0, 0, 0)
        assert box.width == 0
        assert box.height == 0

    def test_negative_position(self):
        box = AABB(-5, -3, 2, 2)
        assert box.x == -5
        assert box.y == -3

    def test_rejects_float_x(self):
        with pytest.raises(TypeError, match="x must be an int"):
            AABB(1.5, 0, 1, 1)

    def test_rejects_float_y(self):
        with pytest.raises(TypeError, match="y must be an int"):
            AABB(0, 1.5, 1, 1)

    def test_rejects_float_width(self):
        with pytest.raises(TypeError, match="width must be an int"):
            AABB(0, 0, 1.5, 1)

    def test_rejects_float_height(self):
        with pytest.raises(TypeError, match="height must be an int"):
            AABB(0, 0, 1, 1.5)

    def test_rejects_bool_x(self):
        with pytest.raises(TypeError, match="x must be an int"):
            AABB(True, 0, 1, 1)

    def test_rejects_bool_width(self):
        with pytest.raises(TypeError, match="width must be an int"):
            AABB(0, 0, True, 1)

    def test_rejects_negative_width(self):
        with pytest.raises(ValueError, match="width must be non-negative"):
            AABB(0, 0, -1, 1)

    def test_rejects_negative_height(self):
        with pytest.raises(ValueError, match="height must be non-negative"):
            AABB(0, 0, 1, -1)

    def test_rejects_string_x(self):
        with pytest.raises(TypeError):
            AABB("0", 0, 1, 1)  # type: ignore[arg-type]


# ── Properties ───────────────────────────────────────────────────────

class TestAABBProperties:
    """right, bottom, and derived properties."""

    def test_right(self):
        box = AABB(5, 0, 3, 1)
        assert box.right == 8

    def test_bottom(self):
        box = AABB(0, 2, 1, 4)
        assert box.bottom == 6

    def test_right_zero_width(self):
        box = AABB(5, 0, 0, 1)
        assert box.right == 5

    def test_bottom_zero_height(self):
        box = AABB(0, 3, 1, 0)
        assert box.bottom == 3


# ── contains_point ───────────────────────────────────────────────────

class TestContainsPoint:
    """Point-in-AABB tests."""

    def test_interior_point(self):
        box = AABB(0, 0, 10, 10)
        assert box.contains_point(5, 5)

    def test_top_left_corner(self):
        box = AABB(2, 3, 4, 4)
        assert box.contains_point(2, 3)

    def test_bottom_right_exclusive(self):
        # right and bottom are exclusive, so the point at (right, bottom)
        # is outside.
        box = AABB(0, 0, 4, 4)
        assert not box.contains_point(4, 4)

    def test_right_edge_exclusive(self):
        box = AABB(0, 0, 4, 4)
        assert not box.contains_point(4, 2)

    def test_bottom_edge_exclusive(self):
        box = AABB(0, 0, 4, 4)
        assert not box.contains_point(2, 4)

    def test_last_included_cell(self):
        box = AABB(0, 0, 4, 4)
        assert box.contains_point(3, 3)

    def test_outside_left(self):
        box = AABB(5, 5, 3, 3)
        assert not box.contains_point(4, 6)

    def test_outside_above(self):
        box = AABB(5, 5, 3, 3)
        assert not box.contains_point(6, 4)

    def test_degenerate_zero_width(self):
        box = AABB(0, 0, 0, 5)
        assert not box.contains_point(0, 0)

    def test_degenerate_zero_height(self):
        box = AABB(0, 0, 5, 0)
        assert not box.contains_point(0, 0)


# ── Equality and repr ────────────────────────────────────────────────

class TestAABBEquality:
    def test_equal_boxes(self):
        assert AABB(1, 2, 3, 4) == AABB(1, 2, 3, 4)

    def test_unequal_boxes(self):
        assert AABB(1, 2, 3, 4) != AABB(1, 2, 3, 5)

    def test_not_equal_to_other_type(self):
        assert AABB(0, 0, 1, 1) != (0, 0, 1, 1)

    def test_repr(self):
        box = AABB(1, 2, 3, 4)
        assert repr(box) == "AABB(x=1, y=2, width=3, height=4)"


# ── aabb_overlap ─────────────────────────────────────────────────────

class TestAABBOverlap:
    """Overlap detection between two AABBs."""

    def test_identical_boxes_overlap(self):
        a = AABB(0, 0, 4, 4)
        assert aabb_overlap(a, a)

    def test_overlapping_corner(self):
        a = AABB(0, 0, 4, 4)
        b = AABB(3, 3, 4, 4)
        assert aabb_overlap(a, b)

    def test_overlap_is_symmetric(self):
        a = AABB(0, 0, 4, 4)
        b = AABB(3, 3, 4, 4)
        assert aabb_overlap(a, b) == aabb_overlap(b, a)

    def test_no_overlap_separated_horizontally(self):
        a = AABB(0, 0, 3, 3)
        b = AABB(5, 0, 3, 3)
        assert not aabb_overlap(a, b)

    def test_no_overlap_separated_vertically(self):
        a = AABB(0, 0, 3, 3)
        b = AABB(0, 5, 3, 3)
        assert not aabb_overlap(a, b)

    def test_adjacent_horizontally_no_overlap(self):
        # a occupies columns 0..2, b starts at column 3 — no shared cell.
        a = AABB(0, 0, 3, 3)
        b = AABB(3, 0, 3, 3)
        assert not aabb_overlap(a, b)

    def test_adjacent_vertically_no_overlap(self):
        a = AABB(0, 0, 3, 3)
        b = AABB(0, 3, 3, 3)
        assert not aabb_overlap(a, b)

    def test_one_cell_overlap(self):
        # a occupies columns 0..2, rows 0..2.
        # b occupies columns 2..4, rows 2..4.
        # Shared cell: (2, 2).
        a = AABB(0, 0, 3, 3)
        b = AABB(2, 2, 3, 3)
        assert aabb_overlap(a, b)

    def test_contained_box(self):
        outer = AABB(0, 0, 10, 10)
        inner = AABB(3, 3, 2, 2)
        assert aabb_overlap(outer, inner)

    def test_degenerate_zero_width_no_overlap(self):
        a = AABB(0, 0, 0, 5)
        b = AABB(0, 0, 5, 5)
        assert not aabb_overlap(a, b)

    def test_degenerate_zero_height_no_overlap(self):
        a = AABB(0, 0, 5, 0)
        b = AABB(0, 0, 5, 5)
        assert not aabb_overlap(a, b)

    def test_both_degenerate_no_overlap(self):
        a = AABB(0, 0, 0, 0)
        b = AABB(0, 0, 0, 0)
        assert not aabb_overlap(a, b)

    def test_negative_position_overlap(self):
        a = AABB(-2, -2, 4, 4)  # covers -2..1
        b = AABB(0, 0, 3, 3)   # covers 0..2
        assert aabb_overlap(a, b)

    def test_negative_position_no_overlap(self):
        a = AABB(-5, -5, 2, 2)  # covers -5..-4
        b = AABB(0, 0, 2, 2)
        assert not aabb_overlap(a, b)

    def test_large_boxes_overlap(self):
        a = AABB(0, 0, 1000, 1000)
        b = AABB(999, 999, 1000, 1000)
        assert aabb_overlap(a, b)

    def test_single_cell_boxes_same_position(self):
        a = AABB(5, 5, 1, 1)
        b = AABB(5, 5, 1, 1)
        assert aabb_overlap(a, b)

    def test_single_cell_boxes_different_position(self):
        a = AABB(5, 5, 1, 1)
        b = AABB(6, 5, 1, 1)
        assert not aabb_overlap(a, b)


# ── Package-level import ─────────────────────────────────────────────

class TestPackageExport:
    """AABB and aabb_overlap are accessible from the top-level package."""

    def test_aabb_importable_from_wyby(self):
        from wyby import AABB as TopLevelAABB
        assert TopLevelAABB is AABB

    def test_aabb_overlap_importable_from_wyby(self):
        from wyby import aabb_overlap as top_level_fn
        assert top_level_fn is aabb_overlap
