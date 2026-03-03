"""Rich Console and Live display integration for terminal output.

This module provides the display layer that connects wyby's game loop
to Rich's terminal rendering capabilities.  It wraps Rich's
:class:`~rich.console.Console` and :class:`~rich.live.Live` objects
with game-appropriate configuration and lifecycle management.

The two main exports are:

- :func:`create_console` — factory function that creates a Rich
  ``Console`` with sensible defaults for game rendering (Rich markup
  disabled, syntax highlighting disabled, auto-detected terminal size).
- :class:`LiveDisplay` — lifecycle manager for Rich ``Live`` that
  provides start/stop/update semantics with ``auto_refresh`` disabled
  so the game loop controls frame timing.

These components form the output foundation that the higher-level
Renderer class will build upon.  Game code can also use them directly
for custom rendering.

Caveats:
    - Rich's ``Live`` display is **not** a double-buffered graphics
      surface.  It re-renders the full renderable on each ``update()``
      call.  Flicker is possible, especially on terminals with slow
      rendering or on Windows ``cmd.exe``.
    - CPU cost scales with frame complexity.  A 120x40 grid of
      individually styled cells is measurably more expensive than a
      plain text block.  Profile with :class:`~wyby.diagnostics.FPSCounter`
      to measure actual throughput in your environment.
    - ``auto_refresh`` is disabled on the underlying ``Live`` object.
      The game loop (or game code) controls exactly when frames are
      pushed to the terminal by calling :meth:`LiveDisplay.update`.
      Rich's background refresh thread is not used.
    - Rich's ``Live.screen`` mode (which manages an alternate screen
      buffer internally) is disabled.  wyby manages the alternate
      screen buffer separately via :mod:`wyby.alt_screen`, giving
      finer control over terminal state restoration on crashes.
    - Console ``width`` and ``height`` can be overridden for testing,
      but in production they should be left as ``None`` to let Rich
      auto-detect the terminal's actual dimensions.  Overriding them
      does **not** resize the terminal — it only affects how Rich
      lays out content.
    - ``force_terminal=True`` bypasses Rich's TTY detection.  This is
      useful for testing (with ``io.StringIO`` as the output stream)
      but should not be set in production — it causes ANSI escape
      sequences to be written even to pipes and files.
"""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING

from rich.console import Console
from rich.live import Live

if TYPE_CHECKING:
    from rich.console import RenderableType

_logger = logging.getLogger(__name__)


def create_console(
    *,
    file: object | None = None,
    force_terminal: bool | None = None,
    width: int | None = None,
    height: int | None = None,
    color_system: str | None = "auto",
) -> Console:
    """Create a Rich Console configured for wyby game output.

    Returns a :class:`rich.console.Console` with game-appropriate
    defaults: syntax highlighting disabled (game output is not code),
    Rich markup disabled (prevents game text like ``[red]`` from being
    interpreted as style tags), and auto-detected terminal size.

    Args:
        file: Writable file-like object for console output.  Defaults
            to ``sys.stdout``.  Pass ``io.StringIO()`` for testing.
        force_terminal: Override Rich's terminal detection.  ``None``
            (default) auto-detects.  ``True`` forces terminal mode
            (useful for testing with ``StringIO``).  ``False`` forces
            non-terminal mode (disables styling).
        width: Override detected terminal width in columns.  ``None``
            (default) uses the actual terminal width.  Overriding does
            **not** resize the terminal.
        height: Override detected terminal height in rows.  ``None``
            (default) uses the actual terminal height.
        color_system: Color system to use.  ``"auto"`` (default)
            detects terminal capability.  Other values: ``"standard"``
            (8 colors), ``"256"``, ``"truecolor"``, or ``None``
            (no color output).

    Returns:
        A configured :class:`rich.console.Console` instance.

    Caveats:
        - Console creation does **not** write anything to the
          terminal.  It only detects capabilities.  Writing happens
          when ``print()``, ``Live``, or other Rich operations use
          the console.
        - ``force_terminal=True`` with ``file=StringIO()`` is the
          recommended pattern for unit tests.  This gives you a real
          Console that formats output (with ANSI escape sequences)
          but writes to a buffer instead of the terminal.
        - Terminal size detection reads ``$COLUMNS`` / ``$LINES``
          environment variables, then falls back to
          ``os.get_terminal_size()``.  In non-TTY contexts (CI, pipes),
          Rich defaults to 80 columns.
        - ``color_system="auto"`` checks ``$COLORTERM``, ``$TERM``,
          and terminal-specific environment variables.  The detected
          system may differ between terminals even on the same machine.
    """
    console = Console(
        file=file if file is not None else sys.stdout,
        force_terminal=force_terminal,
        width=width,
        height=height,
        color_system=color_system,
        # Disable syntax highlighting — game output is not source code.
        highlight=False,
        # Disable Rich markup so that game text containing brackets
        # (e.g., "[red]" in a chat message or "[3]" as a game label)
        # is rendered literally instead of being interpreted as style
        # tags.
        markup=False,
    )
    _logger.debug(
        "Console created: size=%dx%d, color_system=%s, is_terminal=%s",
        console.width,
        console.height,
        console.color_system,
        console.is_terminal,
    )
    return console


class LiveDisplay:
    """Manages a Rich ``Live`` display for pushing game frames to the terminal.

    Wraps :class:`rich.live.Live` with game-appropriate configuration:
    ``auto_refresh`` is disabled (the game loop controls when frames
    are pushed), ``screen`` mode is disabled (wyby manages the
    alternate screen buffer separately), and ``redirect_stdout`` /
    ``redirect_stderr`` are disabled (game code controls its own I/O).

    Use as a context manager::

        display = LiveDisplay(console)
        with display:
            display.update(Text("Frame 1"))
            display.update(Text("Frame 2"))

    Or manage the lifecycle manually::

        display = LiveDisplay(console)
        display.start()
        try:
            display.update(Text("Frame 1"))
        finally:
            display.stop()

    Args:
        console: A :class:`rich.console.Console` to render to.
            If ``None``, a new Console is created via
            :func:`create_console` with default settings.

    Raises:
        TypeError: If *console* is not a :class:`Console` instance
            or ``None``.

    Caveats:
        - ``auto_refresh`` is ``False``.  Nothing appears on screen
          until :meth:`update` is called.  If you create a LiveDisplay
          and never call ``update()``, the terminal shows nothing.
        - Each :meth:`update` call triggers an **immediate** full
          re-render of the renderable to the terminal.  There is no
          frame buffering or batching.  For a 30 tps game loop, this
          means ~30 full renders per second.
        - ``start()`` writes cursor-hiding escape sequences to the
          terminal.  ``stop()`` restores cursor visibility.  If the
          process is killed between start and stop (e.g., ``SIGKILL``),
          the cursor may remain hidden.  Use ``tput cnorm`` or
          ``reset`` to recover.
        - ``screen=False`` on the underlying ``Live``.  wyby manages
          the alternate screen buffer via :class:`wyby.AltScreen`
          rather than delegating to Rich, because ``AltScreen``
          handles crash recovery and is shared with other subsystems.
        - ``redirect_stdout`` and ``redirect_stderr`` are ``False``.
          Any ``print()`` calls during a Live session will interfere
          with the display.  Use logging (to stderr or a file) instead
          of ``print()`` for debug output during gameplay.
        - Calling ``update()`` when the display is not started is a
          silent no-op.  This allows game code to update the display
          unconditionally without checking :attr:`is_started`.
        - ``stop()`` is idempotent.  Calling it multiple times (or
          calling it when never started) is safe.
    """

    __slots__ = ("_console", "_live", "_started")

    def __init__(self, console: Console | None = None) -> None:
        if console is not None and not isinstance(console, Console):
            raise TypeError(
                f"console must be a rich.console.Console or None, "
                f"got {type(console).__name__}"
            )
        self._console: Console = (
            console if console is not None else create_console()
        )
        self._live: Live | None = None
        self._started: bool = False

    @property
    def is_started(self) -> bool:
        """Whether the Live display is currently active."""
        return self._started

    @property
    def console(self) -> Console:
        """The Rich Console used for rendering."""
        return self._console

    def start(self) -> None:
        """Start the Live display.

        Creates and starts the underlying :class:`rich.live.Live`
        context.  Hides the terminal cursor and prepares for frame
        updates via :meth:`update`.

        Calling ``start()`` when already started is a no-op (logged
        at DEBUG level).

        Caveats:
            - Writes cursor-hiding escape sequences to the terminal
              immediately.  If stdout is not a TTY, Rich handles
              this gracefully (no-op).
        """
        if self._started:
            _logger.debug(
                "LiveDisplay.start() called while already started, "
                "ignoring"
            )
            return

        # auto_refresh=False: the game loop calls update() to push
        # frames.  Rich's background refresh thread is not started.
        # screen=False: we manage alt-screen via wyby.alt_screen.
        # transient=False: keep the last frame visible after stop().
        # redirect_stdout/stderr=False: game code manages its own I/O.
        # vertical_overflow="crop": content taller than the terminal
        # is clipped rather than scrolling (important for game grids).
        live = Live(
            console=self._console,
            auto_refresh=False,
            screen=False,
            transient=False,
            redirect_stdout=False,
            redirect_stderr=False,
            vertical_overflow="crop",
        )
        live.start()
        self._live = live
        self._started = True
        _logger.debug("LiveDisplay started")

    def stop(self) -> None:
        """Stop the Live display and restore the terminal cursor.

        Idempotent — safe to call multiple times or when not started.
        If the underlying ``Live.stop()`` raises (e.g., broken pipe
        during shutdown), the error is logged and the display is
        marked as stopped regardless.
        """
        if not self._started:
            return

        if self._live is not None:
            try:
                self._live.stop()
            except Exception:
                _logger.warning(
                    "Error stopping Live display", exc_info=True
                )
            self._live = None

        self._started = False
        _logger.debug("LiveDisplay stopped")

    def update(self, renderable: RenderableType) -> None:
        """Push a new renderable to the terminal.

        Replaces the currently displayed content with *renderable*
        and immediately triggers a refresh (re-render and write to
        terminal).

        Args:
            renderable: Any Rich renderable — :class:`~rich.text.Text`,
                :class:`~rich.table.Table`, :class:`~rich.panel.Panel`,
                a plain string, or any object implementing
                ``__rich__()`` or ``__rich_console__()``.

        Caveats:
            - No-op if the display is not started.  Does not raise.
            - Each call triggers a full re-render.  For complex
              renderables (large grids with per-cell styling), this
              is the main performance bottleneck.  Profile with
              :class:`~wyby.diagnostics.FPSCounter` to measure actual
              throughput.
            - The refresh is synchronous — ``update()`` blocks until
              the terminal write completes.  On slow terminals or
              over SSH, this can limit frame rate.
        """
        if self._live is None:
            return
        self._live.update(renderable, refresh=True)

    def __enter__(self) -> LiveDisplay:
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object | None,
    ) -> None:
        self.stop()

    def __repr__(self) -> str:
        return (
            f"LiveDisplay(started={self._started}, "
            f"console={self._console!r})"
        )
