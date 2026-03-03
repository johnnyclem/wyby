"""Application entry point and game loop.

This module provides the main :class:`Engine` class that drives the
fixed-timestep game loop: drain input -> update active scene -> render
frame.

The loop uses a classic **accumulator pattern**: wall-clock time is
measured via ``time.monotonic()`` and fed into an accumulator.  The
accumulator is drained in fixed increments of ``target_dt`` (``1/tps``),
so game logic always sees the same fixed delta regardless of how fast or
slow the host machine renders frames.  When the loop finishes early it
sleeps the remainder; when it falls behind it runs multiple updates per
frame (up to a frame-skip limit) to catch up.

Quit handling:
    The engine recognises three ways to request shutdown:

    1. **KeyboardInterrupt** (Ctrl+C) — caught by the engine and
       treated as a clean stop.
    2. **Engine.stop()** — called programmatically (e.g., from another
       thread or a timer callback).
    3. **QuitSignal** — a dedicated exception that game code (typically
       a :class:`Scene` subclass) can raise from ``update()`` to
       request an immediate, clean shutdown.  This is the recommended
       way for scenes to quit the game without needing a reference to
       the engine.

    Once the input layer is implemented, the engine will raise
    ``QuitSignal`` automatically when configurable quit keys (e.g.,
    Escape, ``q``) are pressed.  Until then, games should raise
    ``QuitSignal`` from their own input-checking logic.

Graceful shutdown:
    Regardless of *how* the engine stops — ``stop()``, Ctrl+C,
    ``QuitSignal``, or an unhandled exception from game code — the
    engine performs a cleanup pass before ``run()`` returns:

    1. **Scene stack teardown** — every scene on the stack receives its
       ``on_exit()`` hook (and registered exit callbacks) in top-to-
       bottom order.  If an exit hook raises, the exception is logged
       and remaining scenes still receive their hooks.
    2. **Event queue flush** — pending events are discarded so stale
       input does not leak into a subsequent ``run()`` call.

    For expected exits (``stop()``, ``KeyboardInterrupt``,
    ``QuitSignal``), ``run()`` returns normally.  For unexpected
    exceptions from game code, cleanup still runs but the exception
    re-raises after ``run()`` returns, so callers can observe it.

    Caveats:
        - Exit hooks run inside the ``finally`` block of ``run()``.
          If a scene's ``on_exit()`` raises, the exception is logged at
          WARNING level and swallowed so that subsequent scenes are not
          deprived of their cleanup.  This means bugs in exit hooks are
          *silent* unless logging is configured.
        - The engine does **not** manage terminal state (alt-screen
          buffer, cursor visibility).  Use :class:`AltScreen` as an
          outer context manager to ensure the terminal is restored even
          if the engine raises.
        - If the engine is shut down by ``SIGKILL`` (``kill -9``),
          neither ``_shutdown()`` nor ``__exit__`` will run.  This is
          a fundamental OS limitation — ``SIGKILL`` cannot be caught.

Caveats:
    - **Early implementation.** The scene stack and event queue are
      wired into the main loop, but the input layer (keyboard polling)
      and renderer (Rich ``Live`` display) are not yet connected.
    - The game loop targets ~30 ticks per second by default, but actual
      frame rate depends on terminal emulator, grid size, and style
      complexity. Do not assume 60 FPS — that is not a meaningful target
      for terminal output.
    - Rich's ``Live`` display re-renders the full renderable each frame.
      CPU cost scales with frame complexity, and flicker is possible on
      slow terminals (especially Windows ``cmd.exe``).
    - The ``width`` and ``height`` parameters define the logical grid size
      in character cells, **not** pixels. Terminal cells are typically
      ~1:2 aspect ratio (taller than wide), so a "square" grid will
      appear as a tall rectangle. There is no automatic aspect-ratio
      correction — the game is responsible for accounting for cell shape.
    - Grid dimensions are not clamped to the actual terminal size. If
      ``width`` or ``height`` exceeds the terminal's columns or rows, the
      output will wrap or be clipped depending on the terminal emulator.
      Terminal resize detection is an open design question (see SCOPE.md).
    - **Sleep granularity.** ``time.sleep()`` accuracy is OS-dependent
      (typically 1–10 ms).  The accumulator pattern self-corrects for
      overshoot on the next frame, so the loop stays accurate on average
      even though individual sleeps may be imprecise.
    - **Suspend/resume.** If the OS suspends the process (laptop lid
      close, ``SIGSTOP``, debugger breakpoint), the first frame after
      wake will see a large wall-clock gap.  The engine clamps this gap
      to ``_DT_CLAMP`` seconds to prevent a burst of catch-up updates.
    - The engine does not provide networking, audio, or GPU acceleration.
      These are explicitly out of scope for wyby v0.1.
"""

from __future__ import annotations

import dataclasses
import logging
import time
from typing import TYPE_CHECKING

from wyby._logging import configure_logging
from wyby.diagnostics import FPSCounter
from wyby.event import EventQueue
from wyby.renderer import LiveDisplay, create_console
from wyby.scene import SceneStack

if TYPE_CHECKING:
    from rich.console import Console

_logger = logging.getLogger(__name__)

# Minimum grid dimensions. A 1x1 grid is technically valid but useless
# for any real game. We enforce a floor of 1 to prevent nonsensical
# zero or negative sizes, but practical games will need much larger grids.
_MIN_WIDTH = 1
_MIN_HEIGHT = 1

# Sensible upper bound to guard against accidental huge allocations.
# A 1000x1000 grid of styled cells would be extremely expensive to
# render via Rich's Live display — likely single-digit FPS even on a
# fast terminal. This limit can be raised if a concrete use case demands
# it, but exceeding it almost certainly indicates a bug.
_MAX_WIDTH = 1000
_MAX_HEIGHT = 1000

_DEFAULT_TITLE = "wyby"
_DEFAULT_WIDTH = 80
_DEFAULT_HEIGHT = 24

# Default ticks per second.  30 tps (~33 ms per tick) is a reasonable
# baseline for terminal games — fast enough for smooth animation, slow
# enough that Rich can keep up on most terminals.
_DEFAULT_TPS = 30

# TPS range.  1 tps is a valid (if glacial) tick rate for turn-based
# games that still want a heartbeat.  240 tps is well beyond what any
# terminal can render but may be useful for headless simulation.
_MIN_TPS = 1
_MAX_TPS = 240

# Maximum allowed wall-clock frame time before clamping (seconds).
# A gap larger than this almost certainly means the process was
# suspended externally (laptop lid, debugger, SIGSTOP).  Trying to
# catch up with 10+ seconds of accumulated time would cause a burst
# of rapid updates and potentially make things worse ("spiral of
# death").  250 ms ≈ 4 effective FPS — a generous but safe cap.
_DT_CLAMP = 0.25

# Maximum number of fixed-step updates per outer frame.  Prevents the
# spiral of death where each catch-up tick takes longer than target_dt,
# causing the accumulator to grow without bound.  When the limit is
# reached, remaining accumulated time is dropped and the simulation
# accepts that it has fallen behind wall-clock time.
_MAX_FRAME_SKIP = 5

# Don't bother sleeping for less than this (seconds).  OS sleep
# granularity is typically 1–10 ms; sleeping for less than 1 ms is
# unreliable and may actually sleep longer than intended.
_SLEEP_THRESHOLD = 0.001


def _validate_title(title: object) -> str:
    """Validate and return the title, or raise TypeError/ValueError."""
    if not isinstance(title, str):
        raise TypeError(
            f"title must be a str, got {type(title).__name__}"
        )
    if not title.strip():
        raise ValueError("title must not be empty or blank")
    return title


def _validate_int_field(
    name: str, value: object, min_val: int, max_val: int
) -> int:
    """Validate an integer field with range bounds, or raise."""
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(
            f"{name} must be an int, got {type(value).__name__}"
        )
    if not (min_val <= value <= max_val):
        raise ValueError(
            f"{name} must be between {min_val} and {max_val}, "
            f"got {value}"
        )
    return value


@dataclasses.dataclass(frozen=True, slots=True)
class EngineConfig:
    """Immutable configuration object for :class:`Engine` options.

    Bundles all engine-level settings into a single object that can be
    constructed, inspected, and passed around before the engine is
    created.  Validation runs at construction time via ``__post_init__``,
    so an ``EngineConfig`` instance is always in a valid state.

    Args:
        title: Window/application title. Used for diagnostic output.
            Defaults to ``"wyby"``.
        width: Logical grid width in character cells. Must be between 1
            and 1000 inclusive. Defaults to 80.
        height: Logical grid height in character cells. Must be between 1
            and 1000 inclusive. Defaults to 24.
        tps: Target ticks per second. Must be between 1 and 240
            inclusive. Defaults to 30.
        debug: Enable verbose logging to stderr. Defaults to ``False``.
        show_fps: Enable FPS counter tracking. Defaults to ``False``.

    Caveats:
        - ``EngineConfig`` is **frozen** — fields cannot be reassigned
          after construction.  To change a value, use
          :func:`dataclasses.replace` to create a modified copy.
        - ``width`` and ``height`` describe the logical game grid, not
          the terminal window size.  If the grid exceeds the terminal,
          output will wrap or clip.  Terminal resize detection is
          separate from the config.
        - ``debug`` and ``show_fps`` accept any truthy/falsy value
          (they are coerced to ``bool``), but all other fields are
          strictly type-checked.
    """

    title: str = _DEFAULT_TITLE
    width: int = _DEFAULT_WIDTH
    height: int = _DEFAULT_HEIGHT
    tps: int = _DEFAULT_TPS
    debug: bool = False
    show_fps: bool = False

    def __post_init__(self) -> None:
        _validate_title(self.title)
        _validate_int_field("width", self.width, _MIN_WIDTH, _MAX_WIDTH)
        _validate_int_field("height", self.height, _MIN_HEIGHT, _MAX_HEIGHT)
        _validate_int_field("tps", self.tps, _MIN_TPS, _MAX_TPS)
        # Coerce debug and show_fps to strict bool.  Using
        # object.__setattr__ because the dataclass is frozen.
        object.__setattr__(self, "debug", bool(self.debug))
        object.__setattr__(self, "show_fps", bool(self.show_fps))


class QuitSignal(Exception):
    """Raised by game code to request a clean engine shutdown.

    Scenes (or any code running inside the engine's tick) can raise
    this exception to stop the game loop cleanly.  The engine catches
    ``QuitSignal`` the same way it catches ``KeyboardInterrupt`` —
    it sets ``running`` to ``False`` and exits ``run()`` without
    re-raising.

    Example usage in a scene::

        class GameplayScene(Scene):
            def update(self, dt: float) -> None:
                if self.player_pressed_quit:
                    raise QuitSignal("player quit")

    Caveats:
        - ``QuitSignal`` is **not** a ``BaseException`` subclass
          (it inherits from ``Exception``).  Bare ``except:`` blocks
          will catch it, so avoid bare excepts in game code running
          inside the engine tick.  Use ``except Exception`` if you
          must catch broadly, and re-raise ``QuitSignal`` explicitly.
        - The engine does not distinguish between ``QuitSignal`` and
          ``KeyboardInterrupt`` for shutdown behaviour — both result
          in a clean stop.  Future versions may expose the quit reason
          via a callback or property.
        - Once the input layer is implemented, the engine will raise
          ``QuitSignal`` when configurable quit keys (e.g., Escape,
          ``q``) are detected.  Until then, games must raise it
          manually from their input-handling logic.
    """


class Engine:
    """Core engine that manages the game loop and top-level configuration.

    The ``Engine`` holds the game's title, logical grid dimensions, tick
    rate, event queue, and scene stack.  Each tick follows a three-phase
    structure: drain events (input), update the active scene, render the
    active scene.

    Args:
        title: Window/application title. Used for diagnostic output and
            will be passed to the terminal title escape sequence once the
            renderer is implemented. Defaults to ``"wyby"``.
        width: Logical grid width in character cells. Must be between 1
            and 1000 inclusive. Defaults to 80 (standard terminal width).
        height: Logical grid height in character cells. Must be between 1
            and 1000 inclusive. Defaults to 24 (standard terminal height).
        tps: Target ticks per second.  Determines the fixed timestep
            (``target_dt = 1.0 / tps``).  Must be between 1 and 240
            inclusive.  Defaults to 30 (~33 ms per tick).
        debug: When ``True``, automatically configures the ``wyby``
            logger hierarchy to emit ``DEBUG``-level messages to stderr.
            This is a convenience shortcut equivalent to calling
            ``configure_logging(level=logging.DEBUG)`` yourself.
            Defaults to ``False``.
        show_fps: When ``True``, enables an :class:`FPSCounter` that
            tracks wall-clock tick intervals and computes smoothed FPS
            metrics.  Access the counter via :attr:`fps_counter`.
            Defaults to ``False``.

    Raises:
        TypeError: If *title* is not a string, or *width*/*height*/*tps*
            are not integers.
        ValueError: If *title* is empty or blank, or *width*/*height*
            are outside the allowed range (1–1000), or *tps* is outside
            the allowed range (1–240).

    Caveats:
        - ``width`` and ``height`` describe the logical game grid, not
          the terminal window size. The engine does not query or enforce
          terminal dimensions. If the grid exceeds the terminal, output
          will wrap or clip.
        - Terminal cells are not square (~1:2 aspect ratio). A grid of
          80x24 will not appear square on screen.
        - The title is stored but not yet written to the terminal. Once
          the renderer is implemented, it will set the terminal title via
          the ``\\033]0;...\\007`` escape sequence, which is supported by
          most modern terminals but silently ignored by some (notably
          the Linux virtual console).
    """

    __slots__ = (
        "_config",
        "_title",
        "_width",
        "_height",
        "_tps",
        "_target_dt",
        "_debug",
        "_show_fps",
        "_fps_counter",
        "_running",
        "_tick_count",
        "_dt",
        "_elapsed",
        "_last_tick_time",
        "_accumulator",
        "_event_queue",
        "_scene_stack",
        "_console",
        "_live_display",
    )

    def __init__(
        self,
        title: str = _DEFAULT_TITLE,
        width: int = _DEFAULT_WIDTH,
        height: int = _DEFAULT_HEIGHT,
        tps: int = _DEFAULT_TPS,
        debug: bool = False,
        show_fps: bool = False,
        *,
        config: EngineConfig | None = None,
        console: Console | None = None,
    ) -> None:
        if config is not None:
            # When a config object is provided, use its values.
            # Caveat: if both a config and keyword arguments are supplied,
            # the config takes precedence and the keyword arguments are
            # silently ignored.  This avoids ambiguity — callers should
            # use one style or the other, not both.
            if not isinstance(config, EngineConfig):
                raise TypeError(
                    f"config must be an EngineConfig, "
                    f"got {type(config).__name__}"
                )
            self._config = config
        else:
            # Build a config from the individual keyword arguments.
            # EngineConfig.__post_init__ handles all validation.
            self._config = EngineConfig(
                title=title,
                width=width,
                height=height,
                tps=tps,
                debug=debug,
                show_fps=show_fps,
            )

        cfg = self._config
        self._title = cfg.title
        self._width = cfg.width
        self._height = cfg.height
        self._tps = cfg.tps
        self._target_dt = 1.0 / cfg.tps
        self._debug = cfg.debug

        # Caveat: calling configure_logging() is additive — each call adds
        # a new handler. Creating multiple Engine(debug=True) instances will
        # produce duplicate log output. This is a convenience shortcut for
        # the common single-engine case. For multi-engine or advanced setups,
        # call configure_logging() directly before constructing the engine.
        if self._debug:
            configure_logging(level=logging.DEBUG)

        self._show_fps = cfg.show_fps
        # Caveat: the FPS counter tracks wall-clock tick intervals, not
        # actual Rich render throughput (the renderer is not yet connected).
        # Reported FPS includes time spent sleeping between ticks, so at
        # low load it will closely match the target tps. Once the renderer
        # is wired up, a per-render measurement may provide finer detail.
        self._fps_counter: FPSCounter | None = (
            FPSCounter() if self._show_fps else None
        )

        self._running = False
        self._tick_count: int = 0
        self._dt: float = 0.0
        self._elapsed: float = 0.0
        self._last_tick_time: float = 0.0
        self._accumulator: float = 0.0
        self._event_queue = EventQueue()
        self._scene_stack = SceneStack()

        # Rich Console for terminal output.  When not provided, a
        # Console is created with auto-detected terminal settings
        # (size, color capability, TTY detection).  Pass a custom
        # Console for testing or advanced configuration (e.g., forcing
        # a specific color system or writing to a StringIO buffer).
        # Caveat: the Console is shared with the LiveDisplay.  Do not
        # call console.print() directly while the LiveDisplay is
        # started — Rich's Live will conflict with direct writes,
        # causing display corruption.
        self._console = (
            console if console is not None else create_console()
        )
        self._live_display = LiveDisplay(console=self._console)

        _logger.debug(
            "Engine initialized: title=%r, width=%d, height=%d, "
            "tps=%d, show_fps=%s",
            self._title,
            self._width,
            self._height,
            self._tps,
            self._show_fps,
        )

    @property
    def title(self) -> str:
        """The game/application title."""
        return self._title

    @property
    def width(self) -> int:
        """Logical grid width in character cells."""
        return self._width

    @property
    def height(self) -> int:
        """Logical grid height in character cells."""
        return self._height

    @property
    def tps(self) -> int:
        """Target ticks per second."""
        return self._tps

    @property
    def debug(self) -> bool:
        """Whether debug mode is enabled (verbose logging to stderr)."""
        return self._debug

    @property
    def show_fps(self) -> bool:
        """Whether the FPS counter is enabled."""
        return self._show_fps

    @property
    def config(self) -> EngineConfig:
        """The :class:`EngineConfig` snapshot used to initialise this engine.

        Returns a frozen dataclass — fields cannot be mutated.  To create
        a modified config, use ``dataclasses.replace(engine.config, tps=60)``.
        """
        return self._config

    @property
    def fps_counter(self) -> FPSCounter | None:
        """The FPS counter, or ``None`` if ``show_fps`` is ``False``.

        When enabled, the counter tracks wall-clock tick intervals and
        provides smoothed FPS via its :attr:`~FPSCounter.fps` property.

        Caveats:
            - The counter measures tick throughput, not render throughput.
              Until the Rich renderer is connected, FPS reflects the
              engine loop rate (including sleep time), which at low load
              will closely match ``tps``.
            - FPS is inherently variable in terminal environments.
              15–30 FPS is realistic on modern terminals; do not use
              these numbers to promise performance to end users.
        """
        return self._fps_counter

    @property
    def console(self) -> Console:
        """The Rich Console used for terminal output.

        This console is shared with the :attr:`live_display` and
        any future renderer.  It is configured with Rich markup and
        syntax highlighting disabled (appropriate for game output).

        Caveats:
            - Do not call ``console.print()`` directly while the
              :attr:`live_display` is started — Rich's ``Live`` will
              conflict with direct writes, causing display corruption.
              Use ``live_display.update()`` instead.
            - The console's ``width`` and ``height`` reflect the
              terminal size at the time the console was created (or
              the override values if provided).  They do not
              automatically update on terminal resize.
        """
        return self._console

    @property
    def live_display(self) -> LiveDisplay:
        """The :class:`LiveDisplay` for pushing frames to the terminal.

        The display is created during engine initialization but is
        **not** started automatically.  Call ``live_display.start()``
        before pushing renderables, or use it as a context manager.
        The engine's :meth:`_shutdown` method stops the display if
        it was started, ensuring terminal state is restored on exit.

        Caveats:
            - The display is not started by :meth:`run`.  Starting
              and managing the display lifecycle is the responsibility
              of the game code or a higher-level Renderer class.
            - If the display is started, it is stopped during
              :meth:`_shutdown` (which runs on all exit paths from
              :meth:`run`).  This ensures cursor visibility is
              restored even if the game crashes.
        """
        return self._live_display

    @property
    def target_dt(self) -> float:
        """Fixed timestep duration in seconds (``1.0 / tps``).

        This is the time quantum that each tick represents.  Game logic
        should use this (or equivalently :attr:`dt`, which returns the
        same value after a tick) to scale velocities and animations so
        that behaviour is deterministic regardless of wall-clock jitter.
        """
        return self._target_dt

    @property
    def running(self) -> bool:
        """Whether the engine's game loop is currently executing."""
        return self._running

    @property
    def tick_count(self) -> int:
        """Total number of ticks executed since the last ``run()`` call."""
        return self._tick_count

    @property
    def dt(self) -> float:
        """Fixed timestep duration of the most recent tick, in seconds.

        After the first tick completes, this equals :attr:`target_dt`
        (``1.0 / tps``).  Every tick represents the same fixed quantum
        of game time, which keeps physics and game logic deterministic
        regardless of wall-clock frame-rate variation.

        Returns 0.0 before the first tick completes.

        Caveats:
            - This is the *fixed* timestep, not wall-clock elapsed time.
              If you need wall-clock diagnostics, use
              ``time.monotonic()`` directly or the future diagnostics
              module.
            - Machine suspend causes a wall-clock gap, but the
              accumulator in :meth:`run` clamps the catch-up to avoid
              a burst of rapid updates (see ``_DT_CLAMP``).
        """
        return self._dt

    @property
    def elapsed(self) -> float:
        """Cumulative game time spent ticking, in seconds.

        Equal to ``tick_count * target_dt``.  Because each tick adds
        exactly ``target_dt``, this tracks deterministic *game* time,
        not wall-clock time.  Pauses or sleeps between ``run()`` calls
        are not counted.

        Caveats:
            - Accumulated floating-point drift is possible over very
              long sessions (hours).  For a 30-tps game running 10
              hours that's ~1 080 000 additions; IEEE 754 double
              precision keeps ~15 significant digits, so drift stays
              well below 1 ms.  If sub-microsecond accuracy matters
              over marathon sessions, use ``tick_count * target_dt``
              directly.
            - Reset to 0.0 each time ``run()`` is called.
        """
        return self._elapsed

    @property
    def events(self) -> EventQueue:
        """The engine's event queue.

        Subsystems and game code post :class:`Event` instances here.
        The main loop drains the queue once per tick during the input
        phase.
        """
        return self._event_queue

    @property
    def scenes(self) -> SceneStack:
        """The engine's scene stack.

        Push, pop, or replace scenes to control which scene is active.
        Only the top scene receives updates and renders each tick.
        """
        return self._scene_stack

    def run(self, *, loop: bool = True) -> None:
        """Start the engine's main loop.

        When *loop* is ``True`` (the default), the engine runs a
        **fixed-timestep** loop using the accumulator pattern until
        stopped via :meth:`stop`, a ``KeyboardInterrupt`` (Ctrl+C),
        or a :class:`QuitSignal` raised by game code.
        Wall-clock time is accumulated and drained in fixed increments
        of :attr:`target_dt`.  When a frame finishes early the loop
        sleeps the remainder; when it falls behind it runs multiple
        updates (up to ``_MAX_FRAME_SKIP``) to catch up.

        When *loop* is ``False``, the engine executes exactly one tick
        and returns — useful for testing and debugging.

        Args:
            loop: If ``True``, run the game loop until stopped. If
                ``False``, execute a single tick and return.

        Caveats:
            - Each tick runs three phases: drain the event queue
              (input), call the active scene's ``update(dt)`` (update),
              and call the active scene's ``render()`` (render).  The
              input layer and Rich renderer are not yet connected —
              events must be posted manually and ``render()`` output
              is not yet displayed.
            - **Sleep granularity.** ``time.sleep()`` precision is
              OS-dependent (typically 1–10 ms).  The accumulator
              self-corrects for overshoot on the next frame.
            - **Suspend/resume.** If the process is suspended (laptop
              lid, debugger, ``SIGSTOP``), the first frame after wake
              sees a large wall-clock gap.  ``frame_time`` is clamped
              to ``_DT_CLAMP`` to prevent a burst of catch-up ticks.
            - ``KeyboardInterrupt`` and ``QuitSignal`` are both caught
              and treated as a clean shutdown.  Unhandled exceptions
              from game code trigger the same cleanup but re-raise
              after ``run()`` returns.
            - **Graceful shutdown.** On any exit path, the engine
              tears down the scene stack (firing ``on_exit`` hooks
              top-to-bottom) and flushes the event queue.  If a
              scene's exit hook raises, the exception is logged and
              remaining scenes still receive their hooks.
            - Terminal-state cleanup (e.g. restoring cursor
              visibility, alt-screen buffer) is **not** managed by
              the engine.  Wrap ``run()`` in an :class:`AltScreen`
              context manager to ensure the terminal is restored.
            - Calling ``run()`` while the engine is already running has
              no effect; the call returns immediately.
        """
        if self._running:
            _logger.debug("Engine.run() called while already running, ignoring")
            return

        self._running = True
        self._tick_count = 0
        self._dt = 0.0
        self._elapsed = 0.0
        self._accumulator = 0.0
        if self._fps_counter is not None:
            self._fps_counter.reset()
        # time.monotonic() is used rather than time.perf_counter() because
        # monotonic is guaranteed never to go backwards (immune to NTP
        # adjustments and system clock changes).  perf_counter offers
        # higher resolution on some platforms but can theoretically jump
        # on clock adjustment.  For a game loop where correctness matters
        # more than nanosecond precision, monotonic is the safer choice.
        self._last_tick_time = time.monotonic()
        _logger.debug("Engine.run() starting (loop=%s)", loop)

        try:
            if not loop:
                # Single-tick mode: run one fixed-step update and return.
                # No accumulator or sleep — this is for testing/debugging.
                self._tick()
            else:
                self._run_loop()
        except KeyboardInterrupt:
            _logger.debug("KeyboardInterrupt received, stopping engine")
        except QuitSignal:
            _logger.debug("QuitSignal received, stopping engine")
        finally:
            self._shutdown()
            self._running = False
            _logger.debug("Engine.run() finished")

    def _run_loop(self) -> None:
        """Inner fixed-timestep loop (called by :meth:`run`).

        Uses the accumulator pattern:

        1. Measure wall-clock ``frame_time`` since last iteration.
        2. Clamp ``frame_time`` to ``_DT_CLAMP`` (guards against
           suspend/resume or debugger pauses).
        3. Add ``frame_time`` to accumulator.
        4. Drain the accumulator in fixed ``target_dt`` increments,
           running one :meth:`_tick` per increment (up to
           ``_MAX_FRAME_SKIP`` per frame to prevent spiral of death).
        5. Sleep the remaining time to hit the target tick rate.
        """
        while self._running:
            now = time.monotonic()
            frame_time = now - self._last_tick_time
            self._last_tick_time = now

            # Clamp frame_time to prevent spiral of death after OS
            # suspend/resume or debugger breakpoints.  A gap larger
            # than _DT_CLAMP almost certainly means the process was
            # paused externally; trying to catch up would cause a
            # burst of rapid updates.
            if frame_time > _DT_CLAMP:
                _logger.debug(
                    "Clamping frame_time %.4fs -> %.4fs "
                    "(probable suspend/resume or debugger pause)",
                    frame_time,
                    _DT_CLAMP,
                )
                frame_time = _DT_CLAMP

            self._accumulator += frame_time

            # Drain the accumulator in fixed-step increments.
            # Multiple ticks may run in one frame if the previous
            # frame was slow, catching the simulation up to
            # wall-clock time.
            updates = 0
            while (
                self._accumulator >= self._target_dt
                and self._running
            ):
                self._tick()
                self._accumulator -= self._target_dt
                updates += 1
                if updates >= _MAX_FRAME_SKIP:
                    # Cap catch-up to prevent the spiral of death —
                    # if each tick takes longer than target_dt, the
                    # accumulator grows without bound.  Drop the
                    # excess and accept that the simulation has
                    # fallen behind wall-clock time.
                    _logger.debug(
                        "Frame-skip limit reached (%d updates), "
                        "dropping %.4fs of accumulated time",
                        _MAX_FRAME_SKIP,
                        self._accumulator,
                    )
                    self._accumulator = 0.0
                    break

            # Sleep remaining time to avoid busy-waiting.
            # time.sleep() granularity is OS-dependent (typically
            # 1–10 ms), so the actual sleep may overshoot — the
            # accumulator corrects for this on the next frame.
            remaining = self._target_dt - self._accumulator
            if remaining > _SLEEP_THRESHOLD and self._running:
                time.sleep(remaining)

    def stop(self) -> None:
        """Signal the engine to stop after the current tick completes.

        This sets the internal running flag to ``False``. The game loop
        will exit at the end of the current tick. Calling ``stop()`` when
        the engine is not running is a harmless no-op.
        """
        _logger.debug("Engine.stop() called")
        self._running = False

    def _shutdown(self) -> None:
        """Clean up engine state during shutdown.

        Called from the ``finally`` block of :meth:`run`.  Tears down
        the scene stack (firing ``on_exit`` hooks) and flushes the event
        queue so that stale state does not leak into a subsequent
        ``run()`` call.

        Exit hooks are invoked defensively: if a scene's ``on_exit()``
        or a registered exit callback raises, the exception is logged
        and remaining scenes still receive their hooks.

        Caveats:
            - Accesses ``_scene_stack._stack`` directly rather than
              using :meth:`SceneStack.pop` because ``pop()`` calls
              ``on_resume()`` on the new top scene, which is both
              unnecessary during shutdown and could itself raise.
            - If an exit hook raises, the exception is logged at
              WARNING level (not re-raised).  This means bugs in exit
              hooks are silent unless logging is configured — always
              configure logging during development.
            - Safe to call multiple times (idempotent).  A second call
              after a clean shutdown is a no-op since the stack and
              queue are already empty.
        """
        _logger.debug("Engine shutdown: cleaning up")

        # Tear down scenes top-to-bottom.  We bypass SceneStack.pop()
        # and SceneStack.clear() for two reasons:
        # 1. pop() calls on_resume() on the new top, which is
        #    pointless during shutdown and could raise.
        # 2. clear() would propagate the first exception from
        #    _fire_exit(), leaving remaining scenes uncleaned.
        stack = self._scene_stack._stack
        while stack:
            scene = stack.pop()
            try:
                scene._fire_exit()
            except Exception:
                # Log and continue — one buggy exit hook must not
                # prevent other scenes from cleaning up.
                _logger.warning(
                    "Exception in exit hook for %r during shutdown "
                    "(remaining scenes will still be cleaned up)",
                    type(scene).__name__,
                    exc_info=True,
                )

        self._event_queue.clear()

        # Stop the Live display if it was started (by game code or a
        # Renderer).  This restores cursor visibility and cleans up
        # Rich's terminal state.  Idempotent — safe even if the
        # display was never started.
        self._live_display.stop()

        _logger.debug("Engine shutdown complete")

    def _tick(self) -> None:
        """Execute one fixed-timestep update.

        Each call represents exactly :attr:`target_dt` seconds of game
        time, regardless of wall-clock duration.  The accumulator in
        :meth:`_run_loop` handles the mapping between wall-clock time
        and game time.

        The tick follows a strict three-phase structure:

        1. **Input** — drain all pending events from the event queue.
           Events are collected into a list but not automatically
           dispatched to the scene.  The input layer (not yet
           implemented) will post ``KeyEvent`` objects here; for now,
           game code can post custom events via ``engine.events.post()``.
        2. **Update** — call the active (top) scene's ``update(dt)``
           method with the fixed timestep.  If the scene stack is empty,
           this phase is skipped.
        3. **Render** — call the active scene's ``render()`` method.
           If the scene stack is empty, this phase is skipped.

        Caveats:
            - The input phase drains events but does not dispatch them
              to the scene automatically.  Event routing will be added
              when the input subsystem is implemented.  Until then,
              scenes that need input must poll their own state or read
              events from the engine's queue before ``drain()`` is
              called.
            - Update and render are called on the same scene reference
              obtained once per tick.  If ``update()`` mutates the scene
              stack (e.g., pushes a pause menu), the *original* scene
              still renders this tick.  The new top scene will render
              starting next tick.
            - If the scene stack is empty, the tick is effectively a
              no-op (timing bookkeeping still advances).  This is not
              an error — it allows the engine to run with an empty stack
              while waiting for a scene to be pushed.
            - ``render()`` must not modify game state.  It should be a
              pure read of the scene's current state.  The renderer is
              not yet wired to Rich ``Live``; ``render()`` is called to
              establish the contract and allow scenes to prepare output.
        """
        # -- Timing bookkeeping (always runs) --
        self._dt = self._target_dt
        self._elapsed += self._dt
        self._tick_count += 1

        # -- Phase 1: Input --
        # Drain all events posted since the last tick.  The input layer
        # (once implemented) will post KeyEvents here each frame.  For
        # now the queue is typically empty unless game code posts custom
        # events.
        self._event_queue.drain()

        # -- Phase 2: Update --
        # Only the top scene receives updates.  Scenes below it on the
        # stack are paused and do not advance.
        scene = self._scene_stack.peek()
        if scene is not None:
            scene.update(self._target_dt)

        # -- Phase 3: Render --
        # Render the same scene that was updated.  If update() pushed or
        # popped scenes, the new top takes effect next tick — this keeps
        # the three phases consistent within a single tick.
        if scene is not None:
            scene.render()

        # -- FPS tracking --
        # Record the tick timestamp for FPS computation.  This is done
        # after all three phases so that frame_time reflects the full
        # cost of input + update + render (plus any sleep from the
        # outer loop between ticks).
        if self._fps_counter is not None:
            self._fps_counter.tick(time.monotonic())

    def __repr__(self) -> str:
        parts = (
            f"Engine(title={self._title!r}, "
            f"width={self._width!r}, height={self._height!r}, "
            f"tps={self._tps!r}"
        )
        if self._debug:
            parts += ", debug=True"
        if self._show_fps:
            parts += ", show_fps=True"
        return parts + ")"
