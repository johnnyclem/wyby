"""Input context management for focus-based input routing.

An :class:`InputContext` pairs a :class:`~wyby.keymap.KeyMap` with a name
and an enabled/disabled flag.  An :class:`InputContextStack` manages a
stack of contexts so that only the topmost enabled context resolves
input events — giving you focus-like behaviour within a single scene.

The scene stack already handles coarse-grained focus: only the top scene
receives input each tick.  Input contexts handle *fine-grained* focus
**within** a scene — for example, a gameplay scene might push a dialog
context on top of its default movement context, temporarily remapping
keys while the dialog is open.

Usage::

    from wyby.input_context import InputContext, InputContextStack
    from wyby.keymap import KeyMap
    from wyby.input import KeyEvent

    # Define contexts with their own key maps.
    gameplay = InputContext("gameplay", KeyMap({
        "move_up": ["w", "up"],
        "move_down": ["s", "down"],
        "open_menu": ["escape"],
    }))

    dialog = InputContext("dialog", KeyMap({
        "confirm": ["enter"],
        "cancel": ["escape"],
    }))

    # Stack manages focus.  Top context wins.
    stack = InputContextStack()
    stack.push(gameplay)

    event = KeyEvent(key="w")
    action = stack.lookup(event)      # -> "move_up"

    # Dialog opens — push its context.  "w" no longer maps.
    stack.push(dialog)
    action = stack.lookup(event)      # -> None
    action = stack.lookup(KeyEvent(key="escape"))  # -> "cancel"

    # Dialog closes — pop to restore gameplay context.
    stack.pop()
    action = stack.lookup(event)      # -> "move_up" again

Caveats:
    - Input contexts operate within a single scene.  Cross-scene focus
      is handled by the :class:`~wyby.scene.SceneStack` — only the top
      scene receives input.  If you need per-scene input contexts, each
      scene should own its own :class:`InputContextStack`.
    - The stack is not thread-safe.  Like all wyby input types, it
      should only be used from the main loop thread.
    - Disabled contexts on the stack are skipped during lookup, but they
      still occupy a stack slot.  This lets you temporarily disable a
      context (e.g., during an animation) without losing its position.
    - Context names are informational only — they are not unique keys.
      Two contexts can share a name.  Names are used for logging and
      debugging, not for lookup.
    - The ``fallthrough`` flag on :class:`InputContext` controls whether
      unmatched events continue to lower contexts.  By default,
      ``fallthrough=False``, meaning the top context captures all input.
      Set ``fallthrough=True`` to allow unmatched events to be resolved
      by contexts below (e.g., a HUD overlay that only binds a few keys
      while letting movement keys pass through to the gameplay context).
"""

from __future__ import annotations

import logging

from wyby.input import KeyEvent
from wyby.keymap import KeyMap

_logger = logging.getLogger(__name__)

# Stack depth limits — same rationale as SceneStack.
_DEFAULT_MAX_DEPTH = 32
_MIN_MAX_DEPTH = 1
_MAX_MAX_DEPTH = 256


class InputContext:
    """A named input context holding a :class:`~wyby.keymap.KeyMap`.

    Each context represents a set of key bindings that should be active
    when this context has focus.  Contexts are placed on an
    :class:`InputContextStack`; the topmost enabled context resolves
    events.

    Args:
        name: A human-readable label for debugging/logging (e.g.,
            ``"gameplay"``, ``"dialog"``, ``"inventory"``).
        keymap: The :class:`~wyby.keymap.KeyMap` that defines which
            keys map to which actions in this context.  If ``None``,
            an empty :class:`KeyMap` is created.
        enabled: Whether this context is active.  Disabled contexts
            are skipped during event lookup but remain on the stack.
            Defaults to ``True``.
        fallthrough: If ``True``, events that don't match any binding
            in this context are passed to the context below on the
            stack.  If ``False`` (default), unmatched events stop here
            and return ``None``.

    Raises:
        TypeError: If *name* is not a string, *keymap* is not a
            :class:`KeyMap`, or *enabled*/*fallthrough* are not bools.
        ValueError: If *name* is empty.

    Caveats:
        - Context names are not validated for uniqueness.  Multiple
          contexts can share the same name.  Use distinct names for
          easier debugging.
        - An empty keymap is valid — it matches no events.  Combined
          with ``fallthrough=False``, this effectively swallows all
          input (useful as an "input disabled" context during
          cutscenes or animations).
        - Toggling ``enabled`` at runtime is safe and takes effect
          immediately on the next :meth:`InputContextStack.lookup`
          call.
    """

    __slots__ = ("_name", "_keymap", "_enabled", "_fallthrough")

    def __init__(
        self,
        name: str,
        keymap: KeyMap | None = None,
        *,
        enabled: bool = True,
        fallthrough: bool = False,
    ) -> None:
        if not isinstance(name, str):
            raise TypeError(
                f"name must be a string, got {type(name).__name__}"
            )
        if not name:
            raise ValueError("name must not be empty")
        if keymap is not None and not isinstance(keymap, KeyMap):
            raise TypeError(
                f"keymap must be a KeyMap instance or None, "
                f"got {type(keymap).__name__}"
            )
        self._name = name
        self._keymap = keymap if keymap is not None else KeyMap()
        self._enabled = bool(enabled)
        self._fallthrough = bool(fallthrough)

    @property
    def name(self) -> str:
        """The human-readable context name."""
        return self._name

    @property
    def keymap(self) -> KeyMap:
        """The key map for this context."""
        return self._keymap

    @property
    def enabled(self) -> bool:
        """Whether this context participates in event lookup."""
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = bool(value)

    @property
    def fallthrough(self) -> bool:
        """Whether unmatched events pass to the context below."""
        return self._fallthrough

    @fallthrough.setter
    def fallthrough(self, value: bool) -> None:
        self._fallthrough = bool(value)

    def lookup(self, event: KeyEvent) -> str | None:
        """Resolve a key event to an action in this context's keymap.

        Returns the action name or ``None`` if no binding matches.
        """
        return self._keymap.lookup(event)

    def __repr__(self) -> str:
        parts = [f"name={self._name!r}"]
        if not self._enabled:
            parts.append("enabled=False")
        if self._fallthrough:
            parts.append("fallthrough=True")
        parts.append(f"bindings={len(self._keymap)}")
        return f"InputContext({', '.join(parts)})"


class InputContextStack:
    """A stack of :class:`InputContext` instances for focus management.

    Mirrors the :class:`~wyby.scene.SceneStack` pattern: the topmost
    enabled context "has focus" and resolves input events.  Push a
    context when a UI element gains focus; pop it when focus is lost.

    Args:
        max_depth: Maximum number of contexts allowed on the stack.
            Must be between 1 and 256.  Defaults to 32.

    Raises:
        TypeError: If *max_depth* is not an integer.
        ValueError: If *max_depth* is outside the allowed range.

    Caveats:
        - Not thread-safe.  Use only from the main loop thread.
        - The stack does not own context lifetimes.  Popped contexts
          remain alive if the caller holds a reference.
        - When ``fallthrough=True`` on a context, :meth:`lookup`
          walks down the stack until it finds a match or reaches a
          non-fallthrough context.  This walk is O(n) in stack depth
          in the worst case, but stack depth is bounded by
          ``max_depth`` (default 32) and typically very small.
        - Pushing the same context instance twice is allowed but
          discouraged — it may cause confusing behaviour if the
          context's keymap is mutated.
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
        self._stack: list[InputContext] = []
        self._max_depth = max_depth
        _logger.debug(
            "InputContextStack created with max_depth=%d", max_depth
        )

    @property
    def max_depth(self) -> int:
        """Maximum number of contexts allowed on the stack."""
        return self._max_depth

    def __len__(self) -> int:
        """Return the number of contexts on the stack."""
        return len(self._stack)

    def __bool__(self) -> bool:
        """Return ``True`` if the stack is non-empty."""
        return len(self._stack) > 0

    @property
    def is_empty(self) -> bool:
        """Whether the stack has no contexts."""
        return len(self._stack) == 0

    def peek(self) -> InputContext | None:
        """Return the top context without removing it, or ``None``."""
        if self._stack:
            return self._stack[-1]
        return None

    def push(self, context: InputContext) -> None:
        """Push a context onto the top of the stack.

        Args:
            context: The input context to push.

        Raises:
            TypeError: If *context* is not an :class:`InputContext`.
            RuntimeError: If the stack has reached ``max_depth``.
        """
        if not isinstance(context, InputContext):
            raise TypeError(
                f"context must be an InputContext instance, "
                f"got {type(context).__name__}"
            )
        if len(self._stack) >= self._max_depth:
            raise RuntimeError(
                f"InputContext stack depth limit reached "
                f"({self._max_depth}). This likely indicates a "
                f"runaway push loop. Increase max_depth if you "
                f"legitimately need more contexts."
            )
        self._stack.append(context)
        _logger.debug(
            "Pushed input context %r (depth now %d)",
            context.name,
            len(self._stack),
        )

    def pop(self) -> InputContext:
        """Remove and return the top context.

        Returns:
            The context that was removed.

        Raises:
            RuntimeError: If the stack is empty.
        """
        if not self._stack:
            raise RuntimeError(
                "Cannot pop from an empty InputContext stack"
            )
        context = self._stack.pop()
        _logger.debug(
            "Popped input context %r (depth now %d)",
            context.name,
            len(self._stack),
        )
        return context

    def replace(self, context: InputContext) -> InputContext:
        """Replace the top context with a new one.

        Args:
            context: The new context to place on top.

        Returns:
            The context that was replaced.

        Raises:
            TypeError: If *context* is not an :class:`InputContext`.
            RuntimeError: If the stack is empty.
        """
        if not isinstance(context, InputContext):
            raise TypeError(
                f"context must be an InputContext instance, "
                f"got {type(context).__name__}"
            )
        if not self._stack:
            raise RuntimeError(
                "Cannot replace on an empty InputContext stack"
            )
        old = self._stack.pop()
        self._stack.append(context)
        _logger.debug(
            "Replaced input context %r with %r (depth %d)",
            old.name,
            context.name,
            len(self._stack),
        )
        return old

    def clear(self) -> None:
        """Remove all contexts from the stack."""
        count = len(self._stack)
        self._stack.clear()
        if count:
            _logger.debug(
                "Cleared InputContext stack (%d contexts removed)", count
            )

    def lookup(self, event: KeyEvent) -> str | None:
        """Resolve a key event using the focused (top) context.

        Walks the stack from top to bottom.  For each context:

        1. If the context is disabled, skip it.
        2. If the context's keymap matches the event, return the action.
        3. If the context has ``fallthrough=True`` and no match was
           found, continue to the next context below.
        4. If ``fallthrough=False``, stop and return ``None``.

        Returns:
            The action name from the first matching context, or
            ``None`` if no context matches.

        Caveats:
            - Disabled contexts are invisible to lookup but still
              occupy stack slots.  A stack of all-disabled contexts
              returns ``None`` for any event.
            - Fallthrough traversal is O(n) in stack depth.  For
              typical depths (2–5 contexts), this is negligible.
            - If the stack is empty, returns ``None``.
        """
        for i in range(len(self._stack) - 1, -1, -1):
            ctx = self._stack[i]
            if not ctx.enabled:
                continue
            action = ctx.lookup(event)
            if action is not None:
                return action
            if not ctx.fallthrough:
                return None
        return None

    def lookup_all(self, event: KeyEvent) -> list[str]:
        """Resolve a key event to all matching actions across contexts.

        Like :meth:`lookup`, walks the stack top-to-bottom respecting
        ``enabled`` and ``fallthrough`` flags, but collects all
        matching actions instead of stopping at the first.

        Returns:
            A list of action names from all matching contexts, in
            top-to-bottom order.  Empty if no context matches.
        """
        actions: list[str] = []
        for i in range(len(self._stack) - 1, -1, -1):
            ctx = self._stack[i]
            if not ctx.enabled:
                continue
            found = ctx.keymap.lookup_all(event)
            actions.extend(found)
            if not ctx.fallthrough:
                break
        return actions

    def active_context(self) -> InputContext | None:
        """Return the topmost enabled context, or ``None``.

        This is the context that currently "has focus" — the one
        whose keymap will be checked first by :meth:`lookup`.
        """
        for i in range(len(self._stack) - 1, -1, -1):
            if self._stack[i].enabled:
                return self._stack[i]
        return None

    def __repr__(self) -> str:
        names = [ctx.name for ctx in self._stack]
        return (
            f"InputContextStack({names!r}, "
            f"max_depth={self._max_depth})"
        )
