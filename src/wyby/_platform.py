"""Platform-specific input backends (Unix/Windows).

This module provides the low-level, platform-dependent code for
reading raw bytes from stdin without line buffering or echo.

On Unix (Linux, macOS, BSDs):
    Uses ``termios`` to switch stdin to raw mode and ``select.select``
    for non-blocking reads.  Raw mode disables line buffering, echo,
    and signal generation (Ctrl+C no longer sends SIGINT — the byte
    ``\\x03`` is delivered to the application instead).

On Windows:
    Uses ``msvcrt.kbhit()`` to check for available input and
    ``msvcrt.getwch()`` to read characters without echo.  No terminal
    mode switching is needed because ``msvcrt`` operates at a lower
    level than the console line editor.

Why not the ``keyboard`` library (Linux sudo requirement):
    The third-party ``keyboard`` library
    (https://pypi.org/project/keyboard/) uses a fundamentally different
    mechanism on Linux: it opens ``/dev/input/event*`` device files to
    read raw evdev events at the OS level.  These device files are
    owned by ``root:input`` with mode ``0660``, so accessing them
    requires either:

    - Running the process as **root** (``sudo python my_game.py``), or
    - Adding the user to the ``input`` group (``sudo usermod -aG input $USER``),
      which grants access to **all** input devices (keyboards, mice,
      joysticks) for **all** applications — a significant security
      escalation.

    This is a hard requirement of the library's design, not a bug.  On
    Linux, ``keyboard`` hooks into the kernel input subsystem via
    ``/dev/input``, which is a privileged operation.  Without elevated
    access, ``keyboard.on_press()`` and similar calls raise
    ``PermissionError`` or silently fail.

    Additional issues with the ``keyboard`` library on Linux:

    - **System-wide capture**: reads keystrokes from *all* applications,
      not just the terminal running the game.  A game should never
      intercept passwords or other sensitive input from other windows.
    - **Keylogger semantics**: even if used benignly, the ``/dev/input``
      mechanism is identical to how keyloggers work.  Bundling a library
      that requires root to read all keystrokes raises trust concerns.
    - **No terminal integration**: bypasses the terminal entirely, so it
      cannot distinguish between terminals when multiple are open and
      does not work with ``tmux``/``screen`` multiplexers.
    - **Broken in containers/SSH**: Docker containers and SSH sessions
      typically do not expose ``/dev/input``, so ``keyboard`` fails in
      common deployment environments.

    wyby avoids all of these issues by reading only from the process's
    own stdin using ``termios`` (Unix) / ``msvcrt`` (Windows).  No
    elevated privileges are required on any platform.

Caveats:
    - This module is internal (prefixed with ``_``).  Game code should
      use the public API in ``wyby.input``, not import from here
      directly.
    - On Unix, raw mode via ``termios`` disables line buffering and
      echo.  Terminal cooked mode **must** be restored on exit, including
      on crashes and signal interrupts (SIGINT, SIGTERM).  Failure to
      restore leaves the terminal in a broken state.
    - On Windows, ``msvcrt.kbhit()`` / ``msvcrt.getwch()`` behave
      differently from Unix in key representation and timing.  Some
      keys produce two-byte sequences on Windows (e.g., arrow keys
      return ``\\x00`` or ``\\xe0`` followed by a scan code).
    - SSH sessions, ``screen``/``tmux`` multiplexers, and containers
      may alter input behaviour in ways that are difficult to detect
      at runtime.
    - When stdin is not a TTY (e.g., piped input, CI environments),
      raw mode cannot be entered.  The backends detect this and raise
      ``RuntimeError``.
"""

from __future__ import annotations

import abc
import logging
import os
import sys
_logger = logging.getLogger(__name__)


class InputBackend(abc.ABC):
    """Abstract base class for platform-specific input backends.

    Subclasses implement raw-mode entry/exit and non-blocking byte
    reads from stdin.  The public :class:`~wyby.input.InputManager`
    uses a backend instance internally — game code should not interact
    with backends directly.
    """

    @abc.abstractmethod
    def enter_raw_mode(self) -> None:
        """Switch stdin to raw mode (no echo, no line buffering).

        Raises:
            RuntimeError: If stdin is not a TTY.
        """

    @abc.abstractmethod
    def exit_raw_mode(self) -> None:
        """Restore stdin to its original (cooked) mode.

        Safe to call multiple times; subsequent calls are no-ops.
        """

    @abc.abstractmethod
    def has_input(self) -> bool:
        """Check whether input bytes are available without consuming them.

        This is a non-blocking peek — it returns ``True`` if at least
        one byte is ready to be read, ``False`` otherwise.  No bytes
        are consumed; a subsequent :meth:`read_bytes` call will still
        return them.

        Must be called while in raw mode.

        Caveats:
            - A ``True`` return means at least one byte is available,
              but that byte may be part of an incomplete ANSI escape
              sequence (e.g., a lone ``ESC`` byte that hasn't been
              followed by ``[`` yet).  Use :meth:`read_bytes` and the
              parser to get complete key events.
            - On Unix, this uses ``select.select`` with a zero timeout.
              On Windows, this uses ``msvcrt.kbhit()``.  Both are
              non-blocking but have platform-specific edge cases.
        """

    @abc.abstractmethod
    def read_bytes(self) -> bytes:
        """Non-blocking read of all available bytes from stdin.

        Returns an empty ``bytes`` object if no input is available.
        Must be called while in raw mode.
        """

    @property
    @abc.abstractmethod
    def is_raw(self) -> bool:
        """Whether stdin is currently in raw mode."""


# ---- Unix backend --------------------------------------------------------

if sys.platform != "win32":
    import select
    import termios
    import tty

    class UnixInputBackend(InputBackend):
        """Unix input backend using ``termios`` raw mode and ``select``.

        Caveats:
            - Entering raw mode disables Ctrl+C signal generation.
              The byte ``\\x03`` is delivered as regular input.  The
              ``InputManager`` is responsible for interpreting it as
              a ``KeyboardInterrupt``.
            - ``select.select`` with a zero timeout provides
              non-blocking reads but has O(n) cost in the number of
              file descriptors on some platforms.  For a single stdin
              fd this is negligible.
            - If the process is backgrounded (``SIGTSTP``), the terminal
              driver may reset settings.  Foregrounding does not
              automatically re-enter raw mode.  The engine should
              re-enter raw mode after ``SIGCONT`` if needed.
        """

        __slots__ = ("_fd", "_old_settings", "_raw")

        def __init__(self, fd: int | None = None) -> None:
            self._fd = fd if fd is not None else sys.stdin.fileno()
            self._old_settings: list[object] | None = None
            self._raw = False

        def enter_raw_mode(self) -> None:
            if self._raw:
                return
            if not os.isatty(self._fd):
                raise RuntimeError(
                    "stdin is not a TTY — cannot enter raw mode.  "
                    "This typically means input is piped or the process "
                    "is running in a non-interactive environment (CI, "
                    "cron, Docker without -it)."
                )
            self._old_settings = termios.tcgetattr(self._fd)
            tty.setraw(self._fd)
            self._raw = True
            _logger.debug("Entered raw mode on fd %d", self._fd)

        def exit_raw_mode(self) -> None:
            if not self._raw or self._old_settings is None:
                return
            termios.tcsetattr(
                self._fd, termios.TCSADRAIN, self._old_settings
            )
            self._raw = False
            self._old_settings = None
            _logger.debug("Restored cooked mode on fd %d", self._fd)

        def has_input(self) -> bool:
            """Check for available input via ``select`` without consuming.

            Caveats:
                - Uses ``select.select`` with a zero timeout, same as
                  :meth:`read_bytes`.  The cost is negligible for a
                  single file descriptor.
                - A ``True`` result does not guarantee a complete key
                  event — the available byte(s) may be the start of a
                  multi-byte ANSI escape sequence.
            """
            readable, _, _ = select.select([self._fd], [], [], 0)
            return bool(readable)

        def read_bytes(self) -> bytes:
            """Non-blocking read via ``select`` + ``os.read``.

            Returns all available bytes (up to 1024) or empty bytes
            if nothing is available.

            Caveats:
                - Reads up to 1024 bytes at a time.  A single key press
                  is typically 1–6 bytes (UTF-8 char or ANSI escape
                  sequence), so 1024 is generous.
                - If select reports readability but os.read returns
                  empty bytes, stdin has reached EOF (e.g., piped input
                  exhausted).
            """
            readable, _, _ = select.select([self._fd], [], [], 0)
            if not readable:
                return b""
            return os.read(self._fd, 1024)

        @property
        def is_raw(self) -> bool:
            return self._raw


# ---- Windows backend -----------------------------------------------------

if sys.platform == "win32":
    import msvcrt

    class WindowsInputBackend(InputBackend):
        """Windows input backend using ``msvcrt``.

        Caveats:
            - ``msvcrt.getwch()`` returns characters (not bytes).
              The returned string is encoded to bytes for consistency
              with the Unix backend.
            - Arrow keys and function keys produce two-character
              sequences: ``\\x00`` or ``\\xe0`` followed by a scan
              code byte.  The ``read_bytes`` method reads both parts
              in a single call.
            - No terminal mode switching is needed on Windows — there
              is no equivalent of "cooked mode" that needs restoring.
              ``enter_raw_mode`` and ``exit_raw_mode`` are no-ops.
            - On Windows, ``msvcrt`` only works with the console
              (``conhost.exe`` or Windows Terminal).  It does not work
              with pipes or redirected stdin.
        """

        __slots__ = ("_raw",)

        def __init__(self) -> None:
            self._raw = False

        def enter_raw_mode(self) -> None:
            # No mode switching needed on Windows.  msvcrt bypasses
            # the console line editor by default.
            self._raw = True
            _logger.debug("Windows input backend activated (no mode switch)")

        def exit_raw_mode(self) -> None:
            self._raw = False

        def has_input(self) -> bool:
            """Check for available input via ``msvcrt.kbhit()``.

            Caveats:
                - ``msvcrt.kbhit()`` returns ``True`` if a key press
                  is waiting in the console input buffer.  This is a
                  true peek — no characters are consumed.
            """
            return bool(msvcrt.kbhit())

        def read_bytes(self) -> bytes:
            """Read available key bytes via ``msvcrt``.

            Checks ``kbhit()`` and reads one key.  If the key is a
            special key (arrow, function key), reads the second byte
            as well.
            """
            result = b""
            while msvcrt.kbhit():
                ch = msvcrt.getwch()
                encoded = ch.encode("utf-8", errors="replace")
                result += encoded
                # Special keys: \x00 or \xe0 prefix means the next
                # byte is the scan code.
                if ch in ("\x00", "\xe0") and msvcrt.kbhit():
                    ch2 = msvcrt.getwch()
                    result += ch2.encode("utf-8", errors="replace")
            return result

        @property
        def is_raw(self) -> bool:
            return self._raw


class FallbackInputBackend(InputBackend):
    """Fallback backend using line-buffered stdin for non-TTY environments.

    Used when stdin is not a TTY (piped input, CI, containers without
    ``-it``, etc.) and the caller has opted in via ``allow_fallback``.
    Does **not** enter raw mode — terminal settings are left unchanged.

    Intended for use with :meth:`InputManager.read_line`, which calls
    Python's built-in ``input()`` for blocking, line-based interaction.
    :meth:`poll` will always return an empty list because non-blocking
    reads are not possible in cooked (line-buffered) mode without
    platform-specific tricks.

    Caveats:
        - ``input()`` is **blocking** — it waits for a full line
          terminated by Enter.  This is fundamentally different from the
          non-blocking :meth:`poll` used in real-time game loops.
        - No ANSI escape sequence support.  Arrow keys, function keys,
          and modifier combinations (Ctrl+key) are not detectable.  Only
          printable characters and Enter are reliably available.
        - Echo is enabled — typed characters appear on screen.  The
          terminal's built-in line editor handles backspace, cursor
          movement, and history (if supported by the shell).
        - ``has_input()`` always returns ``False`` because there is no
          portable way to peek at cooked-mode stdin without blocking.
        - This backend is suitable for simple menu-driven interfaces
          (e.g., "press 1 for new game"), not real-time gameplay.
    """

    __slots__ = ("_active",)

    def __init__(self) -> None:
        self._active = False

    def enter_raw_mode(self) -> None:
        # No mode switch — stdin stays in cooked (line-buffered) mode.
        self._active = True
        _logger.debug("Fallback input backend activated (no raw mode)")

    def exit_raw_mode(self) -> None:
        self._active = False

    def has_input(self) -> bool:
        # Cannot peek at cooked-mode stdin portably without blocking.
        return False

    def read_bytes(self) -> bytes:
        # Non-blocking reads are not possible in cooked mode.
        # Use InputManager.read_line() instead.
        return b""

    @property
    def is_raw(self) -> bool:
        # Never actually in raw mode — always cooked/line-buffered.
        return False


def create_backend() -> InputBackend:
    """Create the appropriate input backend for the current platform.

    No elevated privileges (sudo/root) are required on any platform.
    The returned backend reads only from the process's own stdin —
    it never accesses ``/dev/input`` or installs system-wide hooks.

    Returns:
        A :class:`UnixInputBackend` on Unix-like systems or a
        :class:`WindowsInputBackend` on Windows.
    """
    if sys.platform == "win32":
        return WindowsInputBackend()
    return UnixInputBackend()
