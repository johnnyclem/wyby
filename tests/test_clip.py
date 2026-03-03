"""Tests for CellBuffer.clip() and clip_to_terminal()."""

from __future__ import annotations

from unittest import mock

from wyby.grid import (
    Cell,
    CellBuffer,
    _DEFAULT_CHAR,
    _MIN_DIMENSION,
    clip_to_terminal,
)


# ---------------------------------------------------------------------------
# CellBuffer.clip — basic behaviour
# ---------------------------------------------------------------------------


class TestClipDimensions:
    """clip() returns a buffer with the correct dimensions."""

    def test_clip_smaller_than_buffer(self) -> None:
        buf = CellBuffer(10, 8)
        clipped = buf.clip(5, 3)
        assert clipped.width == 5
        assert clipped.height == 3

    def test_clip_equal_to_buffer(self) -> None:
        buf = CellBuffer(10, 8)
        clipped = buf.clip(10, 8)
        assert clipped.width == 10
        assert clipped.height == 8

    def test_clip_larger_than_buffer(self) -> None:
        """Clipping to larger dimensions does not pad — keeps original size."""
        buf = CellBuffer(5, 3)
        clipped = buf.clip(20, 20)
        assert clipped.width == 5
        assert clipped.height == 3

    def test_clip_width_only(self) -> None:
        buf = CellBuffer(10, 5)
        clipped = buf.clip(3, 100)
        assert clipped.width == 3
        assert clipped.height == 5

    def test_clip_height_only(self) -> None:
        buf = CellBuffer(10, 5)
        clipped = buf.clip(100, 2)
        assert clipped.width == 10
        assert clipped.height == 2

    def test_clip_to_1x1(self) -> None:
        buf = CellBuffer(10, 10)
        clipped = buf.clip(1, 1)
        assert clipped.width == 1
        assert clipped.height == 1


class TestClipEdgeCases:
    """clip() handles edge cases gracefully."""

    def test_clip_zero_width_clamps_to_min(self) -> None:
        buf = CellBuffer(10, 10)
        clipped = buf.clip(0, 5)
        assert clipped.width == _MIN_DIMENSION

    def test_clip_zero_height_clamps_to_min(self) -> None:
        buf = CellBuffer(10, 10)
        clipped = buf.clip(5, 0)
        assert clipped.height == _MIN_DIMENSION

    def test_clip_negative_dimensions_clamp_to_min(self) -> None:
        buf = CellBuffer(10, 10)
        clipped = buf.clip(-5, -10)
        assert clipped.width == _MIN_DIMENSION
        assert clipped.height == _MIN_DIMENSION

    def test_clip_1x1_buffer(self) -> None:
        buf = CellBuffer(1, 1)
        buf.put(0, 0, Cell(char="X", fg="red"))
        clipped = buf.clip(1, 1)
        assert clipped.width == 1
        assert clipped.height == 1
        cell = clipped.get(0, 0)
        assert cell is not None
        assert cell.char == "X"


# ---------------------------------------------------------------------------
# CellBuffer.clip — cell content
# ---------------------------------------------------------------------------


class TestClipContent:
    """clip() copies the correct cells."""

    def test_preserves_cells_in_clip_region(self) -> None:
        buf = CellBuffer(5, 3)
        buf.put(0, 0, Cell(char="A", fg="red"))
        buf.put(1, 0, Cell(char="B", fg="blue"))
        buf.put(0, 1, Cell(char="C", bold=True))
        clipped = buf.clip(2, 2)
        assert clipped.get(0, 0) == Cell(char="A", fg="red")
        assert clipped.get(1, 0) == Cell(char="B", fg="blue")
        assert clipped.get(0, 1) == Cell(char="C", bold=True)

    def test_discards_cells_outside_clip_width(self) -> None:
        buf = CellBuffer(5, 1)
        buf.put_text(0, 0, "ABCDE")
        clipped = buf.clip(3, 1)
        assert clipped.get(0, 0) is not None
        assert clipped.get(0, 0).char == "A"  # type: ignore[union-attr]
        assert clipped.get(2, 0) is not None
        assert clipped.get(2, 0).char == "C"  # type: ignore[union-attr]
        # Columns 3 and 4 from the original are gone.
        assert clipped.get(3, 0) is None

    def test_discards_cells_outside_clip_height(self) -> None:
        buf = CellBuffer(1, 5)
        for y in range(5):
            buf.put(0, y, Cell(char=str(y)))
        clipped = buf.clip(1, 3)
        for y in range(3):
            cell = clipped.get(0, y)
            assert cell is not None
            assert cell.char == str(y)
        # Rows 3 and 4 from the original are gone.
        assert clipped.get(0, 3) is None

    def test_default_cells_preserved(self) -> None:
        """Unwritten cells in the clip region remain default blanks."""
        buf = CellBuffer(10, 10)
        clipped = buf.clip(3, 3)
        for y in range(3):
            for x in range(3):
                cell = clipped.get(x, y)
                assert cell is not None
                assert cell.char == _DEFAULT_CHAR
                assert cell.fg is None
                assert cell.bg is None

    def test_styled_cells_preserved(self) -> None:
        buf = CellBuffer(5, 5)
        buf.put(2, 2, Cell(char="@", fg="green", bg="black", bold=True, dim=True))
        clipped = buf.clip(5, 5)
        cell = clipped.get(2, 2)
        assert cell is not None
        assert cell.char == "@"
        assert cell.fg == "green"
        assert cell.bg == "black"
        assert cell.bold is True
        assert cell.dim is True

    def test_clip_equal_produces_full_copy(self) -> None:
        """Clipping to the same dimensions produces a copy of all cells."""
        buf = CellBuffer(3, 2)
        buf.put_text(0, 0, "ABC")
        buf.put_text(0, 1, "DEF")
        clipped = buf.clip(3, 2)
        for y in range(2):
            for x in range(3):
                orig = buf.get(x, y)
                copy = clipped.get(x, y)
                assert orig == copy


# ---------------------------------------------------------------------------
# CellBuffer.clip — independence from original
# ---------------------------------------------------------------------------


class TestClipIndependence:
    """clip() returns a new buffer independent of the original."""

    def test_original_not_modified(self) -> None:
        buf = CellBuffer(5, 3)
        buf.put(0, 0, Cell(char="X"))
        clipped = buf.clip(2, 2)
        # Mutate the clipped buffer.
        clipped.put(0, 0, Cell(char="Y"))
        # Original is unaffected (put replaces the cell reference).
        cell = buf.get(0, 0)
        assert cell is not None
        assert cell.char == "X"

    def test_clipped_not_affected_by_original_put(self) -> None:
        buf = CellBuffer(5, 3)
        buf.put(0, 0, Cell(char="X"))
        clipped = buf.clip(5, 3)
        # Mutate the original.
        buf.put(0, 0, Cell(char="Z"))
        # Clipped still has the original cell (shared reference
        # to the Cell written before clip, not the new one).
        cell = clipped.get(0, 0)
        assert cell is not None
        assert cell.char == "X"

    def test_clip_is_new_buffer_object(self) -> None:
        buf = CellBuffer(5, 3)
        clipped = buf.clip(5, 3)
        assert clipped is not buf


# ---------------------------------------------------------------------------
# clip_to_terminal
# ---------------------------------------------------------------------------


class TestClipToTerminal:
    """clip_to_terminal() clips a buffer to the detected terminal size."""

    def test_clips_to_terminal_size(self) -> None:
        buf = CellBuffer(200, 100)
        with mock.patch(
            "shutil.get_terminal_size",
            return_value=mock.Mock(columns=80, lines=24),
        ):
            clipped = clip_to_terminal(buf)
        assert clipped.width == 80
        assert clipped.height == 24

    def test_smaller_buffer_unchanged_dimensions(self) -> None:
        """Buffer smaller than terminal keeps its original dimensions."""
        buf = CellBuffer(40, 10)
        with mock.patch(
            "shutil.get_terminal_size",
            return_value=mock.Mock(columns=80, lines=24),
        ):
            clipped = clip_to_terminal(buf)
        assert clipped.width == 40
        assert clipped.height == 10

    def test_preserves_cell_content(self) -> None:
        buf = CellBuffer(100, 50)
        buf.put(5, 3, Cell(char="@", fg="green"))
        with mock.patch(
            "shutil.get_terminal_size",
            return_value=mock.Mock(columns=80, lines=24),
        ):
            clipped = clip_to_terminal(buf)
        cell = clipped.get(5, 3)
        assert cell is not None
        assert cell.char == "@"
        assert cell.fg == "green"

    def test_clips_content_beyond_terminal(self) -> None:
        """Cells outside the terminal bounds are discarded."""
        buf = CellBuffer(100, 50)
        buf.put(90, 30, Cell(char="X"))
        with mock.patch(
            "shutil.get_terminal_size",
            return_value=mock.Mock(columns=80, lines=24),
        ):
            clipped = clip_to_terminal(buf)
        # (90, 30) is outside the 80x24 clip.
        assert clipped.get(90, 30) is None

    def test_returns_new_buffer(self) -> None:
        buf = CellBuffer(10, 5)
        with mock.patch(
            "shutil.get_terminal_size",
            return_value=mock.Mock(columns=80, lines=24),
        ):
            clipped = clip_to_terminal(buf)
        assert clipped is not buf


# ---------------------------------------------------------------------------
# CellBuffer.clip — usable as Rich renderable
# ---------------------------------------------------------------------------


class TestClippedBufferRenderable:
    """A clipped buffer should still work as a Rich renderable."""

    def test_clipped_buffer_renders(self) -> None:
        """Clipped CellBuffer renders via Rich without errors."""
        import io

        from rich.console import Console

        buf = CellBuffer(20, 10)
        buf.put_text(0, 0, "Hello world")
        clipped = buf.clip(10, 5)

        sio = io.StringIO()
        console = Console(
            file=sio, force_terminal=True, width=clipped.width,
            color_system=None,
        )
        # Should not raise.
        console.print(clipped, end="")
        output = sio.getvalue()
        assert "Hello worl" in output  # 10 chars of "Hello world"

    def test_clipped_rich_measure(self) -> None:
        """Clipped buffer reports correct width for Rich layout."""
        import io

        from rich.console import Console

        buf = CellBuffer(20, 10)
        clipped = buf.clip(8, 4)
        console = Console(file=io.StringIO(), force_terminal=True)
        measurement = clipped.__rich_measure__(console, console.options)
        assert measurement.minimum == 8
        assert measurement.maximum == 8
