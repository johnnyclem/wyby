"""Font and terminal variance detection, catalog, and advisory utilities.

Terminal emulators render the same Unicode text differently depending on
the font, the terminal's text shaping engine, and platform-specific
rendering decisions.  This module catalogues known variance issues and
provides utilities for detecting, reporting, and mitigating them.

The primary concerns are:

1. **Cell aspect ratio.**  Terminal character cells are not square —
   they are typically ~2× taller than wide.  The exact ratio depends
   on the font's metrics and the terminal's line-spacing setting.
   There is no universally supported way to query cell pixel dimensions
   at runtime.

2. **Character width disagreement.**  Unicode assigns each character an
   East Asian Width property, but terminals interpret this inconsistently.
   Ambiguous-width characters may occupy 1 or 2 columns depending on
   the terminal, the locale, and the font.  Emoji width is especially
   unreliable (see :mod:`wyby.unicode` and :mod:`wyby.render_warnings`).

3. **Glyph coverage.**  Monospace fonts vary in which Unicode code
   points they contain glyphs for.  Missing glyphs produce replacement
   characters (□, ?, tofu) at unpredictable widths, corrupting grid
   alignment.

4. **Ligature interference.**  Programming-ligature fonts (Fira Code,
   JetBrains Mono, Cascadia Code) may merge box-drawing characters or
   other adjacent symbols into ligature glyphs, breaking cell-grid
   alignment.

5. **Line spacing / cell padding.**  Some terminals apply extra
   vertical or horizontal padding to cells.  This changes the effective
   aspect ratio and can cause half-block pixel art (▀▄) to show gaps.

6. **Text shaping.**  Terminals that perform HarfBuzz-based text
   shaping (kitty, WezTerm) may handle complex grapheme clusters
   differently from terminals that use simpler rendering (Alacritty,
   Terminal.app).

Caveats
-------
- **No reliable auto-detection of font metrics.**  Some terminals
  respond to the ``\\e[16t`` (report cell size) or ``\\e[14t`` (report
  window pixel size) xterm escape sequences, but support is inconsistent.
  Sending query sequences to stdout also conflicts with game input
  handling because the terminal's response arrives on stdin.  This
  module therefore does **not** attempt escape-sequence queries and
  instead provides heuristic defaults.
- **The cell aspect ratio of 2.0 is a widely-used approximation.**
  Actual values range from ~1.6 to ~2.4 depending on font and
  terminal.  See :func:`estimate_cell_aspect_ratio` for details.
- **Terminal identification is best-effort.**  Inside ``tmux`` or
  ``screen``, the detected terminal may be the multiplexer, not the
  outer terminal.  Font-related issues are properties of the outer
  terminal + font combination, which cannot be detected programmatically
  in that scenario.
- **All advisories are informational.**  They help game developers
  understand rendering variance and design defensively.  They do not
  guarantee correct rendering on any specific terminal.
"""

from __future__ import annotations

import dataclasses
import logging
import struct
import sys

from wyby.diagnostics import TerminalCapabilities, detect_capabilities

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Default cell aspect ratio
# ---------------------------------------------------------------------------

# The conventional approximation for terminal cell height:width.
# Most monospace fonts at typical sizes produce cells roughly twice as
# tall as they are wide.  This is used as a fallback when the actual
# aspect ratio cannot be detected.
#
# Caveat: this default works well for fonts like Menlo, Monaco,
# DejaVu Sans Mono, Consolas, and SF Mono at common sizes (12–16 pt).
# Fonts with unusual metrics (e.g. bitmap fonts, condensed faces) or
# terminals with custom line-spacing may diverge significantly.
DEFAULT_CELL_ASPECT_RATIO: float = 2.0

# Sane bounds for cell aspect ratio.  Values outside this range
# almost certainly indicate a detection error, not a real terminal.
_MIN_ASPECT_RATIO: float = 1.0
_MAX_ASPECT_RATIO: float = 4.0


# ---------------------------------------------------------------------------
# FontVarianceIssue catalog
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class FontVarianceIssue:
    """A documented font or terminal rendering variance issue.

    Each instance describes a specific way in which terminal rendering
    may differ from what the developer expects.

    Attributes:
        category: Broad category (``"aspect_ratio"``, ``"glyph_width"``,
            ``"glyph_coverage"``, ``"ligatures"``, ``"line_spacing"``,
            ``"text_shaping"``).
        issue: Short identifier (e.g. ``"cell_not_square"``).
        description: Human-readable explanation of the issue.
        affected_terminals: Terminals known to be affected, or ``"all"``
            if the issue is universal.
        mitigation: Recommended mitigation strategy.
    """

    category: str
    issue: str
    description: str
    affected_terminals: str
    mitigation: str


# The catalog of known font/terminal variance issues.  Entries are
# intentionally terse; the module docstring and docs/font_terminal_variance.md
# provide full discussion.
#
# Caveat: this catalog is not exhaustive.  Terminal rendering behaviour
# is an empirical domain — new terminals, font updates, and OS changes
# can introduce new variance.  Treat this as a starting point, not a
# comprehensive compatibility matrix.
FONT_VARIANCE_ISSUES: tuple[FontVarianceIssue, ...] = (
    FontVarianceIssue(
        category="aspect_ratio",
        issue="cell_not_square",
        description=(
            "Terminal character cells are rectangular, not square.  "
            "Typical aspect ratio (height:width) is ~2:1.  Images and "
            "pixel art mapped 1:1 will appear vertically stretched."
        ),
        affected_terminals="all",
        mitigation=(
            "Use correct_aspect_ratio() to halve image height before "
            "conversion.  Accept ~2.0 as the default ratio or allow "
            "users to tune it."
        ),
    ),
    FontVarianceIssue(
        category="aspect_ratio",
        issue="aspect_ratio_varies_by_font",
        description=(
            "The exact cell aspect ratio depends on the font's ascent, "
            "descent, and advance width metrics.  A compact font like "
            "Iosevka may have a ratio of ~2.4; a wide font like "
            "Source Code Pro may be ~1.7.  The terminal's line-spacing "
            "setting further modifies the effective ratio."
        ),
        affected_terminals="all",
        mitigation=(
            "Use the default ratio of 2.0 for broad compatibility.  "
            "Provide a configuration option for users who need precise "
            "aspect correction for their specific font."
        ),
    ),
    FontVarianceIssue(
        category="aspect_ratio",
        issue="no_reliable_auto_detection",
        description=(
            "There is no universally supported way to query the terminal "
            "for cell pixel dimensions.  Some terminals support xterm "
            "escape sequences (\\e[16t, \\e[14t), but coverage is "
            "inconsistent and sending queries conflicts with game input."
        ),
        affected_terminals="all",
        mitigation=(
            "Use heuristic defaults (2.0 aspect ratio).  If the "
            "terminal supports pixel-size reporting, "
            "estimate_cell_aspect_ratio() can attempt ioctl-based "
            "detection on supported platforms."
        ),
    ),
    FontVarianceIssue(
        category="glyph_width",
        issue="ambiguous_width_characters",
        description=(
            "Characters with Unicode East Asian Width 'A' (Ambiguous) "
            "— including some Greek, Cyrillic, and mathematical symbols "
            "— may render at width 1 or 2 depending on the terminal's "
            "locale and the font.  CJK-locale terminals typically use "
            "width 2; Western-locale terminals use width 1."
        ),
        affected_terminals="all (locale-dependent)",
        mitigation=(
            "wyby treats Ambiguous characters as width 1.  Avoid "
            "relying on specific widths for Ambiguous characters in "
            "game tiles.  Use ASCII, box-drawing, or block elements "
            "for reliable width."
        ),
    ),
    FontVarianceIssue(
        category="glyph_width",
        issue="emoji_width_disagreement",
        description=(
            "Emoji may render at 1 or 2 columns depending on the "
            "terminal, the emoji presentation (text vs. emoji via "
            "VS15/VS16), and whether the terminal uses the Unicode "
            "Standard's width assignments.  Multi-codepoint emoji "
            "(ZWJ sequences, flags, skin tones) are even less "
            "predictable."
        ),
        affected_terminals="all",
        mitigation=(
            "Avoid emoji in game tiles where column alignment matters.  "
            "Use ASCII, box-drawing, and block elements.  If emoji are "
            "needed, use check_emoji_warning() to alert developers."
        ),
    ),
    FontVarianceIssue(
        category="glyph_coverage",
        issue="missing_glyphs_tofu",
        description=(
            "When the terminal's font lacks a glyph for a character, "
            "the terminal displays a replacement: a box (□), a question "
            "mark (?), or an empty rectangle ('tofu').  The replacement "
            "character's width may differ from the intended character's "
            "width, corrupting grid alignment."
        ),
        affected_terminals="all (font-dependent)",
        mitigation=(
            "Stick to characters that are present in virtually all "
            "monospace fonts: ASCII (U+0020–U+007E), box-drawing "
            "(U+2500–U+257F), and block elements (U+2580–U+259F).  "
            "Test with the TestCard to verify glyph coverage."
        ),
    ),
    FontVarianceIssue(
        category="glyph_coverage",
        issue="font_fallback_chain",
        description=(
            "Most terminals use a font fallback chain: if the primary "
            "font lacks a glyph, the terminal tries secondary fonts.  "
            "The fallback font may have different metrics (cell width, "
            "baseline), causing misaligned or overlapping glyphs."
        ),
        affected_terminals="all",
        mitigation=(
            "Use the TestCard to check that CJK, box-drawing, and "
            "block elements render at the expected width with the "
            "user's font configuration."
        ),
    ),
    FontVarianceIssue(
        category="ligatures",
        issue="ligature_box_drawing",
        description=(
            "Programming-ligature fonts (Fira Code, JetBrains Mono, "
            "Cascadia Code, Hasklig) may combine adjacent box-drawing "
            "characters into ligature glyphs.  This merges what should "
            "be separate cell characters into a single visual glyph, "
            "breaking grid alignment."
        ),
        affected_terminals=(
            "iTerm2, kitty, WezTerm, and others with ligature support "
            "when using ligature-enabled fonts"
        ),
        mitigation=(
            "Recommend users disable ligatures in their terminal "
            "settings when playing wyby games, or use a non-ligature "
            "monospace font.  Alternatively, insert zero-width spaces "
            "or invisible characters between box-drawing chars to "
            "prevent ligation (not recommended — fragile)."
        ),
    ),
    FontVarianceIssue(
        category="line_spacing",
        issue="half_block_gaps",
        description=(
            "Half-block characters (▀ U+2580, ▄ U+2584) are used to "
            "pack two vertical 'pixels' per cell.  If the terminal "
            "applies extra line spacing, visible gaps appear between "
            "rows, breaking the seamless pixel-art effect."
        ),
        affected_terminals="all (line-spacing dependent)",
        mitigation=(
            "Recommend users set line spacing to 1.0 (100%) in their "
            "terminal settings.  Document this requirement for games "
            "that rely on half-block rendering."
        ),
    ),
    FontVarianceIssue(
        category="line_spacing",
        issue="custom_cell_padding",
        description=(
            "Some terminals (kitty, WezTerm) allow per-cell padding "
            "configuration.  Non-zero padding changes the effective "
            "cell aspect ratio and can introduce gaps in block-element "
            "art."
        ),
        affected_terminals="kitty, WezTerm",
        mitigation=(
            "Document that cell padding should be zero for best "
            "rendering results.  Provide aspect-ratio tuning for "
            "users who cannot change their terminal settings."
        ),
    ),
    FontVarianceIssue(
        category="text_shaping",
        issue="harfbuzz_vs_simple",
        description=(
            "Terminals using HarfBuzz text shaping (kitty, WezTerm) "
            "handle complex grapheme clusters (combining marks, ZWJ "
            "sequences) differently from terminals with simpler "
            "rendering (Alacritty, Terminal.app).  This can cause "
            "width and positioning differences for the same text."
        ),
        affected_terminals="varies by terminal rendering engine",
        mitigation=(
            "For game tiles, use only single-codepoint characters that "
            "do not trigger complex text shaping.  Use the TestCard "
            "wide-character and emoji tests to verify behaviour."
        ),
    ),
)


ISSUE_CATEGORIES: frozenset[str] = frozenset(
    issue.category for issue in FONT_VARIANCE_ISSUES
)
"""All distinct category names in :data:`FONT_VARIANCE_ISSUES`."""


# ---------------------------------------------------------------------------
# Filtering and lookup
# ---------------------------------------------------------------------------


def get_issues_by_category(
    category: str,
) -> tuple[FontVarianceIssue, ...]:
    """Return all font variance issues in the given category.

    Args:
        category: One of the category names in :data:`ISSUE_CATEGORIES`.

    Returns:
        A tuple of :class:`FontVarianceIssue` instances with matching
        category.

    Raises:
        ValueError: If *category* is not a recognised category name.

    Caveats:
        - Categories are derived from the built-in catalog.  Custom
          issues added at runtime are not supported.
    """
    if category not in ISSUE_CATEGORIES:
        raise ValueError(
            f"Unknown category {category!r}.  "
            f"Known categories: {sorted(ISSUE_CATEGORIES)}"
        )
    return tuple(i for i in FONT_VARIANCE_ISSUES if i.category == category)


def get_issues_for_terminal(
    terminal_program: str | None,
) -> tuple[FontVarianceIssue, ...]:
    """Return font variance issues relevant to the given terminal.

    Issues with ``affected_terminals="all"`` are always included.
    Issues that mention the terminal name (case-insensitive substring
    match) are also included.

    Args:
        terminal_program: Terminal program identifier as returned by
            :attr:`TerminalCapabilities.terminal_program`, or ``None``
            for an unidentified terminal.

    Returns:
        A tuple of matching :class:`FontVarianceIssue` instances.

    Caveats:
        - Matching is heuristic (substring search on
          ``affected_terminals``).  An issue may be relevant to a
          terminal even if it is not listed in ``affected_terminals``.
        - For unidentified terminals (``None``), returns all
          universal issues (``affected_terminals`` containing "all").
    """
    results: list[FontVarianceIssue] = []
    terminal_lower = terminal_program.lower() if terminal_program else ""
    for issue in FONT_VARIANCE_ISSUES:
        affected = issue.affected_terminals.lower()
        if "all" in affected:
            results.append(issue)
        elif terminal_lower and terminal_lower in affected:
            results.append(issue)
    return tuple(results)


# ---------------------------------------------------------------------------
# Cell aspect ratio estimation
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class CellGeometry:
    """Detected or estimated terminal cell dimensions.

    Attributes:
        cell_width_px: Cell width in pixels, or ``None`` if unknown.
        cell_height_px: Cell height in pixels, or ``None`` if unknown.
        aspect_ratio: Cell height / cell width.  Falls back to
            :data:`DEFAULT_CELL_ASPECT_RATIO` if pixel dimensions
            are unavailable.
        detected: ``True`` if pixel dimensions were detected from
            the terminal, ``False`` if the aspect ratio is a
            heuristic default.
    """

    cell_width_px: int | None
    cell_height_px: int | None
    aspect_ratio: float
    detected: bool


def _try_ioctl_cell_size() -> tuple[int, int, int, int] | None:
    """Attempt to read terminal pixel dimensions via TIOCGWINSZ ioctl.

    Returns (rows, cols, xpixel, ypixel) if successful, or None.

    Caveats:
        - Only works on Unix-like systems with a real TTY on stdout.
        - Some terminals return 0 for xpixel/ypixel even when the
          ioctl succeeds (e.g. Linux virtual console, some tmux
          configurations).
        - Over SSH, pixel dimensions depend on the SSH client passing
          them through (many do not).
    """
    if sys.platform == "win32":
        return None

    try:
        import fcntl
        import termios
    except ImportError:
        return None

    try:
        # TIOCGWINSZ returns: (rows, cols, xpixel, ypixel) as 4 unsigned shorts.
        result = fcntl.ioctl(
            sys.stdout.fileno(),
            termios.TIOCGWINSZ,
            b"\x00" * 8,
        )
        rows, cols, xpixel, ypixel = struct.unpack("HHHH", result)
        if rows > 0 and cols > 0 and xpixel > 0 and ypixel > 0:
            return (rows, cols, xpixel, ypixel)
    except (OSError, ValueError):
        pass

    return None


def estimate_cell_aspect_ratio() -> CellGeometry:
    """Estimate the terminal's cell aspect ratio (height / width).

    Attempts ioctl-based detection on Unix; falls back to
    :data:`DEFAULT_CELL_ASPECT_RATIO` (2.0) if detection is
    unavailable or returns unusable data.

    Returns:
        A :class:`CellGeometry` describing the detected or estimated
        cell dimensions.

    Caveats:
        - Detection via ioctl (``TIOCGWINSZ``) only works on Unix-like
          systems where stdout is connected to a real TTY.  In pytest,
          CI, piped output, or on Windows, this falls back to the
          default.
        - Even when ioctl succeeds, some terminals report 0 for pixel
          dimensions.  This also triggers the fallback.
        - The aspect ratio is a point-in-time snapshot.  It does not
          update if the user changes font or terminal settings.
        - Inside ``tmux``/``screen``, the pixel dimensions may reflect
          the multiplexer's virtual terminal, not the outer terminal.
    """
    ioctl_result = _try_ioctl_cell_size()
    if ioctl_result is not None:
        rows, cols, xpixel, ypixel = ioctl_result
        cell_w = xpixel / cols
        cell_h = ypixel / rows
        if cell_w > 0:
            ratio = cell_h / cell_w
            # Sanity check — reject implausible values.
            if _MIN_ASPECT_RATIO <= ratio <= _MAX_ASPECT_RATIO:
                _logger.debug(
                    "Detected cell geometry: %dx%d px (ratio %.2f) via ioctl",
                    int(cell_w),
                    int(cell_h),
                    ratio,
                )
                return CellGeometry(
                    cell_width_px=int(cell_w),
                    cell_height_px=int(cell_h),
                    aspect_ratio=round(ratio, 3),
                    detected=True,
                )
            else:
                _logger.debug(
                    "Detected aspect ratio %.2f outside sane range "
                    "[%.1f, %.1f]; using default",
                    ratio,
                    _MIN_ASPECT_RATIO,
                    _MAX_ASPECT_RATIO,
                )

    _logger.debug(
        "Cell pixel dimensions not available; using default aspect "
        "ratio %.1f",
        DEFAULT_CELL_ASPECT_RATIO,
    )
    return CellGeometry(
        cell_width_px=None,
        cell_height_px=None,
        aspect_ratio=DEFAULT_CELL_ASPECT_RATIO,
        detected=False,
    )


# ---------------------------------------------------------------------------
# Advisory report
# ---------------------------------------------------------------------------


def check_font_variance_warnings(
    caps: TerminalCapabilities | None = None,
) -> list[str]:
    """Return a list of font/terminal variance warnings for the current environment.

    Examines the detected terminal capabilities and returns human-readable
    warning strings for applicable variance issues.  Returns an empty list
    if no specific warnings apply (though universal issues always exist).

    Args:
        caps: Pre-detected :class:`~wyby.diagnostics.TerminalCapabilities`.
            If ``None``, :func:`~wyby.diagnostics.detect_capabilities` is
            called.

    Returns:
        A list of warning strings.  May be empty if the terminal is
        unidentified and no terminal-specific warnings apply (universal
        issues are included in the report, not as warnings).

    Caveats:
        - Warnings are based on the terminal program name only.  Font
          and font-configuration information is not available at
          runtime, so font-specific issues (ligatures, glyph coverage)
          are surfaced as general advisories.
        - An empty list does **not** mean the terminal is free of
          rendering variance — only that no terminal-specific warnings
          were triggered.
    """
    if caps is None:
        caps = detect_capabilities()

    warnings: list[str] = []
    terminal = caps.terminal_program
    terminal_lower = terminal.lower() if terminal else ""

    # Ligature warning for terminals that support ligatures.
    ligature_terminals = {"iterm2", "iterm.app", "kitty", "wezterm"}
    if terminal_lower in ligature_terminals:
        warnings.append(
            f"{terminal} supports font ligatures.  If using a "
            f"ligature-enabled font (Fira Code, JetBrains Mono, etc.), "
            f"box-drawing characters may be merged into ligature glyphs, "
            f"breaking grid alignment.  Consider disabling ligatures or "
            f"using a non-ligature font."
        )

    # Cell padding warning for terminals that support it.
    padding_terminals = {"kitty", "wezterm"}
    if terminal_lower in padding_terminals:
        warnings.append(
            f"{terminal} supports custom cell padding.  Non-zero padding "
            f"changes the effective cell aspect ratio and may introduce "
            f"gaps in block-element art.  Set cell padding to zero for "
            f"best rendering results."
        )

    # Terminal.app truecolor downgrade.
    if terminal_lower == "apple_terminal":
        warnings.append(
            "Terminal.app does not support truecolor.  Colours will be "
            "silently downgraded to 256 colours.  Bold text may render "
            "as bright colour instead of increased weight."
        )

    # tmux/screen multiplexer warning.
    if terminal_lower in ("tmux", "screen"):
        warnings.append(
            f"Running inside {terminal}.  Font variance issues depend on "
            f"the outer terminal, which cannot be detected from within "
            f"the multiplexer.  Cell pixel dimensions and font metrics "
            f"may be inaccurate."
        )

    return warnings


def format_font_variance_report(
    caps: TerminalCapabilities | None = None,
) -> str:
    """Return a comprehensive human-readable font/terminal variance report.

    The report includes detected cell geometry, terminal-specific
    warnings, and the full catalog of known variance issues grouped
    by category.

    Args:
        caps: Pre-detected :class:`~wyby.diagnostics.TerminalCapabilities`.
            If ``None``, :func:`~wyby.diagnostics.detect_capabilities` is
            called.

    Returns:
        A multi-line string suitable for logging or printing.

    Caveats:
        - Calls :func:`estimate_cell_aspect_ratio` and
          :func:`detect_capabilities` internally.  These read
          environment variables and may perform ioctl calls — do not
          call per-frame.
        - The report is informational.  It describes known variance
          issues and mitigations but does not guarantee correct
          rendering on any specific terminal.
    """
    if caps is None:
        caps = detect_capabilities()

    geometry = estimate_cell_aspect_ratio()
    warnings = check_font_variance_warnings(caps)

    lines: list[str] = []
    lines.append("wyby font/terminal variance report")
    lines.append("=" * 50)
    lines.append("")

    # Terminal info.
    lines.append(
        f"Terminal        : {caps.terminal_program or '(unknown)'}"
    )
    lines.append(f"Size            : {caps.columns}x{caps.rows}")
    lines.append(f"Colour support  : {caps.color_support.name}")
    lines.append(f"UTF-8           : {caps.utf8_supported}")
    lines.append("")

    # Cell geometry.
    lines.append("Cell geometry")
    lines.append("-" * 30)
    if geometry.detected:
        lines.append(
            f"  Cell size     : {geometry.cell_width_px}x"
            f"{geometry.cell_height_px} px (detected)"
        )
    else:
        lines.append("  Cell size     : unknown (using heuristic)")
    lines.append(f"  Aspect ratio  : {geometry.aspect_ratio:.2f}")
    lines.append("")

    # Terminal-specific warnings.
    if warnings:
        lines.append("Warnings for this terminal")
        lines.append("-" * 30)
        for w in warnings:
            lines.append(f"  ! {w}")
        lines.append("")

    # Full issue catalog by category.
    lines.append("Known font/terminal variance issues")
    lines.append("-" * 30)
    for category in sorted(ISSUE_CATEGORIES):
        lines.append(f"  [{category}]")
        for issue in get_issues_by_category(category):
            lines.append(f"    {issue.issue}: {issue.description}")
            lines.append(f"      Affected: {issue.affected_terminals}")
            lines.append(f"      Mitigation: {issue.mitigation}")
        lines.append("")

    return "\n".join(lines)


def log_font_variance_warnings(
    caps: TerminalCapabilities | None = None,
) -> list[str]:
    """Check for font variance issues and log any warnings.

    Convenience wrapper around :func:`check_font_variance_warnings`
    that logs each warning at ``WARNING`` level.

    Args:
        caps: Pre-detected :class:`~wyby.diagnostics.TerminalCapabilities`.
            If ``None``, :func:`~wyby.diagnostics.detect_capabilities` is
            called.

    Returns:
        The list of warning strings (same as
        :func:`check_font_variance_warnings`).
    """
    warnings = check_font_variance_warnings(caps)
    for w in warnings:
        _logger.warning("Font variance: %s", w)
    if not warnings:
        _logger.debug("No terminal-specific font variance warnings.")
    return warnings
