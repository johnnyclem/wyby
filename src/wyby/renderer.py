"""Rich Console and Live display integration for terminal output.

This module provides the display layer that connects wyby's game loop
to Rich's terminal rendering capabilities.  It wraps Rich's
:class:`~rich.console.Console` and :class:`~rich.live.Live` objects
with game-appropriate configuration and lifecycle management.

The three main exports are:

- :func:`create_console` — factory function that creates a Rich
  ``Console`` with sensible defaults for game rendering (Rich markup
  disabled, syntax highlighting disabled, auto-detected terminal size).
- :class:`LiveDisplay` — lifecycle manager for Rich ``Live`` that
  provides start/stop/update semantics with ``auto_refresh`` disabled
  so the game loop controls frame timing.
- :class:`Renderer` — high-level rendering coordinator that wraps
  :class:`LiveDisplay` and provides a game-loop-friendly API for
  pushing frames to the terminal.  This is the primary interface
  that the :class:`~wyby.app.Engine` tick loop uses for output.

Game code can use :class:`Renderer` directly, or drop down to
:class:`LiveDisplay` and :func:`create_console` for custom rendering.

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

from wyby.render_warnings import log_render_cost

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


class Renderer:
    """High-level rendering coordinator that wraps :class:`LiveDisplay`.

    ``Renderer`` is the primary interface between the game loop and the
    terminal.  It owns a :class:`LiveDisplay` (and by extension a Rich
    :class:`~rich.console.Console`) and provides a :meth:`present`
    method for pushing renderables to the screen each tick.

    Typical usage from the engine's tick loop::

        renderer = Renderer(console)
        renderer.start()
        try:
            # Each tick:
            renderable = scene.render()
            renderer.present(renderable)
        finally:
            renderer.stop()

    Or as a context manager::

        with Renderer(console) as renderer:
            renderer.present(Text("Frame 1"))
            renderer.present(Text("Frame 2"))

    Args:
        console: A :class:`rich.console.Console` to render to.  If
            ``None``, a new Console is created via :func:`create_console`
            with default (auto-detected) settings.

    Raises:
        TypeError: If *console* is not a :class:`~rich.console.Console`
            instance or ``None``.

    Caveats:
        - Rich's ``Live`` display is **not** double-buffered.  Each
          :meth:`present` call triggers a full re-render of the
          renderable to the terminal.  There is no differential update
          or dirty-region tracking — the entire renderable is serialised
          to ANSI escape sequences and written to stdout on every frame.
        - **Flicker** is possible on terminals with slow rendering
          (notably Windows ``cmd.exe``, older ``conhost``, or terminals
          over high-latency SSH connections).  Modern terminals (iTerm2,
          WezTerm, Windows Terminal, kitty) handle rapid full-screen
          writes well, but flicker-free rendering is not guaranteed.
        - **CPU cost scales with renderable complexity.**  A large grid
          (e.g., 120x40) of individually styled cells is measurably more
          expensive than a plain text block.  Profile with
          :class:`~wyby.diagnostics.FPSCounter` to measure actual
          throughput in your environment.
        - **Frame rate is terminal-dependent.**  15–30 FPS is realistic
          on most modern terminals.  60 FPS is not a meaningful target
          for terminal output — the terminal emulator's own rendering
          pipeline (text shaping, GPU upload, compositing) is the
          bottleneck, not wyby.
        - ``present()`` is **synchronous** — it blocks until the
          terminal write completes.  On slow terminals or over SSH,
          this is the main source of frame-rate limitation.
        - **Cursor is hidden** while the renderer is started.  If the
          process is killed by ``SIGKILL`` between ``start()`` and
          ``stop()``, the cursor will remain hidden.  Run ``tput cnorm``
          or ``reset`` in the terminal to recover.
        - The renderer does **not** manage the alternate screen buffer.
          Use :class:`~wyby.alt_screen.AltScreen` as an outer context
          manager to enter/exit the alt screen.  This separation allows
          crash recovery to restore the terminal even if the renderer
          fails to stop cleanly.
        - **Do not call** ``console.print()`` while the renderer is
          started.  Rich's ``Live`` conflicts with direct console
          writes, causing display corruption (interleaved output,
          phantom lines, broken cursor positioning).  Use logging
          (to stderr or a file) for debug output during gameplay.
        - ``present()`` when not started is a silent no-op, allowing
          game code to call it unconditionally without checking
          :attr:`is_started`.
        - ``stop()`` is idempotent — safe to call multiple times or
          when never started.
        - Terminal character cells have an approximately **1:2 aspect
          ratio** (taller than wide).  The renderer does not apply any
          aspect-ratio correction — a 10x10 cell grid will appear as a
          tall rectangle on screen.  Games must account for cell shape
          in their rendering logic.
    """

    __slots__ = ("_live_display", "_frame_count")

    def __init__(self, console: Console | None = None) -> None:
        if console is not None and not isinstance(console, Console):
            raise TypeError(
                f"console must be a rich.console.Console or None, "
                f"got {type(console).__name__}"
            )
        # The LiveDisplay validates the console and creates a default
        # one if None is passed, so we delegate directly.
        self._live_display = LiveDisplay(console=console)
        self._frame_count: int = 0

    @property
    def console(self) -> Console:
        """The Rich Console used for terminal output.

        Caveats:
            - Do not call ``console.print()`` while the renderer is
              started — it will corrupt the Live display output.
        """
        return self._live_display.console

    @property
    def live_display(self) -> LiveDisplay:
        """The underlying :class:`LiveDisplay`.

        Exposed for advanced use cases (e.g., passing to the engine
        for shutdown management).  Prefer using :meth:`present` over
        calling ``live_display.update()`` directly.
        """
        return self._live_display

    @property
    def is_started(self) -> bool:
        """Whether the renderer is currently active and accepting frames."""
        return self._live_display.is_started

    @property
    def frame_count(self) -> int:
        """Number of frames presented since the last :meth:`start`.

        Reset to 0 on each ``start()`` call.  Not incremented by
        ``present()`` calls made while the renderer is stopped (those
        are no-ops).
        """
        return self._frame_count

    def start(self) -> None:
        """Start the renderer and prepare for frame output.

        Starts the underlying :class:`LiveDisplay`, which hides the
        terminal cursor and prepares Rich's ``Live`` context for
        receiving frame updates via :meth:`present`.

        Resets :attr:`frame_count` to 0.  Calling ``start()`` when
        already started is a no-op (the frame count is **not** reset).

        Caveats:
            - Writes cursor-hiding escape sequences to the terminal
              immediately.  If stdout is not a TTY, Rich handles this
              gracefully (no-op).
            - The alternate screen buffer is **not** entered.  Use
              :class:`~wyby.alt_screen.AltScreen` separately.
        """
        if self._live_display.is_started:
            _logger.debug(
                "Renderer.start() called while already started, ignoring"
            )
            return
        self._frame_count = 0
        self._live_display.start()

        # Log a flicker/latency warning if the console dimensions
        # suggest heavy rendering.  This runs once at start, not per
        # frame, to avoid log spam.  The warning is advisory — the
        # renderer does not refuse to start for large grids.
        console = self._live_display.console
        log_render_cost(console.width, console.height)

        _logger.debug("Renderer started")

    def stop(self) -> None:
        """Stop the renderer and restore terminal state.

        Stops the underlying :class:`LiveDisplay`, which restores
        cursor visibility.  The last frame remains visible on the
        terminal (``transient=False`` on the underlying ``Live``).

        Idempotent — safe to call multiple times or when not started.
        """
        self._live_display.stop()
        _logger.debug("Renderer stopped")

    def clear_buffer(self) -> None:
        """Clear the terminal display by pushing an empty frame.

        Replaces the currently displayed content with an empty string,
        effectively blanking the renderer's output area.  This is useful
        for scene transitions, fade-to-black effects, or resetting the
        display before a new sequence of :meth:`present` calls.

        Does **not** affect the :attr:`frame_count` — clearing is not
        considered a "frame" in the game-loop sense.

        Caveats:
            - No-op if the renderer is not started.  Does not raise.
            - This clears only the Rich ``Live`` display region.  It does
              **not** clear the entire terminal screen.  Content above or
              below the ``Live`` region (e.g., scrollback, shell prompt)
              is unaffected.  Use :class:`~wyby.alt_screen.AltScreen` for
              full-screen management.
            - This does **not** clear a :class:`~wyby.grid.CellBuffer`.
              If the game uses a ``CellBuffer``, call
              :meth:`CellBuffer.clear() <wyby.grid.CellBuffer.clear>`
              separately to reset the cell data.  ``clear_buffer`` only
              affects what is currently visible on the terminal.
            - The clear is synchronous — it blocks until the terminal
              write completes, just like :meth:`present`.
            - Calling ``clear_buffer()`` followed immediately by
              ``present()`` in the same tick is redundant — ``present()``
              will overwrite the blank frame.  Use ``clear_buffer()`` when
              you want the blank state to be visible for at least one
              frame (e.g., between scenes).
        """
        if not self._live_display.is_started:
            return
        self._live_display.update("")

    def present(self, renderable: RenderableType) -> None:
        """Push a renderable to the terminal as the current frame.

        Replaces the currently displayed content and immediately
        triggers a full re-render to the terminal.  This is the
        method that the game loop calls once per tick after the
        active scene has prepared its visual output.

        Args:
            renderable: Any Rich renderable — :class:`~rich.text.Text`,
                :class:`~rich.table.Table`, :class:`~rich.panel.Panel`,
                a plain string, or any object implementing
                ``__rich__()`` or ``__rich_console__()``.

        Caveats:
            - No-op if the renderer is not started.  Does not raise.
            - Each call triggers a **full** re-render.  For complex
              renderables (large styled grids), this is the main
              performance bottleneck.
            - The write is synchronous — ``present()`` blocks until
              the terminal write completes.
            - There is no frame batching or coalescing.  If
              ``present()`` is called multiple times per tick, each
              call writes to the terminal independently.  The game
              loop should call ``present()`` exactly once per tick.
            - For large or heavily styled grids, flicker and latency
              are likely — especially on slow terminals, over SSH, or
              inside tmux/screen.  Use
              :func:`~wyby.render_warnings.estimate_render_cost` to
              check cost at startup and
              :class:`~wyby.diagnostics.FPSCounter` to measure actual
              throughput at runtime.  See
              ``docs/rendering_performance.md`` for mitigation advice.
        """
        if not self._live_display.is_started:
            return
        self._live_display.update(renderable)
        self._frame_count += 1

    def __enter__(self) -> Renderer:
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
            f"Renderer(started={self.is_started}, "
            f"frame_count={self._frame_count}, "
            f"console={self.console!r})"
        )
