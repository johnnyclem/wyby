"""Viewport that centers a game buffer within the actual terminal dimensions.

When a game defines a logical grid size (e.g., 40x12 for a hello-world scene
or 80x24 for a standard game), the terminal may be a completely different
size.  Without a viewport, the game content renders at the top-left corner
and the rest of the terminal shows stale content, or the content wraps/clips
unpredictably.

The :class:`Viewport` solves this by:

1. Querying the actual terminal size each frame.
2. Creating a terminal-sized :class:`~wyby.grid.CellBuffer`.
3. Centering (blitting) the game's buffer into the terminal buffer.
4. Filling the border (letterbox) area with a configurable background.

This produces a clean, centered presentation regardless of terminal size:

- **Terminal larger than game grid**: Game content is centered with
  a uniform border around it (letterboxing).
- **Terminal smaller than game grid**: The center of the game content
  is shown, with edges clipped symmetrically.
- **Terminal exactly matches game grid**: No border, no clipping —
  pixel-perfect output.

The viewport implements the Rich renderable protocol, so it can be
passed directly to :meth:`Renderer.present()
<wyby.renderer.Renderer.present>` or any Rich consumer.

Caveats:
    - The viewport allocates a new terminal-sized CellBuffer each frame.
      For typical terminal sizes (80x24 to 200x50) this is fast, but
      it does add allocation overhead compared to presenting the game
      buffer directly.
    - Terminal size is queried via :func:`shutil.get_terminal_size` each
      frame.  In non-TTY environments (CI, pipes), this returns a
      fallback of (80, 24).
    - The letterbox fill is a flat color/character.  Decorative borders
      (box-drawing, gradients) are not supported — use overlay widgets
      for that.
    - Overlay widgets registered on the :class:`~wyby.renderer.Renderer`
      draw into the game buffer *before* the viewport wraps it.  This
      means overlays are positioned relative to the game grid, not the
      terminal.  Overlays outside the game grid's bounds are clipped by
      the viewport.
"""

from __future__ import annotations

import shutil
from typing import TYPE_CHECKING

from wyby.grid import Cell, CellBuffer

if TYPE_CHECKING:
    from rich.console import Console, ConsoleOptions, RenderResult
    from rich.measure import Measurement


# Default fill character for the letterbox border area.
_DEFAULT_BORDER_CHAR = " "


class Viewport:
    """Centers a game CellBuffer within the terminal's actual dimensions.

    The viewport acts as a presentation wrapper: it takes the game's
    logical buffer and produces a terminal-sized renderable with the
    game content centered.  The border area is filled with a uniform
    background.

    Args:
        border_char: Character used to fill the letterbox border.
            Defaults to a space.
        border_bg: Background color for the border area (Rich color
            string like ``"black"``, ``"#1a1a2e"``, ``"rgb(26,26,46)"``).
            Defaults to ``None`` (terminal default background).
        border_fg: Foreground color for the border character.  Only
            visible if *border_char* is not a space.  Defaults to
            ``None``.

    Example::

        viewport = Viewport(border_bg="black")
        game_buffer = CellBuffer(40, 12)
        # ... draw game content into game_buffer ...
        viewport.set_buffer(game_buffer)
        renderer.present(viewport)

    Caveats:
        - Call :meth:`set_buffer` each frame before presenting.
          If no buffer has been set, the viewport renders as a
          fully filled border (blank screen with the border style).
        - The viewport does not own the game buffer.  It reads from
          it during rendering but does not modify it.
        - Terminal size can change between :meth:`set_buffer` and the
          actual render call.  The viewport queries the size at render
          time (inside ``__rich_console__``), so it always matches the
          current terminal dimensions.
    """

    __slots__ = (
        "_buffer",
        "_border_char",
        "_border_bg",
        "_border_fg",
        "_term_width_override",
        "_term_height_override",
    )

    def __init__(
        self,
        *,
        border_char: str = _DEFAULT_BORDER_CHAR,
        border_bg: str | None = None,
        border_fg: str | None = None,
    ) -> None:
        self._buffer: CellBuffer | None = None
        self._border_char = border_char
        self._border_bg = border_bg
        self._border_fg = border_fg
        # Allow overriding terminal size for testing.
        self._term_width_override: int | None = None
        self._term_height_override: int | None = None

    @property
    def buffer(self) -> CellBuffer | None:
        """The game buffer currently being presented, or ``None``."""
        return self._buffer

    @property
    def border_char(self) -> str:
        """The character used to fill the letterbox border."""
        return self._border_char

    @property
    def border_bg(self) -> str | None:
        """Background color of the letterbox border."""
        return self._border_bg

    @property
    def border_fg(self) -> str | None:
        """Foreground color of the letterbox border character."""
        return self._border_fg

    def set_buffer(self, buffer: CellBuffer) -> None:
        """Set the game buffer to be presented.

        Args:
            buffer: The game's :class:`~wyby.grid.CellBuffer` to center
                in the terminal.

        Raises:
            TypeError: If *buffer* is not a :class:`CellBuffer`.
        """
        if not isinstance(buffer, CellBuffer):
            raise TypeError(
                f"buffer must be a CellBuffer, got {type(buffer).__name__}"
            )
        self._buffer = buffer

    def _get_terminal_size(self) -> tuple[int, int]:
        """Return (columns, rows) for the output area.

        Uses overrides if set (for testing), otherwise queries the
        actual terminal via shutil.
        """
        if (self._term_width_override is not None
                and self._term_height_override is not None):
            return (self._term_width_override, self._term_height_override)
        size = shutil.get_terminal_size()
        return (size.columns, size.lines)

    def compose(self) -> CellBuffer:
        """Build the terminal-sized buffer with the game content centered.

        Creates a new :class:`CellBuffer` matching the terminal dimensions,
        fills it with the border style, then blits the game buffer into
        the center.

        Returns:
            A terminal-sized CellBuffer ready for rendering.

        This method is called internally by ``__rich_console__`` but is
        exposed publicly for testing and inspection.
        """
        term_cols, term_rows = self._get_terminal_size()
        # Ensure at least 1x1.
        term_cols = max(1, term_cols)
        term_rows = max(1, term_rows)

        # Create the output buffer at terminal size.
        output = CellBuffer(term_cols, term_rows)

        # Fill with border style if non-default.
        if (self._border_bg is not None
                or self._border_fg is not None
                or self._border_char != " "):
            border_cell = Cell(
                char=self._border_char,
                fg=self._border_fg,
                bg=self._border_bg,
            )
            output.fill(border_cell)

        if self._buffer is None:
            return output

        game_w = self._buffer.width
        game_h = self._buffer.height

        # Calculate centering offsets.
        # If terminal is larger: positive offset = padding on left/top.
        # If terminal is smaller: negative offset = skip left/top of game.
        offset_x = (term_cols - game_w) // 2
        offset_y = (term_rows - game_h) // 2

        # Blit the game buffer into the output buffer.
        # We iterate over the game buffer and place cells at the
        # offset position, relying on CellBuffer.put() to silently
        # clip anything outside bounds.
        #
        # When terminal < game: offset is negative, so only the center
        # portion of the game is visible.
        # When terminal > game: offset is positive, creating the
        # letterbox border.
        # When terminal == game: offset is 0, no border.
        self._blit(self._buffer, output, offset_x, offset_y)

        return output

    @staticmethod
    def _blit(
        src: CellBuffer,
        dst: CellBuffer,
        offset_x: int,
        offset_y: int,
    ) -> None:
        """Copy cells from *src* to *dst* at the given offset.

        Uses direct row access for performance.  Cells that fall outside
        *dst* bounds are silently skipped (via CellBuffer.put's clipping).
        """
        src_w = src.width
        src_h = src.height
        dst_w = dst.width
        dst_h = dst.height

        # Calculate the visible region of the source buffer.
        # src_start_y/x: first row/col of src that maps to dst row/col >= 0
        # src_end_y/x: last row/col of src that maps to dst row/col < dst size
        src_start_y = max(0, -offset_y)
        src_end_y = min(src_h, dst_h - offset_y)
        src_start_x = max(0, -offset_x)
        src_end_x = min(src_w, dst_w - offset_x)

        if src_start_y >= src_end_y or src_start_x >= src_end_x:
            return  # No overlap — nothing to blit.

        for sy in range(src_start_y, src_end_y):
            src_row = src.row(sy)
            if src_row is None:
                continue
            dy = sy + offset_y
            dst_row = dst.row(dy)
            if dst_row is None:
                continue
            for sx in range(src_start_x, src_end_x):
                dx = sx + offset_x
                dst_row[dx] = src_row[sx]

    # -- Rich renderable protocol -------------------------------------------

    def __rich_console__(
        self, console: Console, options: ConsoleOptions,
    ) -> RenderResult:
        """Yield the composed viewport as Rich renderables.

        Delegates to the composed CellBuffer's ``__rich_console__`` method.
        """
        composed = self.compose()
        yield from composed.__rich_console__(console, options)

    def __rich_measure__(
        self, console: Console, options: ConsoleOptions,
    ) -> Measurement:
        """Report the terminal width for Rich layout."""
        from rich.measure import Measurement as _Measurement

        term_cols, _ = self._get_terminal_size()
        return _Measurement(term_cols, term_cols)

    def __repr__(self) -> str:
        buf_desc = (
            f"{self._buffer.width}x{self._buffer.height}"
            if self._buffer is not None
            else "None"
        )
        return (
            f"Viewport(buffer={buf_desc}, "
            f"border_char={self._border_char!r}, "
            f"border_bg={self._border_bg!r})"
        )
