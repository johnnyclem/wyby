"""Terminal cell size mapping between world and cell coordinates.

Terminal character cells are not square — they are typically ~2x taller than
wide (~1:2 width-to-height ratio).  This module provides :class:`CellSizeMap`,
a bidirectional mapper between **world coordinates** (where one unit has the
same visual size in both axes) and **cell coordinates** (column/row positions
in the terminal grid).

World coordinates use the cell *column width* as the base unit: 1 world unit
equals 1 cell column of visual width.  Since cells are taller than wide,
1 world unit of vertical distance corresponds to fewer cell rows than columns.

Coordinate conventions
----------------------
- **Cell coordinates**: ``(column, row)`` integers, matching the ``(x, y)``
  convention used by :class:`~wyby.grid.CellBuffer` and
  :class:`~wyby.entity.Entity`.  Origin at top-left.  ``x`` increases
  rightward, ``y`` increases downward.
- **World coordinates**: ``(wx, wy)`` floats in a visually uniform space.
  1 world unit in the X direction looks the same on-screen as 1 world unit
  in the Y direction (assuming the cell aspect ratio is correct).

Conversion rules (given ``cell_aspect_ratio`` = cell height / cell width):

- ``world_x → cell column``:  ``round(wx)``  (1:1, columns are the base unit)
- ``world_y → cell row``:  ``round(wy / cell_aspect_ratio)``
- ``cell column → world_x``:  ``float(column)``
- ``cell row → world_y``:  ``row * cell_aspect_ratio``

Typical usage::

    from wyby.cell_size_map import CellSizeMap

    csm = CellSizeMap()  # uses default 2.0 aspect ratio

    # A 10×10 world-unit square needs 10 columns × 5 rows.
    cols, rows = csm.world_to_cell_size(10.0, 10.0)
    assert cols == 10
    assert rows == 5

    # Convert a world position to cell coordinates.
    cx, cy = csm.world_to_cell(15.0, 20.0)
    assert cx == 15
    assert cy == 10

    # Detect actual cell geometry from the terminal (when available).
    csm = CellSizeMap.detect()

Caveats
-------
- **The default aspect ratio (2.0) is approximate.**  The actual ratio
  depends on the terminal emulator, font, and line-spacing settings.
  Compact fonts like Iosevka may produce ratios of ~2.4; wide fonts like
  Source Code Pro may be ~1.7.  There is no universally reliable way to
  auto-detect the ratio at runtime.  See :mod:`wyby.font_variance` for
  full discussion.
- **Rounding introduces error.**  Cell coordinates are integers; world
  coordinates are floats.  Converting world → cell → world does not
  round-trip exactly.  For rendering, this is typically fine (sub-cell
  precision is invisible).  For game logic (e.g. collision detection),
  work in world coordinates and only convert for display.
- **The mapping assumes uniform cell size.**  All cells in a terminal
  are the same size.  This is true for monospace fonts, which terminals
  require.  If a proportional font or mixed-width fallback font is active,
  the mapping will be incorrect.
- **World-to-cell conversion always rounds to the nearest integer.**
  This means a world coordinate of 0.4 maps to cell 0, and 0.5 maps to
  cell 0 (Python's ``round()`` uses banker's rounding).  For consistent
  flooring behaviour, use ``int()`` on the float result instead.
- **Negative coordinates are supported.**  Negative world and cell
  coordinates convert correctly.  Whether they are valid for a
  particular :class:`~wyby.grid.CellBuffer` depends on the buffer's
  bounds — out-of-bounds writes are silently clipped.
- **Not a spatial index or coordinate system.**  This is a pure
  arithmetic mapping.  It does not store entity positions, manage
  coordinate frames, or provide spatial queries.  It is a utility for
  the arithmetic of non-square cells.
"""

from __future__ import annotations

import logging

from wyby.font_variance import (
    DEFAULT_CELL_ASPECT_RATIO,
    CellGeometry,
    estimate_cell_aspect_ratio,
)

_logger = logging.getLogger(__name__)

# Sane bounds for cell aspect ratio, matching font_variance.py.
_MIN_ASPECT_RATIO: float = 1.0
_MAX_ASPECT_RATIO: float = 4.0


class CellSizeMap:
    """Bidirectional mapping between world coordinates and cell coordinates.

    The mapping accounts for the non-square aspect ratio of terminal cells.
    World coordinates are visually uniform (1 unit looks the same size in
    both X and Y directions); cell coordinates are integer (column, row)
    positions in the terminal grid.

    Args:
        cell_aspect_ratio: The height-to-width ratio of a terminal cell.
            Defaults to :data:`~wyby.font_variance.DEFAULT_CELL_ASPECT_RATIO`
            (2.0).  Must be between 1.0 and 4.0 inclusive.

    Raises:
        TypeError: If *cell_aspect_ratio* is not a number.
        ValueError: If *cell_aspect_ratio* is outside the range [1.0, 4.0].

    Caveats:
        - The aspect ratio is fixed at construction time.  If the user
          changes font or terminal settings, create a new ``CellSizeMap``.
        - The ``detect()`` class method attempts ioctl-based detection
          on Unix but falls back to the default on most platforms
          (Windows, CI, piped output, pytest).
    """

    __slots__ = ("_cell_aspect_ratio", "_geometry")

    def __init__(
        self,
        cell_aspect_ratio: float = DEFAULT_CELL_ASPECT_RATIO,
    ) -> None:
        if isinstance(cell_aspect_ratio, bool) or not isinstance(
            cell_aspect_ratio, (int, float)
        ):
            raise TypeError(
                f"cell_aspect_ratio must be a number, "
                f"got {type(cell_aspect_ratio).__name__}"
            )
        ratio = float(cell_aspect_ratio)
        if not (_MIN_ASPECT_RATIO <= ratio <= _MAX_ASPECT_RATIO):
            raise ValueError(
                f"cell_aspect_ratio must be between {_MIN_ASPECT_RATIO} "
                f"and {_MAX_ASPECT_RATIO}, got {cell_aspect_ratio}"
            )
        self._cell_aspect_ratio = ratio
        self._geometry: CellGeometry | None = None

    @classmethod
    def detect(cls) -> CellSizeMap:
        """Create a CellSizeMap from detected terminal cell geometry.

        Attempts to detect the actual cell aspect ratio via
        :func:`~wyby.font_variance.estimate_cell_aspect_ratio`.  If
        detection fails, falls back to the default ratio.

        Returns:
            A new :class:`CellSizeMap` with the detected (or default)
            aspect ratio.

        Caveats:
            - Detection only works on Unix-like systems with a real TTY
              on stdout.  In pytest, CI, piped output, or on Windows,
              this falls back to the default ratio.
            - Even when detection succeeds, the result is a point-in-time
              snapshot.  Font changes or terminal resizing may invalidate it.
            - Calls :func:`~wyby.font_variance.estimate_cell_aspect_ratio`
              internally, which may perform an ioctl call.  Do not call
              per-frame.
        """
        geometry = estimate_cell_aspect_ratio()
        instance = cls(cell_aspect_ratio=geometry.aspect_ratio)
        instance._geometry = geometry
        _logger.debug(
            "CellSizeMap.detect: ratio=%.3f, detected=%s",
            geometry.aspect_ratio,
            geometry.detected,
        )
        return instance

    # -- Properties ---------------------------------------------------------

    @property
    def cell_aspect_ratio(self) -> float:
        """The cell height-to-width ratio used by this map."""
        return self._cell_aspect_ratio

    @property
    def geometry(self) -> CellGeometry | None:
        """The :class:`~wyby.font_variance.CellGeometry` from detection.

        ``None`` if this map was created with an explicit ratio rather
        than via :meth:`detect`.
        """
        return self._geometry

    # -- World → Cell conversions -------------------------------------------

    def world_to_cell(self, wx: float, wy: float) -> tuple[int, int]:
        """Convert a world-space position to cell (column, row) coordinates.

        Args:
            wx: World X coordinate (horizontal).
            wy: World Y coordinate (vertical).

        Returns:
            A ``(column, row)`` tuple of integers.

        Caveats:
            - Uses ``round()`` for conversion.  Python's ``round()``
              applies banker's rounding (round half to even), so
              ``round(0.5) == 0`` and ``round(1.5) == 2``.
            - The returned coordinates may be negative or exceed the
              buffer dimensions.  Bounds checking is the caller's
              responsibility.
        """
        col = round(wx)
        row = round(wy / self._cell_aspect_ratio)
        return (col, row)

    def world_to_cell_x(self, wx: float) -> int:
        """Convert a world X coordinate to a cell column.

        Equivalent to ``round(wx)`` — included for symmetry and clarity.
        """
        return round(wx)

    def world_to_cell_y(self, wy: float) -> int:
        """Convert a world Y coordinate to a cell row.

        Divides by the cell aspect ratio to account for cells being
        taller than wide.
        """
        return round(wy / self._cell_aspect_ratio)

    def world_to_cell_size(
        self, width: float, height: float,
    ) -> tuple[int, int]:
        """Convert world-space dimensions to cell (columns, rows).

        Given a rectangle that is *width* × *height* in world units
        (visually square when ``width == height``), returns the number
        of cell columns and rows needed to represent it.

        Args:
            width: World-space width (horizontal extent).
            height: World-space height (vertical extent).

        Returns:
            A ``(columns, rows)`` tuple of integers, each at least 1
            (zero-size regions are clamped).

        Caveats:
            - A world-space square of size 10 with aspect ratio 2.0
              produces ``(10, 5)`` — 10 columns, 5 rows.
            - Results are clamped to a minimum of 1 to avoid zero-size
              regions.  Negative dimensions are not meaningful and may
              produce unexpected results.
        """
        cols = max(1, round(width))
        rows = max(1, round(height / self._cell_aspect_ratio))
        return (cols, rows)

    # -- Cell → World conversions -------------------------------------------

    def cell_to_world(self, cx: int, cy: int) -> tuple[float, float]:
        """Convert cell (column, row) coordinates to world-space position.

        Args:
            cx: Cell column.
            cy: Cell row.

        Returns:
            A ``(wx, wy)`` tuple of floats in world coordinates.

        Caveats:
            - ``cell_to_world(world_to_cell(wx, wy))`` does not
              round-trip exactly because ``world_to_cell`` rounds to
              integers.  The error is at most 0.5 in the X axis and
              ``cell_aspect_ratio / 2`` in the Y axis.
        """
        wx = float(cx)
        wy = float(cy) * self._cell_aspect_ratio
        return (wx, wy)

    def cell_to_world_x(self, cx: int) -> float:
        """Convert a cell column to a world X coordinate.

        Equivalent to ``float(cx)`` — included for symmetry.
        """
        return float(cx)

    def cell_to_world_y(self, cy: int) -> float:
        """Convert a cell row to a world Y coordinate.

        Multiplies by the cell aspect ratio to account for cells being
        taller than wide.
        """
        return float(cy) * self._cell_aspect_ratio

    def cell_to_world_size(
        self, columns: int, rows: int,
    ) -> tuple[float, float]:
        """Convert cell dimensions (columns, rows) to world-space size.

        Args:
            columns: Number of cell columns.
            rows: Number of cell rows.

        Returns:
            A ``(width, height)`` tuple of floats in world units.
        """
        width = float(columns)
        height = float(rows) * self._cell_aspect_ratio
        return (width, height)

    # -- Distance utilities -------------------------------------------------

    def world_distance(self, cx1: int, cy1: int, cx2: int, cy2: int) -> float:
        """Compute the visually correct Euclidean distance between two cells.

        Converts cell coordinates to world coordinates before computing
        distance, so the result accounts for the non-square cell aspect
        ratio.  Without this correction, diagonal distances in cell space
        are distorted — moving 1 cell diagonally covers more visual
        distance vertically than horizontally.

        Args:
            cx1: Column of the first cell.
            cy1: Row of the first cell.
            cx2: Column of the second cell.
            cy2: Row of the second cell.

        Returns:
            The Euclidean distance in world units.

        Caveats:
            - This is Euclidean (straight-line) distance.  For grid-based
              movement, Manhattan or Chebyshev distance may be more
              appropriate — but those also need aspect-ratio correction
              to be visually meaningful.
            - The result depends on the cell aspect ratio.  A distance
              computed with ratio 2.0 will differ from one computed with
              ratio 1.8.  Use a consistent ratio throughout your game.
        """
        wx1, wy1 = self.cell_to_world(cx1, cy1)
        wx2, wy2 = self.cell_to_world(cx2, cy2)
        dx = wx2 - wx1
        dy = wy2 - wy1
        return (dx * dx + dy * dy) ** 0.5

    # -- Aspect-correct shapes ----------------------------------------------

    def square_cells(self, world_size: float) -> tuple[int, int]:
        """Return the cell dimensions for a visually square region.

        Given a side length in world units, returns the (columns, rows)
        needed to display a visually square region in the terminal.

        Args:
            world_size: Side length in world units.

        Returns:
            A ``(columns, rows)`` tuple.  ``columns`` will be greater
            than ``rows`` when the aspect ratio is > 1.0 (the common
            case), because more columns are needed to match the visual
            height of the rows.

        Caveats:
            - Equivalent to ``world_to_cell_size(world_size, world_size)``.
            - The result may not be perfectly square due to rounding.
              For a world size of 5.0 with ratio 2.0, the result is
              ``(5, 3)`` — not exactly square, but as close as integer
              cell dimensions allow.
        """
        return self.world_to_cell_size(world_size, world_size)

    # -- Dunder methods -----------------------------------------------------

    def __repr__(self) -> str:
        detected = (
            f", detected={self._geometry.detected}"
            if self._geometry is not None
            else ""
        )
        return f"CellSizeMap(cell_aspect_ratio={self._cell_aspect_ratio}{detected})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, CellSizeMap):
            return NotImplemented
        return self._cell_aspect_ratio == other._cell_aspect_ratio
