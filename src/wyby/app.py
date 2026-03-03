"""Application entry point and game loop.

This module provides the main :class:`Engine` class that will ultimately
drive the fixed-timestep game loop: drain input -> update active scene ->
render frame.

Caveats:
    - **Early implementation.** The ``Engine`` constructor and a basic
      ``run()`` loop are functional, but scene management, input, and
      rendering are not yet connected. See SCOPE.md for the intended design.
    - The game loop will target ~30 ticks per second by default, but
      actual frame rate depends on terminal emulator, grid size, and style
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


class Engine:
    """Core engine that manages the game loop and top-level configuration.

    The ``Engine`` holds the game's title and logical grid dimensions.
    Future versions will own the scene stack, input system, and renderer.

    Args:
        title: Window/application title. Used for diagnostic output and
            will be passed to the terminal title escape sequence once the
            renderer is implemented. Defaults to ``"wyby"``.
        width: Logical grid width in character cells. Must be between 1
            and 1000 inclusive. Defaults to 80 (standard terminal width).
        height: Logical grid height in character cells. Must be between 1
            and 1000 inclusive. Defaults to 24 (standard terminal height).

    Raises:
        TypeError: If *title* is not a string, or *width*/*height* are
            not integers.
        ValueError: If *title* is empty or blank, or *width*/*height*
            are outside the allowed range (1–1000).

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
        "_running",
        "_tick_count",
        "_dt",
        "_elapsed",
        "_last_tick_time",
    )

    def __init__(
        self,
        title: str = _DEFAULT_TITLE,
        width: int = _DEFAULT_WIDTH,
        height: int = _DEFAULT_HEIGHT,
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

        self._title = title
        self._width = width
        self._height = height
        self._running = False
        self._tick_count: int = 0
        self._dt: float = 0.0
        self._elapsed: float = 0.0
        self._last_tick_time: float = 0.0

        _logger.debug(
            "Engine initialized: title=%r, width=%d, height=%d",
            self._title,
            self._width,
            self._height,
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
    def running(self) -> bool:
        """Whether the engine's game loop is currently executing."""
        return self._running

    @property
    def tick_count(self) -> int:
        """Total number of ticks executed since the last ``run()`` call."""
        return self._tick_count

    @property
    def dt(self) -> float:
        """Wall-clock duration of the most recent tick, in seconds.

        Uses ``time.monotonic()``, which is immune to system clock
        adjustments (NTP, manual ``date`` changes, daylight-saving
        transitions) but **not** to OS-level sleep or suspend.  If the
        machine is suspended mid-game, the first tick after wake will
        report a large ``dt`` that includes the suspend duration.  A
        future fixed-timestep implementation should clamp ``dt`` to
        avoid physics explosions after resume.

        Returns 0.0 before the first tick completes.
        """
        return self._dt

    @property
    def elapsed(self) -> float:
        """Cumulative wall-clock time spent ticking, in seconds.

        This is the sum of every ``dt`` since ``run()`` was called — it
        measures only time spent inside the tick loop, not wall-clock
        time since construction.  Pauses or sleeps between ``run()``
        calls are not counted.

        Caveats:
            - Accumulated floating-point drift is possible over very
              long sessions (hours).  For a 30-tps game running 10
              hours that's ~1 080 000 additions; IEEE 754 double
              precision keeps ~15 significant digits, so drift stays
              well below 1 ms.  If sub-microsecond accuracy matters
              over marathon sessions, use ``tick_count`` and a known
              fixed timestep instead.
            - Reset to 0.0 each time ``run()`` is called.
        """
        return self._elapsed

    def run(self, *, loop: bool = True) -> None:
        """Start the engine's main loop.

        When *loop* is ``True`` (the default), the engine runs continuously
        until stopped via :meth:`stop` or a ``KeyboardInterrupt`` (Ctrl+C).
        When *loop* is ``False``, the engine executes exactly one iteration
        of the game loop and returns — useful for testing and debugging.

        Args:
            loop: If ``True``, run the game loop until stopped. If ``False``,
                execute a single tick and return.

        Caveats:
            - **No subsystems connected yet.** Each tick is currently a no-op
              placeholder. Input polling, scene updates, and rendering will
              be wired in by later tasks (see SCOPE.md).
            - **No fixed timestep.** The loop does not yet sleep or pace
              itself — ticks run as fast as Python allows, which will peg
              one CPU core. Fixed-timestep timing (T015/T016) will add
              proper sleep/catch-up logic.
            - ``KeyboardInterrupt`` is caught and treated as a clean
              shutdown. Terminal-state cleanup (e.g. restoring cursor
              visibility) will be added when the renderer is implemented.
            - Calling ``run()`` while the engine is already running has no
              effect; the call returns immediately.
        """
        if self._running:
            _logger.debug("Engine.run() called while already running, ignoring")
            return

        self._running = True
        self._tick_count = 0
        self._dt = 0.0
        self._elapsed = 0.0
        # time.monotonic() is used rather than time.perf_counter() because
        # monotonic is guaranteed never to go backwards (immune to NTP
        # adjustments and system clock changes).  perf_counter offers
        # higher resolution on some platforms but can theoretically jump
        # on clock adjustment.  For a game loop where correctness matters
        # more than nanosecond precision, monotonic is the safer choice.
        self._last_tick_time = time.monotonic()
        _logger.debug("Engine.run() starting (loop=%s)", loop)

        try:
            while self._running:
                self._tick()
                if not loop:
                    break
        except KeyboardInterrupt:
            _logger.debug("KeyboardInterrupt received, stopping engine")
        finally:
            self._running = False
            _logger.debug("Engine.run() finished")

    def stop(self) -> None:
        """Signal the engine to stop after the current tick completes.

        This sets the internal running flag to ``False``. The game loop
        will exit at the end of the current tick. Calling ``stop()`` when
        the engine is not running is a harmless no-op.
        """
        _logger.debug("Engine.stop() called")
        self._running = False

    def _tick(self) -> None:
        """Execute one iteration of the game loop.

        Measures wall-clock duration via ``time.monotonic()`` and updates
        :attr:`dt`, :attr:`elapsed`, and :attr:`tick_count`.

        Currently a no-op beyond timing. Will eventually: drain input →
        update active scene → render frame.
        """
        now = time.monotonic()
        self._dt = now - self._last_tick_time
        self._last_tick_time = now
        self._elapsed += self._dt
        self._tick_count += 1

    def __repr__(self) -> str:
        return (
            f"Engine(title={self._title!r}, "
            f"width={self._width!r}, height={self._height!r})"
        )
