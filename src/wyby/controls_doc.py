"""Generate controls documentation for wyby examples and games.

This module produces comprehensive controls reference documentation that
catalogs supported key names, documents modifier and platform caveats, and
generates per-example controls guides.  It complements :mod:`wyby.example_readme`
(which extracts controls from source code) by adding the framework-level
context that players and developers need — which modifiers work, which keys
are ambiguous, and what platform differences to expect.

The primary entry points are:

- :data:`SUPPORTED_KEYS` — catalog of all key names the input parser
  recognises, with human-readable labels and categories.
- :data:`CONTROL_CAVEATS` — framework-level caveats about keyboard and
  mouse input that apply across all games.
- :func:`controls_for_example` — generate a :class:`ControlsDoc` for a
  single example file, combining extracted controls with relevant caveats.
- :func:`controls_for_all_examples` — generate docs for all bundled
  examples.
- :func:`format_controls_doc` — format a :class:`ControlsDoc` as Markdown.
- :func:`format_controls_reference` — format the full supported-keys
  reference as Markdown.

Caveats:
    - Key name detection in examples is **heuristic** — it delegates to
      :func:`wyby.example_readme._extract_controls` which searches for
      hint strings and ``event.key`` comparisons in source code.  Controls
      defined through indirect patterns (e.g., lookup tables, dynamic
      dispatch) may not be detected.
    - The :data:`SUPPORTED_KEYS` catalog reflects keys parsed by
      :func:`wyby.input.parse_input_events`.  Terminal emulators vary in
      which keys they report — a key listed here may not produce events
      on all terminals.  See :mod:`wyby.input` for terminal-specific
      details.
    - Modifier caveats (Shift, Alt, Ctrl) are terminal-dependent.  The
      caveats in :data:`CONTROL_CAVEATS` describe the *typical* behaviour
      across modern terminals, but edge cases exist.
    - The default examples directory is resolved relative to this module's
      file path (``../../examples/`` from ``src/wyby/``).  If wyby is
      installed as a wheel or zip, the examples directory may not exist.
      :func:`controls_for_all_examples` returns an empty list in that case.
"""

from __future__ import annotations

import logging
from pathlib import Path

from wyby.example_readme import ExampleReadme, generate_example_readme

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Supported key catalog
# ---------------------------------------------------------------------------


class SupportedKey:
    """A key recognised by the wyby input parser.

    Attributes:
        name: The key name string as it appears in :attr:`KeyEvent.key`
            (e.g., ``"up"``, ``"space"``, ``"a"``).
        label: Human-readable display label (e.g., ``"Up Arrow"``,
            ``"Space Bar"``, ``"A"``).
        category: Grouping for documentation (``"arrow"``, ``"modifier"``,
            ``"navigation"``, ``"printable"``, ``"special"``).
        caveat: Optional caveat specific to this key, or ``None``.

    Caveats:
        - ``name`` must match :attr:`KeyEvent.key` values exactly —
          key names are case-sensitive lowercase strings.
        - ``label`` is for display only and has no runtime effect.
    """

    __slots__ = ("name", "label", "category", "caveat")

    def __init__(
        self,
        *,
        name: str,
        label: str,
        category: str,
        caveat: str | None = None,
    ) -> None:
        self.name = name
        self.label = label
        self.category = category
        self.caveat = caveat

    def __repr__(self) -> str:
        return (
            f"SupportedKey(name={self.name!r}, "
            f"label={self.label!r}, category={self.category!r})"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SupportedKey):
            return NotImplemented
        return (
            self.name == other.name
            and self.label == other.label
            and self.category == other.category
            and self.caveat == other.caveat
        )


# Catalog of all keys that parse_input_events can produce.
#
# Caveat: this catalog is maintained manually alongside the parser in
# input.py.  If new keys are added to the parser, they must be added
# here as well.  The test suite verifies consistency.
SUPPORTED_KEYS: tuple[SupportedKey, ...] = (
    # -- Arrow keys ---
    SupportedKey(
        name="up", label="Up Arrow", category="arrow",
    ),
    SupportedKey(
        name="down", label="Down Arrow", category="arrow",
    ),
    SupportedKey(
        name="left", label="Left Arrow", category="arrow",
    ),
    SupportedKey(
        name="right", label="Right Arrow", category="arrow",
    ),
    # -- Navigation ---
    SupportedKey(
        name="home", label="Home", category="navigation",
    ),
    SupportedKey(
        name="end", label="End", category="navigation",
    ),
    SupportedKey(
        name="pageup", label="Page Up", category="navigation",
    ),
    SupportedKey(
        name="pagedown", label="Page Down", category="navigation",
    ),
    SupportedKey(
        name="insert", label="Insert", category="navigation",
        caveat=(
            "Not all keyboards have a dedicated Insert key.  Laptops "
            "often require a Fn+key combo to produce Insert."
        ),
    ),
    SupportedKey(
        name="delete", label="Delete", category="navigation",
    ),
    # -- Special keys ---
    SupportedKey(
        name="enter", label="Enter / Return", category="special",
        caveat=(
            "Enter and Ctrl+M produce the same byte (0x0d) on most "
            "terminals.  The parser cannot distinguish them — both "
            "produce KeyEvent(key='enter').  Avoid binding distinct "
            "actions to Enter and Ctrl+M."
        ),
    ),
    SupportedKey(
        name="escape", label="Escape", category="special",
        caveat=(
            "Escape (0x1b) is also the prefix byte for ANSI escape "
            "sequences.  A lone ESC not followed by '[' is treated as "
            "an Escape key press.  Under heavy load, a split escape "
            "sequence could be misidentified as a standalone Escape, "
            "but this is extremely rare in practice."
        ),
    ),
    SupportedKey(
        name="tab", label="Tab", category="special",
        caveat=(
            "Tab and Ctrl+I produce the same byte (0x09).  The parser "
            "reports KeyEvent(key='tab') for both."
        ),
    ),
    SupportedKey(
        name="backspace", label="Backspace", category="special",
        caveat=(
            "Backspace may produce 0x7f (Delete) or 0x08 (BS) "
            "depending on the terminal.  Both are normalised to "
            "KeyEvent(key='backspace')."
        ),
    ),
    SupportedKey(
        name="space", label="Space Bar", category="special",
    ),
    # -- Printable characters ---
    SupportedKey(
        name="a-z", label="Letter Keys (a-z)", category="printable",
        caveat=(
            "Letter keys are reported as their literal character.  "
            "Lowercase 'a' and uppercase 'A' are different key names.  "
            "Shift is not detectable as a modifier — uppercase letters "
            "arrive as their uppercase character directly."
        ),
    ),
    SupportedKey(
        name="0-9", label="Number Keys (0-9)", category="printable",
    ),
    SupportedKey(
        name="punctuation", label="Punctuation (/, -, =, etc.)", category="printable",
        caveat=(
            "Punctuation key names are the literal character produced "
            "(e.g., '/', '-', '=').  Shifted punctuation produces the "
            "shifted character (e.g., Shift+1 produces '!')."
        ),
    ),
)

# Category display order for documentation.
_CATEGORY_ORDER: tuple[str, ...] = (
    "arrow", "navigation", "special", "printable",
)

# Human-readable category labels.
_CATEGORY_LABELS: dict[str, str] = {
    "arrow": "Arrow Keys",
    "navigation": "Navigation Keys",
    "special": "Special Keys",
    "printable": "Printable Characters",
}


def keys_by_category() -> dict[str, list[SupportedKey]]:
    """Group :data:`SUPPORTED_KEYS` by category.

    Returns:
        A dict mapping category names to lists of :class:`SupportedKey`.
        Categories are in the canonical display order.

    Caveats:
        - Unknown categories (not in ``_CATEGORY_ORDER``) are appended
          at the end.
    """
    result: dict[str, list[SupportedKey]] = {}
    for cat in _CATEGORY_ORDER:
        result[cat] = []
    for key in SUPPORTED_KEYS:
        result.setdefault(key.category, []).append(key)
    return result


# ---------------------------------------------------------------------------
# Control caveats
# ---------------------------------------------------------------------------


class ControlCaveat:
    """A framework-level caveat about input controls.

    Attributes:
        topic: Short label for the caveat (e.g., ``"Ctrl+M vs Enter"``).
        description: Full explanation of the caveat.
        category: Grouping (``"modifier"``, ``"terminal"``,
            ``"platform"``, ``"mouse"``).

    Caveats:
        - These are documentation-only objects.  They have no runtime
          effect on input handling.
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
            f"ControlCaveat(topic={self.topic!r}, "
            f"category={self.category!r})"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ControlCaveat):
            return NotImplemented
        return (
            self.topic == other.topic
            and self.description == other.description
            and self.category == other.category
        )


# Framework-level caveats about keyboard and mouse input.
#
# Caveat: this list is maintained manually and reflects the state of the
# input system in wyby v0.1.  If input.py or keymap.py change their
# behaviour, these caveats may need updating.
CONTROL_CAVEATS: tuple[ControlCaveat, ...] = (
    # -- Modifier caveats ---
    ControlCaveat(
        topic="Ctrl modifier",
        description=(
            "Ctrl+A through Ctrl+Z are reliably detected (byte values "
            "0x01-0x1a).  Ctrl+digit and Ctrl+punctuation are not "
            "reliably detectable across terminals.  Ctrl+C (0x03) always "
            "raises KeyboardInterrupt and never produces a KeyEvent."
        ),
        category="modifier",
    ),
    ControlCaveat(
        topic="Shift modifier",
        description=(
            "Shift is not detectable as a modifier.  Uppercase letters "
            "are reported as their uppercase character (e.g., "
            "KeyEvent(key='A')), not as KeyEvent(key='a', shift=True).  "
            "Bind uppercase characters directly if needed."
        ),
        category="modifier",
    ),
    ControlCaveat(
        topic="Alt/Meta modifier",
        description=(
            "Alt/Meta is not supported in wyby v0.1.  Alt+key sequences "
            "(ESC followed by a character) are parsed as two separate "
            "events: an Escape event followed by the character event.  "
            "Do not rely on Alt+key combos for game controls."
        ),
        category="modifier",
    ),
    ControlCaveat(
        topic="Ctrl+M vs Enter",
        description=(
            "Ctrl+M and Enter both produce byte 0x0d (carriage return) "
            "on most terminals.  The input parser cannot distinguish "
            "them — both result in KeyEvent(key='enter').  Avoid "
            "binding distinct actions to Ctrl+M and Enter."
        ),
        category="modifier",
    ),
    ControlCaveat(
        topic="Ctrl+I vs Tab",
        description=(
            "Ctrl+I and Tab both produce byte 0x09.  The parser reports "
            "KeyEvent(key='tab') for both.  Do not bind distinct actions "
            "to Ctrl+I and Tab."
        ),
        category="modifier",
    ),
    # -- Terminal caveats ---
    ControlCaveat(
        topic="XON/XOFF flow control",
        description=(
            "Ctrl+S (0x13) and Ctrl+Q (0x11) are used for XON/XOFF "
            "flow control on some terminals and may be intercepted "
            "before reaching the application.  Binding actions to "
            "these combos is allowed but may not work on all systems.  "
            "On Linux, run 'stty -ixon' to disable flow control."
        ),
        category="terminal",
    ),
    ControlCaveat(
        topic="Terminal raw mode cleanup",
        description=(
            "InputManager modifies terminal state (raw mode).  If the "
            "process exits without calling stop() — for example, via "
            "SIGKILL — the terminal is left in raw mode (no echo, no "
            "line editing).  Run 'reset' or 'stty sane' to recover."
        ),
        category="terminal",
    ),
    ControlCaveat(
        topic="Escape sequence ambiguity",
        description=(
            "A lone ESC byte (0x1b) could be a standalone Escape key "
            "press or the start of an ANSI escape sequence.  The parser "
            "treats a lone ESC not followed by '[' as an Escape key "
            "press.  Under extremely heavy load, a split sequence could "
            "be misidentified, but this is rare in practice."
        ),
        category="terminal",
    ),
    ControlCaveat(
        topic="Key name typos",
        description=(
            "Key names are lowercase strings, not an enum.  Typos in "
            "key comparisons (e.g., event.key == 'Up' instead of 'up') "
            "silently fail to match.  Use the SUPPORTED_KEYS catalog "
            "as a reference for valid key name strings."
        ),
        category="terminal",
    ),
    # -- Platform caveats ---
    ControlCaveat(
        topic="Key repeat rate",
        description=(
            "Key repeat rate is controlled by the operating system, not "
            "wyby.  Holding a key generates repeated KeyEvents at the "
            "OS repeat rate.  On Linux this is set via 'xset r rate' or "
            "the desktop environment; on macOS via System Settings > "
            "Keyboard; on Windows via Settings > Accessibility > Keyboard."
        ),
        category="platform",
    ),
    ControlCaveat(
        topic="Windows input backend",
        description=(
            "On Windows, wyby uses msvcrt for input instead of termios.  "
            "Special keys (arrows, function keys) produce two-byte "
            "scan-code sequences rather than ANSI escapes.  The input "
            "parser normalises these to the same key names, but timing "
            "and buffering behaviour may differ."
        ),
        category="platform",
    ),
    # -- Mouse caveats ---
    ControlCaveat(
        topic="Mouse support varies",
        description=(
            "Mouse event reporting uses SGR extended mode (xterm mode "
            "1006).  Support varies by terminal: xterm, iTerm2, Windows "
            "Terminal, GNOME Terminal, Alacritty, and kitty support it.  "
            "macOS Terminal.app has limited mouse support.  tmux/screen "
            "require 'set -g mouse on'."
        ),
        category="mouse",
    ),
    ControlCaveat(
        topic="Middle-click paste",
        description=(
            "While mouse mode is enabled, middle-click paste may not "
            "work because the terminal captures the click.  Some "
            "terminals allow Shift+middle-click as a workaround."
        ),
        category="mouse",
    ),
    ControlCaveat(
        topic="Mouse motion event volume",
        description=(
            "Motion tracking (InputMode.FULL) reports cursor movement "
            "even without a button held, generating a high volume of "
            "events that can flood the event queue and degrade "
            "performance.  Use InputMode.MOUSE (click/scroll only) "
            "unless hover or drag tracking is essential."
        ),
        category="mouse",
    ),
)

# Caveat category display order.
_CAVEAT_CATEGORY_ORDER: tuple[str, ...] = (
    "modifier", "terminal", "platform", "mouse",
)

# Human-readable caveat category labels.
_CAVEAT_CATEGORY_LABELS: dict[str, str] = {
    "modifier": "Modifier Keys",
    "terminal": "Terminal Behaviour",
    "platform": "Platform Differences",
    "mouse": "Mouse Input",
}


def caveats_by_category() -> dict[str, list[ControlCaveat]]:
    """Group :data:`CONTROL_CAVEATS` by category.

    Returns:
        A dict mapping category names to lists of :class:`ControlCaveat`.
        Categories are in the canonical display order.

    Caveats:
        - Unknown categories are appended at the end.
    """
    result: dict[str, list[ControlCaveat]] = {}
    for cat in _CAVEAT_CATEGORY_ORDER:
        result[cat] = []
    for caveat in CONTROL_CAVEATS:
        result.setdefault(caveat.category, []).append(caveat)
    return result


# ---------------------------------------------------------------------------
# Per-example controls documentation
# ---------------------------------------------------------------------------


class ControlsDoc:
    """Controls documentation for a single example or game.

    Combines the extracted controls (key-action pairs) from
    :class:`~wyby.example_readme.ExampleReadme` with framework-level
    caveats relevant to that example's control scheme.

    Attributes:
        example_name: Human-readable example name.
        filename: Base filename of the example.
        controls: List of ``(key, action)`` tuples.
        caveats: List of :class:`ControlCaveat` relevant to this example.
        example_caveats: List of example-specific caveat strings from
            the module docstring.

    Caveats:
        - ``controls`` may be empty if the example does not render
          hint strings or uses an unrecognised control pattern.
        - ``caveats`` includes only the framework-level caveats that
          are relevant to the detected controls (e.g., modifier
          caveats are included only if Ctrl+key bindings are present).
          Use :data:`CONTROL_CAVEATS` for the full catalog.
    """

    __slots__ = (
        "example_name",
        "filename",
        "controls",
        "caveats",
        "example_caveats",
    )

    def __init__(
        self,
        *,
        example_name: str,
        filename: str,
        controls: list[tuple[str, str]] | None = None,
        caveats: list[ControlCaveat] | None = None,
        example_caveats: list[str] | None = None,
    ) -> None:
        self.example_name = example_name
        self.filename = filename
        self.controls = controls or []
        self.caveats = caveats or []
        self.example_caveats = example_caveats or []

    def __repr__(self) -> str:
        return (
            f"ControlsDoc(example_name={self.example_name!r}, "
            f"controls={len(self.controls)}, "
            f"caveats={len(self.caveats)})"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ControlsDoc):
            return NotImplemented
        return (
            self.example_name == other.example_name
            and self.filename == other.filename
            and self.controls == other.controls
            and self.caveats == other.caveats
            and self.example_caveats == other.example_caveats
        )


def _select_relevant_caveats(
    controls: list[tuple[str, str]],
) -> list[ControlCaveat]:
    """Select framework caveats relevant to a set of controls.

    Always includes terminal and platform caveats (they apply to all
    games).  Modifier and mouse caveats are included only when the
    controls suggest they are relevant.

    Caveats:
        - Relevance detection is heuristic.  Ctrl-key caveats are
          included if any control key contains "ctrl" (case-insensitive).
          Mouse caveats are included if any action mentions "click",
          "mouse", or "drag".
    """
    result: list[ControlCaveat] = []

    # Always include terminal and platform caveats.
    for caveat in CONTROL_CAVEATS:
        if caveat.category in ("terminal", "platform"):
            result.append(caveat)

    # Check if Ctrl bindings are present.
    key_strings = [k.lower() for k, _ in controls]
    action_strings = [a.lower() for _, a in controls]

    has_ctrl = any("ctrl" in k for k in key_strings)
    has_mouse = any(
        term in a for a in action_strings
        for term in ("click", "mouse", "drag")
    )

    # Modifier caveats are always relevant — they document what's NOT
    # detectable, which is important even when only basic keys are used.
    for caveat in CONTROL_CAVEATS:
        if caveat.category == "modifier" and caveat not in result:
            result.append(caveat)

    # Mouse caveats only if mouse-related controls detected.
    if has_mouse or has_ctrl:
        for caveat in CONTROL_CAVEATS:
            if caveat.category == "mouse" and caveat not in result:
                result.append(caveat)

    return result


def _default_examples_dir() -> Path:
    """Resolve the default examples directory relative to this module.

    Caveats:
        - Relies on the source tree layout (``src/wyby/`` ->
          ``../../examples/``).  Not available in wheel installs.
    """
    return Path(__file__).resolve().parent.parent.parent / "examples"


def controls_for_example(path: str | Path) -> ControlsDoc:
    """Generate controls documentation for a single example file.

    Reads the example, extracts controls and caveats via
    :func:`~wyby.example_readme.generate_example_readme`, then selects
    relevant framework-level caveats.

    Args:
        path: Path to the example ``.py`` file.

    Returns:
        A :class:`ControlsDoc` with controls and caveats.

    Raises:
        FileNotFoundError: If *path* does not exist.

    Caveats:
        - Control extraction is heuristic.  See
          :func:`wyby.example_readme._extract_controls` for details.
        - Framework caveats are selected based on the detected controls.
          If controls are not detected (empty list), a baseline set of
          caveats is still included.
    """
    readme: ExampleReadme = generate_example_readme(path)

    relevant_caveats = _select_relevant_caveats(readme.controls)

    return ControlsDoc(
        example_name=readme.title,
        filename=readme.filename,
        controls=readme.controls,
        caveats=relevant_caveats,
        example_caveats=readme.caveats,
    )


def controls_for_all_examples(
    directory: str | Path | None = None,
) -> list[ControlsDoc]:
    """Generate controls documentation for all examples in a directory.

    Args:
        directory: Path to scan.  Defaults to the bundled ``examples/``
            directory.

    Returns:
        A list of :class:`ControlsDoc` instances, sorted by filename.
        Returns an empty list if the directory does not exist.

    Caveats:
        - Only top-level ``*.py`` files are included.
        - Each example is processed independently; a failure in one
          does not affect others.
    """
    if directory is None:
        directory = _default_examples_dir()

    dir_path = Path(directory)
    if not dir_path.is_dir():
        _logger.debug(
            "Examples directory does not exist: %s", dir_path,
        )
        return []

    results: list[ControlsDoc] = []
    for entry in sorted(dir_path.iterdir()):
        if not entry.is_file() or entry.suffix != ".py":
            continue
        try:
            doc = controls_for_example(entry)
            results.append(doc)
        except Exception as exc:
            _logger.warning(
                "Failed to generate controls doc for %s: %s", entry, exc,
            )

    _logger.debug(
        "Generated controls docs for %d example(s) from %s",
        len(results),
        dir_path,
    )
    return results


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------


def format_controls_doc(doc: ControlsDoc) -> str:
    """Format a :class:`ControlsDoc` as Markdown text.

    Produces a section with the example name, a controls table, and
    relevant caveats.

    Args:
        doc: The controls documentation to format.

    Returns:
        A multi-line Markdown string.

    Caveats:
        - The output is plain Markdown, not a Rich renderable.
        - If ``doc.controls`` is empty, a note is included instead
          of a controls table.
    """
    lines: list[str] = []

    lines.append(f"## {doc.example_name}")
    lines.append("")

    # Controls table.
    if doc.controls:
        lines.append("### Controls")
        lines.append("")
        lines.append("| Key | Action |")
        lines.append("|-----|--------|")
        for key, action in doc.controls:
            lines.append(f"| `{key}` | {action} |")
        lines.append("")
    else:
        lines.append("*No controls detected for this example.*")
        lines.append("")

    # Example-specific caveats.
    if doc.example_caveats:
        lines.append("### Example Caveats")
        lines.append("")
        for caveat in doc.example_caveats:
            lines.append(f"- {caveat}")
        lines.append("")

    # Framework caveats.
    if doc.caveats:
        lines.append("### Input Caveats")
        lines.append("")
        for caveat in doc.caveats:
            lines.append(f"- **{caveat.topic}**: {caveat.description}")
        lines.append("")

    return "\n".join(lines)


def format_controls_reference() -> str:
    """Format the full supported-keys reference as Markdown.

    Produces a document with:

    1. A table of all supported key names grouped by category.
    2. A section listing all control caveats grouped by category.

    Returns:
        A multi-line Markdown string.

    Caveats:
        - The output is a standalone reference document, not
          example-specific.  For per-example documentation, use
          :func:`format_controls_doc`.
    """
    lines: list[str] = []

    lines.append("# Controls Reference")
    lines.append("")
    lines.append(
        "This document lists all key names recognised by the wyby input "
        "parser and documents known caveats for keyboard and mouse input."
    )
    lines.append("")

    # Supported keys by category.
    lines.append("## Supported Keys")
    lines.append("")

    grouped = keys_by_category()
    for category in _CATEGORY_ORDER:
        keys = grouped.get(category, [])
        if not keys:
            continue
        label = _CATEGORY_LABELS.get(category, category.title())
        lines.append(f"### {label}")
        lines.append("")
        lines.append("| Key Name | Label | Caveat |")
        lines.append("|----------|-------|--------|")
        for key in keys:
            caveat_text = key.caveat or "—"
            lines.append(f"| `{key.name}` | {key.label} | {caveat_text} |")
        lines.append("")

    # Control caveats by category.
    lines.append("## Input Caveats")
    lines.append("")

    caveat_groups = caveats_by_category()
    for category in _CAVEAT_CATEGORY_ORDER:
        caveats = caveat_groups.get(category, [])
        if not caveats:
            continue
        label = _CAVEAT_CATEGORY_LABELS.get(category, category.title())
        lines.append(f"### {label}")
        lines.append("")
        for caveat in caveats:
            lines.append(f"- **{caveat.topic}**: {caveat.description}")
        lines.append("")

    return "\n".join(lines)


def format_all_controls_docs(docs: list[ControlsDoc]) -> str:
    """Format all example controls docs as a single Markdown document.

    Args:
        docs: List of :class:`ControlsDoc` instances.

    Returns:
        A multi-line Markdown string with a controls reference header
        followed by per-example sections separated by horizontal rules.
        Returns ``"No examples found."`` if *docs* is empty.

    Caveats:
        - The full controls reference is prepended to the document.
          For per-example docs only, use :func:`format_controls_doc`
          on individual items.
    """
    if not docs:
        return "No examples found."

    sections: list[str] = []
    sections.append("# Example Controls Documentation")
    sections.append("")
    sections.append(
        "Controls and input caveats for each bundled wyby example."
    )
    sections.append("")

    for doc in docs:
        sections.append("---")
        sections.append("")
        sections.append(format_controls_doc(doc))

    return "\n".join(sections)
