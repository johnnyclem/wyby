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
    - Mouse support uses SGR extended mode (mode 1006) for reporting.
      Not all terminals support mouse reporting — coverage varies.
      See :class:`MouseEvent` for terminal compatibility caveats.
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
import sys
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


@dataclasses.dataclass(frozen=True, slots=True)
class MouseEvent(Event):
    """A mouse input event.

    Represents a mouse action (press, release, scroll, move) parsed from
    SGR extended mouse escape sequences (xterm mode 1006).

    Attributes:
        x: Column position (0-based, left edge is 0).
        y: Row position (0-based, top edge is 0).
        button: Which button was involved.  One of ``"left"``,
            ``"middle"``, ``"right"``, ``"scroll_up"``,
            ``"scroll_down"``, or ``"none"`` (for motion-only events).
        action: What happened.  One of ``"press"``, ``"release"``,
            ``"scroll"``, or ``"move"``.

    Caveats:
        - **Terminal support varies widely.**  SGR mouse mode (mode 1006)
          is supported by xterm, iTerm2, Windows Terminal, GNOME Terminal,
          Alacritty, kitty, and most modern terminals.  Older terminals
          (e.g., rxvt, older PuTTY versions, the Linux virtual console)
          may not support it at all or may only support the legacy X10
          protocol (which cannot report coordinates above 223).
        - **macOS Terminal.app** has limited mouse support.  It reports
          basic clicks but may not report releases or scrolls reliably.
        - **tmux/screen** may intercept mouse events unless mouse mode
          is explicitly enabled in the multiplexer config (``set -g
          mouse on`` in tmux).
        - **SSH sessions** pass mouse events through if the local
          terminal supports them and the remote terminal is in mouse
          mode, but latency may cause split escape sequences.
        - **Coordinates are 0-based** in this API, converted from the
          1-based values in the SGR protocol.  The top-left cell is
          ``(0, 0)``.
        - **Motion tracking** (mode 1003) is not enabled by default
          because it generates a high volume of events that can flood
          the event queue and degrade performance.  Use
          ``InputManager(mouse=True, mouse_motion=True)`` to opt in.
        - **Drag events** are reported as ``action="move"`` with a
          non-``"none"`` button.
        - **Middle-click paste** may not work while mouse mode is
          enabled, since the terminal captures the click instead of
          pasting.  Some terminals offer Shift+middle-click as a
          workaround.
    """

    x: int
    y: int
    button: str
    action: str

    def __repr__(self) -> str:
        return (
            f"MouseEvent(x={self.x}, y={self.y}, "
            f"button={self.button!r}, action={self.action!r})"
        )


# SGR mouse button decoding.
# The low 2 bits encode the button (with modifiers in higher bits).
# Bit 5 (value 32) indicates motion.
# Bits 6-7 (value 64) indicate scroll.
_MOUSE_BUTTON_MAP: dict[int, str] = {
    0: "left",
    1: "middle",
    2: "right",
}


def _parse_sgr_mouse(params: str, final: str) -> MouseEvent | None:
    """Parse an SGR mouse sequence ``ESC[<button;x;y{M|m}``.

    Args:
        params: The parameter string after ``<`` (e.g., ``"0;15;3"``).
        final: The final character — ``"M"`` for press, ``"m"`` for release.

    Returns:
        A :class:`MouseEvent` or ``None`` if the sequence is malformed.
    """
    parts = params.split(";")
    if len(parts) != 3:
        return None
    try:
        button_code = int(parts[0])
        # SGR coordinates are 1-based; convert to 0-based.
        x = int(parts[1]) - 1
        y = int(parts[2]) - 1
    except (ValueError, IndexError):
        return None

    is_release = final == "m"
    is_motion = bool(button_code & 32)
    is_scroll = bool(button_code & 64)
    base_button = button_code & 3

    if is_scroll:
        button = "scroll_up" if base_button == 0 else "scroll_down"
        return MouseEvent(x=x, y=y, button=button, action="scroll")

    if is_motion:
        button = _MOUSE_BUTTON_MAP.get(base_button, "none")
        return MouseEvent(x=x, y=y, button=button, action="move")

    button = _MOUSE_BUTTON_MAP.get(base_button, "none")
    action = "release" if is_release else "press"
    return MouseEvent(x=x, y=y, button=button, action=action)


def parse_input_events(data: bytes) -> list[Event]:
    """Parse raw stdin bytes into a list of input events.

    This is the core ANSI escape sequence parser.  It consumes raw
    bytes read from stdin in raw mode and produces normalised
    :class:`KeyEvent` and :class:`MouseEvent` objects.

    Args:
        data: Raw bytes from stdin.  May contain a mix of single-byte
            characters, multi-byte UTF-8 sequences, ANSI escape
            sequences, and SGR mouse sequences.

    Returns:
        A list of :class:`Event` objects (either :class:`KeyEvent` or
        :class:`MouseEvent`), one per detected input.  May be empty
        if *data* is empty.

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
        - Mouse events are only produced when the terminal is in SGR
          mouse mode (mode 1006).  Enable mouse mode via
          ``InputManager(mouse=True)``.
    """
    events: list[Event] = []
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


def parse_key_events(data: bytes) -> list[KeyEvent]:
    """Parse raw stdin bytes into a list of :class:`KeyEvent` objects.

    This is a convenience wrapper around :func:`parse_input_events`
    that filters out non-keyboard events.  Retained for backward
    compatibility — new code should use :func:`parse_input_events`
    if mouse events are needed.

    Args:
        data: Raw bytes from stdin.

    Returns:
        A list of :class:`KeyEvent` objects only (mouse events are
        discarded).
    """
    return [e for e in parse_input_events(data) if isinstance(e, KeyEvent)]


def _parse_csi(data: bytes, start: int) -> tuple[Event | None, int]:
    """Parse a CSI escape sequence starting after ``\\x1b[``.

    Args:
        data: Full input buffer.
        start: Index of the first byte after ``[``.

    Returns:
        A tuple of (Event or None, bytes consumed after ``[``).
        Returns ``(None, consumed)`` for unrecognised sequences.
    """
    n = len(data)
    if start >= n:
        # Incomplete sequence — just an \x1b[ at end of buffer.
        return None, 0

    # --- SGR mouse: \x1b[< button;x;y M/m ---
    # The '<' character introduces SGR extended mouse sequences.
    if data[start] == ord("<"):
        # Collect everything after '<' until 'M' or 'm'.
        i = start + 1
        while i < n and chr(data[i]) not in ("M", "m"):
            i += 1
        if i >= n:
            # Incomplete mouse sequence.
            return None, i - start
        final = chr(data[i])
        params = data[start + 1 : i].decode("ascii", errors="replace")
        consumed = i - start + 1
        mouse_event = _parse_sgr_mouse(params, final)
        return mouse_event, consumed

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


# --- Mouse mode enable/disable ---
# These write ANSI escape sequences directly to stdout to control
# mouse reporting.  They must be called while the terminal is in raw
# mode (after enter_raw_mode).
#
# Mode 1000: Basic mouse tracking (press/release).
# Mode 1003: All-motion tracking (reports movement even without buttons).
# Mode 1006: SGR extended coordinates (supports terminals wider than
#            223 columns; uses decimal coordinates instead of byte encoding).
#
# Caveats:
#   - These sequences are written to stdout, not stdin.  If stdout is
#     redirected (e.g., piped to a file), they have no effect.
#   - Not all terminals support all modes.  Mode 1006 (SGR) is the most
#     widely supported modern protocol; mode 1003 (any-event) may not
#     be supported by older terminals.
#   - The sequences must be disabled on exit, otherwise the terminal
#     will continue sending mouse escape sequences after the program
#     ends, corrupting the user's shell.  The InputManager handles
#     this in stop(), but SIGKILL cannot be caught.
#   - The order matters: enable SGR mode (1006) *after* basic mode
#     (1000) to ensure the terminal uses SGR encoding; disable in
#     reverse order.

# ANSI escape sequences for mouse mode control.
_MOUSE_ENABLE_BASIC = "\x1b[?1000h"
_MOUSE_DISABLE_BASIC = "\x1b[?1000l"
_MOUSE_ENABLE_SGR = "\x1b[?1006h"
_MOUSE_DISABLE_SGR = "\x1b[?1006l"
_MOUSE_ENABLE_ALL_MOTION = "\x1b[?1003h"
_MOUSE_DISABLE_ALL_MOTION = "\x1b[?1003l"


def _enable_mouse_mode(motion: bool = False) -> None:
    """Enable SGR mouse reporting on stdout."""
    sys.stdout.write(_MOUSE_ENABLE_BASIC)
    if motion:
        sys.stdout.write(_MOUSE_ENABLE_ALL_MOTION)
    sys.stdout.write(_MOUSE_ENABLE_SGR)
    sys.stdout.flush()
    _logger.debug("Mouse mode enabled (motion=%s)", motion)


def _disable_mouse_mode(motion: bool = False) -> None:
    """Disable SGR mouse reporting on stdout."""
    sys.stdout.write(_MOUSE_DISABLE_SGR)
    if motion:
        sys.stdout.write(_MOUSE_DISABLE_ALL_MOTION)
    sys.stdout.write(_MOUSE_DISABLE_BASIC)
    sys.stdout.flush()
    _logger.debug("Mouse mode disabled")


class InputManager:
    """High-level input manager for the game loop.

    Wraps a platform-specific :class:`~wyby._platform.InputBackend`
    and provides a simple :meth:`poll` interface that returns parsed
    :class:`KeyEvent` and :class:`MouseEvent` objects.

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

    For mouse support::

        with InputManager(mouse=True) as manager:
            events = manager.poll()
            for event in events:
                if isinstance(event, MouseEvent):
                    handle_click(event.x, event.y, event.button)

    For non-TTY environments (piped input, CI, containers), set
    ``allow_fallback=True`` to fall back to ``input()`` when raw
    mode is unavailable::

        with InputManager(allow_fallback=True) as manager:
            # poll() returns [] in fallback mode — use read_line()
            events = manager.read_line("Your move: ")

    Args:
        backend: An :class:`~wyby._platform.InputBackend` instance.
            If ``None``, one is created automatically for the current
            platform via :func:`~wyby._platform.create_backend`.
        allow_fallback: If ``True``, fall back to Python's ``input()``
            when raw mode is unavailable (stdin is not a TTY).  If
            ``False`` (default), a ``RuntimeError`` is raised instead.
        mouse: If ``True``, enable mouse event reporting using SGR
            extended mode (xterm mode 1006).  Defaults to ``False``.
        mouse_motion: If ``True`` (and ``mouse`` is also ``True``),
            enable motion tracking (mode 1003) which reports mouse
            movement even without a button held.  Generates high event
            volume — use sparingly.  Defaults to ``False``.

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
        - In fallback mode, :meth:`poll` always returns ``[]`` and
          :meth:`has_input` always returns ``False``.  Use
          :meth:`read_line` for blocking line-based input instead.
          Arrow keys and Ctrl+key combos are not available in fallback
          mode — only printable characters and Enter.
        - When mouse mode is enabled, middle-click paste may not work
          in some terminals (the terminal captures the click).  Some
          terminals allow Shift+middle-click as a workaround.
        - Mouse mode is silently ignored in fallback mode (non-TTY)
          since there is no terminal to receive mouse escape sequences.
    """

    __slots__ = ("_backend", "_started", "_fallback", "_mouse", "_mouse_motion")

    def __init__(
        self,
        backend: InputBackend | None = None,
        allow_fallback: bool = False,
        mouse: bool = False,
        mouse_motion: bool = False,
    ) -> None:
        if backend is None:
            from wyby._platform import create_backend

            backend = create_backend()
        self._backend = backend
        self._started = False
        self._fallback = allow_fallback
        self._mouse = mouse
        self._mouse_motion = mouse_motion

    @property
    def is_started(self) -> bool:
        """Whether the manager is active (raw mode entered)."""
        return self._started

    @property
    def is_fallback(self) -> bool:
        """Whether the manager is using ``input()`` fallback mode.

        Returns ``True`` if raw mode was unavailable and the manager
        fell back to line-buffered input.  Only meaningful after
        :meth:`start` has been called.
        """
        from wyby._platform import FallbackInputBackend

        return isinstance(self._backend, FallbackInputBackend)

    def start(self) -> None:
        """Enter raw mode and begin accepting input.

        If ``allow_fallback`` was set and stdin is not a TTY, silently
        switches to :class:`~wyby._platform.FallbackInputBackend`
        instead of raising.

        If ``mouse`` was set, enables SGR mouse reporting after
        entering raw mode.

        Raises:
            RuntimeError: If stdin is not a TTY and ``allow_fallback``
                is ``False``.
        """
        if self._started:
            return
        try:
            self._backend.enter_raw_mode()
        except RuntimeError:
            if not self._fallback:
                raise
            from wyby._platform import FallbackInputBackend

            self._backend = FallbackInputBackend()
            self._backend.enter_raw_mode()
            _logger.info(
                "Raw mode unavailable (stdin is not a TTY); "
                "using input() fallback.  poll() will return []; "
                "use read_line() for blocking input."
            )
        self._started = True
        if self._mouse and not self.is_fallback:
            _enable_mouse_mode(self._mouse_motion)
        _logger.debug("InputManager started (mouse=%s)", self._mouse)

    def stop(self) -> None:
        """Exit raw mode and restore terminal settings.

        Safe to call multiple times; subsequent calls are no-ops.
        Disables mouse reporting before restoring cooked mode.
        """
        if not self._started:
            return
        if self._mouse and not self.is_fallback:
            _disable_mouse_mode(self._mouse_motion)
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

    def poll(self) -> list[Event]:
        """Read and parse all available input events (non-blocking).

        Returns a list of :class:`Event` objects (either
        :class:`KeyEvent` or :class:`MouseEvent`) for all input
        since the last call to :meth:`poll`.  Returns an empty list
        if no input is available.

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
            - In fallback mode, this always returns ``[]``.  Use
              :meth:`read_line` instead for blocking input.
            - Mouse events are only returned when mouse mode is
              enabled (``mouse=True`` at construction).
        """
        if not self._started:
            raise RuntimeError(
                "InputManager.poll() called before start().  "
                "Call start() first or use the context manager."
            )
        raw = self._backend.read_bytes()
        if not raw:
            return []
        return parse_input_events(raw)

    def read_line(self, prompt: str = "") -> list[KeyEvent]:
        """Read a line of input using Python's ``input()`` (blocking).

        This is the primary input method when running in fallback mode
        (stdin is not a TTY), but it also works in normal raw-mode
        operation — :meth:`stop` is called before reading and
        :meth:`start` is called after, so the terminal is temporarily
        returned to cooked mode for ``input()`` to work correctly.

        Each character in the entered line becomes a :class:`KeyEvent`,
        followed by a final ``KeyEvent(key="enter")``.

        Args:
            prompt: Optional prompt string passed to ``input()``.

        Returns:
            A list of :class:`KeyEvent` objects.  Returns an empty
            list on ``EOFError`` (e.g., stdin closed or Ctrl+D).

        Caveats:
            - **Blocking**: this call waits for the user to type a
              full line and press Enter.  It is not suitable for
              real-time game loops that need non-blocking input.
            - **No special keys**: arrow keys, function keys, and
              Ctrl+key combinations are not detectable.  Only
              printable characters and Enter are returned.
            - **Echo is on**: the user sees what they type.  The
              terminal's line editor handles backspace and cursor
              movement.
            - In normal (raw-mode) operation, the terminal is
              temporarily switched back to cooked mode for the
              duration of the ``input()`` call.  This may cause a
              visible mode-switch flicker on some terminals.

        Usage::

            with InputManager(allow_fallback=True) as manager:
                events = manager.read_line("Enter command: ")
                for event in events:
                    if event.key == "q":
                        break
        """
        if not self._started:
            raise RuntimeError(
                "InputManager.read_line() called before start().  "
                "Call start() first or use the context manager."
            )
        # If in raw mode, temporarily exit so input() works correctly
        # (raw mode disables echo and line editing).
        was_raw = self._backend.is_raw
        if was_raw:
            self._backend.exit_raw_mode()
        try:
            line = input(prompt)
        except EOFError:
            return []
        finally:
            if was_raw:
                self._backend.enter_raw_mode()
        events: list[KeyEvent] = []
        for ch in line:
            if ch == " ":
                events.append(KeyEvent(key="space"))
            else:
                events.append(KeyEvent(key=ch))
        events.append(KeyEvent(key="enter"))
        return events

    def __enter__(self) -> InputManager:
        self.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.stop()

    def __repr__(self) -> str:
        if self.is_fallback:
            return f"InputManager(started={self._started}, fallback=True)"
        return f"InputManager(started={self._started})"
