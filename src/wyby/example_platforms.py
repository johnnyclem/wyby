"""Cross-platform compatibility checking for wyby examples.

This module evaluates example files for platform-specific behaviours and
reports OS-specific caveats.  It scans example source code for patterns
that indicate reliance on platform-dependent features (raw-mode input,
timer-sensitive movement, signal handling, key-repeat assumptions) and
produces a per-example, per-platform compatibility report.

The primary entry points are:

- :func:`check_example_platform` — evaluate one example against all
  platforms.
- :func:`check_all_example_platforms` — discover and evaluate all
  ``*.py`` files in the examples directory.
- :func:`format_platform_check_results` — format results as a
  human-readable table with caveats.

Supported platforms: Linux, macOS (``darwin``), Windows (``win32``).

Caveats:
    - **Detection is heuristic.**  The module searches for import
      patterns and string literals in source code, not AST analysis.
      False positives are possible if a string match appears in a
      comment or docstring that does not reflect actual usage.
    - **Caveats are framework-level, not example-specific.**  Every
      example inherits a base set of platform caveats because all
      examples share the same Engine, input, and rendering pipeline.
      The per-example analysis adds caveats only when the source
      code uses features with *additional* platform-sensitive
      behaviour beyond the baseline.
    - **No actual cross-compilation or execution.**  This module
      analyses source text on the current host.  It does not run
      examples on other platforms — it predicts platform issues
      from code patterns and documented framework behaviour.
    - **Windows caveats assume Windows 10+ with Windows Terminal.**
      Legacy ``conhost.exe`` has further limitations (no alt-screen,
      limited Unicode, no SGR mouse) that are not fully enumerated
      here.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Supported platforms
# ---------------------------------------------------------------------------

# Platform identifiers used throughout this module.
# Caveat: these are short labels, not sys.platform values.  "linux"
# covers all Linux distributions; "macos" covers all macOS versions;
# "windows" covers Windows 10+ with Windows Terminal.
PLATFORMS: tuple[str, ...] = ("linux", "macos", "windows")


# ---------------------------------------------------------------------------
# Platform caveat definitions
# ---------------------------------------------------------------------------


class PlatformCaveat:
    """A single platform-specific caveat for an example.

    Attributes:
        platform: Which OS this caveat applies to (``"linux"``,
            ``"macos"``, or ``"windows"``).
        category: Feature category (``"input"``, ``"timing"``,
            ``"signals"``, ``"terminal"``, ``"unicode"``).
        description: Human-readable description of the caveat.

    Caveats:
        - A caveat with ``platform="windows"`` does not imply the
          example is broken on Windows — it means there is a
          behavioural difference that users should be aware of.
    """

    __slots__ = ("platform", "category", "description")

    def __init__(
        self,
        *,
        platform: str,
        category: str,
        description: str,
    ) -> None:
        self.platform = platform
        self.category = category
        self.description = description

    def __repr__(self) -> str:
        return (
            f"PlatformCaveat(platform={self.platform!r}, "
            f"category={self.category!r})"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PlatformCaveat):
            return NotImplemented
        return (
            self.platform == other.platform
            and self.category == other.category
            and self.description == other.description
        )


# Base caveats that apply to every example on each platform.
# These reflect fundamental differences in how the Engine and input
# pipeline operate across OSes.
#
# Caveat: this list is maintained manually and reflects the state of
# wyby's platform abstraction layer.  If _platform.py or app.py change
# their platform strategy, these caveats may need updating.
_BASE_CAVEATS: tuple[PlatformCaveat, ...] = (
    # -- Linux ---------------------------------------------------------------
    PlatformCaveat(
        platform="linux",
        category="input",
        description=(
            "Uses termios raw mode.  If the process is killed (SIGKILL) "
            "without restoring cooked mode, the terminal is left broken.  "
            "Run 'reset' or 'stty sane' to recover."
        ),
    ),
    PlatformCaveat(
        platform="linux",
        category="signals",
        description=(
            "SIGTSTP (Ctrl+Z) suspends the process.  Raw mode must be "
            "re-entered after SIGCONT (fg) to resume input handling."
        ),
    ),
    # -- macOS ---------------------------------------------------------------
    PlatformCaveat(
        platform="macos",
        category="input",
        description=(
            "Uses termios raw mode (same as Linux).  If the process is "
            "killed without restoring cooked mode, run 'reset' to recover."
        ),
    ),
    PlatformCaveat(
        platform="macos",
        category="timing",
        description=(
            "time.sleep() granularity is ~1-10 ms on macOS, depending on "
            "kernel scheduling.  At high tick rates (>60 TPS), frame "
            "timing may be less consistent than on Linux."
        ),
    ),
    PlatformCaveat(
        platform="macos",
        category="signals",
        description=(
            "SIGTSTP (Ctrl+Z) suspends the process.  Raw mode must be "
            "re-entered after SIGCONT (fg) to resume input handling."
        ),
    ),
    # -- Windows -------------------------------------------------------------
    PlatformCaveat(
        platform="windows",
        category="input",
        description=(
            "Uses msvcrt for input.  No terminal mode switching is needed, "
            "but special keys (arrows, function keys) produce two-byte "
            "scan-code sequences instead of ANSI escapes."
        ),
    ),
    PlatformCaveat(
        platform="windows",
        category="timing",
        description=(
            "time.sleep() granularity defaults to ~15.6 ms on Windows.  "
            "At 30 TPS (33 ms/tick), this can cause occasional frame "
            "jitter.  The accumulator pattern compensates by running "
            "extra updates when the loop falls behind."
        ),
    ),
    PlatformCaveat(
        platform="windows",
        category="signals",
        description=(
            "SIGWINCH, SIGTSTP, and SIGCONT do not exist on Windows.  "
            "Terminal resize is detected by polling "
            "shutil.get_terminal_size() each tick (up to one tick of "
            "latency)."
        ),
    ),
    PlatformCaveat(
        platform="windows",
        category="terminal",
        description=(
            "Requires Windows Terminal or ConPTY (Windows 10 1903+) for "
            "alt-screen and full colour support.  Legacy conhost.exe "
            "silently ignores ANSI escape sequences."
        ),
    ),
)


# ---------------------------------------------------------------------------
# Source-code pattern detection
# ---------------------------------------------------------------------------

# Patterns to detect platform-sensitive features in example source code.
# Each entry is (compiled_regex, list_of_PlatformCaveats).
#
# Caveat: these patterns match raw source text, including comments and
# docstrings.  A match in a comment is a false positive — but since
# examples are short and comments typically describe real usage, the
# false-positive rate is low in practice.
_FEATURE_PATTERNS: tuple[tuple[re.Pattern[str], tuple[PlatformCaveat, ...]], ...] = (
    # Timer-based movement (dt-sensitive logic).
    (
        re.compile(r"move_interval|move_timer|self\._timer"),
        (
            PlatformCaveat(
                platform="windows",
                category="timing",
                description=(
                    "Timer-based movement may appear uneven due to ~15.6 ms "
                    "sleep granularity on Windows.  The accumulator pattern "
                    "in the Engine compensates, but visual jitter is possible "
                    "at high movement rates."
                ),
            ),
        ),
    ),
    # Key repeat / paddle movement.
    (
        re.compile(r"key.repeat|repeat.rate|paddle", re.IGNORECASE),
        (
            PlatformCaveat(
                platform="linux",
                category="input",
                description=(
                    "Key repeat rate is controlled by the X11/Wayland "
                    "server or the virtual console, not the terminal "
                    "emulator.  Users may need to adjust 'xset r rate' "
                    "for comfortable paddle speed."
                ),
            ),
            PlatformCaveat(
                platform="macos",
                category="input",
                description=(
                    "Key repeat rate is set in System Settings > Keyboard.  "
                    "The default repeat rate may feel slow for real-time "
                    "games.  Increasing 'Key repeat rate' improves "
                    "responsiveness."
                ),
            ),
            PlatformCaveat(
                platform="windows",
                category="input",
                description=(
                    "Key repeat rate is configured in Settings > "
                    "Accessibility > Keyboard (or Control Panel).  "
                    "msvcrt reads repeated keys from the console input "
                    "buffer, which respects the system repeat rate."
                ),
            ),
        ),
    ),
    # Random number generation (seeded vs unseeded).
    (
        re.compile(r"random\.randint|random\.choice|random\.Random"),
        (
            PlatformCaveat(
                platform="windows",
                category="timing",
                description=(
                    "Random seed behaviour is identical across platforms, "
                    "but timer-seeded randomness (default) may produce "
                    "less entropy variation on Windows due to coarser "
                    "clock resolution on older builds."
                ),
            ),
        ),
    ),
    # Unicode box-drawing or block characters.
    (
        re.compile(r"[─│┌┐└┘├┤┬┴┼█▀▄░▒▓]|box.draw|block.char", re.IGNORECASE),
        (
            PlatformCaveat(
                platform="windows",
                category="unicode",
                description=(
                    "Box-drawing and block element characters render "
                    "correctly in Windows Terminal but may display as "
                    "replacement characters (?) in legacy conhost.exe.  "
                    "Ensure the console font supports Unicode "
                    "(e.g., Cascadia Code, Consolas)."
                ),
            ),
        ),
    ),
)


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


class ExamplePlatformResult:
    """Cross-platform compatibility result for a single example.

    Attributes:
        path: Absolute path to the example file.
        platforms: Mapping of platform name to list of caveats.
        detected_features: Names of platform-sensitive features found
            in the source code.
        error: Error message if analysis failed, or ``None``.

    Caveats:
        - An empty caveat list for a platform does not mean the example
          is guaranteed to work — it means no *additional* caveats
          beyond the base set were detected.
        - ``detected_features`` is informational.  It lists the regex
          pattern labels that matched, not a precise feature inventory.
    """

    __slots__ = ("path", "platforms", "detected_features", "error")

    def __init__(
        self,
        *,
        path: str,
        platforms: dict[str, list[PlatformCaveat]] | None = None,
        detected_features: list[str] | None = None,
        error: str | None = None,
    ) -> None:
        self.path = path
        self.platforms = platforms or {p: [] for p in PLATFORMS}
        self.detected_features = detected_features or []
        self.error = error

    @property
    def filename(self) -> str:
        """Base filename without directory components."""
        return Path(self.path).name

    @property
    def ok(self) -> bool:
        """Whether analysis completed without error."""
        return self.error is None

    def caveats_for(self, platform: str) -> list[PlatformCaveat]:
        """Return caveats for a specific platform.

        Args:
            platform: One of ``"linux"``, ``"macos"``, ``"windows"``.

        Raises:
            KeyError: If *platform* is not a known platform.
        """
        return self.platforms[platform]

    @property
    def total_caveats(self) -> int:
        """Total number of caveats across all platforms."""
        return sum(len(v) for v in self.platforms.values())

    def __repr__(self) -> str:
        status = "OK" if self.ok else "FAIL"
        counts = {p: len(c) for p, c in self.platforms.items()}
        return (
            f"ExamplePlatformResult(filename={self.filename!r}, "
            f"status={status}, caveats={counts})"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ExamplePlatformResult):
            return NotImplemented
        return (
            self.path == other.path
            and self.platforms == other.platforms
            and self.detected_features == other.detected_features
            and self.error == other.error
        )


# ---------------------------------------------------------------------------
# Analysis functions
# ---------------------------------------------------------------------------


def _default_examples_dir() -> Path:
    """Resolve the default examples directory relative to this module.

    Caveats:
        - Relies on the source tree layout (``src/wyby/`` ->
          ``../../examples/``).  Not available in wheel installs.
    """
    return Path(__file__).resolve().parent.parent.parent / "examples"


def _detect_features(source: str) -> tuple[list[str], list[PlatformCaveat]]:
    """Scan source text for platform-sensitive feature patterns.

    Returns:
        A tuple of (feature names, additional caveats).

    Caveats:
        - Matches are against raw source text including comments.
        - Duplicate caveats are not deduplicated here — the caller
          is responsible if needed.
    """
    features: list[str] = []
    caveats: list[PlatformCaveat] = []

    for pattern, pattern_caveats in _FEATURE_PATTERNS:
        if pattern.search(source):
            # Use the pattern's regex as the feature name.
            features.append(pattern.pattern)
            caveats.extend(pattern_caveats)

    return features, caveats


def check_example_platform(path: str | Path) -> ExamplePlatformResult:
    """Evaluate a single example file for cross-platform compatibility.

    Reads the example source code and checks for patterns that indicate
    platform-sensitive behaviour.  Combines base caveats (which apply
    to all examples) with feature-specific caveats detected in the
    source.

    Args:
        path: Path to the example ``.py`` file.

    Returns:
        An :class:`ExamplePlatformResult` with per-platform caveats.

    Caveats:
        - The file is read as UTF-8 text.  Non-UTF-8 files will
          produce an error result.
        - Analysis is static (source text scanning).  It does not
          import or execute the example.
    """
    resolved = str(Path(path).resolve())
    result = ExamplePlatformResult(path=resolved)

    try:
        source = Path(resolved).read_text(encoding="utf-8")
    except FileNotFoundError:
        result.error = f"File not found: {resolved}"
        return result
    except UnicodeDecodeError as exc:
        result.error = f"Cannot read file (encoding error): {exc}"
        return result

    # Start with base caveats for each platform.
    platform_caveats: dict[str, list[PlatformCaveat]] = {
        p: [c for c in _BASE_CAVEATS if c.platform == p]
        for p in PLATFORMS
    }

    # Detect feature-specific caveats.
    features, extra_caveats = _detect_features(source)
    result.detected_features = features

    for caveat in extra_caveats:
        platform_caveats[caveat.platform].append(caveat)

    result.platforms = platform_caveats
    _logger.debug(
        "Platform check for %s: features=%s, total_caveats=%d",
        resolved,
        features,
        result.total_caveats,
    )
    return result


def check_all_example_platforms(
    directory: str | Path | None = None,
) -> list[ExamplePlatformResult]:
    """Discover and evaluate all ``*.py`` files in a directory.

    Args:
        directory: Path to scan.  Defaults to the bundled ``examples/``
            directory.

    Returns:
        A list of :class:`ExamplePlatformResult` instances, sorted by
        filename.  Returns an empty list if the directory does not
        exist.

    Caveats:
        - Only top-level ``*.py`` files are scanned; subdirectories
          are not recursed.
        - Each file is analysed independently.
    """
    if directory is None:
        directory = _default_examples_dir()

    dir_path = Path(directory)
    if not dir_path.is_dir():
        _logger.debug(
            "Examples directory does not exist: %s", dir_path,
        )
        return []

    results: list[ExamplePlatformResult] = []
    for entry in sorted(dir_path.iterdir()):
        if not entry.is_file() or entry.suffix != ".py":
            continue
        result = check_example_platform(entry)
        results.append(result)

    _logger.debug(
        "Platform-checked %d example(s) from %s",
        len(results),
        dir_path,
    )
    return results


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------


def format_platform_check_results(
    results: list[ExamplePlatformResult],
) -> str:
    """Format cross-platform results as a human-readable report.

    Produces a table showing caveat counts per platform for each
    example, followed by the full caveat listing.

    Args:
        results: List of :class:`ExamplePlatformResult` instances.

    Returns:
        A multi-line string.  Returns ``"No examples found."`` if
        *results* is empty.

    Caveats:
        - The report can be long for many examples.  Consider
          filtering results before formatting for focused output.
    """
    if not results:
        return "No examples found."

    name_width = max(len(r.filename) for r in results)
    name_width = max(name_width, len("Example"))

    # Table header.
    header = (
        f"{'Example':<{name_width}}  "
        f"{'Linux':>6}  {'macOS':>6}  {'Windows':>8}  {'Status':>6}"
    )
    separator = "-" * len(header)
    lines = [header, separator]

    for r in results:
        linux_count = str(len(r.caveats_for("linux")))
        macos_count = str(len(r.caveats_for("macos")))
        windows_count = str(len(r.caveats_for("windows")))
        status = "OK" if r.ok else "FAIL"

        lines.append(
            f"{r.filename:<{name_width}}  "
            f"{linux_count:>6}  {macos_count:>6}  "
            f"{windows_count:>8}  {status:>6}"
        )

    lines.append(separator)

    # Per-example caveat details.
    lines.append("")
    lines.append("Platform caveats by example:")
    lines.append("")

    for r in results:
        if not r.ok:
            lines.append(f"  {r.filename}: ERROR — {r.error}")
            continue

        lines.append(f"  {r.filename}:")
        for platform in PLATFORMS:
            caveats = r.caveats_for(platform)
            if not caveats:
                continue
            lines.append(f"    [{platform}]")
            for caveat in caveats:
                lines.append(f"      - [{caveat.category}] {caveat.description}")
        lines.append("")

    # Cross-platform summary.
    lines.append("Cross-platform notes:")
    lines.append(
        "  - All examples require a real TTY for interactive use."
    )
    lines.append(
        "  - On Windows, use Windows Terminal (not legacy conhost) "
        "for best results."
    )
    lines.append(
        "  - On Linux/macOS, if the terminal is left in raw mode "
        "after a crash, run 'reset' or 'stty sane'."
    )
    lines.append(
        "  - Key repeat rate is OS-controlled and affects paddle/"
        "movement responsiveness in real-time games."
    )

    return "\n".join(lines)
