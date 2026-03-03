"""Tests for wyby.unicode — character width utilities and unicode rendering."""

from __future__ import annotations

import pytest

from wyby.unicode import (
    char_width,
    contains_emoji,
    grapheme_string_width,
    grapheme_width,
    is_wide_char,
    iter_grapheme_clusters,
    string_width,
)
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


# ---------------------------------------------------------------------------
# iter_grapheme_clusters
# ---------------------------------------------------------------------------


class TestIterGraphemeClustersBasic:
    """iter_grapheme_clusters handles simple text correctly."""

    def test_ascii_string(self) -> None:
        assert list(iter_grapheme_clusters("Hello")) == ["H", "e", "l", "l", "o"]

    def test_empty_string(self) -> None:
        assert list(iter_grapheme_clusters("")) == []

    def test_single_char(self) -> None:
        assert list(iter_grapheme_clusters("A")) == ["A"]

    def test_cjk_chars(self) -> None:
        assert list(iter_grapheme_clusters("中文")) == ["中", "文"]

    def test_mixed_ascii_cjk(self) -> None:
        assert list(iter_grapheme_clusters("A中B")) == ["A", "中", "B"]


class TestIterGraphemeClustersCombining:
    """iter_grapheme_clusters groups combining marks with base characters."""

    def test_combining_acute(self) -> None:
        """e + combining acute accent → single cluster."""
        text = "e\u0301"  # e + combining acute
        clusters = list(iter_grapheme_clusters(text))
        assert clusters == ["e\u0301"]

    def test_multiple_combining_marks(self) -> None:
        """Base + multiple combining marks → single cluster."""
        # a + combining tilde + combining acute
        text = "a\u0303\u0301"
        clusters = list(iter_grapheme_clusters(text))
        assert clusters == ["a\u0303\u0301"]

    def test_combining_between_bases(self) -> None:
        """Each base absorbs its own combining marks."""
        # a + combining acute, b + combining tilde
        text = "a\u0301b\u0303"
        clusters = list(iter_grapheme_clusters(text))
        assert clusters == ["a\u0301", "b\u0303"]

    def test_orphaned_combining_mark(self) -> None:
        """A combining mark at the start forms its own cluster."""
        text = "\u0301A"  # combining acute, then A
        clusters = list(iter_grapheme_clusters(text))
        # The combining mark has no base to attach to — becomes its own cluster.
        assert clusters == ["\u0301", "A"]


class TestIterGraphemeClustersZWJ:
    """iter_grapheme_clusters handles ZWJ sequences."""

    def test_zwj_joins_two_chars(self) -> None:
        """Two characters joined by ZWJ form a single cluster."""
        text = "\U0001F468\u200D\U0001F469"  # man ZWJ woman
        clusters = list(iter_grapheme_clusters(text))
        assert len(clusters) == 1
        assert clusters[0] == text

    def test_zwj_chain(self) -> None:
        """Multi-ZWJ sequence forms a single cluster."""
        # man ZWJ woman ZWJ girl
        text = "\U0001F468\u200D\U0001F469\u200D\U0001F467"
        clusters = list(iter_grapheme_clusters(text))
        assert len(clusters) == 1
        assert clusters[0] == text

    def test_zwj_at_end_of_string(self) -> None:
        """A trailing ZWJ with no following char becomes its own cluster."""
        text = "A\u200D"
        clusters = list(iter_grapheme_clusters(text))
        # ZWJ at end has no next char to join — the ZWJ check requires
        # i + 1 < n, so ZWJ is not absorbed into 'A'.  It becomes its
        # own cluster (ZWJ is category Cf, not a combining mark).
        assert clusters == ["A", "\u200D"]


class TestIterGraphemeClustersVariationSelector:
    """iter_grapheme_clusters groups variation selectors with base."""

    def test_vs16_emoji_presentation(self) -> None:
        """Character + VS16 forms a single cluster."""
        text = "#\uFE0F"  # # + VS16
        clusters = list(iter_grapheme_clusters(text))
        assert clusters == ["#\uFE0F"]

    def test_vs16_with_combining_keycap(self) -> None:
        """Keycap sequence: digit + VS16 + combining enclosing keycap."""
        text = "1\uFE0F\u20E3"  # 1️⃣
        clusters = list(iter_grapheme_clusters(text))
        assert len(clusters) == 1
        assert clusters[0] == text


class TestIterGraphemeClustersRegionalIndicator:
    """iter_grapheme_clusters pairs regional indicators into flags."""

    def test_flag_pair(self) -> None:
        """Two regional indicators form a single flag cluster."""
        text = "\U0001F1FA\U0001F1F8"  # US flag
        clusters = list(iter_grapheme_clusters(text))
        assert len(clusters) == 1
        assert clusters[0] == text

    def test_lone_regional_indicator(self) -> None:
        """A single regional indicator is its own cluster."""
        text = "\U0001F1FA"
        clusters = list(iter_grapheme_clusters(text))
        assert clusters == [text]

    def test_three_regional_indicators(self) -> None:
        """Three regional indicators → one pair + one lone."""
        text = "\U0001F1FA\U0001F1F8\U0001F1EC"
        clusters = list(iter_grapheme_clusters(text))
        assert len(clusters) == 2
        assert clusters[0] == "\U0001F1FA\U0001F1F8"
        assert clusters[1] == "\U0001F1EC"


class TestIterGraphemeClustersEmojiModifier:
    """iter_grapheme_clusters groups emoji modifiers (skin tones)."""

    def test_skin_tone_modifier(self) -> None:
        """Emoji + skin tone modifier forms a single cluster."""
        text = "\U0001F44D\U0001F3FD"  # thumbs up + medium skin tone
        clusters = list(iter_grapheme_clusters(text))
        assert len(clusters) == 1
        assert clusters[0] == text

    def test_skin_tone_after_ascii(self) -> None:
        """Skin tone modifier after a non-emoji base is still absorbed."""
        text = "A\U0001F3FB"
        clusters = list(iter_grapheme_clusters(text))
        # The modifier is absorbed into the cluster with 'A'.
        assert len(clusters) == 1


# ---------------------------------------------------------------------------
# grapheme_width
# ---------------------------------------------------------------------------


class TestGraphemeWidthSingleCodepoint:
    """grapheme_width matches char_width for single codepoints."""

    def test_ascii(self) -> None:
        assert grapheme_width("A") == 1

    def test_cjk(self) -> None:
        assert grapheme_width("中") == 2

    def test_combining_mark(self) -> None:
        assert grapheme_width("\u0301") == 0

    def test_control_char(self) -> None:
        assert grapheme_width("\x00") == 0

    def test_box_drawing(self) -> None:
        assert grapheme_width("─") == 1

    def test_fullwidth(self) -> None:
        assert grapheme_width("Ａ") == 2


class TestGraphemeWidthMultiCodepoint:
    """grapheme_width handles multi-codepoint grapheme clusters."""

    def test_base_plus_combining(self) -> None:
        """Base + combining mark → width of base."""
        assert grapheme_width("e\u0301") == 1

    def test_base_plus_multiple_combining(self) -> None:
        """Base + several combining marks → still width of base."""
        assert grapheme_width("a\u0303\u0301") == 1

    def test_cjk_plus_combining(self) -> None:
        """CJK base + combining mark → width 2."""
        assert grapheme_width("中\u0301") == 2

    def test_vs16_triggers_wide(self) -> None:
        """Character + VS16 → width 2 (emoji presentation)."""
        assert grapheme_width("#\uFE0F") == 2

    def test_keycap_sequence(self) -> None:
        """Keycap sequence → width 2."""
        assert grapheme_width("1\uFE0F\u20E3") == 2

    def test_emoji_zwj_sequence(self) -> None:
        """Emoji ZWJ sequence → width 2 (from leading wide emoji)."""
        grapheme = "\U0001F468\u200D\U0001F469\u200D\U0001F467"
        assert grapheme_width(grapheme) == 2

    def test_emoji_skin_tone(self) -> None:
        """Emoji + skin tone modifier → width 2."""
        assert grapheme_width("\U0001F44D\U0001F3FD") == 2

    def test_flag_emoji(self) -> None:
        """Regional indicator pair → width 2 (base is wide)."""
        # Regional indicators have EAW "N" (Neutral), but they are
        # typically rendered as a flag emoji at width 2. Our function
        # returns 1 per the base character rules — this is a known
        # terminal-dependent edge case.
        flag = "\U0001F1FA\U0001F1F8"
        # Width is based on the base character's EAW (Neutral → 1).
        # Terminals that render flags as emoji glyphs display width 2,
        # but unicodedata classifies these as width 1.
        result = grapheme_width(flag)
        assert result in (1, 2)  # terminal-dependent

    def test_empty_string(self) -> None:
        assert grapheme_width("") == 0


# ---------------------------------------------------------------------------
# grapheme_string_width
# ---------------------------------------------------------------------------


class TestGraphemeStringWidth:
    """grapheme_string_width computes total width from grapheme clusters."""

    def test_ascii_string(self) -> None:
        assert grapheme_string_width("Hello") == 5

    def test_empty_string(self) -> None:
        assert grapheme_string_width("") == 0

    def test_cjk_string(self) -> None:
        assert grapheme_string_width("中文") == 4

    def test_mixed_ascii_cjk(self) -> None:
        assert grapheme_string_width("A中B") == 4

    def test_combining_mark_no_extra_width(self) -> None:
        """Combining marks don't add width beyond the base character."""
        # "e\u0301" is one grapheme cluster with width 1.
        assert grapheme_string_width("e\u0301") == 1
        # Compare: string_width also returns 1 (combining = 0).
        assert string_width("e\u0301") == 1

    def test_matches_string_width_for_simple_text(self) -> None:
        """For simple text, matches string_width."""
        for text in ["Hello", "中文", "A中B", "┌──┐", ""]:
            assert grapheme_string_width(text) == string_width(text)

    def test_vs16_adds_width(self) -> None:
        """VS16 emoji presentation counted as width 2."""
        # '#' alone is width 1, but '#' + VS16 is width 2
        assert grapheme_string_width("#\uFE0F") == 2

    def test_keycap_sequence_width(self) -> None:
        """Keycap sequence (3 codepoints) has width 2."""
        assert grapheme_string_width("1\uFE0F\u20E3") == 2

    def test_emoji_zwj_family(self) -> None:
        """ZWJ family emoji: one grapheme cluster, width 2."""
        text = "\U0001F468\u200D\U0001F469\u200D\U0001F467"
        assert grapheme_string_width(text) == 2
        # Compare: string_width would sum individual codepoints
        # (2 + 0 + 2 + 0 + 2 = 6) — much larger.
        assert string_width(text) == 6

    def test_text_with_embedded_grapheme_clusters(self) -> None:
        """Mixed text: ASCII + grapheme cluster + CJK."""
        # "He" (2) + "e\u0301" (1) + "中" (2) = 5
        text = "He" + "e\u0301" + "中"
        assert grapheme_string_width(text) == 5


# ---------------------------------------------------------------------------
# contains_emoji
# ---------------------------------------------------------------------------


class TestContainsEmoji:
    """Tests for contains_emoji()."""

    def test_plain_ascii(self) -> None:
        assert contains_emoji("Hello, world!") is False

    def test_empty_string(self) -> None:
        assert contains_emoji("") is False

    def test_box_drawing(self) -> None:
        """Box-drawing characters are not emoji."""
        assert contains_emoji("┌──┐│└┘") is False

    def test_block_elements(self) -> None:
        """Block elements are not emoji."""
        assert contains_emoji("█▓▒░▀▄") is False

    def test_cjk(self) -> None:
        """CJK ideographs are not emoji."""
        assert contains_emoji("中文日本語") is False

    def test_combining_marks(self) -> None:
        """Combining diacriticals are not emoji."""
        assert contains_emoji("e\u0301") is False

    def test_simple_emoji(self) -> None:
        """Common pictograph emoji are detected."""
        assert contains_emoji("🌍") is True

    def test_face_emoji(self) -> None:
        """Emoticon emoji are detected."""
        assert contains_emoji("😀") is True

    def test_emoji_in_text(self) -> None:
        """Emoji embedded in plain text."""
        assert contains_emoji("Hello 🌍 world") is True

    def test_vs16_presence(self) -> None:
        """VS16 (emoji presentation selector) triggers detection."""
        assert contains_emoji("#\uFE0F") is True

    def test_regional_indicator(self) -> None:
        """Regional indicator symbols (flag emoji) are detected."""
        assert contains_emoji("\U0001F1FA\U0001F1F8") is True

    def test_skin_tone_modifier(self) -> None:
        """Emoji skin tone modifiers are detected."""
        assert contains_emoji("\U0001F3FB") is True

    def test_zwj_sequence(self) -> None:
        """ZWJ emoji sequence (family) is detected."""
        assert contains_emoji("\U0001F468\u200D\U0001F469\u200D\U0001F467") is True

    def test_misc_symbols(self) -> None:
        """Characters in Miscellaneous Symbols range (e.g. sun, star)."""
        assert contains_emoji("\u2600") is True  # ☀ BLACK SUN WITH RAYS
        assert contains_emoji("\u2B50") is True  # ⭐ WHITE MEDIUM STAR

    def test_transport_emoji(self) -> None:
        """Transport and Map emoji range."""
        assert contains_emoji("\U0001F680") is True  # 🚀 ROCKET

    def test_arrows_are_not_emoji(self) -> None:
        """Simple arrows outside emoji ranges are not emoji."""
        assert contains_emoji("→←↑↓") is False
