"""Rich Live display tradeoffs documentation for wyby.

This module documents the tradeoffs of using Rich's ``Live`` display for
terminal rendering instead of alternatives like ``curses``.  It catalogs
what Rich gives us, what it does not, performance implications, and
practical guidance for game developers.

The primary entry points are:

- :data:`TRADEOFF_ENTRIES` — the complete catalog of
  :class:`RichLiveTradeoff` items covering each tradeoff aspect.
- :data:`TRADEOFF_CATEGORIES` — the set of all category names.
- :func:`get_tradeoffs_by_category` — filter entries by category.
- :func:`format_rich_live_tradeoffs_doc` — render the full catalog as
  Markdown.
- :func:`format_tradeoffs_for_category` — render a single category.

Caveats:
    - This catalog is maintained manually alongside :mod:`wyby.renderer`
      and :mod:`wyby.grid`.  If the rendering pipeline changes, this
      catalog may need updating.
    - Performance characteristics described here reflect Rich's behaviour
      as of v13.x.  Future Rich versions may change internal rendering
      strategy, invalidating some observations.
    - Flicker susceptibility and frame rate numbers are approximate and
      vary significantly by terminal emulator, OS, and hardware.
    - The curses comparison reflects CPython's ``curses`` module.  Other
      TUI frameworks (Textual, urwid, blessed) have their own tradeoff
      profiles not covered here.
"""

from __future__ import annotations

import dataclasses


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class RichLiveTradeoff:
    """A documented tradeoff of using Rich's Live display in wyby.

    Attributes:
        category: Broad topic area (e.g., ``"advantage"``,
            ``"limitation"``, ``"performance"``, ``"guidance"``).
        topic: Short human-readable label (e.g.,
            ``"No double buffering"``).
        description: Full explanation of the tradeoff, including
            why it matters and what the practical impact is.
        caveat: Optional caveat or edge-case note, or ``None``.

    Caveats:
        - ``category`` values are lowercase strings, not an enum.
        - ``caveat`` describes edge cases, not the main behaviour.
    """

    category: str
    topic: str
    description: str
    caveat: str | None = None


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------

# Caveat: this catalog is maintained manually alongside renderer.py and
# grid.py.  It reflects wyby v0.1.0dev0 and Rich v13.x.  Changes to the
# rendering pipeline or Rich internals may require updates.

TRADEOFF_ENTRIES: tuple[RichLiveTradeoff, ...] = (
    # -- Advantages of Rich's approach ---------------------------------------
    RichLiveTradeoff(
        category="advantage",
        topic="Cross-platform without C extensions",
        description=(
            "Rich is pure Python and pip-installable on all platforms.  "
            "Unlike curses, it does not require a C extension or the "
            "windows-curses shim on Windows.  This simplifies installation "
            "and avoids build-time dependencies."
        ),
    ),
    RichLiveTradeoff(
        category="advantage",
        topic="Windows support without windows-curses",
        description=(
            "Rich works natively on Windows (cmd.exe, PowerShell, Windows "
            "Terminal) without requiring the windows-curses package or WSL.  "
            "curses on Windows requires either windows-curses (a third-party "
            "C extension) or running under WSL/Cygwin."
        ),
        caveat=(
            "Windows cmd.exe and legacy conhost have slower ANSI parsing "
            "than modern terminals, which can exacerbate flicker.  Windows "
            "Terminal is strongly recommended."
        ),
    ),
    RichLiveTradeoff(
        category="advantage",
        topic="Composable Rich renderables",
        description=(
            "The cell grid is a Rich renderable that composes naturally "
            "with other Rich outputs — tables, panels, markdown, progress "
            "bars, and styled text.  This enables debug overlays, menus, "
            "and UI panels without a separate rendering path."
        ),
    ),
    RichLiveTradeoff(
        category="advantage",
        topic="Truecolor and automatic fallback",
        description=(
            "Rich handles truecolor (24-bit), 256-color, and 16-color "
            "output with automatic terminal detection and fallback.  Games "
            "specify colors in RGB; Rich downgrades them based on terminal "
            "capabilities.  curses requires manual color-pair management "
            "and typically supports only 256 colors."
        ),
    ),
    RichLiveTradeoff(
        category="advantage",
        topic="Text styling via Rich's API",
        description=(
            "Bold, dim, italic, underline, strikethrough, and reverse "
            "styles are applied through Rich's Style objects.  This is "
            "more ergonomic than curses' A_BOLD | A_UNDERLINE bitmask "
            "approach and supports style inheritance and composition."
        ),
    ),
    # -- Limitations of Rich Live --------------------------------------------
    RichLiveTradeoff(
        category="limitation",
        topic="No double buffering",
        description=(
            "Rich's Live display re-renders the entire renderable on each "
            "refresh.  Unlike curses, it does not track which cells changed "
            "between frames.  CPU cost scales with total grid size, not "
            "with the number of changed cells.  A static frame costs the "
            "same as a fully animated one."
        ),
        caveat=(
            "wyby's DoubleBuffer class tracks dirty cells at the "
            "application level, but this does not reduce Rich's rendering "
            "cost — Rich still regenerates the full ANSI output on each "
            "frame."
        ),
    ),
    RichLiveTradeoff(
        category="limitation",
        topic="Full-frame ANSI regeneration",
        description=(
            "Every frame, Rich performs layout calculation, style "
            "resolution, and ANSI escape code generation for the entire "
            "grid.  A 120x40 grid of individually styled cells produces "
            "substantially more work than a plain text block of the same "
            "dimensions, because each style transition requires new escape "
            "sequences."
        ),
    ),
    RichLiveTradeoff(
        category="limitation",
        topic="Flicker on slow terminals",
        description=(
            "Large grids or complex per-cell styling may cause visible "
            "flicker on terminals with slow rendering — Windows cmd.exe, "
            "legacy conhost, macOS Terminal.app, and terminals running "
            "over SSH or inside tmux/screen.  The terminal's own ANSI "
            "parsing and compositing time contributes to flicker, which "
            "is outside wyby's control."
        ),
        caveat=(
            "Flicker is a terminal-side issue, not a Rich bug.  Fast "
            "terminals (kitty, WezTerm, iTerm2, Windows Terminal) handle "
            "rapid updates well.  The same grid that flickers in cmd.exe "
            "may render cleanly in Windows Terminal."
        ),
    ),
    RichLiveTradeoff(
        category="limitation",
        topic="No frame rate guarantee",
        description=(
            "Achievable refresh rate depends on terminal emulator, OS, "
            "grid size, style complexity, and connection type.  On a "
            "modern terminal with a modest grid (60x24), 15-30 updates "
            "per second is realistic.  On Windows Console or over SSH, "
            "it may be significantly lower.  60 FPS is not a meaningful "
            "target for terminal rendering."
        ),
        caveat=(
            "Frame rate is limited by the slowest link in the chain: "
            "Python processing, Rich rendering, OS pipe write, and "
            "terminal parsing.  Optimising only one does not help if "
            "another is the bottleneck."
        ),
    ),
    RichLiveTradeoff(
        category="limitation",
        topic="No character-level input with timeout",
        description=(
            "curses provides getch() with nodelay/halfdelay modes "
            "purpose-built for game input loops.  Rich has no input "
            "facility at all — wyby implements its own input layer using "
            "termios (Unix) and msvcrt (Windows).  This works but is "
            "less battle-tested than curses' input handling."
        ),
    ),
    # -- Performance characteristics -----------------------------------------
    RichLiveTradeoff(
        category="performance",
        topic="CPU cost scales with grid area",
        description=(
            "Rendering cost is proportional to width * height, not to "
            "the number of changed cells.  A 120x40 grid (4,800 cells) "
            "costs roughly 4x more than a 60x20 grid (1,200 cells), "
            "even if most cells are unchanged.  This is the fundamental "
            "performance difference from curses."
        ),
    ),
    RichLiveTradeoff(
        category="performance",
        topic="Per-cell styling is expensive",
        description=(
            "When every cell has a unique style (foreground, background, "
            "attributes), Rich must emit an ANSI escape sequence for each "
            "cell.  Uniform-style runs are much cheaper because Rich "
            "batches them into a single escape sequence followed by the "
            "text content.  Minimising style transitions reduces both CPU "
            "and output bandwidth."
        ),
        caveat=(
            "This is a Rich optimisation, not a guarantee.  The batching "
            "behaviour depends on Rich's internal rendering engine and "
            "may change between versions."
        ),
    ),
    RichLiveTradeoff(
        category="performance",
        topic="Terminal multiplexer overhead",
        description=(
            "tmux and screen add an extra rendering layer.  The "
            "multiplexer receives wyby's ANSI output, re-renders into "
            "its own virtual screen, and writes the result to the outer "
            "terminal.  This roughly doubles rendering latency and "
            "increases flicker risk."
        ),
    ),
    RichLiveTradeoff(
        category="performance",
        topic="SSH network latency",
        description=(
            "Over SSH, every frame's ANSI output must traverse the "
            "network.  A 4,800-cell grid with per-cell styling can "
            "produce several kilobytes of ANSI output per frame.  At "
            "30 FPS, this is ~100-300 KB/s of terminal data.  High-"
            "latency or low-bandwidth connections make this impractical."
        ),
        caveat=(
            "ssh -C enables compression, which helps for repetitive "
            "ANSI output.  Reducing grid size and style complexity is "
            "the primary mitigation for SSH-based games."
        ),
    ),
    # -- Practical guidance --------------------------------------------------
    RichLiveTradeoff(
        category="guidance",
        topic="Keep grids under 4,800 cells for 30 FPS",
        description=(
            "As a rule of thumb, grids under 4,800 cells (e.g., 80x60 "
            "or 120x40) achieve 30+ updates/second on fast terminals "
            "(kitty, WezTerm, iTerm2, Windows Terminal).  Larger grids "
            "work but may drop below 30 FPS depending on style "
            "complexity and terminal speed."
        ),
        caveat=(
            "This threshold is approximate and assumes a modern machine "
            "with a fast terminal.  Slower hardware, SSH, or multiplexers "
            "reduce the practical limit."
        ),
    ),
    RichLiveTradeoff(
        category="guidance",
        topic="Minimise per-cell style transitions",
        description=(
            "Uniform-style runs are cheaper than per-cell styling.  "
            "Where possible, use the same foreground/background/style "
            "for contiguous regions.  A grid with 10 style changes per "
            "row renders faster than one with a unique style per cell."
        ),
    ),
    RichLiveTradeoff(
        category="guidance",
        topic="Use estimate_render_cost() to predict performance",
        description=(
            "wyby's estimate_render_cost() function predicts rendering "
            "cost for a given grid size and style density.  Call it "
            "before committing to a grid size to get an approximate "
            "FPS estimate for the target terminal class."
        ),
    ),
    RichLiveTradeoff(
        category="guidance",
        topic="Use FPSCounter to measure actual performance",
        description=(
            "FPSCounter measures the actual achieved frame rate at "
            "runtime.  Use it during development to validate that your "
            "grid size and style choices meet your target frame rate.  "
            "Performance varies across environments, so measuring on "
            "target hardware is essential."
        ),
    ),
    RichLiveTradeoff(
        category="guidance",
        topic="Recommend fast terminals to users",
        description=(
            "Terminal emulator choice has a large impact on rendering "
            "performance and flicker.  Recommend kitty, WezTerm, iTerm2, "
            "or Windows Terminal in your game's documentation.  These "
            "terminals have GPU-accelerated rendering and handle rapid "
            "ANSI updates well."
        ),
        caveat=(
            "You cannot control which terminal your users choose.  "
            "Design for the slowest reasonable target and degrade "
            "gracefully."
        ),
    ),
)


TRADEOFF_CATEGORIES: frozenset[str] = frozenset(
    entry.category for entry in TRADEOFF_ENTRIES
)
"""All distinct category names in :data:`TRADEOFF_ENTRIES`."""


# Human-readable category labels, in display order.
_CATEGORY_ORDER: tuple[str, ...] = (
    "advantage",
    "limitation",
    "performance",
    "guidance",
)

_CATEGORY_LABELS: dict[str, str] = {
    "advantage": "What Rich Gives Us",
    "limitation": "What Rich Does Not Give Us",
    "performance": "Performance Characteristics",
    "guidance": "Practical Guidance",
}


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------


def get_tradeoffs_by_category(
    category: str,
) -> tuple[RichLiveTradeoff, ...]:
    """Return all tradeoff entries in the given category.

    Args:
        category: One of the category names in
            :data:`TRADEOFF_CATEGORIES`.

    Returns:
        A tuple of :class:`RichLiveTradeoff` instances.

    Raises:
        ValueError: If *category* is not a recognised category name.

    Caveats:
        - Categories are derived from the built-in catalog.  Custom
          entries added at runtime are not supported.
    """
    if category not in TRADEOFF_CATEGORIES:
        raise ValueError(
            f"Unknown category {category!r}.  "
            f"Known categories: {sorted(TRADEOFF_CATEGORIES)}"
        )
    return tuple(
        entry for entry in TRADEOFF_ENTRIES
        if entry.category == category
    )


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------


def format_tradeoffs_for_category(category: str) -> str:
    """Format all tradeoff entries in a single category as Markdown.

    Args:
        category: One of the category names in
            :data:`TRADEOFF_CATEGORIES`.

    Returns:
        A multi-line Markdown string.

    Raises:
        ValueError: If *category* is not recognised.

    Caveats:
        - The output is plain Markdown, not a Rich renderable.
    """
    entries = get_tradeoffs_by_category(category)
    label = _CATEGORY_LABELS.get(
        category, category.replace("_", " ").title(),
    )

    lines: list[str] = []
    lines.append(f"## {label}")
    lines.append("")

    for entry in entries:
        lines.append(f"### {entry.topic}")
        lines.append("")
        lines.append(entry.description)
        lines.append("")
        if entry.caveat:
            lines.append(f"**Caveat:** {entry.caveat}")
            lines.append("")

    return "\n".join(lines)


def format_rich_live_tradeoffs_doc() -> str:
    """Format the complete Rich Live tradeoffs catalog as a Markdown document.

    Produces a document with all entries grouped by category, each
    with a description and optional caveat.

    Returns:
        A multi-line Markdown string.

    Caveats:
        - The output is a standalone reference document.
        - Categories are listed in a fixed display order.  Categories
          present in the catalog but not in the display order are
          appended at the end.
    """
    lines: list[str] = []
    lines.append("# Rich Live Display Tradeoffs")
    lines.append("")
    lines.append(
        "wyby uses Rich's Live display for terminal rendering instead of "
        "curses or other TUI frameworks.  This is a deliberate tradeoff, "
        "not an upgrade — Rich provides cross-platform styling and "
        "composability at the cost of efficient differential updates.  "
        "This document catalogs what Rich gives us, what it does not, "
        "performance implications, and practical guidance for game "
        "developers."
    )
    lines.append("")
    lines.append(
        f"**{len(TRADEOFF_ENTRIES)} tradeoffs documented** across "
        f"{len(TRADEOFF_CATEGORIES)} categories."
    )
    lines.append("")

    # Categories in display order.
    seen: set[str] = set()
    ordered_cats: list[str] = []
    for cat in _CATEGORY_ORDER:
        if cat in TRADEOFF_CATEGORIES:
            ordered_cats.append(cat)
            seen.add(cat)
    # Append any categories not in the fixed order.
    for cat in sorted(TRADEOFF_CATEGORIES):
        if cat not in seen:
            ordered_cats.append(cat)

    for cat in ordered_cats:
        lines.append(format_tradeoffs_for_category(cat))

    return "\n".join(lines)
