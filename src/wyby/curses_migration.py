"""Migration guide from curses to wyby.

This module provides a structured catalog of curses API patterns and their
wyby equivalents, helping developers migrate existing curses-based terminal
games to the wyby framework.  Each entry maps a curses concept to the
corresponding wyby approach, with caveats about behavioural differences.

The primary entry points are:

- :data:`MIGRATION_ENTRIES` — the complete catalog of
  :class:`MigrationEntry` items mapping curses patterns to wyby equivalents.
- :data:`MIGRATION_CATEGORIES` — the set of all category names.
- :func:`get_entries_by_category` — filter entries by category.
- :func:`format_migration_guide` — render the full guide as Markdown.
- :func:`format_migration_for_category` — render a single category.

Caveats:
    - This guide targets CPython's :mod:`curses` module.  Other TUI
      frameworks (Textual, urwid, blessed) have their own migration paths
      not covered here.
    - wyby is pre-release (v0.1.0dev0).  API names and module paths may
      change before 1.0.  This guide reflects the current development state.
    - Not every curses feature has a wyby equivalent.  Where there is no
      direct replacement, the entry documents the gap and suggests
      workarounds or explains why the feature was omitted.
    - The curses code snippets are illustrative, not runnable.  They
      assume familiarity with standard curses idioms.

See also:
    - :mod:`wyby.rich_live_tradeoffs` for a detailed comparison of Rich's
      Live display versus curses rendering.
    - :mod:`wyby.limitations_caveats` for a comprehensive catalog of wyby's
      known limitations.
    - :mod:`wyby.input_permissions` for input handling scope and security
      rationale.
"""

from __future__ import annotations

import dataclasses


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class MigrationEntry:
    """A mapping from a curses pattern to its wyby equivalent.

    Attributes:
        category: Broad topic area (e.g., ``"initialization"``,
            ``"rendering"``, ``"input"``, ``"color"``, ``"lifecycle"``).
        curses_pattern: Short label for the curses API or idiom
            (e.g., ``"curses.initscr()"``).
        curses_description: How the pattern works in curses.
        wyby_equivalent: The wyby approach or API that replaces it.
        caveat: Optional caveat about behavioural differences, or ``None``.

    Caveats:
        - ``category`` values are lowercase strings, not an enum.
        - ``caveat`` describes differences or limitations, not the main
          behaviour.
    """

    category: str
    curses_pattern: str
    curses_description: str
    wyby_equivalent: str
    caveat: str | None = None


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------

# Caveat: this catalog is maintained manually.  It reflects wyby v0.1.0dev0
# and CPython's curses module.  Changes to wyby's API or module structure
# may require updates to the wyby_equivalent fields.

MIGRATION_ENTRIES: tuple[MigrationEntry, ...] = (
    # -- Initialization & setup -----------------------------------------------
    MigrationEntry(
        category="initialization",
        curses_pattern="curses.initscr() / curses.wrapper()",
        curses_description=(
            "curses.initscr() initializes the terminal for curses mode, "
            "and curses.wrapper() provides a safe wrapper that restores "
            "terminal state on exit.  The wrapper handles endwin() cleanup "
            "automatically."
        ),
        wyby_equivalent=(
            "Create an Engine instance with an EngineConfig.  Engine "
            "manages Rich's Live display lifecycle.  Terminal state "
            "cleanup is handled automatically when the engine stops.  "
            "Example: engine = Engine(config=EngineConfig(fps=30))"
        ),
        caveat=(
            "Engine does not put the terminal into a raw/cbreak mode the "
            "way curses.initscr() does.  wyby's input layer handles "
            "terminal mode changes separately via InputManager."
        ),
    ),
    MigrationEntry(
        category="initialization",
        curses_pattern="curses.noecho() / curses.cbreak()",
        curses_description=(
            "curses.noecho() disables automatic echoing of input keys. "
            "curses.cbreak() disables line buffering so keys are available "
            "immediately without waiting for Enter."
        ),
        wyby_equivalent=(
            "InputManager configures the terminal for raw input "
            "automatically.  On Unix, it sets termios attributes; on "
            "Windows, it uses msvcrt.  You do not need to call noecho() "
            "or cbreak() manually."
        ),
        caveat=(
            "wyby's input configuration is less granular than curses.  "
            "You cannot selectively enable echo while in raw mode.  The "
            "terminal is either in game input mode or normal mode."
        ),
    ),
    MigrationEntry(
        category="initialization",
        curses_pattern="stdscr = curses.initscr()",
        curses_description=(
            "curses returns a window object (stdscr) representing the "
            "full terminal screen.  All drawing happens on window objects."
        ),
        wyby_equivalent=(
            "wyby uses CellBuffer as the primary drawing surface.  Create "
            "a CellBuffer with a width and height, write Cell objects to "
            "it, and pass it to the Renderer.  There is no global screen "
            "object — you manage your own buffers."
        ),
        caveat=(
            "CellBuffer does not automatically match terminal size.  Use "
            "get_terminal_size() and ResizeHandler to track terminal "
            "dimensions if you need a full-screen buffer."
        ),
    ),
    # -- Rendering & drawing --------------------------------------------------
    MigrationEntry(
        category="rendering",
        curses_pattern="stdscr.addch(y, x, ch) / addstr()",
        curses_description=(
            "addch() and addstr() write characters or strings to specific "
            "positions on a curses window.  Coordinates are (row, col) "
            "with (0, 0) at the top-left."
        ),
        wyby_equivalent=(
            "Write Cell objects directly to a CellBuffer using indexed "
            "access.  Each Cell holds a character, foreground color, "
            "background color, and style attributes.  Coordinates are "
            "(x, y) with (0, 0) at the top-left."
        ),
        caveat=(
            "curses uses (row, col) ordering; wyby uses (x, y).  This "
            "is a common source of bugs when porting.  Double-check all "
            "coordinate arguments during migration."
        ),
    ),
    MigrationEntry(
        category="rendering",
        curses_pattern="stdscr.refresh()",
        curses_description=(
            "refresh() pushes the internal buffer to the terminal.  curses "
            "tracks which cells have changed and only redraws dirty regions "
            "(differential updates)."
        ),
        wyby_equivalent=(
            "Rich's Live display re-renders the entire grid on each frame "
            "via Renderer.  The Engine's game loop calls the renderer "
            "automatically at the configured FPS.  You do not call "
            "refresh() manually."
        ),
        caveat=(
            "Rich does NOT do differential updates.  Every frame "
            "regenerates the full ANSI output regardless of what changed.  "
            "This is the fundamental performance tradeoff versus curses.  "
            "See wyby.rich_live_tradeoffs for details."
        ),
    ),
    MigrationEntry(
        category="rendering",
        curses_pattern="curses.newwin(height, width, y, x)",
        curses_description=(
            "newwin() creates a sub-window for independent drawing.  "
            "Multiple windows can overlap and be refreshed independently."
        ),
        wyby_equivalent=(
            "Use multiple CellBuffer instances or the LayerStack system.  "
            "LayerStack composites multiple layers with z-ordering.  "
            "Each Layer wraps a CellBuffer and supports visibility toggling."
        ),
        caveat=(
            "curses windows can be refreshed independently for performance.  "
            "wyby's LayerStack composites all visible layers into a single "
            "output buffer on every frame — there is no independent "
            "sub-window refresh."
        ),
    ),
    MigrationEntry(
        category="rendering",
        curses_pattern="stdscr.clear() / erase()",
        curses_description=(
            "clear() fills the window with blanks and marks it for full "
            "redraw.  erase() fills with blanks but relies on the next "
            "refresh for differential update."
        ),
        wyby_equivalent=(
            "Create a fresh CellBuffer or clear an existing one by "
            "writing blank cells.  Since Rich re-renders fully on each "
            "frame, there is no functional difference between clear and "
            "erase — both result in a full redraw."
        ),
    ),
    MigrationEntry(
        category="rendering",
        curses_pattern="DoubleBuffer / curses noutrefresh/doupdate",
        curses_description=(
            "curses supports explicit double buffering via noutrefresh() "
            "on individual windows followed by doupdate() to flush all "
            "changes at once.  This minimizes terminal I/O."
        ),
        wyby_equivalent=(
            "wyby provides a DoubleBuffer class that tracks dirty cells "
            "at the application level.  However, this only reduces the "
            "work your game logic does — Rich still regenerates the full "
            "ANSI output on each frame."
        ),
        caveat=(
            "wyby's DoubleBuffer does not provide the same I/O savings "
            "as curses' noutrefresh/doupdate pattern.  The terminal sees "
            "a full redraw every frame regardless of dirty tracking."
        ),
    ),
    # -- Input handling -------------------------------------------------------
    MigrationEntry(
        category="input",
        curses_pattern="stdscr.getch() / getkey()",
        curses_description=(
            "getch() reads a single character from input, blocking until "
            "a key is available.  getkey() is similar but returns a string "
            "name for special keys."
        ),
        wyby_equivalent=(
            "Use InputManager with parse_key_events() or "
            "parse_input_events().  These return KeyEvent objects with "
            "key name and modifier information.  The Engine's game loop "
            "polls input automatically each frame."
        ),
        caveat=(
            "wyby's input layer is less battle-tested than curses' "
            "getch().  Edge cases with terminal escape sequences, "
            "especially on non-standard terminals, may behave differently."
        ),
    ),
    MigrationEntry(
        category="input",
        curses_pattern="stdscr.nodelay(True) / halfdelay()",
        curses_description=(
            "nodelay(True) makes getch() non-blocking (returns -1 if no "
            "input).  halfdelay(n) waits up to n tenths of a second.  "
            "These are essential for game input loops."
        ),
        wyby_equivalent=(
            "InputManager operates in non-blocking mode by default for "
            "game loops.  The Engine polls input each frame at the "
            "configured FPS.  There is no explicit nodelay/halfdelay "
            "toggle — the game loop handles timing."
        ),
        caveat=(
            "If you need custom input timing outside the Engine's game "
            "loop, you must implement your own polling.  wyby does not "
            "expose a halfdelay equivalent for fine-grained input timing."
        ),
    ),
    MigrationEntry(
        category="input",
        curses_pattern="curses.KEY_UP / KEY_DOWN / KEY_LEFT / KEY_RIGHT",
        curses_description=(
            "curses defines constants for arrow keys, function keys, and "
            "other special keys.  getch() returns these constants for "
            "non-character keys."
        ),
        wyby_equivalent=(
            "KeyEvent objects have a key attribute with string names like "
            "'up', 'down', 'left', 'right', 'enter', 'escape'.  Use "
            "KeyMap and KeyBinding to map keys to actions declaratively."
        ),
    ),
    MigrationEntry(
        category="input",
        curses_pattern="curses.mousemask() / getmouse()",
        curses_description=(
            "curses supports mouse input via mousemask() to enable mouse "
            "events and getmouse() to read them.  Support varies by "
            "terminal."
        ),
        wyby_equivalent=(
            "wyby provides MouseEvent via parse_input_events() with "
            "InputMode set to include mouse.  Mouse support is optional "
            "and must be explicitly enabled."
        ),
        caveat=(
            "Mouse support in terminals is inconsistent.  wyby's mouse "
            "handling is basic compared to curses and may not support "
            "all mouse event types (drag, hover) on all terminals.  "
            "See wyby.mouse_warnings for known issues."
        ),
    ),
    # -- Color & styling ------------------------------------------------------
    MigrationEntry(
        category="color",
        curses_pattern="curses.start_color() / init_pair()",
        curses_description=(
            "curses requires explicit color initialization.  start_color() "
            "enables color, and init_pair(n, fg, bg) defines numbered "
            "color pairs.  You then apply pairs with color_pair(n) as "
            "an attribute."
        ),
        wyby_equivalent=(
            "Colors are specified directly on Cell objects as RGB tuples "
            "or color names.  Rich handles terminal color detection and "
            "automatic downgrading (truecolor → 256 → 16) transparently.  "
            "No color pair registration is needed."
        ),
        caveat=(
            "curses' color pair system allows at most 256 (or 32767) "
            "concurrent pairs.  wyby has no such limit — each cell can "
            "have unique colors — but per-cell styling has a rendering "
            "cost.  See wyby.rich_live_tradeoffs for performance details."
        ),
    ),
    MigrationEntry(
        category="color",
        curses_pattern="curses.A_BOLD | curses.A_UNDERLINE",
        curses_description=(
            "curses uses bitmask constants for text attributes.  You "
            "combine them with | and pass them to addch/addstr or "
            "attron/attroff."
        ),
        wyby_equivalent=(
            "Cell objects accept style attributes (bold, dim, italic, "
            "underline, etc.) directly.  Rich's Style objects support "
            "composition and inheritance.  No bitmask arithmetic needed."
        ),
    ),
    MigrationEntry(
        category="color",
        curses_pattern="curses.can_change_color() / init_color()",
        curses_description=(
            "Some terminals allow redefining the RGB values of the base "
            "color palette via init_color().  can_change_color() checks "
            "if this is supported."
        ),
        wyby_equivalent=(
            "wyby does not modify the terminal's color palette.  Instead, "
            "it uses Rich's truecolor output with automatic fallback.  "
            "Use detect_capabilities() to check what the current terminal "
            "supports."
        ),
        caveat=(
            "If your curses code relies on init_color() to redefine base "
            "palette colors, there is no wyby equivalent.  Specify the "
            "exact RGB values you want on each Cell instead."
        ),
    ),
    # -- Lifecycle & terminal management --------------------------------------
    MigrationEntry(
        category="lifecycle",
        curses_pattern="curses.endwin()",
        curses_description=(
            "endwin() restores the terminal to its pre-curses state.  "
            "Failing to call endwin() leaves the terminal in a broken "
            "state (no echo, no line buffering, alternate screen active)."
        ),
        wyby_equivalent=(
            "Engine handles cleanup automatically when the game loop "
            "exits.  AltScreen and HiddenCursor are context managers "
            "that restore terminal state on __exit__.  If you manage "
            "these manually, use try/finally to ensure cleanup."
        ),
    ),
    MigrationEntry(
        category="lifecycle",
        curses_pattern="Alternate screen (curses sets it implicitly)",
        curses_description=(
            "curses.initscr() typically switches to the alternate screen "
            "buffer, preserving the user's scrollback.  endwin() switches "
            "back."
        ),
        wyby_equivalent=(
            "Use AltScreen as a context manager or call "
            "enable_alt_screen() / disable_alt_screen() explicitly.  "
            "Engine can be configured to manage the alternate screen "
            "automatically."
        ),
    ),
    MigrationEntry(
        category="lifecycle",
        curses_pattern="curses.curs_set(0) — hide cursor",
        curses_description=(
            "curs_set(0) hides the cursor, curs_set(1) shows it as "
            "normal, curs_set(2) shows it as very visible.  Essential "
            "for games to avoid a blinking cursor over the play area."
        ),
        wyby_equivalent=(
            "Use HiddenCursor as a context manager, or call "
            "hide_cursor() / show_cursor() explicitly.  "
            "is_cursor_hidden() checks the current state."
        ),
    ),
    MigrationEntry(
        category="lifecycle",
        curses_pattern="SIGWINCH / curses.resizeterm()",
        curses_description=(
            "Terminal resize triggers SIGWINCH.  curses.resizeterm() "
            "updates internal data structures to match the new size.  "
            "Some curses builds handle this automatically."
        ),
        wyby_equivalent=(
            "Use ResizeHandler to detect terminal size changes.  "
            "get_terminal_size() returns the current dimensions.  "
            "SignalHandler can catch SIGWINCH if needed."
        ),
        caveat=(
            "wyby does not automatically resize CellBuffers on terminal "
            "resize.  Your game logic must handle re-creating or resizing "
            "buffers when ResizeHandler reports a size change."
        ),
    ),
    # -- Patterns with no direct equivalent -----------------------------------
    MigrationEntry(
        category="no_equivalent",
        curses_pattern="curses.newpad()",
        curses_description=(
            "Pads are off-screen windows larger than the terminal.  You "
            "draw to the pad and then refresh a viewport region to the "
            "screen, enabling scrolling maps larger than the visible area."
        ),
        wyby_equivalent=(
            "Create a CellBuffer larger than the terminal and copy a "
            "viewport region to the display buffer each frame.  There "
            "is no built-in pad or viewport abstraction — implement "
            "scrolling in your game logic."
        ),
        caveat=(
            "curses pads only refresh the viewport region, which is "
            "efficient for large maps.  wyby always renders the full "
            "display buffer, so the viewport approach saves game-logic "
            "work but not rendering cost."
        ),
    ),
    MigrationEntry(
        category="no_equivalent",
        curses_pattern="curses.panel module",
        curses_description=(
            "The panel module manages overlapping windows with z-ordering "
            "and visibility, useful for popup dialogs and menus."
        ),
        wyby_equivalent=(
            "Use LayerStack for z-ordered compositing and the Dialog, "
            "Button, and Widget classes for UI overlays.  SceneStack "
            "provides push/pop scene management for modal screens."
        ),
    ),
    MigrationEntry(
        category="no_equivalent",
        curses_pattern="curses.textpad.Textbox",
        curses_description=(
            "Textbox provides a simple text editing widget within curses, "
            "handling cursor movement, insertion, and deletion."
        ),
        wyby_equivalent=(
            "wyby provides TextInput for single-line text entry.  It "
            "handles basic editing (insert, delete, cursor movement) "
            "within the wyby input system."
        ),
        caveat=(
            "TextInput is simpler than curses.textpad.Textbox and does "
            "not support multi-line editing.  For complex text entry, "
            "consider dropping to a regular terminal prompt temporarily."
        ),
    ),
    MigrationEntry(
        category="no_equivalent",
        curses_pattern="curses.ascii utilities",
        curses_description=(
            "The curses.ascii module provides character classification "
            "functions (isprint, isctrl, etc.) and constants for "
            "control characters."
        ),
        wyby_equivalent=(
            "Use Python's built-in str methods (str.isprintable(), etc.) "
            "and wyby's unicode module (char_width, is_wide_char, "
            "is_single_grapheme) for character classification.  There "
            "is no direct curses.ascii replacement."
        ),
    ),
)


MIGRATION_CATEGORIES: frozenset[str] = frozenset(
    entry.category for entry in MIGRATION_ENTRIES
)
"""All distinct category names in :data:`MIGRATION_ENTRIES`."""


# Human-readable category labels, in display order.
_CATEGORY_ORDER: tuple[str, ...] = (
    "initialization",
    "rendering",
    "input",
    "color",
    "lifecycle",
    "no_equivalent",
)

_CATEGORY_LABELS: dict[str, str] = {
    "initialization": "Initialization & Setup",
    "rendering": "Rendering & Drawing",
    "input": "Input Handling",
    "color": "Color & Styling",
    "lifecycle": "Lifecycle & Terminal Management",
    "no_equivalent": "Patterns With No Direct Equivalent",
}


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------


def get_entries_by_category(
    category: str,
) -> tuple[MigrationEntry, ...]:
    """Return all migration entries in the given category.

    Args:
        category: One of the category names in
            :data:`MIGRATION_CATEGORIES`.

    Returns:
        A tuple of :class:`MigrationEntry` instances.

    Raises:
        ValueError: If *category* is not a recognised category name.

    Caveats:
        - Categories are derived from the built-in catalog.  Custom
          entries added at runtime are not supported.
    """
    if category not in MIGRATION_CATEGORIES:
        raise ValueError(
            f"Unknown category {category!r}.  "
            f"Known categories: {sorted(MIGRATION_CATEGORIES)}"
        )
    return tuple(
        entry for entry in MIGRATION_ENTRIES
        if entry.category == category
    )


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------


def format_migration_for_category(category: str) -> str:
    """Format all migration entries in a single category as Markdown.

    Args:
        category: One of the category names in
            :data:`MIGRATION_CATEGORIES`.

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
        lines.append(f"### {entry.curses_pattern}")
        lines.append("")
        lines.append(f"**curses:** {entry.curses_description}")
        lines.append("")
        lines.append(f"**wyby:** {entry.wyby_equivalent}")
        lines.append("")
        if entry.caveat:
            lines.append(f"**Caveat:** {entry.caveat}")
            lines.append("")

    return "\n".join(lines)


def format_migration_guide() -> str:
    """Format the complete curses migration guide as a Markdown document.

    Produces a document with all entries grouped by category, each
    mapping a curses pattern to its wyby equivalent with optional caveats.

    Returns:
        A multi-line Markdown string.

    Caveats:
        - The output is a standalone reference document.
        - Categories are listed in a fixed display order.  Categories
          present in the catalog but not in the display order are
          appended at the end.
        - This guide targets CPython's curses module.  Other TUI
          frameworks have different migration paths.
    """
    lines: list[str] = []
    lines.append("# Migrating from curses to wyby")
    lines.append("")
    lines.append(
        "This guide maps common curses API patterns to their wyby "
        "equivalents.  wyby uses Rich for terminal rendering instead of "
        "curses — this is a deliberate tradeoff, not a drop-in "
        "replacement.  Rich provides cross-platform styling, Windows "
        "support, and composability at the cost of efficient differential "
        "updates.  Not every curses feature has a direct wyby equivalent."
    )
    lines.append("")
    lines.append(
        f"**{len(MIGRATION_ENTRIES)} patterns documented** across "
        f"{len(MIGRATION_CATEGORIES)} categories."
    )
    lines.append("")

    # Categories in display order.
    seen: set[str] = set()
    ordered_cats: list[str] = []
    for cat in _CATEGORY_ORDER:
        if cat in MIGRATION_CATEGORIES:
            ordered_cats.append(cat)
            seen.add(cat)
    # Append any categories not in the fixed order.
    for cat in sorted(MIGRATION_CATEGORIES):
        if cat not in seen:
            ordered_cats.append(cat)

    for cat in ordered_cats:
        lines.append(format_migration_for_category(cat))

    return "\n".join(lines)
