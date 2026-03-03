"""Process-level signal handlers for safe Ctrl+C and SIGTERM handling.

This module provides :class:`SignalHandler`, a context manager that
installs SIGINT and SIGTERM handlers for graceful shutdown of terminal
games.

Why process-level handlers (not global hooks):
    wyby uses Python's standard :mod:`signal` module, which registers
    handlers at the **process level** only.  These handlers affect only
    the game's own process — they do not install system-wide keyboard
    hooks, do not access ``/dev/input``, and do not require elevated
    privileges.  This is consistent with wyby's design principle of
    reading only from the process's own stdin (see ``input.py`` and
    ``_platform.py`` for the full rationale on avoiding the ``keyboard``
    library).

How Ctrl+C reaches the engine (two paths):
    1. **In raw mode (Unix):** ``termios`` raw mode disables ISIG, so
       Ctrl+C does not generate SIGINT.  Instead, the terminal delivers
       byte ``0x03`` to stdin.  :func:`~wyby.input.parse_input_events`
       detects this byte and raises ``KeyboardInterrupt``.  The engine
       catches this in :meth:`~wyby.app.Engine.run`.
    2. **External SIGINT:** ``kill -2 <pid>`` (or Ctrl+C before raw mode
       is entered) delivers SIGINT to the process.  The handler installed
       by this module sets a flag and raises ``KeyboardInterrupt`` in the
       main thread, which the engine catches the same way.

    Both paths converge on the same ``except KeyboardInterrupt`` clause
    in :meth:`~wyby.app.Engine.run`, ensuring consistent cleanup.

SIGTERM handling:
    ``kill <pid>`` sends SIGTERM, which by default terminates the process
    immediately with no cleanup — the terminal is left in raw mode.  The
    handler installed by this module converts SIGTERM into a
    ``KeyboardInterrupt`` so the engine performs its normal graceful
    shutdown (scene teardown, terminal restoration).

Double-interrupt protection:
    If the user presses Ctrl+C a second time during shutdown (e.g.,
    because an exit hook is slow), the handler raises
    ``KeyboardInterrupt`` again.  The engine's ``_shutdown`` method
    is hardened against this — it catches ``KeyboardInterrupt`` and
    still attempts to restore the terminal.

Caveats:
    - ``signal.signal()`` can only be called from the **main thread**.
      Calling :meth:`SignalHandler.install` from a background thread
      raises ``ValueError``.  The engine calls it from its main loop,
      which is always the main thread.
    - ``SIGKILL`` (``kill -9``) **cannot** be caught by any handler.
      If the process is killed with ``-9``, the terminal will be left
      in raw mode.  Run ``reset`` or ``stty sane`` to recover.
    - On Windows, only ``SIGINT`` is supported (``SIGTERM`` is not
      reliably delivered).  The handler installs a ``SIGINT`` handler
      on all platforms but only installs ``SIGTERM`` on Unix.
    - Signal handlers are global per-process state.  Installing a
      handler replaces any previously installed handler for that signal.
      :class:`SignalHandler` saves and restores the original handlers
      on :meth:`uninstall` (or context manager exit).
"""

from __future__ import annotations

import logging
import os
import signal
from types import FrameType

_logger = logging.getLogger(__name__)

# SIGTERM is not reliably delivered on Windows.  Only install a handler
# for it on platforms that support it (Unix-like systems).
_HAS_SIGTERM = hasattr(signal, "SIGTERM") and os.name != "nt"


class SignalHandler:
    """Context manager for process-level SIGINT/SIGTERM handling.

    Installs signal handlers that convert OS signals into
    ``KeyboardInterrupt`` exceptions, ensuring the engine's normal
    shutdown path runs.

    Usage::

        handler = SignalHandler()
        handler.install()
        try:
            run_game_loop()
        finally:
            handler.uninstall()

    Or as a context manager::

        with SignalHandler():
            run_game_loop()

    Caveats:
        - Must be instantiated and used from the **main thread**.
          ``signal.signal()`` raises ``ValueError`` if called from
          a non-main thread.
        - The handler is not re-entrant.  Do not nest multiple
          ``SignalHandler`` instances for the same signals.
        - After :meth:`uninstall`, the original signal handlers
          (whatever was installed before) are restored.  If the
          original handler was ``SIG_DFL`` or ``SIG_IGN``, that
          behaviour is restored exactly.
    """

    __slots__ = (
        "_original_sigint",
        "_original_sigterm",
        "_interrupted",
        "_installed",
    )

    def __init__(self) -> None:
        self._original_sigint: signal.Handlers | None = None
        self._original_sigterm: signal.Handlers | None = None
        self._interrupted = False
        self._installed = False

    @property
    def interrupted(self) -> bool:
        """Whether at least one interrupt signal has been received.

        This flag is set ``True`` on the first SIGINT or SIGTERM and
        never resets.  Use it to detect whether a second signal is a
        "force quit" request.
        """
        return self._interrupted

    def install(self) -> None:
        """Install SIGINT and SIGTERM handlers.

        Saves the current handlers so they can be restored by
        :meth:`uninstall`.  Safe to call multiple times — subsequent
        calls are no-ops.

        Raises:
            ValueError: If called from a non-main thread (Python
                limitation of ``signal.signal``).
        """
        if self._installed:
            return
        self._original_sigint = signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGINT, self._handle_interrupt)
        if _HAS_SIGTERM:
            self._original_sigterm = signal.getsignal(signal.SIGTERM)
            signal.signal(signal.SIGTERM, self._handle_interrupt)
        self._installed = True
        _logger.debug("Signal handlers installed (SIGINT%s)",
                       "+SIGTERM" if _HAS_SIGTERM else " only")

    def uninstall(self) -> None:
        """Restore original signal handlers.

        Safe to call multiple times — subsequent calls are no-ops.
        After this call, SIGINT and SIGTERM revert to whatever
        handlers were installed before :meth:`install`.
        """
        if not self._installed:
            return
        if self._original_sigint is not None:
            signal.signal(signal.SIGINT, self._original_sigint)
        if _HAS_SIGTERM and self._original_sigterm is not None:
            signal.signal(signal.SIGTERM, self._original_sigterm)
        self._installed = False
        _logger.debug("Signal handlers restored to originals")

    def _handle_interrupt(
        self, signum: int, frame: FrameType | None
    ) -> None:
        """Handle SIGINT or SIGTERM by raising KeyboardInterrupt.

        On the first signal, sets the ``interrupted`` flag and raises
        ``KeyboardInterrupt``.  On subsequent signals (e.g., user
        pressing Ctrl+C during shutdown), raises ``KeyboardInterrupt``
        again so the user can force-quit if cleanup is stuck.

        Caveats:
            - Raising an exception from a signal handler is delivered
              asynchronously to the main thread.  It will interrupt
              whatever code is currently executing, including ``sleep``
              calls and I/O operations.
            - The ``interrupted`` flag is not thread-safe (no lock).
              This is acceptable because signal handlers are always
              invoked in the main thread.
        """
        sig_name = signal.Signals(signum).name
        if self._interrupted:
            _logger.debug(
                "Second %s received — forcing KeyboardInterrupt", sig_name
            )
        else:
            _logger.debug(
                "%s received — initiating graceful shutdown", sig_name
            )
        self._interrupted = True
        raise KeyboardInterrupt

    def __enter__(self) -> SignalHandler:
        self.install()
        return self

    def __exit__(self, *_: object) -> None:
        self.uninstall()

    def __repr__(self) -> str:
        state = "installed" if self._installed else "not installed"
        if self._interrupted:
            state += ", interrupted"
        return f"SignalHandler({state})"
