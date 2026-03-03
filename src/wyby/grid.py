"""Grid and cell types for the virtual frame buffer.

This module provides :class:`Cell` and :class:`CellBuffer` — the data
types that sit between game logic and the renderer.  Game code writes
characters and styles into a :class:`CellBuffer`; the renderer reads the
buffer and converts it to Rich renderables for terminal output.

The buffer is implemented as a **list of lists** (rows × columns) of
:class:`Cell` objects.  This layout was chosen for compositing:

- Straightforward row-major iteration for conversion to Rich ``Table``.
- Multiple sources (background tiles, entities, UI overlays) write into
  the same buffer in z-order, with later writes overwriting earlier ones.
- The buffer is a plain Python data structure with **no Rich dependency**,
  so it can be tested and inspected without a terminal.

Caveats
-------
- **No double-buffering.**  There is a single buffer; the renderer reads
  whatever state it finds when ``present()`` is called.  If the game
  loop mutates the buffer while the renderer is converting it to Rich
  output, torn frames are possible.  In practice the single-threaded
  game loop prevents this, but be aware of it if concurrency is added.
- **Full-buffer clear every frame.**  ``clear()`` rewrites every cell.
  For large buffers (e.g. 200×60 = 12 000 cells) this is measurable but
  still fast enough for 30 FPS on modern hardware.  A dirty-region
  system could be added later as an optimisation.
- **Terminal cells are not square.**  A typical terminal character cell
  is roughly twice as tall as it is wide (~1:2 aspect ratio).  Nothing
  in this module corrects for that — callers must account for it when
  designing visuals.
- **Unicode width is not handled here.**  CJK characters occupy 2 cells,
  and emoji width varies by terminal.  ``put_text`` places one ``Cell``
  per Python character; correct multi-cell handling is deferred to a
  future ``wcwidth`` integration.
- **No bounds errors.**  ``put()`` and ``put_text()`` silently clip
  writes that fall outside the buffer.  ``get()`` returns ``None`` for
  out-of-bounds coordinates.  This keeps rendering code simple (no need
  to pre-clip) but means typos in coordinates fail silently.
"""

from __future__ import annotations

from dataclasses import dataclass

# Default character for empty / cleared cells.
_DEFAULT_CHAR = " "

# Minimum and maximum buffer dimensions.  These guard against accidental
# zero-size buffers and absurdly large allocations.
_MIN_DIMENSION = 1
_MAX_DIMENSION = 1000


@dataclass
class Cell:
    """A single terminal cell: one character plus style attributes.

    Attributes map directly to Rich ``Style`` fields so the renderer can
    convert without translation.

    Parameters
    ----------
    char:
        A single printable character.  Must be exactly one character long.
    fg:
        Foreground colour as a Rich colour string (e.g. ``"red"``,
        ``"#ff0000"``, ``"rgb(255,0,0)"``), or ``None`` for the
        terminal default.
    bg:
        Background colour, same format as *fg*.
    bold:
        Whether the cell is rendered in bold.
    dim:
        Whether the cell is rendered dim (half-bright).
    """

    char: str = _DEFAULT_CHAR
    fg: str | None = None
    bg: str | None = None
    bold: bool = False
    dim: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.char, str) or len(self.char) != 1:
            msg = f"char must be a single character, got {self.char!r}"
            raise ValueError(msg)


def _default_cell() -> Cell:
    """Return a fresh default (blank) cell."""
    return Cell()


class CellBuffer:
    """A 2D grid of :class:`Cell` objects backed by a list of lists.

    The buffer uses **row-major order**: ``_cells[row][col]``, but the
    public API uses **(x, y)** coordinates where *x* is the column and
    *y* is the row (matching typical game/screen conventions where the
    origin is at the top-left corner).

    Parameters
    ----------
    width:
        Number of columns.  Clamped to [``_MIN_DIMENSION``,
        ``_MAX_DIMENSION``].
    height:
        Number of rows.  Clamped to [``_MIN_DIMENSION``,
        ``_MAX_DIMENSION``].
    """

    def __init__(self, width: int, height: int) -> None:
        if not isinstance(width, int):
            msg = f"width must be an int, got {type(width).__name__}"
            raise TypeError(msg)
        if not isinstance(height, int):
            msg = f"height must be an int, got {type(height).__name__}"
            raise TypeError(msg)

        self._width = max(_MIN_DIMENSION, min(width, _MAX_DIMENSION))
        self._height = max(_MIN_DIMENSION, min(height, _MAX_DIMENSION))

        # The virtual buffer: a list of rows, each row a list of Cells.
        # Caveat: every Cell is an independent object — no shared
        # references — so mutating one cell never affects another.
        self._cells: list[list[Cell]] = self._make_blank_grid()

    # -- Properties ---------------------------------------------------------

    @property
    def width(self) -> int:
        """Number of columns in the buffer."""
        return self._width

    @property
    def height(self) -> int:
        """Number of rows in the buffer."""
        return self._height

    # -- Public API ---------------------------------------------------------

    def clear(self) -> None:
        """Reset every cell to the default blank state.

        This replaces the entire internal grid.  It is called once per
        frame before the game redraws.
        """
        self._cells = self._make_blank_grid()

    def put(self, x: int, y: int, cell: Cell) -> None:
        """Write *cell* at position (*x*, *y*).

        Out-of-bounds coordinates are silently ignored (no exception).
        This allows rendering code to draw without pre-clipping to the
        buffer dimensions.
        """
        if 0 <= x < self._width and 0 <= y < self._height:
            self._cells[y][x] = cell

    def get(self, x: int, y: int) -> Cell | None:
        """Return the :class:`Cell` at (*x*, *y*), or ``None`` if out of bounds."""
        if 0 <= x < self._width and 0 <= y < self._height:
            return self._cells[y][x]
        return None

    def put_text(
        self,
        x: int,
        y: int,
        text: str,
        *,
        fg: str | None = None,
        bg: str | None = None,
        bold: bool = False,
        dim: bool = False,
    ) -> None:
        """Write a string of characters starting at (*x*, *y*).

        Each character in *text* occupies one cell.  Characters that
        fall outside the buffer (either because *x* is negative, or
        because the string extends past the right edge) are silently
        clipped.

        Caveat: this treats every Python character as one cell wide.
        CJK or emoji characters that occupy two terminal columns are
        **not** handled — the caller must account for multi-cell glyphs.
        """
        for i, char in enumerate(text):
            self.put(x + i, y, Cell(char=char, fg=fg, bg=bg, bold=bold, dim=dim))

    def fill(self, cell: Cell) -> None:
        """Fill the entire buffer with copies of *cell*."""
        for row in self._cells:
            for col in range(len(row)):
                row[col] = Cell(
                    char=cell.char, fg=cell.fg, bg=cell.bg,
                    bold=cell.bold, dim=cell.dim,
                )

    def row(self, y: int) -> list[Cell] | None:
        """Return the list of cells for row *y*, or ``None`` if out of bounds.

        The returned list is the **actual row** in the buffer — mutations
        to it will be visible in subsequent ``get()`` calls.  This is
        intentional: the renderer iterates rows to build Rich output and
        benefits from zero-copy access.
        """
        if 0 <= y < self._height:
            return self._cells[y]
        return None

    # -- Internals ----------------------------------------------------------

    def _make_blank_grid(self) -> list[list[Cell]]:
        """Allocate a fresh width × height grid of default cells."""
        return [
            [_default_cell() for _ in range(self._width)]
            for _ in range(self._height)
        ]
