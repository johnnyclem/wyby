"""FPS counter, tick timing, and terminal capability reporting.

This module provides diagnostic tools for measuring actual performance
in a given terminal environment.  The primary class is :class:`FPSCounter`,
which tracks wall-clock tick intervals and computes smoothed FPS metrics
over a rolling window.

Caveats:
    - FPS reflects wall-clock tick throughput, **not** a guaranteed frame
      rate.  Achievable refresh rate depends on terminal emulator, OS, grid
      size, and style complexity.  On a modern terminal with a modest grid,
      15–30 updates per second is realistic.  On Windows Console or over
      SSH, it may be significantly lower.
    - FPS measurement tracks tick intervals, not actual Rich render calls
      (the renderer is not yet connected).  Once the renderer is wired up,
      a per-render measurement may be added for finer granularity.
    - Do not use FPS numbers to promise performance to end users.  Terminal
      rendering performance is inherently variable and outside the engine's
      control.
    - The rolling window introduces smoothing lag — at 30 tps with a
      60-sample window, it takes ~2 seconds before the average fully
      reflects a sustained change in frame rate.
    - Terminal capability detection (truecolor support, Unicode width,
      terminal size) is best-effort and not yet implemented.  Not all
      terminals accurately report their capabilities.
"""

from __future__ import annotations

import collections
import logging

_logger = logging.getLogger(__name__)

# Sensible bounds for the rolling window size.
_MIN_WINDOW_SIZE = 1
_MAX_WINDOW_SIZE = 1000
_DEFAULT_WINDOW_SIZE = 60


class FPSCounter:
    """Tracks wall-clock tick intervals and computes smoothed FPS metrics.

    Call :meth:`tick` once per engine tick with the current monotonic
    timestamp.  The counter maintains a rolling window of inter-tick
    durations and derives FPS from their average.

    Args:
        window_size: Number of samples in the rolling window.  Larger
            windows produce smoother averages but respond more slowly to
            sustained rate changes.  Must be between 1 and 1000 inclusive.
            Defaults to 60 (~2 seconds at 30 tps).

    Raises:
        TypeError: If *window_size* is not an integer.
        ValueError: If *window_size* is outside the allowed range (1–1000).

    Caveats:
        - FPS is computed from wall-clock intervals between :meth:`tick`
          calls, which includes time spent in ``update()``, ``render()``,
          event draining, **and** sleep.  It measures overall loop
          throughput, not the cost of any single phase.
        - The first call to :meth:`tick` establishes a baseline timestamp
          but cannot compute a duration.  :attr:`fps` returns ``0.0``
          until at least two ticks have been recorded.
        - Very short windows (1–5 samples) will produce noisy readings.
          Very long windows (500+) will be slow to reflect rate changes.
          The default of 60 is a reasonable middle ground for most games.
        - On platforms where ``time.monotonic()`` has coarse resolution
          (some older Windows builds report ~15 ms granularity),
          individual frame times may appear quantized.  The rolling
          average smooths this out over several samples.
    """

    __slots__ = (
        "_window_size",
        "_samples",
        "_last_time",
        "_tick_count",
    )

    def __init__(self, window_size: int = _DEFAULT_WINDOW_SIZE) -> None:
        if not isinstance(window_size, int) or isinstance(window_size, bool):
            raise TypeError(
                f"window_size must be an int, got {type(window_size).__name__}"
            )
        if not (_MIN_WINDOW_SIZE <= window_size <= _MAX_WINDOW_SIZE):
            raise ValueError(
                f"window_size must be between {_MIN_WINDOW_SIZE} and "
                f"{_MAX_WINDOW_SIZE}, got {window_size}"
            )

        self._window_size = window_size
        self._samples: collections.deque[float] = collections.deque(
            maxlen=window_size,
        )
        self._last_time: float | None = None
        self._tick_count: int = 0

    @property
    def window_size(self) -> int:
        """Number of samples in the rolling window."""
        return self._window_size

    @property
    def sample_count(self) -> int:
        """Number of frame-time samples currently stored."""
        return len(self._samples)

    @property
    def tick_count(self) -> int:
        """Total number of ticks recorded (including the baseline tick)."""
        return self._tick_count

    @property
    def fps(self) -> float:
        """Current smoothed FPS based on the rolling window average.

        Returns ``0.0`` if fewer than one frame-time sample has been
        recorded (i.e., before the second call to :meth:`tick`).

        Caveat: this is a *smoothed* average over the window, not an
        instantaneous measurement.  Short spikes or drops are dampened.
        """
        if not self._samples:
            return 0.0
        avg = sum(self._samples) / len(self._samples)
        if avg <= 0.0:
            return 0.0
        return 1.0 / avg

    @property
    def frame_time_ms(self) -> float:
        """Most recent frame time in milliseconds.

        Returns ``0.0`` if no frame-time samples have been recorded yet.

        Caveat: this is the raw wall-clock interval for the most recent
        tick, which may be noisy due to OS scheduling jitter and sleep
        granularity.  Use :attr:`fps` for a smoothed metric.
        """
        if not self._samples:
            return 0.0
        return self._samples[-1] * 1000.0

    @property
    def avg_frame_time_ms(self) -> float:
        """Average frame time in milliseconds over the rolling window.

        Returns ``0.0`` if no samples have been recorded.
        """
        if not self._samples:
            return 0.0
        return (sum(self._samples) / len(self._samples)) * 1000.0

    @property
    def min_fps(self) -> float:
        """Minimum FPS seen in the current rolling window.

        Derived from the *longest* frame time in the window.
        Returns ``0.0`` if no samples have been recorded.

        Caveat: a single long frame (e.g., GC pause, OS scheduling delay)
        can make this value appear much lower than typical performance.
        """
        if not self._samples:
            return 0.0
        longest = max(self._samples)
        if longest <= 0.0:
            return 0.0
        return 1.0 / longest

    @property
    def max_fps(self) -> float:
        """Maximum FPS seen in the current rolling window.

        Derived from the *shortest* frame time in the window.
        Returns ``0.0`` if no samples have been recorded.

        Caveat: very short frame times (near zero) can produce
        misleadingly high max FPS values.  This reflects the fastest
        single tick, not sustainable throughput.
        """
        if not self._samples:
            return 0.0
        shortest = min(self._samples)
        if shortest <= 0.0:
            return 0.0
        return 1.0 / shortest

    def tick(self, now: float) -> None:
        """Record a tick timestamp and update frame-time samples.

        Should be called once per engine tick with the current value of
        ``time.monotonic()``.

        Args:
            now: Current monotonic timestamp in seconds.

        The first call establishes the baseline; subsequent calls compute
        the inter-tick duration and add it to the rolling window.
        """
        self._tick_count += 1
        if self._last_time is not None:
            dt = now - self._last_time
            self._samples.append(dt)
        self._last_time = now

    def reset(self) -> None:
        """Clear all samples and reset the baseline timestamp.

        After calling ``reset()``, the counter behaves as if freshly
        constructed — :attr:`fps` returns ``0.0`` until two new ticks
        are recorded.
        """
        self._samples.clear()
        self._last_time = None
        self._tick_count = 0
        _logger.debug("FPSCounter reset")

    def __repr__(self) -> str:
        return (
            f"FPSCounter(window_size={self._window_size}, "
            f"fps={self.fps:.1f}, "
            f"samples={len(self._samples)})"
        )
