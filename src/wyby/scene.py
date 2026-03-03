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
      for that case.
    - :meth:`Scene.handle_events` is called once per tick with the
      list of events drained from the :class:`EventQueue`, **before**
      :meth:`Scene.update`. Only the top scene receives events.
      Scenes that do not need input can leave the default no-op.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
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
    :meth:`add_exit_hook`, etc. These allow external code (debug
    tools, analytics, sound managers) to react to scene transitions
    without subclassing.

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
          ``on_enter``/``on_exit`` method, in registration order.
          If the overridden method raises, callbacks are not invoked.
        - Callbacks must not raise exceptions. If a callback raises,
          remaining callbacks in the list are skipped and the exception
          propagates. Guard your callbacks with try/except if they
          might fail.
    """

    def __init__(self) -> None:
        self._enter_hooks: list[Callable[[], None]] = []
        self._exit_hooks: list[Callable[[], None]] = []
        self._updates_when_paused: bool = False
        self._renders_when_paused: bool = False

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
            current.on_pause()

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
            new_top.on_resume()

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
