"""Scene management for RuneTUI.

Scenes represent distinct game states (menu, gameplay, pause). The engine
maintains a scene stack — only the top scene receives input and updates.
Scenes can be pushed, popped, or replaced.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional

from runetui.entity import Entity
from runetui.events import Event

if TYPE_CHECKING:
    from runetui.engine import Engine
    from runetui.renderer import Renderer

logger = logging.getLogger(__name__)


class Scene(ABC):
    """Abstract base class for game scenes.

    Subclass this and implement handle_event, update, and render.
    Optionally override on_enter, on_exit, and on_resize for lifecycle hooks.

    Each scene maintains its own entity list. Input is routed only to the
    top scene on the stack.
    """

    def __init__(self) -> None:
        self.engine: Optional[Engine] = None
        self.entities: list[Entity] = []

    def on_enter(self) -> None:
        """Called when this scene becomes the active (top) scene.

        Override to initialize resources, start music, etc.
        """
        pass

    def on_exit(self) -> None:
        """Called when this scene is removed from the top of the stack.

        Override to clean up resources.
        """
        pass

    def on_resize(self, width: int, height: int) -> None:
        """Called when the terminal is resized.

        Caveat: Resize detection reliability varies by terminal. Some terminals
        do not send SIGWINCH. The width/height values come from os.get_terminal_size()
        which may not reflect the actual renderable area.
        """
        pass

    @abstractmethod
    def handle_event(self, event: Event) -> None:
        """Process a single event (key press, mouse click, etc.).

        Called once per event during the input phase.
        """
        ...

    @abstractmethod
    def update(self, dt: float) -> None:
        """Update game logic for this scene.

        Args:
            dt: Delta time in seconds since the last update.
        """
        ...

    @abstractmethod
    def render(self, renderer: Renderer) -> None:
        """Draw this scene to the renderer's buffer.

        Called after update. Write into the renderer's buffer using
        draw_text, draw_rect, etc. Do not call present() — the engine
        handles that.
        """
        ...

    def add_entity(self, entity: Entity) -> Entity:
        """Add an entity to this scene's entity list."""
        self.entities.append(entity)
        return entity

    def remove_dead_entities(self) -> None:
        """Remove entities that have been marked as destroyed."""
        self.entities = [e for e in self.entities if e.alive]

    def get_entities_with(self, component_type: type) -> list[Entity]:
        """Query entities that have a specific component type."""
        return [e for e in self.entities if e.has_component(component_type)]
