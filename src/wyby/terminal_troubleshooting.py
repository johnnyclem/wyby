"""Troubleshooting guide for common terminal issues with wyby.

This module provides a structured catalog of common terminal problems
encountered when running wyby games, along with diagnostic checks,
symptoms, and recommended fixes.

The primary entry points are:

- :data:`TROUBLESHOOTING_ENTRIES` — the complete catalog of
  :class:`TroubleshootingEntry` items covering known terminal issues.
- :data:`TROUBLESHOOTING_CATEGORIES` — the set of all category names.
- :func:`get_entries_by_category` — filter entries by category.
- :func:`diagnose_terminal` — run automated checks against the current
  terminal and return a list of :class:`DiagnosticResult` findings.
- :func:`format_troubleshooting_guide` — render the full guide as Markdown.
- :func:`format_troubleshooting_for_category` — render a single category.

Caveats:
    - Automated diagnosis (:func:`diagnose_terminal`) is **best-effort**.
      It checks environment variables and OS APIs but cannot probe the
      terminal emulator's internal capabilities.  A clean diagnostic
      report does not guarantee flawless rendering.
    - Some issues (e.g., font ligatures, emoji width) cannot be detected
      programmatically — they depend on the terminal's font stack and
      rendering engine.  These are documented in the catalog but not
      covered by :func:`diagnose_terminal`.
    - This catalog is maintained manually.  New terminal emulators or
      OS updates may introduce issues not yet documented here.
    - The catalog covers wyby v0.1.0dev0.  Some entries may become
      outdated as the framework and terminal ecosystem evolve.
"""

from __future__ import annotations

import dataclasses
import logging
import os

from wyby.diagnostics import (
    ColorSupport,
    TerminalCapabilities,
    detect_capabilities,
)

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class TroubleshootingEntry:
    """A documented terminal issue with symptoms and recommended fix.

    Attributes:
        category: Broad area (e.g., ``"display"``, ``"input"``,
            ``"color"``, ``"performance"``, ``"environment"``).
        symptom: Short human-readable label describing what the user
            sees (e.g., ``"Characters overlap or misalign"``).
        cause: Explanation of why this happens.
        fix: Recommended steps to resolve the issue.
        caveat: Optional additional context or edge-case note.

    Caveats:
        - ``category`` values are lowercase strings, not an enum.
        - ``fix`` describes the *best known* mitigation, not a
          guaranteed solution.  Terminal behaviour varies widely.
    """

    category: str
    symptom: str
    cause: str
    fix: str
    caveat: str | None = None


@dataclasses.dataclass(frozen=True)
class DiagnosticResult:
    """A single finding from :func:`diagnose_terminal`.

    Attributes:
        check: Short name of the check that was run.
        passed: ``True`` if no issue was detected.
        message: Human-readable description of the finding.
        suggestion: Recommended action if the check failed, or ``None``.

    Caveats:
        - A ``passed=True`` result means no issue was *detected*, not
          that the terminal is guaranteed to work correctly.  Some
          problems cannot be detected programmatically.
    """

    check: str
    passed: bool
    message: str
    suggestion: str | None = None


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------

# Caveat: this catalog is maintained manually.  It reflects
# wyby v0.1.0dev0.  Terminal emulator updates, new platforms, or
# changed framework behaviour may require updates here.

TROUBLESHOOTING_ENTRIES: tuple[TroubleshootingEntry, ...] = (
    # -- Display issues -------------------------------------------------------
    TroubleshootingEntry(
        category="display",
        symptom="Characters overlap or grid is misaligned",
        cause=(
            "The terminal font has ligatures enabled.  Programming-ligature "
            "fonts (Fira Code, JetBrains Mono, Cascadia Code) merge adjacent "
            "box-drawing or operator characters into ligature glyphs, breaking "
            "the fixed-width cell grid that wyby depends on."
        ),
        fix=(
            "Disable ligatures in the terminal emulator's font settings, or "
            "switch to a monospace font without ligatures (e.g., Menlo, "
            "Consolas, DejaVu Sans Mono, Liberation Mono)."
        ),
        caveat=(
            "Some terminals (e.g., kitty) allow disabling ligatures per-font "
            "via configuration.  Others require choosing a different font "
            "entirely."
        ),
    ),
    TroubleshootingEntry(
        category="display",
        symptom="Emoji render at wrong width or cause row shifts",
        cause=(
            "Terminal emulators disagree on emoji display width.  The Unicode "
            "standard assigns most emoji a width of 2 (East Asian Width 'W'), "
            "but some terminals render them at 1 column.  Multi-codepoint "
            "sequences (ZWJ, flags, skin tones) are especially inconsistent.  "
            "wyby's one-character-per-cell model cannot faithfully represent "
            "multi-codepoint emoji."
        ),
        fix=(
            "Avoid emoji in game tile sets and cell buffer content.  Use "
            "ASCII, box-drawing characters (U+2500-U+257F), and block "
            "elements (U+2580-U+259F) instead.  These have consistent "
            "single-cell width across all terminals."
        ),
        caveat=(
            "Even terminals that handle simple emoji correctly may fail on "
            "ZWJ sequences or flag emoji.  There is no reliable way to "
            "detect emoji width support programmatically."
        ),
    ),
    TroubleshootingEntry(
        category="display",
        symptom="Screen flickers during gameplay",
        cause=(
            "Rich's Live display re-renders the entire frame on each "
            "refresh.  If the grid is large or has many individually styled "
            "cells, the terminal cannot parse and render the ANSI output "
            "within the frame interval.  The user sees a partially drawn "
            "frame — this is flicker."
        ),
        fix=(
            "Reduce grid dimensions (keep under 4,800 cells for 30 FPS on "
            "fast terminals).  Minimise per-cell styling — uniform-style "
            "runs are cheaper because Rich batches them.  Use "
            "estimate_render_cost() to assess grid size before committing."
        ),
        caveat=(
            "Flicker severity depends on the terminal emulator.  kitty, "
            "WezTerm, and Windows Terminal are fast.  Legacy Windows "
            "conhost, macOS Terminal.app, and terminals over SSH are slower."
        ),
    ),
    TroubleshootingEntry(
        category="display",
        symptom="Output appears garbled after crash or Ctrl+C",
        cause=(
            "wyby's InputManager switches the terminal to raw mode "
            "(disabling echo and line buffering).  If the process exits "
            "without restoring cooked mode (e.g., SIGKILL, unhandled "
            "exception outside a try/finally), the terminal is left in "
            "raw mode."
        ),
        fix=(
            "Run 'reset' or 'stty sane' in the terminal to restore normal "
            "settings.  To prevent this, use Engine (which installs signal "
            "handlers for cleanup) or wrap InputManager usage in a "
            "try/finally block that calls InputManager.stop()."
        ),
        caveat=(
            "SIGKILL (kill -9) cannot be caught — there is no way to "
            "restore terminal state if the process is killed with SIGKILL.  "
            "This is an OS-level limitation, not a wyby bug."
        ),
    ),
    # -- Color issues ---------------------------------------------------------
    TroubleshootingEntry(
        category="color",
        symptom="Colors look wrong or are missing entirely",
        cause=(
            "The terminal does not support the colour depth that the game "
            "expects.  Rich auto-detects colour support via $COLORTERM and "
            "$TERM, but detection is best-effort.  Some terminals support "
            "truecolor but do not set $COLORTERM.  Inside tmux/screen, the "
            "outer terminal's capabilities may be masked."
        ),
        fix=(
            "Set $COLORTERM=truecolor in your shell profile if your terminal "
            "supports 24-bit colour.  For tmux, add "
            "'set -ga terminal-overrides \",*256col*:Tc\"' to ~/.tmux.conf.  "
            "Use detect_capabilities() at startup to log the detected colour "
            "depth."
        ),
        caveat=(
            "$COLORTERM is a de-facto convention, not a formal standard.  "
            "Setting it incorrectly (claiming truecolor when unsupported) "
            "will cause Rich to emit escape sequences the terminal cannot "
            "render, producing garbled output."
        ),
    ),
    TroubleshootingEntry(
        category="color",
        symptom="Colors differ between terminals",
        cause=(
            "Each terminal emulator has its own palette for the standard 16 "
            "ANSI colours.  The 'red' in iTerm2 is not the same RGB value "
            "as 'red' in GNOME Terminal or Windows Terminal.  256-colour "
            "palette indices 0-15 also vary.  Only truecolor (24-bit) "
            "produces consistent colours across terminals."
        ),
        fix=(
            "Design colour palettes using truecolor (RGB) values rather "
            "than ANSI palette indices.  Accept that the 16-colour fallback "
            "will look different across terminals.  Test on your target "
            "terminals."
        ),
        caveat=(
            "Even with truecolor, monitor calibration and terminal gamma "
            "settings affect perceived colour.  Exact colour matching "
            "across environments is not achievable."
        ),
    ),
    # -- Input issues ---------------------------------------------------------
    TroubleshootingEntry(
        category="input",
        symptom="Key presses are not detected or are delayed",
        cause=(
            "The terminal or multiplexer is buffering or intercepting "
            "keystrokes.  tmux and screen intercept certain key sequences "
            "for their own bindings before passing them through.  SSH adds "
            "network latency to every keystroke.  Some terminals delay "
            "ESC-prefixed sequences to disambiguate Alt+key from a bare "
            "Escape press."
        ),
        fix=(
            "For tmux, check that the key is not bound by tmux itself "
            "(tmux list-keys).  For SSH, accept that keystroke latency is "
            "limited by network round-trip time.  For Escape delay, set "
            "'set -sg escape-time 0' in tmux.conf."
        ),
        caveat=(
            "Some key combinations (Ctrl+Shift+letter, Ctrl+number, "
            "function keys beyond F12) are not reliably transmitted by all "
            "terminals.  Design game controls using commonly supported keys: "
            "arrows, WASD, Enter, Space, Escape, Tab, and Ctrl+letter."
        ),
    ),
    TroubleshootingEntry(
        category="input",
        symptom="Arrow keys produce escape characters instead of movement",
        cause=(
            "The terminal is not in raw mode, or the ANSI escape sequence "
            "parser is not processing multi-byte input correctly.  Arrow "
            "keys generate 3-byte ANSI sequences (e.g., ESC[A for Up).  "
            "If the parser reads only the first byte, it sees ESC and "
            "interprets the rest as separate characters."
        ),
        fix=(
            "Ensure InputManager.start() has been called before reading "
            "input.  Use Engine (which manages InputManager lifecycle) "
            "rather than reading stdin directly.  Check that nothing else "
            "is reading from stdin concurrently."
        ),
        caveat=(
            "On Windows with msvcrt, arrow keys use a different encoding "
            "(two-byte scan codes prefixed with 0x00 or 0xe0).  wyby's "
            "WindowsInputBackend normalises these, but third-party input "
            "readers may not."
        ),
    ),
    TroubleshootingEntry(
        category="input",
        symptom="Ctrl+C does not quit the game",
        cause=(
            "In raw mode, Ctrl+C does not generate SIGINT.  Instead, the "
            "byte 0x03 is delivered as a normal input event.  wyby's "
            "Engine handles this by converting Ctrl+C to a quit signal, "
            "but custom input handling code may not."
        ),
        fix=(
            "Use Engine for game loop management — it handles Ctrl+C "
            "correctly.  If implementing custom input handling, check for "
            "the byte 0x03 (or KeyEvent with key='ctrl+c') and call "
            "Engine.stop() or raise KeyboardInterrupt."
        ),
        caveat=(
            "Even with Engine, SIGKILL (kill -9) is always effective as "
            "a last resort.  On macOS, Cmd+Q will also close the terminal "
            "window."
        ),
    ),
    # -- Performance issues ---------------------------------------------------
    TroubleshootingEntry(
        category="performance",
        symptom="Low frame rate despite small grid",
        cause=(
            "Per-cell styling is expensive.  Each cell with a unique "
            "Rich Style object requires its own ANSI escape sequence, "
            "increasing both serialisation time and terminal parse time.  "
            "A 40x24 grid with every cell styled differently costs much "
            "more than the same grid with uniform styling."
        ),
        fix=(
            "Reduce the number of unique styles.  Batch adjacent cells "
            "with the same style.  Use FPSCounter and RenderTimer to "
            "identify whether the bottleneck is Python-side serialisation "
            "or terminal-side rendering."
        ),
    ),
    TroubleshootingEntry(
        category="performance",
        symptom="Game runs slowly over SSH",
        cause=(
            "Every frame's ANSI output must traverse the network.  A "
            "typical 80x24 frame produces several kilobytes of ANSI "
            "escape sequences.  At 30 FPS, that is ~100 KB/s — well "
            "within bandwidth limits, but network latency delays each "
            "frame's display by the round-trip time."
        ),
        fix=(
            "Enable SSH compression (ssh -C) to reduce bandwidth for "
            "large frames.  Reduce grid size and style complexity.  "
            "Lower the tick rate (e.g., 15 tps instead of 30).  Accept "
            "that SSH play will always have higher latency than local."
        ),
        caveat=(
            "SSH compression adds CPU overhead.  On very fast local "
            "networks, compression may not help.  mosh is not a solution "
            "for games because it uses screen-level diffing that conflicts "
            "with Rich's full-frame updates."
        ),
    ),
    TroubleshootingEntry(
        category="performance",
        symptom="Game runs slowly inside tmux or screen",
        cause=(
            "Terminal multiplexers add an extra rendering layer.  The "
            "multiplexer receives wyby's ANSI output, re-renders it into "
            "its own virtual terminal buffer, then writes that buffer to "
            "the outer terminal.  This roughly doubles rendering latency."
        ),
        fix=(
            "For best performance, run wyby games directly in the "
            "terminal, not inside a multiplexer.  If a multiplexer is "
            "necessary, use tmux (faster than screen) and keep the grid "
            "size small."
        ),
    ),
    # -- Environment issues ---------------------------------------------------
    TroubleshootingEntry(
        category="environment",
        symptom="'not a tty' error or blank output when piping",
        cause=(
            "wyby's renderer requires stdout to be connected to a "
            "terminal (TTY).  When stdout is redirected to a file or "
            "pipe (e.g., python game.py | less, or python game.py > "
            "output.txt), Rich detects the non-TTY and disables "
            "interactive features."
        ),
        fix=(
            "Run the game directly in a terminal, not piped or "
            "redirected.  If you need to capture output for debugging, "
            "use logging to a file instead of redirecting stdout."
        ),
        caveat=(
            "detect_capabilities().is_tty checks sys.stdout.isatty().  "
            "In rare cases (e.g., some IDE terminals, Jupyter notebooks), "
            "isatty() returns False even though the output is visible.  "
            "wyby is designed for real terminal emulators, not embedded "
            "consoles."
        ),
    ),
    TroubleshootingEntry(
        category="environment",
        symptom="Unicode characters show as '?' or empty boxes",
        cause=(
            "The terminal locale is not set to UTF-8, or the terminal "
            "font lacks glyphs for the requested characters.  On Unix, "
            "locale is controlled by $LC_ALL, $LC_CTYPE, and $LANG.  "
            "On Windows, legacy conhost has limited Unicode support."
        ),
        fix=(
            "Ensure your locale is set to a UTF-8 variant: "
            "'export LANG=en_US.UTF-8' (or your preferred locale).  "
            "On Windows, use Windows Terminal instead of legacy conhost.  "
            "Choose a font with broad Unicode coverage (e.g., Noto Mono, "
            "DejaVu Sans Mono)."
        ),
        caveat=(
            "Even with UTF-8 locale and a good font, some Unicode "
            "characters (especially emoji and rare scripts) may not "
            "render correctly.  Stick to ASCII, box-drawing, and block "
            "elements for maximum compatibility."
        ),
    ),
    TroubleshootingEntry(
        category="environment",
        symptom="$TERM or $COLORTERM is empty or wrong",
        cause=(
            "$TERM and $COLORTERM are set by the terminal emulator and "
            "may be overridden by shell profiles, tmux, or SSH.  If "
            "these variables are wrong, wyby's capability detection will "
            "under-report or over-report terminal features."
        ),
        fix=(
            "Check your current values: echo $TERM $COLORTERM.  For "
            "truecolor terminals, ensure $COLORTERM=truecolor is set.  "
            "In tmux, add 'set -g default-terminal \"tmux-256color\"' to "
            "~/.tmux.conf.  Avoid manually setting $TERM unless you know "
            "the correct terminfo entry."
        ),
        caveat=(
            "Setting $TERM to an incorrect value (e.g., xterm-256color "
            "on a terminal that does not support 256 colours) causes "
            "applications to emit escape sequences the terminal cannot "
            "handle.  Let the terminal emulator set $TERM automatically "
            "whenever possible."
        ),
    ),
    TroubleshootingEntry(
        category="environment",
        symptom="Game works locally but fails in CI or Docker",
        cause=(
            "CI environments and Docker containers typically do not have "
            "a TTY attached to stdout.  Without a TTY, Rich disables "
            "interactive rendering, terminal size detection returns "
            "fallback values (80x24), and input reading may block "
            "indefinitely."
        ),
        fix=(
            "For CI testing, mock terminal capabilities or run in "
            "headless mode.  Use detect_capabilities() to check is_tty "
            "before entering the game loop.  For Docker, use "
            "'docker run -it' to allocate a pseudo-TTY."
        ),
        caveat=(
            "Some CI systems (GitHub Actions, GitLab CI) can allocate "
            "a pseudo-TTY via configuration, but the 'terminal' will "
            "have no real display — rendering output goes nowhere.  "
            "Use CI for running unit tests, not for visual testing."
        ),
    ),
)

TROUBLESHOOTING_CATEGORIES: frozenset[str] = frozenset(
    entry.category for entry in TROUBLESHOOTING_ENTRIES
)
"""All distinct category names in :data:`TROUBLESHOOTING_ENTRIES`."""

# Human-readable category labels, in display order.
_CATEGORY_ORDER: tuple[str, ...] = (
    "display",
    "color",
    "input",
    "performance",
    "environment",
)

_CATEGORY_LABELS: dict[str, str] = {
    "display": "Display Issues",
    "color": "Colour Issues",
    "input": "Input Issues",
    "performance": "Performance Issues",
    "environment": "Environment Issues",
}


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------


def get_entries_by_category(
    category: str,
) -> tuple[TroubleshootingEntry, ...]:
    """Return all troubleshooting entries in the given category.

    Args:
        category: One of the category names in
            :data:`TROUBLESHOOTING_CATEGORIES`.

    Returns:
        A tuple of :class:`TroubleshootingEntry` instances.

    Raises:
        ValueError: If *category* is not a recognised category name.

    Caveats:
        - Categories are derived from the built-in catalog.
    """
    if category not in TROUBLESHOOTING_CATEGORIES:
        raise ValueError(
            f"Unknown category {category!r}.  "
            f"Known categories: {sorted(TROUBLESHOOTING_CATEGORIES)}"
        )
    return tuple(
        entry for entry in TROUBLESHOOTING_ENTRIES
        if entry.category == category
    )


# ---------------------------------------------------------------------------
# Automated diagnostics
# ---------------------------------------------------------------------------


def diagnose_terminal(
    caps: TerminalCapabilities | None = None,
) -> list[DiagnosticResult]:
    """Run automated checks against the current terminal environment.

    Probes environment variables, TTY status, colour support, and
    locale settings to identify potential problems.

    Args:
        caps: Pre-detected terminal capabilities.  If ``None``,
            :func:`~wyby.diagnostics.detect_capabilities` is called
            internally.

    Returns:
        A list of :class:`DiagnosticResult` findings, one per check.
        Results with ``passed=False`` indicate potential issues.

    Caveats:
        - These checks are **best-effort** and cannot detect all
          terminal issues.  Font problems, emoji width disagreements,
          and rendering bugs are not detectable via environment probing.
        - A clean report (all passed) does not guarantee correct
          rendering — it means no *detectable* issues were found.
        - The checks read environment variables and call
          ``sys.stdout.isatty()``.  They do not send escape sequences
          to the terminal or modify terminal state.
    """
    if caps is None:
        caps = detect_capabilities()

    results: list[DiagnosticResult] = []

    # 1. TTY check
    if caps.is_tty:
        results.append(DiagnosticResult(
            check="tty",
            passed=True,
            message="stdout is connected to a TTY.",
        ))
    else:
        results.append(DiagnosticResult(
            check="tty",
            passed=False,
            message="stdout is not a TTY (piped or redirected).",
            suggestion=(
                "Run the game directly in a terminal.  Interactive "
                "rendering requires a TTY-connected stdout."
            ),
        ))

    # 2. Colour support check
    if caps.color_support >= ColorSupport.TRUECOLOR:
        results.append(DiagnosticResult(
            check="color",
            passed=True,
            message=f"Truecolor (24-bit) support detected via $COLORTERM={caps.colorterm_env!r}.",
        ))
    elif caps.color_support >= ColorSupport.EXTENDED:
        results.append(DiagnosticResult(
            check="color",
            passed=True,
            message=f"256-colour support detected via $TERM={caps.term_env!r}.",
            suggestion=(
                "For best results, set $COLORTERM=truecolor if your "
                "terminal supports 24-bit colour."
            ),
        ))
    elif caps.color_support >= ColorSupport.STANDARD:
        results.append(DiagnosticResult(
            check="color",
            passed=False,
            message="Only 16-colour support detected.",
            suggestion=(
                "Set $COLORTERM=truecolor if your terminal supports "
                "24-bit colour, or use a modern terminal emulator "
                "(Windows Terminal, iTerm2, kitty, GNOME Terminal)."
            ),
        ))
    else:
        results.append(DiagnosticResult(
            check="color",
            passed=False,
            message="No colour support detected (dumb terminal or pipe).",
            suggestion=(
                "Use a terminal emulator that supports ANSI colours.  "
                "Check that $TERM is not set to 'dumb'."
            ),
        ))

    # 3. UTF-8 check
    if caps.utf8_supported:
        results.append(DiagnosticResult(
            check="utf8",
            passed=True,
            message="UTF-8 locale detected.",
        ))
    else:
        results.append(DiagnosticResult(
            check="utf8",
            passed=False,
            message="UTF-8 locale not detected.",
            suggestion=(
                "Set your locale to UTF-8: export LANG=en_US.UTF-8 "
                "(or your preferred locale).  On Windows, use Windows "
                "Terminal for better Unicode support."
            ),
        ))

    # 4. Terminal size check
    # Caveat: a very small terminal may not be usable for games but is
    # not strictly an error.  We flag sizes below 40x12 as a warning.
    if caps.columns >= 40 and caps.rows >= 12:
        results.append(DiagnosticResult(
            check="size",
            passed=True,
            message=f"Terminal size {caps.columns}x{caps.rows} is adequate.",
        ))
    else:
        results.append(DiagnosticResult(
            check="size",
            passed=False,
            message=f"Terminal size {caps.columns}x{caps.rows} may be too small.",
            suggestion=(
                "Resize the terminal window to at least 40 columns by "
                "12 rows.  Most wyby games expect 80x24 or larger."
            ),
        ))

    # 5. Terminal program identification
    if caps.terminal_program:
        results.append(DiagnosticResult(
            check="terminal_id",
            passed=True,
            message=f"Terminal identified as {caps.terminal_program!r}.",
        ))
    else:
        results.append(DiagnosticResult(
            check="terminal_id",
            passed=True,
            message=(
                "Terminal program not identified (no $TERM_PROGRAM or "
                "similar variable set)."
            ),
            suggestion=(
                "This is not an error — many terminals work fine "
                "without identification.  Capability detection uses "
                "$COLORTERM and $TERM instead."
            ),
        ))

    # 6. Multiplexer detection
    # Caveat: detecting tmux/screen is best-effort.  We check $TMUX
    # and $STY which are set by tmux and screen respectively.
    in_tmux = bool(os.environ.get("TMUX"))
    in_screen = bool(os.environ.get("STY"))
    if in_tmux or in_screen:
        mux_name = "tmux" if in_tmux else "screen"
        results.append(DiagnosticResult(
            check="multiplexer",
            passed=True,
            message=f"Running inside {mux_name}.",
            suggestion=(
                "Multiplexers add rendering latency.  For best "
                "performance, run games directly in the terminal.  "
                "If using tmux, set 'set -sg escape-time 0' and "
                "'set -ga terminal-overrides \",*256col*:Tc\"' for "
                "truecolor passthrough."
            ),
        ))
    else:
        results.append(DiagnosticResult(
            check="multiplexer",
            passed=True,
            message="Not running inside a known multiplexer.",
        ))

    _logger.debug(
        "Terminal diagnosis complete: %d checks, %d passed",
        len(results),
        sum(1 for r in results if r.passed),
    )
    return results


def format_diagnostic_report(
    results: list[DiagnosticResult] | None = None,
) -> str:
    """Format diagnostic results as a human-readable report.

    Args:
        results: Diagnostic results to format.  If ``None``,
            :func:`diagnose_terminal` is called internally.

    Returns:
        A multi-line string suitable for logging or display.

    Caveats:
        - If no results are provided, this function calls
          :func:`diagnose_terminal`, which reads environment variables.
    """
    if results is None:
        results = diagnose_terminal()

    lines: list[str] = []
    lines.append("wyby terminal diagnostic report")
    lines.append("=" * 40)

    passed = sum(1 for r in results if r.passed)
    total = len(results)
    lines.append(f"Checks: {passed}/{total} passed")
    lines.append("")

    for result in results:
        status = "OK" if result.passed else "!!"
        lines.append(f"  [{status}] {result.check}: {result.message}")
        if result.suggestion:
            lines.append(f"       -> {result.suggestion}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------


def format_troubleshooting_for_category(category: str) -> str:
    """Format all troubleshooting entries in a single category as Markdown.

    Args:
        category: One of the category names in
            :data:`TROUBLESHOOTING_CATEGORIES`.

    Returns:
        A multi-line Markdown string.

    Raises:
        ValueError: If *category* is not recognised.

    Caveats:
        - The output is plain Markdown, not a Rich renderable.
    """
    entries = get_entries_by_category(category)
    label = _CATEGORY_LABELS.get(
        category, category.replace("_", " ").title(),
    )

    lines: list[str] = []
    lines.append(f"## {label}")
    lines.append("")

    for entry in entries:
        lines.append(f"### {entry.symptom}")
        lines.append("")
        lines.append(f"**Cause:** {entry.cause}")
        lines.append("")
        lines.append(f"**Fix:** {entry.fix}")
        lines.append("")
        if entry.caveat:
            lines.append(f"**Caveat:** {entry.caveat}")
            lines.append("")

    return "\n".join(lines)


def format_troubleshooting_guide() -> str:
    """Format the complete troubleshooting catalog as a Markdown document.

    Produces a document with all issues grouped by category, each with
    symptom, cause, fix, and caveat (if available).

    Returns:
        A multi-line Markdown string.

    Caveats:
        - Categories are listed in a fixed display order.  Categories
          present in the catalog but not in the display order are
          appended at the end.
    """
    lines: list[str] = []
    lines.append("# wyby Terminal Troubleshooting Guide")
    lines.append("")
    lines.append(
        "This guide covers common terminal issues encountered when "
        "running wyby games, along with their causes and recommended fixes."
    )
    lines.append("")
    lines.append(f"**{len(TROUBLESHOOTING_ENTRIES)} issues documented.**")
    lines.append("")

    # Categories in display order.
    seen: set[str] = set()
    ordered_cats: list[str] = []
    for cat in _CATEGORY_ORDER:
        if cat in TROUBLESHOOTING_CATEGORIES:
            ordered_cats.append(cat)
            seen.add(cat)
    # Append any categories not in the fixed order.
    for cat in sorted(TROUBLESHOOTING_CATEGORIES):
        if cat not in seen:
            ordered_cats.append(cat)

    for cat in ordered_cats:
        lines.append(format_troubleshooting_for_category(cat))

    return "\n".join(lines)
