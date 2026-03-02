"""Tests for the Renderer and virtual buffer."""

import pytest

from rich.style import Style

from runetui.renderer import Cell, Layer, Renderer


class TestCell:
    def test_defaults(self):
        cell = Cell()
        assert cell.char == " "
        assert cell.layer == Layer.BACKGROUND

    def test_custom(self):
        style = Style(color="red")
        cell = Cell(char="X", style=style, layer=Layer.UI)
        assert cell.char == "X"
        assert cell.layer == Layer.UI


class TestRenderer:
    def test_init_creates_buffer(self):
        r = Renderer(10, 5)
        assert len(r._buffer) == 5
        assert len(r._buffer[0]) == 10

    def test_clear_buffer(self):
        r = Renderer(10, 5)
        r._buffer[0][0].char = "X"
        r.clear_buffer()
        assert r._buffer[0][0].char == " "

    def test_draw_text(self):
        r = Renderer(20, 5)
        r.draw_text(2, 1, "Hello")
        assert r._buffer[1][2].char == "H"
        assert r._buffer[1][3].char == "e"
        assert r._buffer[1][4].char == "l"
        assert r._buffer[1][5].char == "l"
        assert r._buffer[1][6].char == "o"

    def test_draw_text_with_style(self):
        r = Renderer(20, 5)
        style = Style(color="red")
        r.draw_text(0, 0, "X", style=style)
        assert r._buffer[0][0].char == "X"
        assert r._buffer[0][0].style == style

    def test_draw_text_clips_horizontal(self):
        r = Renderer(5, 3)
        r.draw_text(3, 0, "ABCDE")
        assert r._buffer[0][3].char == "A"
        assert r._buffer[0][4].char == "B"
        # Columns 5+ are out of bounds — should be clipped

    def test_draw_text_clips_vertical(self):
        r = Renderer(10, 3)
        # Should not raise for out-of-bounds y
        r.draw_text(0, -1, "test")
        r.draw_text(0, 5, "test")

    def test_draw_text_negative_x(self):
        r = Renderer(10, 3)
        r.draw_text(-2, 0, "ABCD")
        # Only C and D should appear at columns 0 and 1
        assert r._buffer[0][0].char == "C"
        assert r._buffer[0][1].char == "D"

    def test_layer_ordering(self):
        r = Renderer(10, 3)
        style_bg = Style(bgcolor="blue")
        style_fg = Style(color="red")
        r.draw_text(0, 0, "B", style=style_bg, layer=Layer.BACKGROUND)
        r.draw_text(0, 0, "E", style=style_fg, layer=Layer.ENTITIES)
        assert r._buffer[0][0].char == "E"
        assert r._buffer[0][0].style == style_fg

    def test_lower_layer_cannot_overwrite_higher(self):
        r = Renderer(10, 3)
        r.draw_text(0, 0, "U", layer=Layer.UI)
        r.draw_text(0, 0, "B", layer=Layer.BACKGROUND)
        assert r._buffer[0][0].char == "U"

    def test_draw_rect(self):
        r = Renderer(10, 5)
        r.draw_rect(1, 1, 3, 2, char="#")
        assert r._buffer[1][1].char == "#"
        assert r._buffer[1][2].char == "#"
        assert r._buffer[1][3].char == "#"
        assert r._buffer[2][1].char == "#"
        assert r._buffer[2][3].char == "#"
        assert r._buffer[0][0].char == " "  # outside rect

    def test_compose_buffer(self):
        r = Renderer(3, 2)
        r.draw_text(0, 0, "ABC")
        r.draw_text(0, 1, "DEF")
        composed = r._compose_buffer()
        assert "ABC" in composed.plain
        assert "DEF" in composed.plain
