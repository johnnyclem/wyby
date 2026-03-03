"""Cursor visibility management.

Hide and show the terminal text cursor.  Games typically hide the
cursor during gameplay to prevent a blinking block or underline from
appearing over the game grid, then restore it on exit so the user's
shell prompt looks normal.

Usage::

    from wyby.cursor import HiddenCursor

    with HiddenCursor():
        # game runs with cursor hidden
        ...
    # cursor is visible again here

Or manually::

    from wyby.cursor import hide_cursor, show_cursor

    hide_cursor()
    try:
        ...
    finally:
        show_cursor()

Caveats:
    - The escape sequences used (``CSI ?25l`` / ``CSI ?25h``) control
      **DECTCEM** (DEC Text Cursor Enable Mode).  This is an xterm
      private mode, not part of the core ECMA-48 standard, but it is
      supported by virtually all modern terminal emulators (xterm,
      iTerm2, kitty, WezTerm, Windows Terminal, GNOME Terminal,
      Alacritty).
    - The **Linux virtual console** (tty1–tty6) supports DECTCEM, so
      cursor hiding works there — unlike the alternate screen buffer,
      which the Linux console does not support.
    - On **Windows**, cursor hiding is supported by Windows Terminal
      and ConPTY-based terminals (Windows 10 1903+).  The legacy
      Windows Console Host (``conhost.exe``) also supports ``?25l`` /
      ``?25h`` in recent builds but may not honour them in all modes.
    - **screen** and **tmux** support DECTCEM and pass the sequences
      through to the outer terminal.  However, when detaching and
      reattaching a session, the multiplexer may reset cursor
      visibility — the cursor could reappear unexpectedly after a
      reattach.
    - If the process is killed with ``SIGKILL`` (``kill -9``) or by a
      power loss, the cursor will remain hidden.  The user can recover
      with ``tput cnorm``, ``reset``, or ``printf '\\033[?25h'`` in
      the shell.  ``SIGTERM`` and ``SIGINT`` can be caught to run
      cleanup, but ``SIGKILL`` cannot.
    - Rich's ``Live`` display hides and shows the cursor internally
      via the same DECTCEM sequences.  If you use
      :class:`~wyby.renderer.LiveDisplay` or
      :class:`~wyby.renderer.Renderer`, the cursor is already hidden
      while the display is active.  This module is for code that needs
      cursor control **without** a Rich ``Live`` context — for
      example, custom rendering loops, splash screens, or non-Rich
      output phases.
    - **Nested hide/show** is not ref-counted by terminals.  Calling
      ``hide_cursor()`` twice does not require two ``show_cursor()``
      calls — a single show restores the cursor.  This module tracks
      state to prevent redundant writes.
    - **Redirected stdout**: if stdout is not a TTY (e.g., piped to a
      file, running in CI), the hide/show functions are no-ops.
      Escape sequences written to a non-terminal pollute log files
      and break downstream parsers.
"""

from __future__ import annotations

import logging
import sys

_logger = logging.getLogger(__name__)

# CSI (Control Sequence Introducer) escape sequences for cursor
# visibility.  These control DECTCEM (DEC Text Cursor Enable Mode).
#
# ?25l — hide the text cursor.
# ?25h — show (restore) the text cursor.
_HIDE_SEQ = "\033[?25l"
_SHOW_SEQ = "\033[?25h"

# Module-level flag to track whether the cursor is currently hidden.
# This prevents redundant escape-sequence writes and provides a way to
# query the current state.  Note: this tracks *our* intent, not the
# terminal's actual state — if another process or library (e.g., Rich's
# Live display) writes ?25h/l directly, we won't know about it.
_hidden: bool = False


def is_cursor_hidden() -> bool:
    """Return whether the cursor is currently hidden.

    This reflects the state as tracked by this module, not the
    terminal's actual cursor visibility.  If another process or
    library (e.g., Rich's ``Live`` display) writes DECTCEM sequences
    directly, this flag will be out of sync.
    """
    return _hidden


def _is_tty() -> bool:
    """Return whether stdout is attached to a terminal."""
    try:
        return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()
    except ValueError:
        # stdout may be closed (e.g., during interpreter shutdown).
        return False


def hide_cursor(*, stream: object | None = None) -> bool:
    """Hide the terminal text cursor.

    Writes the ``CSI ?25l`` escape sequence to stdout (or the
    provided *stream*), which disables DECTCEM and hides the cursor.

    Args:
        stream: Writable file-like object to send the escape sequence
            to.  Defaults to ``sys.stdout``.  Must have ``write()``
            and ``flush()`` methods.

    Returns:
        ``True`` if the escape sequence was written, ``False`` if
        it was skipped (stdout not a TTY, or cursor already hidden).

    Caveats:
        - No-op if stdout is not a TTY (prevents polluting piped
          output or log files with escape sequences).
        - No-op if the cursor is already hidden (prevents redundant
          writes, though terminals would silently ignore them anyway).
        - The ``flush()`` call ensures the sequence reaches the
          terminal immediately rather than sitting in Python's output
          buffer.  Without it, the hide may be delayed until the
          next newline or buffer-full event.
    """
    global _hidden

    if _hidden:
        _logger.debug("hide_cursor(): already hidden, skipping")
        return False

    out = stream if stream is not None else sys.stdout

    # When using the default stdout, check that it's a real terminal.
    # When a custom stream is provided, trust the caller — they may be
    # testing or writing to a pty.
    if stream is None and not _is_tty():
        _logger.debug("hide_cursor(): stdout is not a TTY, skipping")
        return False

    try:
        out.write(_HIDE_SEQ)  # type: ignore[union-attr]
        out.flush()  # type: ignore[union-attr]
    except (OSError, ValueError) as exc:
        # OSError: broken pipe, device not configured, etc.
        # ValueError: I/O operation on closed file.
        _logger.warning("hide_cursor() failed: %s", exc)
        return False

    _hidden = True
    _logger.debug("Cursor hidden")
    return True


def show_cursor(*, stream: object | None = None) -> bool:
    """Show (restore) the terminal text cursor.

    Writes the ``CSI ?25h`` escape sequence to stdout (or the
    provided *stream*), which enables DECTCEM and shows the cursor.

    Args:
        stream: Writable file-like object to send the escape sequence
            to.  Defaults to ``sys.stdout``.  Must have ``write()``
            and ``flush()`` methods.

    Returns:
        ``True`` if the escape sequence was written, ``False`` if
        it was skipped (cursor not currently hidden).

    Caveats:
        - No-op if the cursor is not currently hidden.  This makes
          it safe to call ``show_cursor()`` unconditionally in
          cleanup / ``finally`` blocks without worrying about double-
          show.
        - The ``flush()`` call ensures the sequence is written
          immediately so the cursor is visible before any subsequent
          output (e.g., a shell prompt).
        - If the write fails (e.g., broken pipe during shutdown), the
          ``_hidden`` flag is still cleared — we assume the terminal
          session is gone or will be cleaned up externally.
    """
    global _hidden

    if not _hidden:
        _logger.debug("show_cursor(): not hidden, skipping")
        return False

    out = stream if stream is not None else sys.stdout

    try:
        out.write(_SHOW_SEQ)  # type: ignore[union-attr]
        out.flush()  # type: ignore[union-attr]
    except (OSError, ValueError) as exc:
        # Best-effort: clear the flag even if the write fails.
        # The terminal session is likely gone or broken.
        _logger.warning("show_cursor() failed: %s", exc)
        _hidden = False
        return False

    _hidden = False
    _logger.debug("Cursor shown")
    return True


class HiddenCursor:
    """Context manager that hides the cursor for its duration.

    Hides the cursor on entry and shows it on exit, including when
    an exception is raised inside the ``with`` block.

    Example::

        with HiddenCursor():
            engine.run()
        # Cursor is visible again here, even if engine.run() raised.

    Caveats:
        - Uses module-level state, so only one :class:`HiddenCursor`
          context should be active at a time.  Nesting ``HiddenCursor``
          contexts will cause the inner ``__exit__`` to show the cursor
          prematurely.
        - If the process receives ``SIGKILL``, ``__exit__`` will not
          run and the cursor will remain hidden.  Use ``atexit`` or
          signal handlers for more robust cleanup if needed — but note
          that ``SIGKILL`` cannot be caught at all.  The user can
          recover with ``tput cnorm`` or ``reset``.
        - If stdout is not a TTY, both ``__enter__`` and ``__exit__``
          are silent no-ops.
    """

    __slots__ = ("_stream", "_entered")

    def __init__(self, *, stream: object | None = None) -> None:
        self._stream = stream
        self._entered = False

    def __enter__(self) -> HiddenCursor:
        self._entered = hide_cursor(stream=self._stream)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object | None,
    ) -> None:
        if self._entered:
            show_cursor(stream=self._stream)

    @property
    def entered(self) -> bool:
        """Whether the cursor was successfully hidden on entry."""
        return self._entered

    def __repr__(self) -> str:
        return f"HiddenCursor(hidden={self._entered})"
