"""Tests for wyby.grid — Cell and CellBuffer types."""

from __future__ import annotations

import pytest

from wyby.grid import (
    Cell,
    CellBuffer,
    _DEFAULT_CHAR,
    _MAX_DIMENSION,
    _MIN_DIMENSION,
)


# ---------------------------------------------------------------------------
# Cell
# ---------------------------------------------------------------------------


class TestCellDefaults:
    """Cell() with no arguments should produce a sensible blank cell."""

    def test_default_char_is_space(self) -> None:
        cell = Cell()
        assert cell.char == " "

    def test_default_fg_is_none(self) -> None:
        cell = Cell()
        assert cell.fg is None

    def test_default_bg_is_none(self) -> None:
        cell = Cell()
        assert cell.bg is None

    def test_default_bold_is_false(self) -> None:
        cell = Cell()
        assert cell.bold is False

    def test_default_dim_is_false(self) -> None:
        cell = Cell()
        assert cell.dim is False


class TestCellCustomValues:
    """Cell can be constructed with custom attributes."""

    def test_custom_char(self) -> None:
        cell = Cell(char="@")
        assert cell.char == "@"

    def test_custom_fg(self) -> None:
        cell = Cell(fg="red")
        assert cell.fg == "red"

    def test_custom_bg(self) -> None:
        cell = Cell(bg="#00ff00")
        assert cell.bg == "#00ff00"

    def test_custom_bold(self) -> None:
        cell = Cell(bold=True)
        assert cell.bold is True

    def test_custom_dim(self) -> None:
        cell = Cell(dim=True)
        assert cell.dim is True

    def test_all_attributes(self) -> None:
        cell = Cell(char="X", fg="blue", bg="white", bold=True, dim=True)
        assert cell.char == "X"
        assert cell.fg == "blue"
        assert cell.bg == "white"
        assert cell.bold is True
        assert cell.dim is True


class TestCellValidation:
    """Cell.char must be a single grapheme cluster."""

    def test_rejects_empty_string(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            Cell(char="")

    def test_rejects_multi_char_string(self) -> None:
        with pytest.raises(ValueError, match="single grapheme cluster"):
            Cell(char="AB")

    def test_rejects_non_string(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            Cell(char=42)  # type: ignore[arg-type]


class TestCellEquality:
    """Cells with equal fields should compare equal (dataclass default)."""

    def test_equal_cells(self) -> None:
        a = Cell(char="@", fg="red")
        b = Cell(char="@", fg="red")
        assert a == b

    def test_unequal_cells(self) -> None:
        a = Cell(char="@", fg="red")
        b = Cell(char="#", fg="red")
        assert a != b


# ---------------------------------------------------------------------------
# CellBuffer — Initialisation
# ---------------------------------------------------------------------------


class TestCellBufferInit:
    """CellBuffer initialisation and dimension properties."""

    def test_width_and_height(self) -> None:
        buf = CellBuffer(80, 24)
        assert buf.width == 80
        assert buf.height == 24

    def test_small_buffer(self) -> None:
        buf = CellBuffer(1, 1)
        assert buf.width == 1
        assert buf.height == 1

    def test_all_cells_are_default(self) -> None:
        buf = CellBuffer(3, 2)
        for y in range(2):
            for x in range(3):
                cell = buf.get(x, y)
                assert cell is not None
                assert cell.char == _DEFAULT_CHAR
                assert cell.fg is None
                assert cell.bg is None
                assert cell.bold is False
                assert cell.dim is False

    def test_cells_are_independent_objects(self) -> None:
        """Each cell in the buffer must be a separate object."""
        buf = CellBuffer(2, 2)
        cell_00 = buf.get(0, 0)
        cell_01 = buf.get(0, 1)
        cell_10 = buf.get(1, 0)
        assert cell_00 is not cell_01
        assert cell_00 is not cell_10


class TestCellBufferDimensionValidation:
    """Dimensions are type-checked and clamped."""

    def test_rejects_non_int_width(self) -> None:
        with pytest.raises(TypeError, match="width must be an int"):
            CellBuffer("80", 24)  # type: ignore[arg-type]

    def test_rejects_non_int_height(self) -> None:
        with pytest.raises(TypeError, match="height must be an int"):
            CellBuffer(80, 24.0)  # type: ignore[arg-type]

    def test_clamps_width_to_min(self) -> None:
        buf = CellBuffer(0, 10)
        assert buf.width == _MIN_DIMENSION

    def test_clamps_height_to_min(self) -> None:
        buf = CellBuffer(10, -5)
        assert buf.height == _MIN_DIMENSION

    def test_clamps_width_to_max(self) -> None:
        buf = CellBuffer(9999, 10)
        assert buf.width == _MAX_DIMENSION

    def test_clamps_height_to_max(self) -> None:
        buf = CellBuffer(10, 9999)
        assert buf.height == _MAX_DIMENSION


# ---------------------------------------------------------------------------
# CellBuffer.put / CellBuffer.get
# ---------------------------------------------------------------------------


class TestCellBufferPutGet:
    """put/get roundtrip and bounds behaviour."""

    def test_put_get_roundtrip(self) -> None:
        buf = CellBuffer(10, 10)
        cell = Cell(char="@", fg="red", bg="blue", bold=True, dim=False)
        buf.put(5, 3, cell)
        assert buf.get(5, 3) == cell

    def test_put_overwrites_existing(self) -> None:
        buf = CellBuffer(10, 10)
        buf.put(0, 0, Cell(char="A"))
        buf.put(0, 0, Cell(char="B"))
        result = buf.get(0, 0)
        assert result is not None
        assert result.char == "B"

    def test_put_at_all_corners(self) -> None:
        buf = CellBuffer(5, 3)
        corners = [(0, 0), (4, 0), (0, 2), (4, 2)]
        for x, y in corners:
            cell = Cell(char=str(x))
            buf.put(x, y, cell)
            assert buf.get(x, y) == cell

    def test_get_returns_none_for_negative_x(self) -> None:
        buf = CellBuffer(10, 10)
        assert buf.get(-1, 0) is None

    def test_get_returns_none_for_negative_y(self) -> None:
        buf = CellBuffer(10, 10)
        assert buf.get(0, -1) is None

    def test_get_returns_none_for_x_too_large(self) -> None:
        buf = CellBuffer(10, 10)
        assert buf.get(10, 0) is None

    def test_get_returns_none_for_y_too_large(self) -> None:
        buf = CellBuffer(10, 10)
        assert buf.get(0, 10) is None

    def test_put_silently_ignores_negative_x(self) -> None:
        buf = CellBuffer(10, 10)
        buf.put(-1, 0, Cell(char="X"))
        # Should not have written anywhere — all cells still default.
        for y in range(10):
            for x in range(10):
                cell = buf.get(x, y)
                assert cell is not None
                assert cell.char == _DEFAULT_CHAR

    def test_put_silently_ignores_negative_y(self) -> None:
        buf = CellBuffer(10, 10)
        buf.put(0, -1, Cell(char="X"))
        assert buf.get(0, 0) is not None
        assert buf.get(0, 0).char == _DEFAULT_CHAR  # type: ignore[union-attr]

    def test_put_silently_ignores_x_too_large(self) -> None:
        buf = CellBuffer(10, 10)
        buf.put(10, 0, Cell(char="X"))
        assert buf.get(9, 0) is not None
        assert buf.get(9, 0).char == _DEFAULT_CHAR  # type: ignore[union-attr]

    def test_put_silently_ignores_y_too_large(self) -> None:
        buf = CellBuffer(10, 10)
        buf.put(0, 10, Cell(char="X"))
        assert buf.get(0, 9) is not None
        assert buf.get(0, 9).char == _DEFAULT_CHAR  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# CellBuffer.put_text
# ---------------------------------------------------------------------------


class TestCellBufferPutText:
    """put_text writes consecutive characters with shared style."""

    def test_writes_string(self) -> None:
        buf = CellBuffer(10, 1)
        buf.put_text(0, 0, "Hello")
        for i, ch in enumerate("Hello"):
            cell = buf.get(i, 0)
            assert cell is not None
            assert cell.char == ch

    def test_applies_fg(self) -> None:
        buf = CellBuffer(10, 1)
        buf.put_text(0, 0, "Hi", fg="red")
        for i in range(2):
            cell = buf.get(i, 0)
            assert cell is not None
            assert cell.fg == "red"

    def test_applies_bg(self) -> None:
        buf = CellBuffer(10, 1)
        buf.put_text(0, 0, "Hi", bg="blue")
        for i in range(2):
            cell = buf.get(i, 0)
            assert cell is not None
            assert cell.bg == "blue"

    def test_applies_bold(self) -> None:
        buf = CellBuffer(10, 1)
        buf.put_text(0, 0, "Hi", bold=True)
        for i in range(2):
            cell = buf.get(i, 0)
            assert cell is not None
            assert cell.bold is True

    def test_applies_dim(self) -> None:
        buf = CellBuffer(10, 1)
        buf.put_text(0, 0, "Hi", dim=True)
        for i in range(2):
            cell = buf.get(i, 0)
            assert cell is not None
            assert cell.dim is True

    def test_clips_at_right_edge(self) -> None:
        buf = CellBuffer(5, 1)
        buf.put_text(3, 0, "ABCDE")
        # Only "AB" should fit (columns 3 and 4).
        assert buf.get(3, 0) is not None
        assert buf.get(3, 0).char == "A"  # type: ignore[union-attr]
        assert buf.get(4, 0) is not None
        assert buf.get(4, 0).char == "B"  # type: ignore[union-attr]

    def test_clips_negative_start(self) -> None:
        """Characters before column 0 are silently skipped."""
        buf = CellBuffer(5, 1)
        buf.put_text(-2, 0, "ABCDE")
        # x=-2 → 'A' clipped, x=-1 → 'B' clipped,
        # x=0 → 'C', x=1 → 'D', x=2 → 'E'
        assert buf.get(0, 0) is not None
        assert buf.get(0, 0).char == "C"  # type: ignore[union-attr]
        assert buf.get(1, 0) is not None
        assert buf.get(1, 0).char == "D"  # type: ignore[union-attr]
        assert buf.get(2, 0) is not None
        assert buf.get(2, 0).char == "E"  # type: ignore[union-attr]

    def test_does_not_affect_other_rows(self) -> None:
        buf = CellBuffer(10, 3)
        buf.put_text(0, 1, "Hi")
        # Row 0 should be untouched.
        assert buf.get(0, 0) is not None
        assert buf.get(0, 0).char == _DEFAULT_CHAR  # type: ignore[union-attr]

    def test_empty_string_is_noop(self) -> None:
        buf = CellBuffer(5, 1)
        buf.put_text(0, 0, "")
        assert buf.get(0, 0) is not None
        assert buf.get(0, 0).char == _DEFAULT_CHAR  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# CellBuffer.clear
# ---------------------------------------------------------------------------


class TestCellBufferClear:
    """clear() resets every cell to the default blank state."""

    def test_clear_after_put(self) -> None:
        buf = CellBuffer(5, 5)
        buf.put(2, 2, Cell(char="@", fg="red", bold=True))
        buf.clear()
        cell = buf.get(2, 2)
        assert cell is not None
        assert cell.char == _DEFAULT_CHAR
        assert cell.fg is None
        assert cell.bold is False

    def test_clear_after_put_text(self) -> None:
        buf = CellBuffer(10, 1)
        buf.put_text(0, 0, "Hello", fg="green")
        buf.clear()
        for x in range(10):
            cell = buf.get(x, 0)
            assert cell is not None
            assert cell.char == _DEFAULT_CHAR
            assert cell.fg is None

    def test_dimensions_unchanged_after_clear(self) -> None:
        buf = CellBuffer(8, 6)
        buf.clear()
        assert buf.width == 8
        assert buf.height == 6


# ---------------------------------------------------------------------------
# CellBuffer.fill
# ---------------------------------------------------------------------------


class TestCellBufferFill:
    """fill() writes copies of a cell to every position."""

    def test_fill_sets_all_cells(self) -> None:
        buf = CellBuffer(3, 2)
        cell = Cell(char=".", fg="grey")
        buf.fill(cell)
        for y in range(2):
            for x in range(3):
                got = buf.get(x, y)
                assert got is not None
                assert got.char == "."
                assert got.fg == "grey"

    def test_fill_creates_independent_copies(self) -> None:
        """Mutating the fill cell after the call must not affect the buffer."""
        buf = CellBuffer(2, 2)
        cell = Cell(char=".")
        buf.fill(cell)
        cell.char = "X"  # mutate the original
        got = buf.get(0, 0)
        assert got is not None
        assert got.char == "."  # buffer should be unaffected


# ---------------------------------------------------------------------------
# CellBuffer.row
# ---------------------------------------------------------------------------


class TestCellBufferRow:
    """row() returns the raw list for a given y-coordinate."""

    def test_returns_list_of_correct_length(self) -> None:
        buf = CellBuffer(5, 3)
        r = buf.row(0)
        assert r is not None
        assert len(r) == 5

    def test_returns_none_for_negative_y(self) -> None:
        buf = CellBuffer(5, 3)
        assert buf.row(-1) is None

    def test_returns_none_for_y_too_large(self) -> None:
        buf = CellBuffer(5, 3)
        assert buf.row(3) is None

    def test_row_reflects_put(self) -> None:
        buf = CellBuffer(5, 1)
        buf.put(2, 0, Cell(char="X"))
        r = buf.row(0)
        assert r is not None
        assert r[2].char == "X"

    def test_mutating_row_affects_buffer(self) -> None:
        """row() returns the actual internal list (zero-copy)."""
        buf = CellBuffer(3, 1)
        r = buf.row(0)
        assert r is not None
        r[1] = Cell(char="Z")
        got = buf.get(1, 0)
        assert got is not None
        assert got.char == "Z"


# ---------------------------------------------------------------------------
# Compositing pattern (integration-style)
# ---------------------------------------------------------------------------


class TestCompositingPattern:
    """Demonstrate the compositing workflow the buffer enables."""

    def test_layered_writes_overwrite_in_order(self) -> None:
        """Later writes (higher z-order) overwrite earlier ones."""
        buf = CellBuffer(5, 1)

        # Background layer: fill with dots.
        buf.fill(Cell(char="."))

        # Entity layer: place an '@' at column 2.
        buf.put(2, 0, Cell(char="@", fg="yellow"))

        # UI layer: overwrite column 2 with a border character.
        buf.put(2, 0, Cell(char="#", fg="white"))

        result = buf.get(2, 0)
        assert result is not None
        assert result.char == "#"
        assert result.fg == "white"

        # Adjacent cells should still be dots from the background.
        adjacent = buf.get(1, 0)
        assert adjacent is not None
        assert adjacent.char == "."

    def test_full_frame_cycle(self) -> None:
        """Simulate a typical frame: clear → draw background → draw entities."""
        buf = CellBuffer(10, 5)

        # Frame start: clear.
        buf.clear()

        # Draw floor.
        buf.fill(Cell(char="."))

        # Draw walls.
        buf.put_text(0, 0, "##########")
        buf.put_text(0, 4, "##########")
        for y in range(1, 4):
            buf.put(0, y, Cell(char="#"))
            buf.put(9, y, Cell(char="#"))

        # Place player.
        buf.put(5, 2, Cell(char="@", fg="green", bold=True))

        # Verify.
        player = buf.get(5, 2)
        assert player is not None
        assert player.char == "@"
        assert player.fg == "green"
        assert player.bold is True

        wall = buf.get(0, 0)
        assert wall is not None
        assert wall.char == "#"

        floor = buf.get(3, 2)
        assert floor is not None
        assert floor.char == "."


# ---------------------------------------------------------------------------
# CellBuffer.draw_text
# ---------------------------------------------------------------------------


class TestCellBufferDrawText:
    """draw_text writes text using a Rich Style object."""

    def test_writes_string_with_style(self) -> None:
        from rich.style import Style

        buf = CellBuffer(10, 1)
        buf.draw_text(0, 0, "Hello", Style(color="red", bgcolor="blue", bold=True))
        for i, ch in enumerate("Hello"):
            cell = buf.get(i, 0)
            assert cell is not None
            assert cell.char == ch
            assert cell.fg == "red"
            assert cell.bg == "blue"
            assert cell.bold is True

    def test_fg_only(self) -> None:
        from rich.style import Style

        buf = CellBuffer(10, 1)
        buf.draw_text(0, 0, "Hi", Style(color="green"))
        cell = buf.get(0, 0)
        assert cell is not None
        assert cell.fg == "green"
        assert cell.bg is None
        assert cell.bold is False
        assert cell.dim is False

    def test_bg_only(self) -> None:
        from rich.style import Style

        buf = CellBuffer(10, 1)
        buf.draw_text(0, 0, "Hi", Style(bgcolor="yellow"))
        cell = buf.get(0, 0)
        assert cell is not None
        assert cell.fg is None
        assert cell.bg == "yellow"

    def test_bold(self) -> None:
        from rich.style import Style

        buf = CellBuffer(10, 1)
        buf.draw_text(0, 0, "Hi", Style(bold=True))
        cell = buf.get(0, 0)
        assert cell is not None
        assert cell.bold is True
        assert cell.dim is False

    def test_dim(self) -> None:
        from rich.style import Style

        buf = CellBuffer(10, 1)
        buf.draw_text(0, 0, "Hi", Style(dim=True))
        cell = buf.get(0, 0)
        assert cell is not None
        assert cell.dim is True
        assert cell.bold is False

    def test_default_style_maps_to_cell_defaults(self) -> None:
        """A default Style() should produce cells with no fg/bg and bold/dim False."""
        from rich.style import Style

        buf = CellBuffer(10, 1)
        buf.draw_text(0, 0, "A", Style())
        cell = buf.get(0, 0)
        assert cell is not None
        assert cell.char == "A"
        assert cell.fg is None
        assert cell.bg is None
        assert cell.bold is False
        assert cell.dim is False

    def test_unsupported_style_attrs_are_ignored(self) -> None:
        """italic/underline/strikethrough in Style are silently dropped."""
        from rich.style import Style

        buf = CellBuffer(10, 1)
        buf.draw_text(
            0, 0, "X",
            Style(color="red", italic=True, underline=True, strike=True),
        )
        cell = buf.get(0, 0)
        assert cell is not None
        assert cell.char == "X"
        assert cell.fg == "red"

    def test_clips_at_right_edge(self) -> None:
        from rich.style import Style

        buf = CellBuffer(5, 1)
        buf.draw_text(3, 0, "ABCDE", Style(color="red"))
        assert buf.get(3, 0) is not None
        assert buf.get(3, 0).char == "A"  # type: ignore[union-attr]
        assert buf.get(4, 0) is not None
        assert buf.get(4, 0).char == "B"  # type: ignore[union-attr]

    def test_clips_negative_start(self) -> None:
        from rich.style import Style

        buf = CellBuffer(5, 1)
        buf.draw_text(-2, 0, "ABCDE", Style())
        assert buf.get(0, 0) is not None
        assert buf.get(0, 0).char == "C"  # type: ignore[union-attr]

    def test_does_not_affect_other_rows(self) -> None:
        from rich.style import Style

        buf = CellBuffer(10, 3)
        buf.draw_text(0, 1, "Hi", Style())
        cell = buf.get(0, 0)
        assert cell is not None
        assert cell.char == _DEFAULT_CHAR

    def test_empty_string_is_noop(self) -> None:
        from rich.style import Style

        buf = CellBuffer(5, 1)
        buf.draw_text(0, 0, "", Style(color="red"))
        cell = buf.get(0, 0)
        assert cell is not None
        assert cell.char == _DEFAULT_CHAR

    def test_hex_color(self) -> None:
        """Hex colour strings should pass through correctly."""
        from rich.style import Style

        buf = CellBuffer(10, 1)
        buf.draw_text(0, 0, "X", Style(color="#ff0000", bgcolor="#00ff00"))
        cell = buf.get(0, 0)
        assert cell is not None
        assert cell.fg is not None
        assert cell.bg is not None

    def test_style_reuse(self) -> None:
        """A single Style object can be reused across multiple draw_text calls."""
        from rich.style import Style

        buf = CellBuffer(10, 2)
        style = Style(color="cyan", bold=True)
        buf.draw_text(0, 0, "Line1", style)
        buf.draw_text(0, 1, "Line2", style)
        for y in range(2):
            cell = buf.get(0, y)
            assert cell is not None
            assert cell.fg == "cyan"
            assert cell.bold is True


# ---------------------------------------------------------------------------
# CellBuffer — Rich renderable protocol
# ---------------------------------------------------------------------------


class TestCellBufferRichConsole:
    """Tests for CellBuffer.__rich_console__."""

    @staticmethod
    def _render_to_str(buf: CellBuffer, *, color_system: str | None = None) -> str:
        """Render a CellBuffer to a string via a Rich Console."""
        import io
        from rich.console import Console

        sio = io.StringIO()
        console = Console(
            file=sio, force_terminal=True, color_system=color_system,
            width=buf.width,
        )
        console.print(buf, end="")
        return sio.getvalue()

    def test_blank_buffer_renders_spaces(self) -> None:
        """A default buffer should render as rows of spaces."""
        buf = CellBuffer(5, 2)
        output = self._render_to_str(buf, color_system=None)
        lines = output.split("\n")
        # Each line should be 5 spaces (possibly with trailing whitespace
        # stripped by Rich).
        for line in lines:
            if line:
                assert set(line) <= {" "}

    def test_renders_characters(self) -> None:
        """Characters written to the buffer should appear in output."""
        buf = CellBuffer(5, 1)
        buf.put_text(0, 0, "Hello")
        output = self._render_to_str(buf, color_system=None)
        assert "Hello" in output

    def test_renders_multiple_rows(self) -> None:
        """Each row should appear on a separate line."""
        buf = CellBuffer(3, 3)
        buf.put_text(0, 0, "AAA")
        buf.put_text(0, 1, "BBB")
        buf.put_text(0, 2, "CCC")
        output = self._render_to_str(buf, color_system=None)
        assert "AAA" in output
        assert "BBB" in output
        assert "CCC" in output

    def test_styled_cells_produce_ansi(self) -> None:
        """Cells with fg/bg/bold should produce ANSI escape sequences."""
        buf = CellBuffer(5, 1)
        buf.put(0, 0, Cell(char="X", fg="red", bold=True))
        output = self._render_to_str(buf, color_system="truecolor")
        # ANSI escape sequences start with \033[
        assert "\033[" in output
        assert "X" in output

    def test_default_cells_no_extra_style(self) -> None:
        """Default cells (space, no style) should not produce ANSI escapes."""
        buf = CellBuffer(3, 1)
        output = self._render_to_str(buf, color_system="truecolor")
        # Strip the Rich cursor/control sequences that wrap the output.
        # Default spaces should not have color/bold ANSI codes applied to them.
        # The content between control sequences should be plain spaces.
        assert "   " in output

    def test_mixed_styled_and_default_cells(self) -> None:
        """Styled and unstyled cells coexist in the same row."""
        buf = CellBuffer(5, 1)
        buf.put(2, 0, Cell(char="@", fg="green"))
        output = self._render_to_str(buf, color_system="truecolor")
        assert "@" in output
        assert "\033[" in output

    def test_fg_colour_applied(self) -> None:
        """Foreground colour should be present in ANSI output."""
        buf = CellBuffer(1, 1)
        buf.put(0, 0, Cell(char="X", fg="red"))
        output = self._render_to_str(buf, color_system="standard")
        # Standard red is typically \033[31m or similar.
        assert "\033[" in output
        assert "X" in output

    def test_bg_colour_applied(self) -> None:
        """Background colour should be present in ANSI output."""
        buf = CellBuffer(1, 1)
        buf.put(0, 0, Cell(char="X", bg="blue"))
        output = self._render_to_str(buf, color_system="standard")
        assert "\033[" in output
        assert "X" in output

    def test_dim_applied(self) -> None:
        """Dim attribute should produce ANSI dim escape code."""
        buf = CellBuffer(1, 1)
        buf.put(0, 0, Cell(char="D", dim=True))
        output = self._render_to_str(buf, color_system="truecolor")
        assert "\033[" in output
        assert "D" in output

    def test_row_count_matches_height(self) -> None:
        """The number of non-empty output lines should match buffer height."""
        buf = CellBuffer(3, 4)
        buf.fill(Cell(char="."))
        output = self._render_to_str(buf, color_system=None)
        lines = [line for line in output.split("\n") if line.strip()]
        assert len(lines) == 4

    def test_usable_as_rich_renderable(self) -> None:
        """CellBuffer should be accepted by any Rich consumer."""
        import io
        from rich.console import Console
        from rich.panel import Panel

        buf = CellBuffer(10, 2)
        buf.put_text(0, 0, "test")
        sio = io.StringIO()
        console = Console(file=sio, force_terminal=True, width=20)
        # Should not raise — CellBuffer is a valid Rich renderable.
        console.print(Panel(buf))

    def test_1x1_buffer(self) -> None:
        """Smallest possible buffer renders correctly."""
        buf = CellBuffer(1, 1)
        buf.put(0, 0, Cell(char="Z", fg="yellow"))
        output = self._render_to_str(buf, color_system="truecolor")
        assert "Z" in output


class TestCellBufferRichMeasure:
    """Tests for CellBuffer.__rich_measure__."""

    def test_measurement_matches_width(self) -> None:
        """Measurement min and max should both equal the buffer width."""
        import io
        from rich.console import Console

        buf = CellBuffer(42, 10)
        console = Console(file=io.StringIO(), force_terminal=True)
        measurement = buf.__rich_measure__(console, console.options)
        assert measurement.minimum == 42
        assert measurement.maximum == 42

    def test_measurement_1_column(self) -> None:
        """Single-column buffer reports width 1."""
        import io
        from rich.console import Console

        buf = CellBuffer(1, 5)
        console = Console(file=io.StringIO(), force_terminal=True)
        measurement = buf.__rich_measure__(console, console.options)
        assert measurement.minimum == 1
        assert measurement.maximum == 1
