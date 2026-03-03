"""Tests for wyby.sprite.from_image_with_fallback."""

from __future__ import annotations

import logging

import pytest
from PIL import Image

from wyby.sprite import Sprite, from_image_with_fallback


# ---------------------------------------------------------------------------
# Image path succeeds
# ---------------------------------------------------------------------------


class TestImagePathSucceeds:
    """When the image is valid, from_image is used."""

    def test_returns_image_entities(self) -> None:
        img = Image.new("RGB", (2, 2), color=(255, 0, 0))
        entities = from_image_with_fallback(img, "##\n##")
        # 2x2 image → 4 entities, each with full-block char
        assert len(entities) == 4
        sprite = entities[0].get_component(Sprite)
        assert sprite.char == "\u2588"
        assert sprite.style.color is not None
        assert sprite.style.color.name == "#ff0000"

    def test_origin_passed_to_image_path(self) -> None:
        img = Image.new("RGB", (1, 1), color=(0, 0, 0))
        entities = from_image_with_fallback(
            img, "@", origin_x=5, origin_y=10,
        )
        assert entities[0].x == 5
        assert entities[0].y == 10

    def test_custom_char_used_for_image(self) -> None:
        img = Image.new("RGB", (1, 1), color=(0, 0, 0))
        entities = from_image_with_fallback(img, "@", char="#")
        assert entities[0].get_component(Sprite).char == "#"

    def test_alpha_handling_in_image_path(self) -> None:
        img = Image.new("RGBA", (2, 1))
        img.putpixel((0, 0), (255, 0, 0, 255))
        img.putpixel((1, 0), (0, 255, 0, 0))  # fully transparent
        entities = from_image_with_fallback(img, "##")
        assert len(entities) == 1


# ---------------------------------------------------------------------------
# Fallback to text — image is None
# ---------------------------------------------------------------------------


class TestFallbackImageNone:
    """When image is None, text fallback is used immediately."""

    def test_returns_text_entities(self) -> None:
        entities = from_image_with_fallback(None, "##\n##")
        assert len(entities) == 4
        for e in entities:
            assert e.get_component(Sprite).char == "#"

    def test_origin_passed_to_text_fallback(self) -> None:
        entities = from_image_with_fallback(
            None, "@", origin_x=3, origin_y=7,
        )
        assert entities[0].x == 3
        assert entities[0].y == 7

    def test_fallback_style_applied(self) -> None:
        from rich.style import Style
        style = Style(color="green")
        entities = from_image_with_fallback(
            None, "@", fallback_style=style,
        )
        assert entities[0].get_component(Sprite).style.color.name == "green"

    def test_skip_whitespace_in_fallback(self) -> None:
        entities = from_image_with_fallback(
            None, "# #", skip_whitespace=False,
        )
        # 3 entities: '#', ' ', '#'
        assert len(entities) == 3

    def test_logs_warning_on_none(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.WARNING, logger="wyby.sprite"):
            from_image_with_fallback(None, "@")
        assert "image is None" in caplog.text
        assert "text fallback" in caplog.text


# ---------------------------------------------------------------------------
# Fallback to text — image conversion fails
# ---------------------------------------------------------------------------


class TestFallbackImageConversionFails:
    """When from_image raises, text fallback is used."""

    def test_bad_image_type_falls_back(self) -> None:
        """Passing a non-Image triggers TypeError → fallback."""
        entities = from_image_with_fallback(
            "not_an_image", "@@\n@@",  # type: ignore[arg-type]
        )
        assert len(entities) == 4
        for e in entities:
            assert e.get_component(Sprite).char == "@"

    def test_zero_dimension_image_falls_back(self) -> None:
        """A zero-size image triggers ValueError → fallback."""
        # PIL doesn't allow 0-size via Image.new, so we create a crop
        # that results in 0 width.
        img = Image.new("RGB", (2, 2), color=(0, 0, 0))
        cropped = img.crop((0, 0, 0, 2))  # 0-width
        entities = from_image_with_fallback(cropped, "X")
        assert len(entities) == 1
        assert entities[0].get_component(Sprite).char == "X"

    def test_logs_warning_on_failure(
        self, caplog: pytest.LogCaptureFixture,
    ) -> None:
        with caplog.at_level(logging.WARNING, logger="wyby.sprite"):
            from_image_with_fallback(
                "bad", "@",  # type: ignore[arg-type]
            )
        assert "image conversion failed" in caplog.text
        assert "text fallback" in caplog.text

    def test_fallback_preserves_origin_after_failure(self) -> None:
        entities = from_image_with_fallback(
            "bad",  # type: ignore[arg-type]
            "@",
            origin_x=10,
            origin_y=20,
        )
        assert entities[0].x == 10
        assert entities[0].y == 20


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class TestFallbackValidation:
    """Input validation for from_image_with_fallback."""

    def test_rejects_non_string_fallback_text(self) -> None:
        img = Image.new("RGB", (1, 1), color=(0, 0, 0))
        with pytest.raises(TypeError, match="fallback_text must be a string"):
            from_image_with_fallback(img, 42)  # type: ignore[arg-type]

    def test_rejects_none_fallback_text(self) -> None:
        with pytest.raises(TypeError, match="fallback_text must be a string"):
            from_image_with_fallback(None, None)  # type: ignore[arg-type]

    def test_empty_fallback_text_raises_on_fallback(self) -> None:
        """Empty fallback text raises ValueError when fallback is triggered."""
        with pytest.raises(ValueError, match="must not be empty"):
            from_image_with_fallback(None, "")

    def test_whitespace_only_fallback_raises_on_fallback(self) -> None:
        with pytest.raises(ValueError, match="must not be empty"):
            from_image_with_fallback(None, "   \n   ")


# ---------------------------------------------------------------------------
# Import from package root
# ---------------------------------------------------------------------------


class TestFallbackImport:
    """from_image_with_fallback is accessible from the wyby package root."""

    def test_import_from_wyby(self) -> None:
        from wyby import from_image_with_fallback as f
        assert f is from_image_with_fallback
