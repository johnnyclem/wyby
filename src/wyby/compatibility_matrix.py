"""Terminal emulator compatibility matrix for wyby.

This module provides a structured, queryable registry of terminal emulator
compatibility with wyby's rendering and input features.  It covers the most
common terminal emulators across Linux, macOS, and Windows, and documents
the support level for each feature.

The primary entry points are:

- :data:`TERMINALS` — the catalog of :class:`TerminalInfo` entries.
- :data:`FEATURES` — the list of feature names evaluated in the matrix.
- :func:`get_terminal` — look up a terminal by identifier.
- :func:`get_support` — query support level for a terminal + feature pair.
- :func:`format_compatibility_matrix` — render the full matrix as Markdown.

Caveats:
    - This matrix is maintained manually against documented terminal
      behaviour and community reports.  Terminal emulators update
      frequently — a feature marked "none" may gain support in a future
      release.
    - Support levels are broad categories (``"full"``, ``"partial"``,
      ``"none"``).  "Partial" means the feature works in some
      configurations or with known quirks; see the ``notes`` field for
      details.
    - The matrix does not cover every terminal emulator in existence.
      Uncommon or discontinued emulators are omitted.
    - Inside terminal multiplexers (tmux, screen), capabilities
      reflect the multiplexer's passthrough behaviour, not the outer
      terminal.  Running wyby inside tmux may reduce effective
      capability even if the outer terminal is fully capable.
    - "Truecolor" support refers to 24-bit RGB via SGR sequences.
      Some terminals claim truecolor but quantise to 256 colours
      internally.
"""

from __future__ import annotations

import dataclasses


# ---------------------------------------------------------------------------
# Support levels
# ---------------------------------------------------------------------------

SUPPORT_LEVELS: frozenset[str] = frozenset({"full", "partial", "none"})
"""Valid support level values: ``"full"``, ``"partial"``, ``"none"``.

Caveats:
    - ``"partial"`` is deliberately broad — it may mean "works with
      configuration", "works for basic cases", or "works on recent
      versions only".  Consult the ``notes`` dict on the
      :class:`TerminalInfo` for specifics.
"""


# ---------------------------------------------------------------------------
# Feature identifiers
# ---------------------------------------------------------------------------

# Caveat: this tuple defines the column order in the formatted matrix.
# Adding a new feature requires adding a corresponding entry to every
# TerminalInfo in TERMINALS.
FEATURES: tuple[str, ...] = (
    "truecolor",
    "alt_screen",
    "unicode_box_drawing",
    "mouse_click",
    "mouse_hover",
    "mouse_drag",
    "key_sequences",
)
"""Feature identifiers evaluated in the compatibility matrix.

Each feature corresponds to a column in the formatted output:

- ``"truecolor"`` — 24-bit RGB colour via SGR 38;2;r;g;b sequences.
- ``"alt_screen"`` — alternate screen buffer (smcup/rmcup).
- ``"unicode_box_drawing"`` — box-drawing (U+2500) and block element
  (U+2580) characters.
- ``"mouse_click"`` — basic mouse click reporting (SGR mode 1006).
- ``"mouse_hover"`` — mouse motion / hover tracking (mode 1003).
- ``"mouse_drag"`` — mouse button-motion / drag reporting.
- ``"key_sequences"`` — ANSI escape sequences for arrow keys, function
  keys, and modifiers.

Caveats:
    - Emoji rendering, ligature handling, and image protocols (Sixel,
      iTerm2 inline images, kitty graphics) are not included in this
      matrix.  Emoji width is too inconsistent to categorise, and
      image protocols are outside wyby's scope.
"""

_FEATURE_LABELS: dict[str, str] = {
    "truecolor": "Truecolor (24-bit)",
    "alt_screen": "Alt Screen",
    "unicode_box_drawing": "Box Drawing / Blocks",
    "mouse_click": "Mouse Click",
    "mouse_hover": "Mouse Hover",
    "mouse_drag": "Mouse Drag",
    "key_sequences": "Key Sequences",
}


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class TerminalInfo:
    """Compatibility profile for a single terminal emulator.

    Attributes:
        id: Short identifier (e.g., ``"iterm2"``, ``"windows_terminal"``).
        name: Human-readable display name (e.g., ``"iTerm2"``).
        platform: Primary OS — ``"linux"``, ``"macos"``, ``"windows"``,
            or ``"cross-platform"``.
        support: Mapping of feature identifier to support level
            (``"full"``, ``"partial"``, or ``"none"``).
        notes: Per-feature notes explaining partial support or caveats.
            Keys are feature identifiers; values are human-readable
            strings.  Only features with non-obvious behaviour need
            entries.
        general_notes: Overall notes about using wyby with this terminal.

    Caveats:
        - ``platform`` indicates the *primary* platform.  Some
          terminals are available on multiple OSes (e.g., kitty,
          Alacritty) but are listed under their most common platform
          or ``"cross-platform"``.
        - ``support`` must contain an entry for every feature in
          :data:`FEATURES`.  Missing keys will cause :func:`get_support`
          to raise ``KeyError``.
    """

    id: str
    name: str
    platform: str
    support: dict[str, str]
    notes: dict[str, str] = dataclasses.field(default_factory=dict)
    general_notes: str = ""


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------

# Caveat: this catalog is maintained manually.  Terminal emulators are
# listed in approximate order of recommendation for wyby usage.  The
# first entries are the most capable and well-tested.

TERMINALS: tuple[TerminalInfo, ...] = (
    TerminalInfo(
        id="kitty",
        name="kitty",
        platform="cross-platform",
        support={
            "truecolor": "full",
            "alt_screen": "full",
            "unicode_box_drawing": "full",
            "mouse_click": "full",
            "mouse_hover": "full",
            "mouse_drag": "full",
            "key_sequences": "full",
        },
        general_notes=(
            "Excellent wyby compatibility.  GPU-accelerated rendering "
            "provides the best frame rate for large grids."
        ),
    ),
    TerminalInfo(
        id="wezterm",
        name="WezTerm",
        platform="cross-platform",
        support={
            "truecolor": "full",
            "alt_screen": "full",
            "unicode_box_drawing": "full",
            "mouse_click": "full",
            "mouse_hover": "full",
            "mouse_drag": "full",
            "key_sequences": "full",
        },
        general_notes=(
            "Excellent wyby compatibility.  GPU-accelerated, "
            "cross-platform, and highly configurable."
        ),
    ),
    TerminalInfo(
        id="iterm2",
        name="iTerm2",
        platform="macos",
        support={
            "truecolor": "full",
            "alt_screen": "full",
            "unicode_box_drawing": "full",
            "mouse_click": "full",
            "mouse_hover": "full",
            "mouse_drag": "full",
            "key_sequences": "full",
        },
        general_notes="Excellent wyby compatibility on macOS.",
    ),
    TerminalInfo(
        id="windows_terminal",
        name="Windows Terminal",
        platform="windows",
        support={
            "truecolor": "full",
            "alt_screen": "full",
            "unicode_box_drawing": "full",
            "mouse_click": "full",
            "mouse_hover": "full",
            "mouse_drag": "full",
            "key_sequences": "full",
        },
        notes={
            "key_sequences": (
                "Uses ConPTY.  Arrow and function keys produce standard "
                "ANSI sequences, but some extended key combos may differ "
                "from Unix terminals."
            ),
        },
        general_notes=(
            "Recommended terminal for wyby on Windows.  Requires "
            "Windows 10 1903+ for full ConPTY support."
        ),
    ),
    TerminalInfo(
        id="alacritty",
        name="Alacritty",
        platform="cross-platform",
        support={
            "truecolor": "full",
            "alt_screen": "full",
            "unicode_box_drawing": "full",
            "mouse_click": "full",
            "mouse_hover": "full",
            "mouse_drag": "full",
            "key_sequences": "full",
        },
        general_notes=(
            "GPU-accelerated and minimal.  Excellent wyby "
            "compatibility across all platforms."
        ),
    ),
    TerminalInfo(
        id="gnome_terminal",
        name="GNOME Terminal",
        platform="linux",
        support={
            "truecolor": "full",
            "alt_screen": "full",
            "unicode_box_drawing": "full",
            "mouse_click": "full",
            "mouse_hover": "full",
            "mouse_drag": "full",
            "key_sequences": "full",
        },
        general_notes=(
            "Default terminal on many Linux desktops.  Full wyby "
            "compatibility."
        ),
    ),
    TerminalInfo(
        id="konsole",
        name="Konsole",
        platform="linux",
        support={
            "truecolor": "full",
            "alt_screen": "full",
            "unicode_box_drawing": "full",
            "mouse_click": "full",
            "mouse_hover": "full",
            "mouse_drag": "full",
            "key_sequences": "full",
        },
        general_notes="Default KDE terminal.  Full wyby compatibility.",
    ),
    TerminalInfo(
        id="macos_terminal",
        name="macOS Terminal.app",
        platform="macos",
        support={
            "truecolor": "partial",
            "alt_screen": "full",
            "unicode_box_drawing": "full",
            "mouse_click": "partial",
            "mouse_hover": "partial",
            "mouse_drag": "partial",
            "key_sequences": "full",
        },
        notes={
            "truecolor": (
                "Terminal.app supports 256 colours but truecolor (24-bit) "
                "support is unreliable.  Rich falls back to 256-colour "
                "mode.  Colours will differ from truecolor terminals."
            ),
            "mouse_click": (
                "Basic click reporting works but may require enabling "
                "'Allow Mouse Reporting' in the terminal profile."
            ),
            "mouse_hover": (
                "Motion tracking is inconsistent.  Events may be "
                "dropped or delayed."
            ),
            "mouse_drag": (
                "Drag reporting is unreliable.  Button state may not "
                "be preserved during motion."
            ),
        },
        general_notes=(
            "Ships with macOS but has limited capabilities compared to "
            "iTerm2.  wyby works but with reduced colour fidelity and "
            "unreliable mouse support.  iTerm2 is recommended instead."
        ),
    ),
    TerminalInfo(
        id="xterm",
        name="xterm",
        platform="linux",
        support={
            "truecolor": "partial",
            "alt_screen": "full",
            "unicode_box_drawing": "full",
            "mouse_click": "full",
            "mouse_hover": "full",
            "mouse_drag": "full",
            "key_sequences": "full",
        },
        notes={
            "truecolor": (
                "Truecolor requires xterm compiled with --enable-direct-color "
                "(xterm 331+).  Older builds fall back to 256 colours.  "
                "Set COLORTERM=truecolor if the terminal supports it but "
                "the env var is missing."
            ),
        },
        general_notes=(
            "The original X11 terminal emulator.  Capable but "
            "requires modern builds for truecolor."
        ),
    ),
    TerminalInfo(
        id="tmux",
        name="tmux",
        platform="cross-platform",
        support={
            "truecolor": "partial",
            "alt_screen": "full",
            "unicode_box_drawing": "full",
            "mouse_click": "partial",
            "mouse_hover": "partial",
            "mouse_drag": "partial",
            "key_sequences": "full",
        },
        notes={
            "truecolor": (
                "Requires 'set -g default-terminal tmux-256color' and "
                "'set -ga terminal-overrides \",*256col*:Tc\"' in "
                "tmux.conf.  Without this, tmux strips truecolor "
                "sequences."
            ),
            "mouse_click": (
                "Requires 'set -g mouse on' in tmux.conf.  tmux "
                "intercepts mouse events for its own scrollback; "
                "passthrough works but adds latency."
            ),
            "mouse_hover": (
                "Motion events are passed through when mouse mode is "
                "enabled, but tmux may throttle high-frequency motion "
                "events."
            ),
            "mouse_drag": (
                "Drag events are passed through but button state "
                "tracking may be lost if tmux intercepts a click for "
                "pane selection."
            ),
        },
        general_notes=(
            "Terminal multiplexer — adds an extra rendering layer that "
            "roughly doubles rendering latency.  For best wyby "
            "performance, run outside tmux.  If tmux is needed, "
            "configure truecolor and mouse passthrough."
        ),
    ),
    TerminalInfo(
        id="screen",
        name="GNU Screen",
        platform="cross-platform",
        support={
            "truecolor": "none",
            "alt_screen": "full",
            "unicode_box_drawing": "partial",
            "mouse_click": "partial",
            "mouse_hover": "none",
            "mouse_drag": "none",
            "key_sequences": "full",
        },
        notes={
            "truecolor": (
                "GNU Screen does not support truecolor passthrough.  "
                "Colours are quantised to 256.  Use tmux instead if "
                "truecolor is needed."
            ),
            "unicode_box_drawing": (
                "Depends on the outer terminal and locale.  Screen "
                "itself passes through UTF-8, but misconfigured locale "
                "can cause garbled output."
            ),
            "mouse_click": (
                "Basic mouse click passthrough works with "
                "'mousetrack on' in .screenrc, but support is less "
                "reliable than tmux."
            ),
        },
        general_notes=(
            "Legacy multiplexer with limited capability passthrough.  "
            "tmux is recommended over screen for wyby usage."
        ),
    ),
    TerminalInfo(
        id="conhost",
        name="Windows conhost.exe (legacy)",
        platform="windows",
        support={
            "truecolor": "none",
            "alt_screen": "none",
            "unicode_box_drawing": "partial",
            "mouse_click": "none",
            "mouse_hover": "none",
            "mouse_drag": "none",
            "key_sequences": "partial",
        },
        notes={
            "truecolor": (
                "Legacy conhost silently ignores ANSI colour sequences.  "
                "No colour output is possible without Windows Terminal "
                "or ConPTY."
            ),
            "alt_screen": (
                "Alt screen escape sequences are silently ignored.  "
                "Game output mixes with the shell history."
            ),
            "unicode_box_drawing": (
                "Depends on the console font.  Consolas and Cascadia "
                "Code support box-drawing characters; Lucida Console "
                "and raster fonts do not."
            ),
            "key_sequences": (
                "Special keys produce scan-code sequences via msvcrt, "
                "not ANSI escapes.  The wyby input parser handles this, "
                "but modifier detection is limited."
            ),
        },
        general_notes=(
            "Legacy Windows console host.  Not recommended for wyby.  "
            "Use Windows Terminal instead.  Most features are "
            "non-functional."
        ),
    ),
    TerminalInfo(
        id="linux_console",
        name="Linux virtual console (TTY)",
        platform="linux",
        support={
            "truecolor": "none",
            "alt_screen": "full",
            "unicode_box_drawing": "partial",
            "mouse_click": "none",
            "mouse_hover": "none",
            "mouse_drag": "none",
            "key_sequences": "full",
        },
        notes={
            "truecolor": (
                "The Linux framebuffer console supports 16 colours only.  "
                "Rich falls back to basic colour mode."
            ),
            "unicode_box_drawing": (
                "Depends on the console font (setfont).  The default "
                "font may lack box-drawing glyphs.  Install a Unicode "
                "console font like Terminus."
            ),
            "mouse_click": (
                "No mouse support in the Linux virtual console.  "
                "gpm can provide basic mouse reporting but is not "
                "widely deployed."
            ),
        },
        general_notes=(
            "The raw Linux TTY (Ctrl+Alt+F1).  Keyboard input works "
            "but colours and mouse are severely limited.  Use a "
            "graphical terminal emulator for wyby."
        ),
    ),
    TerminalInfo(
        id="ssh",
        name="SSH session",
        platform="cross-platform",
        support={
            "truecolor": "partial",
            "alt_screen": "full",
            "unicode_box_drawing": "full",
            "mouse_click": "partial",
            "mouse_hover": "partial",
            "mouse_drag": "partial",
            "key_sequences": "full",
        },
        notes={
            "truecolor": (
                "Truecolor support depends on both the local terminal "
                "and the remote TERM/COLORTERM environment.  SSH does "
                "not forward COLORTERM by default — add "
                "'SendEnv COLORTERM' to ssh_config and 'AcceptEnv "
                "COLORTERM' to sshd_config."
            ),
            "mouse_click": (
                "Mouse events are forwarded through the SSH channel "
                "but add round-trip latency.  On high-latency "
                "connections, clicks may feel sluggish."
            ),
            "mouse_hover": (
                "High-frequency motion events over SSH add significant "
                "bandwidth.  Hover-based gameplay is impractical over "
                "slow connections."
            ),
            "mouse_drag": (
                "Drag events work but latency makes real-time drag "
                "interactions (e.g., drawing) unusable on connections "
                "above ~50 ms RTT."
            ),
        },
        general_notes=(
            "SSH forwards terminal I/O over the network.  All "
            "capabilities depend on the local terminal emulator.  "
            "Network latency affects every frame — use ssh -C for "
            "compression and keep grids small."
        ),
    ),
)


# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------


def get_terminal(terminal_id: str) -> TerminalInfo:
    """Look up a terminal by its identifier.

    Args:
        terminal_id: One of the ``id`` values in :data:`TERMINALS`
            (e.g., ``"kitty"``, ``"windows_terminal"``).

    Returns:
        The matching :class:`TerminalInfo`.

    Raises:
        ValueError: If *terminal_id* is not found in :data:`TERMINALS`.

    Caveats:
        - Identifiers are case-sensitive.  Use lowercase with
          underscores (e.g., ``"gnome_terminal"``, not
          ``"GNOME Terminal"``).
    """
    for t in TERMINALS:
        if t.id == terminal_id:
            return t
    known = [t.id for t in TERMINALS]
    raise ValueError(
        f"Unknown terminal {terminal_id!r}.  "
        f"Known terminals: {known}"
    )


def get_support(terminal_id: str, feature: str) -> str:
    """Query the support level for a terminal + feature pair.

    Args:
        terminal_id: Terminal identifier (see :func:`get_terminal`).
        feature: Feature identifier (one of :data:`FEATURES`).

    Returns:
        ``"full"``, ``"partial"``, or ``"none"``.

    Raises:
        ValueError: If *terminal_id* or *feature* is not recognised.

    Caveats:
        - Returns the catalogued support level, which may not reflect
          the user's specific terminal version or configuration.
    """
    terminal = get_terminal(terminal_id)
    if feature not in FEATURES:
        raise ValueError(
            f"Unknown feature {feature!r}.  "
            f"Known features: {list(FEATURES)}"
        )
    return terminal.support[feature]


def get_terminals_by_platform(platform: str) -> tuple[TerminalInfo, ...]:
    """Return all terminals for a given platform.

    Args:
        platform: One of ``"linux"``, ``"macos"``, ``"windows"``,
            or ``"cross-platform"``.

    Returns:
        A tuple of matching :class:`TerminalInfo` instances.

    Caveats:
        - ``"cross-platform"`` terminals are not included when
          filtering by a specific OS.  To get all terminals usable on
          Linux, query both ``"linux"`` and ``"cross-platform"``.
    """
    return tuple(t for t in TERMINALS if t.platform == platform)


def get_fully_supported_terminals(feature: str) -> tuple[TerminalInfo, ...]:
    """Return all terminals with full support for a feature.

    Args:
        feature: Feature identifier (one of :data:`FEATURES`).

    Returns:
        A tuple of :class:`TerminalInfo` instances.

    Raises:
        ValueError: If *feature* is not recognised.

    Caveats:
        - "Full" support means the feature is known to work without
          configuration.  It does not account for user-specific font
          or locale issues.
    """
    if feature not in FEATURES:
        raise ValueError(
            f"Unknown feature {feature!r}.  "
            f"Known features: {list(FEATURES)}"
        )
    return tuple(t for t in TERMINALS if t.support[feature] == "full")


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

_SUPPORT_SYMBOLS: dict[str, str] = {
    "full": "Yes",
    "partial": "Partial",
    "none": "No",
}


def format_compatibility_matrix() -> str:
    """Render the full compatibility matrix as a Markdown document.

    Produces a Markdown document with:

    1. A summary table showing support levels for every terminal +
       feature combination.
    2. Per-terminal detail sections with notes and caveats.
    3. General recommendations.

    Returns:
        A multi-line Markdown string.

    Caveats:
        - The output is plain Markdown, not a Rich renderable.
        - Table columns are fixed-width for readability in plain text
          but render better in Markdown viewers.
    """
    lines: list[str] = []

    # Header
    lines.append("# wyby Terminal Compatibility Matrix")
    lines.append("")
    lines.append(
        "This document shows which terminal features wyby depends on "
        "and how well each terminal emulator supports them.  Use this "
        "to choose a terminal for development and to set expectations "
        "for end users."
    )
    lines.append("")
    lines.append(
        f"**{len(TERMINALS)} terminals evaluated** across "
        f"**{len(FEATURES)} features**."
    )
    lines.append("")

    # Caveats section
    lines.append("## Important Caveats")
    lines.append("")
    lines.append(
        "- **This matrix is manually maintained** and reflects known "
        "behaviour as of wyby v0.1.0dev0.  Terminal emulators update "
        "frequently."
    )
    lines.append(
        "- **\"Partial\" means it works with caveats** — see the "
        "per-terminal notes below for details."
    )
    lines.append(
        "- **Multiplexers (tmux, screen) reduce capabilities** even "
        "if the outer terminal is fully capable."
    )
    lines.append(
        "- **SSH sessions inherit the local terminal's capabilities** "
        "but add network latency to every frame."
    )
    lines.append(
        "- **Emoji rendering is excluded** from this matrix because "
        "width handling is too inconsistent across terminals to "
        "categorise reliably."
    )
    lines.append("")

    # Summary table
    lines.append("## Support Matrix")
    lines.append("")

    # Build header row
    feature_headers = [_FEATURE_LABELS.get(f, f) for f in FEATURES]
    header = "| Terminal | " + " | ".join(feature_headers) + " |"
    separator = "|" + "|".join(
        "-" * (len(h) + 2) for h in ["Terminal"] + feature_headers
    ) + "|"
    lines.append(header)
    lines.append(separator)

    # Build data rows
    for terminal in TERMINALS:
        cells = [terminal.name]
        for feature in FEATURES:
            level = terminal.support[feature]
            cells.append(_SUPPORT_SYMBOLS.get(level, level))
        lines.append("| " + " | ".join(cells) + " |")

    lines.append("")

    # Per-terminal details
    lines.append("## Terminal Details")
    lines.append("")

    for terminal in TERMINALS:
        lines.append(f"### {terminal.name}")
        lines.append("")
        lines.append(f"**Platform:** {terminal.platform}")
        lines.append("")

        if terminal.general_notes:
            lines.append(terminal.general_notes)
            lines.append("")

        if terminal.notes:
            lines.append("**Feature notes:**")
            lines.append("")
            for feature_id, note in terminal.notes.items():
                label = _FEATURE_LABELS.get(feature_id, feature_id)
                lines.append(f"- **{label}:** {note}")
            lines.append("")

    # Recommendations
    lines.append("## Recommendations")
    lines.append("")
    lines.append("### Best terminals for wyby development")
    lines.append("")
    lines.append(
        "These terminals have full support for all wyby features:"
    )
    lines.append("")
    full_support = [
        t for t in TERMINALS
        if all(t.support[f] == "full" for f in FEATURES)
    ]
    for t in full_support:
        lines.append(f"- **{t.name}** ({t.platform})")
    lines.append("")

    lines.append("### Terminals to avoid")
    lines.append("")
    lines.append(
        "These terminals have significant limitations that affect "
        "core wyby functionality:"
    )
    lines.append("")
    avoid = [
        t for t in TERMINALS
        if sum(1 for f in FEATURES if t.support[f] == "none") >= 3
    ]
    for t in avoid:
        none_count = sum(1 for f in FEATURES if t.support[f] == "none")
        lines.append(
            f"- **{t.name}** — {none_count} unsupported features"
        )
    lines.append("")

    lines.append("### Tips for cross-platform games")
    lines.append("")
    lines.append(
        "- Always provide keyboard-only controls as a fallback for "
        "terminals without mouse support."
    )
    lines.append(
        "- Design colour palettes that degrade gracefully to 256 "
        "colours for terminals without truecolor."
    )
    lines.append(
        "- Use ASCII and box-drawing characters (U+2500-U+257F) "
        "rather than emoji for game tiles."
    )
    lines.append(
        "- Test in at least one terminal per target platform "
        "(e.g., iTerm2 on macOS, Windows Terminal on Windows, "
        "GNOME Terminal on Linux)."
    )
    lines.append(
        "- Avoid relying on mouse hover or drag for core gameplay — "
        "these are the least consistently supported features."
    )

    return "\n".join(lines)
