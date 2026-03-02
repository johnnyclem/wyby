"""Basic collision detection for RuneTUI.

Provides simple AABB (Axis-Aligned Bounding Box) collision checks and
basic velocity/physics helpers. This is not a full physics engine — there
is no continuous collision detection, no spatial partitioning, and no
complex shapes. All coordinates are in terminal cell space.
"""

from __future__ import annotations

from dataclasses import dataclass

from runetui.components import Position, Velocity
from runetui.entity import Entity


@dataclass
class AABB:
    """Axis-Aligned Bounding Box for collision detection.

    Coordinates are in terminal cell space. Note that terminal cells
    have a roughly 2:1 aspect ratio, so a "square" AABB will appear
    rectangular on screen.
    """

    x: float
    y: float
    width: float
    height: float

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def bottom(self) -> float:
        return self.y + self.height

    def overlaps(self, other: AABB) -> bool:
        """Check if this AABB overlaps with another."""
        return (
            self.x < other.right
            and self.right > other.x
            and self.y < other.bottom
            and self.bottom > other.y
        )

    @classmethod
    def from_entity(cls, entity: Entity, width: float = 1.0, height: float = 1.0) -> AABB:
        """Create an AABB from an entity's position."""
        pos = entity.get_component(Position)
        if pos is None:
            return cls(0, 0, width, height)
        return cls(pos.x, pos.y, width, height)


def check_aabb_collision(a: Entity, b: Entity, a_size: tuple[float, float] = (1.0, 1.0), b_size: tuple[float, float] = (1.0, 1.0)) -> bool:
    """Check if two entities' AABBs overlap.

    Args:
        a: First entity (must have Position component).
        b: Second entity (must have Position component).
        a_size: (width, height) of entity a's bounding box.
        b_size: (width, height) of entity b's bounding box.

    Returns:
        True if the bounding boxes overlap.
    """
    box_a = AABB.from_entity(a, *a_size)
    box_b = AABB.from_entity(b, *b_size)
    return box_a.overlaps(box_b)


def apply_velocity(entity: Entity, dt: float, gravity: float = 0.0, friction: float = 0.0) -> None:
    """Update an entity's position using its velocity, with optional gravity and friction.

    Args:
        entity: Entity with Position and Velocity components.
        dt: Delta time in seconds.
        gravity: Downward acceleration in cells/s^2 (applied to vy).
        friction: Deceleration factor (0.0 = none, 1.0 = full stop).
            Applied as velocity *= (1 - friction * dt).
    """
    vel = entity.get_component(Velocity)
    pos = entity.get_component(Position)
    if vel is None or pos is None:
        return

    # Apply gravity
    if gravity != 0.0:
        vel.vy += gravity * dt

    # Apply friction
    if friction > 0.0:
        factor = max(0.0, 1.0 - friction * dt)
        vel.vx *= factor
        vel.vy *= factor

    # Update position
    pos.x += vel.vx * dt
    pos.y += vel.vy * dt
