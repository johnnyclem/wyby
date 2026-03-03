"""Cell-level collision accuracy utilities.

Provides functions to inspect, verify, and debug collision detection
accuracy at the cell level.  These are useful for:

- Enumerating the exact cells occupied by a bounding box.
- Computing the overlap region (intersection) of two AABBs.
- Detecting tunneling risk when entities move fast relative to
  obstacle thickness.
- Measuring cell-distance between two AABBs.

Usage::

    from wyby.collision import AABB
    from wyby.collision_accuracy import (
        cells_occupied,
        overlap_region,
        overlap_cells,
        check_tunneling_risk,
        cell_distance,
    )

    box = AABB(2, 3, 3, 2)
    assert (2, 3) in cells_occupied(box)
    assert len(cells_occupied(box)) == 6  # 3 wide × 2 tall

    a = AABB(0, 0, 4, 4)
    b = AABB(2, 2, 4, 4)
    region = overlap_region(a, b)  # AABB(2, 2, 2, 2)
    shared = overlap_cells(a, b)  # {(2,2), (2,3), (3,2), (3,3)}

    # Will a 30-cell/sec entity tunnel through a 1-cell-thick wall?
    assert check_tunneling_risk(speed=30.0, dt=1/30, thickness=1)

Caveats:
    - **Integer cell coordinates only.**  All functions operate on the
      integer grid used by :class:`~wyby.collision.AABB` and
      :class:`~wyby.entity.Entity`.  Float positions from
      :class:`~wyby.position.Position` must be converted to ints
      (via :func:`~wyby.physics.sync_positions` or manual truncation)
      before using these functions.
    - **Truncation bias.**  :func:`~wyby.physics.sync_positions` uses
      ``int()`` (truncation toward zero), not ``round()``.  This means
      ``Position(2.9, 3.9)`` maps to cell ``(2, 3)``, not ``(3, 4)``.
      Collision checks against the integer grid therefore have up to
      one cell of positional error in each axis.  For sub-cell-accurate
      collision, compare float positions directly rather than relying
      on the integer grid.
    - **Terminal cells are not square.**  A typical terminal cell has
      ~1:2 aspect ratio (width:height).  A ``cell_distance`` of 5 in
      the x-axis covers roughly half the screen distance of 5 cells in
      the y-axis.  These functions operate in cell coordinates and do
      not correct for aspect ratio.
    - **No spatial indexing.**  ``cells_occupied`` and ``overlap_cells``
      enumerate cells explicitly.  For large bounding boxes this
      allocates proportionally large sets.  These functions are intended
      for testing and debugging, not tight inner loops.
    - **Tunneling detection is conservative.**  ``check_tunneling_risk``
      uses a simple displacement-vs-thickness comparison.  It does not
      account for intermediate positions or swept-volume tests.  A
      ``True`` result means tunneling *could* happen, not that it *will*.
"""

from __future__ import annotations

import math

from wyby.collision import AABB, aabb_overlap


def cells_occupied(box: AABB) -> frozenset[tuple[int, int]]:
    """Return the set of ``(x, y)`` cells occupied by a bounding box.

    Each cell in the box's extent is included, from ``(box.x, box.y)``
    to ``(box.x + box.width - 1, box.y + box.height - 1)`` inclusive.

    Args:
        box: The bounding box to enumerate.

    Returns:
        A frozenset of ``(x, y)`` tuples for every cell the box covers.
        Empty for degenerate boxes (zero width or height).

    Raises:
        TypeError: If *box* is not an :class:`~wyby.collision.AABB`.

    Caveats:
        - **O(w × h) time and space.**  Intended for testing and
          debugging, not for per-frame use with large boxes.
        - **Degenerate boxes return an empty set.**
    """
    if not isinstance(box, AABB):
        raise TypeError(f"box must be an AABB, got {type(box).__name__}")
    if box.width == 0 or box.height == 0:
        return frozenset()
    return frozenset(
        (x, y)
        for y in range(box.y, box.bottom)
        for x in range(box.x, box.right)
    )


def overlap_region(a: AABB, b: AABB) -> AABB | None:
    """Compute the intersection rectangle of two AABBs.

    If the boxes overlap, returns a new :class:`~wyby.collision.AABB`
    representing the shared rectangular region.  If they do not overlap,
    returns ``None``.

    Args:
        a: First bounding box.
        b: Second bounding box.

    Returns:
        An :class:`~wyby.collision.AABB` for the intersection, or
        ``None`` if the boxes do not overlap.

    Raises:
        TypeError: If *a* or *b* is not an :class:`~wyby.collision.AABB`.

    Caveats:
        - **Degenerate boxes never overlap** (consistent with
          :func:`~wyby.collision.aabb_overlap`).
        - The returned AABB may have width or height of 1 when boxes
          share exactly one row or column of cells.
    """
    if not isinstance(a, AABB):
        raise TypeError(f"a must be an AABB, got {type(a).__name__}")
    if not isinstance(b, AABB):
        raise TypeError(f"b must be an AABB, got {type(b).__name__}")
    if not aabb_overlap(a, b):
        return None
    x = max(a.x, b.x)
    y = max(a.y, b.y)
    right = min(a.right, b.right)
    bottom = min(a.bottom, b.bottom)
    return AABB(x, y, right - x, bottom - y)


def overlap_cells(a: AABB, b: AABB) -> frozenset[tuple[int, int]]:
    """Return the set of ``(x, y)`` cells shared by two overlapping AABBs.

    This is equivalent to ``cells_occupied(overlap_region(a, b))`` but
    returns an empty frozenset (instead of raising) when the boxes do
    not overlap.

    Args:
        a: First bounding box.
        b: Second bounding box.

    Returns:
        A frozenset of ``(x, y)`` tuples for every shared cell.
        Empty if the boxes do not overlap or either is degenerate.

    Raises:
        TypeError: If *a* or *b* is not an :class:`~wyby.collision.AABB`.

    Caveats:
        - **O(w × h) time and space** where w and h are the dimensions
          of the overlap region.
    """
    region = overlap_region(a, b)
    if region is None:
        return frozenset()
    return cells_occupied(region)


def check_tunneling_risk(
    speed: float,
    dt: float,
    thickness: int = 1,
) -> bool:
    """Check whether an entity's speed risks tunneling through obstacles.

    Tunneling occurs when an entity moves far enough in a single tick
    to skip entirely over a thin obstacle.  This function compares the
    per-tick displacement (``speed × dt``) against the obstacle
    *thickness* in cells.

    Args:
        speed: Entity speed in cells per second (magnitude, always
            non-negative).  For 2D velocity ``(vx, vy)``, pass
            ``math.hypot(vx, vy)``.
        dt: Time step in seconds.
        thickness: Obstacle thickness in cells.  Defaults to 1 (a
            single-cell wall, the most vulnerable case).

    Returns:
        ``True`` if the displacement per tick exceeds the obstacle
        thickness, meaning tunneling is possible.

    Raises:
        TypeError: If *speed* or *dt* is not a number, or *thickness*
            is not an int.
        ValueError: If *speed* is negative, *dt* is negative, NaN, or
            infinite, or *thickness* is less than 1.

    Caveats:
        - **Conservative estimate.**  A ``True`` result means tunneling
          *could* happen under worst-case alignment (entity heading
          straight at the obstacle's thinnest axis).  Actual tunneling
          also depends on collision-check timing and obstacle placement.
        - **Does not account for aspect ratio.**  Speed is assumed to
          be in cell units.  Since terminal cells are ~1:2, horizontal
          and vertical speeds cover different screen distances.
        - **Mitigation strategies** when this returns ``True``:
          reduce ``dt`` (substep), cap entity speed, increase obstacle
          thickness, or implement swept/continuous collision detection
          (not provided by wyby).
    """
    # Validate speed.
    if isinstance(speed, bool) or not isinstance(speed, (int, float)):
        raise TypeError(
            f"speed must be a number, got {type(speed).__name__}"
        )
    if speed < 0:
        raise ValueError(f"speed must be non-negative, got {speed}")

    # Validate dt.
    if isinstance(dt, bool) or not isinstance(dt, (int, float)):
        raise TypeError(
            f"dt must be a number, got {type(dt).__name__}"
        )
    if math.isnan(dt) or math.isinf(dt):
        raise ValueError(f"dt must be finite, got {dt}")
    if dt < 0:
        raise ValueError(f"dt must be non-negative, got {dt}")

    # Validate thickness.
    if isinstance(thickness, bool) or not isinstance(thickness, int):
        raise TypeError(
            f"thickness must be an int, got {type(thickness).__name__}"
        )
    if thickness < 1:
        raise ValueError(
            f"thickness must be >= 1, got {thickness}"
        )

    displacement = speed * dt
    return displacement > thickness


def cell_distance(a: AABB, b: AABB) -> int:
    """Compute the minimum Chebyshev distance between two AABBs in cells.

    The Chebyshev distance is the minimum number of single-cell moves
    (including diagonals) needed to reach from one box to the other.
    Overlapping boxes have distance 0.

    Args:
        a: First bounding box.
        b: Second bounding box.

    Returns:
        The minimum Chebyshev distance in cells.  ``0`` when the boxes
        overlap or touch.

    Raises:
        TypeError: If *a* or *b* is not an :class:`~wyby.collision.AABB`.

    Caveats:
        - **Degenerate boxes.**  A zero-width or zero-height box is
          treated as having no extent.  The distance is computed from
          the box's position point if degenerate.
        - **Chebyshev, not Euclidean.**  ``cell_distance`` returns
          ``max(dx, dy)`` not ``sqrt(dx² + dy²)``.  This matches the
          movement model where diagonal moves cost the same as
          cardinal moves.
        - **Aspect ratio not corrected.**  A distance of 5 horizontally
          covers different screen space than 5 vertically in a terminal.
    """
    if not isinstance(a, AABB):
        raise TypeError(f"a must be an AABB, got {type(a).__name__}")
    if not isinstance(b, AABB):
        raise TypeError(f"b must be an AABB, got {type(b).__name__}")

    # Compute gap on each axis.  If ranges overlap, gap is 0.
    # For degenerate boxes (width=0 or height=0), right==x or bottom==y,
    # so the range is empty.  We use the position point in that case.
    dx = max(0, max(a.x - b.right, b.x - a.right))
    if a.width > 0 and b.width > 0:
        dx = max(0, max(a.x - (b.right - 1), b.x - (a.right - 1)))

    dy = max(0, max(a.y - b.bottom, b.y - a.bottom))
    if a.height > 0 and b.height > 0:
        dy = max(0, max(a.y - (b.bottom - 1), b.y - (a.bottom - 1)))

    return max(dx, dy)
