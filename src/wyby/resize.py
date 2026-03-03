"""Terminal resize detection and SIGWINCH handling.

This module provides :class:`ResizeHandler`, which detects terminal size
changes and notifies registered callbacks.  On Unix systems it installs
a ``SIGWINCH`` signal handler for immediate notification; on all
platforms it supports polling via :func:`shutil.get_terminal_size`.

The handler is designed to be installed by the :class:`~wyby.app.Engine`
at the start of ``run()`` and uninstalled in the ``finally`` block.
Game code registers callbacks via :meth:`ResizeHandler.add_callback`
to react to terminal size changes (e.g., re-layout, pause and prompt).

Caveats:
    - **Stub implementation.** This module detects resize events and
      fires callbacks, but the engine does not yet automatically
      re-layout or re-render in response to resize.  Game code is
      responsible for deciding how to handle the new dimensions.
    - **SIGWINCH is Unix-only.**  On Windows, ``signal.SIGWINCH``
      does not exist.  The handler falls back to size-change detection
      via polling (call :meth:`ResizeHandler.poll` each tick).  The
      polling approach works but introduces latency — resize is
      detected on the next poll, not immediately.
    - **Signal handler limitations.**  Python signal handlers execute
      in the main thread between bytecodes.  They cannot interrupt
      blocking I/O (e.g., ``time.sleep``).  The resize-pending flag
      is set atomically and checked on the next game-loop iteration.
    - **Nested/stacked handlers.**  Installing the ``SIGWINCH``
      handler replaces any previously installed handler.  The previous
      handler is saved and restored on :meth:`uninstall`.  Libraries
      that also install ``SIGWINCH`` handlers (e.g., Rich's ``Live``
      display) may conflict if both are active simultaneously.
    - **Terminal size accuracy.**  :func:`shutil.get_terminal_size`
      returns a fallback value (typically 80x24) when stdout is not a
      terminal (piped output, CI environments, some IDEs).  Do not
      assume the reported size always matches the actual visible area.
    - **Thread safety.**  Signal handlers always run in the main
      thread.  The ``_resize_pending`` flag is a simple boolean read
      and written from the main thread only.  If callbacks are
      registered from other threads, external synchronization is the
      caller's responsibility.
"""

from __future__ import annotations

import logging
import shutil
import signal
from collections.abc import Callable

_logger = logging.getLogger(__name__)

# Type alias for resize callbacks.  Receives (columns, rows).
ResizeCallback = Callable[[int, int], None]

# Whether the current platform supports SIGWINCH.  This is True on
# Unix (Linux, macOS, BSDs) and False on Windows.  We check for the
# attribute rather than the platform name so that exotic Unix-like
# systems are handled correctly.
_HAS_SIGWINCH: bool = hasattr(signal, "SIGWINCH")


def get_terminal_size() -> tuple[int, int]:
    """Return the current terminal size as ``(columns, rows)``.

    Uses :func:`shutil.get_terminal_size`, which queries the terminal
    attached to stdout (or stderr as fallback) and returns
    ``os.terminal_size``.

    Returns:
        A ``(columns, rows)`` tuple of integers.

    Caveats:
        - Returns a fallback of ``(80, 24)`` when stdout is not a
          terminal (e.g., piped output, pytest capture, CI).  This
          matches the classic VT100 default but may not reflect the
          real display area.
        - On some platforms, the reported size may lag behind the
          actual terminal dimensions by one frame after a resize,
          depending on when the OS updates the pty size.
    """
    size = shutil.get_terminal_size()
    return (size.columns, size.lines)


class ResizeHandler:
    """Detects terminal size changes and fires registered callbacks.

    The handler tracks the *last known* terminal size.  When a resize
    is detected (via ``SIGWINCH`` on Unix, or :meth:`poll` on any
    platform), it sets a pending flag and records the new size.
    Calling :meth:`consume` clears the flag, fires all registered
    callbacks with the new ``(columns, rows)``, and returns ``True``.
    If no resize is pending, :meth:`consume` returns ``False``.

    Typical usage inside a game loop::

        handler = ResizeHandler()
        handler.install()
        try:
            while running:
                handler.poll()  # No-op if SIGWINCH already set the flag
                if handler.consume():
                    # React to new terminal size
                    pass
                # ... rest of game loop ...
        finally:
            handler.uninstall()

    Args:
        fallback_columns: Column count to use when terminal size
            cannot be determined.  Defaults to 80.
        fallback_rows: Row count to use when terminal size cannot
            be determined.  Defaults to 24.

    Caveats:
        - Callbacks are fired synchronously inside :meth:`consume`,
          which runs in the game-loop thread.  Long-running callbacks
          will block the game loop.  Keep callbacks fast.
        - The handler does **not** automatically call :meth:`poll` or
          :meth:`consume`.  The engine (or game code) must call these
          at the appropriate point in the loop.
        - Installing the handler on a non-main thread raises
          ``ValueError`` (Python restriction on signal handlers).
          The handler gracefully falls back to poll-only mode and
          logs a warning.
    """

    __slots__ = (
        "_columns",
        "_rows",
        "_resize_pending",
        "_callbacks",
        "_prev_handler",
        "_installed",
    )

    def __init__(
        self,
        fallback_columns: int = 80,
        fallback_rows: int = 24,
    ) -> None:
        cols, rows = get_terminal_size()
        # shutil.get_terminal_size returns (80, 24) as its own default
        # when not attached to a terminal.  We use the caller's
        # fallback only if the system returned the exact default AND
        # stdout is not a real tty — but in practice
        # shutil.get_terminal_size already handles this, so we just
        # store whatever it returns.  The fallback params exist for
        # future use (e.g., headless testing).
        self._columns: int = cols if cols > 0 else fallback_columns
        self._rows: int = rows if rows > 0 else fallback_rows
        self._resize_pending: bool = False
        self._callbacks: list[ResizeCallback] = []
        self._prev_handler: signal.Handlers | Callable[..., object] | None = (
            None
        )
        self._installed: bool = False

        _logger.debug(
            "ResizeHandler created: terminal=%dx%d, SIGWINCH=%s",
            self._columns,
            self._rows,
            "available" if _HAS_SIGWINCH else "unavailable",
        )

    @property
    def columns(self) -> int:
        """Last known terminal width in columns."""
        return self._columns

    @property
    def rows(self) -> int:
        """Last known terminal height in rows."""
        return self._rows

    @property
    def size(self) -> tuple[int, int]:
        """Last known terminal size as ``(columns, rows)``."""
        return (self._columns, self._rows)

    @property
    def resize_pending(self) -> bool:
        """Whether a resize has been detected but not yet consumed."""
        return self._resize_pending

    @property
    def installed(self) -> bool:
        """Whether the SIGWINCH handler is currently installed."""
        return self._installed

    def add_callback(self, callback: ResizeCallback) -> None:
        """Register a callback to be fired on terminal resize.

        Callbacks receive ``(columns, rows)`` as positional arguments
        and are called synchronously inside :meth:`consume`.

        Args:
            callback: A callable accepting two ints (columns, rows).

        Raises:
            TypeError: If *callback* is not callable.
        """
        if not callable(callback):
            raise TypeError(
                f"callback must be callable, got {type(callback).__name__}"
            )
        self._callbacks.append(callback)
        _logger.debug("Resize callback added: %r", callback)

    def remove_callback(self, callback: ResizeCallback) -> None:
        """Remove a previously registered resize callback.

        Args:
            callback: The callback to remove.

        Raises:
            ValueError: If *callback* was not registered.
        """
        try:
            self._callbacks.remove(callback)
        except ValueError:
            raise ValueError(
                f"callback {callback!r} is not registered"
            ) from None
        _logger.debug("Resize callback removed: %r", callback)

    def install(self) -> None:
        """Install the SIGWINCH signal handler (Unix only).

        On platforms without ``SIGWINCH`` (Windows), this method is a
        no-op — resize detection relies on :meth:`poll` instead.

        If called from a non-main thread, the signal handler cannot
        be installed (Python limitation).  A warning is logged and
        the handler falls back to poll-only mode.

        Calling ``install()`` when already installed is a no-op.
        """
        if self._installed:
            _logger.debug("ResizeHandler.install() called while already installed")
            return

        if not _HAS_SIGWINCH:
            _logger.debug(
                "SIGWINCH not available on this platform; "
                "resize detection requires polling"
            )
            return

        try:
            self._prev_handler = signal.getsignal(signal.SIGWINCH)
            signal.signal(signal.SIGWINCH, self._sigwinch_handler)
            self._installed = True
            _logger.debug("SIGWINCH handler installed")
        except ValueError:
            # signal.signal() raises ValueError if called from a
            # non-main thread.  Fall back to poll-only mode.
            _logger.warning(
                "Cannot install SIGWINCH handler from non-main thread; "
                "falling back to poll-only resize detection"
            )

    def uninstall(self) -> None:
        """Remove the SIGWINCH handler and restore the previous one.

        Calling ``uninstall()`` when not installed is a no-op.
        """
        if not self._installed:
            return

        if _HAS_SIGWINCH:
            try:
                if self._prev_handler is not None:
                    signal.signal(signal.SIGWINCH, self._prev_handler)
                else:
                    signal.signal(signal.SIGWINCH, signal.SIG_DFL)
                _logger.debug("SIGWINCH handler uninstalled, previous restored")
            except (ValueError, OSError):
                # Best-effort restoration.  If we can't restore (e.g.,
                # called from wrong thread), log and move on.
                _logger.warning("Could not restore previous SIGWINCH handler")

        self._installed = False
        self._prev_handler = None

    def poll(self) -> None:
        """Check the current terminal size and flag a resize if changed.

        This is the primary resize-detection mechanism on Windows and
        a supplementary check on Unix (where ``SIGWINCH`` provides
        immediate notification).  Calling ``poll()`` each tick ensures
        resize detection works on all platforms.

        If the terminal size has changed since the last check, the
        pending flag is set and the stored size is updated.
        """
        cols, rows = get_terminal_size()
        if cols != self._columns or rows != self._rows:
            _logger.debug(
                "Terminal resize detected via poll: %dx%d -> %dx%d",
                self._columns,
                self._rows,
                cols,
                rows,
            )
            self._columns = cols
            self._rows = rows
            self._resize_pending = True

    def consume(self) -> bool:
        """Clear the resize-pending flag and fire callbacks.

        Returns:
            ``True`` if a resize was pending (and callbacks were fired),
            ``False`` otherwise.

        Caveats:
            - Callbacks are fired in registration order.  If a callback
              raises an exception, subsequent callbacks are skipped.
              The pending flag is still cleared.
            - This method should be called from the main game-loop
              thread to ensure consistent state.
        """
        if not self._resize_pending:
            return False

        self._resize_pending = False
        cols, rows = self._columns, self._rows
        _logger.debug(
            "Consuming resize event: %dx%d (%d callbacks)",
            cols,
            rows,
            len(self._callbacks),
        )

        for cb in self._callbacks:
            cb(cols, rows)

        return True

    def _sigwinch_handler(self, signum: int, frame: object) -> None:
        """Signal handler for SIGWINCH.

        Sets the resize-pending flag and updates the stored terminal
        size.  The actual callback dispatch happens in :meth:`consume`,
        not here — signal handlers should do minimal work.
        """
        cols, rows = get_terminal_size()
        _logger.debug(
            "SIGWINCH received: %dx%d -> %dx%d",
            self._columns,
            self._rows,
            cols,
            rows,
        )
        self._columns = cols
        self._rows = rows
        self._resize_pending = True
