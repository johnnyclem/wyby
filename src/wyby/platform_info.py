"""Platform differences between Windows and Unix.

This module provides a structured catalog of platform-specific behaviours
across wyby, plus runtime detection of the current platform's capabilities.

Use :func:`get_platform_info` to get a snapshot of the current platform,
and :data:`PLATFORM_DIFFERENCES` for the full catalog of known differences.

The differences are organized into categories matching wyby's subsystems:
input handling, resize detection, terminal features, timing, and signals.

Why this matters for terminal games
------------------------------------
Terminal games are unusually sensitive to platform differences because
they rely on OS-level APIs (``termios``, ``msvcrt``, signals) rather
than a cross-platform graphics layer.  Every subsystem in wyby has at
least one behaviour that differs between Windows and Unix:

- **Input**: Unix uses ``termios`` raw mode + ``select``; Windows uses
  ``msvcrt``.  Key encoding differs (ANSI escapes vs scan-code pairs).
- **Resize**: Unix has ``SIGWINCH`` for immediate notification; Windows
  must poll.
- **Signals**: ``SIGWINCH``, ``SIGTSTP``, and ``SIGCONT`` exist only on
  Unix.  ``SIGINT`` and ``SIGTERM`` exist on both platforms but behave
  differently in raw mode.
- **Alt screen**: Supported by Windows Terminal (ConPTY, Windows 10
  1903+) but not by legacy ``conhost.exe``.
- **Timing**: ``time.monotonic()`` has ~15 ms granularity on some older
  Windows builds; Unix typically has sub-millisecond resolution.
- **Unicode**: Windows Terminal handles UTF-8 well; legacy ``conhost``
  has limited support.  Unix depends on locale configuration.

Caveats:
    - This module reports what the *platform* supports, not what the
      *terminal emulator* supports.  A Unix system running an ancient
      terminal may lack features that Windows Terminal provides.  Use
      :func:`~wyby.diagnostics.detect_capabilities` for terminal-level
      detection.
    - The Windows differences documented here assume a modern Windows 10+
      environment.  Older Windows versions may have additional limitations
      not covered here.
    - Platform detection uses ``sys.platform``.  In emulation layers
      (WSL, Cygwin, MSYS2), ``sys.platform`` may report ``"linux"``
      even though the underlying OS is Windows.  This is generally
      correct behaviour — WSL provides a Linux-compatible environment.
"""

from __future__ import annotations

import dataclasses
import logging
import os
import signal
import sys

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Platform difference catalog
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True, slots=True)
class PlatformDifference:
    """A single documented difference between Windows and Unix.

    Attributes:
        category: Subsystem this difference belongs to (e.g., ``"input"``,
            ``"resize"``, ``"signals"``).
        feature: Short name of the feature (e.g., ``"raw_mode"``).
        unix_behaviour: How this feature works on Unix (Linux, macOS, BSDs).
        windows_behaviour: How this feature works on Windows.
        caveat: Additional context, gotchas, or edge cases.
    """

    category: str
    feature: str
    unix_behaviour: str
    windows_behaviour: str
    caveat: str


# The full catalog of known platform differences.  Each entry corresponds
# to a concrete behavioral difference that affects wyby's operation.
#
# Caveat: this is a point-in-time snapshot of known differences.  New
# terminal emulators and OS updates may change platform behaviour.
# Entries reflect the state of Windows 10+ and modern Linux/macOS.
PLATFORM_DIFFERENCES: tuple[PlatformDifference, ...] = (
    # -- Input handling ---------------------------------------------------
    PlatformDifference(
        category="input",
        feature="raw_mode",
        unix_behaviour=(
            "termios switches stdin to raw mode: disables echo, line "
            "buffering, and signal generation.  Ctrl+C delivers byte "
            "0x03 instead of SIGINT.  Terminal settings must be restored "
            "on exit (termios.tcsetattr with TCSADRAIN)."
        ),
        windows_behaviour=(
            "msvcrt bypasses the console line editor without mode "
            "switching.  No terminal state to save/restore.  "
            "enter_raw_mode and exit_raw_mode are no-ops."
        ),
        caveat=(
            "On Unix, failure to restore cooked mode (e.g., SIGKILL) "
            "leaves the terminal broken.  Run 'reset' or 'stty sane' "
            "to recover.  Windows has no equivalent failure mode."
        ),
    ),
    PlatformDifference(
        category="input",
        feature="non_blocking_read",
        unix_behaviour=(
            "select.select with a zero timeout checks stdin readability.  "
            "os.read(fd, 1024) reads available bytes.  Cost is O(n) in "
            "fd count but negligible for a single fd."
        ),
        windows_behaviour=(
            "msvcrt.kbhit() peeks at the console input buffer.  "
            "msvcrt.getwch() reads one character without echo.  "
            "Returns characters (str), not bytes."
        ),
        caveat=(
            "Unix reads raw bytes that may be partial ANSI escape "
            "sequences.  Windows reads complete characters but encodes "
            "special keys as two-character sequences."
        ),
    ),
    PlatformDifference(
        category="input",
        feature="special_key_encoding",
        unix_behaviour=(
            "Special keys (arrows, Home, End, etc.) are ANSI escape "
            "sequences: ESC [ followed by parameter bytes and a final "
            "byte (e.g., ESC[A for Up).  Multi-byte, variable length."
        ),
        windows_behaviour=(
            "Special keys produce two-character sequences: a prefix "
            "byte (0x00 or 0xe0) followed by a scan code.  Fixed "
            "two-byte encoding, not ANSI-based."
        ),
        caveat=(
            "The parse_input_events function in wyby.input handles "
            "ANSI sequences.  The WindowsInputBackend encodes to "
            "UTF-8 bytes for consistency, but the underlying encoding "
            "is fundamentally different."
        ),
    ),
    PlatformDifference(
        category="input",
        feature="ctrl_c_handling",
        unix_behaviour=(
            "In raw mode, Ctrl+C does not generate SIGINT.  The byte "
            "0x03 is delivered to the application.  wyby's parser "
            "raises KeyboardInterrupt when it encounters 0x03."
        ),
        windows_behaviour=(
            "Ctrl+C may generate a console control event depending "
            "on SetConsoleMode flags.  msvcrt.getwch() returns the "
            "character '\\x03', which wyby treats the same way."
        ),
        caveat=(
            "On both platforms, wyby converts Ctrl+C (0x03) into a "
            "KeyboardInterrupt.  The mechanism differs but the "
            "observable behaviour is consistent."
        ),
    ),
    PlatformDifference(
        category="input",
        feature="sigtstp_suspend",
        unix_behaviour=(
            "SIGTSTP (Ctrl+Z) suspends the process.  The terminal "
            "driver may reset settings on suspend.  Raw mode must be "
            "re-entered after SIGCONT (resume) if needed."
        ),
        windows_behaviour=(
            "SIGTSTP does not exist on Windows.  Ctrl+Z in a console "
            "is typically interpreted as EOF, not suspend."
        ),
        caveat=(
            "Games running on Unix should handle SIGCONT to re-enter "
            "raw mode after being backgrounded and foregrounded."
        ),
    ),
    # -- Resize detection -------------------------------------------------
    PlatformDifference(
        category="resize",
        feature="sigwinch",
        unix_behaviour=(
            "SIGWINCH is delivered when the terminal is resized.  "
            "wyby installs a signal handler for immediate notification.  "
            "The handler sets a flag; actual callback dispatch happens "
            "in the game loop via ResizeHandler.consume()."
        ),
        windows_behaviour=(
            "SIGWINCH does not exist.  Terminal resize is detected "
            "by polling shutil.get_terminal_size() each tick.  This "
            "introduces up to one tick of latency before resize is "
            "detected."
        ),
        caveat=(
            "On Unix, SIGWINCH handlers run in the main thread between "
            "bytecodes.  They cannot interrupt blocking I/O.  On "
            "Windows, polling is the only option; call "
            "ResizeHandler.poll() every tick."
        ),
    ),
    PlatformDifference(
        category="resize",
        feature="terminal_size_api",
        unix_behaviour=(
            "os.get_terminal_size() uses ioctl TIOCGWINSZ to query "
            "the kernel's terminal dimensions directly."
        ),
        windows_behaviour=(
            "os.get_terminal_size() uses GetConsoleScreenBufferInfo "
            "to query the console buffer size."
        ),
        caveat=(
            "Both fall back to 80x24 when stdout is not a TTY.  The "
            "shutil.get_terminal_size() wrapper used by wyby handles "
            "this fallback consistently across platforms."
        ),
    ),
    # -- Terminal features ------------------------------------------------
    PlatformDifference(
        category="terminal",
        feature="alt_screen",
        unix_behaviour=(
            "CSI ?1049h/l is supported by virtually all modern Unix "
            "terminal emulators.  The Linux virtual console (tty1-tty6) "
            "does not support it — sequences are silently ignored."
        ),
        windows_behaviour=(
            "Supported by Windows Terminal and ConPTY-based terminals "
            "(Windows 10 1903+).  Legacy conhost.exe ignores the "
            "sequences silently."
        ),
        caveat=(
            "wyby's AltScreen context manager writes the sequences "
            "only when stdout is a TTY.  On both platforms, the "
            "sequences are no-ops when unsupported — no error is raised."
        ),
    ),
    PlatformDifference(
        category="terminal",
        feature="color_detection",
        unix_behaviour=(
            "$COLORTERM and $TERM environment variables are the primary "
            "signals.  Most modern Unix terminals set "
            "$COLORTERM=truecolor.  $TERM describes the terminfo entry "
            "(e.g., xterm-256color)."
        ),
        windows_behaviour=(
            "Environment variables may not be set.  Windows Terminal "
            "sets $WT_SESSION (a GUID) but may not set $COLORTERM or "
            "$TERM.  Legacy console has limited colour support (16 "
            "colours via the system palette)."
        ),
        caveat=(
            "wyby's detect_capabilities() checks $COLORTERM first, "
            "then falls back to $TERM heuristics.  On Windows, "
            "$WT_SESSION presence identifies Windows Terminal.  The "
            "absence of $COLORTERM does not mean truecolor is "
            "unsupported — it may just be unreported."
        ),
    ),
    PlatformDifference(
        category="terminal",
        feature="unicode_support",
        unix_behaviour=(
            "UTF-8 support depends on locale configuration (LC_ALL, "
            "LC_CTYPE, LANG).  Most modern Linux distributions default "
            "to UTF-8 locales.  Actual glyph rendering depends on the "
            "terminal emulator and font."
        ),
        windows_behaviour=(
            "Locale environment variables may not be set.  Windows "
            "Terminal has good UTF-8 support.  Legacy conhost has "
            "limited Unicode rendering.  Python's "
            "sys.getdefaultencoding() returns 'utf-8' on modern Python "
            "regardless of console capabilities."
        ),
        caveat=(
            "wyby checks locale variables for UTF-8 detection, which "
            "may return False on Windows even when the terminal handles "
            "UTF-8 correctly.  Box-drawing and block element characters "
            "are safe on both platforms; emoji and CJK are less reliable."
        ),
    ),
    PlatformDifference(
        category="terminal",
        feature="mouse_reporting",
        unix_behaviour=(
            "SGR extended mouse mode (mode 1006) is supported by most "
            "modern Unix terminals.  macOS Terminal.app has limited "
            "support (basic clicks only, unreliable releases/scrolls).  "
            "tmux/screen require 'set -g mouse on'."
        ),
        windows_behaviour=(
            "Windows Terminal supports SGR mouse mode.  Legacy conhost "
            "does not support ANSI mouse escape sequences.  Mouse "
            "input on legacy console requires the Windows Console API."
        ),
        caveat=(
            "wyby uses ANSI escape sequences for mouse mode control, "
            "written to stdout.  This works on Windows Terminal but "
            "not on legacy conhost.  There is no fallback to the "
            "Windows Console API — mouse support requires a modern "
            "terminal."
        ),
    ),
    # -- Timing -----------------------------------------------------------
    PlatformDifference(
        category="timing",
        feature="monotonic_clock",
        unix_behaviour=(
            "time.monotonic() typically has sub-millisecond resolution "
            "on Linux and macOS (uses clock_gettime with CLOCK_MONOTONIC "
            "or mach_absolute_time)."
        ),
        windows_behaviour=(
            "time.monotonic() uses QueryPerformanceCounter on modern "
            "Windows, providing sub-microsecond resolution.  On some "
            "older Windows builds, resolution may be ~15 ms due to the "
            "system timer interrupt frequency."
        ),
        caveat=(
            "The ~15 ms granularity on older Windows can cause "
            "frame-time measurements to appear quantized.  The FPS "
            "counter's rolling average smooths this out.  Modern "
            "Windows 10+ generally has high-resolution timers."
        ),
    ),
    PlatformDifference(
        category="timing",
        feature="sleep_granularity",
        unix_behaviour=(
            "time.sleep() granularity is typically ~1 ms on Linux "
            "and ~1-10 ms on macOS, depending on kernel configuration."
        ),
        windows_behaviour=(
            "time.sleep() granularity defaults to ~15.6 ms (the system "
            "timer interrupt period).  timeBeginPeriod(1) can improve "
            "this to ~1 ms but affects system-wide power consumption.  "
            "Python does not call timeBeginPeriod."
        ),
        caveat=(
            "wyby's game loop uses time.sleep() for frame pacing.  On "
            "Windows, sleep may overshoot by up to ~15 ms, causing "
            "inconsistent frame timing at high tick rates.  The "
            "accumulator pattern compensates by running multiple "
            "updates per frame when the loop falls behind."
        ),
    ),
    # -- Signals ----------------------------------------------------------
    PlatformDifference(
        category="signals",
        feature="available_signals",
        unix_behaviour=(
            "SIGWINCH (terminal resize), SIGTSTP (Ctrl+Z suspend), "
            "SIGCONT (resume), SIGINT (Ctrl+C), SIGTERM (terminate) "
            "are all available.  Signal handlers run in the main thread."
        ),
        windows_behaviour=(
            "Only SIGINT, SIGTERM, and SIGABRT are available.  "
            "SIGWINCH, SIGTSTP, and SIGCONT do not exist.  Console "
            "control events (Ctrl+C, Ctrl+Break) are delivered via "
            "SetConsoleCtrlHandler, not POSIX signals."
        ),
        caveat=(
            "wyby checks for signal availability using hasattr() "
            "(e.g., hasattr(signal, 'SIGWINCH')) rather than "
            "sys.platform checks.  This handles exotic Unix-like "
            "systems correctly."
        ),
    ),
)

# Category names used in PLATFORM_DIFFERENCES, for validation and iteration.
CATEGORIES: frozenset[str] = frozenset(
    d.category for d in PLATFORM_DIFFERENCES
)


def get_differences_by_category(
    category: str,
) -> tuple[PlatformDifference, ...]:
    """Return all platform differences in a given category.

    Args:
        category: One of ``"input"``, ``"resize"``, ``"terminal"``,
            ``"timing"``, or ``"signals"``.

    Returns:
        A tuple of :class:`PlatformDifference` entries for the category.

    Raises:
        ValueError: If *category* is not a known category name.

    Caveats:
        - Returns an empty tuple if the category exists but has no
          entries (should not happen with the built-in catalog, but
          possible if the catalog is extended).
    """
    if category not in CATEGORIES:
        raise ValueError(
            f"Unknown category {category!r}.  "
            f"Known categories: {sorted(CATEGORIES)}"
        )
    return tuple(d for d in PLATFORM_DIFFERENCES if d.category == category)


# ---------------------------------------------------------------------------
# Runtime platform info
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True, slots=True)
class PlatformInfo:
    """Runtime snapshot of the current platform's capabilities.

    Created by :func:`get_platform_info`.  All fields are read-only.

    Attributes:
        platform: The value of ``sys.platform`` (e.g., ``"linux"``,
            ``"darwin"``, ``"win32"``).
        is_windows: ``True`` if running on Windows (``sys.platform == "win32"``).
        is_unix: ``True`` if running on a Unix-like system (not Windows).
        has_termios: ``True`` if the ``termios`` module is available.
        has_msvcrt: ``True`` if the ``msvcrt`` module is available.
        has_sigwinch: ``True`` if ``signal.SIGWINCH`` exists.
        has_sigtstp: ``True`` if ``signal.SIGTSTP`` exists.
        has_sigcont: ``True`` if ``signal.SIGCONT`` exists.
        input_backend: Name of the input backend that would be used
            (``"UnixInputBackend"``, ``"WindowsInputBackend"``, or
            ``"FallbackInputBackend"``).
        resize_mechanism: How resize is detected (``"sigwinch+poll"``
            on Unix, ``"poll"`` on Windows).

    Caveats:
        - This is a point-in-time snapshot.  Platform capabilities do
          not change at runtime, but this object does not track
          environment changes (e.g., ``$TERM`` being modified).
        - ``is_unix`` is ``True`` for Linux, macOS, BSDs, and other
          non-Windows platforms.  It may be ``True`` in WSL, which
          provides a Unix-compatible environment on Windows.
        - Module availability (``has_termios``, ``has_msvcrt``) is
          checked via import, not ``sys.platform``.  This handles
          edge cases like Cygwin (which has termios but runs on
          Windows) correctly.
    """

    platform: str
    is_windows: bool
    is_unix: bool
    has_termios: bool
    has_msvcrt: bool
    has_sigwinch: bool
    has_sigtstp: bool
    has_sigcont: bool
    input_backend: str
    resize_mechanism: str

    def summary(self) -> str:
        """Return a human-readable multi-line summary.

        Suitable for logging at startup or including in diagnostic
        reports alongside :func:`~wyby.diagnostics.detect_capabilities`.
        """
        lines = [
            "wyby platform info",
            "=" * 40,
            f"sys.platform     : {self.platform}",
            f"Platform type    : {'Windows' if self.is_windows else 'Unix'}",
            f"termios          : {'available' if self.has_termios else 'unavailable'}",
            f"msvcrt           : {'available' if self.has_msvcrt else 'unavailable'}",
            f"SIGWINCH         : {'available' if self.has_sigwinch else 'unavailable'}",
            f"SIGTSTP          : {'available' if self.has_sigtstp else 'unavailable'}",
            f"SIGCONT          : {'available' if self.has_sigcont else 'unavailable'}",
            f"Input backend    : {self.input_backend}",
            f"Resize mechanism : {self.resize_mechanism}",
        ]
        return "\n".join(lines)


def _check_module(name: str) -> bool:
    """Check if a module is importable without side effects."""
    try:
        __import__(name)
        return True
    except ImportError:
        return False


def _stdin_is_tty() -> bool:
    """Check if stdin is a TTY, handling redirected/pseudofile stdin.

    In environments like pytest, sys.stdin may be replaced with a
    pseudofile that raises on fileno().  This helper catches those
    errors and returns False.
    """
    try:
        return os.isatty(sys.stdin.fileno())
    except (OSError, ValueError, AttributeError):
        return False


def get_platform_info() -> PlatformInfo:
    """Detect the current platform's capabilities and return a snapshot.

    This inspects ``sys.platform``, checks for the availability of
    platform-specific modules (``termios``, ``msvcrt``), and probes
    signal availability.

    Returns:
        A :class:`PlatformInfo` instance describing the current platform.

    Caveats:
        - Module availability checks use ``__import__``, which actually
          imports the module.  This is safe for ``termios`` and
          ``msvcrt`` (they have no import-time side effects) but would
          not be appropriate for modules with side effects.
        - Call this once at startup and cache the result.  The platform
          does not change at runtime.
    """
    is_windows = sys.platform == "win32"
    has_termios = _check_module("termios")
    has_msvcrt = _check_module("msvcrt")
    has_sigwinch = hasattr(signal, "SIGWINCH")
    has_sigtstp = hasattr(signal, "SIGTSTP")
    has_sigcont = hasattr(signal, "SIGCONT")

    # Determine which input backend would be used.
    if is_windows:
        backend_name = "WindowsInputBackend"
    elif has_termios:
        backend_name = "UnixInputBackend"
    else:
        backend_name = "FallbackInputBackend"

    # Determine resize detection mechanism.
    # On Unix with SIGWINCH: signal-based + polling as backup.
    # On Windows (no SIGWINCH): polling only.
    resize_mechanism = "sigwinch+poll" if has_sigwinch else "poll"

    info = PlatformInfo(
        platform=sys.platform,
        is_windows=is_windows,
        is_unix=not is_windows,
        has_termios=has_termios,
        has_msvcrt=has_msvcrt,
        has_sigwinch=has_sigwinch,
        has_sigtstp=has_sigtstp,
        has_sigcont=has_sigcont,
        input_backend=backend_name,
        resize_mechanism=resize_mechanism,
    )
    _logger.debug("Detected platform info: %s", info)
    return info


def format_platform_report() -> str:
    """Return a comprehensive report of platform differences and current state.

    Combines :func:`get_platform_info` with the full
    :data:`PLATFORM_DIFFERENCES` catalog, highlighting which column
    (Unix or Windows) applies to the current platform.

    Returns:
        A human-readable multi-line string suitable for logging or
        display.

    Caveats:
        - The report can be long (~60 lines).  It is intended for
          diagnostic output, not in-game display.
        - Calls :func:`get_platform_info` internally, which imports
          ``termios`` or ``msvcrt`` as a side effect.
    """
    info = get_platform_info()
    lines: list[str] = []

    lines.append(info.summary())
    lines.append("")
    lines.append("Platform differences (current platform marked with >)")
    lines.append("-" * 40)

    current_category = ""
    for diff in PLATFORM_DIFFERENCES:
        if diff.category != current_category:
            current_category = diff.category
            lines.append("")
            lines.append(f"[{current_category}]")

        lines.append(f"  {diff.feature}:")
        # Mark the current platform's behaviour with '>'.
        unix_marker = ">" if info.is_unix else " "
        win_marker = ">" if info.is_windows else " "
        lines.append(f"    {unix_marker} Unix: {diff.unix_behaviour}")
        lines.append(f"    {win_marker} Windows: {diff.windows_behaviour}")
        if diff.caveat:
            lines.append(f"      Caveat: {diff.caveat}")

    return "\n".join(lines)
