"""Tests for wyby.unicode — character width utilities and unicode rendering."""

from __future__ import annotations

import pytest

from wyby.unicode import char_width, is_wide_char, string_width
from wyby.grid import Cell, CellBuffer, _DEFAULT_CHAR, _WIDE_CHAR_FILLER


# ---------------------------------------------------------------------------
# char_width
# ---------------------------------------------------------------------------


class TestCharWidthASCII:
    """ASCII characters should all be width 1."""

    def test_letter(self) -> None:
        assert char_width("A") == 1

    def test_digit(self) -> None:
        assert char_width("0") == 1

    def test_space(self) -> None:
        assert char_width(" ") == 1

    def test_punctuation(self) -> None:
        assert char_width("!") == 1
        assert char_width(".") == 1
        assert char_width("@") == 1


class TestCharWidthBoxDrawing:
    """Box-drawing characters (U+2500–U+257F) are width 1."""

    def test_horizontal_line(self) -> None:
        assert char_width("─") == 1  # U+2500

    def test_vertical_line(self) -> None:
        assert char_width("│") == 1  # U+2502

    def test_corners(self) -> None:
        assert char_width("┌") == 1  # U+250C
        assert char_width("┐") == 1  # U+2510
        assert char_width("└") == 1  # U+2514
        assert char_width("┘") == 1  # U+2518

    def test_tees(self) -> None:
        assert char_width("├") == 1  # U+251C
        assert char_width("┤") == 1  # U+2524
        assert char_width("┬") == 1  # U+252C
        assert char_width("┴") == 1  # U+2534

    def test_cross(self) -> None:
        assert char_width("┼") == 1  # U+253C

    def test_double_lines(self) -> None:
        assert char_width("═") == 1  # U+2550
        assert char_width("║") == 1  # U+2551


class TestCharWidthBlockElements:
    """Block element characters (U+2580–U+259F) are width 1."""

    def test_full_block(self) -> None:
        assert char_width("█") == 1  # U+2588

    def test_shade_blocks(self) -> None:
        assert char_width("░") == 1  # U+2591 light shade
        assert char_width("▒") == 1  # U+2592 medium shade
        assert char_width("▓") == 1  # U+2593 dark shade

    def test_half_blocks(self) -> None:
        assert char_width("▀") == 1  # U+2580 upper half
        assert char_width("▄") == 1  # U+2584 lower half
        assert char_width("▌") == 1  # U+258C left half
        assert char_width("▐") == 1  # U+2590 right half


class TestCharWidthArrowsAndSymbols:
    """Common Unicode symbols used in games are width 1."""

    def test_arrows(self) -> None:
        assert char_width("←") == 1  # U+2190
        assert char_width("→") == 1  # U+2192
        assert char_width("↑") == 1  # U+2191
        assert char_width("↓") == 1  # U+2193

    def test_misc_symbols(self) -> None:
        assert char_width("♠") == 1  # U+2660
        assert char_width("♣") == 1  # U+2663
        assert char_width("★") == 1  # U+2605
        assert char_width("●") == 1  # U+25CF
        assert char_width("◆") == 1  # U+25C6
        assert char_width("▶") == 1  # U+25B6

    def test_mathematical(self) -> None:
        assert char_width("±") == 1
        assert char_width("×") == 1
        assert char_width("÷") == 1


class TestCharWidthWide:
    """CJK and fullwidth characters are width 2."""

    def test_cjk_ideograph(self) -> None:
        assert char_width("中") == 2
        assert char_width("文") == 2
        assert char_width("字") == 2

    def test_japanese_hiragana(self) -> None:
        assert char_width("あ") == 2
        assert char_width("い") == 2

    def test_japanese_katakana(self) -> None:
        assert char_width("ア") == 2
        assert char_width("イ") == 2

    def test_korean_hangul(self) -> None:
        assert char_width("가") == 2
        assert char_width("나") == 2

    def test_fullwidth_latin(self) -> None:
        assert char_width("Ａ") == 2  # U+FF21 Fullwidth A
        assert char_width("ａ") == 2  # U+FF41 Fullwidth a
        assert char_width("０") == 2  # U+FF10 Fullwidth 0


class TestCharWidthZero:
    """Combining marks and control characters have width 0."""

    def test_combining_acute_accent(self) -> None:
        assert char_width("\u0301") == 0  # Combining acute accent

    def test_combining_tilde(self) -> None:
        assert char_width("\u0303") == 0  # Combining tilde

    def test_null_char(self) -> None:
        assert char_width("\x00") == 0

    def test_zero_width_joiner(self) -> None:
        assert char_width("\u200D") == 0  # ZWJ

    def test_soft_hyphen(self) -> None:
        assert char_width("\u00AD") == 0  # Soft hyphen (Cf category)


class TestCharWidthValidation:
    """char_width rejects invalid input."""

    def test_rejects_empty_string(self) -> None:
        with pytest.raises(ValueError, match="single character"):
            char_width("")

    def test_rejects_multi_char_string(self) -> None:
        with pytest.raises(ValueError, match="single character"):
            char_width("AB")

    def test_rejects_non_string(self) -> None:
        with pytest.raises(ValueError, match="single character"):
            char_width(42)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# string_width
# ---------------------------------------------------------------------------


class TestStringWidth:
    """string_width sums display widths of all characters."""

    def test_ascii_string(self) -> None:
        assert string_width("Hello") == 5

    def test_empty_string(self) -> None:
        assert string_width("") == 0

    def test_cjk_string(self) -> None:
        assert string_width("中文") == 4  # 2 + 2

    def test_mixed_ascii_cjk(self) -> None:
        assert string_width("A中B") == 4  # 1 + 2 + 1

    def test_box_drawing_string(self) -> None:
        assert string_width("┌──┐") == 4  # all width 1

    def test_fullwidth_string(self) -> None:
        assert string_width("ＡＢ") == 4  # 2 + 2


# ---------------------------------------------------------------------------
# is_wide_char
# ---------------------------------------------------------------------------


class TestIsWideChar:
    """is_wide_char returns True only for 2-column characters."""

    def test_ascii_not_wide(self) -> None:
        assert is_wide_char("A") is False

    def test_box_drawing_not_wide(self) -> None:
        assert is_wide_char("│") is False

    def test_block_not_wide(self) -> None:
        assert is_wide_char("█") is False

    def test_cjk_is_wide(self) -> None:
        assert is_wide_char("中") is True

    def test_fullwidth_is_wide(self) -> None:
        assert is_wide_char("Ａ") is True


# ---------------------------------------------------------------------------
# Cell with unicode characters
# ---------------------------------------------------------------------------


class TestCellUnicode:
    """Cell accepts single-codepoint Unicode characters."""

    def test_box_drawing_char(self) -> None:
        cell = Cell(char="│")
        assert cell.char == "│"

    def test_block_element(self) -> None:
        cell = Cell(char="█")
        assert cell.char == "█"

    def test_arrow(self) -> None:
        cell = Cell(char="→")
        assert cell.char == "→"

    def test_cjk_ideograph(self) -> None:
        cell = Cell(char="中")
        assert cell.char == "中"

    def test_fullwidth_char(self) -> None:
        cell = Cell(char="Ａ")
        assert cell.char == "Ａ"

    def test_symbol(self) -> None:
        cell = Cell(char="★")
        assert cell.char == "★"

    def test_styled_unicode(self) -> None:
        cell = Cell(char="●", fg="red", bg="blue", bold=True)
        assert cell.char == "●"
        assert cell.fg == "red"
        assert cell.bg == "blue"
        assert cell.bold is True


# ---------------------------------------------------------------------------
# CellBuffer.put_text with unicode — narrow characters
# ---------------------------------------------------------------------------


class TestCellBufferPutTextUnicode:
    """put_text handles basic Unicode characters correctly."""

    def test_box_drawing_string(self) -> None:
        buf = CellBuffer(10, 1)
        buf.put_text(0, 0, "┌──┐")
        assert buf.get(0, 0).char == "┌"  # type: ignore[union-attr]
        assert buf.get(1, 0).char == "─"  # type: ignore[union-attr]
        assert buf.get(2, 0).char == "─"  # type: ignore[union-attr]
        assert buf.get(3, 0).char == "┐"  # type: ignore[union-attr]

    def test_block_elements(self) -> None:
        buf = CellBuffer(5, 1)
        buf.put_text(0, 0, "█▓▒░")
        assert buf.get(0, 0).char == "█"  # type: ignore[union-attr]
        assert buf.get(1, 0).char == "▓"  # type: ignore[union-attr]
        assert buf.get(2, 0).char == "▒"  # type: ignore[union-attr]
        assert buf.get(3, 0).char == "░"  # type: ignore[union-attr]

    def test_arrows_with_style(self) -> None:
        buf = CellBuffer(10, 1)
        buf.put_text(0, 0, "←↑→↓", fg="green")
        for i, ch in enumerate("←↑→↓"):
            cell = buf.get(i, 0)
            assert cell is not None
            assert cell.char == ch
            assert cell.fg == "green"

    def test_unicode_clips_at_right_edge(self) -> None:
        buf = CellBuffer(3, 1)
        buf.put_text(1, 0, "│──│")
        # Only 2 chars fit (columns 1 and 2)
        assert buf.get(1, 0).char == "│"  # type: ignore[union-attr]
        assert buf.get(2, 0).char == "─"  # type: ignore[union-attr]

    def test_roguelike_map_tiles(self) -> None:
        """Common roguelike tiles render correctly."""
        buf = CellBuffer(10, 3)
        # Walls
        buf.put_text(0, 0, "##########")
        # Floor with player and items
        buf.put(0, 1, Cell(char="#"))
        buf.put(1, 1, Cell(char="·"))  # middle dot
        buf.put(2, 1, Cell(char="@", fg="yellow"))
        buf.put(3, 1, Cell(char="·"))
        buf.put(4, 1, Cell(char="♦", fg="cyan"))  # diamond
        assert buf.get(2, 1).char == "@"  # type: ignore[union-attr]
        assert buf.get(4, 1).char == "♦"  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# CellBuffer.put_text with wide characters (CJK)
# ---------------------------------------------------------------------------


class TestCellBufferPutTextWide:
    """put_text handles wide (2-column) characters correctly."""

    def test_single_wide_char(self) -> None:
        """A wide char should occupy 2 columns."""
        buf = CellBuffer(10, 1)
        buf.put_text(0, 0, "中")
        cell = buf.get(0, 0)
        assert cell is not None
        assert cell.char == "中"
        # The next cell should be the filler.
        filler = buf.get(1, 0)
        assert filler is not None
        assert filler.char == _WIDE_CHAR_FILLER

    def test_wide_char_with_style(self) -> None:
        """Style is applied to the wide character cell."""
        buf = CellBuffer(10, 1)
        buf.put_text(0, 0, "中", fg="red", bold=True)
        cell = buf.get(0, 0)
        assert cell is not None
        assert cell.fg == "red"
        assert cell.bold is True

    def test_wide_char_filler_preserves_bg(self) -> None:
        """Filler cell preserves background colour for visual consistency."""
        buf = CellBuffer(10, 1)
        buf.put_text(0, 0, "中", bg="blue")
        filler = buf.get(1, 0)
        assert filler is not None
        assert filler.bg == "blue"

    def test_consecutive_wide_chars(self) -> None:
        """Multiple wide chars advance by 2 each."""
        buf = CellBuffer(10, 1)
        buf.put_text(0, 0, "中文")
        # '中' at 0, filler at 1, '文' at 2, filler at 3
        assert buf.get(0, 0).char == "中"  # type: ignore[union-attr]
        assert buf.get(1, 0).char == _WIDE_CHAR_FILLER  # type: ignore[union-attr]
        assert buf.get(2, 0).char == "文"  # type: ignore[union-attr]
        assert buf.get(3, 0).char == _WIDE_CHAR_FILLER  # type: ignore[union-attr]

    def test_mixed_narrow_and_wide(self) -> None:
        """Mixed narrow + wide characters advance correctly."""
        buf = CellBuffer(10, 1)
        buf.put_text(0, 0, "A中B")
        # 'A' at 0, '中' at 1, filler at 2, 'B' at 3
        assert buf.get(0, 0).char == "A"  # type: ignore[union-attr]
        assert buf.get(1, 0).char == "中"  # type: ignore[union-attr]
        assert buf.get(2, 0).char == _WIDE_CHAR_FILLER  # type: ignore[union-attr]
        assert buf.get(3, 0).char == "B"  # type: ignore[union-attr]

    def test_wide_char_at_last_column_is_skipped(self) -> None:
        """A wide char that doesn't fit at the right edge is dropped."""
        buf = CellBuffer(3, 1)
        buf.put_text(2, 0, "中")
        # Column 2 is the last — wide char needs 2 columns, should be skipped.
        cell = buf.get(2, 0)
        assert cell is not None
        assert cell.char == _DEFAULT_CHAR

    def test_wide_char_followed_by_narrow_at_edge(self) -> None:
        """Wide char skipped at edge, but a following narrow char is placed."""
        buf = CellBuffer(5, 1)
        buf.put_text(3, 0, "中A")
        # '中' needs columns 3-4, but only column 3 and 4 exist (5-wide buffer).
        # Actually column 4 is the last (0-indexed), so 3+1=4 < 5, so it fits!
        assert buf.get(3, 0).char == "中"  # type: ignore[union-attr]
        assert buf.get(4, 0).char == _WIDE_CHAR_FILLER  # type: ignore[union-attr]

    def test_wide_char_skipped_narrow_placed_after(self) -> None:
        """When a wide char is skipped at the edge, subsequent chars continue."""
        buf = CellBuffer(3, 1)
        # Put "X中A" starting at column 0:
        # 'X' at 0, '中' at 1 (needs 1 & 2 — fits!), 'A' at 3 — clipped
        buf.put_text(0, 0, "X中A")
        assert buf.get(0, 0).char == "X"  # type: ignore[union-attr]
        assert buf.get(1, 0).char == "中"  # type: ignore[union-attr]
        assert buf.get(2, 0).char == _WIDE_CHAR_FILLER  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# Wide character overwrite cleanup in put()
# ---------------------------------------------------------------------------


class TestWideCharOverwriteCleanup:
    """Overwriting part of a wide character cleans up the other half."""

    def test_overwrite_filler_blanks_wide_char(self) -> None:
        """Overwriting the filler cell of a wide char blanks the char."""
        buf = CellBuffer(10, 1)
        buf.put_text(0, 0, "中")
        assert buf.get(0, 0).char == "中"  # type: ignore[union-attr]
        assert buf.get(1, 0).char == _WIDE_CHAR_FILLER  # type: ignore[union-attr]

        # Overwrite the filler at column 1
        buf.put(1, 0, Cell(char="B"))
        assert buf.get(1, 0).char == "B"  # type: ignore[union-attr]
        # The wide char at column 0 should be blanked
        assert buf.get(0, 0).char == _DEFAULT_CHAR  # type: ignore[union-attr]

    def test_overwrite_wide_char_blanks_filler(self) -> None:
        """Overwriting a wide char blanks its filler in the next cell."""
        buf = CellBuffer(10, 1)
        buf.put_text(0, 0, "中")
        assert buf.get(0, 0).char == "中"  # type: ignore[union-attr]
        assert buf.get(1, 0).char == _WIDE_CHAR_FILLER  # type: ignore[union-attr]

        # Overwrite the wide char at column 0
        buf.put(0, 0, Cell(char="A"))
        assert buf.get(0, 0).char == "A"  # type: ignore[union-attr]
        # The filler at column 1 should be blanked
        assert buf.get(1, 0).char == _DEFAULT_CHAR  # type: ignore[union-attr]

    def test_overwrite_with_another_wide_char(self) -> None:
        """Replacing a wide char with another wide char works."""
        buf = CellBuffer(10, 1)
        buf.put_text(0, 0, "中")
        buf.put_text(0, 0, "文")
        assert buf.get(0, 0).char == "文"  # type: ignore[union-attr]
        assert buf.get(1, 0).char == _WIDE_CHAR_FILLER  # type: ignore[union-attr]

    def test_clear_removes_fillers(self) -> None:
        """clear() resets all cells including fillers."""
        buf = CellBuffer(10, 1)
        buf.put_text(0, 0, "中文字")
        buf.clear()
        for x in range(10):
            cell = buf.get(x, 0)
            assert cell is not None
            assert cell.char == _DEFAULT_CHAR


# ---------------------------------------------------------------------------
# CellBuffer.draw_text with unicode
# ---------------------------------------------------------------------------


class TestCellBufferDrawTextUnicode:
    """draw_text delegates to put_text and handles unicode correctly."""

    def test_draw_text_box_drawing(self) -> None:
        from rich.style import Style

        buf = CellBuffer(10, 1)
        buf.draw_text(0, 0, "┌──┐", Style(color="green"))
        for i, ch in enumerate("┌──┐"):
            cell = buf.get(i, 0)
            assert cell is not None
            assert cell.char == ch
            assert cell.fg == "green"

    def test_draw_text_wide_char(self) -> None:
        from rich.style import Style

        buf = CellBuffer(10, 1)
        buf.draw_text(0, 0, "中", Style(color="red", bgcolor="blue"))
        cell = buf.get(0, 0)
        assert cell is not None
        assert cell.char == "中"
        assert cell.fg == "red"
        assert cell.bg == "blue"
        # Filler
        filler = buf.get(1, 0)
        assert filler is not None
        assert filler.char == _WIDE_CHAR_FILLER


# ---------------------------------------------------------------------------
# CellBuffer Rich rendering with unicode
# ---------------------------------------------------------------------------


class TestCellBufferRichRenderUnicode:
    """Tests for __rich_console__ with unicode characters."""

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

    def test_renders_box_drawing(self) -> None:
        """Box-drawing characters appear in output."""
        buf = CellBuffer(5, 1)
        buf.put_text(0, 0, "┌──┐")
        output = self._render_to_str(buf, color_system=None)
        assert "┌" in output
        assert "─" in output
        assert "┐" in output

    def test_renders_block_elements(self) -> None:
        """Block element characters appear in output."""
        buf = CellBuffer(4, 1)
        buf.put_text(0, 0, "█▓▒░")
        output = self._render_to_str(buf, color_system=None)
        assert "█" in output
        assert "░" in output

    def test_renders_arrows(self) -> None:
        buf = CellBuffer(4, 1)
        buf.put_text(0, 0, "←→↑↓")
        output = self._render_to_str(buf, color_system=None)
        assert "←" in output
        assert "→" in output

    def test_renders_wide_char(self) -> None:
        """Wide characters are rendered without their filler cells."""
        buf = CellBuffer(10, 1)
        buf.put_text(0, 0, "中")
        output = self._render_to_str(buf, color_system=None)
        assert "中" in output
        # The filler (\x00) should NOT appear in the output
        assert "\x00" not in output

    def test_renders_mixed_narrow_wide(self) -> None:
        """Mixed narrow and wide characters render correctly."""
        buf = CellBuffer(10, 1)
        buf.put_text(0, 0, "A中B")
        output = self._render_to_str(buf, color_system=None)
        assert "A" in output
        assert "中" in output
        assert "B" in output
        assert "\x00" not in output

    def test_renders_styled_unicode(self) -> None:
        """Styled unicode characters produce ANSI output."""
        buf = CellBuffer(5, 1)
        buf.put(0, 0, Cell(char="█", fg="red"))
        buf.put(1, 0, Cell(char="░", fg="blue"))
        output = self._render_to_str(buf, color_system="truecolor")
        assert "█" in output
        assert "░" in output
        assert "\033[" in output  # ANSI escapes present

    def test_roguelike_map_renders(self) -> None:
        """A small roguelike map with Unicode tiles renders correctly."""
        buf = CellBuffer(5, 3)
        buf.put_text(0, 0, "┌───┐")
        buf.put_text(0, 1, "│")
        buf.put(1, 1, Cell(char="·"))
        buf.put(2, 1, Cell(char="@", fg="yellow", bold=True))
        buf.put(3, 1, Cell(char="·"))
        buf.put_text(4, 1, "│")
        buf.put_text(0, 2, "└───┘")
        output = self._render_to_str(buf, color_system=None)
        assert "┌" in output
        assert "@" in output
        assert "└" in output

    def test_half_block_rendering(self) -> None:
        """Half-block 'pixel' technique renders correctly."""
        buf = CellBuffer(3, 1)
        # Upper half block with fg/bg to simulate 2x vertical resolution
        buf.put(0, 0, Cell(char="▀", fg="red", bg="blue"))
        buf.put(1, 0, Cell(char="▄", fg="green", bg="yellow"))
        buf.put(2, 0, Cell(char="█", fg="white"))
        output = self._render_to_str(buf, color_system="truecolor")
        assert "▀" in output
        assert "▄" in output
        assert "█" in output


# ---------------------------------------------------------------------------
# CellBuffer.fill with unicode
# ---------------------------------------------------------------------------


class TestCellBufferFillUnicode:
    """fill() works with unicode characters."""

    def test_fill_with_box_drawing(self) -> None:
        buf = CellBuffer(3, 2)
        buf.fill(Cell(char="·"))
        for y in range(2):
            for x in range(3):
                cell = buf.get(x, y)
                assert cell is not None
                assert cell.char == "·"

    def test_fill_with_block(self) -> None:
        buf = CellBuffer(2, 2)
        buf.fill(Cell(char="█", fg="grey"))
        for y in range(2):
            for x in range(2):
                cell = buf.get(x, y)
                assert cell is not None
                assert cell.char == "█"
                assert cell.fg == "grey"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestUnicodeEdgeCases:
    """Edge cases for unicode rendering."""

    def test_put_text_skips_zero_width_chars(self) -> None:
        """Zero-width characters (combining marks) are silently skipped."""
        buf = CellBuffer(10, 1)
        # U+0301 is combining acute accent (zero width)
        buf.put_text(0, 0, "A\u0301B")
        # 'A' at 0, combining mark skipped, 'B' at 1
        assert buf.get(0, 0).char == "A"  # type: ignore[union-attr]
        assert buf.get(1, 0).char == "B"  # type: ignore[union-attr]

    def test_wide_char_at_negative_x(self) -> None:
        """Wide chars at negative x are silently clipped."""
        buf = CellBuffer(5, 1)
        buf.put_text(-1, 0, "中A")
        # '中' at -1 needs -1 and 0 — put at -1 is clipped, filler at 0 placed
        # 'A' at 1
        assert buf.get(1, 0).char == "A"  # type: ignore[union-attr]

    def test_latin_extended_chars(self) -> None:
        """Latin extended characters (accented) are width 1."""
        buf = CellBuffer(10, 1)
        buf.put_text(0, 0, "éàü")
        assert buf.get(0, 0).char == "é"  # type: ignore[union-attr]
        assert buf.get(1, 0).char == "à"  # type: ignore[union-attr]
        assert buf.get(2, 0).char == "ü"  # type: ignore[union-attr]

    def test_cyrillic_chars(self) -> None:
        """Cyrillic characters are width 1."""
        buf = CellBuffer(10, 1)
        buf.put_text(0, 0, "Дом")
        assert buf.get(0, 0).char == "Д"  # type: ignore[union-attr]
        assert buf.get(1, 0).char == "о"  # type: ignore[union-attr]
        assert buf.get(2, 0).char == "м"  # type: ignore[union-attr]

    def test_greek_chars(self) -> None:
        """Greek characters are width 1."""
        buf = CellBuffer(5, 1)
        buf.put_text(0, 0, "αβγ")
        assert buf.get(0, 0).char == "α"  # type: ignore[union-attr]
        assert buf.get(1, 0).char == "β"  # type: ignore[union-attr]
        assert buf.get(2, 0).char == "γ"  # type: ignore[union-attr]

    def test_multiple_wide_chars_fill_buffer(self) -> None:
        """Wide chars that fill the buffer exactly."""
        buf = CellBuffer(4, 1)
        buf.put_text(0, 0, "中文")
        # '中' at 0, filler at 1, '文' at 2, filler at 3
        assert buf.get(0, 0).char == "中"  # type: ignore[union-attr]
        assert buf.get(2, 0).char == "文"  # type: ignore[union-attr]
        assert buf.get(1, 0).char == _WIDE_CHAR_FILLER  # type: ignore[union-attr]
        assert buf.get(3, 0).char == _WIDE_CHAR_FILLER  # type: ignore[union-attr]

    def test_wide_char_overflow_exact(self) -> None:
        """Wide char at second-to-last column fits."""
        buf = CellBuffer(4, 1)
        buf.put_text(2, 0, "中")
        # Column 2 + 3 (width 4) — fits exactly
        assert buf.get(2, 0).char == "中"  # type: ignore[union-attr]
        assert buf.get(3, 0).char == _WIDE_CHAR_FILLER  # type: ignore[union-attr]

    def test_wide_char_overflow_by_one(self) -> None:
        """Wide char at last column doesn't fit — skipped."""
        buf = CellBuffer(4, 1)
        buf.put_text(3, 0, "中")
        # Column 3 is the last (0-indexed in width-4 buffer)
        # Wide char needs columns 3 and 4, but 4 is out of bounds.
        assert buf.get(3, 0).char == _DEFAULT_CHAR  # type: ignore[union-attr]
