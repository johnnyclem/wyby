"""Tests for the Sprite system."""

import pytest

from rich.style import Style

from runetui.sprite import Sprite, SpriteFrame


class TestSpriteFrame:
    def test_empty_frame(self):
        f = SpriteFrame()
        assert f.width == 0
        assert f.height == 0

    def test_dimensions(self):
        lines = [
            [("A", Style()), ("B", Style())],
            [("C", Style()), ("D", Style()), ("E", Style())],
        ]
        f = SpriteFrame(lines=lines)
        assert f.width == 3
        assert f.height == 2


class TestSprite:
    def test_from_text(self):
        sprite = Sprite.from_text("AB\nCD")
        assert len(sprite.frames) == 1
        assert sprite.frame.height == 2
        assert sprite.frame.width == 2

    def test_from_text_single_line(self):
        sprite = Sprite.from_text("Hello")
        assert sprite.frame.height == 1
        assert sprite.frame.width == 5

    def test_advance_frame(self):
        f1 = SpriteFrame(lines=[[("1", Style())]])
        f2 = SpriteFrame(lines=[[("2", Style())]])
        sprite = Sprite(frames=[f1, f2])
        assert sprite.current_frame == 0
        sprite.advance_frame()
        assert sprite.current_frame == 1
        sprite.advance_frame()
        assert sprite.current_frame == 0  # wraps

    def test_from_image_without_pillow(self):
        # Should return a fallback sprite, not crash
        sprite = Sprite.from_image("nonexistent.png")
        assert len(sprite.frames) > 0
