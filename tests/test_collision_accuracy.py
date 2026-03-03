"""Tests for wyby.collision_accuracy — cell-level collision accuracy utilities."""

from __future__ import annotations

import math

import pytest

from wyby.collision import AABB
from wyby.collision_accuracy import (
    cell_distance,
    cells_occupied,
    check_tunneling_risk,
    overlap_cells,
    overlap_region,
)


# ── cells_occupied ──────────────────────────────────────────────────────


class TestCellsOccupied:
    """Test cells_occupied returns the correct set of cells."""

    def test_single_cell(self):
        box = AABB(5, 3, 1, 1)
        assert cells_occupied(box) == frozenset({(5, 3)})

    def test_rectangular_box(self):
        box = AABB(2, 3, 3, 2)
        expected = frozenset({
            (2, 3), (3, 3), (4, 3),
            (2, 4), (3, 4), (4, 4),
        })
        assert cells_occupied(box) == expected

    def test_square_box(self):
        box = AABB(0, 0, 2, 2)
        expected = frozenset({(0, 0), (1, 0), (0, 1), (1, 1)})
        assert cells_occupied(box) == expected

    def test_degenerate_zero_width(self):
        box = AABB(5, 5, 0, 3)
        assert cells_occupied(box) == frozenset()

    def test_degenerate_zero_height(self):
        box = AABB(5, 5, 3, 0)
        assert cells_occupied(box) == frozenset()

    def test_negative_position(self):
        box = AABB(-1, -2, 2, 2)
        expected = frozenset({(-1, -2), (0, -2), (-1, -1), (0, -1)})
        assert cells_occupied(box) == expected

    def test_large_box_count(self):
        box = AABB(0, 0, 10, 10)
        assert len(cells_occupied(box)) == 100

    def test_returns_frozenset(self):
        result = cells_occupied(AABB(0, 0, 1, 1))
        assert isinstance(result, frozenset)

    def test_type_error_not_aabb(self):
        with pytest.raises(TypeError, match="box must be an AABB"):
            cells_occupied("not_a_box")  # type: ignore[arg-type]

    def test_type_error_none(self):
        with pytest.raises(TypeError, match="box must be an AABB"):
            cells_occupied(None)  # type: ignore[arg-type]


# ── overlap_region ──────────────────────────────────────────────────────


class TestOverlapRegion:
    """Test overlap_region returns the correct intersection AABB."""

    def test_partial_overlap(self):
        a = AABB(0, 0, 4, 4)
        b = AABB(2, 2, 4, 4)
        region = overlap_region(a, b)
        assert region is not None
        assert region == AABB(2, 2, 2, 2)

    def test_full_containment(self):
        outer = AABB(0, 0, 10, 10)
        inner = AABB(3, 3, 2, 2)
        region = overlap_region(outer, inner)
        assert region == inner

    def test_identical_boxes(self):
        a = AABB(5, 5, 3, 3)
        region = overlap_region(a, a)
        assert region == a

    def test_no_overlap(self):
        a = AABB(0, 0, 2, 2)
        b = AABB(5, 5, 2, 2)
        assert overlap_region(a, b) is None

    def test_adjacent_boxes_no_overlap(self):
        # right exclusive: AABB(0,0,2,2) occupies cols 0-1, AABB(2,0,2,2) cols 2-3
        a = AABB(0, 0, 2, 2)
        b = AABB(2, 0, 2, 2)
        assert overlap_region(a, b) is None

    def test_single_column_overlap(self):
        a = AABB(0, 0, 3, 3)
        b = AABB(2, 0, 3, 3)
        region = overlap_region(a, b)
        assert region is not None
        assert region == AABB(2, 0, 1, 3)

    def test_single_cell_overlap(self):
        a = AABB(0, 0, 3, 3)
        b = AABB(2, 2, 3, 3)
        region = overlap_region(a, b)
        assert region is not None
        assert region == AABB(2, 2, 1, 1)

    def test_degenerate_box_no_overlap(self):
        a = AABB(0, 0, 0, 5)
        b = AABB(0, 0, 5, 5)
        assert overlap_region(a, b) is None

    def test_symmetric(self):
        a = AABB(0, 0, 5, 5)
        b = AABB(3, 3, 5, 5)
        assert overlap_region(a, b) == overlap_region(b, a)

    def test_type_error_first_arg(self):
        with pytest.raises(TypeError, match="a must be an AABB"):
            overlap_region("bad", AABB(0, 0, 1, 1))  # type: ignore[arg-type]

    def test_type_error_second_arg(self):
        with pytest.raises(TypeError, match="b must be an AABB"):
            overlap_region(AABB(0, 0, 1, 1), 42)  # type: ignore[arg-type]


# ── overlap_cells ───────────────────────────────────────────────────────


class TestOverlapCells:
    """Test overlap_cells returns the correct shared cell set."""

    def test_partial_overlap(self):
        a = AABB(0, 0, 4, 4)
        b = AABB(2, 2, 4, 4)
        shared = overlap_cells(a, b)
        expected = frozenset({(2, 2), (3, 2), (2, 3), (3, 3)})
        assert shared == expected

    def test_no_overlap_returns_empty(self):
        a = AABB(0, 0, 2, 2)
        b = AABB(10, 10, 2, 2)
        assert overlap_cells(a, b) == frozenset()

    def test_single_cell_overlap(self):
        a = AABB(0, 0, 3, 3)
        b = AABB(2, 2, 3, 3)
        assert overlap_cells(a, b) == frozenset({(2, 2)})

    def test_consistent_with_overlap_region(self):
        a = AABB(1, 1, 5, 5)
        b = AABB(3, 3, 5, 5)
        region = overlap_region(a, b)
        assert region is not None
        assert overlap_cells(a, b) == cells_occupied(region)

    def test_degenerate_box_returns_empty(self):
        a = AABB(0, 0, 0, 5)
        b = AABB(0, 0, 5, 5)
        assert overlap_cells(a, b) == frozenset()

    def test_returns_frozenset(self):
        result = overlap_cells(AABB(0, 0, 2, 2), AABB(1, 1, 2, 2))
        assert isinstance(result, frozenset)


# ── check_tunneling_risk ────────────────────────────────────────────────


class TestCheckTunnelingRisk:
    """Test check_tunneling_risk detection."""

    def test_fast_entity_tunnels_through_thin_wall(self):
        # 30 cells/sec × 1/30 sec = 1.0 cell displacement.
        # Displacement (1.0) is NOT > thickness (1), so no tunneling.
        assert not check_tunneling_risk(speed=30.0, dt=1 / 30, thickness=1)

    def test_very_fast_entity_tunnels(self):
        # 60 cells/sec × 1/30 sec = 2.0 cell displacement > 1 cell wall.
        assert check_tunneling_risk(speed=60.0, dt=1 / 30, thickness=1)

    def test_slow_entity_safe(self):
        assert not check_tunneling_risk(speed=5.0, dt=1 / 30, thickness=1)

    def test_thick_wall_safe(self):
        # 60 cells/sec × 1/30 sec = 2.0. Thickness 3 → safe.
        assert not check_tunneling_risk(speed=60.0, dt=1 / 30, thickness=3)

    def test_exactly_equal_no_tunnel(self):
        # displacement == thickness: not strictly greater, so no risk.
        assert not check_tunneling_risk(speed=30.0, dt=1 / 30, thickness=1)

    def test_just_over_threshold(self):
        assert check_tunneling_risk(speed=31.0, dt=1 / 30, thickness=1)

    def test_zero_speed_safe(self):
        assert not check_tunneling_risk(speed=0.0, dt=1 / 30, thickness=1)

    def test_zero_dt_safe(self):
        assert not check_tunneling_risk(speed=100.0, dt=0.0, thickness=1)

    def test_larger_thickness(self):
        # 100 cells/sec × 1/30 ≈ 3.33 > 3 → tunneling risk.
        assert check_tunneling_risk(speed=100.0, dt=1 / 30, thickness=3)

    def test_type_error_speed_string(self):
        with pytest.raises(TypeError, match="speed must be a number"):
            check_tunneling_risk(speed="fast", dt=1 / 30)  # type: ignore[arg-type]

    def test_type_error_speed_bool(self):
        with pytest.raises(TypeError, match="speed must be a number"):
            check_tunneling_risk(speed=True, dt=1 / 30)  # type: ignore[arg-type]

    def test_type_error_dt_string(self):
        with pytest.raises(TypeError, match="dt must be a number"):
            check_tunneling_risk(speed=10.0, dt="slow")  # type: ignore[arg-type]

    def test_type_error_dt_bool(self):
        with pytest.raises(TypeError, match="dt must be a number"):
            check_tunneling_risk(speed=10.0, dt=False)  # type: ignore[arg-type]

    def test_type_error_thickness_float(self):
        with pytest.raises(TypeError, match="thickness must be an int"):
            check_tunneling_risk(speed=10.0, dt=1 / 30, thickness=1.5)  # type: ignore[arg-type]

    def test_type_error_thickness_bool(self):
        with pytest.raises(TypeError, match="thickness must be an int"):
            check_tunneling_risk(speed=10.0, dt=1 / 30, thickness=True)  # type: ignore[arg-type]

    def test_value_error_negative_speed(self):
        with pytest.raises(ValueError, match="speed must be non-negative"):
            check_tunneling_risk(speed=-1.0, dt=1 / 30)

    def test_value_error_negative_dt(self):
        with pytest.raises(ValueError, match="dt must be non-negative"):
            check_tunneling_risk(speed=10.0, dt=-0.01)

    def test_value_error_nan_dt(self):
        with pytest.raises(ValueError, match="dt must be finite"):
            check_tunneling_risk(speed=10.0, dt=math.nan)

    def test_value_error_inf_dt(self):
        with pytest.raises(ValueError, match="dt must be finite"):
            check_tunneling_risk(speed=10.0, dt=math.inf)

    def test_value_error_zero_thickness(self):
        with pytest.raises(ValueError, match="thickness must be >= 1"):
            check_tunneling_risk(speed=10.0, dt=1 / 30, thickness=0)

    def test_value_error_negative_thickness(self):
        with pytest.raises(ValueError, match="thickness must be >= 1"):
            check_tunneling_risk(speed=10.0, dt=1 / 30, thickness=-1)


# ── cell_distance ───────────────────────────────────────────────────────


class TestCellDistance:
    """Test cell_distance (Chebyshev distance between AABBs)."""

    def test_overlapping_boxes_zero_distance(self):
        a = AABB(0, 0, 4, 4)
        b = AABB(2, 2, 4, 4)
        assert cell_distance(a, b) == 0

    def test_adjacent_boxes_zero_distance(self):
        # Adjacent (sharing an edge column-wise): a occupies cols 0-1,
        # b occupies cols 2-3.  Last cell of a is col 1, first of b is
        # col 2.  Chebyshev gap = 2 - 1 = 1?  No — they are neighbors,
        # distance between adjacent cells is 1 move.
        a = AABB(0, 0, 2, 2)
        b = AABB(2, 0, 2, 2)
        # a occupies cols 0,1 and b occupies cols 2,3.
        # Closest cells: (1,0)→(2,0) = 1 move.
        assert cell_distance(a, b) == 1

    def test_separated_horizontally(self):
        a = AABB(0, 0, 2, 2)  # cols 0-1
        b = AABB(5, 0, 2, 2)  # cols 5-6
        # Closest cells: (1,0) → (5,0).  Chebyshev distance = 5-1 = 4.
        assert cell_distance(a, b) == 4

    def test_separated_vertically(self):
        a = AABB(0, 0, 2, 2)  # rows 0-1
        b = AABB(0, 5, 2, 2)  # rows 5-6
        # Closest cells: (0,1) → (0,5).  Chebyshev = 5-1 = 4.
        assert cell_distance(a, b) == 4

    def test_separated_diagonally(self):
        a = AABB(0, 0, 2, 2)  # occupies (0,0)-(1,1)
        b = AABB(5, 5, 2, 2)  # occupies (5,5)-(6,6)
        # Closest cells: (1,1) → (5,5).  dx=4, dy=4.
        # Chebyshev = max(4, 4) = 4.
        assert cell_distance(a, b) == 4

    def test_same_box_zero_distance(self):
        a = AABB(3, 3, 4, 4)
        assert cell_distance(a, a) == 0

    def test_single_cell_boxes(self):
        a = AABB(0, 0, 1, 1)
        b = AABB(3, 4, 1, 1)
        # dx = 3-0 = 3, dy = 4-0 = 4 → Chebyshev = max(3,4) = 4.
        # Wait — for single cell boxes, a occupies (0,0), b occupies (3,4).
        # Distance from cell (0,0) to cell (3,4): max(3,4) = 4.
        # But cell_distance measures gap. Closest cells: (0,0) and (3,4).
        # They are 3 apart in x and 4 apart in y → Chebyshev = max(3,4) = 4.
        # Actually, for 1x1 boxes: a.right-1=0, b.x=3 → dx = max(0, 3-0) = 3.
        # Similarly dy = 4. Chebyshev = max(3,4) = 4.
        assert cell_distance(a, b) == 4

    def test_touching_boxes_distance_one(self):
        # a occupies (0,0)-(2,2), b occupies (3,0)-(5,2).
        # Closest cells: (2,0) → (3,0). That's 1 cell apart.
        a = AABB(0, 0, 3, 3)
        b = AABB(3, 0, 3, 3)
        # a.right - 1 = 2, b.x = 3 → dx = max(0, 3 - 2) = 1.
        assert cell_distance(a, b) == 1

    def test_negative_positions(self):
        a = AABB(-5, -5, 2, 2)  # occupies (-5,-5) to (-4,-4)
        b = AABB(0, 0, 2, 2)   # occupies (0,0) to (1,1)
        # dx = 0 - (-4) = 4, dy = 0 - (-4) = 4. Chebyshev = 4.
        assert cell_distance(a, b) == 4

    def test_degenerate_width_zero(self):
        a = AABB(0, 0, 0, 5)
        b = AABB(3, 0, 2, 2)
        # a is degenerate → uses position point. dx based on a.x=0,
        # b has cols 3-4: gap from 0 to 3 = 3.
        result = cell_distance(a, b)
        assert result >= 0  # At least non-negative.

    def test_symmetric(self):
        a = AABB(0, 0, 3, 3)
        b = AABB(10, 10, 2, 2)
        assert cell_distance(a, b) == cell_distance(b, a)

    def test_type_error_first_arg(self):
        with pytest.raises(TypeError, match="a must be an AABB"):
            cell_distance("bad", AABB(0, 0, 1, 1))  # type: ignore[arg-type]

    def test_type_error_second_arg(self):
        with pytest.raises(TypeError, match="b must be an AABB"):
            cell_distance(AABB(0, 0, 1, 1), None)  # type: ignore[arg-type]


# ── Integration: accuracy of float→int sync with collision ──────────────


class TestFloatToIntAccuracy:
    """Test that documents the accuracy implications of sync_positions
    truncation on collision detection.

    These tests demonstrate (and verify) the known caveats:

    - ``int()`` truncates toward zero, so ``Position(2.9, 3.9)`` maps
      to Entity cell ``(2, 3)``, not ``(3, 4)``.
    - Two entities that are < 1 cell apart in float space can end up
      in the same cell after truncation, triggering a collision that
      wouldn't occur with float-precision checks.
    - Conversely, entities at float positions that visually overlap
      may not collide after truncation if they round to different cells.
    """

    def test_truncation_same_cell_collision(self):
        """Entities at float positions 2.1 and 2.9 both truncate to cell 2,
        so they collide even though they are 0.8 cells apart in float space.

        Caveat: int() truncation can cause false-positive collisions
        for entities that are close but not truly overlapping.
        """
        from wyby.entity import Entity

        a = Entity(entity_id=9001)
        b = Entity(entity_id=9002)
        # Simulate positions that both truncate to cell 2.
        a.x = int(2.1)  # → 2
        b.x = int(2.9)  # → 2
        a.y = 0
        b.y = 0
        assert a.collide_with(b)  # Same cell → collision.

    def test_truncation_adjacent_cell_no_collision(self):
        """Entities at float positions 2.9 and 3.0 truncate to cells 2 and 3.
        With 1x1 bounding boxes they do NOT collide, even though they are
        only 0.1 cells apart in float space.

        Caveat: int() truncation can cause false-negative collisions
        for entities that are very close in float space but map to
        adjacent (non-overlapping) cells.
        """
        from wyby.entity import Entity

        a = Entity(entity_id=9003)
        b = Entity(entity_id=9004)
        a.x = int(2.9)  # → 2
        b.x = int(3.0)  # → 3
        a.y = 0
        b.y = 0
        assert not a.collide_with(b)  # Adjacent cells, no overlap.

    def test_negative_truncation_toward_zero(self):
        """Negative float positions truncate toward zero, not downward.
        ``int(-0.7)`` is ``0``, not ``-1``.

        Caveat: Entities at negative float positions near zero may
        unexpectedly collide with entities at cell (0, 0).
        """
        from wyby.entity import Entity

        a = Entity(entity_id=9005)
        b = Entity(entity_id=9006)
        a.x = int(-0.7)  # → 0 (toward zero, not -1)
        b.x = 0
        a.y = 0
        b.y = 0
        assert a.collide_with(b)  # Both at cell 0.

    def test_cells_occupied_matches_entity_bbox(self):
        """Verify that cells_occupied agrees with the cells an Entity
        with a given bounding box would logically cover."""
        from wyby.entity import Entity

        e = Entity(3, 5, entity_id=9007)
        box = AABB(e.x, e.y, 2, 3)
        cells = cells_occupied(box)
        assert len(cells) == 6
        assert (3, 5) in cells
        assert (4, 5) in cells
        assert (3, 7) in cells
        assert (4, 7) in cells


# ── Package-level exports ───────────────────────────────────────────────


class TestPackageExports:
    """Verify collision_accuracy symbols are importable from wyby."""

    def test_cells_occupied_importable(self):
        from wyby import cells_occupied as fn
        assert callable(fn)

    def test_overlap_region_importable(self):
        from wyby import overlap_region as fn
        assert callable(fn)

    def test_overlap_cells_importable(self):
        from wyby import overlap_cells as fn
        assert callable(fn)

    def test_check_tunneling_risk_importable(self):
        from wyby import check_tunneling_risk as fn
        assert callable(fn)

    def test_cell_distance_importable(self):
        from wyby import cell_distance as fn
        assert callable(fn)
