"""Alternate screen buffer management.

Enable and disable the terminal's alternate screen buffer.  When
enabled, the terminal switches to a clean, separate buffer.  When
disabled, the original screen content is restored.  This is the
standard behaviour for full-screen terminal applications (vim, less,
htop) and is essential for terminal games that want to preserve the
user's scrollback.

Usage::

    from wyby.alt_screen import AltScreen

    with AltScreen():
        # game runs in the alternate buffer
        ...
    # original screen is restored here

Or manually::

    from wyby.alt_screen import enable_alt_screen, disable_alt_screen

    enable_alt_screen()
    try:
        ...
    finally:
        disable_alt_screen()

Caveats:
    - The escape sequences used (``CSI ?1049h`` / ``CSI ?1049l``) are
      part of the xterm private mode extensions, not the core ECMA-48
      standard.  They are supported by virtually all modern terminal
      emulators (xterm, iTerm2, kitty, WezTerm, Windows Terminal, GNOME
      Terminal, Alacritty) but are **not universal**.
    - The **Linux virtual console** (tty1–tty6) does not support the
      alternate screen buffer.  The escape sequences are silently
      ignored, and the game output will overwrite visible console text.
    - On **Windows**, alt-screen is supported by Windows Terminal and
      ConPTY-based terminals (Windows 10 1903+) but **not** by the
      legacy Windows Console Host (``conhost.exe`` before the ConPTY
      update).  Legacy console ignores the sequences silently.
    - **screen** and **tmux** support alt-screen but may intercept or
      modify the behaviour via their ``altscreen`` option.  If the
      multiplexer has ``altscreen off``, the sequences are swallowed
      and the user's scrollback is not preserved.
    - If the process is killed with ``SIGKILL`` (``kill -9``) or by a
      power loss, the terminal may be left in alt-screen mode.  The
      user can recover with ``reset``, ``tput rmcup``, or by closing
      and reopening the terminal window.  ``SIGTERM`` and ``SIGINT``
      can be caught to run cleanup, but ``SIGKILL`` cannot.
    - **Nested enable/disable** is not supported by terminals.  Calling
      ``enable_alt_screen()`` twice does not create a stack — the
      second call is a no-op at the terminal level, and a single
      ``disable_alt_screen()`` returns to the main buffer.  This module
      tracks state to prevent redundant writes.
    - **Redirected stdout**: if stdout is not a TTY (e.g., piped to a
      file, running in a CI environment), the enable/disable functions
      are no-ops.  Escape sequences written to a non-terminal pollute
      log files and break downstream parsers.
    - The ``?1049`` mode combines cursor save/restore (``DECSC`` /
      ``DECRC``) with the alt-screen switch.  This means the cursor
      position on the main screen is saved on enable and restored on
      disable.  Not all terminals implement this identically — some
      older xterm versions only support ``?47`` (alt screen without
      cursor save/restore).  We use ``?1049`` as the modern standard.
"""

from __future__ import annotations

import logging
import sys

_logger = logging.getLogger(__name__)

# CSI (Control Sequence Introducer) escape sequences for the alternate
# screen buffer.  These are xterm private mode sequences, not part of
# ECMA-48, but universally supported by modern terminal emulators.
#
# ?1049h — save cursor position, switch to alternate screen, clear it.
# ?1049l — switch back to main screen, restore saved cursor position.
_ENABLE_SEQ = "\033[?1049h"
_DISABLE_SEQ = "\033[?1049l"

# Module-level flag to track whether alt-screen is currently active.
# This prevents redundant escape-sequence writes and provides a way to
# query the current state.  Note: this tracks *our* intent, not the
# terminal's actual state — if another process writes ?1049l to the
# same terminal, we won't know about it.
_active: bool = False


def is_active() -> bool:
    """Return whether the alternate screen buffer is currently enabled.

    This reflects the state as tracked by this module, not the
    terminal's actual mode.  If another process or library writes
    alt-screen escape sequences directly, this flag will be out of
    sync.
    """
    return _active


def _is_tty() -> bool:
    """Return whether stdout is attached to a terminal."""
    try:
        return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()
    except ValueError:
        # stdout may be closed (e.g., during interpreter shutdown).
        return False


def enable_alt_screen(*, stream: object | None = None) -> bool:
    """Switch to the terminal's alternate screen buffer.

    Writes the ``CSI ?1049h`` escape sequence to stdout (or the
    provided *stream*), which saves the cursor position, switches
    to the alternate screen, and clears it.

    Args:
        stream: Writable file-like object to send the escape sequence
            to.  Defaults to ``sys.stdout``.  Must have ``write()``
            and ``flush()`` methods.

    Returns:
        ``True`` if the escape sequence was written, ``False`` if
        it was skipped (stdout not a TTY, or alt-screen already
        active).

    Caveats:
        - No-op if stdout is not a TTY (prevents polluting piped
          output or log files with escape sequences).
        - No-op if alt-screen is already active (prevents redundant
          writes, though terminals would silently ignore them anyway).
        - The ``flush()`` call ensures the sequence reaches the
          terminal immediately rather than sitting in Python's output
          buffer.  Without it, the switch may be delayed until the
          next newline or buffer-full event.
    """
    global _active

    if _active:
        _logger.debug("enable_alt_screen(): already active, skipping")
        return False

    out = stream if stream is not None else sys.stdout

    # When using the default stdout, check that it's a real terminal.
    # When a custom stream is provided, trust the caller — they may be
    # testing or writing to a pty.
    if stream is None and not _is_tty():
        _logger.debug(
            "enable_alt_screen(): stdout is not a TTY, skipping"
        )
        return False

    try:
        out.write(_ENABLE_SEQ)  # type: ignore[union-attr]
        out.flush()  # type: ignore[union-attr]
    except (OSError, ValueError) as exc:
        # OSError: broken pipe, device not configured, etc.
        # ValueError: I/O operation on closed file.
        _logger.warning("enable_alt_screen() failed: %s", exc)
        return False

    _active = True
    _logger.debug("Alternate screen buffer enabled")
    return True


def disable_alt_screen(*, stream: object | None = None) -> bool:
    """Switch back to the terminal's main screen buffer.

    Writes the ``CSI ?1049l`` escape sequence to stdout (or the
    provided *stream*), which switches back to the main screen and
    restores the saved cursor position.

    Args:
        stream: Writable file-like object to send the escape sequence
            to.  Defaults to ``sys.stdout``.  Must have ``write()``
            and ``flush()`` methods.

    Returns:
        ``True`` if the escape sequence was written, ``False`` if
        it was skipped (alt-screen not active).

    Caveats:
        - No-op if alt-screen is not currently active.  This makes
          it safe to call ``disable_alt_screen()`` unconditionally in
          cleanup / ``finally`` blocks without worrying about double-
          disable.
        - The ``flush()`` call ensures the sequence is written
          immediately so the main screen is restored before any
          subsequent output.
        - If the write fails (e.g., broken pipe during shutdown), the
          ``_active`` flag is still cleared — we assume the terminal
          session is gone or will be cleaned up externally.
    """
    global _active

    if not _active:
        _logger.debug("disable_alt_screen(): not active, skipping")
        return False

    out = stream if stream is not None else sys.stdout

    try:
        out.write(_DISABLE_SEQ)  # type: ignore[union-attr]
        out.flush()  # type: ignore[union-attr]
    except (OSError, ValueError) as exc:
        # Best-effort: clear the flag even if the write fails.
        # The terminal session is likely gone or broken.
        _logger.warning("disable_alt_screen() failed: %s", exc)
        _active = False
        return False

    _active = False
    _logger.debug("Alternate screen buffer disabled")
    return True


class AltScreen:
    """Context manager for the alternate screen buffer.

    Enables the alt-screen on entry and disables it on exit, including
    when an exception is raised inside the ``with`` block.

    Example::

        with AltScreen():
            engine.run()
        # Terminal is restored here, even if engine.run() raised.

    Caveats:
        - Uses module-level state, so only one :class:`AltScreen`
          context should be active at a time.  Nesting ``AltScreen``
          contexts will cause the inner ``__exit__`` to disable the
          alt-screen prematurely.
        - If the process receives ``SIGKILL``, ``__exit__`` will not
          run and the terminal will be left in alt-screen mode.  Use
          ``atexit`` or signal handlers for more robust cleanup if
          needed — but note that ``SIGKILL`` cannot be caught at all.
        - If stdout is not a TTY, both ``__enter__`` and ``__exit__``
          are silent no-ops.
    """

    __slots__ = ("_stream", "_entered")

    def __init__(self, *, stream: object | None = None) -> None:
        self._stream = stream
        self._entered = False

    def __enter__(self) -> AltScreen:
        self._entered = enable_alt_screen(stream=self._stream)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object | None,
    ) -> None:
        if self._entered:
            disable_alt_screen(stream=self._stream)

    @property
    def entered(self) -> bool:
        """Whether alt-screen was successfully enabled on entry."""
        return self._entered

    def __repr__(self) -> str:
        return f"AltScreen(active={self._entered})"
