"""Generate text-based screenshot placeholders for example documentation.

This module produces ASCII-art placeholder blocks that represent what each
bundled example looks like when running in a terminal.  These placeholders
are intended for use in README files, documentation, and other contexts
where actual terminal screenshots are not available or practical.

Each placeholder is a bordered text box showing the example title, a brief
visual description, the buffer dimensions, and key visual elements extracted
from the source code.

The primary entry points are:

- :func:`generate_placeholder` — generate a placeholder for a single
  example file.
- :func:`generate_all_placeholders` — discover all examples and generate
  placeholders for each.
- :func:`format_placeholder` — format a :class:`ScreenshotPlaceholder` as
  a fenced code block suitable for Markdown.
- :func:`format_all_placeholders` — format all placeholders as a single
  Markdown document.

Caveats:
    - Visual element detection is **heuristic, not AST-based**.  The module
      searches for patterns like ``CellBuffer(width, height)``,
      ``put_text(...)`` calls, and string literals in the source code.
      Examples that construct their visuals dynamically or use indirect
      patterns may produce incomplete element lists.
    - Buffer dimensions are extracted from ``CellBuffer(w, h)`` or
      ``Engine(..., width=w, height=h)`` constructor calls.  If an example
      uses variables or computed values for dimensions, the defaults
      (80x24) are used instead.
    - The placeholder is a **static text approximation**, not an actual
      rendering of the example.  It shows *what kind of content* the
      example displays, not the exact pixel-level output.
    - The default examples directory is resolved relative to this module's
      file path (``../../examples/`` from ``src/wyby/``).  If wyby is
      installed as a wheel or zip, the examples directory may not exist.
      :func:`generate_all_placeholders` returns an empty list in that case.
"""

from __future__ import annotations

import ast
import logging
import re
from pathlib import Path

_logger = logging.getLogger(__name__)


class ScreenshotPlaceholder:
    """A text-based screenshot placeholder for a single example.

    Attributes:
        path: Absolute path to the example file.
        title: Human-readable title derived from the filename.
        description: One-line description extracted from the module
            docstring.
        width: Detected buffer width in columns.
        height: Detected buffer height in rows.
        elements: List of visual element descriptions detected in the
            source (e.g., ``"Centred greeting text"``,
            ``"Score display"``).

    Caveats:
        - ``title`` is derived from the filename by replacing underscores
          with spaces and title-casing.  This is a heuristic that produces
          reasonable results for the bundled examples but may not be ideal
          for all filenames.
        - ``width`` and ``height`` default to 80x24 when dimensions cannot
          be extracted from the source.  These defaults represent a common
          terminal size but may not match the example's actual buffer.
        - ``elements`` may be empty if the example uses visual patterns
          that the heuristic does not recognise.
    """

    __slots__ = (
        "path",
        "title",
        "description",
        "width",
        "height",
        "elements",
    )

    # Default buffer dimensions when detection fails.
    DEFAULT_WIDTH = 80
    DEFAULT_HEIGHT = 24

    def __init__(
        self,
        *,
        path: str,
        title: str = "",
        description: str = "",
        width: int = DEFAULT_WIDTH,
        height: int = DEFAULT_HEIGHT,
        elements: list[str] | None = None,
    ) -> None:
        self.path = path
        self.title = title
        self.description = description
        self.width = width
        self.height = height
        self.elements = elements or []

    @property
    def filename(self) -> str:
        """Base filename without directory components."""
        return Path(self.path).name

    def __repr__(self) -> str:
        return (
            f"ScreenshotPlaceholder(filename={self.filename!r}, "
            f"title={self.title!r}, "
            f"{self.width}x{self.height}, "
            f"elements={len(self.elements)})"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ScreenshotPlaceholder):
            return NotImplemented
        return (
            self.path == other.path
            and self.title == other.title
            and self.description == other.description
            and self.width == other.width
            and self.height == other.height
            and self.elements == other.elements
        )


def _default_examples_dir() -> Path:
    """Resolve the default examples directory relative to this module.

    Caveats:
        - Relies on the source tree layout (``src/wyby/`` ->
          ``../../examples/``).  Not available in wheel installs.
    """
    return Path(__file__).resolve().parent.parent.parent / "examples"


def _title_from_filename(filename: str) -> str:
    """Derive a human-readable title from an example filename.

    Strips the ``.py`` extension, replaces underscores with spaces,
    and title-cases the result.

    Caveats:
        - This is a heuristic.  Filenames like ``healthbar_demo.py``
          become ``Healthbar Demo`` rather than ``HealthBar Demo``.
    """
    stem = Path(filename).stem
    return stem.replace("_", " ").title()


def _extract_description(source: str) -> str:
    """Extract the first-line description from a module docstring.

    Caveats:
        - Uses :func:`ast.parse` to extract the docstring.  If the file
          has a syntax error, returns an empty string.
        - Only the first non-empty line of the docstring is used.
          ``Example:`` prefixes are stripped if present.
    """
    try:
        tree = ast.parse(source)
        docstring = ast.get_docstring(tree) or ""
    except SyntaxError:
        return ""

    if not docstring:
        return ""

    first_line = docstring.strip().splitlines()[0].strip()
    if first_line.lower().startswith("example:"):
        first_line = first_line[len("example:"):].strip()
    return first_line


def _extract_dimensions(source: str) -> tuple[int, int]:
    """Extract buffer dimensions from example source code.

    Looks for ``CellBuffer(width, height)`` and
    ``Engine(..., width=N, height=N)`` patterns.

    Returns:
        A tuple ``(width, height)``.  Returns the class defaults if
        dimensions cannot be detected.

    Caveats:
        - Detection uses regular expressions on the source text, not AST
          analysis.  Dimensions defined via variables, expressions, or
          class attributes may not be detected.
        - If multiple dimension patterns are found, the first match is
          used.  This works well for the bundled examples (which typically
          define dimensions once) but may be surprising for more complex
          files.
        - Only integer literal dimensions are detected.  Computed values
          like ``cols - 2`` are not resolved.
    """
    # Pattern 1: CellBuffer(width, height) — positional args.
    match = re.search(
        r"CellBuffer\s*\(\s*(\d+)\s*,\s*(\d+)",
        source,
    )
    if match:
        return int(match.group(1)), int(match.group(2))

    # Pattern 2: Engine(..., width=N, height=N) — keyword args.
    width_match = re.search(r"width\s*=\s*(\d+)", source)
    height_match = re.search(r"height\s*=\s*(\d+)", source)
    if width_match and height_match:
        return int(width_match.group(1)), int(height_match.group(1))

    return ScreenshotPlaceholder.DEFAULT_WIDTH, ScreenshotPlaceholder.DEFAULT_HEIGHT


def _extract_elements(source: str) -> list[str]:
    """Extract visual element descriptions from example source code.

    Looks for ``put_text`` calls, border/box drawing, score/HUD
    patterns, and other common visual elements.

    Returns:
        A list of human-readable element descriptions.

    Caveats:
        - Detection is heuristic and relies on common naming patterns
          in the bundled examples.  Custom examples with different
          conventions may produce incomplete results.
        - Elements are deduplicated but ordering follows detection order,
          not visual layout order.
        - String content from ``put_text`` calls is extracted as-is.
          Very long strings may produce verbose element descriptions.
    """
    elements: list[str] = []
    seen: set[str] = set()

    def _add(desc: str) -> None:
        if desc not in seen:
            seen.add(desc)
            elements.append(desc)

    # Detect put_text calls with string content.
    # Caveat: only matches simple string literals, not f-strings or
    # concatenated strings.
    for match in re.finditer(
        r'put_text\s*\([^)]*["\']([^"\']+)["\']',
        source,
    ):
        text = match.group(1).strip()
        if len(text) > 40:
            text = text[:37] + "..."
        if text:
            _add(f'Text: "{text}"')

    # Detect border/box drawing.
    if re.search(r'["\'][─│┌┐└┘┬┴├┤┼═║╔╗╚╝╬]', source):
        _add("Box-drawing border")
    # Also check for fill_rect or draw_rect patterns for borders.
    if re.search(r"fill_rect|draw_rect|draw_border", source):
        _add("Rectangular border")

    # Detect score/HUD display.
    if re.search(r"score|Score|SCORE", source):
        _add("Score display")
    if re.search(r"health|Health|HP|hp", source):
        _add("Health indicator")

    # Detect game-over screen.
    if re.search(r"game.?over|GAME.?OVER|Game.?Over", source):
        _add("Game-over screen")

    # Detect menu items.
    if re.search(r"menu|Menu|MENU", source):
        _add("Menu interface")

    # Detect entity/sprite rendering.
    if re.search(r"entity|Entity|sprite|Sprite", source):
        _add("Entity/sprite rendering")

    # Detect food/collectible markers (common in snake-like games).
    if re.search(r'food|Food|["\']\\*["\']', source):
        _add("Collectible markers")

    # Detect paddle (pong-like games).
    if re.search(r"paddle|Paddle", source):
        _add("Paddle elements")

    # Detect ball (pong-like games).
    if re.search(r"ball|Ball", source):
        _add("Ball element")

    return elements


def generate_placeholder(path: str | Path) -> ScreenshotPlaceholder:
    """Generate a screenshot placeholder for a single example file.

    Reads the example file, extracts its dimensions, description, and
    visual elements to produce a text-based placeholder.

    Args:
        path: Path to the example ``.py`` file.

    Returns:
        A :class:`ScreenshotPlaceholder` with the extracted information.

    Raises:
        FileNotFoundError: If *path* does not exist.

    Caveats:
        - The file is read entirely into memory.  For the intended use
          case (example scripts of a few hundred lines) this is fine.
        - Dimension and element extraction are heuristic.  See
          :func:`_extract_dimensions` and :func:`_extract_elements` for
          details.
        - If the file has no module docstring, the placeholder will have
          an empty description.
    """
    resolved = Path(path).resolve()
    source = resolved.read_text(encoding="utf-8")
    filename = resolved.name

    title = _title_from_filename(filename)
    description = _extract_description(source)
    width, height = _extract_dimensions(source)
    elements = _extract_elements(source)

    _logger.debug(
        "Generated placeholder for %s: %dx%d, %d elements",
        filename,
        width,
        height,
        len(elements),
    )

    return ScreenshotPlaceholder(
        path=str(resolved),
        title=title,
        description=description,
        width=width,
        height=height,
        elements=elements,
    )


def generate_all_placeholders(
    directory: str | Path | None = None,
) -> list[ScreenshotPlaceholder]:
    """Discover all ``*.py`` files in a directory and generate placeholders.

    Args:
        directory: Path to the directory to scan.  Defaults to the
            bundled ``examples/`` directory resolved relative to this
            module's source file.

    Returns:
        A list of :class:`ScreenshotPlaceholder` instances, sorted by
        filename.  Returns an empty list if the directory does not exist
        or contains no ``*.py`` files.

    Caveats:
        - Only ``*.py`` files in the top level of the directory are
          included.  Subdirectories are **not** recursed into.
        - Each example is processed independently.  A failure in one
          example does not affect processing of others.
        - The default examples directory is resolved from the source
          tree layout.  If wyby is installed from a wheel, the
          ``examples/`` directory is typically not included and this
          function returns an empty list.
    """
    if directory is None:
        directory = _default_examples_dir()

    dir_path = Path(directory)
    if not dir_path.is_dir():
        _logger.debug(
            "Examples directory does not exist: %s",
            dir_path,
        )
        return []

    results: list[ScreenshotPlaceholder] = []
    for entry in sorted(dir_path.iterdir()):
        if not entry.is_file() or entry.suffix != ".py":
            continue
        try:
            placeholder = generate_placeholder(entry)
            results.append(placeholder)
        except Exception as exc:
            _logger.warning(
                "Failed to generate placeholder for %s: %s",
                entry,
                exc,
            )

    _logger.debug(
        "Generated placeholders for %d example file(s) from %s",
        len(results),
        dir_path,
    )
    return results


def format_placeholder(placeholder: ScreenshotPlaceholder) -> str:
    """Format a :class:`ScreenshotPlaceholder` as a Markdown section.

    Produces a fenced code block containing an ASCII-art box with the
    example title, description, dimensions, and detected visual elements.

    Args:
        placeholder: The placeholder to format.

    Returns:
        A multi-line Markdown string with a heading and a code block.

    Caveats:
        - The box width is based on the example's detected buffer width,
          clamped to a minimum of 40 and maximum of 78 columns to keep
          the output readable in documentation.
        - The placeholder is a static text representation — it does not
          reflect the actual rendering output of the example.
        - Long element descriptions are truncated to fit the box width.
    """
    # Clamp the box width for readability.
    # Caveat: the box width is for documentation display, not a 1:1
    # mapping of the example's buffer dimensions.
    box_width = max(40, min(placeholder.width, 78))
    inner_width = box_width - 4  # Account for "│ " and " │" borders.

    lines: list[str] = []

    # Markdown heading.
    lines.append(f"### {placeholder.title}")
    lines.append("")

    # Description above the box.
    if placeholder.description:
        lines.append(placeholder.description)
        lines.append("")

    # Start fenced code block.
    lines.append("```")

    # Top border.
    lines.append("┌" + "─" * (box_width - 2) + "┐")

    # Empty line.
    lines.append("│" + " " * (box_width - 2) + "│")

    # Title line, centred.
    title_text = f"[Screenshot: {placeholder.title}]"
    if len(title_text) > inner_width:
        title_text = title_text[: inner_width - 3] + "..."
    padding = inner_width - len(title_text)
    left_pad = padding // 2
    right_pad = padding - left_pad
    lines.append(
        "│ " + " " * left_pad + title_text + " " * right_pad + " │"
    )

    # Empty line.
    lines.append("│" + " " * (box_width - 2) + "│")

    # Dimensions line.
    dim_text = f"{placeholder.width}x{placeholder.height} character grid"
    if len(dim_text) > inner_width:
        dim_text = dim_text[: inner_width - 3] + "..."
    dim_padding = inner_width - len(dim_text)
    dim_left = dim_padding // 2
    dim_right = dim_padding - dim_left
    lines.append(
        "│ " + " " * dim_left + dim_text + " " * dim_right + " │"
    )

    # Empty line.
    lines.append("│" + " " * (box_width - 2) + "│")

    # Visual elements.
    if placeholder.elements:
        for element in placeholder.elements:
            elem_text = f"• {element}"
            if len(elem_text) > inner_width:
                elem_text = elem_text[: inner_width - 3] + "..."
            elem_pad = inner_width - len(elem_text)
            lines.append("│ " + elem_text + " " * elem_pad + " │")

        # Empty line after elements.
        lines.append("│" + " " * (box_width - 2) + "│")

    # Bottom border.
    lines.append("└" + "─" * (box_width - 2) + "┘")

    # End fenced code block.
    lines.append("```")

    return "\n".join(lines)


def format_all_placeholders(
    placeholders: list[ScreenshotPlaceholder],
) -> str:
    """Format all screenshot placeholders as a single Markdown document.

    Args:
        placeholders: List of :class:`ScreenshotPlaceholder` instances.

    Returns:
        A multi-line Markdown string with a document header followed by
        each placeholder section.  Returns ``"No examples found."`` if
        *placeholders* is empty.

    Caveats:
        - Each placeholder section includes a heading, description, and
          ASCII-art box.  The document is intended for inclusion in a
          README or documentation file.
        - The output is plain Markdown text, not a Rich renderable.
    """
    if not placeholders:
        return "No examples found."

    sections: list[str] = []
    sections.append("## Screenshot Placeholders")
    sections.append("")
    sections.append(
        "Text-based placeholders showing what each example looks like "
        "when running in a terminal.  Replace these with actual terminal "
        "screenshots when available."
    )
    sections.append("")

    for placeholder in placeholders:
        sections.append(format_placeholder(placeholder))
        sections.append("")

    return "\n".join(sections)
