"""Component system for RuneTUI entities.

Components are simple data containers attached to entities. This is not a full
ECS (Entity-Component-System) implementation — there are no systems in the MVP.
Components hold data; update logic lives in scene update methods or entity
update calls.
"""

from __future__ import annotations

from dataclasses import dataclass


class Component:
    """Base class for all components.

    Subclass this to define custom data components for entities.
    """

    pass


@dataclass
class Position(Component):
    """2D position in terminal cell coordinates.

    Note: Terminal cells are typically taller than they are wide (roughly 2:1
    aspect ratio). Movement that appears uniform in code may look stretched
    vertically on screen.
    """

    x: float = 0.0
    y: float = 0.0


@dataclass
class Velocity(Component):
    """2D velocity in cells per second.

    Applied during entity update to modify Position. Actual movement per frame
    depends on delta_time, which varies with frame rate.
    """

    vx: float = 0.0
    vy: float = 0.0
