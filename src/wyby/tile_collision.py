"""Tile-based collision detection for grid maps.

Provides :class:`TileMap` for defining 2D grids of solid/passable tiles
and querying whether a position or rectangular region collides with solid
geometry.  This complements :mod:`wyby.collision` (entity-vs-entity AABB)
with map-vs-entity collision.

Usage::

    from wyby.tile_collision import TileMap

    # Create an 8×6 map, all tiles passable by default
    tm = TileMap(width=8, height=6)

    # Mark walls
    tm.set_solid(0, 0)
    tm.set_solid(1, 0)
    tm.fill_solid(0, 5, 8, 1)  # floor across the bottom row

    # Point query
    if tm.is_solid(3, 2):
        print("blocked!")

    # Region query — does a 2×2 entity at (4, 3) hit any solid tile?
    if tm.region_has_solid(4, 3, 2, 2):
        print("entity collides with map geometry")

Caveats:
    - **Detection only, no response.**  This module answers "is this tile
      solid?" and "does this region overlap any solid tile?" — it does not
      block movement, slide along walls, or resolve penetration.  Response
      logic belongs in the game's update loop.
    - **Binary solid/passable only.**  Each tile is either solid or not.
      There are no partial-solidity flags, one-way platforms, slope tiles,
      or per-edge blocking.  Games needing richer tile properties should
      layer additional data structures on top.
    - **No tile type or metadata storage.**  ``TileMap`` stores a boolean
      grid, not tile IDs, terrain types, or rendering data.  It is purely
      a collision mask.  Pair it with your own tile-type grid for rendering
      and gameplay logic.
    - **Integer coordinates only.**  All positions and sizes are ints that
      match the Entity grid model.  For sub-cell precision (e.g. from a
      ``Position`` component), truncate or round floats before querying.
    - **No spatial indexing overhead.**  Lookups are O(1) per tile via
      direct array indexing.  Region queries are O(w×h) where w and h are
      the region dimensions — typically small for single entities.
    - **Out-of-bounds is configurable.**  By default, coordinates outside
      the map are treated as solid (``default_solid=True``).  This
      prevents entities from escaping the map.  Set ``default_solid=False``
      if you want open boundaries.
    - **No automatic resize.**  The map dimensions are fixed at
      construction.  If your game world changes size, create a new
      ``TileMap``.
    - **Terminal cells are not square.**  A typical terminal cell is
      roughly twice as tall as it is wide (~1:2 aspect ratio).  This
      module operates in cell coordinates and does not correct for aspect
      ratio — a "square" region in tile coordinates will look rectangular
      on screen.
"""

from __future__ import annotations


class TileMap:
    """A 2D grid of solid/passable tiles for collision queries.

    The map uses row-major storage with (x, y) public API coordinates
    where x is the column and y is the row, matching :class:`wyby.grid.CellBuffer`.

    Args:
        width: Number of columns.  Must be a positive int.
        height: Number of rows.  Must be a positive int.
        default_solid: Whether out-of-bounds coordinates are treated as
            solid (``True``, the default) or passable (``False``).

    Raises:
        TypeError: If *width* or *height* is not an int (booleans rejected).
        ValueError: If *width* or *height* is less than 1.

    Caveats:
        - **Top-left origin.**  ``(0, 0)`` is the top-left corner.
          x increases rightward, y increases downward — same as terminal
          convention and :class:`wyby.grid.CellBuffer`.
        - **All tiles start passable.**  Call :meth:`set_solid`,
          :meth:`fill_solid`, or :meth:`load` to mark solid tiles.
    """

    __slots__ = ("_width", "_height", "_default_solid", "_grid")

    def __init__(
        self,
        width: int,
        height: int,
        *,
        default_solid: bool = True,
    ) -> None:
        if isinstance(width, bool) or not isinstance(width, int):
            raise TypeError(
                f"width must be an int, got {type(width).__name__}"
            )
        if isinstance(height, bool) or not isinstance(height, int):
            raise TypeError(
                f"height must be an int, got {type(height).__name__}"
            )
        if width < 1:
            raise ValueError(f"width must be >= 1, got {width}")
        if height < 1:
            raise ValueError(f"height must be >= 1, got {height}")
        if not isinstance(default_solid, bool):
            raise TypeError(
                f"default_solid must be a bool, got {type(default_solid).__name__}"
            )
        self._width = width
        self._height = height
        self._default_solid = default_solid
        # Row-major: _grid[row][col].  All tiles start passable (False).
        self._grid: list[list[bool]] = [
            [False] * width for _ in range(height)
        ]

    @property
    def width(self) -> int:
        """Number of columns in the map."""
        return self._width

    @property
    def height(self) -> int:
        """Number of rows in the map."""
        return self._height

    @property
    def default_solid(self) -> bool:
        """Whether out-of-bounds coordinates are treated as solid."""
        return self._default_solid

    def _in_bounds(self, x: int, y: int) -> bool:
        """Return True if (x, y) is within the map boundaries."""
        return 0 <= x < self._width and 0 <= y < self._height

    def is_solid(self, x: int, y: int) -> bool:
        """Test whether the tile at ``(x, y)`` is solid.

        Args:
            x: Column index.
            y: Row index.

        Returns:
            ``True`` if the tile is solid.  For out-of-bounds coordinates,
            returns :attr:`default_solid`.

        Raises:
            TypeError: If *x* or *y* is not an int (booleans rejected).

        Caveats:
            - O(1) lookup via direct array indexing.
        """
        _validate_point(x, y)
        if not self._in_bounds(x, y):
            return self._default_solid
        return self._grid[y][x]

    def set_solid(self, x: int, y: int, solid: bool = True) -> None:
        """Mark the tile at ``(x, y)`` as solid or passable.

        Args:
            x: Column index.
            y: Row index.
            solid: ``True`` to mark solid, ``False`` to mark passable.

        Raises:
            TypeError: If *x* or *y* is not an int, or *solid* is not a bool.
            ValueError: If ``(x, y)`` is out of bounds.
        """
        _validate_point(x, y)
        if not isinstance(solid, bool):
            raise TypeError(
                f"solid must be a bool, got {type(solid).__name__}"
            )
        if not self._in_bounds(x, y):
            raise ValueError(
                f"({x}, {y}) is out of bounds for {self._width}×{self._height} map"
            )
        self._grid[y][x] = solid

    def fill_solid(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        solid: bool = True,
    ) -> None:
        """Mark a rectangular region of tiles as solid or passable.

        The region spans from ``(x, y)`` to ``(x + width - 1, y + height - 1)``
        inclusive.  Tiles outside the map boundaries are silently skipped.

        Args:
            x: Left column of the region.
            y: Top row of the region.
            width: Number of columns in the region.  Must be non-negative.
            height: Number of rows in the region.  Must be non-negative.
            solid: ``True`` to mark solid, ``False`` to mark passable.

        Raises:
            TypeError: If any coordinate/size is not an int, or *solid* is
                not a bool.
            ValueError: If *width* or *height* is negative.
        """
        _validate_point(x, y)
        _validate_size(width, height)
        if not isinstance(solid, bool):
            raise TypeError(
                f"solid must be a bool, got {type(solid).__name__}"
            )
        # Clamp to map boundaries for the actual fill.
        x0 = max(x, 0)
        y0 = max(y, 0)
        x1 = min(x + width, self._width)
        y1 = min(y + height, self._height)
        for row in range(y0, y1):
            for col in range(x0, x1):
                self._grid[row][col] = solid

    def region_has_solid(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
    ) -> bool:
        """Test whether any tile in a rectangular region is solid.

        The region spans from ``(x, y)`` to ``(x + width - 1, y + height - 1)``
        inclusive.  If any part of the region extends outside the map,
        those out-of-bounds tiles use :attr:`default_solid`.

        Args:
            x: Left column of the query region.
            y: Top row of the query region.
            width: Number of columns.  Must be non-negative.
            height: Number of rows.  Must be non-negative.

        Returns:
            ``True`` if at least one tile in the region is solid.

        Raises:
            TypeError: If any argument is not an int (booleans rejected).
            ValueError: If *width* or *height* is negative.

        Caveats:
            - **Zero-size regions.**  If *width* or *height* is 0, the
              region contains no tiles and the result is always ``False``.
            - **O(w×h) per call** where w and h are the region dimensions.
              For single entities this is typically O(1) to O(4).
        """
        _validate_point(x, y)
        _validate_size(width, height)
        if width == 0 or height == 0:
            return False
        for row in range(y, y + height):
            for col in range(x, x + width):
                if not self._in_bounds(col, row):
                    if self._default_solid:
                        return True
                else:
                    if self._grid[row][col]:
                        return True
        return False

    def load(self, data: list[list[int]]) -> None:
        """Load solidity data from a 2D list of ints.

        Each element should be ``0`` (passable) or non-zero (solid).
        The outer list is rows (y), the inner list is columns (x).

        Args:
            data: A list of *height* rows, each a list of *width* ints.

        Raises:
            TypeError: If *data* is not a list of lists of ints.
            ValueError: If *data* dimensions do not match the map size.

        Example::

            tm = TileMap(4, 3)
            tm.load([
                [1, 1, 1, 1],  # top wall
                [1, 0, 0, 1],  # side walls, open middle
                [1, 1, 1, 1],  # bottom wall
            ])
        """
        if not isinstance(data, list):
            raise TypeError(
                f"data must be a list, got {type(data).__name__}"
            )
        if len(data) != self._height:
            raise ValueError(
                f"data has {len(data)} rows, expected {self._height}"
            )
        for row_idx, row in enumerate(data):
            if not isinstance(row, list):
                raise TypeError(
                    f"row {row_idx} must be a list, got {type(row).__name__}"
                )
            if len(row) != self._width:
                raise ValueError(
                    f"row {row_idx} has {len(row)} columns, expected {self._width}"
                )
            for col_idx, val in enumerate(row):
                if isinstance(val, bool) or not isinstance(val, int):
                    raise TypeError(
                        f"data[{row_idx}][{col_idx}] must be an int, "
                        f"got {type(val).__name__}"
                    )
                self._grid[row_idx][col_idx] = val != 0

    def clear(self) -> None:
        """Reset all tiles to passable."""
        for row in self._grid:
            for col in range(len(row)):
                row[col] = False

    def __repr__(self) -> str:
        return (
            f"TileMap(width={self._width}, height={self._height}, "
            f"default_solid={self._default_solid})"
        )


def _validate_point(x: int, y: int) -> None:
    """Validate that x and y are ints (not bools)."""
    if isinstance(x, bool) or not isinstance(x, int):
        raise TypeError(f"x must be an int, got {type(x).__name__}")
    if isinstance(y, bool) or not isinstance(y, int):
        raise TypeError(f"y must be an int, got {type(y).__name__}")


def _validate_size(width: int, height: int) -> None:
    """Validate that width and height are non-negative ints."""
    if isinstance(width, bool) or not isinstance(width, int):
        raise TypeError(
            f"width must be an int, got {type(width).__name__}"
        )
    if isinstance(height, bool) or not isinstance(height, int):
        raise TypeError(
            f"height must be an int, got {type(height).__name__}"
        )
    if width < 0:
        raise ValueError(f"width must be non-negative, got {width}")
    if height < 0:
        raise ValueError(f"height must be non-negative, got {height}")
