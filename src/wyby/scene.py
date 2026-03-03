"""Scene base class and scene stack management.

This module provides the :class:`Scene` abstract base class and a
:class:`SceneStack` that allows pushing, popping, and replacing scenes
(e.g., pushing a pause menu over gameplay).

Caveats:
    - Only the top scene on the stack receives input. Scenes below it
      may or may not update/render depending on their per-scene flags
      (:attr:`Scene.updates_when_paused`,
      :attr:`Scene.renders_when_paused`).  Both default to ``False``.
      For example, set ``renders_when_paused = True`` on a gameplay
      scene so it stays visible behind a transparent pause overlay.
    - Scenes own their entities and state. There is no implicit global
      state shared between scenes. Cross-scene communication must be
      done explicitly (e.g., via a shared context object passed to
      scene constructors).
    - Scene transitions (push, pop, replace) are explicit. There is no
      automatic transition animation system in v0.1.
    - The stack enforces a maximum depth (default 32) to catch runaway
      push loops. This limit is intentionally generous — most games
      need fewer than 10 stacked scenes. If you legitimately need more,
      pass a higher ``max_depth`` to :class:`SceneStack`.
    - :meth:`Scene.on_enter` and :meth:`Scene.on_exit` are called when
      a scene becomes or ceases to be the active (top) scene. They are
      **not** called when the scene is merely covered by another scene
      pushed on top. Override :meth:`on_pause` and :meth:`on_resume`
      for that case.  All four lifecycle hooks support callback-based
      hooks (``add_pause_hook``, ``add_resume_hook``, etc.) for
      external systems that need to react without subclassing.
    - :meth:`Scene.handle_events` is called once per tick with the
      list of events drained from the :class:`EventQueue`, **before**
      :meth:`Scene.update`. Only the top scene receives events.
      Scenes that do not need input can leave the default no-op.
    - :meth:`Scene.on_resize` is called when the terminal size changes.
      Unlike input events, **all** scenes on the stack receive resize
      notifications — not just the top scene — because paused scenes
      that render behind an overlay also need to adapt their layout.
      The callback receives ``(columns, rows)`` and defaults to a
      no-op.  Resize dispatch depends on the engine polling
      :class:`~wyby.resize.ResizeHandler` and calling
      :meth:`SceneStack.dispatch_resize`; if the engine does not do
      this, ``on_resize`` is never called.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterator
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from wyby.entity import Entity
    from wyby.event import Event

_logger = logging.getLogger(__name__)

# Default maximum scene stack depth.  32 is generous — most games use
# fewer than 10 levels (e.g., gameplay → pause → settings → confirm
# dialog).  The limit exists to catch accidental infinite push loops,
# not to constrain legitimate use.
_DEFAULT_MAX_DEPTH = 32
_MIN_MAX_DEPTH = 1
_MAX_MAX_DEPTH = 256


class Scene(ABC):
    """Abstract base class for game scenes.

    A scene is the primary organizational unit in wyby.  Each scene
    owns its own state and entities.  The game engine maintains a stack
    of scenes; only the top scene receives input and is guaranteed to
    be updated and rendered each tick.

    Subclasses must implement :meth:`update` and :meth:`render`.
    Override :meth:`handle_events` to process input each tick.
    Lifecycle hooks (:meth:`on_enter`, :meth:`on_exit`,
    :meth:`on_pause`, :meth:`on_resume`) are optional and default
    to no-ops.

    In addition to the override-based hooks, scenes support
    **callback-based hooks** via :meth:`add_enter_hook`,
    :meth:`add_exit_hook`, :meth:`add_pause_hook`,
    :meth:`add_resume_hook`, and :meth:`add_resize_hook`.  These
    allow external code (debug tools, analytics, sound managers)
    to react to scene transitions and terminal resize without
    subclassing.  For menus and pause overlays, the pause and
    resume hooks are particularly useful — e.g., pausing background
    music when a pause menu is pushed, and resuming it when the
    menu is popped.

    Caveats:
        - Scenes do **not** receive a reference to the engine or stack
          automatically. If a scene needs to trigger transitions (e.g.,
          push a pause menu), pass the engine or stack to the scene's
          constructor or use a callback pattern.
        - ``update`` and ``render`` are separate methods to allow the
          engine to call them at different rates in the future (e.g.,
          rendering at display refresh rate while updating at a fixed
          timestep). In v0.1 they are called 1:1 each tick.
        - By default, only the top scene is updated and rendered.
          Set :attr:`updates_when_paused` or :attr:`renders_when_paused`
          to ``True`` on a scene to keep it active when covered by
          another scene.  Even when updating while paused, a scene
          does **not** receive events — input always routes to the top
          scene only.
        - Subclasses that define ``__init__`` should call
          ``super().__init__()`` to ensure callback hook lists are
          initialized. If ``super().__init__()`` is not called,
          registered callbacks will still work (lazy initialization),
          but calling ``super().__init__()`` is the recommended pattern.
        - Registered callbacks are invoked **after** the overridden
          ``on_enter``/``on_exit``/``on_pause``/``on_resume`` method,
          in registration order.  If the overridden method raises,
          callbacks are not invoked.
        - Callbacks must not raise exceptions. If a callback raises,
          remaining callbacks in the list are skipped and the exception
          propagates. Guard your callbacks with try/except if they
          might fail.
    """

    def __init__(self) -> None:
        self._enter_hooks: list[Callable[[], None]] = []
        self._exit_hooks: list[Callable[[], None]] = []
        self._pause_hooks: list[Callable[[], None]] = []
        self._resume_hooks: list[Callable[[], None]] = []
        self._resize_hooks: list[Callable[[int, int], None]] = []
        self._updates_when_paused: bool = False
        self._renders_when_paused: bool = False
        self._entities: dict[int, Entity] = {}

    # ------------------------------------------------------------------
    # Per-scene update/render policy (paused scenes)
    # ------------------------------------------------------------------

    @property
    def updates_when_paused(self) -> bool:
        """Whether this scene's ``update()`` is called when it is not the
        top scene on the stack.

        Defaults to ``False``.  Set to ``True`` for scenes that should
        keep advancing game state while covered by another scene (e.g.,
        gameplay ticking behind a transparent pause overlay).

        Caveats:
            - A paused scene that updates does **not** receive events
              (``handle_events`` is always top-scene-only).  If your
              paused scene needs input, route it explicitly via a shared
              context object or custom events.
            - Update order is bottom-to-top.  If a lower scene's
              ``update()`` mutates the stack, the remaining scenes in
              the snapshot are still updated this tick.  Stack changes
              take full effect next tick.
        """
        return getattr(self, "_updates_when_paused", False)

    @updates_when_paused.setter
    def updates_when_paused(self, value: bool) -> None:
        self._updates_when_paused = bool(value)

    @property
    def renders_when_paused(self) -> bool:
        """Whether this scene's ``render()`` is called when it is not the
        top scene on the stack.

        Defaults to ``False``.  Set to ``True`` for scenes that should
        remain visible underneath the top scene (e.g., a gameplay scene
        rendering behind a semi-transparent HUD or pause menu).

        Caveats:
            - Render order is bottom-to-top within a single tick.
              Scenes rendered earlier may be fully or partially
              overwritten by scenes rendered later, depending on the
              renderer implementation.  wyby does not composite layers
              automatically — each scene writes to the same output
              surface.
            - Marking a scene as ``renders_when_paused`` does not
              guarantee it is *visible*.  If the top scene fills the
              entire screen with opaque content, lower scene renders
              are wasted work.  Games should set this flag only when
              the top scene is actually transparent or partial.
        """
        return getattr(self, "_renders_when_paused", False)

    @renders_when_paused.setter
    def renders_when_paused(self, value: bool) -> None:
        self._renders_when_paused = bool(value)

    @abstractmethod
    def update(self, dt: float) -> None:
        """Advance the scene's game state by one fixed timestep.

        Args:
            dt: The fixed timestep duration in seconds (same as
                ``Engine.target_dt``). Use this to scale velocities
                and animations for deterministic behaviour.
        """

    @abstractmethod
    def render(self) -> None:
        """Render the scene's current state.

        Called once per tick after :meth:`update`. The scene should
        write its visual output to a cell buffer or Rich renderable.
        The exact rendering mechanism will be defined when the renderer
        module is implemented.

        Caveats:
            - This method must **not** modify game state. Rendering
              should be a pure read of the scene's current state.
            - The renderer is not yet implemented, so this method is
              currently a no-op in practice. It exists to establish
              the interface contract.
        """

    # ------------------------------------------------------------------
    # Per-tick event handling (subclasses override this)
    # ------------------------------------------------------------------

    def handle_events(self, events: list[Event]) -> None:
        """Process input events for this tick.

        Called once per tick by the engine with all events drained from
        the :class:`~wyby.event.EventQueue`, **before** :meth:`update`.
        Override this to inspect, filter, or react to input events.

        The default implementation is a no-op.  Scenes that do not need
        input can leave it unoverridden.

        Args:
            events: A list of :class:`~wyby.event.Event` instances
                drained from the queue this tick, in FIFO order.
                May be empty if no events were posted.

        Caveats:
            - Only the **top** scene on the stack receives events.
              Scenes below it are paused and do not see input.
            - The list contains **all** event types
              (:class:`~wyby.input.KeyEvent`,
              :class:`~wyby.input.MouseEvent`, and any custom
              subclasses).  Filter with ``isinstance`` checks to
              handle specific types.
            - Mouse events are only present when the
              :class:`~wyby.input.InputManager` is configured with a
              mouse-enabled :class:`~wyby.input.InputMode`.
            - Events are delivered as a batch (the full drain), not
              one at a time.  If ordering between events matters,
              iterate the list in order.
            - Do **not** mutate the scene stack from within
              ``handle_events``.  Stack mutations take effect
              immediately and can confuse the current tick's
              update/render sequence.  Prefer setting a flag and
              performing the transition in :meth:`update`, or posting
              a custom event for the next tick.
            - This method should not raise exceptions during normal
              operation.  An unhandled exception will propagate
              through the engine's tick and trigger shutdown.
        """

    # ------------------------------------------------------------------
    # Override-based lifecycle hooks (subclasses override these)
    # ------------------------------------------------------------------

    def on_enter(self) -> None:
        """Called when this scene becomes the active (top) scene.

        This is invoked when the scene is first pushed onto the stack,
        or when it becomes the top scene again after the scene above it
        is popped.

        Override this to initialize resources, start music, etc.
        Registered enter-hook callbacks fire after this method returns.
        """

    def on_exit(self) -> None:
        """Called when this scene is removed from the stack.

        This is invoked when the scene is popped or replaced. Use it
        to clean up resources that should not persist after the scene
        is gone.

        Registered exit-hook callbacks fire after this method returns.

        Caveats:
            - ``on_exit`` is called **after** the scene is removed
              from the stack, so ``SceneStack.peek()`` will already
              return the new top scene (or ``None``).
        """

    def on_pause(self) -> None:
        """Called when another scene is pushed on top of this one.

        The scene is still on the stack but is no longer the active
        scene. Override this to pause music, timers, etc.
        """

    def on_resume(self) -> None:
        """Called when this scene becomes active again after being paused.

        This happens when the scene above it is popped. Override this
        to resume music, timers, etc.
        """

    def on_resize(self, columns: int, rows: int) -> None:
        """Called when the terminal is resized.

        Unlike input events, **all** scenes on the stack receive
        resize notifications — not just the top scene.  This is
        because paused scenes that render behind a transparent
        overlay (``renders_when_paused = True``) also need to know
        the new terminal dimensions in order to re-layout.

        Override this to recalculate layouts, reposition UI elements,
        or clamp entity positions to the new bounds.

        Args:
            columns: The new terminal width in columns.
            rows: The new terminal height in rows.

        Caveats:
            - This is only called when the engine's
              :class:`~wyby.resize.ResizeHandler` detects a resize
              **and** the engine calls
              :meth:`SceneStack.dispatch_resize`.  If the engine
              does not poll for resize, ``on_resize`` is never called.
            - The reported size comes from
              :func:`shutil.get_terminal_size`, which returns a
              fallback of ``(80, 24)`` when stdout is not a real
              terminal (piped output, CI, pytest capture).  Do not
              assume the values always reflect the actual display.
            - On some platforms, the size may lag behind the actual
              terminal by one frame after a resize, depending on when
              the OS updates the pty size.
            - This method is called synchronously in the game-loop
              thread.  Keep the implementation fast to avoid blocking
              the loop.
            - Resize may fire at any point in the tick (depending on
              when the engine polls).  Do not assume it runs before
              or after ``update()`` / ``render()`` in the same tick.
        """

    # ------------------------------------------------------------------
    # Entity management
    # ------------------------------------------------------------------

    @property
    def entities(self) -> list[Entity]:
        """A snapshot list of all entities in this scene.

        Returns a new list each call, ordered by insertion order.
        Mutating the returned list does not affect the scene — use
        :meth:`add_entity` and :meth:`remove_entity` instead.

        Caveats:
            - Returns a **copy**, not a live view.  Calling this in a
              tight loop (e.g. every frame for a large entity count)
              allocates a new list each time.  For iteration, prefer
              iterating directly or caching the result per tick.
            - Insertion order is preserved (dict ordering, Python 3.7+).
        """
        return list(self._entities.values())

    def add_entity(self, entity: Entity) -> None:
        """Add an entity to this scene.

        Args:
            entity: The entity to add.

        Raises:
            TypeError: If *entity* is not an :class:`~wyby.entity.Entity`.
            ValueError: If an entity with the same id is already in
                this scene.

        Caveats:
            - **No cross-scene ownership tracking.**  An entity can be
              added to multiple scenes simultaneously.  The framework
              does not enforce single-scene ownership — this is the
              game's responsibility.  Adding the same entity to two
              active scenes may cause it to be updated or rendered
              twice per tick.
            - **No spatial index.**  Adding an entity does not register
              it in any acceleration structure.  Spatial queries
              (:meth:`get_entities_at`) are O(n) over all entities.
              For games with hundreds of entities this is fine; for
              thousands, consider a spatial hash maintained in your
              scene subclass.
            - Duplicate detection is by entity :attr:`~wyby.entity.Entity.id`,
              not by identity (``is``).  Two different Entity objects
              with the same id cannot both be in the same scene.
        """
        from wyby.entity import Entity as _Entity

        if not isinstance(entity, _Entity):
            raise TypeError(
                f"entity must be an Entity instance, got {type(entity).__name__}"
            )
        if entity.id in self._entities:
            raise ValueError(
                f"Entity with id={entity.id} is already in this scene"
            )
        self._entities[entity.id] = entity
        _logger.debug(
            "Entity id=%d added to scene %s (count now %d)",
            entity.id, type(self).__name__, len(self._entities),
        )

    def remove_entity(self, entity: Entity) -> Entity:
        """Remove an entity from this scene and return it.

        Args:
            entity: The entity to remove.

        Returns:
            The removed entity.

        Raises:
            TypeError: If *entity* is not an :class:`~wyby.entity.Entity`.
            KeyError: If the entity is not in this scene.

        Caveats:
            - Removal is by entity :attr:`~wyby.entity.Entity.id`.  The
              entity object passed in must have the same id as the one
              stored; identity (``is``) is not checked.
            - **Safe during iteration.**  If you need to remove entities
              while iterating (e.g. despawning dead enemies in
              ``update``), iterate over a snapshot::

                  for e in list(self.entities):
                      if e.should_despawn:
                          self.remove_entity(e)

              Or collect ids to remove after the loop.
        """
        from wyby.entity import Entity as _Entity

        if not isinstance(entity, _Entity):
            raise TypeError(
                f"entity must be an Entity instance, got {type(entity).__name__}"
            )
        if entity.id not in self._entities:
            raise KeyError(
                f"Entity with id={entity.id} is not in this scene"
            )
        removed = self._entities.pop(entity.id)
        _logger.debug(
            "Entity id=%d removed from scene %s (count now %d)",
            entity.id, type(self).__name__, len(self._entities),
        )
        return removed

    def get_entity(self, entity_id: int) -> Entity | None:
        """Look up an entity by its id.

        Args:
            entity_id: The integer id to look up.

        Returns:
            The entity, or ``None`` if no entity with that id is in
            this scene.

        Caveats:
            - O(1) lookup via dict.
        """
        return self._entities.get(entity_id)

    def get_entities_at(self, x: int, y: int) -> list[Entity]:
        """Return all entities at the given grid position.

        Args:
            x: Horizontal grid position (column).
            y: Vertical grid position (row).

        Returns:
            A list of entities at ``(x, y)``, in insertion order.
            Empty if none are found.

        Caveats:
            - **O(n) scan** over all entities in the scene.  This is
              fine for scenes with up to a few hundred entities.  For
              thousands, maintain a spatial index (e.g. a dict keyed
              by ``(x, y)``) in your scene subclass and update it
              when entities move.
            - Checks ``entity.x`` and ``entity.y`` (the grid-cell
              position), not sub-cell :class:`~wyby.position.Position`
              component values.  If your entities use the Position
              component for smooth movement, you may need to convert
              to grid coordinates before querying.
        """
        return [e for e in self._entities.values() if e.x == x and e.y == y]

    def get_entities_by_tag(self, tag: str) -> list[Entity]:
        """Return all entities that have the given tag.

        Args:
            tag: The tag string to filter by.

        Returns:
            A list of matching entities, in insertion order.
            Empty if none match.

        Caveats:
            - **O(n) scan** over all entities in the scene.  If you
              frequently query by tag, consider maintaining a
              ``dict[str, set[Entity]]`` index in your scene subclass.
            - Tag matching is exact string equality; no wildcards or
              pattern matching.
        """
        return [e for e in self._entities.values() if e.has_tag(tag)]

    # ------------------------------------------------------------------
    # Callback-based hooks (register/remove without subclassing)
    # ------------------------------------------------------------------

    def add_enter_hook(self, callback: Callable[[], None]) -> None:
        """Register a callback invoked when this scene enters.

        Callbacks run after :meth:`on_enter`, in registration order.

        Args:
            callback: A zero-argument callable.

        Raises:
            TypeError: If *callback* is not callable.

        Caveats:
            - The same callback can be registered multiple times and
              will be called once per registration.
            - Callbacks must not raise. An exception in a callback
              prevents subsequent callbacks from running.
        """
        if not callable(callback):
            raise TypeError(
                f"callback must be callable, got {type(callback).__name__}"
            )
        # Lazy init for subclasses that don't call super().__init__().
        if not hasattr(self, "_enter_hooks"):
            self._enter_hooks = []
        self._enter_hooks.append(callback)

    def remove_enter_hook(self, callback: Callable[[], None]) -> None:
        """Remove a previously registered on-enter callback.

        Only the first matching registration is removed.

        Args:
            callback: The callback to remove.

        Raises:
            ValueError: If *callback* is not registered.
        """
        hooks = getattr(self, "_enter_hooks", [])
        hooks.remove(callback)  # raises ValueError if not found

    def add_exit_hook(self, callback: Callable[[], None]) -> None:
        """Register a callback invoked when this scene exits.

        Callbacks run after :meth:`on_exit`, in registration order.

        Args:
            callback: A zero-argument callable.

        Raises:
            TypeError: If *callback* is not callable.

        Caveats:
            - The same callback can be registered multiple times and
              will be called once per registration.
            - Callbacks must not raise. An exception in a callback
              prevents subsequent callbacks from running.
        """
        if not callable(callback):
            raise TypeError(
                f"callback must be callable, got {type(callback).__name__}"
            )
        if not hasattr(self, "_exit_hooks"):
            self._exit_hooks = []
        self._exit_hooks.append(callback)

    def remove_exit_hook(self, callback: Callable[[], None]) -> None:
        """Remove a previously registered on-exit callback.

        Only the first matching registration is removed.

        Args:
            callback: The callback to remove.

        Raises:
            ValueError: If *callback* is not registered.
        """
        hooks = getattr(self, "_exit_hooks", [])
        hooks.remove(callback)  # raises ValueError if not found

    def add_pause_hook(self, callback: Callable[[], None]) -> None:
        """Register a callback invoked when this scene is paused.

        Callbacks run after :meth:`on_pause`, in registration order.
        A scene is paused when another scene is pushed on top of it.

        Args:
            callback: A zero-argument callable.

        Raises:
            TypeError: If *callback* is not callable.

        Caveats:
            - The same callback can be registered multiple times and
              will be called once per registration.
            - Callbacks must not raise. An exception in a callback
              prevents subsequent callbacks from running.
            - Pause hooks are useful for external systems (sound
              managers, timers, analytics) that need to react when a
              menu or overlay is pushed over this scene.
        """
        if not callable(callback):
            raise TypeError(
                f"callback must be callable, got {type(callback).__name__}"
            )
        if not hasattr(self, "_pause_hooks"):
            self._pause_hooks = []
        self._pause_hooks.append(callback)

    def remove_pause_hook(self, callback: Callable[[], None]) -> None:
        """Remove a previously registered on-pause callback.

        Only the first matching registration is removed.

        Args:
            callback: The callback to remove.

        Raises:
            ValueError: If *callback* is not registered.
        """
        hooks = getattr(self, "_pause_hooks", [])
        hooks.remove(callback)  # raises ValueError if not found

    def add_resume_hook(self, callback: Callable[[], None]) -> None:
        """Register a callback invoked when this scene resumes.

        Callbacks run after :meth:`on_resume`, in registration order.
        A scene resumes when the scene above it is popped.

        Args:
            callback: A zero-argument callable.

        Raises:
            TypeError: If *callback* is not callable.

        Caveats:
            - The same callback can be registered multiple times and
              will be called once per registration.
            - Callbacks must not raise. An exception in a callback
              prevents subsequent callbacks from running.
            - Resume hooks are useful for external systems (sound
              managers, timers) that need to restart when returning
              from a menu or overlay.
        """
        if not callable(callback):
            raise TypeError(
                f"callback must be callable, got {type(callback).__name__}"
            )
        if not hasattr(self, "_resume_hooks"):
            self._resume_hooks = []
        self._resume_hooks.append(callback)

    def remove_resume_hook(self, callback: Callable[[], None]) -> None:
        """Remove a previously registered on-resume callback.

        Only the first matching registration is removed.

        Args:
            callback: The callback to remove.

        Raises:
            ValueError: If *callback* is not registered.
        """
        hooks = getattr(self, "_resume_hooks", [])
        hooks.remove(callback)  # raises ValueError if not found

    def add_resize_hook(self, callback: Callable[[int, int], None]) -> None:
        """Register a callback invoked when the terminal is resized.

        Callbacks run after :meth:`on_resize`, in registration order.
        Each callback receives ``(columns, rows)`` as positional
        arguments.

        Args:
            callback: A callable accepting two ints (columns, rows).

        Raises:
            TypeError: If *callback* is not callable.

        Caveats:
            - The same callback can be registered multiple times and
              will be called once per registration.
            - Callbacks must not raise. An exception in a callback
              prevents subsequent callbacks from running.
            - Unlike enter/exit/pause/resume hooks which take zero
              arguments, resize hooks receive the new terminal
              dimensions ``(columns, rows)``.
        """
        if not callable(callback):
            raise TypeError(
                f"callback must be callable, got {type(callback).__name__}"
            )
        if not hasattr(self, "_resize_hooks"):
            self._resize_hooks = []
        self._resize_hooks.append(callback)

    def remove_resize_hook(self, callback: Callable[[int, int], None]) -> None:
        """Remove a previously registered on-resize callback.

        Only the first matching registration is removed.

        Args:
            callback: The callback to remove.

        Raises:
            ValueError: If *callback* is not registered.
        """
        hooks = getattr(self, "_resize_hooks", [])
        hooks.remove(callback)  # raises ValueError if not found

    # ------------------------------------------------------------------
    # Internal: fire hooks (called by SceneStack)
    # ------------------------------------------------------------------

    def _fire_enter(self) -> None:
        """Invoke on_enter() then all registered enter callbacks."""
        self.on_enter()
        for cb in getattr(self, "_enter_hooks", ()):
            cb()

    def _fire_exit(self) -> None:
        """Invoke on_exit() then all registered exit callbacks."""
        self.on_exit()
        for cb in getattr(self, "_exit_hooks", ()):
            cb()

    def _fire_pause(self) -> None:
        """Invoke on_pause() then all registered pause callbacks."""
        self.on_pause()
        for cb in getattr(self, "_pause_hooks", ()):
            cb()

    def _fire_resume(self) -> None:
        """Invoke on_resume() then all registered resume callbacks."""
        self.on_resume()
        for cb in getattr(self, "_resume_hooks", ()):
            cb()

    def _fire_resize(self, columns: int, rows: int) -> None:
        """Invoke on_resize(columns, rows) then all registered resize callbacks."""
        self.on_resize(columns, rows)
        for cb in getattr(self, "_resize_hooks", ()):
            cb(columns, rows)


class SceneStack:
    """A stack of :class:`Scene` instances with push, pop, and replace.

    The stack follows last-in-first-out (LIFO) semantics. Only the
    topmost scene is considered "active" — it receives input and is
    updated/rendered by the engine each tick.

    Args:
        max_depth: Maximum number of scenes allowed on the stack.
            Must be between 1 and 256. Defaults to 32.

    Raises:
        TypeError: If *max_depth* is not an integer.
        ValueError: If *max_depth* is outside the allowed range.

    Caveats:
        - The stack does **not** own or manage scene lifetimes beyond
          calling lifecycle hooks. Scenes are not garbage-collected
          when popped — they remain alive as long as the caller holds
          a reference.
        - ``push`` and ``replace`` accept any :class:`Scene` subclass
          instance. The stack does not enforce uniqueness — the same
          scene instance can be pushed multiple times, though this is
          rarely useful and may cause confusing lifecycle hook calls.
        - All operations are synchronous and not thread-safe. The
          scene stack should only be mutated from the engine's main
          loop thread.
    """

    __slots__ = ("_stack", "_max_depth")

    def __init__(self, max_depth: int = _DEFAULT_MAX_DEPTH) -> None:
        if not isinstance(max_depth, int) or isinstance(max_depth, bool):
            raise TypeError(
                f"max_depth must be an int, got {type(max_depth).__name__}"
            )
        if not (_MIN_MAX_DEPTH <= max_depth <= _MAX_MAX_DEPTH):
            raise ValueError(
                f"max_depth must be between {_MIN_MAX_DEPTH} and "
                f"{_MAX_MAX_DEPTH}, got {max_depth}"
            )
        self._stack: list[Scene] = []
        self._max_depth = max_depth
        _logger.debug("SceneStack created with max_depth=%d", max_depth)

    @property
    def max_depth(self) -> int:
        """Maximum number of scenes allowed on the stack."""
        return self._max_depth

    def __len__(self) -> int:
        """Return the number of scenes currently on the stack."""
        return len(self._stack)

    def __bool__(self) -> bool:
        """Return ``True`` if the stack is non-empty."""
        return len(self._stack) > 0

    @property
    def is_empty(self) -> bool:
        """Whether the stack has no scenes."""
        return len(self._stack) == 0

    def __contains__(self, scene: object) -> bool:
        """Check whether a scene instance is on the stack.

        Uses identity comparison (``is``), not equality.  This is
        useful for the common menu/pause pattern of checking whether
        a pause menu is already on the stack before pushing a second
        one::

            if pause_menu not in engine.scenes:
                engine.push_scene(pause_menu)

        Caveats:
            - This is an O(n) scan.  For typical stack depths (< 10)
              this is negligible.
            - Checks identity, not type.  Two different instances of
              the same scene class are considered different scenes.
        """
        return any(s is scene for s in self._stack)

    def __iter__(self) -> Iterator[Scene]:
        """Iterate over scenes from bottom to top.

        Yields a snapshot — mutating the stack during iteration does
        not affect the iterator.

        Caveats:
            - Bottom-to-top order matches render and update order.
              The last yielded scene is the active (top) scene.
        """
        yield from list(self._stack)

    def peek(self) -> Scene | None:
        """Return the top scene without removing it, or ``None`` if empty.

        This is the scene that should receive input and be updated
        each tick.
        """
        if self._stack:
            return self._stack[-1]
        return None

    def scenes_to_update(self) -> list[Scene]:
        """Return a snapshot of scenes whose ``update()`` should be called.

        The top scene is always included.  Paused scenes (those below
        the top) are included only if their
        :attr:`~Scene.updates_when_paused` flag is ``True``.

        The returned list is ordered bottom-to-top so that lower scenes
        update before higher ones within the same tick.  Returns an
        empty list if the stack is empty.

        Caveats:
            - The list is a **snapshot**.  If a scene's ``update()``
              mutates the stack (push/pop/replace), the remaining
              scenes in the list are still updated.  Stack changes
              take full effect next tick.
            - Only the top scene receives events via
              :meth:`Scene.handle_events`.  Paused scenes that update
              do **not** receive input.
        """
        if not self._stack:
            return []
        result: list[Scene] = []
        # Paused scenes (all except top) — include if they opted in.
        for scene in self._stack[:-1]:
            if scene.updates_when_paused:
                result.append(scene)
        # Top scene always updates.
        result.append(self._stack[-1])
        return result

    def scenes_to_render(self) -> list[Scene]:
        """Return a snapshot of scenes whose ``render()`` should be called.

        The top scene is always included.  Paused scenes (those below
        the top) are included only if their
        :attr:`~Scene.renders_when_paused` flag is ``True``.

        The returned list is ordered bottom-to-top so that lower
        scenes render first and higher scenes paint over them.
        Returns an empty list if the stack is empty.

        Caveats:
            - The list is a **snapshot**.  Stack mutations during
              rendering take effect next tick.
            - wyby does not composite scene output automatically.
              Each scene writes to the same output surface.  If the
              top scene fills the screen with opaque content, renders
              from lower scenes are wasted work.
            - ``render()`` must not modify game state — it should be a
              pure read of each scene's current state.
        """
        if not self._stack:
            return []
        result: list[Scene] = []
        for scene in self._stack[:-1]:
            if scene.renders_when_paused:
                result.append(scene)
        result.append(self._stack[-1])
        return result

    def push(self, scene: Scene) -> None:
        """Push a scene onto the top of the stack.

        If there is already a scene on top, its :meth:`Scene.on_pause`
        hook is called before the new scene's :meth:`Scene.on_enter`.

        Args:
            scene: The scene to push.

        Raises:
            TypeError: If *scene* is not a :class:`Scene` instance.
            RuntimeError: If the stack has reached ``max_depth``.

        Caveats:
            - Pushing the same scene instance that is already on the
              stack is allowed but discouraged — it will receive
              ``on_pause``/``on_enter`` calls that may cause confusing
              state if not handled carefully.
        """
        if not isinstance(scene, Scene):
            raise TypeError(
                f"scene must be a Scene instance, got {type(scene).__name__}"
            )
        if len(self._stack) >= self._max_depth:
            raise RuntimeError(
                f"Scene stack depth limit reached ({self._max_depth}). "
                f"This likely indicates a runaway push loop. If you "
                f"legitimately need more scenes, increase max_depth."
            )

        # Pause the current top scene before pushing the new one.
        current = self.peek()
        if current is not None:
            _logger.debug(
                "Pausing scene %r (depth %d)", type(current).__name__, len(self._stack)
            )
            current._fire_pause()

        self._stack.append(scene)
        _logger.debug(
            "Pushed scene %r (depth now %d)",
            type(scene).__name__,
            len(self._stack),
        )
        scene._fire_enter()

    def pop(self) -> Scene:
        """Remove and return the top scene from the stack.

        The popped scene's :meth:`Scene.on_exit` is called. If there
        is a scene beneath it, that scene's :meth:`Scene.on_resume`
        is called (it becomes the new active scene).

        Returns:
            The scene that was removed.

        Raises:
            RuntimeError: If the stack is empty.
        """
        if not self._stack:
            raise RuntimeError("Cannot pop from an empty scene stack")

        scene = self._stack.pop()
        _logger.debug(
            "Popped scene %r (depth now %d)",
            type(scene).__name__,
            len(self._stack),
        )
        scene._fire_exit()

        # Resume the scene that is now on top (if any).
        new_top = self.peek()
        if new_top is not None:
            _logger.debug(
                "Resuming scene %r (depth %d)",
                type(new_top).__name__,
                len(self._stack),
            )
            new_top._fire_resume()

        return scene

    def replace(self, scene: Scene) -> Scene:
        """Replace the top scene with a new one.

        This is equivalent to a pop followed by a push, but the
        scene beneath the old top does **not** receive ``on_resume``
        or ``on_pause`` calls — only the replaced scene gets
        ``on_exit`` and the new scene gets ``on_enter``.

        Args:
            scene: The new scene to place on top.

        Returns:
            The scene that was replaced.

        Raises:
            TypeError: If *scene* is not a :class:`Scene` instance.
            RuntimeError: If the stack is empty (nothing to replace).

        Caveats:
            - ``replace`` does not trigger ``on_pause``/``on_resume``
              on the scene below the top. This is intentional — a
              replace is a lateral transition, not a push/pop pair.
              If you need those hooks, call ``pop`` then ``push``
              explicitly.
        """
        if not isinstance(scene, Scene):
            raise TypeError(
                f"scene must be a Scene instance, got {type(scene).__name__}"
            )
        if not self._stack:
            raise RuntimeError(
                "Cannot replace on an empty scene stack"
            )

        old_scene = self._stack.pop()
        _logger.debug(
            "Replacing scene %r with %r (depth %d)",
            type(old_scene).__name__,
            type(scene).__name__,
            len(self._stack) + 1,
        )
        old_scene._fire_exit()

        self._stack.append(scene)
        scene._fire_enter()

        return old_scene

    def dispatch_events(self, events: list[Event]) -> bool:
        """Route input events to the top scene on the stack.

        This is the formal input routing entry point.  The engine calls
        this once per tick (after draining the event queue, before update)
        to deliver input to the active scene.

        Only the **top** scene receives events.  Scenes below it — even
        those with :attr:`~Scene.updates_when_paused` set to ``True`` —
        do **not** see input.  If a paused scene needs to react to input,
        route it explicitly via a shared context object, custom events
        posted to the queue, or the :class:`~wyby.input_context.InputContextStack`.

        Args:
            events: A list of :class:`~wyby.event.Event` instances
                drained from the :class:`~wyby.event.EventQueue` this
                tick, in FIFO order.  May be empty.

        Returns:
            ``True`` if events were delivered to a scene, ``False`` if
            the stack was empty and events were discarded.

        Caveats:
            - **Top-scene-only routing.**  This is a deliberate design
              choice, not an oversight.  Routing input to multiple scenes
              simultaneously creates ambiguity about which scene "owns" a
              key press, leading to duplicate actions or swallowed input.
              The scene stack's push/pop model means exactly one scene is
              in focus at any time — the same model used by OS window
              managers and mobile navigation stacks.
            - **Events are passed by reference.**  The list is not copied
              before delivery.  If the scene mutates the list (e.g.,
              removes handled events), the caller sees those mutations.
              The engine drains into a fresh list each tick, so this is
              safe in practice, but custom callers should be aware.
            - **No filtering or transformation.**  All event types
              (``KeyEvent``, ``MouseEvent``, custom subclasses) are
              delivered as a single batch.  Per-type routing is the
              scene's responsibility — use ``isinstance`` checks or a
              :class:`~wyby.keymap.KeyMap` to dispatch by type.
            - **Empty event lists are delivered.**  When no events were
              queued, the scene still receives an empty list.  This is
              intentional — it lets scenes distinguish "no input this
              tick" from "not receiving input at all" (which happens to
              paused scenes that never get ``handle_events`` called).
            - **Stack mutations during dispatch.**  If the scene's
              ``handle_events()`` mutates the stack (push/pop/replace),
              those changes take effect immediately.  This can cause the
              *new* top scene's ``update()`` to run in the same tick.
              Prefer setting a flag and performing transitions in
              ``update()`` to avoid mid-tick surprises.
            - **Exceptions propagate.**  If ``handle_events()`` raises,
              the exception propagates to the caller (typically
              ``Engine._tick``).  The engine treats unhandled exceptions
              as fatal and triggers shutdown.
        """
        top = self.peek()
        if top is None:
            if events:
                _logger.debug(
                    "dispatch_events: stack empty, discarding %d event(s)",
                    len(events),
                )
            return False
        top.handle_events(events)
        return True

    def dispatch_resize(self, columns: int, rows: int) -> bool:
        """Notify all scenes on the stack of a terminal resize.

        Unlike :meth:`dispatch_events` (top-scene-only), resize is
        dispatched to **every** scene on the stack, bottom-to-top.
        This is because all scenes — including paused ones that render
        behind an overlay — may need to adapt their layout to the new
        terminal dimensions.

        The engine should call this when
        :meth:`~wyby.resize.ResizeHandler.consume` returns ``True``.

        Args:
            columns: The new terminal width in columns.
            rows: The new terminal height in rows.

        Returns:
            ``True`` if at least one scene was notified, ``False`` if
            the stack was empty.

        Caveats:
            - **All scenes are notified**, not just the top scene.
              A paused gameplay scene behind a pause overlay may need
              to re-layout its grid to the new terminal size.
            - Dispatch order is bottom-to-top, matching the update and
              render order.  If a scene's ``on_resize`` mutates the
              stack, the remaining scenes in the snapshot are still
              notified.
            - Scenes that do not care about resize can leave
              ``on_resize`` as the default no-op.  There is no per-scene
              flag to opt out — the cost of calling a no-op on a few
              scenes is negligible.
            - The values come from :func:`shutil.get_terminal_size`
              via the :class:`~wyby.resize.ResizeHandler`.  See
              :meth:`Scene.on_resize` caveats for accuracy notes.
        """
        if not self._stack:
            _logger.debug(
                "dispatch_resize: stack empty, ignoring %dx%d",
                columns,
                rows,
            )
            return False

        # Snapshot the stack so mutations during on_resize don't
        # affect the iteration.
        snapshot = list(self._stack)
        _logger.debug(
            "Dispatching resize %dx%d to %d scene(s)",
            columns,
            rows,
            len(snapshot),
        )
        for scene in snapshot:
            scene._fire_resize(columns, rows)
        return True

    def clear(self) -> None:
        """Remove all scenes from the stack.

        Each scene's :meth:`Scene.on_exit` is called in top-to-bottom
        order (the topmost scene exits first).

        Caveats:
            - No ``on_resume`` calls are made during clear — every
              scene is exiting, so there is no scene that "resumes."
        """
        _logger.debug("Clearing scene stack (depth %d)", len(self._stack))
        while self._stack:
            scene = self._stack.pop()
            _logger.debug(
                "Clearing scene %r (depth now %d)",
                type(scene).__name__,
                len(self._stack),
            )
            scene._fire_exit()

    def __repr__(self) -> str:
        scene_names = [type(s).__name__ for s in self._stack]
        return f"SceneStack({scene_names!r}, max_depth={self._max_depth})"
