"""Comprehensive catalog of all wyby framework limitations and caveats.

This module provides a single, queryable registry of every known limitation
and caveat across the entire wyby framework.  Individual subsystem modules
(:mod:`wyby.render_warnings`, :mod:`wyby.mouse_warnings`,
:mod:`wyby.font_variance`, :mod:`wyby.controls_doc`) document domain-specific
caveats in detail.  This module aggregates them into a unified catalog and
adds framework-wide limitations that span multiple subsystems.

The primary entry points are:

- :data:`LIMITATIONS` — the complete catalog of :class:`Limitation` entries.
- :data:`LIMITATION_CATEGORIES` — the set of all category names.
- :func:`get_limitations_by_category` — filter by category.
- :func:`get_limitations_by_severity` — filter by severity level.
- :func:`format_limitations_doc` — render the catalog as Markdown.
- :func:`format_limitations_for_category` — render a single category.

Caveats:
    - This catalog is maintained manually.  When subsystem behaviour
      changes, both the subsystem module and this catalog may need
      updating.
    - Severity levels are subjective assessments of impact on typical
      game development, not objective measurements.
    - The catalog covers v0.1 (pre-release) limitations.  Some entries
      may become outdated as the framework matures.
    - Not all limitations are bugs — many are intentional design
      decisions documented here for transparency.
"""

from __future__ import annotations

import dataclasses


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class Limitation:
    """A documented limitation or caveat of the wyby framework.

    Attributes:
        category: Broad area of the framework (e.g., ``"rendering"``,
            ``"input"``, ``"entity_model"``, ``"physics"``).
        topic: Short human-readable label (e.g.,
            ``"No frame rate guarantee"``).
        description: Full explanation of the limitation, including
            why it exists and what the practical impact is.
        severity: Impact level — ``"info"`` (awareness only),
            ``"warning"`` (may affect some use cases), or
            ``"critical"`` (affects most users or has no workaround).
        workaround: Suggested mitigation or workaround, or ``None``
            if no practical workaround exists.

    Caveats:
        - ``severity`` is a subjective assessment.  A ``"warning"``
          for one project may be ``"critical"`` for another.
        - ``workaround`` describes the *best known* mitigation, not
          a complete solution.
    """

    category: str
    topic: str
    description: str
    severity: str
    workaround: str | None = None


# Allowed severity levels.
SEVERITIES: frozenset[str] = frozenset({"info", "warning", "critical"})
"""Valid severity values for :attr:`Limitation.severity`."""


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------

# Caveat: this catalog is maintained manually alongside the subsystem
# modules.  It reflects wyby v0.1.0dev0.  New modules or changed
# behaviour may require updates to this list.

LIMITATIONS: tuple[Limitation, ...] = (
    # -- Rendering -----------------------------------------------------------
    Limitation(
        category="rendering",
        topic="No frame rate guarantee",
        description=(
            "Terminal rendering performance depends on the terminal emulator, "
            "OS, grid size, style complexity, and connection type (local vs "
            "SSH).  Realistic throughput is 15-30 updates/second on modern "
            "terminals.  60 FPS is not a meaningful target for terminal "
            "output.  wyby does not and cannot guarantee any specific frame "
            "rate."
        ),
        severity="warning",
        workaround=(
            "Use FPSCounter to measure actual performance.  Reduce grid "
            "dimensions or style density if frame rate is too low.  Use "
            "estimate_render_cost() to predict cost before committing to "
            "a grid size."
        ),
    ),
    Limitation(
        category="rendering",
        topic="No double buffering in Rich",
        description=(
            "Rich's Live display re-renders the entire renderable on each "
            "refresh.  Unlike curses, it does not track which cells changed "
            "between frames.  This means CPU cost scales with total grid "
            "size, not with the number of changed cells."
        ),
        severity="warning",
        workaround=(
            "Keep grids small (under 4,800 cells for 30 FPS on fast "
            "terminals).  Minimise per-cell styling — uniform-style runs "
            "are cheaper because Rich batches them."
        ),
    ),
    Limitation(
        category="rendering",
        topic="Flicker on slow terminals",
        description=(
            "Large grids or complex styling may cause visible flicker on "
            "slow terminals (Windows cmd.exe, legacy conhost), over SSH, "
            "or inside tmux/screen.  The terminal's own parsing and "
            "compositing time contributes to flicker, which is outside "
            "wyby's control."
        ),
        severity="warning",
        workaround=(
            "Use check_flicker_risk() to assess risk before choosing grid "
            "dimensions.  Recommend fast terminals (kitty, WezTerm, iTerm2, "
            "Windows Terminal) to users."
        ),
    ),
    Limitation(
        category="rendering",
        topic="Cell aspect ratio is not square",
        description=(
            "Terminal character cells are rectangular (typically ~2:1 "
            "height:width).  A 'square' game tile in cell coordinates "
            "appears as a tall rectangle.  The exact ratio varies by "
            "font and terminal, and there is no reliable way to detect "
            "it at runtime."
        ),
        severity="info",
        workaround=(
            "Use correct_aspect_ratio() to compensate when converting "
            "images.  Accept the 2.0 default or expose an aspect ratio "
            "configuration option."
        ),
    ),
    # -- Input ---------------------------------------------------------------
    Limitation(
        category="input",
        topic="No system-wide input hooks",
        description=(
            "wyby only reads from the process's own stdin.  It cannot "
            "capture global keyboard events.  The keyboard library is "
            "explicitly excluded because it requires elevated permissions "
            "and raises security concerns."
        ),
        severity="info",
        workaround=None,
    ),
    Limitation(
        category="input",
        topic="Shift not detectable as modifier",
        description=(
            "Shift is not reported as a modifier flag.  Uppercase letters "
            "arrive as their uppercase character directly (e.g., "
            "KeyEvent(key='A'), not KeyEvent(key='a', shift=True)).  "
            "Shift+digit produces the shifted character (e.g., '!' for "
            "Shift+1)."
        ),
        severity="warning",
        workaround=(
            "Bind uppercase characters directly if Shift-based controls "
            "are needed.  Do not rely on detecting Shift as a separate "
            "modifier."
        ),
    ),
    Limitation(
        category="input",
        topic="Alt/Meta modifier not supported",
        description=(
            "Alt+key sequences (ESC followed by a character) are parsed "
            "as two separate events: an Escape event and a character "
            "event.  Alt key combos are unreliable for game controls."
        ),
        severity="warning",
        workaround=(
            "Avoid Alt+key bindings in games.  Use Ctrl+letter or "
            "direct character keys instead."
        ),
    ),
    Limitation(
        category="input",
        topic="Ctrl+M and Enter are indistinguishable",
        description=(
            "Ctrl+M and Enter both produce byte 0x0d (carriage return) on "
            "most terminals.  The input parser cannot tell them apart — "
            "both produce KeyEvent(key='enter').  Similarly, Ctrl+I and "
            "Tab both produce 0x09."
        ),
        severity="warning",
        workaround=(
            "Do not bind distinct actions to Enter and Ctrl+M, or to "
            "Tab and Ctrl+I."
        ),
    ),
    Limitation(
        category="input",
        topic="Terminal raw mode cleanup on abnormal exit",
        description=(
            "InputManager modifies terminal state (raw mode).  If the "
            "process is killed with SIGKILL or crashes without calling "
            "stop(), the terminal is left in raw mode with no echo and "
            "no line editing."
        ),
        severity="warning",
        workaround=(
            "Use Engine (which handles cleanup via signal handlers) or "
            "ensure InputManager.stop() is called in a finally block.  "
            "If the terminal is stuck, run 'reset' or 'stty sane'."
        ),
    ),
    # -- Mouse ---------------------------------------------------------------
    Limitation(
        category="mouse",
        topic="Mouse support varies by terminal",
        description=(
            "Mouse event reporting uses SGR extended mode (xterm mode "
            "1006).  Support varies: xterm, iTerm2, Windows Terminal, "
            "GNOME Terminal, Alacritty, and kitty support it well.  "
            "macOS Terminal.app has limited support.  tmux/screen require "
            "'set -g mouse on' and may throttle events."
        ),
        severity="warning",
        workaround=(
            "Always provide keyboard-only fallback controls.  Use "
            "check_mouse_hover_warning() and check_mouse_drag_warning() "
            "to surface terminal-specific issues."
        ),
    ),
    Limitation(
        category="mouse",
        topic="Hover and drag inconsistency",
        description=(
            "Mouse motion tracking (mode 1003) is less consistently "
            "supported than basic click reporting.  Some terminals drop "
            "motion events, report stale coordinates, or fail to report "
            "button state during drags.  Dragging outside the terminal "
            "window may silently stop events."
        ),
        severity="warning",
        workaround=(
            "Implement timeout-based button release detection.  Do not "
            "rely on hover for core gameplay.  Test on target terminals."
        ),
    ),
    # -- Entity model --------------------------------------------------------
    Limitation(
        category="entity_model",
        topic="Not a full ECS",
        description=(
            "wyby's entity system is a simple composition model, not a "
            "full Entity Component System.  There is no archetype storage, "
            "no bitset component masks, and no automatic system "
            "scheduling.  Entities are Python objects with components "
            "stored in a dict keyed by class."
        ),
        severity="info",
        workaround=(
            "For terminal games with tens to hundreds of entities, this "
            "is sufficient.  If your game outgrows it, bring in the esper "
            "library for ECS and use wyby only for rendering."
        ),
    ),
    Limitation(
        category="entity_model",
        topic="No automatic component updates",
        description=(
            "The framework does not automatically call update() on "
            "components or systems.  The game must explicitly call "
            "entity.update(dt) or iterate entities and update them "
            "in the scene's update method."
        ),
        severity="info",
        workaround=(
            "Call update_velocities() and sync_positions() in your "
            "scene's update() method.  Manage update order explicitly."
        ),
    ),
    Limitation(
        category="entity_model",
        topic="Single-component queries only",
        description=(
            "get_entities_by_component() queries for entities that have "
            "a single component type.  There is no built-in multi-"
            "component query (e.g., 'all entities with both Position "
            "and Velocity')."
        ),
        severity="info",
        workaround=(
            "Chain single-component queries with set intersection, or "
            "iterate entities and check for multiple components manually."
        ),
    ),
    # -- Physics -------------------------------------------------------------
    Limitation(
        category="physics",
        topic="Not a physics engine",
        description=(
            "wyby provides movement helpers and collision detection "
            "primitives only.  update_velocities() uses forward-Euler "
            "integration, which is simple but accumulates error.  There "
            "is no rigid-body dynamics, no constraint solver, and no "
            "continuous collision detection."
        ),
        severity="info",
        workaround=(
            "Implement game-specific collision response (blocking, "
            "bouncing, sliding) in your scene logic.  For complex "
            "physics, use a dedicated library."
        ),
    ),
    Limitation(
        category="physics",
        topic="Detection only, no collision response",
        description=(
            "AABB overlap and TileMap queries detect collisions but do "
            "not resolve them.  Separation, bouncing, and blocking are "
            "the game's responsibility."
        ),
        severity="info",
        workaround=(
            "After detecting a collision with aabb_overlap() or "
            "TileMap.is_solid(), move the entity back or adjust its "
            "velocity in your game logic."
        ),
    ),
    # -- Terminal compatibility ----------------------------------------------
    Limitation(
        category="terminal",
        topic="Unicode width inconsistency",
        description=(
            "CJK characters occupy 2 cells, but Ambiguous-width "
            "characters may be 1 or 2 depending on terminal locale.  "
            "Emoji width is especially unreliable — some terminals "
            "render emoji as 1 column, others as 2, and multi-codepoint "
            "sequences are unpredictable."
        ),
        severity="warning",
        workaround=(
            "Use ASCII, box-drawing (U+2500-U+257F), and block elements "
            "(U+2580-U+259F) for game tiles.  Avoid emoji where column "
            "alignment matters.  Use check_emoji_warning() to flag "
            "problematic text."
        ),
    ),
    Limitation(
        category="terminal",
        topic="Truecolor not universal",
        description=(
            "Most modern terminals support truecolor (24-bit colour), "
            "but some do not (older xterm, Linux virtual console, some "
            "SSH setups).  Rich handles fallback to 256 or 16 colours, "
            "but the visual result will differ."
        ),
        severity="info",
        workaround=(
            "Use detect_capabilities() to check colour support at "
            "startup.  Design colour palettes that degrade gracefully "
            "to 256 colours."
        ),
    ),
    Limitation(
        category="terminal",
        topic="Ligature fonts break grid alignment",
        description=(
            "Programming-ligature fonts (Fira Code, JetBrains Mono, "
            "Cascadia Code) may merge adjacent box-drawing or operator "
            "characters into ligature glyphs, breaking cell-grid "
            "alignment."
        ),
        severity="warning",
        workaround=(
            "Recommend users disable ligatures in their terminal "
            "settings when playing wyby games, or use a non-ligature "
            "monospace font."
        ),
    ),
    # -- Save/Load -----------------------------------------------------------
    Limitation(
        category="save_load",
        topic="No automatic serialisation",
        description=(
            "wyby does not automatically serialize scene objects, entity "
            "instances, or runtime state.  The game must implement "
            "to_save_data() and from_save_data() methods that produce "
            "and consume plain data structures."
        ),
        severity="info",
        workaround=(
            "Implement explicit save/load methods using JSON or msgpack.  "
            "This is intentional — implicit serialisation leads to "
            "versioning issues and pickle is unsafe."
        ),
    ),
    Limitation(
        category="save_load",
        topic="No pickle — by design",
        description=(
            "Pickle is explicitly excluded from wyby.  Pickle "
            "deserialization is arbitrary code execution, making it "
            "unsafe for loading save files from untrusted sources.  "
            "Implicit object-graph serialisation also causes opaque "
            "versioning bugs."
        ),
        severity="info",
        workaround=None,
    ),
    # -- Networking ----------------------------------------------------------
    Limitation(
        category="networking",
        topic="No networking support",
        description=(
            "Multiplayer and networking are out of scope for v0.1.  "
            "Networking is a major subsystem requiring synchronisation "
            "strategy, latency compensation, and protocol design.  "
            "These cannot be meaningfully stubbed."
        ),
        severity="info",
        workaround=(
            "Games can implement their own networking layer.  wyby "
            "handles rendering; the game is responsible for network "
            "communication."
        ),
    ),
    # -- Image conversion ----------------------------------------------------
    Limitation(
        category="image_conversion",
        topic="Significant quality loss",
        description=(
            "Converting raster images to terminal cell grids involves "
            "extreme downsampling (a 200x200 image mapped to a 40x20 "
            "grid loses ~99% of its pixels), colour quantisation, and "
            "aspect ratio distortion.  The result looks like terminal "
            "art, not the original image."
        ),
        severity="info",
        workaround=(
            "Accept that converted images are approximations.  Use "
            "prepare_for_terminal() for the full pipeline (resize + "
            "aspect correction + quantise).  Pre-convert at load time "
            "and cache the result."
        ),
    ),
    Limitation(
        category="image_conversion",
        topic="Convert once, cache, reuse",
        description=(
            "Image-to-entity conversion creates one Entity per pixel. "
            "This is expensive — do not call from_image() per frame.  "
            "Convert images at load time and reuse the entity list."
        ),
        severity="critical",
        workaround=(
            "Call from_image() or prepare_for_terminal() once during "
            "scene initialization.  Store the resulting entities and "
            "render them from the cache every frame."
        ),
    ),
    Limitation(
        category="image_conversion",
        topic="Pillow is an optional dependency",
        description=(
            "Image conversion requires Pillow (pillow >= 9.0), which is "
            "an optional dependency.  SVG support requires cairosvg, "
            "which depends on the system libcairo library.  Games that "
            "don't use image conversion don't need these dependencies."
        ),
        severity="info",
        workaround=(
            "Install with pip install 'wyby[images]' for Pillow support, "
            "or install pillow and/or cairosvg manually."
        ),
    ),
    # -- Platform ------------------------------------------------------------
    Limitation(
        category="platform",
        topic="Windows input backend differs",
        description=(
            "On Windows, wyby uses msvcrt for input instead of termios.  "
            "Special keys produce two-byte scan-code sequences rather "
            "than ANSI escapes.  The parser normalises key names, but "
            "timing and buffering behaviour may differ from Unix."
        ),
        severity="info",
        workaround=(
            "Test on Windows if cross-platform support is needed.  "
            "Key names are normalised — the same event.key strings work "
            "on both platforms."
        ),
    ),
    Limitation(
        category="platform",
        topic="SSH adds latency to all rendering",
        description=(
            "Over SSH, every frame's ANSI output must traverse the "
            "network.  Even small grids feel laggy on high-latency "
            "connections.  This is inherent to terminal-over-network "
            "and outside wyby's control."
        ),
        severity="warning",
        workaround=(
            "Use ssh -C for compression on large frames.  Reduce grid "
            "size and style complexity for SSH-friendly games.  Accept "
            "lower frame rates."
        ),
    ),
    Limitation(
        category="platform",
        topic="tmux/screen double rendering overhead",
        description=(
            "Terminal multiplexers (tmux, screen) add an extra rendering "
            "layer.  The multiplexer receives wyby's ANSI output, "
            "re-renders into its own virtual screen, and writes that to "
            "the outer terminal.  This roughly doubles rendering latency."
        ),
        severity="warning",
        workaround=(
            "For best performance, run wyby games directly in the "
            "terminal, not inside tmux or screen.  If a multiplexer is "
            "needed, prefer tmux with 'set -g mouse on' for mouse "
            "passthrough."
        ),
    ),
    # -- API stability -------------------------------------------------------
    Limitation(
        category="api",
        topic="Unstable pre-release API",
        description=(
            "wyby is v0.1.0dev0 (pre-release).  The API is subject to "
            "breaking changes without deprecation warnings.  Nothing "
            "is available on PyPI yet."
        ),
        severity="critical",
        workaround=(
            "Pin to a specific commit or version when depending on "
            "wyby.  Expect API changes between releases."
        ),
    ),
)


LIMITATION_CATEGORIES: frozenset[str] = frozenset(
    lim.category for lim in LIMITATIONS
)
"""All distinct category names in :data:`LIMITATIONS`."""

# Human-readable category labels, in display order.
_CATEGORY_ORDER: tuple[str, ...] = (
    "rendering",
    "input",
    "mouse",
    "entity_model",
    "physics",
    "terminal",
    "image_conversion",
    "save_load",
    "networking",
    "platform",
    "api",
)

_CATEGORY_LABELS: dict[str, str] = {
    "rendering": "Rendering",
    "input": "Input Handling",
    "mouse": "Mouse Support",
    "entity_model": "Entity Model",
    "physics": "Physics",
    "terminal": "Terminal Compatibility",
    "image_conversion": "Image Conversion",
    "save_load": "Save / Load",
    "networking": "Networking",
    "platform": "Platform Differences",
    "api": "API Stability",
}

_SEVERITY_LABELS: dict[str, str] = {
    "info": "Info",
    "warning": "Warning",
    "critical": "Critical",
}


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------


def get_limitations_by_category(
    category: str,
) -> tuple[Limitation, ...]:
    """Return all limitations in the given category.

    Args:
        category: One of the category names in
            :data:`LIMITATION_CATEGORIES`.

    Returns:
        A tuple of :class:`Limitation` instances.

    Raises:
        ValueError: If *category* is not a recognised category name.

    Caveats:
        - Categories are derived from the built-in catalog.  Custom
          limitations added at runtime are not supported.
    """
    if category not in LIMITATION_CATEGORIES:
        raise ValueError(
            f"Unknown category {category!r}.  "
            f"Known categories: {sorted(LIMITATION_CATEGORIES)}"
        )
    return tuple(lim for lim in LIMITATIONS if lim.category == category)


def get_limitations_by_severity(
    severity: str,
) -> tuple[Limitation, ...]:
    """Return all limitations at the given severity level.

    Args:
        severity: One of ``"info"``, ``"warning"``, or ``"critical"``.

    Returns:
        A tuple of :class:`Limitation` instances.

    Raises:
        ValueError: If *severity* is not a valid severity level.

    Caveats:
        - Severity is a subjective assessment.  The returned list
          includes all limitations with the exact severity string,
          not a threshold filter.
    """
    if severity not in SEVERITIES:
        raise ValueError(
            f"Unknown severity {severity!r}.  "
            f"Valid severities: {sorted(SEVERITIES)}"
        )
    return tuple(lim for lim in LIMITATIONS if lim.severity == severity)


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------


def format_limitations_for_category(category: str) -> str:
    """Format all limitations in a single category as Markdown.

    Args:
        category: One of the category names in
            :data:`LIMITATION_CATEGORIES`.

    Returns:
        A multi-line Markdown string.

    Raises:
        ValueError: If *category* is not recognised.

    Caveats:
        - The output is plain Markdown, not a Rich renderable.
    """
    lims = get_limitations_by_category(category)
    label = _CATEGORY_LABELS.get(category, category.replace("_", " ").title())

    lines: list[str] = []
    lines.append(f"## {label}")
    lines.append("")

    for lim in lims:
        sev_label = _SEVERITY_LABELS.get(lim.severity, lim.severity)
        lines.append(f"### {lim.topic}")
        lines.append("")
        lines.append(f"**Severity:** {sev_label}")
        lines.append("")
        lines.append(lim.description)
        lines.append("")
        if lim.workaround:
            lines.append(f"**Workaround:** {lim.workaround}")
            lines.append("")

    return "\n".join(lines)


def format_limitations_doc() -> str:
    """Format the complete limitations catalog as a Markdown document.

    Produces a document with all limitations grouped by category,
    each with severity, description, and workaround (if available).

    Returns:
        A multi-line Markdown string.

    Caveats:
        - The output is a standalone reference document.
        - Categories are listed in a fixed display order.  Categories
          present in the catalog but not in the display order are
          appended at the end.
    """
    lines: list[str] = []
    lines.append("# wyby Limitations and Caveats")
    lines.append("")
    lines.append(
        "This document catalogs all known limitations and caveats of the "
        "wyby framework.  Understanding these constraints helps you design "
        "games that work well within wyby's intended scope."
    )
    lines.append("")

    # Summary counts.
    critical = len(get_limitations_by_severity("critical"))
    warning = len(get_limitations_by_severity("warning"))
    info = len(get_limitations_by_severity("info"))
    lines.append(
        f"**{len(LIMITATIONS)} limitations documented:** "
        f"{critical} critical, {warning} warning, {info} info."
    )
    lines.append("")

    # Categories in display order.
    seen: set[str] = set()
    ordered_cats: list[str] = []
    for cat in _CATEGORY_ORDER:
        if cat in LIMITATION_CATEGORIES:
            ordered_cats.append(cat)
            seen.add(cat)
    # Append any categories not in the fixed order.
    for cat in sorted(LIMITATION_CATEGORIES):
        if cat not in seen:
            ordered_cats.append(cat)

    for cat in ordered_cats:
        lines.append(format_limitations_for_category(cat))

    return "\n".join(lines)
