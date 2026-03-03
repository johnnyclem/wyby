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
- **Basic Unicode support.**  Single-codepoint Unicode characters
  (box-drawing ``─│┌┐``, block elements ``█▓▒░▀▄``, arrows, symbols)
  work reliably across modern terminals.  Wide characters (CJK
  ideographs, fullwidth forms) are supported via
  :func:`~wyby.unicode.char_width` — they occupy two cells and
  ``put_text`` / ``draw_text`` advance the cursor accordingly.
  **Emoji rendering is terminal-dependent and unreliable** — stick to
  ASCII and simple Unicode for game tiles.  See :mod:`wyby.unicode`
  for full caveats on width calculation.
- **Wide character filler cells.**  When a wide (2-column) character is
  placed in the buffer, the next cell is filled with an internal
  sentinel (``_WIDE_CHAR_FILLER``).  The renderer skips these fillers.
  Overwriting either half of a wide character via ``put()`` cleans up
  the other half automatically.
- **No bounds errors.**  ``put()`` and ``put_text()`` silently clip
  writes that fall outside the buffer.  ``get()`` returns ``None`` for
  out-of-bounds coordinates.  This keeps rendering code simple (no need
  to pre-clip) but means typos in coordinates fail silently.
- **Terminal clipping.**  :meth:`CellBuffer.clip` returns a new buffer
  truncated to a given width and height.  :func:`clip_to_terminal` is a
  convenience that clips to the current terminal dimensions, useful for
  ensuring a buffer does not exceed what the terminal can display.
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

# Internal sentinel for the trailing cell of a wide (2-column) character.
# When a wide character (e.g. CJK ideograph) is placed at column x,
# column x+1 is filled with this sentinel so the renderer knows to skip
# it.  This is an implementation detail — game code should never need to
# use this value directly.
_WIDE_CHAR_FILLER = "\x00"

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

        When overwriting part of a wide character (either the character
        itself or its filler cell), the other half is automatically
        replaced with a default blank cell to prevent rendering
        artifacts.
        """
        if 0 <= x < self._width and 0 <= y < self._height:
            row = self._cells[y]
            # If we're overwriting the filler of a wide character,
            # blank the wide char in the preceding cell.
            if row[x].char == _WIDE_CHAR_FILLER and x > 0:
                row[x - 1] = _default_cell()
            # If we're overwriting a wide character that has a filler
            # to its right, blank the filler.
            if (x + 1 < self._width
                    and row[x + 1].char == _WIDE_CHAR_FILLER):
                row[x + 1] = _default_cell()
            row[x] = cell

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

        Characters are placed left-to-right, advancing by each
        character's display width.  Narrow characters (ASCII, Latin,
        box-drawing, etc.) advance by 1 column.  Wide characters (CJK
        ideographs, fullwidth forms) advance by 2 columns and place an
        internal filler cell in the trailing column.

        Characters that fall outside the buffer (either because *x* is
        negative, or because the string extends past the right edge)
        are silently clipped.  A wide character that would be split at
        the right edge (only one column remaining) is skipped entirely.

        Caveats:
            - Zero-width characters (combining marks, control
              characters) are silently skipped.  They cannot be
              meaningfully placed in a cell grid.
            - Emoji width is terminal-dependent.  Single-codepoint emoji
              are treated as width 2 per UAX #11, but actual rendering
              varies.  See :mod:`wyby.unicode` for details.
        """
        from wyby.unicode import char_width as _char_width

        col = x
        for char in text:
            w = _char_width(char)
            if w == 0:
                # Zero-width characters (combining marks, control chars)
                # cannot occupy a cell.  Skip them.
                continue
            if w == 2:
                # Wide character needs 2 columns.  If only one column
                # remains before the right edge, skip the character
                # (we can't render half a wide char).
                if 0 <= col < self._width and col + 1 >= self._width:
                    col += w
                    continue
                self.put(col, y, Cell(char=char, fg=fg, bg=bg, bold=bold, dim=dim))
                self.put(col + 1, y, Cell(
                    char=_WIDE_CHAR_FILLER, fg=None, bg=bg,
                ))
            else:
                self.put(col, y, Cell(char=char, fg=fg, bg=bg, bold=bold, dim=dim))
            col += w

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
            - Same Unicode width handling as :meth:`put_text`: wide
              characters (CJK, fullwidth) advance by 2 columns.  See
              :meth:`put_text` for details on clipping and zero-width
              character handling.
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

    def clip(self, width: int, height: int) -> CellBuffer:
        """Return a new CellBuffer clipped to the given dimensions.

        Creates a new buffer whose dimensions are the intersection of
        this buffer and the specified bounds.  Cells that fall within
        both the original buffer and the clip region are copied; cells
        outside are discarded.

        This is useful for fitting a game buffer to the actual terminal
        size before presenting, avoiding wasted rendering work for
        cells that would be invisible.

        Args:
            width: Maximum number of columns in the result.
            height: Maximum number of rows in the result.

        Returns:
            A new :class:`CellBuffer` with dimensions
            ``(min(self.width, width), min(self.height, height))``.
            If both *width* and *height* are >= the current dimensions,
            the result is a full copy of this buffer.

        Caveats:
            - Returns a **new** CellBuffer — the original is not
              modified.  Cell objects are shared (not deep-copied)
              between the original and the result.  Since game code
              typically replaces cells via ``put()`` rather than
              mutating Cell attributes in place, this is safe in
              practice.  If you mutate a Cell's attributes after
              clipping, the change is visible in both buffers.
            - Negative or zero values for *width* / *height* are
              clamped to ``_MIN_DIMENSION`` by CellBuffer's constructor,
              resulting in a 1×1 buffer.
            - Clipping removes cells at the right and bottom edges
              only.  The clip region always starts at ``(0, 0)``.
              There is no offset — to clip a sub-region, copy cells
              manually or use a future ``blit()`` method.
            - If the buffer is already smaller than the given
              dimensions, the result has the same dimensions as the
              original (it is not padded).
        """
        new_w = max(_MIN_DIMENSION, min(self._width, width))
        new_h = max(_MIN_DIMENSION, min(self._height, height))
        result = CellBuffer(new_w, new_h)
        for y in range(new_h):
            src_row = self._cells[y]
            dst_row = result._cells[y]
            for x in range(new_w):
                dst_row[x] = src_row[x]
        return result

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
                # Skip filler cells — the wide character in the
                # preceding cell already occupies this column.
                if cell.char == _WIDE_CHAR_FILLER:
                    continue
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


def clip_to_terminal(buffer: CellBuffer) -> CellBuffer:
    """Clip a CellBuffer to the current terminal dimensions.

    Convenience wrapper around :meth:`CellBuffer.clip` that queries
    the terminal size via :func:`shutil.get_terminal_size` and clips
    the buffer to fit.

    Args:
        buffer: The buffer to clip.

    Returns:
        A new :class:`CellBuffer` whose dimensions do not exceed
        the terminal's column and row counts.  If the buffer is
        already smaller than the terminal, the result is a full
        copy with the original dimensions (no padding).

    Caveats:
        - Terminal size is queried at call time via
          :func:`shutil.get_terminal_size`.  In non-TTY environments
          (CI, piped output, pytest capture), this returns a fallback
          of ``(80, 24)``, which may not reflect the actual display
          area.
        - The terminal size can change between the call to
          ``clip_to_terminal()`` and the subsequent ``present()``
          call (e.g., the user resizes the window).  For robust
          handling, use :class:`~wyby.resize.ResizeHandler` to
          detect resizes and re-clip on each frame.
        - Only the right and bottom edges are clipped.  Content at
          the top-left of the buffer is always preserved.  If the
          game's viewport is offset from ``(0, 0)``, the caller
          must handle the offset before clipping.
        - Rich's ``Live`` display already applies its own clipping
          (``vertical_overflow="crop"`` and per-row
          ``overflow="crop"``).  Calling ``clip_to_terminal()``
          before ``present()`` is an optimisation — it avoids
          building Rich ``Text`` objects and ANSI sequences for
          rows and columns that Rich would crop anyway.  For small
          buffers or low frame rates, the difference is negligible.
    """
    import shutil

    size = shutil.get_terminal_size()
    return buffer.clip(size.columns, size.lines)
