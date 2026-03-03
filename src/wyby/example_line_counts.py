"""Line-count reporting for example files.

This module provides utilities to count lines in wyby example scripts,
breaking them down into code, blank, and comment lines.  It is intended
for documentation and diagnostic purposes — e.g., showing users how
concise each example is.

The primary entry points are:

- :func:`count_lines` — count lines in a single file.
- :func:`count_example_lines` — discover and count all ``*.py`` files
  in a directory (defaults to the bundled ``examples/`` directory).

Caveats:
    - Line classification is **heuristic**, not AST-based.  A line is
      classified as a "comment line" if its stripped form starts with
      ``#``.  Lines inside multi-line strings (triple-quoted docstrings)
      are counted as code lines, not comments.  This is intentional —
      docstrings are executable Python (they become the ``__doc__``
      attribute) and contribute to the runtime footprint.
    - Blank lines are lines that contain only whitespace.  A line
      containing only a comment (``# ...``) is classified as a comment
      line, not a blank line.
    - Line counts are computed from the raw file bytes decoded as UTF-8.
      Files that are not valid UTF-8 are skipped with a logged warning.
    - The default examples directory is resolved relative to this
      module's file path (``../../examples/`` from ``src/wyby/``).
      If wyby is installed as a wheel or zip, the examples directory
      may not exist on disk.  :func:`count_example_lines` returns an
      empty list in that case rather than raising.
    - Line counts do not measure code complexity, quality, or
      performance.  A 50-line example may be harder to understand than
      a 200-line one.  Use line counts as a rough size indicator only.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

_logger = logging.getLogger(__name__)


class LineCounts:
    """Line-count breakdown for a single file.

    Attributes:
        path: Absolute path to the counted file.
        total: Total number of lines (including blank and comment lines).
        code: Lines that are neither blank nor full-line comments.
        blank: Lines containing only whitespace.
        comment: Lines whose stripped form starts with ``#``.

    The invariant ``total == code + blank + comment`` always holds.

    Caveats:
        - ``comment`` only counts full-line comments (lines where the
          first non-whitespace character is ``#``).  Inline comments
          (``x = 1  # set x``) are counted as code lines because the
          line contains executable code.
        - ``total`` counts lines produced by ``str.splitlines()``.  A
          file that ends without a trailing newline has the same
          ``total`` as one that does — ``splitlines()`` does not add
          a phantom empty line for a trailing newline.
    """

    __slots__ = ("path", "total", "code", "blank", "comment")

    def __init__(
        self,
        *,
        path: str,
        total: int,
        code: int,
        blank: int,
        comment: int,
    ) -> None:
        self.path = path
        self.total = total
        self.code = code
        self.blank = blank
        self.comment = comment

    @property
    def filename(self) -> str:
        """Base filename without directory components."""
        return os.path.basename(self.path)

    def __repr__(self) -> str:
        return (
            f"LineCounts(filename={self.filename!r}, total={self.total}, "
            f"code={self.code}, blank={self.blank}, comment={self.comment})"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, LineCounts):
            return NotImplemented
        return (
            self.path == other.path
            and self.total == other.total
            and self.code == other.code
            and self.blank == other.blank
            and self.comment == other.comment
        )


def _default_examples_dir() -> Path:
    """Resolve the default examples directory relative to this module.

    Returns the ``examples/`` directory at the repository root, located
    by traversing up from ``src/wyby/`` to the repo root.

    Caveats:
        - This relies on the source tree layout (``src/wyby/`` →
          ``../../examples/``).  If wyby is installed from a wheel
          or running from a zip archive, this path will not exist.
    """
    return Path(__file__).resolve().parent.parent.parent / "examples"


def count_lines(path: str | os.PathLike[str]) -> LineCounts:
    """Count lines in a single file, broken down by category.

    Args:
        path: Path to the file to count.

    Returns:
        A :class:`LineCounts` instance with the breakdown.

    Raises:
        FileNotFoundError: If *path* does not exist.
        IsADirectoryError: If *path* is a directory.
        UnicodeDecodeError: If the file is not valid UTF-8.

    Caveats:
        - The file is read entirely into memory.  For the intended use
          case (example scripts of a few hundred lines) this is fine.
          Do not use this on multi-gigabyte files.
        - Line classification is heuristic — see module-level docstring
          for details.
    """
    resolved = Path(path).resolve()
    text = resolved.read_text(encoding="utf-8")
    lines = text.splitlines()

    total = len(lines)
    blank = 0
    comment = 0

    for line in lines:
        stripped = line.strip()
        if not stripped:
            blank += 1
        elif stripped.startswith("#"):
            comment += 1

    code = total - blank - comment
    return LineCounts(
        path=str(resolved),
        total=total,
        code=code,
        blank=blank,
        comment=comment,
    )


def count_example_lines(
    directory: str | os.PathLike[str] | None = None,
) -> list[LineCounts]:
    """Discover and count lines in all ``*.py`` files in a directory.

    Args:
        directory: Path to the directory to scan.  Defaults to the
            bundled ``examples/`` directory resolved relative to this
            module's source file.

    Returns:
        A list of :class:`LineCounts` instances, sorted by filename.
        Returns an empty list if the directory does not exist or
        contains no ``*.py`` files.

    Caveats:
        - Only ``*.py`` files in the top level of the directory are
          included.  Subdirectories are **not** recursed into.  This
          avoids accidentally counting ``__pycache__`` artefacts or
          nested packages.
        - Files that cannot be decoded as UTF-8 are skipped with a
          logged warning rather than raising an exception.  This
          prevents a single malformed file from blocking the entire
          report.
        - The default examples directory is resolved from the source
          tree layout.  If wyby is installed from a wheel, the
          ``examples/`` directory is typically not included in the
          installed package and this function will return an empty list.
        - Line counts reflect the file's current state on disk.  If an
          example is being edited, the counts may not match the last
          committed version.
    """
    if directory is None:
        directory = _default_examples_dir()

    dir_path = Path(directory)
    if not dir_path.is_dir():
        _logger.debug(
            "Examples directory does not exist: %s", dir_path,
        )
        return []

    results: list[LineCounts] = []
    for entry in sorted(dir_path.iterdir()):
        if not entry.is_file() or entry.suffix != ".py":
            continue
        try:
            counts = count_lines(entry)
        except UnicodeDecodeError:
            _logger.warning(
                "Skipping non-UTF-8 file: %s", entry,
            )
            continue
        results.append(counts)

    _logger.debug(
        "Counted lines in %d example file(s) from %s",
        len(results),
        dir_path,
    )
    return results


def format_line_counts(counts: list[LineCounts]) -> str:
    """Format a list of line counts as a human-readable table.

    Args:
        counts: List of :class:`LineCounts` instances to format.

    Returns:
        A multi-line string with a header row and one row per file,
        plus a totals row.  Returns ``"No examples found."`` if
        *counts* is empty.

    Caveats:
        - Column widths are computed from the data.  Very long filenames
          may produce wide output that wraps in narrow terminals.
        - The table is plain text, not a Rich renderable.  For
          integration with Rich-based UIs, consume the :class:`LineCounts`
          objects directly rather than formatting to text.
    """
    if not counts:
        return "No examples found."

    # Determine column widths.
    name_width = max(len(c.filename) for c in counts)
    name_width = max(name_width, len("File"))

    header = (
        f"{'File':<{name_width}}  "
        f"{'Total':>6}  {'Code':>6}  {'Blank':>6}  {'Comment':>7}"
    )
    separator = "-" * len(header)

    lines = [header, separator]
    for c in counts:
        lines.append(
            f"{c.filename:<{name_width}}  "
            f"{c.total:>6}  {c.code:>6}  {c.blank:>6}  {c.comment:>7}"
        )

    # Totals row.
    total_total = sum(c.total for c in counts)
    total_code = sum(c.code for c in counts)
    total_blank = sum(c.blank for c in counts)
    total_comment = sum(c.comment for c in counts)

    lines.append(separator)
    lines.append(
        f"{'TOTAL':<{name_width}}  "
        f"{total_total:>6}  {total_code:>6}  {total_blank:>6}  {total_comment:>7}"
    )

    return "\n".join(lines)
