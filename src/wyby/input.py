"""Keyboard input abstraction.

This module will provide a cross-platform keyboard input layer that reads
from the process's own stdin, parses ANSI escape sequences into normalised
key events, and exposes a polling/queue-based API for the game loop.

Caveats:
    - **Not yet implemented.** This module is a placeholder establishing
      the package structure. See SCOPE.md for the intended design.
    - Terminal input is inherently platform-dependent. On Unix, raw mode
      via ``termios`` is used; on Windows, ``msvcrt.kbhit()`` /
      ``msvcrt.getwch()``. Behaviour differs in key representation and
      timing between platforms.
    - The ``keyboard`` library is **explicitly excluded**. It installs
      system-wide hooks, requires root/admin on Linux, captures input
      from all applications, and raises security concerns. wyby only
      reads from its own terminal's stdin.
    - Mouse support is not included in v0.1. Some terminals support mouse
      reporting via escape sequences, but coverage is inconsistent.
    - Terminal cooked-mode must be restored on exit. Signal handlers are
      needed to clean up even on Ctrl+C or unexpected termination.
    - Modifier key detection (Shift, Alt, Ctrl) varies by terminal.
      Not all terminals report all modifier combinations.
"""
