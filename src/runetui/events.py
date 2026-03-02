"""Event system for RuneTUI.

Provides a minimal event queue and event types for input handling
and inter-system communication within the game loop.
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional

logger = logging.getLogger(__name__)


class EventType(Enum):
    """Types of events in the system."""

    KEY = auto()
    MOUSE = auto()
    QUIT = auto()
    RESIZE = auto()
    CUSTOM = auto()


@dataclass(frozen=True)
class Event:
    """Base event with a type identifier."""

    event_type: EventType
    data: Optional[dict] = None


@dataclass(frozen=True)
class KeyEvent(Event):
    """Keyboard input event.

    Caveat: Key detection accuracy depends on the input library and terminal.
    Some key combinations may not be detectable in all environments.
    """

    key: str = ""
    event_type: EventType = field(default=EventType.KEY, init=False)


@dataclass(frozen=True)
class MouseEvent(Event):
    """Mouse input event.

    Caveat: Mouse support is inconsistent across terminals. Hover and drag
    events may not be reliably detected. Bracketed paste mode and mouse
    tracking require explicit terminal support.
    """

    x: int = 0
    y: int = 0
    button: str = ""
    event_type: EventType = field(default=EventType.MOUSE, init=False)


class EventQueue:
    """Simple FIFO event queue for the game loop.

    Events are polled each frame during the input phase.
    """

    def __init__(self, max_size: int = 256) -> None:
        self._queue: deque[Event] = deque(maxlen=max_size)

    def push(self, event: Event) -> None:
        """Add an event to the queue."""
        self._queue.append(event)

    def poll(self) -> Optional[Event]:
        """Remove and return the next event, or None if empty."""
        if self._queue:
            return self._queue.popleft()
        return None

    def peek(self) -> Optional[Event]:
        """Return the next event without removing it, or None if empty."""
        if self._queue:
            return self._queue[0]
        return None

    def clear(self) -> None:
        """Discard all pending events."""
        self._queue.clear()

    def __len__(self) -> int:
        return len(self._queue)

    def __bool__(self) -> bool:
        return bool(self._queue)
