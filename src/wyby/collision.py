"""Axis-Aligned Bounding Box (AABB) collision detection.

Provides :class:`AABB` for defining rectangular bounding boxes and
:func:`aabb_overlap` for testing whether two boxes intersect.  This is
the simplest useful collision primitive for grid-based terminal games.

Usage::

    from wyby.collision import AABB, aabb_overlap

    player = AABB(x=5, y=3, width=2, height=2)
    wall = AABB(x=6, y=4, width=3, height=1)

    if aabb_overlap(player, wall):
        # handle collision
        ...

Caveats:
    - **Detection only, no response.**  This module answers "do these
      two boxes overlap?" — it does not resolve collisions, apply
      forces, or separate overlapping bodies.  Response logic (blocking
      movement, bouncing, taking damage) is the game's responsibility.
    - **No spatial indexing.**  Testing all entity pairs is O(n²).  For
      games with dozens of entities this is fine.  For hundreds or more,
      you'll want a broad-phase structure (grid hash, sweep-and-prune)
      that this module does not provide.
    - **Terminal cells are not square.**  A typical terminal cell is
      roughly twice as tall as it is wide (~1:2 aspect ratio).  An AABB
      of ``width=2, height=2`` looks like a tall rectangle on screen,
      not a square.  This module operates in cell coordinates and does
      not correct for aspect ratio — visual and logical extents differ.
    - **Integer coordinates only.**  Positions and sizes are ints to
      match the Entity grid model.  For sub-cell precision, round your
      float positions before constructing an AABB.
    - **Edge-touching counts as overlap.**  Two boxes that share an
      edge or corner are considered overlapping.  If you need
      strict-interior-only overlap, subtract 1 from the comparison
      (i.e. use ``<`` instead of ``<=``).
    - **Zero-size boxes.**  An AABB with ``width=0`` or ``height=0`` is
      degenerate and will never overlap with anything.
    - **No rotation.**  Axis-aligned means the edges are always parallel
      to the x and y axes.  Rotated collision requires OBB (Oriented
      Bounding Box), which is not provided.
"""

from __future__ import annotations


class AABB:
    """An axis-aligned bounding box defined by position and size.

    The box spans from ``(x, y)`` to ``(x + width - 1, y + height - 1)``
    in cell coordinates, inclusive.  This matches the convention that an
    entity at position ``(5, 3)`` with ``width=2, height=2`` occupies
    cells ``(5,3), (6,3), (5,4), (6,4)``.

    Args:
        x: Left edge (column) of the box.
        y: Top edge (row) of the box.
        width: Horizontal extent in cells.  Must be non-negative.
        height: Vertical extent in cells.  Must be non-negative.

    Raises:
        TypeError: If any argument is not an int (booleans rejected).
        ValueError: If *width* or *height* is negative.

    Caveats:
        - **Top-left origin.**  Follows terminal convention: (0, 0) is
          the top-left corner, x increases rightward, y increases
          downward.
        - **Width/height of 1 means a single cell.**  An entity that
          occupies one cell has ``width=1, height=1``.
        - **Negative positions are allowed.**  Useful for entities that
          are partially off-screen or for scrolling viewports.
    """

    __slots__ = ("x", "y", "width", "height")

    def __init__(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
    ) -> None:
        if isinstance(x, bool) or not isinstance(x, int):
            raise TypeError(
                f"x must be an int, got {type(x).__name__}"
            )
        if isinstance(y, bool) or not isinstance(y, int):
            raise TypeError(
                f"y must be an int, got {type(y).__name__}"
            )
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
        self.x = x
        self.y = y
        self.width = width
        self.height = height

    @property
    def right(self) -> int:
        """X coordinate one past the right edge (exclusive).

        For a box at ``x=5`` with ``width=3``, ``right`` is ``8``.
        The occupied columns are 5, 6, 7.
        """
        return self.x + self.width

    @property
    def bottom(self) -> int:
        """Y coordinate one past the bottom edge (exclusive).

        For a box at ``y=2`` with ``height=4``, ``bottom`` is ``6``.
        The occupied rows are 2, 3, 4, 5.
        """
        return self.y + self.height

    def contains_point(self, px: int, py: int) -> bool:
        """Test whether the point ``(px, py)`` lies inside this box.

        Points on the boundary are considered inside.

        Args:
            px: X coordinate of the point.
            py: Y coordinate of the point.

        Returns:
            ``True`` if the point is inside or on the edge of the box.

        Caveats:
            - Returns ``False`` for degenerate boxes (zero width or
              height) since they have no interior.
        """
        return (
            self.x <= px < self.right
            and self.y <= py < self.bottom
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, AABB):
            return NotImplemented
        return (
            self.x == other.x
            and self.y == other.y
            and self.width == other.width
            and self.height == other.height
        )

    def __repr__(self) -> str:
        return (
            f"AABB(x={self.x}, y={self.y}, "
            f"width={self.width}, height={self.height})"
        )


def aabb_overlap(a: AABB, b: AABB) -> bool:
    """Test whether two axis-aligned bounding boxes overlap.

    Uses the separating-axis test: two AABBs do **not** overlap if and
    only if there is a gap between them on at least one axis.  This
    function returns ``True`` when the boxes share at least one cell.

    Args:
        a: First bounding box.
        b: Second bounding box.

    Returns:
        ``True`` if the boxes overlap (share at least one cell),
        ``False`` otherwise.

    Caveats:
        - **Edge-touching counts as overlap** by the strict inequality
          check (``<`` on exclusive bounds).  Two boxes where
          ``a.right == b.x`` do NOT overlap since ``right`` is
          exclusive.
        - **Degenerate boxes** (zero width or height) never overlap.
        - **Same box overlaps itself** (unless degenerate).
        - **O(1) per pair.**  This is a constant-time check.  Testing
          all pairs in a scene is O(n²) which is fine for small entity
          counts.  For large counts, use a spatial index to prune pairs
          before calling this function.

    Example::

        a = AABB(0, 0, 4, 4)
        b = AABB(3, 3, 4, 4)
        assert aabb_overlap(a, b)  # overlapping corner

        c = AABB(10, 10, 2, 2)
        assert not aabb_overlap(a, c)  # far apart
    """
    if a.width == 0 or a.height == 0 or b.width == 0 or b.height == 0:
        return False

    # Separating-axis test on each axis.  The boxes overlap if and only
    # if they overlap on BOTH axes.  They do not overlap on an axis if
    # one box is entirely to one side of the other on that axis.
    #
    # Using exclusive right/bottom bounds: a.right is x + width, so
    # a box at x=0, width=4 occupies columns 0..3.  If b.x == 4,
    # there is no shared column.
    if a.right <= b.x or b.right <= a.x:
        return False
    if a.bottom <= b.y or b.bottom <= a.y:
        return False

    return True
