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

Caveats:
    - **Early implementation.** Scene management, input, and rendering
      are not yet connected. See SCOPE.md for the intended design.
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

import logging
import time

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


class Engine:
    """Core engine that manages the game loop and top-level configuration.

    The ``Engine`` holds the game's title, logical grid dimensions, and
    tick rate.  Future versions will own the scene stack, input system,
    and renderer.

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
        "_title",
        "_width",
        "_height",
        "_tps",
        "_target_dt",
        "_running",
        "_tick_count",
        "_dt",
        "_elapsed",
        "_last_tick_time",
        "_accumulator",
    )

    def __init__(
        self,
        title: str = _DEFAULT_TITLE,
        width: int = _DEFAULT_WIDTH,
        height: int = _DEFAULT_HEIGHT,
        tps: int = _DEFAULT_TPS,
    ) -> None:
        if not isinstance(title, str):
            raise TypeError(
                f"title must be a str, got {type(title).__name__}"
            )
        if not title.strip():
            raise ValueError("title must not be empty or blank")

        if not isinstance(width, int) or isinstance(width, bool):
            raise TypeError(
                f"width must be an int, got {type(width).__name__}"
            )
        if not isinstance(height, int) or isinstance(height, bool):
            raise TypeError(
                f"height must be an int, got {type(height).__name__}"
            )
        if not isinstance(tps, int) or isinstance(tps, bool):
            raise TypeError(
                f"tps must be an int, got {type(tps).__name__}"
            )

        if not (_MIN_WIDTH <= width <= _MAX_WIDTH):
            raise ValueError(
                f"width must be between {_MIN_WIDTH} and {_MAX_WIDTH}, "
                f"got {width}"
            )
        if not (_MIN_HEIGHT <= height <= _MAX_HEIGHT):
            raise ValueError(
                f"height must be between {_MIN_HEIGHT} and {_MAX_HEIGHT}, "
                f"got {height}"
            )
        if not (_MIN_TPS <= tps <= _MAX_TPS):
            raise ValueError(
                f"tps must be between {_MIN_TPS} and {_MAX_TPS}, "
                f"got {tps}"
            )

        self._title = title
        self._width = width
        self._height = height
        self._tps = tps
        self._target_dt = 1.0 / tps
        self._running = False
        self._tick_count: int = 0
        self._dt: float = 0.0
        self._elapsed: float = 0.0
        self._last_tick_time: float = 0.0
        self._accumulator: float = 0.0

        _logger.debug(
            "Engine initialized: title=%r, width=%d, height=%d, tps=%d",
            self._title,
            self._width,
            self._height,
            self._tps,
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

    def run(self, *, loop: bool = True) -> None:
        """Start the engine's main loop.

        When *loop* is ``True`` (the default), the engine runs a
        **fixed-timestep** loop using the accumulator pattern until
        stopped via :meth:`stop` or a ``KeyboardInterrupt`` (Ctrl+C).
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
            - **No subsystems connected yet.** Each tick is currently a
              no-op placeholder. Input polling, scene updates, and
              rendering will be wired in by later tasks (see SCOPE.md).
            - **Sleep granularity.** ``time.sleep()`` precision is
              OS-dependent (typically 1–10 ms).  The accumulator
              self-corrects for overshoot on the next frame.
            - **Suspend/resume.** If the process is suspended (laptop
              lid, debugger, ``SIGSTOP``), the first frame after wake
              sees a large wall-clock gap.  ``frame_time`` is clamped
              to ``_DT_CLAMP`` to prevent a burst of catch-up ticks.
            - ``KeyboardInterrupt`` is caught and treated as a clean
              shutdown. Terminal-state cleanup (e.g. restoring cursor
              visibility) will be added when the renderer is implemented.
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
        finally:
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

    def _tick(self) -> None:
        """Execute one fixed-timestep update.

        Each call represents exactly :attr:`target_dt` seconds of game
        time, regardless of wall-clock duration.  The accumulator in
        :meth:`_run_loop` handles the mapping between wall-clock time
        and game time.

        Currently a no-op beyond timing bookkeeping. Will eventually:
        drain input → update active scene → render frame.
        """
        self._dt = self._target_dt
        self._elapsed += self._dt
        self._tick_count += 1

    def __repr__(self) -> str:
        return (
            f"Engine(title={self._title!r}, "
            f"width={self._width!r}, height={self._height!r}, "
            f"tps={self._tps!r})"
        )
