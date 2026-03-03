"""Tests for wyby.tile_collision — tile-based collision detection."""

from __future__ import annotations

import pytest

from wyby.tile_collision import TileMap


# ── TileMap construction ────────────────────────────────────────────

class TestTileMapInit:
    """TileMap construction and validation."""

    def test_basic_construction(self):
        tm = TileMap(10, 8)
        assert tm.width == 10
        assert tm.height == 8
        assert tm.default_solid is True

    def test_default_solid_false(self):
        tm = TileMap(5, 5, default_solid=False)
        assert tm.default_solid is False

    def test_all_tiles_start_passable(self):
        tm = TileMap(3, 3)
        for y in range(3):
            for x in range(3):
                assert not tm.is_solid(x, y)

    def test_rejects_zero_width(self):
        with pytest.raises(ValueError, match="width must be >= 1"):
            TileMap(0, 5)

    def test_rejects_zero_height(self):
        with pytest.raises(ValueError, match="height must be >= 1"):
            TileMap(5, 0)

    def test_rejects_negative_width(self):
        with pytest.raises(ValueError, match="width must be >= 1"):
            TileMap(-1, 5)

    def test_rejects_negative_height(self):
        with pytest.raises(ValueError, match="height must be >= 1"):
            TileMap(5, -1)

    def test_rejects_float_width(self):
        with pytest.raises(TypeError, match="width must be an int"):
            TileMap(1.5, 5)  # type: ignore[arg-type]

    def test_rejects_float_height(self):
        with pytest.raises(TypeError, match="height must be an int"):
            TileMap(5, 1.5)  # type: ignore[arg-type]

    def test_rejects_bool_width(self):
        with pytest.raises(TypeError, match="width must be an int"):
            TileMap(True, 5)  # type: ignore[arg-type]

    def test_rejects_bool_height(self):
        with pytest.raises(TypeError, match="height must be an int"):
            TileMap(5, True)  # type: ignore[arg-type]

    def test_rejects_string_width(self):
        with pytest.raises(TypeError, match="width must be an int"):
            TileMap("5", 5)  # type: ignore[arg-type]

    def test_rejects_non_bool_default_solid(self):
        with pytest.raises(TypeError, match="default_solid must be a bool"):
            TileMap(5, 5, default_solid=1)  # type: ignore[arg-type]

    def test_repr(self):
        tm = TileMap(10, 8)
        assert repr(tm) == "TileMap(width=10, height=8, default_solid=True)"

    def test_repr_open_boundaries(self):
        tm = TileMap(4, 3, default_solid=False)
        assert repr(tm) == "TileMap(width=4, height=3, default_solid=False)"


# ── is_solid ────────────────────────────────────────────────────────

class TestIsSolid:
    """Point queries on the tile map."""

    def test_passable_by_default(self):
        tm = TileMap(5, 5)
        assert not tm.is_solid(2, 2)

    def test_solid_after_set(self):
        tm = TileMap(5, 5)
        tm.set_solid(2, 2)
        assert tm.is_solid(2, 2)

    def test_out_of_bounds_default_solid_true(self):
        tm = TileMap(5, 5, default_solid=True)
        assert tm.is_solid(-1, 0)
        assert tm.is_solid(0, -1)
        assert tm.is_solid(5, 0)
        assert tm.is_solid(0, 5)

    def test_out_of_bounds_default_solid_false(self):
        tm = TileMap(5, 5, default_solid=False)
        assert not tm.is_solid(-1, 0)
        assert not tm.is_solid(0, -1)
        assert not tm.is_solid(5, 0)
        assert not tm.is_solid(0, 5)

    def test_corners(self):
        tm = TileMap(4, 3)
        tm.set_solid(0, 0)
        tm.set_solid(3, 0)
        tm.set_solid(0, 2)
        tm.set_solid(3, 2)
        assert tm.is_solid(0, 0)
        assert tm.is_solid(3, 0)
        assert tm.is_solid(0, 2)
        assert tm.is_solid(3, 2)
        assert not tm.is_solid(1, 1)

    def test_rejects_float_x(self):
        tm = TileMap(5, 5)
        with pytest.raises(TypeError, match="x must be an int"):
            tm.is_solid(1.5, 0)  # type: ignore[arg-type]

    def test_rejects_float_y(self):
        tm = TileMap(5, 5)
        with pytest.raises(TypeError, match="y must be an int"):
            tm.is_solid(0, 1.5)  # type: ignore[arg-type]

    def test_rejects_bool_x(self):
        tm = TileMap(5, 5)
        with pytest.raises(TypeError, match="x must be an int"):
            tm.is_solid(True, 0)  # type: ignore[arg-type]


# ── set_solid ───────────────────────────────────────────────────────

class TestSetSolid:
    """Setting individual tiles solid or passable."""

    def test_set_solid(self):
        tm = TileMap(5, 5)
        tm.set_solid(2, 3)
        assert tm.is_solid(2, 3)

    def test_set_passable(self):
        tm = TileMap(5, 5)
        tm.set_solid(2, 3)
        tm.set_solid(2, 3, solid=False)
        assert not tm.is_solid(2, 3)

    def test_out_of_bounds_raises(self):
        tm = TileMap(5, 5)
        with pytest.raises(ValueError, match="out of bounds"):
            tm.set_solid(5, 0)

    def test_negative_out_of_bounds_raises(self):
        tm = TileMap(5, 5)
        with pytest.raises(ValueError, match="out of bounds"):
            tm.set_solid(-1, 0)

    def test_rejects_non_bool_solid(self):
        tm = TileMap(5, 5)
        with pytest.raises(TypeError, match="solid must be a bool"):
            tm.set_solid(0, 0, solid=1)  # type: ignore[arg-type]

    def test_rejects_bool_x(self):
        tm = TileMap(5, 5)
        with pytest.raises(TypeError, match="x must be an int"):
            tm.set_solid(True, 0)  # type: ignore[arg-type]


# ── fill_solid ──────────────────────────────────────────────────────

class TestFillSolid:
    """Filling rectangular regions."""

    def test_fill_region(self):
        tm = TileMap(8, 6)
        tm.fill_solid(2, 1, 3, 2)
        # Inside region
        assert tm.is_solid(2, 1)
        assert tm.is_solid(4, 2)
        # Outside region
        assert not tm.is_solid(1, 1)
        assert not tm.is_solid(5, 1)
        assert not tm.is_solid(2, 0)
        assert not tm.is_solid(2, 3)

    def test_fill_entire_map(self):
        tm = TileMap(3, 3)
        tm.fill_solid(0, 0, 3, 3)
        for y in range(3):
            for x in range(3):
                assert tm.is_solid(x, y)

    def test_fill_clips_to_bounds(self):
        tm = TileMap(5, 5)
        # Region extends outside — should not raise.
        tm.fill_solid(-2, -2, 10, 10)
        for y in range(5):
            for x in range(5):
                assert tm.is_solid(x, y)

    def test_fill_passable(self):
        tm = TileMap(5, 5)
        tm.fill_solid(0, 0, 5, 5)
        tm.fill_solid(1, 1, 3, 3, solid=False)
        assert tm.is_solid(0, 0)
        assert not tm.is_solid(1, 1)
        assert not tm.is_solid(3, 3)
        assert tm.is_solid(4, 4)

    def test_fill_zero_width(self):
        tm = TileMap(5, 5)
        tm.fill_solid(0, 0, 0, 5)
        for y in range(5):
            for x in range(5):
                assert not tm.is_solid(x, y)

    def test_fill_zero_height(self):
        tm = TileMap(5, 5)
        tm.fill_solid(0, 0, 5, 0)
        for y in range(5):
            for x in range(5):
                assert not tm.is_solid(x, y)

    def test_rejects_negative_width(self):
        tm = TileMap(5, 5)
        with pytest.raises(ValueError, match="width must be non-negative"):
            tm.fill_solid(0, 0, -1, 1)

    def test_rejects_negative_height(self):
        tm = TileMap(5, 5)
        with pytest.raises(ValueError, match="height must be non-negative"):
            tm.fill_solid(0, 0, 1, -1)

    def test_rejects_float_width(self):
        tm = TileMap(5, 5)
        with pytest.raises(TypeError, match="width must be an int"):
            tm.fill_solid(0, 0, 1.5, 1)  # type: ignore[arg-type]

    def test_rejects_non_bool_solid(self):
        tm = TileMap(5, 5)
        with pytest.raises(TypeError, match="solid must be a bool"):
            tm.fill_solid(0, 0, 1, 1, solid=1)  # type: ignore[arg-type]


# ── region_has_solid ────────────────────────────────────────────────

class TestRegionHasSolid:
    """Region collision queries."""

    def test_no_solid_in_region(self):
        tm = TileMap(5, 5)
        assert not tm.region_has_solid(0, 0, 5, 5)

    def test_solid_in_region(self):
        tm = TileMap(5, 5)
        tm.set_solid(2, 2)
        assert tm.region_has_solid(1, 1, 3, 3)

    def test_solid_at_region_edge(self):
        tm = TileMap(5, 5)
        tm.set_solid(3, 3)
        # Region covers (2,2) to (3,3) — solid at corner.
        assert tm.region_has_solid(2, 2, 2, 2)

    def test_solid_outside_region(self):
        tm = TileMap(5, 5)
        tm.set_solid(4, 4)
        assert not tm.region_has_solid(0, 0, 3, 3)

    def test_single_cell_region_solid(self):
        tm = TileMap(5, 5)
        tm.set_solid(2, 2)
        assert tm.region_has_solid(2, 2, 1, 1)

    def test_single_cell_region_passable(self):
        tm = TileMap(5, 5)
        assert not tm.region_has_solid(2, 2, 1, 1)

    def test_zero_width_region_always_false(self):
        tm = TileMap(5, 5)
        tm.fill_solid(0, 0, 5, 5)
        assert not tm.region_has_solid(0, 0, 0, 5)

    def test_zero_height_region_always_false(self):
        tm = TileMap(5, 5)
        tm.fill_solid(0, 0, 5, 5)
        assert not tm.region_has_solid(0, 0, 5, 0)

    def test_out_of_bounds_default_solid_true(self):
        tm = TileMap(5, 5, default_solid=True)
        # Region extends past right edge.
        assert tm.region_has_solid(4, 0, 3, 1)

    def test_out_of_bounds_default_solid_false(self):
        tm = TileMap(5, 5, default_solid=False)
        # Region extends past right edge — out-of-bounds is passable.
        assert not tm.region_has_solid(4, 0, 3, 1)

    def test_entirely_out_of_bounds_default_solid_true(self):
        tm = TileMap(5, 5, default_solid=True)
        assert tm.region_has_solid(10, 10, 2, 2)

    def test_entirely_out_of_bounds_default_solid_false(self):
        tm = TileMap(5, 5, default_solid=False)
        assert not tm.region_has_solid(10, 10, 2, 2)

    def test_negative_region_default_solid_true(self):
        tm = TileMap(5, 5, default_solid=True)
        assert tm.region_has_solid(-2, -2, 1, 1)

    def test_rejects_negative_width(self):
        tm = TileMap(5, 5)
        with pytest.raises(ValueError, match="width must be non-negative"):
            tm.region_has_solid(0, 0, -1, 1)

    def test_rejects_negative_height(self):
        tm = TileMap(5, 5)
        with pytest.raises(ValueError, match="height must be non-negative"):
            tm.region_has_solid(0, 0, 1, -1)

    def test_rejects_float_x(self):
        tm = TileMap(5, 5)
        with pytest.raises(TypeError, match="x must be an int"):
            tm.region_has_solid(1.5, 0, 1, 1)  # type: ignore[arg-type]

    def test_rejects_bool_width(self):
        tm = TileMap(5, 5)
        with pytest.raises(TypeError, match="width must be an int"):
            tm.region_has_solid(0, 0, True, 1)  # type: ignore[arg-type]


# ── load ────────────────────────────────────────────────────────────

class TestLoad:
    """Loading tile data from 2D lists."""

    def test_load_basic(self):
        tm = TileMap(4, 3)
        tm.load([
            [1, 1, 1, 1],
            [1, 0, 0, 1],
            [1, 1, 1, 1],
        ])
        assert tm.is_solid(0, 0)
        assert not tm.is_solid(1, 1)
        assert not tm.is_solid(2, 1)
        assert tm.is_solid(3, 1)
        assert tm.is_solid(0, 2)

    def test_load_nonzero_is_solid(self):
        tm = TileMap(3, 1)
        tm.load([[0, 2, -1]])
        assert not tm.is_solid(0, 0)
        assert tm.is_solid(1, 0)
        assert tm.is_solid(2, 0)

    def test_load_wrong_row_count(self):
        tm = TileMap(3, 2)
        with pytest.raises(ValueError, match="3 rows, expected 2"):
            tm.load([[0, 0, 0], [0, 0, 0], [0, 0, 0]])

    def test_load_wrong_column_count(self):
        tm = TileMap(3, 2)
        with pytest.raises(ValueError, match="row 1 has 2 columns, expected 3"):
            tm.load([[0, 0, 0], [0, 0]])

    def test_load_not_a_list(self):
        tm = TileMap(3, 2)
        with pytest.raises(TypeError, match="data must be a list"):
            tm.load((0, 0))  # type: ignore[arg-type]

    def test_load_row_not_a_list(self):
        tm = TileMap(3, 1)
        with pytest.raises(TypeError, match="row 0 must be a list"):
            tm.load([(0, 0, 0)])  # type: ignore[list-item]

    def test_load_rejects_bool_value(self):
        tm = TileMap(2, 1)
        with pytest.raises(TypeError, match=r"data\[0\]\[1\] must be an int"):
            tm.load([[0, True]])  # type: ignore[list-item]

    def test_load_rejects_float_value(self):
        tm = TileMap(2, 1)
        with pytest.raises(TypeError, match=r"data\[0\]\[0\] must be an int"):
            tm.load([[1.5, 0]])  # type: ignore[list-item]

    def test_load_overwrites_previous(self):
        tm = TileMap(2, 2)
        tm.fill_solid(0, 0, 2, 2)
        tm.load([[0, 0], [0, 0]])
        assert not tm.is_solid(0, 0)
        assert not tm.is_solid(1, 1)


# ── clear ───────────────────────────────────────────────────────────

class TestClear:
    """Resetting the tile map."""

    def test_clear_resets_all(self):
        tm = TileMap(3, 3)
        tm.fill_solid(0, 0, 3, 3)
        tm.clear()
        for y in range(3):
            for x in range(3):
                assert not tm.is_solid(x, y)


# ── Package-level import ────────────────────────────────────────────

class TestPackageExport:
    """TileMap is accessible from the top-level package."""

    def test_tilemap_importable_from_wyby(self):
        from wyby import TileMap as TopLevelTileMap
        assert TopLevelTileMap is TileMap
