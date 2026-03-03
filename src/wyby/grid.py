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
  and emoji width varies by terminal.  ``put_text`` and ``draw_text``
  place one ``Cell`` per Python character; correct multi-cell handling
  is deferred to a future ``wcwidth`` integration.
- **No bounds errors.**  ``put()`` and ``put_text()`` silently clip
  writes that fall outside the buffer.  ``get()`` returns ``None`` for
  out-of-bounds coordinates.  This keeps rendering code simple (no need
  to pre-clip) but means typos in coordinates fail silently.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rich.console import Console, ConsoleOptions, RenderResult
    from rich.measure import Measurement
    from rich.style import Style

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

    def draw_text(
        self,
        x: int,
        y: int,
        text: str,
        style: Style,
    ) -> None:
        """Write a string at (*x*, *y*) using a Rich :class:`~rich.style.Style`.

        Convenience wrapper around :meth:`put_text` that accepts a Rich
        ``Style`` object instead of individual keyword arguments.  The
        style is decomposed into :class:`Cell` attributes and delegated
        to ``put_text``.

        Args:
            x: Starting column (0-indexed).
            y: Row (0-indexed).
            text: The string to write.  Each Python character occupies
                one cell.
            style: A :class:`rich.style.Style` instance.  Only ``color``
                (foreground), ``bgcolor`` (background), ``bold``, and
                ``dim`` are extracted — other attributes (italic,
                underline, strikethrough, etc.) are **silently ignored**
                because :class:`Cell` does not support them.

        Caveats:
            - ``Style`` attributes that are ``None`` (meaning "not set"
              / "inherit") map to the Cell default: ``None`` for colours,
              ``False`` for bold/dim.  There is no style inheritance in
              CellBuffer.
            - ``Style.color`` and ``Style.bgcolor`` are converted to
              strings via ``str()``.  This produces Rich-compatible
              colour names (``"red"``, ``"#ff0000"``, etc.) but the
              CellBuffer does not validate colour values — invalid
              strings pass through and may cause errors at render time.
            - Only ``bold`` and ``dim`` are mapped.  ``italic``,
              ``underline``, ``blink``, ``reverse``, and ``strike``
              are part of Rich's ``Style`` but are not representable
              in :class:`Cell`.  If you need those, render directly
              with Rich rather than through CellBuffer.
            - Same clipping behaviour as :meth:`put_text`: characters
              outside the buffer bounds are silently ignored.
            - Same Unicode caveat as :meth:`put_text`: each Python
              character is treated as one cell wide.  CJK and emoji
              that occupy two terminal columns are not handled correctly.
        """
        # Rich Color.__str__ returns the repr, not the color name.
        # Use Color.name to get the original string ("red", "#ff0000").
        fg = style.color.name if style.color is not None else None
        bg = style.bgcolor.name if style.bgcolor is not None else None
        self.put_text(
            x, y, text,
            fg=fg,
            bg=bg,
            bold=bool(style.bold),
            dim=bool(style.dim),
        )

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

    # -- Rich renderable protocol -------------------------------------------

    def __rich_console__(
        self, console: Console, options: ConsoleOptions,
    ) -> RenderResult:
        """Yield one :class:`~rich.text.Text` per row for Rich rendering.

        Converts the cell buffer into styled Rich output that can be
        displayed by any Rich-aware consumer — ``Console.print()``,
        ``Live.update()``, or :meth:`Renderer.present()
        <wyby.renderer.Renderer.present>`.

        Each row becomes a :class:`~rich.text.Text` object with per-character
        styling derived from the cell's ``fg``, ``bg``, ``bold``, and ``dim``
        attributes.  Rows are yielded as separate renderables so Rich renders
        each on its own line.

        Caveats:
            - A :class:`~rich.style.Style` object is allocated for every
              non-default cell.  For large buffers with many styled cells
              (e.g., 120×40 = 4 800 cells), this is the main cost.  Default
              cells (space, no colours, no bold/dim) skip ``Style`` creation.
            - ``no_wrap=True`` and ``overflow="crop"`` are set on each
              ``Text`` row.  If the buffer is wider than the console, excess
              columns are silently clipped rather than wrapping to the next
              terminal line.  This matches game-grid semantics but means
              content can be invisible if the console is too narrow.
            - Only ``color``, ``bgcolor``, ``bold``, and ``dim`` are mapped
              from :class:`Cell` to :class:`~rich.style.Style`.  Rich style
              attributes like ``italic``, ``underline``, or ``strike`` are
              not representable in Cell and therefore not produced here.
            - Rich imports (``Text``, ``Style``) are deferred to call time
              so that ``grid.py`` has no module-level Rich dependency.  This
              keeps the buffer testable without Rich but adds a small
              per-frame import-lookup cost (negligible after first call due
              to module caching).
        """
        from rich.style import Style as _Style
        from rich.text import Text

        for y in range(self._height):
            line = Text(no_wrap=True, overflow="crop")
            for cell in self._cells[y]:
                # Skip Style allocation for completely default cells.
                if cell.fg or cell.bg or cell.bold or cell.dim:
                    style: _Style | None = _Style(
                        color=cell.fg,
                        bgcolor=cell.bg,
                        bold=cell.bold or None,
                        dim=cell.dim or None,
                    )
                else:
                    style = None
                line.append(cell.char, style=style)
            yield line

    def __rich_measure__(
        self, console: Console, options: ConsoleOptions,
    ) -> Measurement:
        """Report the exact width of the buffer for Rich layout.

        Returns a fixed measurement of ``(width, width)`` — the buffer's
        column count is both the minimum and maximum width.  This tells
        Rich not to shrink or expand the renderable during layout.
        """
        from rich.measure import Measurement as _Measurement

        return _Measurement(self._width, self._width)

    # -- Internals ----------------------------------------------------------

    def _make_blank_grid(self) -> list[list[Cell]]:
        """Allocate a fresh width × height grid of default cells."""
        return [
            [_default_cell() for _ in range(self._width)]
            for _ in range(self._height)
        ]
