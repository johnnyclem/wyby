"""Keyboard input abstraction.

This module provides a cross-platform keyboard input layer that reads
from the process's own stdin, parses ANSI escape sequences into
normalised :class:`KeyEvent` objects, and exposes a polling API for the
game loop.

Library choice — stdin via termios/msvcrt (not ``keyboard``):
    wyby deliberately reads only from the process's own stdin using
    platform primitives (``termios`` + ``select`` on Unix,
    ``msvcrt`` on Windows).  The third-party ``keyboard`` library was
    evaluated and **explicitly excluded** for these reasons:

    1. **System-wide hooks.**  ``keyboard`` installs OS-level input
       hooks that capture keystrokes from *all* applications, not just
       the terminal running the game.  This is inappropriate for a
       game framework.
    2. **Root/sudo required on Linux.**  On Linux, ``keyboard`` reads
       raw input events from ``/dev/input/event*`` device files (the
       evdev interface).  These files are owned by ``root:input`` with
       mode ``0660``.  Without elevated privileges, the library raises
       ``PermissionError``.  Users must either run with ``sudo`` or
       add themselves to the ``input`` group — both grant access to
       *all* input devices system-wide, which is a serious security
       escalation for a terminal game.  See ``_platform.py`` for
       full details.
    3. **Security concerns.**  A library that can see every keystroke
       system-wide is a keylogger by design.  Even if used benignly,
       bundling it raises trust issues for end users.
    4. **Poor terminal integration.**  ``keyboard`` bypasses the
       terminal entirely, so it cannot distinguish between terminals
       when multiple are open, and it does not respect terminal
       multiplexers (tmux, screen).

    The chosen approach (``termios`` raw mode + ``select`` on Unix,
    ``msvcrt`` on Windows) reads only from the game's own stdin,
    requires no special privileges, and integrates naturally with
    terminal emulators and multiplexers.

Usage::

    from wyby.input import InputManager, KeyEvent

    manager = InputManager()
    manager.start()
    try:
        events = manager.poll()
        for event in events:
            if event.key == "up":
                player.move_up()
            elif event.key == "q":
                break
    finally:
        manager.stop()

Caveats:
    - Terminal input is inherently platform-dependent.  On Unix, raw
      mode via ``termios`` is used; on Windows, ``msvcrt.kbhit()`` /
      ``msvcrt.getwch()``.  Behaviour differs in key representation
      and timing between platforms.
    - The ``keyboard`` library is **explicitly excluded**.  On Linux it
      requires root/sudo to access ``/dev/input`` device files; on all
      platforms it installs system-wide hooks that capture input from
      every application.  wyby reads only from its own stdin and never
      requires elevated privileges.  See the "Library choice" section
      above and ``_platform.py`` for full rationale.
    - Mouse support is not included in v0.1.  Some terminals support
      mouse reporting via escape sequences, but coverage is
      inconsistent.
    - Terminal cooked-mode must be restored on exit.  The
      :class:`InputManager` handles this via :meth:`stop` and signal
      handlers, but ``SIGKILL`` cannot be caught.
    - Modifier key detection (Shift, Alt, Ctrl) varies by terminal.
      Not all terminals report all modifier combinations.  Only
      Ctrl is reliably detectable (as byte values 0x01–0x1a).
    - Escape key detection has an inherent ambiguity: a lone ``ESC``
      byte (``\\x1b``) could be a standalone Escape press or the start
      of an ANSI escape sequence.  The parser treats a lone ``\\x1b``
      not followed by ``[`` as an Escape key press.
"""

from __future__ import annotations

import dataclasses
import logging
from typing import TYPE_CHECKING

from wyby.event import Event

if TYPE_CHECKING:
    from wyby._platform import InputBackend

_logger = logging.getLogger(__name__)

# ANSI escape sequence lookup table.
# Maps the final byte of CSI sequences (after \x1b[) to key names.
# Only the most common and reliably-supported sequences are included.
# Terminal emulators vary in which sequences they emit — this covers
# the intersection that works across xterm, VT100 descendants, and
# most modern terminals (iTerm2, Windows Terminal, GNOME Terminal,
# Alacritty, etc.).
_CSI_SEQUENCES: dict[str, str] = {
    "A": "up",
    "B": "down",
    "C": "right",
    "D": "left",
    "H": "home",
    "F": "end",
}

# Extended CSI sequences using numeric parameters (\x1b[N~).
# These are less universally supported than the basic arrow keys.
_CSI_TILDE_SEQUENCES: dict[str, str] = {
    "1": "home",
    "2": "insert",
    "3": "delete",
    "4": "end",
    "5": "pageup",
    "6": "pagedown",
}

# Ctrl+letter key mapping.  In raw mode, Ctrl+A through Ctrl+Z produce
# byte values 0x01 through 0x1a.  Some of these have special meanings:
#   0x03 = Ctrl+C (we raise KeyboardInterrupt)
#   0x09 = Tab (Ctrl+I)
#   0x0a = Enter/newline (Ctrl+J) — on some terminals
#   0x0d = Enter/carriage-return (Ctrl+M) — on most terminals
#   0x1b = Escape (Ctrl+[) — handled separately as escape sequence prefix
# Caveat: Ctrl+S (0x13) and Ctrl+Q (0x11) are used for XON/XOFF flow
# control on some terminals and may not be delivered to the application.
_CTRL_C = 0x03


@dataclasses.dataclass(frozen=True, slots=True)
class KeyEvent(Event):
    """A keyboard input event.

    Represents a single key press parsed from raw stdin bytes.
    Subclasses :class:`~wyby.event.Event` so it can be posted to
    the engine's :class:`~wyby.event.EventQueue`.

    Attributes:
        key: Normalised key name.  Single printable characters are
            represented as themselves (``"a"``, ``"z"``, ``"1"``,
            ``"/"``).  Special keys use descriptive names: ``"up"``,
            ``"down"``, ``"left"``, ``"right"``, ``"enter"``,
            ``"escape"``, ``"tab"``, ``"backspace"``, ``"space"``,
            ``"home"``, ``"end"``, ``"insert"``, ``"delete"``,
            ``"pageup"``, ``"pagedown"``.
        ctrl: ``True`` if the Ctrl modifier was held.  Only reliably
            detectable for letter keys (Ctrl+A through Ctrl+Z).

    Caveats:
        - Key names are lowercase strings, not an enum.  This keeps
          the API simple and extensible, but means typos in key
          comparisons (e.g., ``event.key == "Up"`` instead of
          ``"up"``) will silently fail to match.
        - Shift detection is not supported.  Uppercase letters are
          reported as their uppercase character (``"A"``), but the
          ``ctrl`` flag is always ``False`` for shifted keys.
        - Alt/Meta modifier is not detected in v0.1.  Alt+key
          sequences (``ESC`` followed by a character) are parsed as
          two separate events (Escape then the character).
        - Not all key combinations produce distinct byte sequences.
          For example, Ctrl+M and Enter both produce ``\\r`` (0x0d)
          on most terminals.  The parser cannot distinguish them.
    """

    key: str
    ctrl: bool = False

    def __repr__(self) -> str:
        if self.ctrl:
            return f"KeyEvent(key={self.key!r}, ctrl=True)"
        return f"KeyEvent(key={self.key!r})"


def parse_key_events(data: bytes) -> list[KeyEvent]:
    """Parse raw stdin bytes into a list of :class:`KeyEvent` objects.

    This is the core ANSI escape sequence parser.  It consumes raw
    bytes read from stdin in raw mode and produces normalised key
    events.

    Args:
        data: Raw bytes from stdin.  May contain a mix of single-byte
            characters, multi-byte UTF-8 sequences, and ANSI escape
            sequences.

    Returns:
        A list of :class:`KeyEvent` objects, one per detected key
        press.  May be empty if *data* is empty.

    Caveats:
        - The parser is stateless — it processes each *data* buffer
          independently.  If an ANSI escape sequence is split across
          two ``read_bytes()`` calls (rare but possible under heavy
          load), the second half will be parsed as garbage characters.
          In practice, escape sequences are short (3–6 bytes) and
          arrive atomically on all tested terminals.
        - Unrecognised escape sequences are silently dropped.  This
          is intentional — terminals emit many sequences that are
          irrelevant for game input (e.g., focus events, bracketed
          paste markers).
        - Ctrl+C (byte 0x03) raises ``KeyboardInterrupt`` rather than
          producing a ``KeyEvent``.  This preserves the standard
          terminal behaviour of Ctrl+C as an interrupt signal.
    """
    events: list[KeyEvent] = []
    i = 0
    n = len(data)

    while i < n:
        byte = data[i]

        # --- Ctrl+C: raise KeyboardInterrupt ---
        if byte == _CTRL_C:
            raise KeyboardInterrupt

        # --- ESC (0x1b): escape sequence or standalone Escape ---
        if byte == 0x1B:
            if i + 1 < n and data[i + 1] == ord("["):
                # CSI sequence: \x1b[ followed by parameter bytes and
                # a final byte.
                event, consumed = _parse_csi(data, i + 2)
                if event is not None:
                    events.append(event)
                i = i + 2 + consumed
            else:
                # Standalone Escape key (no [ follows).
                events.append(KeyEvent(key="escape"))
                i += 1
            continue

        # --- Ctrl+letter (0x01–0x1a, excluding special keys) ---
        # 0x08 = BS (backspace on some terminals), 0x09 = Tab,
        # 0x0a = LF (Enter), 0x0d = CR (Enter), 0x1b = ESC
        if 0x01 <= byte <= 0x1A and byte not in (0x08, 0x09, 0x0A, 0x0D, 0x1B):
            letter = chr(byte + 0x60)  # 0x01 -> 'a', 0x02 -> 'b', etc.
            events.append(KeyEvent(key=letter, ctrl=True))
            i += 1
            continue

        # --- Special single-byte keys ---
        if byte == 0x0D:  # Carriage return
            events.append(KeyEvent(key="enter"))
            i += 1
            continue
        if byte == 0x0A:  # Newline (some terminals send this for Enter)
            events.append(KeyEvent(key="enter"))
            i += 1
            continue
        if byte == 0x09:  # Tab
            events.append(KeyEvent(key="tab"))
            i += 1
            continue
        if byte == 0x7F:  # Delete/Backspace (most terminals)
            events.append(KeyEvent(key="backspace"))
            i += 1
            continue
        if byte == 0x08:  # Backspace (some terminals)
            events.append(KeyEvent(key="backspace"))
            i += 1
            continue

        # --- Printable ASCII (0x20–0x7e) ---
        if 0x20 <= byte <= 0x7E:
            ch = chr(byte)
            if ch == " ":
                events.append(KeyEvent(key="space"))
            else:
                events.append(KeyEvent(key=ch))
            i += 1
            continue

        # --- Multi-byte UTF-8 ---
        # Determine the number of bytes from the leading byte.
        if byte & 0xE0 == 0xC0:
            char_len = 2
        elif byte & 0xF0 == 0xE0:
            char_len = 3
        elif byte & 0xF8 == 0xF0:
            char_len = 4
        else:
            # Invalid or continuation byte — skip.
            i += 1
            continue

        if i + char_len <= n:
            try:
                ch = data[i : i + char_len].decode("utf-8")
                events.append(KeyEvent(key=ch))
            except UnicodeDecodeError:
                pass  # Skip malformed sequences
            i += char_len
        else:
            # Incomplete multi-byte sequence at end of buffer — skip.
            i += 1

    return events


def _parse_csi(data: bytes, start: int) -> tuple[KeyEvent | None, int]:
    """Parse a CSI escape sequence starting after ``\\x1b[``.

    Args:
        data: Full input buffer.
        start: Index of the first byte after ``[``.

    Returns:
        A tuple of (KeyEvent or None, bytes consumed after ``[``).
        Returns ``(None, consumed)`` for unrecognised sequences.
    """
    n = len(data)
    if start >= n:
        # Incomplete sequence — just an \x1b[ at end of buffer.
        return None, 0

    # Collect parameter bytes (digits and semicolons).
    param_start = start
    i = start
    while i < n and (data[i] in range(0x30, 0x3A) or data[i] == ord(";")):
        i += 1

    if i >= n:
        # Incomplete — parameters but no final byte.
        return None, i - start

    final = chr(data[i])
    params = data[param_start:i].decode("ascii", errors="replace")
    consumed = i - start + 1  # +1 for the final byte

    # --- Tilde sequences: \x1b[N~ ---
    if final == "~" and params in _CSI_TILDE_SEQUENCES:
        key_name = _CSI_TILDE_SEQUENCES[params]
        return KeyEvent(key=key_name), consumed

    # --- Direct final-byte sequences: \x1b[A, \x1b[B, etc. ---
    if final in _CSI_SEQUENCES:
        key_name = _CSI_SEQUENCES[final]
        return KeyEvent(key=key_name), consumed

    # Unrecognised sequence — drop it silently.
    _logger.debug(
        "Unrecognised CSI sequence: ESC[%s%s", params, final
    )
    return None, consumed


class InputManager:
    """High-level keyboard input manager for the game loop.

    Wraps a platform-specific :class:`~wyby._platform.InputBackend`
    and provides a simple :meth:`poll` interface that returns parsed
    :class:`KeyEvent` objects.

    The typical lifecycle is::

        manager = InputManager()
        manager.start()   # enters raw mode
        try:
            while running:
                events = manager.poll()
                for event in events:
                    handle(event)
        finally:
            manager.stop()  # restores cooked mode

    Or as a context manager::

        with InputManager() as manager:
            events = manager.poll()

    Args:
        backend: An :class:`~wyby._platform.InputBackend` instance.
            If ``None``, one is created automatically for the current
            platform via :func:`~wyby._platform.create_backend`.

    Caveats:
        - You **must** call :meth:`stop` (or use the context manager)
          to restore terminal settings.  If the process exits without
          restoring cooked mode, the terminal will be left in a broken
          state (no echo, no line editing).  Run ``reset`` or
          ``stty sane`` in the terminal to recover.
        - :meth:`poll` may raise ``KeyboardInterrupt`` if Ctrl+C is
          pressed.  This is by design — Ctrl+C should still work as
          an interrupt signal.  Catch it in your game loop if you want
          to handle it gracefully (e.g., show a "really quit?" dialog).
        - The manager is not thread-safe.  Call :meth:`poll` only from
          the main loop thread.
    """

    __slots__ = ("_backend", "_started")

    def __init__(self, backend: InputBackend | None = None) -> None:
        if backend is None:
            from wyby._platform import create_backend

            backend = create_backend()
        self._backend = backend
        self._started = False

    @property
    def is_started(self) -> bool:
        """Whether the manager is active (raw mode entered)."""
        return self._started

    def start(self) -> None:
        """Enter raw mode and begin accepting input.

        Raises:
            RuntimeError: If stdin is not a TTY.
        """
        if self._started:
            return
        self._backend.enter_raw_mode()
        self._started = True
        _logger.debug("InputManager started")

    def stop(self) -> None:
        """Exit raw mode and restore terminal settings.

        Safe to call multiple times; subsequent calls are no-ops.
        """
        if not self._started:
            return
        self._backend.exit_raw_mode()
        self._started = False
        _logger.debug("InputManager stopped")

    def has_input(self) -> bool:
        """Check whether key press data is available (non-blocking peek).

        Returns ``True`` if at least one byte is waiting in the stdin
        buffer, ``False`` otherwise.  No input is consumed — a
        subsequent :meth:`poll` call will still return the pending
        events.

        This is useful in game loops that want to skip input processing
        when nothing has been pressed, or that need to check for input
        availability without committing to a full parse::

            with InputManager() as manager:
                while running:
                    if manager.has_input():
                        events = manager.poll()
                        handle_input(events)
                    update_game_state()
                    render()

        Raises:
            RuntimeError: If the manager has not been started.

        Caveats:
            - This is a byte-level check, not a key-event-level check.
              A ``True`` return means raw bytes are available, but those
              bytes may form an incomplete ANSI escape sequence (e.g.,
              just the ``ESC`` byte before the ``[`` arrives).  In
              practice, escape sequences arrive atomically, so this is
              rarely an issue.
            - On Unix, uses ``select.select`` with a zero timeout.  On
              Windows, uses ``msvcrt.kbhit()``.  Both return
              immediately without blocking.
            - Terminal key-repeat is OS-controlled.  Holding a key
              generates repeated bytes at the OS repeat rate, which
              this method will detect.
            - This method cannot distinguish between "a key was pressed"
              and "stdin has data" (e.g., pasted text).  Pasted text
              will also cause ``True`` to be returned.
        """
        if not self._started:
            raise RuntimeError(
                "InputManager.has_input() called before start().  "
                "Call start() first or use the context manager."
            )
        return self._backend.has_input()

    def poll(self) -> list[KeyEvent]:
        """Read and parse all available key presses (non-blocking).

        Returns a list of :class:`KeyEvent` objects for all keys
        pressed since the last call to :meth:`poll`.  Returns an empty
        list if no keys are available.

        Raises:
            KeyboardInterrupt: If Ctrl+C was pressed.
            RuntimeError: If the manager has not been started.

        Caveats:
            - Non-blocking: returns immediately even if no input is
              available.  Call this once per game tick.
            - If the input buffer contains a partial ANSI escape
              sequence (split across reads), the partial sequence
              will produce unexpected events.  In practice this is
              extremely rare — escape sequences are short and arrive
              atomically.
        """
        if not self._started:
            raise RuntimeError(
                "InputManager.poll() called before start().  "
                "Call start() first or use the context manager."
            )
        raw = self._backend.read_bytes()
        if not raw:
            return []
        return parse_key_events(raw)

    def __enter__(self) -> InputManager:
        self.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.stop()

    def __repr__(self) -> str:
        return f"InputManager(started={self._started})"
