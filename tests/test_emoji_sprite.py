"""Tests for emoji as sprites with variation selectors.

Covers the full pipeline: Sprite construction, Cell storage, CellBuffer
rendering, from_text parsing, and AnimationFrame support for emoji
grapheme clusters (e.g. base emoji + VS16).

Caveats tested and documented:
    - VS16 (U+FE0F) requests emoji presentation at width 2.
    - VS15 (U+FE0E) requests text presentation at width 1.
    - Emoji width is terminal-dependent — the width reported by
      grapheme_width may not match what a given terminal renders.
    - ZWJ sequences, skin tone modifiers, and flag emoji are accepted
      as single grapheme clusters.
    - Multi-cluster strings are still rejected.
"""

from __future__ import annotations

import pytest
from rich.style import Style

from wyby.animation import AnimationFrame
from wyby.entity import Entity
from wyby.grid import Cell, CellBuffer, _WIDE_CHAR_FILLER
from wyby.sprite import Sprite, from_text
from wyby.unicode import (
    grapheme_width,
    is_single_grapheme,
    iter_grapheme_clusters,
)


# ---------------------------------------------------------------------------
# Common emoji test data
# ---------------------------------------------------------------------------

# Heart emoji with VS16 — requests emoji presentation (width 2).
HEART_EMOJI = "\u2764\uFE0F"  # ❤️

# Sword emoji with VS16 — requests emoji presentation (width 2).
SWORDS_EMOJI = "\u2694\uFE0F"  # ⚔️

# Star with VS16 — requests emoji presentation (width 2).
STAR_EMOJI = "\u2B50"  # ⭐ (already emoji-presentation by default)

# Simple single-codepoint emoji (no variation selector).
ROCKET_EMOJI = "\U0001F680"  # 🚀

# Thumbs up with skin tone modifier.
THUMBS_MEDIUM = "\U0001F44D\U0001F3FD"  # 👍🏽

# Family ZWJ sequence.
FAMILY_EMOJI = "\U0001F468\u200D\U0001F469\u200D\U0001F467"

# Flag emoji (regional indicator pair).
US_FLAG = "\U0001F1FA\U0001F1F8"  # 🇺🇸

# Heart with VS15 (text presentation) — should be width 1.
HEART_TEXT = "\u2764\uFE0E"

# Keycap sequence: digit + VS16 + combining enclosing keycap.
KEYCAP_ONE = "1\uFE0F\u20E3"  # 1️⃣


# ---------------------------------------------------------------------------
# is_single_grapheme
# ---------------------------------------------------------------------------


class TestIsSingleGrapheme:
    """is_single_grapheme correctly identifies single grapheme clusters."""

    def test_single_ascii(self) -> None:
        assert is_single_grapheme("A") is True

    def test_empty_string(self) -> None:
        assert is_single_grapheme("") is False

    def test_multi_char_ascii(self) -> None:
        assert is_single_grapheme("AB") is False

    def test_emoji_with_vs16(self) -> None:
        assert is_single_grapheme(HEART_EMOJI) is True

    def test_emoji_with_vs15(self) -> None:
        assert is_single_grapheme(HEART_TEXT) is True

    def test_emoji_with_skin_tone(self) -> None:
        assert is_single_grapheme(THUMBS_MEDIUM) is True

    def test_zwj_sequence(self) -> None:
        assert is_single_grapheme(FAMILY_EMOJI) is True

    def test_flag_emoji(self) -> None:
        assert is_single_grapheme(US_FLAG) is True

    def test_keycap_sequence(self) -> None:
        assert is_single_grapheme(KEYCAP_ONE) is True

    def test_two_separate_emoji(self) -> None:
        """Two unrelated emoji are not a single grapheme cluster."""
        assert is_single_grapheme("\U0001F680\U0001F525") is False

    def test_base_plus_combining(self) -> None:
        assert is_single_grapheme("e\u0301") is True


# ---------------------------------------------------------------------------
# Sprite with emoji
# ---------------------------------------------------------------------------


class TestSpriteEmojiConstruction:
    """Sprite accepts emoji with variation selectors."""

    def test_emoji_with_vs16(self) -> None:
        """Heart + VS16 is accepted as a sprite char."""
        s = Sprite(HEART_EMOJI)
        assert s.char == HEART_EMOJI

    def test_swords_with_vs16(self) -> None:
        s = Sprite(SWORDS_EMOJI)
        assert s.char == SWORDS_EMOJI

    def test_single_codepoint_emoji(self) -> None:
        """Single-codepoint emoji (no VS) is accepted."""
        s = Sprite(ROCKET_EMOJI)
        assert s.char == ROCKET_EMOJI

    def test_emoji_with_skin_tone(self) -> None:
        s = Sprite(THUMBS_MEDIUM)
        assert s.char == THUMBS_MEDIUM

    def test_zwj_sequence(self) -> None:
        s = Sprite(FAMILY_EMOJI)
        assert s.char == FAMILY_EMOJI

    def test_flag_emoji(self) -> None:
        s = Sprite(US_FLAG)
        assert s.char == US_FLAG

    def test_keycap_sequence(self) -> None:
        s = Sprite(KEYCAP_ONE)
        assert s.char == KEYCAP_ONE

    def test_emoji_with_vs15(self) -> None:
        """VS15 (text presentation) is accepted — width 1."""
        s = Sprite(HEART_TEXT)
        assert s.char == HEART_TEXT

    def test_emoji_with_style(self) -> None:
        """Emoji sprite accepts a Rich Style."""
        style = Style(bgcolor="black")
        s = Sprite(HEART_EMOJI, style)
        assert s.char == HEART_EMOJI
        assert s.style is style

    def test_rejects_two_separate_emoji(self) -> None:
        """Two unrelated emoji are not a single grapheme cluster."""
        with pytest.raises(ValueError, match="single grapheme cluster"):
            Sprite("\U0001F680\U0001F525")

    def test_rejects_empty(self) -> None:
        with pytest.raises(ValueError, match="must not be empty"):
            Sprite("")


class TestSpriteEmojiCharSetter:
    """Sprite.char setter accepts emoji grapheme clusters."""

    def test_set_emoji_with_vs16(self) -> None:
        s = Sprite()
        s.char = HEART_EMOJI
        assert s.char == HEART_EMOJI

    def test_set_single_codepoint_emoji(self) -> None:
        s = Sprite()
        s.char = ROCKET_EMOJI
        assert s.char == ROCKET_EMOJI

    def test_set_rejects_multi_cluster(self) -> None:
        s = Sprite()
        with pytest.raises(ValueError, match="single grapheme cluster"):
            s.char = "\U0001F680\U0001F525"

    def test_set_rejects_empty(self) -> None:
        s = Sprite()
        with pytest.raises(ValueError, match="must not be empty"):
            s.char = ""


class TestSpriteEmojiEntityIntegration:
    """Emoji sprites integrate with entities."""

    def test_attach_emoji_sprite(self) -> None:
        e = Entity(entity_id=42)
        s = Sprite(HEART_EMOJI)
        e.add_component(s)
        assert e.get_component(Sprite).char == HEART_EMOJI

    def test_repr_with_emoji(self) -> None:
        s = Sprite(HEART_EMOJI)
        r = repr(s)
        assert "Sprite(char=" in r
        assert "detached" in r


# ---------------------------------------------------------------------------
# Cell with emoji
# ---------------------------------------------------------------------------


class TestCellEmoji:
    """Cell accepts emoji grapheme clusters."""

    def test_emoji_with_vs16(self) -> None:
        cell = Cell(char=HEART_EMOJI)
        assert cell.char == HEART_EMOJI

    def test_single_codepoint_emoji(self) -> None:
        cell = Cell(char=ROCKET_EMOJI)
        assert cell.char == ROCKET_EMOJI

    def test_emoji_with_style(self) -> None:
        cell = Cell(char=HEART_EMOJI, fg="red", bg="black")
        assert cell.char == HEART_EMOJI
        assert cell.fg == "red"

    def test_rejects_multi_cluster(self) -> None:
        with pytest.raises(ValueError, match="single grapheme cluster"):
            Cell(char="\U0001F680\U0001F525")

    def test_rejects_empty(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            Cell(char="")

    def test_single_char_still_works(self) -> None:
        """Regular single characters still work (regression check)."""
        cell = Cell(char="@")
        assert cell.char == "@"


# ---------------------------------------------------------------------------
# CellBuffer.put_text with emoji
# ---------------------------------------------------------------------------


class TestCellBufferPutTextEmoji:
    """put_text handles emoji grapheme clusters correctly."""

    def test_emoji_with_vs16_occupies_two_columns(self) -> None:
        """Heart + VS16 should occupy 2 columns (emoji presentation).

        Caveat: Actual terminal rendering may differ — some terminals
        render this at width 1 instead of 2.  The CellBuffer uses
        grapheme_width() which reports width 2 for VS16 sequences.
        """
        buf = CellBuffer(10, 1)
        buf.put_text(0, 0, HEART_EMOJI)
        cell = buf.get(0, 0)
        assert cell is not None
        assert cell.char == HEART_EMOJI
        # Filler in the trailing column.
        filler = buf.get(1, 0)
        assert filler is not None
        assert filler.char == _WIDE_CHAR_FILLER

    def test_emoji_with_vs15_occupies_one_column(self) -> None:
        """Heart + VS15 (text presentation) should occupy 1 column.

        Caveat: VS15 requests text presentation, which is typically
        width 1.  grapheme_width returns 1 because the cluster does
        not contain VS16.
        """
        buf = CellBuffer(10, 1)
        buf.put_text(0, 0, HEART_TEXT)
        cell = buf.get(0, 0)
        assert cell is not None
        assert cell.char == HEART_TEXT
        # No filler — width 1.
        next_cell = buf.get(1, 0)
        assert next_cell is not None
        assert next_cell.char != _WIDE_CHAR_FILLER

    def test_single_codepoint_emoji_width_2(self) -> None:
        """Single-codepoint emoji (e.g. 🚀) treated as width 2 per UAX #11.

        Caveat: UAX #11 classifies many single-codepoint emoji as Wide
        (EAW=W), so char_width returns 2.  Terminal rendering varies.
        """
        buf = CellBuffer(10, 1)
        buf.put_text(0, 0, ROCKET_EMOJI)
        cell = buf.get(0, 0)
        assert cell is not None
        assert cell.char == ROCKET_EMOJI
        filler = buf.get(1, 0)
        assert filler is not None
        assert filler.char == _WIDE_CHAR_FILLER

    def test_mixed_ascii_and_emoji(self) -> None:
        """ASCII and emoji mixed in one put_text call."""
        buf = CellBuffer(10, 1)
        # "A" (width 1) + heart+VS16 (width 2) + "B" (width 1) = 4 cols
        buf.put_text(0, 0, "A" + HEART_EMOJI + "B")
        assert buf.get(0, 0).char == "A"  # type: ignore[union-attr]
        assert buf.get(1, 0).char == HEART_EMOJI  # type: ignore[union-attr]
        assert buf.get(2, 0).char == _WIDE_CHAR_FILLER  # type: ignore[union-attr]
        assert buf.get(3, 0).char == "B"  # type: ignore[union-attr]

    def test_emoji_clipped_at_right_edge(self) -> None:
        """Wide emoji at the last column is skipped (can't split)."""
        buf = CellBuffer(3, 1)
        buf.put_text(2, 0, HEART_EMOJI)
        # Only 1 column remains at position 2 — wide emoji skipped.
        cell = buf.get(2, 0)
        assert cell is not None
        assert cell.char == " "  # default, emoji was skipped

    def test_emoji_with_style(self) -> None:
        buf = CellBuffer(10, 1)
        buf.put_text(0, 0, HEART_EMOJI, fg="red", bg="black")
        cell = buf.get(0, 0)
        assert cell is not None
        assert cell.char == HEART_EMOJI
        assert cell.fg == "red"
        assert cell.bg == "black"


# ---------------------------------------------------------------------------
# CellBuffer Rich rendering with emoji
# ---------------------------------------------------------------------------


class TestCellBufferRichRenderEmoji:
    """Emoji cells render correctly through Rich."""

    @staticmethod
    def _render_to_str(buf: CellBuffer, *, color_system: str | None = None) -> str:
        import io
        from rich.console import Console

        sio = io.StringIO()
        console = Console(
            file=sio, force_terminal=True, color_system=color_system,
            width=buf.width,
        )
        console.print(buf, end="")
        return sio.getvalue()

    def test_emoji_appears_in_output(self) -> None:
        """Emoji grapheme cluster appears in rendered output."""
        buf = CellBuffer(10, 1)
        buf.put_text(0, 0, HEART_EMOJI)
        output = self._render_to_str(buf, color_system=None)
        # The base character (❤) should appear in the output.
        assert "\u2764" in output

    def test_filler_not_in_output(self) -> None:
        """Wide char filler sentinel does not appear in rendered output."""
        buf = CellBuffer(10, 1)
        buf.put_text(0, 0, HEART_EMOJI)
        output = self._render_to_str(buf, color_system=None)
        assert "\x00" not in output

    def test_rocket_emoji_in_output(self) -> None:
        buf = CellBuffer(10, 1)
        buf.put_text(0, 0, ROCKET_EMOJI)
        output = self._render_to_str(buf, color_system=None)
        assert ROCKET_EMOJI in output


# ---------------------------------------------------------------------------
# from_text with emoji
# ---------------------------------------------------------------------------


class TestFromTextEmoji:
    """from_text handles emoji grapheme clusters in text input."""

    def test_single_emoji_with_vs16(self) -> None:
        """A single emoji with VS16 produces one entity."""
        entities = from_text(HEART_EMOJI)
        assert len(entities) == 1
        sprite = entities[0].get_component(Sprite)
        assert sprite.char == HEART_EMOJI

    def test_emoji_position_with_vs16(self) -> None:
        """Emoji with VS16 (width 2) advances column by 2."""
        # heart+VS16 at col 0 (width 2), then 'A' at col 2
        text = HEART_EMOJI + "A"
        entities = from_text(text)
        assert len(entities) == 2
        assert entities[0].x == 0
        assert entities[0].get_component(Sprite).char == HEART_EMOJI
        assert entities[1].x == 2
        assert entities[1].get_component(Sprite).char == "A"

    def test_mixed_ascii_and_emoji(self) -> None:
        """Mixed ASCII and emoji produce correct positions."""
        text = "X" + HEART_EMOJI + "Y"
        entities = from_text(text)
        assert len(entities) == 3
        assert entities[0].x == 0
        assert entities[0].get_component(Sprite).char == "X"
        assert entities[1].x == 1
        assert entities[1].get_component(Sprite).char == HEART_EMOJI
        assert entities[2].x == 3
        assert entities[2].get_component(Sprite).char == "Y"

    def test_multi_line_with_emoji(self) -> None:
        """Emoji in multi-line text preserves row positions."""
        text = HEART_EMOJI + "\n" + "AB"
        entities = from_text(text)
        assert len(entities) == 3
        # Row 0: heart
        assert entities[0].y == 0
        assert entities[0].get_component(Sprite).char == HEART_EMOJI
        # Row 1: A, B
        assert entities[1].y == 1
        assert entities[1].x == 0
        assert entities[2].y == 1
        assert entities[2].x == 1

    def test_single_codepoint_emoji(self) -> None:
        """Single-codepoint emoji (no VS) works in from_text."""
        entities = from_text(ROCKET_EMOJI)
        assert len(entities) == 1
        assert entities[0].get_component(Sprite).char == ROCKET_EMOJI


# ---------------------------------------------------------------------------
# AnimationFrame with emoji
# ---------------------------------------------------------------------------


class TestAnimationFrameEmoji:
    """AnimationFrame accepts emoji grapheme clusters."""

    def test_emoji_with_vs16(self) -> None:
        frame = AnimationFrame(HEART_EMOJI, duration=0.1)
        assert frame.char == HEART_EMOJI

    def test_single_codepoint_emoji(self) -> None:
        frame = AnimationFrame(ROCKET_EMOJI, duration=0.2)
        assert frame.char == ROCKET_EMOJI

    def test_rejects_multi_cluster(self) -> None:
        with pytest.raises(ValueError, match="single grapheme cluster"):
            AnimationFrame("\U0001F680\U0001F525")

    def test_rejects_empty(self) -> None:
        with pytest.raises(ValueError, match="must not be empty"):
            AnimationFrame("")


# ---------------------------------------------------------------------------
# Variation selector width caveats
# ---------------------------------------------------------------------------


class TestVariationSelectorWidthCaveats:
    """Document and test the width behaviour of variation selectors.

    Caveats:
        - VS16 (U+FE0F) requests emoji presentation.  grapheme_width
          returns 2 for sequences containing VS16.  Most modern terminals
          (iTerm2, kitty, WezTerm, Windows Terminal) honour this and
          render the character at 2 columns.  Some older terminals or
          configurations may render at 1 column, causing misalignment.
        - VS15 (U+FE0E) requests text presentation.  grapheme_width
          returns the base character's width (typically 1).  The character
          renders as a monochrome text glyph.
        - Without any variation selector, the default presentation depends
          on the character and the terminal.  Characters in Unicode's
          Emoji_Presentation=Yes list default to emoji presentation;
          others default to text.  This module does not distinguish
          Emoji_Presentation — it relies on EAW and VS16 presence.
    """

    def test_vs16_width_is_2(self) -> None:
        """Grapheme with VS16 reports width 2."""
        assert grapheme_width(HEART_EMOJI) == 2

    def test_vs15_width_is_1(self) -> None:
        """Grapheme with VS15 reports width 1 (text presentation)."""
        assert grapheme_width(HEART_TEXT) == 1

    def test_bare_heart_width(self) -> None:
        """Bare heart (no VS) — width depends on EAW classification.

        U+2764 HEAVY BLACK HEART has EAW 'N' (Neutral), so char_width
        returns 1.  Without VS16, grapheme_width also returns 1.
        However, some terminals may render it as emoji (width 2) by
        default — this is a known terminal-dependent discrepancy.
        """
        assert grapheme_width("\u2764") == 1

    def test_keycap_width_is_2(self) -> None:
        """Keycap sequence (digit + VS16 + enclosing keycap) is width 2."""
        assert grapheme_width(KEYCAP_ONE) == 2

    def test_single_codepoint_emoji_width(self) -> None:
        """Single-codepoint emoji with EAW=W is width 2."""
        # 🚀 has EAW 'W' (Wide)
        assert grapheme_width(ROCKET_EMOJI) == 2


# ---------------------------------------------------------------------------
# grapheme cluster iteration with emoji
# ---------------------------------------------------------------------------


class TestGraphemeClusterEmoji:
    """iter_grapheme_clusters correctly segments emoji sequences."""

    def test_emoji_with_vs16_is_one_cluster(self) -> None:
        clusters = list(iter_grapheme_clusters(HEART_EMOJI))
        assert len(clusters) == 1
        assert clusters[0] == HEART_EMOJI

    def test_two_emoji_with_vs16_are_two_clusters(self) -> None:
        text = HEART_EMOJI + SWORDS_EMOJI
        clusters = list(iter_grapheme_clusters(text))
        assert len(clusters) == 2
        assert clusters[0] == HEART_EMOJI
        assert clusters[1] == SWORDS_EMOJI

    def test_ascii_then_emoji_then_ascii(self) -> None:
        text = "A" + HEART_EMOJI + "B"
        clusters = list(iter_grapheme_clusters(text))
        assert clusters == ["A", HEART_EMOJI, "B"]


# ---------------------------------------------------------------------------
# Import from package root
# ---------------------------------------------------------------------------


class TestEmojiSpriteImport:
    """is_single_grapheme is accessible from the wyby package root."""

    def test_import_is_single_grapheme(self) -> None:
        from wyby import is_single_grapheme as isg
        assert isg is is_single_grapheme
