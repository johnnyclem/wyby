"""Input handling for RuneTUI.

Caveat: Full non-blocking keyboard input in the terminal is platform-dependent.
- On Linux, the `keyboard` library requires root/sudo for global hooks.
- On Windows, msvcrt provides basic key detection without elevation.
- On macOS, behavior varies by terminal emulator.

This module provides a cross-platform fallback using sys.stdin with select
(Unix) or msvcrt (Windows). For advanced input, users can opt into the
`keyboard` library at their own risk (see docs for permission requirements).

Mouse support requires terminal-level escape sequence parsing and is not
reliably available across all terminals.
"""

from __future__ import annotations

import logging
import sys
from typing import Optional

from runetui.events import EventQueue, KeyEvent, Event, EventType

logger = logging.getLogger(__name__)


def _is_windows() -> bool:
    return sys.platform == "win32"


class InputManager:
    """Manages keyboard input for the game loop.

    Uses platform-appropriate non-blocking input detection. Events are pushed
    into the provided EventQueue for consumption by scenes.

    Caveat: Non-blocking input detection varies by platform:
    - Windows: uses msvcrt.kbhit/getch (no sudo needed)
    - Unix/macOS: uses select on stdin in raw/cbreak mode
    - The `keyboard` library can be used for richer input but requires
      elevated permissions on Linux. This is opt-in and not used by default.
    """

    def __init__(self, event_queue: EventQueue) -> None:
        self._event_queue = event_queue
        self._raw_mode_active = False
        self._old_settings = None

    def start(self) -> None:
        """Initialize input handling. On Unix, puts stdin into cbreak mode."""
        if _is_windows():
            logger.debug("Input: using msvcrt (Windows)")
            return

        try:
            import termios
            import tty

            self._old_settings = termios.tcgetattr(sys.stdin)
            tty.setcbreak(sys.stdin.fileno())
            self._raw_mode_active = True
            logger.debug("Input: cbreak mode enabled (Unix)")
        except (ImportError, termios.error) as exc:
            logger.warning("Could not set cbreak mode: %s. Input may require Enter key.", exc)

    def poll(self) -> None:
        """Check for pending input and push events to the queue.

        Call this once per frame in the game loop's input phase.
        """
        if _is_windows():
            self._poll_windows()
        else:
            self._poll_unix()

    def _poll_windows(self) -> None:
        """Poll for input on Windows using msvcrt."""
        try:
            import msvcrt

            while msvcrt.kbhit():
                ch = msvcrt.getch().decode("utf-8", errors="replace")
                self._event_queue.push(KeyEvent(key=ch))
        except Exception:
            pass

    def _poll_unix(self) -> None:
        """Poll for input on Unix using select on stdin."""
        try:
            import select

            while select.select([sys.stdin], [], [], 0)[0]:
                ch = sys.stdin.read(1)
                if ch:
                    # Handle escape sequences (arrow keys, etc.)
                    if ch == "\x1b":
                        ch = self._read_escape_sequence()
                    self._event_queue.push(KeyEvent(key=ch))
        except Exception:
            pass

    def _read_escape_sequence(self) -> str:
        """Attempt to read a multi-byte escape sequence."""
        import select

        seq = "\x1b"
        # Check for more bytes with a short timeout
        if select.select([sys.stdin], [], [], 0.05)[0]:
            ch = sys.stdin.read(1)
            seq += ch
            if ch == "[":
                # CSI sequence
                if select.select([sys.stdin], [], [], 0.05)[0]:
                    ch = sys.stdin.read(1)
                    seq += ch
                    key_map = {"A": "UP", "B": "DOWN", "C": "RIGHT", "D": "LEFT"}
                    if ch in key_map:
                        return key_map[ch]
        # If we only got ESC with no follow-up, it's the Escape key
        if seq == "\x1b":
            return "ESCAPE"
        return seq

    def stop(self) -> None:
        """Restore terminal settings."""
        if self._raw_mode_active and self._old_settings is not None:
            try:
                import termios

                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self._old_settings)
                self._raw_mode_active = False
                logger.debug("Input: terminal settings restored")
            except Exception as exc:
                logger.warning("Failed to restore terminal settings: %s", exc)

    def create_quit_event(self) -> Event:
        """Create a quit event to signal the engine to stop."""
        return Event(event_type=EventType.QUIT)
