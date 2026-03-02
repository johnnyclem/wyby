"""Entity system for RuneTUI.

Entities are lightweight containers that hold components. Each entity has a
unique ID and a dictionary of components keyed by type. This is intentionally
simple — a full ECS with systems can be built on top later.
"""

from __future__ import annotations

import itertools
import logging
from typing import Optional, Type, TypeVar

from runetui.components import Component, Position, Velocity

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=Component)

_id_counter = itertools.count(1)


class Entity:
    """A game entity composed of components.

    Entities are simple containers with an auto-incrementing ID.
    Attach components (Position, Velocity, custom) to define behavior.
    """

    def __init__(self, x: float = 0.0, y: float = 0.0) -> None:
        self.id: int = next(_id_counter)
        self._components: dict[type, Component] = {}
        self._alive: bool = True
        # Convenience: always start with a Position component
        self.add_component(Position(x=x, y=y))

    @property
    def position(self) -> Position:
        """Shortcut to the Position component."""
        return self.get_component(Position)  # type: ignore[return-value]

    @property
    def alive(self) -> bool:
        return self._alive

    def add_component(self, component: Component) -> None:
        """Attach a component to this entity, replacing any existing of the same type."""
        self._components[type(component)] = component

    def remove_component(self, component_type: Type[T]) -> Optional[T]:
        """Remove and return a component by type, or None if not present."""
        return self._components.pop(component_type, None)  # type: ignore[return-value]

    def get_component(self, component_type: Type[T]) -> Optional[T]:
        """Retrieve a component by type, or None if not attached."""
        return self._components.get(component_type)  # type: ignore[return-value]

    def has_component(self, component_type: Type[Component]) -> bool:
        """Check whether a component of the given type is attached."""
        return component_type in self._components

    def update(self, dt: float) -> None:
        """Apply basic physics: velocity updates position.

        This is a convenience method. For complex logic, handle updates
        in the scene's update method instead.
        """
        vel = self.get_component(Velocity)
        pos = self.get_component(Position)
        if vel and pos:
            pos.x += vel.vx * dt
            pos.y += vel.vy * dt

    def destroy(self) -> None:
        """Mark this entity for removal."""
        self._alive = False
        logger.debug("Entity %d destroyed", self.id)
