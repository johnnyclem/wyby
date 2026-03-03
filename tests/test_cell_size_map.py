"""Tests for wyby.cell_size_map — terminal cell size mapping."""

from __future__ import annotations

import pytest

from wyby.cell_size_map import CellSizeMap
from wyby.font_variance import DEFAULT_CELL_ASPECT_RATIO, CellGeometry


# ---------------------------------------------------------------------------
# Construction and validation
# ---------------------------------------------------------------------------


class TestCellSizeMapConstruction:
    """CellSizeMap construction, defaults, and validation."""

    def test_default_aspect_ratio(self) -> None:
        csm = CellSizeMap()
        assert csm.cell_aspect_ratio == DEFAULT_CELL_ASPECT_RATIO

    def test_custom_aspect_ratio(self) -> None:
        csm = CellSizeMap(cell_aspect_ratio=1.5)
        assert csm.cell_aspect_ratio == 1.5

    def test_int_aspect_ratio_accepted(self) -> None:
        csm = CellSizeMap(cell_aspect_ratio=2)
        assert csm.cell_aspect_ratio == 2.0

    def test_min_aspect_ratio(self) -> None:
        csm = CellSizeMap(cell_aspect_ratio=1.0)
        assert csm.cell_aspect_ratio == 1.0

    def test_max_aspect_ratio(self) -> None:
        csm = CellSizeMap(cell_aspect_ratio=4.0)
        assert csm.cell_aspect_ratio == 4.0

    def test_below_min_raises(self) -> None:
        with pytest.raises(ValueError, match="between"):
            CellSizeMap(cell_aspect_ratio=0.5)

    def test_above_max_raises(self) -> None:
        with pytest.raises(ValueError, match="between"):
            CellSizeMap(cell_aspect_ratio=5.0)

    def test_zero_raises(self) -> None:
        with pytest.raises(ValueError, match="between"):
            CellSizeMap(cell_aspect_ratio=0.0)

    def test_negative_raises(self) -> None:
        with pytest.raises(ValueError, match="between"):
            CellSizeMap(cell_aspect_ratio=-1.0)

    def test_string_raises_type_error(self) -> None:
        with pytest.raises(TypeError, match="must be a number"):
            CellSizeMap(cell_aspect_ratio="2.0")  # type: ignore[arg-type]

    def test_none_raises_type_error(self) -> None:
        with pytest.raises(TypeError, match="must be a number"):
            CellSizeMap(cell_aspect_ratio=None)  # type: ignore[arg-type]

    def test_bool_raises_type_error(self) -> None:
        with pytest.raises(TypeError, match="must be a number"):
            CellSizeMap(cell_aspect_ratio=True)  # type: ignore[arg-type]

    def test_geometry_is_none_by_default(self) -> None:
        csm = CellSizeMap()
        assert csm.geometry is None


# ---------------------------------------------------------------------------
# detect() class method
# ---------------------------------------------------------------------------


class TestCellSizeMapDetect:
    """CellSizeMap.detect() class method."""

    def test_returns_cell_size_map(self) -> None:
        csm = CellSizeMap.detect()
        assert isinstance(csm, CellSizeMap)

    def test_aspect_ratio_is_positive(self) -> None:
        csm = CellSizeMap.detect()
        assert csm.cell_aspect_ratio > 0

    def test_geometry_is_set(self) -> None:
        csm = CellSizeMap.detect()
        assert isinstance(csm.geometry, CellGeometry)

    def test_fallback_when_detection_fails(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When ioctl detection fails, falls back to the default ratio."""
        monkeypatch.setattr(
            "wyby.font_variance._try_ioctl_cell_size", lambda: None,
        )
        csm = CellSizeMap.detect()
        assert csm.cell_aspect_ratio == DEFAULT_CELL_ASPECT_RATIO
        assert csm.geometry is not None
        assert csm.geometry.detected is False

    def test_uses_detected_ratio(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When ioctl returns valid data, uses the detected ratio."""
        # 40 rows, 120 cols, 960px width, 800px height
        # cell_w = 960/120 = 8, cell_h = 800/40 = 20, ratio = 2.5
        monkeypatch.setattr(
            "wyby.font_variance._try_ioctl_cell_size",
            lambda: (40, 120, 960, 800),
        )
        csm = CellSizeMap.detect()
        assert csm.cell_aspect_ratio == 2.5
        assert csm.geometry is not None
        assert csm.geometry.detected is True


# ---------------------------------------------------------------------------
# World → Cell conversions
# ---------------------------------------------------------------------------


class TestWorldToCell:
    """world_to_cell() and related X/Y methods."""

    def test_origin(self) -> None:
        csm = CellSizeMap(cell_aspect_ratio=2.0)
        assert csm.world_to_cell(0.0, 0.0) == (0, 0)

    def test_simple_position(self) -> None:
        csm = CellSizeMap(cell_aspect_ratio=2.0)
        # wx=10.0 → col=10, wy=20.0 → row=20/2=10
        assert csm.world_to_cell(10.0, 20.0) == (10, 10)

    def test_aspect_ratio_effect(self) -> None:
        csm = CellSizeMap(cell_aspect_ratio=2.0)
        # Same world distance in X and Y → different cell distances
        col = csm.world_to_cell_x(10.0)
        row = csm.world_to_cell_y(10.0)
        assert col == 10
        assert row == 5  # 10 / 2.0 = 5

    def test_fractional_world_coords(self) -> None:
        csm = CellSizeMap(cell_aspect_ratio=2.0)
        # 5.4 / 2.0 = 2.7 → rounds to 3
        assert csm.world_to_cell_y(5.4) == 3

    def test_negative_coords(self) -> None:
        csm = CellSizeMap(cell_aspect_ratio=2.0)
        col, row = csm.world_to_cell(-5.0, -10.0)
        assert col == -5
        assert row == -5

    def test_world_to_cell_x(self) -> None:
        csm = CellSizeMap(cell_aspect_ratio=2.0)
        assert csm.world_to_cell_x(7.0) == 7
        assert csm.world_to_cell_x(7.6) == 8
        assert csm.world_to_cell_x(-3.2) == -3

    def test_world_to_cell_y(self) -> None:
        csm = CellSizeMap(cell_aspect_ratio=2.0)
        assert csm.world_to_cell_y(10.0) == 5
        assert csm.world_to_cell_y(7.0) == 4  # 7/2 = 3.5, rounds to 4

    def test_different_aspect_ratio(self) -> None:
        csm = CellSizeMap(cell_aspect_ratio=1.5)
        # 9.0 / 1.5 = 6.0
        assert csm.world_to_cell_y(9.0) == 6

    def test_ratio_1_is_identity(self) -> None:
        csm = CellSizeMap(cell_aspect_ratio=1.0)
        assert csm.world_to_cell(10.0, 10.0) == (10, 10)


# ---------------------------------------------------------------------------
# World → Cell size conversions
# ---------------------------------------------------------------------------


class TestWorldToCellSize:
    """world_to_cell_size() for dimensions."""

    def test_square_world_region(self) -> None:
        csm = CellSizeMap(cell_aspect_ratio=2.0)
        # A 10×10 world square → 10 cols × 5 rows
        cols, rows = csm.world_to_cell_size(10.0, 10.0)
        assert cols == 10
        assert rows == 5

    def test_rectangular_region(self) -> None:
        csm = CellSizeMap(cell_aspect_ratio=2.0)
        cols, rows = csm.world_to_cell_size(20.0, 10.0)
        assert cols == 20
        assert rows == 5

    def test_minimum_clamp(self) -> None:
        csm = CellSizeMap(cell_aspect_ratio=2.0)
        # Very small dimensions clamp to 1
        cols, rows = csm.world_to_cell_size(0.1, 0.1)
        assert cols >= 1
        assert rows >= 1

    def test_zero_clamps_to_one(self) -> None:
        csm = CellSizeMap(cell_aspect_ratio=2.0)
        cols, rows = csm.world_to_cell_size(0.0, 0.0)
        assert cols == 1
        assert rows == 1


# ---------------------------------------------------------------------------
# Cell → World conversions
# ---------------------------------------------------------------------------


class TestCellToWorld:
    """cell_to_world() and related X/Y methods."""

    def test_origin(self) -> None:
        csm = CellSizeMap(cell_aspect_ratio=2.0)
        assert csm.cell_to_world(0, 0) == (0.0, 0.0)

    def test_simple_position(self) -> None:
        csm = CellSizeMap(cell_aspect_ratio=2.0)
        # col=10 → wx=10.0, row=5 → wy=5*2.0=10.0
        wx, wy = csm.cell_to_world(10, 5)
        assert wx == 10.0
        assert wy == 10.0

    def test_aspect_ratio_applied_to_y(self) -> None:
        csm = CellSizeMap(cell_aspect_ratio=2.0)
        assert csm.cell_to_world_x(5) == 5.0
        assert csm.cell_to_world_y(5) == 10.0  # 5 * 2.0

    def test_cell_to_world_x(self) -> None:
        csm = CellSizeMap(cell_aspect_ratio=2.0)
        assert csm.cell_to_world_x(0) == 0.0
        assert csm.cell_to_world_x(42) == 42.0
        assert csm.cell_to_world_x(-3) == -3.0

    def test_cell_to_world_y(self) -> None:
        csm = CellSizeMap(cell_aspect_ratio=2.0)
        assert csm.cell_to_world_y(0) == 0.0
        assert csm.cell_to_world_y(10) == 20.0
        assert csm.cell_to_world_y(-5) == -10.0

    def test_different_aspect_ratio(self) -> None:
        csm = CellSizeMap(cell_aspect_ratio=1.5)
        assert csm.cell_to_world_y(6) == 9.0  # 6 * 1.5

    def test_ratio_1_is_identity(self) -> None:
        csm = CellSizeMap(cell_aspect_ratio=1.0)
        assert csm.cell_to_world(10, 10) == (10.0, 10.0)

    def test_negative_coordinates(self) -> None:
        csm = CellSizeMap(cell_aspect_ratio=2.0)
        wx, wy = csm.cell_to_world(-5, -3)
        assert wx == -5.0
        assert wy == -6.0  # -3 * 2.0


# ---------------------------------------------------------------------------
# Cell → World size conversions
# ---------------------------------------------------------------------------


class TestCellToWorldSize:
    """cell_to_world_size() for dimensions."""

    def test_basic_conversion(self) -> None:
        csm = CellSizeMap(cell_aspect_ratio=2.0)
        w, h = csm.cell_to_world_size(10, 5)
        assert w == 10.0
        assert h == 10.0  # 5 * 2.0

    def test_zero_size(self) -> None:
        csm = CellSizeMap(cell_aspect_ratio=2.0)
        w, h = csm.cell_to_world_size(0, 0)
        assert w == 0.0
        assert h == 0.0


# ---------------------------------------------------------------------------
# world_distance
# ---------------------------------------------------------------------------


class TestWorldDistance:
    """world_distance() — aspect-corrected Euclidean distance."""

    def test_zero_distance(self) -> None:
        csm = CellSizeMap(cell_aspect_ratio=2.0)
        assert csm.world_distance(5, 3, 5, 3) == 0.0

    def test_horizontal_distance(self) -> None:
        csm = CellSizeMap(cell_aspect_ratio=2.0)
        # 10 columns apart, same row → 10.0 world units
        d = csm.world_distance(0, 0, 10, 0)
        assert d == pytest.approx(10.0)

    def test_vertical_distance(self) -> None:
        csm = CellSizeMap(cell_aspect_ratio=2.0)
        # 5 rows apart → 5 * 2.0 = 10.0 world units
        d = csm.world_distance(0, 0, 0, 5)
        assert d == pytest.approx(10.0)

    def test_horizontal_equals_vertical_for_square_visual(self) -> None:
        csm = CellSizeMap(cell_aspect_ratio=2.0)
        # 10 columns horizontal = 10.0 world units
        dh = csm.world_distance(0, 0, 10, 0)
        # 5 rows vertical = 5 * 2.0 = 10.0 world units
        dv = csm.world_distance(0, 0, 0, 5)
        assert dh == pytest.approx(dv)

    def test_diagonal_distance(self) -> None:
        csm = CellSizeMap(cell_aspect_ratio=2.0)
        # (0,0) to (3,2): world coords (0,0) to (3, 4)
        # distance = sqrt(3^2 + 4^2) = 5.0
        d = csm.world_distance(0, 0, 3, 2)
        assert d == pytest.approx(5.0)

    def test_negative_coords(self) -> None:
        csm = CellSizeMap(cell_aspect_ratio=2.0)
        d = csm.world_distance(-3, -2, 0, 0)
        assert d == pytest.approx(5.0)

    def test_ratio_1_is_standard_euclidean(self) -> None:
        csm = CellSizeMap(cell_aspect_ratio=1.0)
        d = csm.world_distance(0, 0, 3, 4)
        assert d == pytest.approx(5.0)

    def test_symmetry(self) -> None:
        csm = CellSizeMap(cell_aspect_ratio=2.0)
        d1 = csm.world_distance(1, 2, 5, 8)
        d2 = csm.world_distance(5, 8, 1, 2)
        assert d1 == pytest.approx(d2)


# ---------------------------------------------------------------------------
# square_cells
# ---------------------------------------------------------------------------


class TestSquareCells:
    """square_cells() — cell dimensions for a visually square region."""

    def test_basic_square(self) -> None:
        csm = CellSizeMap(cell_aspect_ratio=2.0)
        cols, rows = csm.square_cells(10.0)
        assert cols == 10
        assert rows == 5

    def test_small_square(self) -> None:
        csm = CellSizeMap(cell_aspect_ratio=2.0)
        cols, rows = csm.square_cells(1.0)
        assert cols == 1
        assert rows == 1  # max(1, round(1/2)) = max(1,0) = 1

    def test_ratio_1_gives_equal_dims(self) -> None:
        csm = CellSizeMap(cell_aspect_ratio=1.0)
        cols, rows = csm.square_cells(10.0)
        assert cols == 10
        assert rows == 10

    def test_matches_world_to_cell_size(self) -> None:
        csm = CellSizeMap(cell_aspect_ratio=2.0)
        assert csm.square_cells(8.0) == csm.world_to_cell_size(8.0, 8.0)


# ---------------------------------------------------------------------------
# Round-trip consistency
# ---------------------------------------------------------------------------


class TestRoundTrip:
    """World → Cell → World and Cell → World → Cell round-trips."""

    def test_cell_to_world_to_cell(self) -> None:
        csm = CellSizeMap(cell_aspect_ratio=2.0)
        # Start with cell coords, convert to world, convert back
        cx, cy = 10, 5
        wx, wy = csm.cell_to_world(cx, cy)
        cx2, cy2 = csm.world_to_cell(wx, wy)
        assert cx2 == cx
        assert cy2 == cy

    def test_world_to_cell_to_world_approximate(self) -> None:
        csm = CellSizeMap(cell_aspect_ratio=2.0)
        # World → Cell loses precision due to rounding
        wx, wy = 7.3, 15.7
        cx, cy = csm.world_to_cell(wx, wy)
        wx2, wy2 = csm.cell_to_world(cx, cy)
        # Error should be within rounding tolerance
        assert abs(wx2 - wx) <= 0.5
        assert abs(wy2 - wy) <= csm.cell_aspect_ratio / 2 + 0.01


# ---------------------------------------------------------------------------
# __repr__ and __eq__
# ---------------------------------------------------------------------------


class TestReprAndEquality:
    """repr and equality semantics."""

    def test_repr_basic(self) -> None:
        csm = CellSizeMap(cell_aspect_ratio=2.0)
        r = repr(csm)
        assert "CellSizeMap" in r
        assert "2.0" in r

    def test_repr_detected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "wyby.font_variance._try_ioctl_cell_size", lambda: None,
        )
        csm = CellSizeMap.detect()
        r = repr(csm)
        assert "detected=" in r

    def test_equality_same_ratio(self) -> None:
        assert CellSizeMap(2.0) == CellSizeMap(2.0)

    def test_inequality_different_ratio(self) -> None:
        assert CellSizeMap(2.0) != CellSizeMap(1.5)

    def test_not_equal_to_other_types(self) -> None:
        assert CellSizeMap(2.0) != 2.0
        assert CellSizeMap(2.0) != "CellSizeMap"


# ---------------------------------------------------------------------------
# Package exports
# ---------------------------------------------------------------------------


class TestCellSizeMapExports:
    """CellSizeMap should be importable from the top-level package."""

    def test_importable_from_wyby(self) -> None:
        from wyby import CellSizeMap as CSM

        assert CSM is CellSizeMap

    def test_in_all(self) -> None:
        import wyby

        assert "CellSizeMap" in wyby.__all__
