"""Tests for wyby.sprite.from_text — ASCII art to entities factory."""

from __future__ import annotations

import pytest
from rich.style import Style

from wyby.sprite import Sprite, from_text


# ---------------------------------------------------------------------------
# Basic functionality
# ---------------------------------------------------------------------------


class TestFromTextBasic:
    """Core from_text behaviour with simple inputs."""

    def test_single_char(self) -> None:
        entities = from_text("@")
        assert len(entities) == 1
        e = entities[0]
        assert e.x == 0
        assert e.y == 0
        sprite = e.get_component(Sprite)
        assert sprite is not None
        assert sprite.char == "@"

    def test_single_line(self) -> None:
        entities = from_text("ABC")
        assert len(entities) == 3
        chars = [(e.x, e.y, e.get_component(Sprite).char) for e in entities]
        assert chars == [(0, 0, "A"), (1, 0, "B"), (2, 0, "C")]

    def test_multi_line(self) -> None:
        text = "AB\nCD"
        entities = from_text(text)
        assert len(entities) == 4
        positions = [(e.x, e.y) for e in entities]
        assert positions == [(0, 0), (1, 0), (0, 1), (1, 1)]

    def test_ascii_art_box(self) -> None:
        text = "###\n# #\n###"
        entities = from_text(text)
        # 3+2+3 = 8 chars (space in middle is skipped)
        assert len(entities) == 8
        # All should be '#'
        for e in entities:
            assert e.get_component(Sprite).char == "#"

    def test_entities_are_alive(self) -> None:
        entities = from_text("AB")
        for e in entities:
            assert e.alive is True

    def test_each_entity_has_unique_id(self) -> None:
        entities = from_text("ABC")
        ids = [e.id for e in entities]
        assert len(set(ids)) == 3  # all unique


# ---------------------------------------------------------------------------
# Whitespace handling
# ---------------------------------------------------------------------------


class TestFromTextWhitespace:
    """Whitespace skipping and inclusion."""

    def test_spaces_skipped_by_default(self) -> None:
        entities = from_text("A B")
        assert len(entities) == 2
        assert entities[0].x == 0
        assert entities[1].x == 2

    def test_spaces_included_when_skip_false(self) -> None:
        entities = from_text("A B", skip_whitespace=False)
        assert len(entities) == 3
        chars = [e.get_component(Sprite).char for e in entities]
        assert chars == ["A", " ", "B"]

    def test_leading_spaces_affect_position(self) -> None:
        entities = from_text("  X")
        assert len(entities) == 1
        assert entities[0].x == 2

    def test_empty_lines_produce_no_entities(self) -> None:
        text = "A\n\nB"
        entities = from_text(text)
        assert len(entities) == 2
        # A at row 0, B at row 2 (empty line is row 1)
        assert entities[0].y == 0
        assert entities[1].y == 2

    def test_trailing_newline(self) -> None:
        """Trailing newline creates an empty last line — no entities."""
        entities = from_text("AB\n")
        assert len(entities) == 2


# ---------------------------------------------------------------------------
# Origin offset
# ---------------------------------------------------------------------------


class TestFromTextOrigin:
    """Origin offset shifts all entity positions."""

    def test_origin_x(self) -> None:
        entities = from_text("AB", origin_x=5)
        assert entities[0].x == 5
        assert entities[1].x == 6

    def test_origin_y(self) -> None:
        entities = from_text("A\nB", origin_y=10)
        assert entities[0].y == 10
        assert entities[1].y == 11

    def test_origin_both(self) -> None:
        entities = from_text("X", origin_x=3, origin_y=7)
        assert entities[0].x == 3
        assert entities[0].y == 7

    def test_negative_origin(self) -> None:
        entities = from_text("X", origin_x=-2, origin_y=-1)
        assert entities[0].x == -2
        assert entities[0].y == -1


# ---------------------------------------------------------------------------
# Style
# ---------------------------------------------------------------------------


class TestFromTextStyle:
    """Style parameter applies to all sprites."""

    def test_default_style_is_null(self) -> None:
        entities = from_text("A")
        sprite = entities[0].get_component(Sprite)
        assert sprite.style == Style.null()

    def test_custom_style(self) -> None:
        style = Style(color="red", bold=True)
        entities = from_text("AB", style=style)
        for e in entities:
            sprite = e.get_component(Sprite)
            assert sprite.style.color.name == "red"
            assert sprite.style.bold is True

    def test_all_sprites_share_same_style_object(self) -> None:
        style = Style(color="blue")
        entities = from_text("AB", style=style)
        s0 = entities[0].get_component(Sprite)
        s1 = entities[1].get_component(Sprite)
        # Sprite constructor creates Style.null() for None, but passes
        # through the given style object.
        assert s0.style is style
        assert s1.style is style


# ---------------------------------------------------------------------------
# Wide characters (CJK)
# ---------------------------------------------------------------------------


class TestFromTextWideChars:
    """Wide characters advance by 2 columns."""

    def test_wide_char_advances_by_two(self) -> None:
        # 世 is a CJK ideograph — width 2
        entities = from_text("\u4e16A")
        assert len(entities) == 2
        assert entities[0].x == 0
        assert entities[0].get_component(Sprite).char == "\u4e16"
        assert entities[1].x == 2  # skipped col 1
        assert entities[1].get_component(Sprite).char == "A"

    def test_multiple_wide_chars(self) -> None:
        entities = from_text("\u4e16\u754c")  # 世界
        assert len(entities) == 2
        assert entities[0].x == 0
        assert entities[1].x == 2

    def test_wide_char_with_origin(self) -> None:
        entities = from_text("\u4e16A", origin_x=10)
        assert entities[0].x == 10
        assert entities[1].x == 12


# ---------------------------------------------------------------------------
# Zero-width characters
# ---------------------------------------------------------------------------


class TestFromTextZeroWidth:
    """Zero-width characters are silently skipped."""

    def test_combining_mark_skipped(self) -> None:
        # e + combining grave accent — the combining mark is skipped
        entities = from_text("e\u0300X")
        assert len(entities) == 2
        assert entities[0].get_component(Sprite).char == "e"
        assert entities[1].get_component(Sprite).char == "X"
        # X should be at col 1 (combining mark has width 0)
        assert entities[1].x == 1


# ---------------------------------------------------------------------------
# Cross-platform newlines
# ---------------------------------------------------------------------------


class TestFromTextNewlines:
    """Windows and old Mac line endings are handled."""

    def test_crlf_treated_as_single_newline(self) -> None:
        entities = from_text("A\r\nB")
        assert len(entities) == 2
        assert entities[0].y == 0
        assert entities[1].y == 1

    def test_bare_cr_stripped(self) -> None:
        entities = from_text("A\rB")
        # \r is stripped, so "AB" on one line
        assert len(entities) == 2
        assert entities[0].y == 0
        assert entities[1].y == 0


# ---------------------------------------------------------------------------
# Validation — errors
# ---------------------------------------------------------------------------


class TestFromTextValidation:
    """Input validation and error handling."""

    def test_rejects_non_string(self) -> None:
        with pytest.raises(TypeError, match="text must be a string"):
            from_text(42)  # type: ignore[arg-type]

    def test_rejects_none(self) -> None:
        with pytest.raises(TypeError, match="text must be a string"):
            from_text(None)  # type: ignore[arg-type]

    def test_rejects_empty_string(self) -> None:
        with pytest.raises(ValueError, match="must not be empty"):
            from_text("")

    def test_rejects_whitespace_only(self) -> None:
        with pytest.raises(ValueError, match="must not be empty"):
            from_text("   \n  \n  ")

    def test_rejects_non_int_origin_x(self) -> None:
        with pytest.raises(TypeError, match="origin_x must be an int"):
            from_text("A", origin_x=1.5)  # type: ignore[arg-type]

    def test_rejects_non_int_origin_y(self) -> None:
        with pytest.raises(TypeError, match="origin_y must be an int"):
            from_text("A", origin_y="0")  # type: ignore[arg-type]

    def test_rejects_bool_origin_x(self) -> None:
        with pytest.raises(TypeError, match="origin_x must be an int"):
            from_text("A", origin_x=True)  # type: ignore[arg-type]

    def test_rejects_bool_origin_y(self) -> None:
        with pytest.raises(TypeError, match="origin_y must be an int"):
            from_text("A", origin_y=False)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Ordering
# ---------------------------------------------------------------------------


class TestFromTextOrdering:
    """Entities are ordered top-to-bottom, left-to-right."""

    def test_order_is_row_major(self) -> None:
        entities = from_text("AB\nCD")
        positions = [(e.x, e.y) for e in entities]
        assert positions == [(0, 0), (1, 0), (0, 1), (1, 1)]


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestFromTextEdgeCases:
    """Edge cases and corner scenarios."""

    def test_single_newline_only_rejected(self) -> None:
        """A string of only newlines is whitespace-only."""
        with pytest.raises(ValueError, match="must not be empty"):
            from_text("\n\n\n")

    def test_mixed_line_lengths(self) -> None:
        text = "A\nBCD\nEF"
        entities = from_text(text)
        assert len(entities) == 6
        # Row 0: A at (0,0)
        # Row 1: B at (0,1), C at (1,1), D at (2,1)
        # Row 2: E at (0,2), F at (1,2)
        positions = [(e.x, e.y) for e in entities]
        assert positions == [
            (0, 0),
            (0, 1), (1, 1), (2, 1),
            (0, 2), (1, 2),
        ]

    def test_whitespace_only_line_skip_true(self) -> None:
        """A line of spaces with skip_whitespace=True creates no entities."""
        entities = from_text("A\n   \nB")
        assert len(entities) == 2
        assert entities[0].y == 0
        assert entities[1].y == 2

    def test_returns_empty_list_for_all_spaces_skip_true(self) -> None:
        """Text that is not blank but only spaces (after \\r strip)
        raises ValueError since it's whitespace-only."""
        with pytest.raises(ValueError, match="must not be empty"):
            from_text("   ")

    def test_special_chars(self) -> None:
        """Box-drawing and block elements work fine."""
        entities = from_text("\u2588\u2591")  # █░
        assert len(entities) == 2
        assert entities[0].get_component(Sprite).char == "\u2588"
        assert entities[1].get_component(Sprite).char == "\u2591"


# ---------------------------------------------------------------------------
# Import from package root
# ---------------------------------------------------------------------------


class TestFromTextImport:
    """from_text is accessible from the wyby package root."""

    def test_import_from_wyby(self) -> None:
        from wyby import from_text as ft
        assert ft is from_text
