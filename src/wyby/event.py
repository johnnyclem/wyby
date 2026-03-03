"""Minimal event queue for the game loop.

This module provides a simple FIFO :class:`EventQueue` that game code and
engine subsystems use to communicate asynchronously within a single tick.
The intended usage pattern is:

1. Input layer (or any subsystem) **posts** events during the frame.
2. The game loop **drains** all queued events at the start of each tick
   and dispatches them to the active scene.

Events are plain, immutable objects.  This module defines a lightweight
:class:`Event` base class that all event types must inherit from.
Concrete event types (``KeyEvent``, ``MouseEvent``, custom game events)
will be defined in later modules — the queue itself is type-agnostic
and accepts any :class:`Event` subclass.

Caveats:
    - **Single-threaded only.**  The queue uses a plain
      :class:`collections.deque` with no locking.  It must only be
      accessed from the engine's main loop thread.  If you need to post
      events from another thread, you must add your own synchronization
      (e.g., wrap ``post`` in a ``threading.Lock``).
    - **Bounded by default.**  The queue enforces a maximum size
      (default 1024) to prevent unbounded memory growth from runaway
      event producers.  When the queue is full, new events are
      **dropped** (not queued) and a warning is logged.  This is a
      deliberate design choice — in a game loop, stale input events
      are worse than dropped ones because they cause perceived input
      lag.
    - **No priority or ordering guarantees beyond FIFO.**  Events are
      drained in the order they were posted.  There is no priority
      queue or event channel separation.  If ordering between
      subsystems matters, post events in the desired order.
    - **Events are not persisted.**  Draining clears the queue.  If
      you need event replay or history, implement that in game code.
    - **No automatic dispatching.**  The queue is a passive data
      structure.  Routing events to the correct handler is the
      responsibility of the scene or game loop, not the queue.
"""

from __future__ import annotations

import logging
from collections import deque

_logger = logging.getLogger(__name__)

# Default maximum number of events the queue can hold before dropping
# new arrivals.  1024 is generous — at 30 tps, that's ~34 seconds of
# events if every tick posts one event.  In practice, keyboard input
# rarely exceeds a handful of events per tick.  The limit guards
# against pathological producers (e.g., a bug that posts events in a
# loop).
_DEFAULT_MAX_SIZE = 1024
_MIN_MAX_SIZE = 1
_MAX_MAX_SIZE = 65536


class Event:
    """Base class for all game events.

    Events are lightweight, immutable-by-convention objects that flow
    through the :class:`EventQueue`.  Subclass this to define concrete
    event types (e.g., ``KeyEvent``, ``QuitRequestEvent``).

    The base class carries no data — it exists solely to provide a
    common type for the queue's type hints and ``isinstance`` checks.

    Caveats:
        - Events are **not** enforced to be immutable.  By convention,
          event attributes should be set at construction time and not
          modified afterward.  Mutating an event after posting it leads
          to unpredictable behaviour if the event is read multiple times
          or inspected by multiple handlers.
        - ``__eq__`` and ``__hash__`` are not overridden.  Events use
          identity-based equality by default.  Subclasses may override
          these if value-based comparison is needed.
    """

    __slots__ = ()

    def __repr__(self) -> str:
        return f"{type(self).__name__}()"


class EventQueue:
    """A bounded FIFO queue for :class:`Event` objects.

    The queue is designed to be drained once per game tick.  Subsystems
    post events throughout the frame, and the game loop drains them all
    at the start of the next tick via :meth:`drain`.

    Args:
        max_size: Maximum number of events the queue can hold.
            Must be between 1 and 65536. Defaults to 1024.

    Raises:
        TypeError: If *max_size* is not an integer.
        ValueError: If *max_size* is outside the allowed range.

    Caveats:
        - **Not thread-safe.**  Use only from the main loop thread.
          See module-level docstring for details.
        - When full, :meth:`post` silently drops new events and logs
          a warning.  This avoids blocking the game loop but means
          events can be lost under load.  Monitor the warning logs
          during development to detect if your ``max_size`` is too
          small.
        - :meth:`drain` returns a ``list``, not a generator.  The
          entire queue is copied and cleared atomically (relative to
          the single thread).  For typical event volumes (< 100 per
          tick) this is negligible.
    """

    __slots__ = ("_queue", "_max_size", "_drop_count")

    def __init__(self, max_size: int = _DEFAULT_MAX_SIZE) -> None:
        if not isinstance(max_size, int) or isinstance(max_size, bool):
            raise TypeError(
                f"max_size must be an int, got {type(max_size).__name__}"
            )
        if not (_MIN_MAX_SIZE <= max_size <= _MAX_MAX_SIZE):
            raise ValueError(
                f"max_size must be between {_MIN_MAX_SIZE} and "
                f"{_MAX_MAX_SIZE}, got {max_size}"
            )
        self._queue: deque[Event] = deque()
        self._max_size = max_size
        # Tracks cumulative drops for diagnostics.  Reset is the
        # caller's responsibility (or just read the warning logs).
        self._drop_count: int = 0
        _logger.debug("EventQueue created with max_size=%d", max_size)

    @property
    def max_size(self) -> int:
        """Maximum number of events the queue can hold."""
        return self._max_size

    @property
    def drop_count(self) -> int:
        """Cumulative number of events dropped due to the queue being full."""
        return self._drop_count

    def __len__(self) -> int:
        """Return the number of events currently in the queue."""
        return len(self._queue)

    def __bool__(self) -> bool:
        """Return ``True`` if the queue contains any events."""
        return len(self._queue) > 0

    @property
    def is_empty(self) -> bool:
        """Whether the queue contains no events."""
        return len(self._queue) == 0

    @property
    def is_full(self) -> bool:
        """Whether the queue has reached its maximum size."""
        return len(self._queue) >= self._max_size

    def post(self, event: Event) -> bool:
        """Add an event to the back of the queue.

        Args:
            event: The event to enqueue.  Must be an :class:`Event`
                instance.

        Returns:
            ``True`` if the event was successfully queued, ``False``
            if it was dropped because the queue is full.

        Raises:
            TypeError: If *event* is not an :class:`Event` instance.

        Caveats:
            - When the queue is full, the event is **dropped** (not
              queued) and a warning is logged.  The return value
              indicates whether the event was accepted.
            - Posting ``None`` or a non-Event object raises
              ``TypeError``.  This catches accidental misuse early.
        """
        if not isinstance(event, Event):
            raise TypeError(
                f"event must be an Event instance, got "
                f"{type(event).__name__}"
            )
        if len(self._queue) >= self._max_size:
            self._drop_count += 1
            _logger.warning(
                "EventQueue full (max_size=%d), dropping %r "
                "(total drops: %d)",
                self._max_size,
                event,
                self._drop_count,
            )
            return False
        self._queue.append(event)
        return True

    def drain(self) -> list[Event]:
        """Remove and return all events from the queue.

        Returns a list of events in FIFO order (oldest first) and
        clears the queue.  If the queue is empty, returns an empty
        list.

        This is the primary consumption API.  Call it once per tick
        at the start of the update phase.

        Returns:
            A list of all queued events, in posting order.

        Caveats:
            - The returned list is a snapshot.  Events posted *after*
              ``drain()`` returns will appear in the *next* drain.
            - The list may be empty if no events were posted since the
              last drain.  Callers should handle this gracefully.
        """
        if not self._queue:
            return []
        events = list(self._queue)
        self._queue.clear()
        return events

    def peek(self) -> Event | None:
        """Return the next event without removing it, or ``None`` if empty.

        Useful for inspecting the front of the queue without committing
        to consumption.
        """
        if self._queue:
            return self._queue[0]
        return None

    def clear(self) -> None:
        """Discard all queued events.

        This does **not** increment :attr:`drop_count` — clearing is
        an intentional action, not a capacity overflow.
        """
        count = len(self._queue)
        self._queue.clear()
        if count:
            _logger.debug("EventQueue cleared (%d events discarded)", count)

    def __repr__(self) -> str:
        return (
            f"EventQueue(len={len(self._queue)}, "
            f"max_size={self._max_size})"
        )
