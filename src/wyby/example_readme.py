"""Generate README instructions for each bundled example.

This module extracts documentation from example module docstrings and
produces per-example README text.  Each README includes a description,
run command, controls, and relevant caveats.  This is useful for
documentation generation and for displaying instructions alongside
examples.

The primary entry points are:

- :func:`generate_example_readme` — generate a README for a single
  example file.
- :func:`generate_all_readmes` — discover all examples and generate
  READMEs for each.
- :func:`format_readme` — format a :class:`ExampleReadme` as plain
  Markdown text.

Caveats:
    - Docstring parsing is **heuristic, not AST-based**.  The module
      splits the docstring on known section headers (``Caveats:``,
      ``Run this example::``) to extract structured information.  If
      an example uses a different docstring format, parsing may produce
      incomplete results.
    - Controls are extracted from HUD hint strings rendered in the
      example's ``render()`` method.  This is a best-effort heuristic
      that looks for patterns like ``"Arrows:move Q:quit"`` in the
      source code.  If an example uses a different pattern, controls
      may not be detected.
    - The generated README is plain Markdown text.  It is not a Rich
      renderable.  For integration with Rich-based UIs, consume the
      :class:`ExampleReadme` objects directly.
    - The default examples directory is resolved relative to this
      module's file path (``../../examples/`` from ``src/wyby/``).
      If wyby is installed as a wheel or zip, the examples directory
      may not exist.  :func:`generate_all_readmes` returns an empty
      list in that case rather than raising.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

_logger = logging.getLogger(__name__)


class ExampleReadme:
    """README content for a single example file.

    Attributes:
        path: Absolute path to the example file.
        title: Human-readable title derived from the filename.
        description: One-line description extracted from the module
            docstring's first line.
        detail: Extended description from the docstring body (between
            the first line and the ``Run this example::`` or ``Caveats:``
            section).
        run_command: Shell command to run the example (e.g.,
            ``python examples/hello_world.py``).
        controls: List of ``(key, action)`` tuples extracted from the
            example source.
        caveats: List of caveat strings from the module docstring.

    Caveats:
        - ``title`` is derived from the filename by replacing
          underscores with spaces and title-casing.  This is a
          heuristic that produces reasonable results for the bundled
          examples but may not be ideal for all filenames.
        - ``controls`` may be empty if the example does not render
          a controls hint string or uses an unrecognised format.
        - ``caveats`` are extracted from the ``Caveats:`` section
          of the module docstring.  If the section is missing or
          uses a different header, the list will be empty.
    """

    __slots__ = (
        "path",
        "title",
        "description",
        "detail",
        "run_command",
        "controls",
        "caveats",
    )

    def __init__(
        self,
        *,
        path: str,
        title: str = "",
        description: str = "",
        detail: str = "",
        run_command: str = "",
        controls: list[tuple[str, str]] | None = None,
        caveats: list[str] | None = None,
    ) -> None:
        self.path = path
        self.title = title
        self.description = description
        self.detail = detail
        self.run_command = run_command
        self.controls = controls or []
        self.caveats = caveats or []

    @property
    def filename(self) -> str:
        """Base filename without directory components."""
        return Path(self.path).name

    def __repr__(self) -> str:
        return (
            f"ExampleReadme(filename={self.filename!r}, "
            f"title={self.title!r}, "
            f"controls={len(self.controls)}, "
            f"caveats={len(self.caveats)})"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ExampleReadme):
            return NotImplemented
        return (
            self.path == other.path
            and self.title == other.title
            and self.description == other.description
            and self.detail == other.detail
            and self.run_command == other.run_command
            and self.controls == other.controls
            and self.caveats == other.caveats
        )


def _default_examples_dir() -> Path:
    """Resolve the default examples directory relative to this module.

    Returns the ``examples/`` directory at the repository root, located
    by traversing up from ``src/wyby/`` to the repo root.

    Caveats:
        - This relies on the source tree layout (``src/wyby/`` ->
          ``../../examples/``).  If wyby is installed from a wheel
          or running from a zip archive, this path will not exist.
    """
    return Path(__file__).resolve().parent.parent.parent / "examples"


def _title_from_filename(filename: str) -> str:
    """Derive a human-readable title from an example filename.

    Strips the ``.py`` extension, replaces underscores with spaces,
    and title-cases the result.

    Caveats:
        - This is a heuristic.  Filenames like ``healthbar_demo.py``
          become ``Healthbar Demo`` rather than ``HealthBar Demo``.
          For the bundled examples this produces acceptable results.
    """
    stem = Path(filename).stem
    return stem.replace("_", " ").title()


def _parse_docstring(docstring: str) -> tuple[str, str, str, list[str]]:
    """Parse a module docstring into structured components.

    Returns:
        A tuple of (description, detail, run_command, caveats).

    Caveats:
        - Parsing is line-based and heuristic.  It looks for
          ``Run this example::`` and ``Caveats:`` section headers.
          If the docstring uses different formatting, results may
          be incomplete.
        - The description is the text after ``Example:`` on the
          first non-empty line, or the first line itself if no
          ``Example:`` prefix is found.
    """
    if not docstring:
        return ("", "", "", [])

    lines = docstring.strip().splitlines()
    if not lines:
        return ("", "", "", [])

    # Extract description from first line.
    first_line = lines[0].strip()
    # Remove "Example: " prefix if present.
    if first_line.lower().startswith("example:"):
        description = first_line[len("example:"):].strip()
    else:
        description = first_line

    # Find section boundaries.
    run_idx = None
    caveats_idx = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("Run this example"):
            run_idx = i
        if stripped == "Caveats:":
            caveats_idx = i

    # Extract detail — text between first line and Run/Caveats section.
    detail_end = run_idx or caveats_idx or len(lines)
    detail_lines = []
    for line in lines[1:detail_end]:
        detail_lines.append(line.strip())
    # Strip leading/trailing blank lines from detail.
    while detail_lines and not detail_lines[0]:
        detail_lines.pop(0)
    while detail_lines and not detail_lines[-1]:
        detail_lines.pop()
    detail = " ".join(line for line in detail_lines if line)

    # Extract run command.
    run_command = ""
    if run_idx is not None:
        # The command is on the lines following "Run this example::"
        for line in lines[run_idx + 1:]:
            stripped = line.strip()
            if stripped and not stripped.startswith("Run"):
                run_command = stripped
                break

    # Extract caveats.
    caveats: list[str] = []
    if caveats_idx is not None:
        current_caveat = ""
        for line in lines[caveats_idx + 1:]:
            stripped = line.strip()
            if not stripped:
                # Empty line — end of caveats section if we have some.
                if current_caveat:
                    caveats.append(current_caveat)
                    current_caveat = ""
                continue
            if stripped.startswith("- "):
                # New caveat bullet.
                if current_caveat:
                    caveats.append(current_caveat)
                current_caveat = stripped[2:]
            else:
                # Continuation of the current caveat.
                if current_caveat:
                    current_caveat += " " + stripped
                else:
                    current_caveat = stripped
        if current_caveat:
            caveats.append(current_caveat)

    return (description, detail, run_command, caveats)


def _extract_controls(source: str) -> list[tuple[str, str]]:
    """Extract control hints from example source code.

    Looks for hint strings in the source that follow common patterns
    like ``"Arrows:move Q:quit"`` or ``"W/S:P1 Up/Down:P2"``.

    Returns:
        A list of ``(key, action)`` tuples.

    Caveats:
        - This is a heuristic that searches for patterns in string
          literals assigned to ``hint`` variables or passed to
          ``put_text``.  It may miss controls defined in other ways.
        - Controls from ``handle_events`` methods (like ``r`` for
          restart) are detected by searching for key string
          comparisons in the source.
    """
    controls: list[tuple[str, str]] = []
    seen: set[str] = set()

    # Pattern 1: "Key:action" pairs in hint-like string assignments.
    # Look for lines that assign hint strings (e.g., hint = "...").
    # Also matches put_text calls with inline hint strings.
    hint_line_pattern = re.compile(
        r"""(?:hint\s*=|put_text\s*\([^)]*)\s*["']([^"']*(?:[\w/\u2191\u2193]+:[\w]+)[^"']*)["']""",
    )
    pair_pattern = re.compile(r"([\w/\u2191\u2193]+):([\w]+)")

    # Skip keys that look like Unicode escape fragments (e.g., "u2191"
    # from \u2191 in source code).
    _unicode_frag = re.compile(r"^u[0-9a-fA-F]{4}$")

    for match in hint_line_pattern.finditer(source):
        content = match.group(1)
        pairs = pair_pattern.findall(content)
        for key, action in pairs:
            if _unicode_frag.match(key):
                continue
            key_lower = key.lower()
            if key_lower not in seen:
                seen.add(key_lower)
                controls.append((key, action))

    # Pattern 2: Key comparisons in handle_events.
    # Look for event.key == "keyname" or event.key in ("key1", "key2")
    key_eq_pattern = re.compile(
        r'event\.key\s*(?:==\s*"(\w+)"|in\s*\(([^)]+)\))'
    )
    key_actions: dict[str, str] = {
        "q": "quit",
        "escape": "quit",
        "r": "restart",
        "up": "move up",
        "down": "move down",
        "left": "move left",
        "right": "move right",
        "w": "move up (P1)",
        "s": "move down (P1)",
        "space": "flap/action",
        "enter": "confirm",
        "d": "damage",
        "h": "heal",
    }

    for match in key_eq_pattern.finditer(source):
        if match.group(1):
            key = match.group(1)
            if key.lower() not in seen:
                action = key_actions.get(key.lower(), key)
                seen.add(key.lower())
                controls.append((key, action))
        elif match.group(2):
            # Parse tuple of keys: ("key1", "key2")
            keys = re.findall(r'"(\w+)"', match.group(2))
            for key in keys:
                if key.lower() not in seen:
                    action = key_actions.get(key.lower(), key)
                    seen.add(key.lower())
                    controls.append((key, action))

    return controls


def generate_example_readme(path: str | Path) -> ExampleReadme:
    """Generate a README for a single example file.

    Reads the example file, extracts its module docstring, parses
    structured information (description, run command, caveats), and
    extracts controls from the source code.

    Args:
        path: Path to the example ``.py`` file.

    Returns:
        An :class:`ExampleReadme` with the extracted information.

    Raises:
        FileNotFoundError: If *path* does not exist.

    Caveats:
        - The file is read entirely into memory.  For the intended
          use case (example scripts of a few hundred lines) this
          is fine.
        - Docstring parsing and control extraction are heuristic.
          See :func:`_parse_docstring` and :func:`_extract_controls`
          for details.
        - If the file has no module docstring, the README will have
          empty description, detail, and caveats fields.
    """
    resolved = Path(path).resolve()
    source = resolved.read_text(encoding="utf-8")
    filename = resolved.name

    title = _title_from_filename(filename)

    # Extract module docstring — the first triple-quoted string.
    docstring = ""
    # Use ast to extract the docstring reliably.
    import ast

    try:
        tree = ast.parse(source)
        docstring = ast.get_docstring(tree) or ""
    except SyntaxError:
        _logger.warning("Syntax error parsing %s", resolved)

    description, detail, run_command, caveats = _parse_docstring(docstring)

    # Fall back to a default run command if none found in docstring.
    if not run_command:
        run_command = f"python examples/{filename}"

    controls = _extract_controls(source)

    return ExampleReadme(
        path=str(resolved),
        title=title,
        description=description,
        detail=detail,
        run_command=run_command,
        controls=controls,
        caveats=caveats,
    )


def generate_all_readmes(
    directory: str | Path | None = None,
) -> list[ExampleReadme]:
    """Discover all ``*.py`` files in a directory and generate READMEs.

    Args:
        directory: Path to the directory to scan.  Defaults to the
            bundled ``examples/`` directory resolved relative to this
            module's source file.

    Returns:
        A list of :class:`ExampleReadme` instances, sorted by filename.
        Returns an empty list if the directory does not exist or
        contains no ``*.py`` files.

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
            "Examples directory does not exist: %s", dir_path,
        )
        return []

    results: list[ExampleReadme] = []
    for entry in sorted(dir_path.iterdir()):
        if not entry.is_file() or entry.suffix != ".py":
            continue
        try:
            readme = generate_example_readme(entry)
            results.append(readme)
        except Exception as exc:
            _logger.warning("Failed to generate README for %s: %s", entry, exc)

    _logger.debug(
        "Generated READMEs for %d example file(s) from %s",
        len(results),
        dir_path,
    )
    return results


def format_readme(readme: ExampleReadme) -> str:
    """Format an :class:`ExampleReadme` as Markdown text.

    Args:
        readme: The README data to format.

    Returns:
        A multi-line Markdown string suitable for writing to a
        ``README.md`` file or displaying in documentation.

    Caveats:
        - The output is plain Markdown.  It is not a Rich renderable.
        - The format is opinionated — it uses ``#`` for the title,
          a code block for the run command, a table for controls,
          and a bulleted list for caveats.
    """
    lines: list[str] = []

    # Title.
    lines.append(f"# {readme.title}")
    lines.append("")

    # Description.
    if readme.description:
        lines.append(readme.description)
        lines.append("")

    # Detail.
    if readme.detail:
        lines.append(readme.detail)
        lines.append("")

    # Run command.
    lines.append("## How to Run")
    lines.append("")
    lines.append("```bash")
    lines.append(readme.run_command)
    lines.append("```")
    lines.append("")

    # Controls.
    if readme.controls:
        lines.append("## Controls")
        lines.append("")
        lines.append("| Key | Action |")
        lines.append("|-----|--------|")
        for key, action in readme.controls:
            lines.append(f"| `{key}` | {action} |")
        lines.append("")

    # Caveats.
    if readme.caveats:
        lines.append("## Caveats")
        lines.append("")
        for caveat in readme.caveats:
            lines.append(f"- {caveat}")
        lines.append("")

    return "\n".join(lines)


def format_all_readmes(readmes: list[ExampleReadme]) -> str:
    """Format all example READMEs as a single document.

    Args:
        readmes: List of :class:`ExampleReadme` instances.

    Returns:
        A multi-line Markdown string with all READMEs concatenated,
        separated by horizontal rules.  Returns
        ``"No examples found."`` if *readmes* is empty.

    Caveats:
        - Each example's README is separated by a Markdown horizontal
          rule (``---``).  This is suitable for a single combined
          document but may not be ideal for individual files.
    """
    if not readmes:
        return "No examples found."

    sections: list[str] = []
    for readme in readmes:
        sections.append(format_readme(readme))

    return "\n---\n\n".join(sections)
