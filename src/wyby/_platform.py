"""Platform-specific input backends (Unix/Windows).

This module will provide the low-level, platform-dependent code for
reading keyboard input: ``termios`` raw mode on Unix, ``msvcrt`` on
Windows.

Caveats:
    - **Not yet implemented.** This module is a placeholder establishing
      the package structure. See SCOPE.md for the intended design.
    - This module is internal (prefixed with ``_``). Game code should
      use the public API in ``wyby.input``, not import from here
      directly.
    - On Unix, raw mode via ``termios`` disables line buffering and
      echo. Terminal cooked mode **must** be restored on exit, including
      on crashes and signal interrupts (SIGINT, SIGTERM). Failure to
      restore leaves the terminal in a broken state.
    - On Windows, ``msvcrt.kbhit()`` / ``msvcrt.getwch()`` behave
      differently from Unix in key representation and timing. Some
      keys produce two-byte sequences on Windows (e.g., arrow keys
      return ``\\x00`` or ``\\xe0`` followed by a scan code).
    - SSH sessions, ``screen``/``tmux`` multiplexers, and containers
      may alter input behaviour in ways that are difficult to detect
      at runtime.
"""
