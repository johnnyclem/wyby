"""Key mapping configuration for game input.

Maps raw :class:`~wyby.input.KeyEvent` key names to game-defined action
strings.  This lets games decouple input handling from game logic —
game code checks for actions (``"move_up"``, ``"attack"``) rather than
raw keys (``"w"``, ``"up"``), making rebinding straightforward.

Usage::

    from wyby.keymap import KeyMap
    from wyby.input import KeyEvent

    # Define default bindings: action -> list of key specs.
    km = KeyMap({
        "move_up": ["w", "up"],
        "move_down": ["s", "down"],
        "quit": ["q", "escape"],
        "save": [("s", True)],     # Ctrl+S
    })

    # Resolve a KeyEvent to an action name.
    event = KeyEvent(key="w")
    action = km.lookup(event)       # -> "move_up"

    # Rebind at runtime.
    km.bind("jump", "space")
    km.unbind("move_up", "w")

    # Serialise for save/load (JSON-safe dict).
    data = km.to_dict()
    km2 = KeyMap.from_dict(data)

Caveats:
    - Key names are lowercase strings matching :attr:`KeyEvent.key` values.
      There is no compile-time validation of key name typos — a binding
      for ``"uup"`` will silently never match.  Use :meth:`KeyMap.lookup`
      return values (``None`` for no match) to detect misconfigurations
      at runtime.
    - Ctrl+S and Ctrl+Q may be intercepted by XON/XOFF flow control on
      some terminals before reaching the application.  Binding actions to
      these combos is allowed but may not work on all systems.  See
      :mod:`wyby.input` for details.
    - Ctrl+M produces the same byte as Enter (``\\r`` / 0x0d).  The parser
      cannot distinguish them, so ``KeyEvent(key="enter")`` and
      ``KeyEvent(key="m", ctrl=True)`` are ambiguous at the terminal level.
      Avoid binding distinct actions to both.
    - Shift is not detectable as a modifier.  Uppercase letters arrive as
      their uppercase character (e.g., ``KeyEvent(key="A")``), not as
      ``KeyEvent(key="a", shift=True)``.  Bind uppercase characters
      directly if needed.
    - Alt/Meta is not supported in v0.1.  Alt+key arrives as two separate
      events (Escape then the key character).
    - When multiple actions are bound to the same key, only the first
      matching action (in insertion order) is returned by :meth:`lookup`.
      Use :meth:`lookup_all` to get all matching actions.
    - Action names and key names are case-sensitive.  ``"Quit"`` and
      ``"quit"`` are different actions; ``"A"`` and ``"a"`` are different
      keys.
"""

from __future__ import annotations

import dataclasses
import logging
from typing import Union

from wyby.input import KeyEvent

_logger = logging.getLogger(__name__)

# A key spec is either a plain key name string or a (key, ctrl) tuple.
# The tuple form is used to bind Ctrl+key combos.
KeySpec = Union[str, tuple[str, bool]]


def _parse_key_spec(spec: KeySpec) -> tuple[str, bool]:
    """Normalise a key spec into a ``(key, ctrl)`` pair.

    Accepts either a plain string (``"w"``) or a tuple/list
    (``("s", True)``).  The list form is accepted for JSON round-trip
    compatibility.

    Raises:
        TypeError: If *spec* is not a string or sequence.
        ValueError: If the key name is empty.
    """
    if isinstance(spec, str):
        if not spec:
            raise ValueError("key name must not be empty")
        return spec, False
    if isinstance(spec, (tuple, list)) and len(spec) == 2:
        key, ctrl = str(spec[0]), bool(spec[1])
        if not key:
            raise ValueError("key name must not be empty")
        return key, ctrl
    raise TypeError(
        f"key spec must be a string or (key, ctrl) pair, got {spec!r}"
    )


@dataclasses.dataclass(frozen=True, slots=True)
class KeyBinding:
    """A single key-to-action mapping.

    Attributes:
        key: The key name to match (e.g., ``"w"``, ``"up"``, ``"space"``).
            Must match :attr:`KeyEvent.key` values exactly.
        ctrl: If ``True``, only matches when the Ctrl modifier is held.
        action: The game action this binding triggers.

    Caveats:
        - Ctrl+letter detection is limited to A–Z (byte values 0x01–0x1a).
          Ctrl+digit and Ctrl+punctuation are not reliably detectable
          across terminals.
        - Ctrl+C (0x03) always raises ``KeyboardInterrupt`` and never
          produces a ``KeyEvent``, so binding an action to Ctrl+C has
          no effect.
    """

    key: str
    ctrl: bool
    action: str

    def matches(self, event: KeyEvent) -> bool:
        """Return ``True`` if *event* matches this binding."""
        return event.key == self.key and event.ctrl == self.ctrl

    def to_spec(self) -> KeySpec:
        """Return the key spec representation of this binding.

        Returns a plain string for non-Ctrl bindings, or a
        ``(key, True)`` tuple for Ctrl bindings.
        """
        if self.ctrl:
            return (self.key, True)
        return self.key


class KeyMap:
    """Configurable key-to-action mapping.

    Holds a set of :class:`KeyBinding` entries and resolves
    :class:`~wyby.input.KeyEvent` objects to action name strings.

    Args:
        bindings: A dict mapping action names to lists of key specs.
            Each key spec is either a plain key name string (``"w"``)
            or a ``(key_name, ctrl_flag)`` tuple (``("s", True)`` for
            Ctrl+S).

    Raises:
        TypeError: If *bindings* is not a dict or contains invalid types.
        ValueError: If a key name is empty.

    Caveats:
        - Binding order matters for :meth:`lookup`.  When the same key is
          bound to multiple actions, :meth:`lookup` returns the action
          from the binding that was added first.  Use :meth:`lookup_all`
          for all matches.
        - The mapping is mutable at runtime via :meth:`bind` and
          :meth:`unbind`.  If you need an immutable snapshot (e.g., for
          threading), call :meth:`to_dict` to get a plain dict copy.
        - No validation is performed against the set of known key names
          from the input parser.  Typos in key names silently fail to
          match.  This is intentional — the set of possible key names
          depends on terminal, platform, and InputMode.
    """

    __slots__ = ("_bindings",)

    def __init__(self, bindings: dict[str, list[KeySpec]] | None = None) -> None:
        self._bindings: list[KeyBinding] = []
        if bindings is not None:
            if not isinstance(bindings, dict):
                raise TypeError(
                    f"bindings must be a dict, got {type(bindings).__name__}"
                )
            for action, specs in bindings.items():
                if not isinstance(action, str):
                    raise TypeError(
                        f"action name must be a string, got {type(action).__name__}"
                    )
                if not isinstance(specs, list):
                    raise TypeError(
                        f"key specs for action {action!r} must be a list, "
                        f"got {type(specs).__name__}"
                    )
                for spec in specs:
                    key, ctrl = _parse_key_spec(spec)
                    self._bindings.append(KeyBinding(key=key, ctrl=ctrl, action=action))

    def bind(self, action: str, key: str, ctrl: bool = False) -> None:
        """Add a key binding for an action.

        If the exact same ``(key, ctrl)`` → ``action`` binding already
        exists, this is a no-op.

        Args:
            action: The action name to trigger.
            key: The key name to bind.
            ctrl: Whether the Ctrl modifier is required.

        Raises:
            ValueError: If *key* is empty or *action* is empty.
        """
        if not key:
            raise ValueError("key name must not be empty")
        if not action:
            raise ValueError("action name must not be empty")
        binding = KeyBinding(key=key, ctrl=ctrl, action=action)
        if binding in self._bindings:
            return
        self._bindings.append(binding)
        _logger.debug("Bound %r to action %r (ctrl=%s)", key, action, ctrl)

    def unbind(self, action: str, key: str, ctrl: bool = False) -> bool:
        """Remove a specific key binding for an action.

        Args:
            action: The action name.
            key: The key name to unbind.
            ctrl: Whether the Ctrl modifier was required.

        Returns:
            ``True`` if the binding was found and removed, ``False`` if
            no such binding existed.
        """
        binding = KeyBinding(key=key, ctrl=ctrl, action=action)
        try:
            self._bindings.remove(binding)
            _logger.debug("Unbound %r from action %r (ctrl=%s)", key, action, ctrl)
            return True
        except ValueError:
            return False

    def unbind_action(self, action: str) -> int:
        """Remove all key bindings for an action.

        Args:
            action: The action name whose bindings should be removed.

        Returns:
            The number of bindings removed.
        """
        before = len(self._bindings)
        self._bindings = [b for b in self._bindings if b.action != action]
        removed = before - len(self._bindings)
        if removed:
            _logger.debug("Removed all %d binding(s) for action %r", removed, action)
        return removed

    def unbind_key(self, key: str, ctrl: bool = False) -> int:
        """Remove all bindings for a specific key (regardless of action).

        Args:
            key: The key name to unbind.
            ctrl: Whether to match Ctrl bindings.

        Returns:
            The number of bindings removed.
        """
        before = len(self._bindings)
        self._bindings = [
            b for b in self._bindings
            if not (b.key == key and b.ctrl == ctrl)
        ]
        return before - len(self._bindings)

    def lookup(self, event: KeyEvent) -> str | None:
        """Resolve a :class:`~wyby.input.KeyEvent` to an action name.

        Returns the action name of the first matching binding, or
        ``None`` if no binding matches.

        Args:
            event: The key event to look up.

        Caveats:
            - When multiple actions are bound to the same key, the first
              binding (in insertion order) wins.  Use :meth:`lookup_all`
              to get all matching actions.
        """
        for binding in self._bindings:
            if binding.matches(event):
                return binding.action
        return None

    def lookup_all(self, event: KeyEvent) -> list[str]:
        """Resolve a :class:`~wyby.input.KeyEvent` to all matching actions.

        Returns a list of action names for all bindings that match
        *event*, in insertion order.  Returns an empty list if no
        binding matches.
        """
        return [b.action for b in self._bindings if b.matches(event)]

    def keys_for_action(self, action: str) -> list[KeyBinding]:
        """Return all :class:`KeyBinding` entries for an action.

        Useful for displaying "Press W or Up to move" hints in the UI.
        """
        return [b for b in self._bindings if b.action == action]

    def actions(self) -> list[str]:
        """Return a list of all unique action names, in insertion order."""
        seen: set[str] = set()
        result: list[str] = []
        for b in self._bindings:
            if b.action not in seen:
                seen.add(b.action)
                result.append(b.action)
        return result

    def to_dict(self) -> dict[str, list[KeySpec]]:
        """Serialise the key map to a JSON-safe dict.

        Returns:
            A dict mapping action names to lists of key specs.  Plain
            key bindings are strings; Ctrl bindings are ``[key, true]``
            lists (JSON arrays).

        The output is suitable for ``json.dumps()`` and can be restored
        via :meth:`from_dict`.
        """
        result: dict[str, list[KeySpec]] = {}
        for binding in self._bindings:
            specs = result.setdefault(binding.action, [])
            if binding.ctrl:
                # Use a list (not tuple) for JSON compatibility.
                specs.append([binding.key, True])  # type: ignore[arg-type]
            else:
                specs.append(binding.key)
        return result

    @classmethod
    def from_dict(cls, data: dict[str, list[KeySpec]]) -> KeyMap:
        """Deserialise a key map from a dict (e.g., loaded from JSON).

        Args:
            data: A dict in the same format as :meth:`to_dict` output.
                Key specs may be strings or ``[key, true]`` lists.

        Returns:
            A new :class:`KeyMap` instance.

        Raises:
            TypeError: If *data* is not a dict or contains invalid types.
            ValueError: If a key name is empty.

        Caveats:
            - JSON deserialisation produces lists, not tuples.  Both
              ``("s", True)`` and ``["s", true]`` are accepted as
              Ctrl key specs.
        """
        # Normalise list-form specs from JSON back to tuples.
        normalised: dict[str, list[KeySpec]] = {}
        if not isinstance(data, dict):
            raise TypeError(f"data must be a dict, got {type(data).__name__}")
        for action, specs in data.items():
            if not isinstance(specs, list):
                raise TypeError(
                    f"key specs for action {action!r} must be a list, "
                    f"got {type(specs).__name__}"
                )
            norm_specs: list[KeySpec] = []
            for spec in specs:
                if isinstance(spec, (list, tuple)) and len(spec) == 2:
                    norm_specs.append((str(spec[0]), bool(spec[1])))
                elif isinstance(spec, str):
                    norm_specs.append(spec)
                else:
                    raise TypeError(
                        f"invalid key spec {spec!r} for action {action!r}: "
                        f"expected a string or [key, ctrl] pair"
                    )
            normalised[action] = norm_specs
        return cls(normalised)

    def __len__(self) -> int:
        """Return the total number of key bindings."""
        return len(self._bindings)

    def __contains__(self, action: str) -> bool:
        """Check if any binding exists for an action name."""
        return any(b.action == action for b in self._bindings)

    def __repr__(self) -> str:
        actions = self.actions()
        if len(actions) <= 3:
            return f"KeyMap(actions={actions!r}, bindings={len(self._bindings)})"
        return (
            f"KeyMap(actions={actions[:3]!r}... "
            f"({len(actions)} total), bindings={len(self._bindings)})"
        )
