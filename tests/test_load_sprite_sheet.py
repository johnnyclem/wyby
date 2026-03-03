"""Tests for wyby.sprite.load_sprite_sheet — sprite sheet extraction."""

from __future__ import annotations

import pytest
from rich.style import Style

from wyby.sprite import Sprite, load_sprite_sheet


# ---------------------------------------------------------------------------
# Basic functionality
# ---------------------------------------------------------------------------


class TestLoadSpriteSheetBasic:
    """Core load_sprite_sheet behaviour with simple inputs."""

    def test_single_frame(self) -> None:
        """A sheet with exactly one frame."""
        text = "###\n# #\n###"
        frames = load_sprite_sheet(text, frame_width=3, frame_height=3)
        assert len(frames) == 1
        assert "0" in frames
        # 8 non-space chars
        assert len(frames["0"]) == 8

    def test_two_frames_side_by_side(self) -> None:
        """Two 3×3 frames arranged horizontally."""
        text = "###.@.\n# #.@.\n###.@."
        frames = load_sprite_sheet(text, frame_width=3, frame_height=3)
        assert len(frames) == 2
        assert "0" in frames
        assert "1" in frames

    def test_two_frames_stacked(self) -> None:
        """Two 3×2 frames arranged vertically."""
        text = "ABC\nDEF\nGHI\nJKL"
        frames = load_sprite_sheet(text, frame_width=3, frame_height=2)
        assert len(frames) == 2
        assert "0" in frames
        assert "1" in frames
        # Frame 0: ABC / DEF
        chars_0 = [e.get_component(Sprite).char for e in frames["0"]]
        assert chars_0 == ["A", "B", "C", "D", "E", "F"]
        # Frame 1: GHI / JKL
        chars_1 = [e.get_component(Sprite).char for e in frames["1"]]
        assert chars_1 == ["G", "H", "I", "J", "K", "L"]

    def test_four_frames_grid(self) -> None:
        """2×2 grid of 2×2 frames."""
        text = "AABB\nAABB\nCCDD\nCCDD"
        frames = load_sprite_sheet(text, frame_width=2, frame_height=2)
        assert len(frames) == 4
        assert set(frames.keys()) == {"0", "1", "2", "3"}

    def test_frame_entity_positions_are_relative(self) -> None:
        """Entity positions within a frame are relative to the frame's top-left."""
        text = "AABB\nCCDD"
        frames = load_sprite_sheet(text, frame_width=2, frame_height=2)
        # Frame "1" is the right half (cols 2-3).
        # Entities should be at (0,0), (1,0), (0,1), (1,1).
        positions = [(e.x, e.y) for e in frames["1"]]
        assert positions == [(0, 0), (1, 0), (0, 1), (1, 1)]


# ---------------------------------------------------------------------------
# Names
# ---------------------------------------------------------------------------


class TestLoadSpriteSheetNames:
    """Custom frame naming."""

    def test_custom_names(self) -> None:
        text = "AABB\nCCDD"
        frames = load_sprite_sheet(
            text, frame_width=2, frame_height=2,
            names=["idle", "walk"],
        )
        assert "idle" in frames
        assert "walk" in frames

    def test_names_wrong_length_raises(self) -> None:
        text = "AABB\nCCDD"
        with pytest.raises(ValueError, match="names length"):
            load_sprite_sheet(
                text, frame_width=2, frame_height=2,
                names=["only_one"],
            )

    def test_default_names_are_string_indices(self) -> None:
        text = "ABCD"
        frames = load_sprite_sheet(text, frame_width=2, frame_height=1)
        assert set(frames.keys()) == {"0", "1"}


# ---------------------------------------------------------------------------
# Origin offset
# ---------------------------------------------------------------------------


class TestLoadSpriteSheetOrigin:
    """Origin offsets shift entity positions."""

    def test_origin_x(self) -> None:
        text = "AB"
        frames = load_sprite_sheet(text, frame_width=2, frame_height=1, origin_x=10)
        positions = [(e.x, e.y) for e in frames["0"]]
        assert positions == [(10, 0), (11, 0)]

    def test_origin_y(self) -> None:
        text = "A\nB"
        frames = load_sprite_sheet(text, frame_width=1, frame_height=2, origin_y=5)
        positions = [(e.x, e.y) for e in frames["0"]]
        assert positions == [(0, 5), (0, 6)]

    def test_origin_both(self) -> None:
        text = "X"
        frames = load_sprite_sheet(
            text, frame_width=1, frame_height=1,
            origin_x=3, origin_y=7,
        )
        e = frames["0"][0]
        assert e.x == 3
        assert e.y == 7


# ---------------------------------------------------------------------------
# Style
# ---------------------------------------------------------------------------


class TestLoadSpriteSheetStyle:
    """Style parameter applies to all sprites in all frames."""

    def test_default_style_is_null(self) -> None:
        frames = load_sprite_sheet("AB", frame_width=1, frame_height=1)
        sprite = frames["0"][0].get_component(Sprite)
        assert sprite.style == Style.null()

    def test_custom_style(self) -> None:
        style = Style(color="red", bold=True)
        frames = load_sprite_sheet("AB", frame_width=1, frame_height=1, style=style)
        for name in frames:
            for e in frames[name]:
                sprite = e.get_component(Sprite)
                assert sprite.style is style


# ---------------------------------------------------------------------------
# Whitespace handling
# ---------------------------------------------------------------------------


class TestLoadSpriteSheetWhitespace:
    """Whitespace skipping."""

    def test_spaces_skipped_by_default(self) -> None:
        text = "A \n B"
        frames = load_sprite_sheet(text, frame_width=2, frame_height=2)
        assert len(frames["0"]) == 2  # A and B, spaces skipped

    def test_spaces_included_when_skip_false(self) -> None:
        text = "A \n B"
        frames = load_sprite_sheet(
            text, frame_width=2, frame_height=2, skip_whitespace=False,
        )
        assert len(frames["0"]) == 4  # All 4 cells


# ---------------------------------------------------------------------------
# Truncation (frames that don't tile evenly)
# ---------------------------------------------------------------------------


class TestLoadSpriteSheetTruncation:
    """Extra columns/rows that don't fill a frame are ignored."""

    def test_extra_columns_ignored(self) -> None:
        """5-char wide sheet with frame_width=2 → 2 frames, last column ignored."""
        text = "ABCDE"
        frames = load_sprite_sheet(text, frame_width=2, frame_height=1)
        assert len(frames) == 2
        chars_0 = [e.get_component(Sprite).char for e in frames["0"]]
        chars_1 = [e.get_component(Sprite).char for e in frames["1"]]
        assert chars_0 == ["A", "B"]
        assert chars_1 == ["C", "D"]
        # "E" is in the truncated remainder

    def test_extra_rows_ignored(self) -> None:
        """3-row sheet with frame_height=2 → 1 frame row, last row ignored."""
        text = "A\nB\nC"
        frames = load_sprite_sheet(text, frame_width=1, frame_height=2)
        assert len(frames) == 1
        chars = [e.get_component(Sprite).char for e in frames["0"]]
        assert chars == ["A", "B"]

    def test_no_frames_when_too_small(self) -> None:
        """Sheet smaller than one frame → zero frames."""
        text = "AB"
        frames = load_sprite_sheet(text, frame_width=5, frame_height=1)
        assert len(frames) == 0


# ---------------------------------------------------------------------------
# Short lines (padding)
# ---------------------------------------------------------------------------


class TestLoadSpriteSheetShortLines:
    """Short lines are treated as padded with spaces."""

    def test_short_line_in_frame(self) -> None:
        """A line shorter than the sheet width produces fewer entities."""
        text = "AABB\nAA"
        frames = load_sprite_sheet(text, frame_width=2, frame_height=2)
        # Frame "0" (left): AA / AA → 4 entities
        assert len(frames["0"]) == 4
        # Frame "1" (right): BB / (empty) → 2 entities
        assert len(frames["1"]) == 2


# ---------------------------------------------------------------------------
# Wide characters (CJK)
# ---------------------------------------------------------------------------


class TestLoadSpriteSheetWideChars:
    """Wide characters in sprite sheets."""

    def test_wide_char_in_frame(self) -> None:
        # 世 is width 2, A is width 1
        # "世A" occupies columns 0-1 (世) and column 2 (A) = 3 cols
        text = "\u4e16A"
        frames = load_sprite_sheet(text, frame_width=3, frame_height=1)
        assert len(frames) == 1
        assert len(frames["0"]) == 2
        chars = [e.get_component(Sprite).char for e in frames["0"]]
        assert chars == ["\u4e16", "A"]
        # Wide char at x=0, A at x=2 (relative to frame)
        assert frames["0"][0].x == 0
        assert frames["0"][1].x == 2


# ---------------------------------------------------------------------------
# Cross-platform newlines
# ---------------------------------------------------------------------------


class TestLoadSpriteSheetNewlines:
    """Windows line endings handled."""

    def test_crlf(self) -> None:
        text = "AB\r\nCD"
        frames = load_sprite_sheet(text, frame_width=2, frame_height=2)
        assert len(frames) == 1
        assert len(frames["0"]) == 4


# ---------------------------------------------------------------------------
# Validation — type errors
# ---------------------------------------------------------------------------


class TestLoadSpriteSheetTypeErrors:
    """Type validation."""

    def test_rejects_non_string_text(self) -> None:
        with pytest.raises(TypeError, match="text must be a string"):
            load_sprite_sheet(42, frame_width=1, frame_height=1)  # type: ignore[arg-type]

    def test_rejects_non_int_frame_width(self) -> None:
        with pytest.raises(TypeError, match="frame_width must be an int"):
            load_sprite_sheet("A", frame_width=1.5, frame_height=1)  # type: ignore[arg-type]

    def test_rejects_non_int_frame_height(self) -> None:
        with pytest.raises(TypeError, match="frame_height must be an int"):
            load_sprite_sheet("A", frame_width=1, frame_height=1.5)  # type: ignore[arg-type]

    def test_rejects_bool_frame_width(self) -> None:
        with pytest.raises(TypeError, match="frame_width must be an int"):
            load_sprite_sheet("A", frame_width=True, frame_height=1)  # type: ignore[arg-type]

    def test_rejects_bool_frame_height(self) -> None:
        with pytest.raises(TypeError, match="frame_height must be an int"):
            load_sprite_sheet("A", frame_width=1, frame_height=False)  # type: ignore[arg-type]

    def test_rejects_non_int_origin_x(self) -> None:
        with pytest.raises(TypeError, match="origin_x must be an int"):
            load_sprite_sheet("A", frame_width=1, frame_height=1, origin_x=1.0)  # type: ignore[arg-type]

    def test_rejects_non_int_origin_y(self) -> None:
        with pytest.raises(TypeError, match="origin_y must be an int"):
            load_sprite_sheet("A", frame_width=1, frame_height=1, origin_y="0")  # type: ignore[arg-type]

    def test_rejects_bool_origin_x(self) -> None:
        with pytest.raises(TypeError, match="origin_x must be an int"):
            load_sprite_sheet("A", frame_width=1, frame_height=1, origin_x=True)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Validation — value errors
# ---------------------------------------------------------------------------


class TestLoadSpriteSheetValueErrors:
    """Value validation."""

    def test_rejects_empty_text(self) -> None:
        with pytest.raises(ValueError, match="must not be empty"):
            load_sprite_sheet("", frame_width=1, frame_height=1)

    def test_rejects_zero_frame_width(self) -> None:
        with pytest.raises(ValueError, match="frame_width must be >= 1"):
            load_sprite_sheet("A", frame_width=0, frame_height=1)

    def test_rejects_negative_frame_width(self) -> None:
        with pytest.raises(ValueError, match="frame_width must be >= 1"):
            load_sprite_sheet("A", frame_width=-1, frame_height=1)

    def test_rejects_zero_frame_height(self) -> None:
        with pytest.raises(ValueError, match="frame_height must be >= 1"):
            load_sprite_sheet("A", frame_width=1, frame_height=0)

    def test_rejects_negative_frame_height(self) -> None:
        with pytest.raises(ValueError, match="frame_height must be >= 1"):
            load_sprite_sheet("A", frame_width=1, frame_height=-1)


# ---------------------------------------------------------------------------
# Import from package root
# ---------------------------------------------------------------------------


class TestLoadSpriteSheetImport:
    """load_sprite_sheet is accessible from the wyby package root."""

    def test_import_from_wyby(self) -> None:
        from wyby import load_sprite_sheet as lss
        assert lss is load_sprite_sheet
