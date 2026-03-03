"""Generate a full API reference for the wyby README.

This module produces structured API reference documentation by cataloging
every public module, class, and function in the wyby package.  It groups
symbols by functional area (core, rendering, input, etc.) and attaches
relevant caveats drawn from the source modules' docstrings.

The primary entry points are:

- :data:`API_MODULES` — catalog of all public modules with one-line
  descriptions and category assignments.
- :data:`API_CAVEATS` — package-level caveats that apply across the API.
- :func:`generate_api_reference` — build a list of :class:`ApiEntry`
  objects from the live package.
- :func:`format_api_reference` — format entries as a Markdown reference
  suitable for inclusion in the README.
- :func:`format_api_caveats` — format the caveats catalog as Markdown.

Caveats:
    - The module catalog (:data:`API_MODULES`) is **maintained manually**.
      When new modules are added to ``wyby/__init__.py``, a corresponding
      entry must be added here.  The test suite verifies consistency
      between the two.
    - Symbol introspection uses ``dir()`` on the live package and
      ``__all__`` from ``wyby.__init__``.  Symbols that are imported but
      not listed in ``__all__`` are excluded.
    - Description text is extracted from class/function docstrings by
      taking the first line.  Multi-line docstrings are truncated.  If
      no docstring is present, a placeholder is used.
    - The default output is Markdown.  It is not a Rich renderable.
"""

from __future__ import annotations

import logging
from pathlib import Path

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Module catalog
# ---------------------------------------------------------------------------


class ModuleInfo:
    """Metadata for one public wyby module.

    Attributes:
        name: The module name without the ``wyby.`` prefix
            (e.g., ``"app"``, ``"scene"``).
        description: One-line description of the module's purpose.
        category: Functional area (``"core"``, ``"rendering"``,
            ``"input"``, ``"ui"``, ``"physics"``, ``"platform"``,
            ``"docs"``).

    Caveats:
        - ``name`` must match the actual module filename (without
          ``.py``).  Internal modules prefixed with ``_`` are excluded
          from the public catalog.
    """

    __slots__ = ("name", "description", "category")

    def __init__(
        self,
        *,
        name: str,
        description: str,
        category: str,
    ) -> None:
        self.name = name
        self.description = description
        self.category = category

    def __repr__(self) -> str:
        return (
            f"ModuleInfo(name={self.name!r}, "
            f"category={self.category!r})"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ModuleInfo):
            return NotImplemented
        return (
            self.name == other.name
            and self.description == other.description
            and self.category == other.category
        )


# Catalog of all public wyby modules.
#
# Caveat: maintained manually — must stay in sync with wyby/__init__.py
# and the actual modules under src/wyby/.  The test suite checks that
# every module imported in __init__.py has a corresponding entry here.
API_MODULES: tuple[ModuleInfo, ...] = (
    # -- Core ---
    ModuleInfo(
        name="app",
        description=(
            "Application entry point and fixed-timestep game loop "
            "(Engine, EngineConfig, QuitSignal)."
        ),
        category="core",
    ),
    ModuleInfo(
        name="scene",
        description=(
            "Scene base class and scene stack for push/pop/replace "
            "scene management."
        ),
        category="core",
    ),
    ModuleInfo(
        name="entity",
        description=(
            "Lightweight entity container with position, tags, and "
            "spatial queries.  Not a full ECS."
        ),
        category="core",
    ),
    ModuleInfo(
        name="component",
        description="Component base class for entity data containers.",
        category="core",
    ),
    ModuleInfo(
        name="position",
        description="Position component with integer x/y coordinates.",
        category="core",
    ),
    ModuleInfo(
        name="velocity",
        description="Velocity component for per-tick movement deltas.",
        category="core",
    ),
    ModuleInfo(
        name="event",
        description="Event and EventQueue for decoupled event dispatch.",
        category="core",
    ),
    ModuleInfo(
        name="save",
        description=(
            "Schema-based save/load helpers using JSON.  No pickle — "
            "games must implement explicit serialization."
        ),
        category="core",
    ),
    # -- Rendering ---
    ModuleInfo(
        name="renderer",
        description=(
            "Cell buffer to Rich renderable conversion, LiveDisplay "
            "wrapper, and console creation."
        ),
        category="rendering",
    ),
    ModuleInfo(
        name="grid",
        description=(
            "Cell, CellBuffer, DoubleBuffer, and terminal clipping.  "
            "The fundamental grid data structures."
        ),
        category="rendering",
    ),
    ModuleInfo(
        name="color",
        description=(
            "Color parsing, palette management, and downgrade/fallback "
            "for limited terminals."
        ),
        category="rendering",
    ),
    ModuleInfo(
        name="layer",
        description=(
            "Layer and LayerStack for compositing multiple cell buffers "
            "with z-ordering."
        ),
        category="rendering",
    ),
    ModuleInfo(
        name="dithering",
        description=(
            "Dithering, aspect ratio correction, and SVG-to-cell "
            "conversion for image assets."
        ),
        category="rendering",
    ),
    ModuleInfo(
        name="transforms",
        description=(
            "Sprite transforms: flip_h, flip_v, rotate (90/180/270), "
            "and tint."
        ),
        category="rendering",
    ),
    ModuleInfo(
        name="animation",
        description="Animation and AnimationFrame for frame-based sprite animation.",
        category="rendering",
    ),
    ModuleInfo(
        name="sprite",
        description=(
            "Sprite loading from images, text, and sprite sheets.  "
            "Requires Pillow for image conversion."
        ),
        category="rendering",
    ),
    ModuleInfo(
        name="unicode",
        description=(
            "Character and grapheme width utilities for accurate "
            "cell-grid layout."
        ),
        category="rendering",
    ),
    ModuleInfo(
        name="transition",
        description=(
            "Scene transition effects: Cut, FadeTransition, and "
            "SlideTransition."
        ),
        category="rendering",
    ),
    ModuleInfo(
        name="alt_screen",
        description=(
            "Alternate screen buffer enable/disable for clean terminal "
            "restore on exit."
        ),
        category="rendering",
    ),
    ModuleInfo(
        name="cursor",
        description="Cursor hide/show and HiddenCursor context manager.",
        category="rendering",
    ),
    # -- Input ---
    ModuleInfo(
        name="input",
        description=(
            "Cross-platform keyboard/mouse input via stdin (termios/msvcrt).  "
            "No system-wide hooks."
        ),
        category="input",
    ),
    ModuleInfo(
        name="input_context",
        description=(
            "InputContext and InputContextStack for scoped keybinding "
            "sets (e.g., menu vs gameplay)."
        ),
        category="input",
    ),
    ModuleInfo(
        name="keymap",
        description="KeyBinding and KeyMap for declarative key-to-action mapping.",
        category="input",
    ),
    # -- UI Widgets ---
    ModuleInfo(
        name="widget",
        description="Widget base class for in-game UI elements.",
        category="ui",
    ),
    ModuleInfo(
        name="button",
        description="Button widget with click/select callback.",
        category="ui",
    ),
    ModuleInfo(
        name="dialog",
        description="Dialog widget for modal message boxes.",
        category="ui",
    ),
    ModuleInfo(
        name="healthbar",
        description="HealthBar widget for visual health/progress display.",
        category="ui",
    ),
    ModuleInfo(
        name="text_input",
        description="TextInput widget for in-game text entry fields.",
        category="ui",
    ),
    ModuleInfo(
        name="focus",
        description="FocusManager for tab-order navigation between widgets.",
        category="ui",
    ),
    ModuleInfo(
        name="layout",
        description=(
            "Layout containers: Alignment, HBox, and VBox for "
            "arranging widgets."
        ),
        category="ui",
    ),
    # -- Physics / Collision ---
    ModuleInfo(
        name="collision",
        description="AABB and axis-aligned bounding box overlap detection.",
        category="physics",
    ),
    ModuleInfo(
        name="collision_accuracy",
        description=(
            "Cell distance, tunneling risk checks, and overlap region "
            "calculation for grid-based collision."
        ),
        category="physics",
    ),
    ModuleInfo(
        name="tile_collision",
        description="TileMap for tile-based collision lookup.",
        category="physics",
    ),
    ModuleInfo(
        name="physics",
        description=(
            "Velocity integration and position sync.  Integer-only "
            "physics — no sub-cell precision."
        ),
        category="physics",
    ),
    ModuleInfo(
        name="particle",
        description="Particle and update_particles for simple particle effects.",
        category="physics",
    ),
    # -- Platform / Diagnostics ---
    ModuleInfo(
        name="diagnostics",
        description=(
            "FPSCounter, RenderTimer, TerminalCapabilities, and "
            "capability detection."
        ),
        category="platform",
    ),
    ModuleInfo(
        name="platform_info",
        description=(
            "Platform differences catalog documenting Windows vs "
            "Unix behaviour."
        ),
        category="platform",
    ),
    ModuleInfo(
        name="resize",
        description=(
            "ResizeHandler and get_terminal_size for responsive "
            "terminal resizing."
        ),
        category="platform",
    ),
    ModuleInfo(
        name="signal_handlers",
        description=(
            "SignalHandler for graceful SIGTERM/SIGINT shutdown without "
            "leaving terminal in raw mode."
        ),
        category="platform",
    ),
    ModuleInfo(
        name="font_variance",
        description=(
            "Font and terminal variance issues catalog.  Documents "
            "rendering differences across terminals."
        ),
        category="platform",
    ),
    ModuleInfo(
        name="render_warnings",
        description=(
            "RenderCost estimation, flicker risk, and emoji width "
            "warnings for proactive diagnostics."
        ),
        category="platform",
    ),
    ModuleInfo(
        name="mouse_warnings",
        description=(
            "Mouse drag/hover event volume warnings for performance "
            "awareness."
        ),
        category="platform",
    ),
    ModuleInfo(
        name="cell_size_map",
        description="CellSizeMap for terminal cell geometry estimation.",
        category="platform",
    ),
    ModuleInfo(
        name="terminal_test",
        description=(
            "TestCard builder for verifying terminal rendering "
            "capabilities."
        ),
        category="platform",
    ),
    ModuleInfo(
        name="project_init",
        description=(
            "Project scaffolding: Git repo initialization and "
            ".gitignore creation for new game projects."
        ),
        category="platform",
    ),
)

# Category display order.
_CATEGORY_ORDER: tuple[str, ...] = (
    "core", "rendering", "input", "ui", "physics", "platform",
)

# Human-readable category labels.
_CATEGORY_LABELS: dict[str, str] = {
    "core": "Core",
    "rendering": "Rendering",
    "input": "Input",
    "ui": "UI Widgets",
    "physics": "Physics & Collision",
    "platform": "Platform & Diagnostics",
}

# Category-level descriptions for the API reference.
_CATEGORY_DESCRIPTIONS: dict[str, str] = {
    "core": (
        "The game loop, scene management, entity model, and event system."
    ),
    "rendering": (
        "Cell grid data structures, Rich-based rendering, color management, "
        "sprites, animation, and visual transforms."
    ),
    "input": (
        "Cross-platform keyboard and mouse input via stdin.  No system-wide "
        "hooks — reads only from the process's own stdin."
    ),
    "ui": (
        "In-game UI widgets rendered into the cell grid.  These are not "
        "Rich widgets — they draw into CellBuffer directly."
    ),
    "physics": (
        "Grid-based collision detection, integer physics, and particle effects.  "
        "All coordinates are integer cell positions — no sub-cell precision."
    ),
    "platform": (
        "Terminal capability detection, platform differences, diagnostics, "
        "and project scaffolding utilities."
    ),
}


def modules_by_category() -> dict[str, list[ModuleInfo]]:
    """Group :data:`API_MODULES` by category.

    Returns:
        A dict mapping category names to lists of :class:`ModuleInfo`.
        Categories are in the canonical display order.

    Caveats:
        - Unknown categories (not in ``_CATEGORY_ORDER``) are appended
          at the end.
    """
    result: dict[str, list[ModuleInfo]] = {}
    for cat in _CATEGORY_ORDER:
        result[cat] = []
    for mod in API_MODULES:
        result.setdefault(mod.category, []).append(mod)
    return result


# ---------------------------------------------------------------------------
# API caveats
# ---------------------------------------------------------------------------


class ApiCaveat:
    """A package-level caveat about the wyby API.

    Attributes:
        topic: Short label (e.g., ``"Pre-release API"``).
        description: Full explanation of the caveat.
        category: Grouping (``"stability"``, ``"rendering"``,
            ``"input"``, ``"architecture"``, ``"platform"``).

    Caveats:
        - These are documentation-only objects with no runtime effect.
    """

    __slots__ = ("topic", "description", "category")

    def __init__(
        self,
        *,
        topic: str,
        description: str,
        category: str,
    ) -> None:
        self.topic = topic
        self.description = description
        self.category = category

    def __repr__(self) -> str:
        return (
            f"ApiCaveat(topic={self.topic!r}, "
            f"category={self.category!r})"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ApiCaveat):
            return NotImplemented
        return (
            self.topic == other.topic
            and self.description == other.description
            and self.category == other.category
        )


# Package-level API caveats.
#
# Caveat: maintained manually — update when major architectural or
# compatibility changes occur.
API_CAVEATS: tuple[ApiCaveat, ...] = (
    # -- Stability ---
    ApiCaveat(
        topic="Pre-release API",
        description=(
            "wyby is v0.1.0dev0.  Every public symbol may change or be "
            "removed without notice.  Pin to an exact commit hash if you "
            "depend on the current API."
        ),
        category="stability",
    ),
    ApiCaveat(
        topic="Not on PyPI",
        description=(
            "wyby is not published to PyPI.  Install from source with "
            "'pip install -e .' or 'pip install -e \".[dev]\"'."
        ),
        category="stability",
    ),
    # -- Rendering ---
    ApiCaveat(
        topic="Rich Live full-frame re-render",
        description=(
            "Rich's Live display re-renders the full renderable every "
            "frame.  There is no differential update or double-buffered "
            "surface at the terminal level.  Flicker is possible on "
            "slow terminals or with large grids (>80x24)."
        ),
        category="rendering",
    ),
    ApiCaveat(
        topic="Terminal cells are not square",
        description=(
            "Terminal cells have roughly a 1:2 aspect ratio (taller than "
            "wide).  A 'square' tile in cell coordinates appears as a "
            "tall rectangle.  Use CELL_ASPECT_RATIO from wyby.dithering "
            "to correct for this when converting images."
        ),
        category="rendering",
    ),
    ApiCaveat(
        topic="Unicode width varies by terminal",
        description=(
            "CJK characters occupy 2 cells; emoji width is terminal-"
            "dependent and may cause misalignment.  Stick to ASCII or "
            "simple Unicode (box-drawing, block elements) for reliable "
            "rendering.  Use wyby.unicode.char_width() for measurement."
        ),
        category="rendering",
    ),
    # -- Input ---
    ApiCaveat(
        topic="No system-wide input hooks",
        description=(
            "wyby reads only from its own stdin via termios (Unix) or "
            "msvcrt (Windows).  The 'keyboard' library is excluded — it "
            "requires root on Linux and installs system-wide key hooks."
        ),
        category="input",
    ),
    ApiCaveat(
        topic="Modifier key limitations",
        description=(
            "Shift is not detectable as a modifier — uppercase letters "
            "arrive as their character directly.  Alt/Meta is not "
            "supported in v0.1.  Ctrl+M and Enter are indistinguishable "
            "(both produce byte 0x0d)."
        ),
        category="input",
    ),
    # -- Architecture ---
    ApiCaveat(
        topic="Not a full ECS",
        description=(
            "The entity model is a simple container with position, tags, "
            "and spatial queries.  There are no systems, no archetype "
            "storage, and no automatic component-update scheduling.  "
            "Game logic lives in Scene.update() as explicit iteration."
        ),
        category="architecture",
    ),
    ApiCaveat(
        topic="No pickle for save/load",
        description=(
            "Games must implement to_save_data()/from_save_data() with "
            "JSON or msgpack.  Pickle deserialization is arbitrary code "
            "execution and is not safe for game saves."
        ),
        category="architecture",
    ),
    ApiCaveat(
        topic="No networking",
        description=(
            "Multiplayer networking is not included in v0.1.  It requires "
            "synchronization, latency compensation, and protocol design "
            "that cannot be meaningfully stubbed."
        ),
        category="architecture",
    ),
    # -- Platform ---
    ApiCaveat(
        topic="Frame rate is terminal-dependent",
        description=(
            "Rendering speed depends on the terminal emulator, OS, grid "
            "size, and style complexity.  15-30 updates/second is "
            "realistic on modern terminals (kitty, WezTerm, iTerm2).  "
            "Windows Console or SSH may be significantly slower."
        ),
        category="platform",
    ),
    ApiCaveat(
        topic="Integer-only physics",
        description=(
            "All coordinates are integer cell positions.  There is no "
            "sub-cell precision, no floating-point velocity, and no "
            "continuous collision detection.  Fast-moving objects may "
            "tunnel through thin walls."
        ),
        category="platform",
    ),
)

# Caveat category display order.
_CAVEAT_CATEGORY_ORDER: tuple[str, ...] = (
    "stability", "rendering", "input", "architecture", "platform",
)

_CAVEAT_CATEGORY_LABELS: dict[str, str] = {
    "stability": "Stability & Installation",
    "rendering": "Rendering",
    "input": "Input",
    "architecture": "Architecture",
    "platform": "Platform & Performance",
}


def caveats_by_category() -> dict[str, list[ApiCaveat]]:
    """Group :data:`API_CAVEATS` by category.

    Returns:
        A dict mapping category names to lists of :class:`ApiCaveat`.
        Categories are in the canonical display order.

    Caveats:
        - Unknown categories are appended at the end.
    """
    result: dict[str, list[ApiCaveat]] = {}
    for cat in _CAVEAT_CATEGORY_ORDER:
        result[cat] = []
    for caveat in API_CAVEATS:
        result.setdefault(caveat.category, []).append(caveat)
    return result


# ---------------------------------------------------------------------------
# API entry (per-symbol documentation)
# ---------------------------------------------------------------------------


class ApiEntry:
    """Documentation entry for one public symbol.

    Attributes:
        name: Fully qualified name (e.g., ``"Engine"``, ``"CellBuffer"``).
        kind: Symbol kind (``"class"``, ``"function"``, ``"constant"``).
        module: Source module name without ``wyby.`` prefix.
        summary: One-line summary from the symbol's docstring.
        category: Functional category inherited from :class:`ModuleInfo`.

    Caveats:
        - ``summary`` is extracted from the first line of the docstring.
          If the symbol has no docstring, a placeholder is used.
    """

    __slots__ = ("name", "kind", "module", "summary", "category")

    def __init__(
        self,
        *,
        name: str,
        kind: str,
        module: str,
        summary: str,
        category: str,
    ) -> None:
        self.name = name
        self.kind = kind
        self.module = module
        self.summary = summary
        self.category = category

    def __repr__(self) -> str:
        return (
            f"ApiEntry(name={self.name!r}, kind={self.kind!r}, "
            f"module={self.module!r})"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ApiEntry):
            return NotImplemented
        return (
            self.name == other.name
            and self.kind == other.kind
            and self.module == other.module
            and self.summary == other.summary
            and self.category == other.category
        )


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------


def _first_docstring_line(obj: object) -> str:
    """Extract the first non-empty line from an object's docstring.

    Returns a placeholder string if no docstring is present.

    Caveats:
        - Only the first line is returned.  Multi-paragraph docstrings
          are truncated without indication.
    """
    doc = getattr(obj, "__doc__", None)
    if not doc:
        return "(no description)"
    for line in doc.strip().splitlines():
        stripped = line.strip()
        if stripped:
            # Remove trailing period for consistency.
            return stripped
    return "(no description)"


def _symbol_kind(obj: object) -> str:
    """Classify a symbol as class, function, or constant."""
    if isinstance(obj, type):
        return "class"
    if callable(obj):
        return "function"
    return "constant"


def _module_name_map() -> dict[str, ModuleInfo]:
    """Build a lookup from module name to ModuleInfo."""
    return {m.name: m for m in API_MODULES}


def _build_symbol_to_module_map() -> dict[str, str]:
    """Build a map from symbol name to source module name.

    Parses ``wyby/__init__.py`` import statements to determine which
    module each symbol was imported from.  This is needed because
    constants (tuples, strings) do not carry ``__module__`` metadata.

    Returns:
        A dict mapping symbol names to bare module names (e.g.,
        ``"Engine"`` -> ``"app"``).

    Caveats:
        - Uses AST parsing of ``__init__.py``.  If the init file uses
          dynamic imports, those symbols are not captured.
    """
    import ast

    init_path = Path(__file__).resolve().parent / "__init__.py"
    if not init_path.is_file():
        return {}

    source = init_path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}

    result: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            # e.g. "from wyby.app import Engine" -> module="wyby.app"
            bare = node.module.replace("wyby.", "")
            for alias in node.names:
                # Use the alias name (as) if present, else the original.
                imported_as = alias.asname if alias.asname else alias.name
                result[imported_as] = bare

    return result


def generate_api_reference() -> list[ApiEntry]:
    """Build API entries from the live wyby package.

    Introspects ``wyby.__init__.__all__`` to discover public symbols,
    resolves each to its object, extracts docstrings, and assigns
    categories based on :data:`API_MODULES`.

    Returns:
        A list of :class:`ApiEntry` sorted by category order then by
        name within each category.

    Caveats:
        - Symbols not traceable to a known module (via ``__module__``)
          are assigned category ``"core"`` as a fallback.
        - Import-time side effects from ``wyby`` submodules may occur.
        - Only symbols listed in ``wyby.__all__`` are included.
    """
    import wyby as _pkg

    all_names: list[str] = getattr(_pkg, "__all__", [])
    mod_map = _module_name_map()
    sym_to_mod = _build_symbol_to_module_map()

    entries: list[ApiEntry] = []
    for sym_name in all_names:
        obj = getattr(_pkg, sym_name, None)
        if obj is None:
            continue

        kind = _symbol_kind(obj)
        summary = _first_docstring_line(obj)

        # Determine which module this symbol comes from.
        # For classes/functions, __module__ is reliable.
        # For constants (tuples, etc.), fall back to AST-derived map.
        obj_module = getattr(obj, "__module__", "") or ""
        bare_module = obj_module.replace("wyby.", "")

        if not bare_module:
            bare_module = sym_to_mod.get(sym_name, "")

        mod_info = mod_map.get(bare_module)
        category = mod_info.category if mod_info else "core"
        module = mod_info.name if mod_info else bare_module

        entries.append(ApiEntry(
            name=sym_name,
            kind=kind,
            module=module,
            summary=summary,
            category=category,
        ))

    # Sort: category order first, then alphabetically within category.
    cat_order = {cat: i for i, cat in enumerate(_CATEGORY_ORDER)}

    def sort_key(entry: ApiEntry) -> tuple[int, str]:
        return (cat_order.get(entry.category, 999), entry.name)

    entries.sort(key=sort_key)

    _logger.debug(
        "Generated API reference with %d entries across %d categories",
        len(entries),
        len({e.category for e in entries}),
    )
    return entries


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------


def format_api_reference(entries: list[ApiEntry]) -> str:
    """Format API entries as a Markdown reference document.

    Produces a document with:

    1. A header and disclaimer.
    2. A module overview table grouped by category.
    3. Per-category symbol tables listing every public class, function,
       and constant.
    4. A caveats section.

    Args:
        entries: List of :class:`ApiEntry` objects.

    Returns:
        A multi-line Markdown string.  Returns ``"No API entries found."``
        if *entries* is empty.

    Caveats:
        - The output is plain Markdown, not a Rich renderable.
        - Very long summaries may wrap awkwardly in narrow terminals.
    """
    if not entries:
        return "No API entries found."

    lines: list[str] = []

    lines.append("## API Reference")
    lines.append("")
    lines.append(
        "> **Pre-release (v0.1.0dev0).** All APIs are unstable and may "
        "change without notice."
    )
    lines.append("")

    # Module overview table.
    lines.append("### Module Overview")
    lines.append("")

    grouped_mods = modules_by_category()
    for category in _CATEGORY_ORDER:
        mods = grouped_mods.get(category, [])
        if not mods:
            continue
        label = _CATEGORY_LABELS.get(category, category.title())
        cat_desc = _CATEGORY_DESCRIPTIONS.get(category, "")
        lines.append(f"#### {label}")
        lines.append("")
        if cat_desc:
            lines.append(cat_desc)
            lines.append("")
        lines.append("| Module | Description |")
        lines.append("|--------|-------------|")
        for mod in mods:
            lines.append(f"| `wyby.{mod.name}` | {mod.description} |")
        lines.append("")

    # Per-category symbol tables.
    lines.append("### Symbols by Category")
    lines.append("")

    # Group entries by category.
    entries_by_cat: dict[str, list[ApiEntry]] = {}
    for cat in _CATEGORY_ORDER:
        entries_by_cat[cat] = []
    for entry in entries:
        entries_by_cat.setdefault(entry.category, []).append(entry)

    for category in _CATEGORY_ORDER:
        cat_entries = entries_by_cat.get(category, [])
        if not cat_entries:
            continue
        label = _CATEGORY_LABELS.get(category, category.title())
        lines.append(f"#### {label}")
        lines.append("")
        lines.append("| Symbol | Kind | Module | Summary |")
        lines.append("|--------|------|--------|---------|")
        for entry in cat_entries:
            lines.append(
                f"| `{entry.name}` | {entry.kind} "
                f"| `wyby.{entry.module}` | {entry.summary} |"
            )
        lines.append("")

    # Caveats section.
    lines.append("### API Caveats")
    lines.append("")
    lines.append(format_api_caveats())

    return "\n".join(lines)


def format_api_caveats() -> str:
    """Format :data:`API_CAVEATS` as Markdown.

    Returns:
        A multi-line Markdown string with caveats grouped by category.

    Caveats:
        - Returns an empty string if :data:`API_CAVEATS` is empty.
    """
    if not API_CAVEATS:
        return ""

    lines: list[str] = []

    grouped = caveats_by_category()
    for category in _CAVEAT_CATEGORY_ORDER:
        caveats = grouped.get(category, [])
        if not caveats:
            continue
        label = _CAVEAT_CATEGORY_LABELS.get(category, category.title())
        lines.append(f"**{label}**")
        lines.append("")
        for caveat in caveats:
            lines.append(f"- **{caveat.topic}**: {caveat.description}")
        lines.append("")

    return "\n".join(lines)
