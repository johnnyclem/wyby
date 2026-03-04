"""Tests for the Viewport class that centers game content in the terminal."""

from __future__ import annotations

import pytest

from wyby.grid import Cell, CellBuffer
from wyby.viewport import Viewport


class TestViewportInit:
    """Test Viewport construction and defaults."""

    def test_default_construction(self) -> None:
        vp = Viewport()
        assert vp.buffer is None
        assert vp.border_char == " "
        assert vp.border_bg is None
        assert vp.border_fg is None

    def test_custom_border_style(self) -> None:
        vp = Viewport(border_char=".", border_bg="black", border_fg="gray")
        assert vp.border_char == "."
        assert vp.border_bg == "black"
        assert vp.border_fg == "gray"


class TestSetBuffer:
    """Test set_buffer validation and state."""

    def test_set_buffer_stores_reference(self) -> None:
        vp = Viewport()
        buf = CellBuffer(10, 5)
        vp.set_buffer(buf)
        assert vp.buffer is buf

    def test_set_buffer_rejects_non_cellbuffer(self) -> None:
        vp = Viewport()
        with pytest.raises(TypeError, match="CellBuffer"):
            vp.set_buffer("not a buffer")  # type: ignore[arg-type]

    def test_set_buffer_replaces_previous(self) -> None:
        vp = Viewport()
        buf1 = CellBuffer(10, 5)
        buf2 = CellBuffer(20, 10)
        vp.set_buffer(buf1)
        vp.set_buffer(buf2)
        assert vp.buffer is buf2


class TestCompose:
    """Test the compose method that builds the terminal-sized output."""

    @staticmethod
    def _make_viewport(
        term_w: int, term_h: int, **kwargs: object,
    ) -> Viewport:
        """Create a viewport with a fixed terminal size override."""
        vp = Viewport(**kwargs)  # type: ignore[arg-type]
        vp._term_width_override = term_w
        vp._term_height_override = term_h
        return vp

    def test_no_buffer_returns_empty(self) -> None:
        vp = self._make_viewport(80, 24)
        result = vp.compose()
        assert result.width == 80
        assert result.height == 24
        # All cells should be default (space with no style).
        cell = result.get(0, 0)
        assert cell is not None
        assert cell.char == " "

    def test_exact_fit_no_border(self) -> None:
        """When terminal matches game grid, no offset is applied."""
        vp = self._make_viewport(40, 12)
        buf = CellBuffer(40, 12)
        buf.put(0, 0, Cell(char="A", fg="red"))
        buf.put(39, 11, Cell(char="Z", fg="blue"))
        vp.set_buffer(buf)

        result = vp.compose()
        assert result.width == 40
        assert result.height == 12
        # Corners should match.
        assert result.get(0, 0).char == "A"
        assert result.get(39, 11).char == "Z"

    def test_terminal_larger_centers_content(self) -> None:
        """When terminal is larger, game content should be centered."""
        # Game: 10x4, Terminal: 20x8
        # Offsets: x=(20-10)//2=5, y=(8-4)//2=2
        vp = self._make_viewport(20, 8)
        buf = CellBuffer(10, 4)
        buf.put(0, 0, Cell(char="A"))
        buf.put(9, 3, Cell(char="Z"))
        vp.set_buffer(buf)

        result = vp.compose()
        assert result.width == 20
        assert result.height == 8

        # Game content should be at offset (5, 2).
        assert result.get(5, 2).char == "A"
        assert result.get(14, 5).char == "Z"

        # Border area should be default space.
        assert result.get(0, 0).char == " "
        assert result.get(4, 1).char == " "

    def test_terminal_smaller_clips_center(self) -> None:
        """When terminal is smaller, center of game content is shown."""
        # Game: 20x10, Terminal: 10x4
        # Offsets: x=(10-20)//2=-5, y=(4-10)//2=-3
        # Game cols 5..14 map to terminal cols 0..9
        # Game rows 3..6 map to terminal rows 0..3
        vp = self._make_viewport(10, 4)
        buf = CellBuffer(20, 10)
        # Place a marker at game position (7, 5).
        # In terminal coords: x=7-5=2, y=5-3=2
        buf.put(7, 5, Cell(char="X"))
        vp.set_buffer(buf)

        result = vp.compose()
        assert result.width == 10
        assert result.height == 4
        assert result.get(2, 2).char == "X"

    def test_terminal_smaller_clips_edges(self) -> None:
        """Content outside the visible center is not in the output."""
        # Game: 20x10, Terminal: 10x4
        # Only game rows 3-6, cols 5-14 visible
        vp = self._make_viewport(10, 4)
        buf = CellBuffer(20, 10)
        # Place marker at game (0, 0) — outside visible region.
        buf.put(0, 0, Cell(char="Q"))
        # Place marker at game (19, 9) — outside visible region.
        buf.put(19, 9, Cell(char="R"))
        vp.set_buffer(buf)

        result = vp.compose()
        # Neither marker should appear in the output.
        for y in range(result.height):
            for x in range(result.width):
                cell = result.get(x, y)
                assert cell.char != "Q"
                assert cell.char != "R"

    def test_border_bg_fills_letterbox(self) -> None:
        """Border background color fills the letterbox area."""
        vp = self._make_viewport(20, 8, border_bg="navy")
        buf = CellBuffer(10, 4)
        vp.set_buffer(buf)

        result = vp.compose()
        # Check a border cell (0, 0 is in the border).
        border_cell = result.get(0, 0)
        assert border_cell.bg == "navy"

    def test_border_char_fills_letterbox(self) -> None:
        """Custom border character fills the letterbox area."""
        vp = self._make_viewport(20, 8, border_char=".")
        buf = CellBuffer(10, 4)
        vp.set_buffer(buf)

        result = vp.compose()
        border_cell = result.get(0, 0)
        assert border_cell.char == "."

    def test_asymmetric_centering(self) -> None:
        """Odd-sized difference produces consistent centering."""
        # Game: 5x3, Terminal: 10x7
        # x offset: (10-5)//2 = 2
        # y offset: (7-3)//2 = 2
        vp = self._make_viewport(10, 7)
        buf = CellBuffer(5, 3)
        buf.put(0, 0, Cell(char="A"))
        buf.put(4, 2, Cell(char="Z"))
        vp.set_buffer(buf)

        result = vp.compose()
        assert result.get(2, 2).char == "A"
        assert result.get(6, 4).char == "Z"

    def test_1x1_game_buffer(self) -> None:
        """Edge case: single-cell game buffer in a larger terminal."""
        vp = self._make_viewport(10, 6)
        buf = CellBuffer(1, 1)
        buf.put(0, 0, Cell(char="*"))
        vp.set_buffer(buf)

        result = vp.compose()
        # Center position: (4, 2)
        assert result.get(4, 2).char == "*"

    def test_1x1_terminal(self) -> None:
        """Edge case: 1x1 terminal showing center of game buffer."""
        vp = self._make_viewport(1, 1)
        buf = CellBuffer(10, 10)
        # Center of 10x10 in 1x1: offset = (1-10)//2 = -4 (Python floor div)
        # Visible: game col 4, game row 4
        # offset_x = (1 - 10) // 2 = -9 // 2 = -5 (Python floor division)
        # So game col 5 maps to terminal col 0.
        buf.put(5, 5, Cell(char="C"))
        vp.set_buffer(buf)

        result = vp.compose()
        assert result.width == 1
        assert result.height == 1
        assert result.get(0, 0).char == "C"


class TestRichProtocol:
    """Test that Viewport works as a Rich renderable."""

    def test_rich_console_yields_lines(self) -> None:
        """__rich_console__ should yield one item per row."""
        from io import StringIO
        from rich.console import Console

        vp = Viewport()
        vp._term_width_override = 10
        vp._term_height_override = 3
        buf = CellBuffer(10, 3)
        buf.put_text(0, 1, "Hello!", fg="green")
        vp.set_buffer(buf)

        console = Console(file=StringIO(), force_terminal=True, width=10, height=3)
        options = console.options
        lines = list(vp.__rich_console__(console, options))
        assert len(lines) == 3

    def test_rich_measure_returns_terminal_width(self) -> None:
        """__rich_measure__ should return the terminal width."""
        from io import StringIO
        from rich.console import Console

        vp = Viewport()
        vp._term_width_override = 42
        vp._term_height_override = 10

        console = Console(file=StringIO(), force_terminal=True, width=42)
        options = console.options
        measurement = vp.__rich_measure__(console, options)
        assert measurement.minimum == 42
        assert measurement.maximum == 42


class TestRepr:
    """Test the string representation."""

    def test_repr_no_buffer(self) -> None:
        vp = Viewport()
        r = repr(vp)
        assert "None" in r
        assert "Viewport" in r

    def test_repr_with_buffer(self) -> None:
        vp = Viewport(border_bg="black")
        vp.set_buffer(CellBuffer(40, 12))
        r = repr(vp)
        assert "40x12" in r
        assert "black" in r
