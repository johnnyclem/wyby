"""Velocity component for entity movement.

Provides a :class:`Velocity` component that stores directional speed
(cells per second) and applies it to a :class:`~wyby.position.Position`
component during :meth:`update`.

Usage::

    from wyby.entity import Entity
    from wyby.position import Position
    from wyby.velocity import Velocity

    e = Entity()
    e.add_component(Position(0.0, 0.0))
    e.add_component(Velocity(5.0, 0.0))  # 5 cells/sec rightward

    # Each tick, call update to apply velocity:
    vel = e._components[Velocity]
    vel.update(1 / 30)  # dt = one tick at 30 FPS

Caveats:
    - **Requires a Position component.**  ``update(dt)`` modifies the
      :class:`~wyby.position.Position` component on the same entity.
      If the entity has no Position component, ``update`` is a no-op.
      No error is raised — this allows temporarily detaching Position
      without crashing the game loop.
    - **Does not update Entity.x / Entity.y.**  The Entity's built-in
      integer coordinates are not touched.  Synchronizing those (e.g.
      ``entity.x = int(pos.x)``) is the game's responsibility, typically
      done once per frame after all velocity updates.
    - **Units are cells per second.**  If your fixed timestep is 1/30,
      a velocity of ``(30.0, 0.0)`` moves the entity one cell per tick.
    - **No acceleration or friction.**  This is a constant-velocity
      component.  For acceleration, modify ``vx``/``vy`` from your game
      logic each tick, or implement a dedicated physics component.
    - **No collision detection.**  Velocity moves the position
      unconditionally.  Collision response is the game's responsibility.
    - **Float precision.**  Same caveats as
      :class:`~wyby.position.Position` — 64-bit floats are more than
      sufficient for typical game worlds.
"""

from __future__ import annotations

from wyby.component import Component


class Velocity(Component):
    """Velocity component storing directional speed in cells per second.

    Stores ``vx`` and ``vy`` as floats.  When :meth:`update` is called,
    the velocity is applied to the entity's
    :class:`~wyby.position.Position` component.

    Args:
        vx: Horizontal velocity (cells per second).  Positive = rightward.
            Defaults to ``0.0``.
        vy: Vertical velocity (cells per second).  Positive = downward.
            Defaults to ``0.0``.

    Raises:
        TypeError: If *vx* or *vy* is not an int or float.

    Caveats:
        - **Booleans are rejected**, same as :class:`Position`.
        - **Downward is positive vy.**  Terminal grids have y increasing
          downward, so positive ``vy`` moves the entity down the screen.
    """

    __slots__ = ("_vx", "_vy")

    def __init__(self, vx: float = 0.0, vy: float = 0.0) -> None:
        super().__init__()
        if isinstance(vx, bool) or not isinstance(vx, (int, float)):
            raise TypeError(
                f"vx must be a number (int or float), got {type(vx).__name__}"
            )
        if isinstance(vy, bool) or not isinstance(vy, (int, float)):
            raise TypeError(
                f"vy must be a number (int or float), got {type(vy).__name__}"
            )
        self._vx = float(vx)
        self._vy = float(vy)

    @property
    def vx(self) -> float:
        """Horizontal velocity in cells per second."""
        return self._vx

    @vx.setter
    def vx(self, value: float) -> None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(
                f"vx must be a number (int or float), "
                f"got {type(value).__name__}"
            )
        self._vx = float(value)

    @property
    def vy(self) -> float:
        """Vertical velocity in cells per second."""
        return self._vy

    @vy.setter
    def vy(self, value: float) -> None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(
                f"vy must be a number (int or float), "
                f"got {type(value).__name__}"
            )
        self._vy = float(value)

    def update(self, dt: float) -> None:
        """Apply velocity to the entity's Position component.

        Adds ``vx * dt`` to the Position's x and ``vy * dt`` to
        the Position's y.

        If the entity has no :class:`~wyby.position.Position` component,
        this method does nothing (no error is raised).

        Args:
            dt: Time elapsed since the last tick, in seconds.

        Caveats:
            - **No-op without Position.**  If the owning entity lacks a
              Position component, the velocity is silently ignored.
              This avoids crashing if Position is temporarily removed.
            - **dt should be a fixed timestep**, not wall-clock delta,
              to ensure deterministic movement.
        """
        if self._entity is None:
            return
        from wyby.position import Position
        pos = self._entity._components.get(Position)
        if pos is None:
            return
        pos._x += self._vx * dt
        pos._y += self._vy * dt

    def __repr__(self) -> str:
        entity_info = (
            f"entity_id={self._entity.id}" if self._entity is not None
            else "detached"
        )
        return f"Velocity(vx={self._vx}, vy={self._vy}, {entity_info})"
