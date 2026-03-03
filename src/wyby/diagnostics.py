"""FPS counter, render timing, and terminal capability reporting.

This module provides diagnostic tools for measuring actual performance
in a given terminal environment and detecting terminal capabilities.

The primary classes are:

- :class:`FPSCounter` — tracks wall-clock tick intervals and computes
  smoothed FPS metrics over a rolling window.
- :class:`RenderTimer` — tracks wall-clock duration of individual render
  (``present()``) calls and computes rolling statistics.
- :class:`ColorSupport` — enum representing the terminal's colour depth
  (none, standard 16-colour, 256-colour, or truecolor 24-bit).
- :class:`TerminalCapabilities` — frozen snapshot of detected terminal
  capabilities (colour depth, Unicode support, terminal size, TTY status,
  and identified terminal emulator).

Use :func:`detect_capabilities` to probe the current environment.

Caveats:
    - FPS reflects wall-clock tick throughput, **not** a guaranteed frame
      rate.  Achievable refresh rate depends on terminal emulator, OS, grid
      size, and style complexity.  On a modern terminal with a modest grid,
      15–30 updates per second is realistic.  On Windows Console or over
      SSH, it may be significantly lower.
    - :class:`RenderTimer` measures wall-clock time spent inside
      ``present()`` (Rich serialisation + terminal write).  It does **not**
      capture terminal-side rendering time (glyph rasterisation, GPU
      compositing, VSync).  The actual visible-frame latency is always
      higher than the measured ``present()`` duration.
    - Do not use FPS or render-time numbers to promise performance to end
      users.  Terminal rendering performance is inherently variable and
      outside the engine's control.
    - The rolling window introduces smoothing lag — at 30 tps with a
      60-sample window, it takes ~2 seconds before the average fully
      reflects a sustained change in frame rate.
    - Terminal capability detection is **best-effort**.  Not all terminals
      accurately report their capabilities via environment variables.
      Some terminals support truecolor but do not set ``$COLORTERM``.
      Some report UTF-8 in locale settings but render Unicode poorly.
      Detection results should be treated as hints, not guarantees.
    - ``$COLORTERM`` is the primary signal for truecolor support, but it
      is not standardised — it is a de-facto convention adopted by most
      modern terminal emulators.  Absence of ``$COLORTERM`` does not
      necessarily mean truecolor is unsupported.
    - ``$TERM_PROGRAM`` and similar environment variables are set by the
      terminal emulator process.  Inside ``tmux`` or ``screen``, these may
      reflect the multiplexer rather than the outer terminal, which can
      cause capability under-reporting.
"""

from __future__ import annotations

import collections
import enum
import logging
import os
import sys

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Terminal capability detection
# ---------------------------------------------------------------------------


class ColorSupport(enum.Enum):
    """Terminal colour depth levels.

    Ordered from least to most capable.  Use comparison (``>=``, ``<``,
    etc.) via the :meth:`__ge__` family to check minimum support level::

        caps = detect_capabilities()
        if caps.color_support >= ColorSupport.TRUECOLOR:
            # safe to use 24-bit RGB colours
            ...

    Caveats:
        - These levels represent what the terminal *claims* to support,
          not what it actually renders correctly.  A terminal may report
          truecolor support but have buggy 24-bit rendering.
        - Rich performs its own colour fallback internally.  This enum
          reflects the *detected* capability before Rich's fallback
          logic runs.
    """

    NONE = 0
    """No colour support detected (e.g., dumb terminal or pipe)."""

    STANDARD = 1
    """Standard 16-colour (4-bit) ANSI palette."""

    EXTENDED = 2
    """Extended 256-colour (8-bit) palette."""

    TRUECOLOR = 3
    """Truecolor 24-bit RGB support."""

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, ColorSupport):
            return NotImplemented
        return self.value >= other.value

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, ColorSupport):
            return NotImplemented
        return self.value > other.value

    def __le__(self, other: object) -> bool:
        if not isinstance(other, ColorSupport):
            return NotImplemented
        return self.value <= other.value

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, ColorSupport):
            return NotImplemented
        return self.value < other.value


class TerminalCapabilities:
    """Frozen snapshot of detected terminal capabilities.

    Instances are created by :func:`detect_capabilities` and are
    immutable after construction.  All fields are read-only properties.

    Caveats:
        - Capabilities are detected at construction time from environment
          variables and file descriptor state.  They do **not** update if
          the environment changes later (e.g., terminal resize, ``$TERM``
          modification).  Call :func:`detect_capabilities` again to get
          a fresh snapshot.
        - ``is_tty`` checks ``sys.stdout.isatty()``.  If stdout is
          redirected to a pipe or file, this will be ``False`` even if
          the process is running inside a terminal emulator.
        - ``utf8_supported`` checks locale environment variables
          (``$LC_ALL``, ``$LC_CTYPE``, ``$LANG``).  A ``True`` result
          means the locale *claims* UTF-8 support, not that the terminal
          font contains all Unicode glyphs.  CJK characters, emoji, and
          complex grapheme clusters may still render incorrectly.
        - ``terminal_program`` is ``None`` if no known terminal
          identification variable is set.  Inside ``tmux`` or ``screen``,
          the reported program may be the multiplexer, not the outer
          terminal.
        - ``columns`` and ``rows`` reflect the terminal size at detection
          time.  They fall back to 80x24 if the size cannot be determined
          (e.g., when stdout is not a TTY).
    """

    __slots__ = (
        "_color_support",
        "_utf8_supported",
        "_is_tty",
        "_terminal_program",
        "_columns",
        "_rows",
        "_colorterm_env",
        "_term_env",
    )

    def __init__(
        self,
        *,
        color_support: ColorSupport,
        utf8_supported: bool,
        is_tty: bool,
        terminal_program: str | None,
        columns: int,
        rows: int,
        colorterm_env: str,
        term_env: str,
    ) -> None:
        self._color_support = color_support
        self._utf8_supported = utf8_supported
        self._is_tty = is_tty
        self._terminal_program = terminal_program
        self._columns = columns
        self._rows = rows
        self._colorterm_env = colorterm_env
        self._term_env = term_env

    @property
    def color_support(self) -> ColorSupport:
        """Detected colour depth level."""
        return self._color_support

    @property
    def utf8_supported(self) -> bool:
        """Whether the locale claims UTF-8 encoding."""
        return self._utf8_supported

    @property
    def is_tty(self) -> bool:
        """Whether stdout is connected to a terminal."""
        return self._is_tty

    @property
    def terminal_program(self) -> str | None:
        """Identified terminal emulator name, or ``None`` if unknown."""
        return self._terminal_program

    @property
    def columns(self) -> int:
        """Detected terminal width in columns."""
        return self._columns

    @property
    def rows(self) -> int:
        """Detected terminal height in rows."""
        return self._rows

    @property
    def colorterm_env(self) -> str:
        """Raw value of ``$COLORTERM`` (empty string if unset)."""
        return self._colorterm_env

    @property
    def term_env(self) -> str:
        """Raw value of ``$TERM`` (empty string if unset)."""
        return self._term_env

    def __repr__(self) -> str:
        return (
            f"TerminalCapabilities("
            f"color_support={self._color_support.name}, "
            f"utf8={self._utf8_supported}, "
            f"tty={self._is_tty}, "
            f"size={self._columns}x{self._rows}, "
            f"program={self._terminal_program!r})"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, TerminalCapabilities):
            return NotImplemented
        return (
            self._color_support == other._color_support
            and self._utf8_supported == other._utf8_supported
            and self._is_tty == other._is_tty
            and self._terminal_program == other._terminal_program
            and self._columns == other._columns
            and self._rows == other._rows
            and self._colorterm_env == other._colorterm_env
            and self._term_env == other._term_env
        )


def _detect_color_support(colorterm: str, term: str) -> ColorSupport:
    """Infer colour depth from environment variables.

    Checks ``$COLORTERM`` first (the de-facto standard for signalling
    truecolor), then falls back to heuristics on ``$TERM``.

    Caveats:
        - ``$COLORTERM`` is not part of any formal standard.  It is a
          convention adopted by terminal emulators (kitty, iTerm2,
          WezTerm, GNOME Terminal, etc.) and libraries (Rich, ncurses).
        - Some terminals support truecolor but do not set ``$COLORTERM``.
          Users can set it manually: ``export COLORTERM=truecolor``.
        - ``$TERM`` values like ``xterm-256color`` indicate 256-colour
          support, but the actual terminal may support more (or less)
          than what ``$TERM`` claims — ``$TERM`` describes the *terminfo
          entry*, not the terminal's true capabilities.
        - Inside ``tmux``/``screen``, ``$TERM`` is typically overridden
          to ``screen`` or ``tmux``, which may hide the outer terminal's
          truecolor support.  Users should configure tmux to pass through
          ``$COLORTERM`` or set ``terminal-overrides``.
    """
    # $COLORTERM is the strongest signal for truecolor.
    colorterm_lower = colorterm.lower()
    if colorterm_lower in ("truecolor", "24bit"):
        return ColorSupport.TRUECOLOR

    # Some terminals set $COLORTERM but not to a truecolor value.
    # Fall through to $TERM-based heuristics.

    term_lower = term.lower()

    # Check for 256-color indicators in $TERM.
    if "256color" in term_lower:
        return ColorSupport.EXTENDED

    # Bare "dumb" terminal or empty $TERM — no colour.
    if term_lower in ("", "dumb"):
        return ColorSupport.NONE

    # Any other $TERM value — assume at least standard 16-colour.
    return ColorSupport.STANDARD


def _detect_utf8() -> bool:
    """Check locale environment variables for UTF-8 encoding.

    Inspects ``$LC_ALL``, ``$LC_CTYPE``, and ``$LANG`` (in priority
    order, matching the POSIX locale resolution chain).

    Caveats:
        - A ``True`` result means the locale *claims* UTF-8 support.
          The terminal font may not contain glyphs for all Unicode
          code points.  Box-drawing characters and block elements are
          safe; emoji and CJK characters are not guaranteed.
        - On Windows, locale environment variables may not be set.
          Python's ``sys.getdefaultencoding()`` typically returns
          ``'utf-8'`` on modern Python, but terminal rendering of
          Unicode depends on the console host (Windows Terminal handles
          it well; legacy ``conhost`` does not).
        - Inside containers or minimal environments, locale variables
          may be unset.  This function returns ``False`` in that case,
          even if the terminal actually handles UTF-8.
    """
    for var in ("LC_ALL", "LC_CTYPE", "LANG"):
        value = os.environ.get(var, "")
        if value and "utf-8" in value.lower().replace("utf8", "utf-8"):
            return True
    return False


def _detect_terminal_program() -> str | None:
    """Identify the terminal emulator from environment variables.

    Checks, in order: ``$TERM_PROGRAM``, ``$TERMINAL_EMULATOR``,
    ``$WT_SESSION`` (Windows Terminal), and ``$KITTY_WINDOW_ID``
    (kitty).

    Caveats:
        - These variables are set by the terminal emulator process and
          are not standardised.  Inside ``tmux`` or ``screen``, they
          may reflect the multiplexer rather than the outer terminal.
        - ``$WT_SESSION`` is a GUID set by Windows Terminal.  Its
          presence indicates Windows Terminal, but its value is opaque.
        - ``$KITTY_WINDOW_ID`` is set by kitty.  It may coexist with
          ``$TERM_PROGRAM`` (kitty sets both).  We check
          ``$TERM_PROGRAM`` first, so kitty is typically identified
          by that variable.
        - Returns ``None`` if no known variable is set, which does
          **not** mean the terminal is incapable — only unidentified.
    """
    term_program = os.environ.get("TERM_PROGRAM", "")
    if term_program:
        return term_program

    terminal_emulator = os.environ.get("TERMINAL_EMULATOR", "")
    if terminal_emulator:
        return terminal_emulator

    # Windows Terminal sets $WT_SESSION (a GUID) but not $TERM_PROGRAM.
    if os.environ.get("WT_SESSION"):
        return "Windows Terminal"

    # kitty sets $KITTY_WINDOW_ID.
    if os.environ.get("KITTY_WINDOW_ID"):
        return "kitty"

    return None


def _detect_terminal_size() -> tuple[int, int]:
    """Detect terminal dimensions (columns, rows).

    Falls back to 80x24 if the size cannot be determined (e.g.,
    stdout is not a TTY).

    Caveats:
        - ``os.get_terminal_size()`` queries the file descriptor
          associated with stdout.  If stdout is redirected to a pipe
          or file, this raises ``OSError`` and we fall back to 80x24.
        - The ``$COLUMNS`` and ``$LINES`` environment variables are
          **not** checked here.  ``os.get_terminal_size()`` reads the
          kernel's terminal size (via ``ioctl TIOCGWINSZ`` on Unix or
          ``GetConsoleScreenBufferInfo`` on Windows), which is more
          reliable than shell-set variables.
        - Terminal size can change at any time (user resizes the
          window).  This function returns a point-in-time snapshot.
          Use :class:`~wyby.resize.ResizeHandler` for ongoing resize
          tracking.
    """
    try:
        size = os.get_terminal_size()
        return (size.columns, size.lines)
    except OSError:
        return (80, 24)


def detect_capabilities() -> TerminalCapabilities:
    """Probe the current terminal environment and return a capability snapshot.

    Inspects environment variables (``$COLORTERM``, ``$TERM``,
    ``$TERM_PROGRAM``, ``$LC_ALL``, ``$LC_CTYPE``, ``$LANG``),
    checks whether stdout is a TTY, and queries terminal dimensions.

    Returns:
        A :class:`TerminalCapabilities` instance with all detected
        values.  The result is a frozen snapshot — it does not track
        subsequent environment changes.

    Caveats:
        - All detection is **best-effort** via environment variables
          and OS APIs.  Terminals are not required to set any of these
          variables, and some actively misrepresent their capabilities.
        - This function does **not** send query escape sequences to the
          terminal (e.g., ``\\e[c`` Device Attributes).  Such queries
          are more accurate but require reading the terminal's response
          from stdin, which conflicts with game input handling and is
          not safe to do mid-session.
        - For the most accurate colour detection, users should ensure
          their terminal sets ``$COLORTERM=truecolor`` if it supports
          24-bit colour.  Most modern terminals do this automatically.
        - Call this function **before** entering the game loop to log
          capabilities at startup.  Avoid calling it per-frame — it
          reads environment variables and may call ``os.get_terminal_size()``
          on each invocation.
    """
    colorterm = os.environ.get("COLORTERM", "")
    term = os.environ.get("TERM", "")

    color_support = _detect_color_support(colorterm, term)
    utf8 = _detect_utf8()
    is_tty = sys.stdout.isatty()
    terminal_program = _detect_terminal_program()
    columns, rows = _detect_terminal_size()

    caps = TerminalCapabilities(
        color_support=color_support,
        utf8_supported=utf8,
        is_tty=is_tty,
        terminal_program=terminal_program,
        columns=columns,
        rows=rows,
        colorterm_env=colorterm,
        term_env=term,
    )
    _logger.debug("Detected terminal capabilities: %s", caps)
    return caps


# ---------------------------------------------------------------------------
# FPS counter
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Render timer
# ---------------------------------------------------------------------------


class RenderTimer:
    """Tracks wall-clock duration of individual render calls.

    Call :meth:`record` with the duration (in seconds) of each
    ``Renderer.present()`` call.  The timer maintains a rolling window
    of render durations and derives min/avg/max statistics.

    This is the per-render complement to :class:`FPSCounter`, which
    tracks tick-to-tick intervals.  Together they answer two different
    questions:

    - **FPSCounter**: "How many ticks per second is the loop achieving?"
      (includes update logic, input handling, sleep, *and* rendering)
    - **RenderTimer**: "How long does the ``present()`` call itself take?"
      (only the Rich serialisation + terminal write)

    Args:
        window_size: Number of samples in the rolling window.  Larger
            windows produce smoother averages but respond more slowly to
            sustained changes.  Must be between 1 and 1000 inclusive.
            Defaults to 60 (~2 seconds at 30 tps).

    Raises:
        TypeError: If *window_size* is not an integer.
        ValueError: If *window_size* is outside the allowed range (1–1000).

    Caveats:
        - Measured duration covers ``Live.update()`` (Rich renderable
          serialisation to ANSI escape sequences) and the synchronous
          ``stdout.write()`` that follows.  It does **not** include
          terminal-side processing (ANSI parsing, glyph rasterisation,
          GPU compositing, VSync wait).  The actual time from
          ``present()`` to pixels-on-screen is always higher.
        - On terminals that buffer writes (most modern terminals), the
          ``write()`` returns as soon as the data is in the kernel's
          write buffer, not when the terminal has finished rendering.
          Measured times therefore underestimate true render latency.
        - ``time.perf_counter()`` is used for measurement.  On most
          platforms this provides sub-microsecond resolution, but on
          some older Windows builds the resolution is ~100 ns.  For
          the millisecond-scale durations of typical render calls,
          this is more than sufficient.
        - Very short windows (1–5 samples) produce noisy statistics.
          Very long windows (500+) are slow to reflect rate changes.
          The default of 60 is a reasonable middle ground.
        - Statistics are only meaningful after at least one sample has
          been recorded.  All properties return ``0.0`` until then.
    """

    __slots__ = ("_window_size", "_samples", "_total_renders")

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
        self._total_renders: int = 0

    @property
    def window_size(self) -> int:
        """Number of samples in the rolling window."""
        return self._window_size

    @property
    def sample_count(self) -> int:
        """Number of render-time samples currently stored."""
        return len(self._samples)

    @property
    def total_renders(self) -> int:
        """Total number of render calls recorded (including evicted samples)."""
        return self._total_renders

    @property
    def last_render_ms(self) -> float:
        """Most recent render call duration in milliseconds.

        Returns ``0.0`` if no samples have been recorded.

        Caveat: this is a single raw measurement that may be noisy due
        to OS scheduling jitter, GC pauses, or terminal write buffering.
        Use :attr:`avg_render_ms` for a smoothed metric.
        """
        if not self._samples:
            return 0.0
        return self._samples[-1] * 1000.0

    @property
    def avg_render_ms(self) -> float:
        """Average render duration in milliseconds over the rolling window.

        Returns ``0.0`` if no samples have been recorded.
        """
        if not self._samples:
            return 0.0
        return (sum(self._samples) / len(self._samples)) * 1000.0

    @property
    def min_render_ms(self) -> float:
        """Minimum render duration in the current rolling window (ms).

        Returns ``0.0`` if no samples have been recorded.
        """
        if not self._samples:
            return 0.0
        return min(self._samples) * 1000.0

    @property
    def max_render_ms(self) -> float:
        """Maximum render duration in the current rolling window (ms).

        Returns ``0.0`` if no samples have been recorded.

        Caveat: a single slow render (e.g., GC pause during
        serialisation, terminal write stall) can make this value
        appear much higher than typical performance.
        """
        if not self._samples:
            return 0.0
        return max(self._samples) * 1000.0

    def record(self, duration_s: float) -> None:
        """Record a render call duration.

        Args:
            duration_s: Duration in seconds of the ``present()`` call,
                measured with ``time.perf_counter()``.
        """
        self._samples.append(duration_s)
        self._total_renders += 1

    def reset(self) -> None:
        """Clear all samples and reset the render count.

        After calling ``reset()``, all properties return ``0.0`` until
        new samples are recorded via :meth:`record`.
        """
        self._samples.clear()
        self._total_renders = 0
        _logger.debug("RenderTimer reset")

    def __repr__(self) -> str:
        return (
            f"RenderTimer(window_size={self._window_size}, "
            f"avg_ms={self.avg_render_ms:.2f}, "
            f"samples={len(self._samples)})"
        )
