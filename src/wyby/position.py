"""Position component for sub-cell entity positioning.

Provides a :class:`Position` component that stores float coordinates,
enabling smooth movement and sub-cell precision.  This complements the
:class:`~wyby.entity.Entity`'s built-in integer ``x``/``y`` grid
position with continuous coordinates.

Usage::

    from wyby.entity import Entity
    from wyby.position import Position

    e = Entity()
    pos = Position(3.5, 7.2)
    e.add_component(pos)

    # Read back
    assert pos.x == 3.5
    assert pos.y == 7.2

Caveats:
    - **Separate from Entity.x / Entity.y.**  The Entity class has its
      own integer ``x`` and ``y`` for grid-cell positioning.  The
      Position component stores independent float coordinates.  These
      two systems are **not** automatically synchronized — it is the
      game's responsibility to reconcile them (e.g. snapping
      ``entity.x = int(pos.x)`` each tick for rendering).
    - **Float precision.**  Coordinates are Python floats (64-bit IEEE
      754 doubles).  For typical game worlds (thousands of cells) this
      is far more than sufficient.  Precision degrades only at extreme
      magnitudes (~2^53), which is well beyond any practical grid size.
    - **No bounds enforcement.**  Coordinates can be negative or exceed
      the grid dimensions.  Clamping is the game's responsibility.
    - **Not a full physics system.**  Position stores coordinates and
      nothing more.  There is no collision detection, spatial indexing,
      or constraint solving.  For physics, pair this with
      :class:`~wyby.velocity.Velocity` for basic movement, and implement
      collision logic in your game code.
"""

from __future__ import annotations

from wyby.component import Component


class Position(Component):
    """Float-precision position component.

    Stores ``x`` and ``y`` as floats, allowing sub-cell precision for
    smooth movement, interpolation, and fractional positioning.

    Args:
        x: Horizontal position.  Defaults to ``0.0``.
        y: Vertical position.  Defaults to ``0.0``.

    Raises:
        TypeError: If *x* or *y* is not an int or float.

    Caveats:
        - **Coordinates are floats.**  Even if you pass ints, they are
          stored as floats.  ``Position(3, 4).x`` returns ``3.0``.
        - **Booleans are rejected.**  ``True``/``False`` are not accepted
          even though ``bool`` is a subclass of ``int`` in Python.
        - **Terminal grids use (0, 0) as top-left**, with x increasing
          rightward and y increasing downward.  This is opposite to
          mathematical convention where y increases upward.
    """

    __slots__ = ("_x", "_y")

    def __init__(self, x: float = 0.0, y: float = 0.0) -> None:
        super().__init__()
        if isinstance(x, bool) or not isinstance(x, (int, float)):
            raise TypeError(
                f"x must be a number (int or float), got {type(x).__name__}"
            )
        if isinstance(y, bool) or not isinstance(y, (int, float)):
            raise TypeError(
                f"y must be a number (int or float), got {type(y).__name__}"
            )
        self._x = float(x)
        self._y = float(y)

    @property
    def x(self) -> float:
        """Horizontal position."""
        return self._x

    @x.setter
    def x(self, value: float) -> None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(
                f"x must be a number (int or float), got {type(value).__name__}"
            )
        self._x = float(value)

    @property
    def y(self) -> float:
        """Vertical position."""
        return self._y

    @y.setter
    def y(self, value: float) -> None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(
                f"y must be a number (int or float), got {type(value).__name__}"
            )
        self._y = float(value)

    @property
    def xy(self) -> tuple[float, float]:
        """The ``(x, y)`` position as a tuple.

        Caveats:
            - Returns a new tuple each call.  Do not rely on identity
              (``is``) comparisons between tuples.
        """
        return (self._x, self._y)

    @xy.setter
    def xy(self, value: tuple[float, float]) -> None:
        if not isinstance(value, tuple) or len(value) != 2:
            raise TypeError("xy must be a (x, y) tuple of two numbers")
        x, y = value
        if isinstance(x, bool) or not isinstance(x, (int, float)):
            raise TypeError(
                f"x must be a number (int or float), got {type(x).__name__}"
            )
        if isinstance(y, bool) or not isinstance(y, (int, float)):
            raise TypeError(
                f"y must be a number (int or float), got {type(y).__name__}"
            )
        self._x = float(x)
        self._y = float(y)

    def __repr__(self) -> str:
        entity_info = (
            f"entity_id={self._entity.id}" if self._entity is not None
            else "detached"
        )
        return f"Position(x={self._x}, y={self._y}, {entity_info})"
