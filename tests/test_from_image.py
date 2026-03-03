"""Tests for wyby.sprite.from_image — Pillow image to entities factory."""

from __future__ import annotations

import pytest
from PIL import Image

from wyby.sprite import Sprite, from_image


# ---------------------------------------------------------------------------
# Basic functionality
# ---------------------------------------------------------------------------


class TestFromImageBasic:
    """Core from_image behaviour with simple images."""

    def test_single_pixel(self) -> None:
        img = Image.new("RGB", (1, 1), color=(255, 0, 0))
        entities = from_image(img)
        assert len(entities) == 1
        e = entities[0]
        assert e.x == 0
        assert e.y == 0
        sprite = e.get_component(Sprite)
        assert sprite is not None
        assert sprite.char == "\u2588"
        assert sprite.style.color is not None
        assert sprite.style.color.name == "#ff0000"

    def test_small_image(self) -> None:
        img = Image.new("RGB", (3, 2), color=(0, 128, 255))
        entities = from_image(img)
        assert len(entities) == 6
        # All should have the same colour
        for e in entities:
            sprite = e.get_component(Sprite)
            assert sprite.style.color.name == "#0080ff"

    def test_positions_match_pixels(self) -> None:
        img = Image.new("RGB", (3, 2), color=(0, 0, 0))
        entities = from_image(img)
        positions = [(e.x, e.y) for e in entities]
        # Row-major order: top-to-bottom, left-to-right
        assert positions == [
            (0, 0), (1, 0), (2, 0),
            (0, 1), (1, 1), (2, 1),
        ]

    def test_entities_are_alive(self) -> None:
        img = Image.new("RGB", (2, 2), color=(0, 0, 0))
        entities = from_image(img)
        for e in entities:
            assert e.alive is True

    def test_each_entity_has_unique_id(self) -> None:
        img = Image.new("RGB", (3, 1), color=(0, 0, 0))
        entities = from_image(img)
        ids = [e.id for e in entities]
        assert len(set(ids)) == 3

    def test_per_pixel_colour(self) -> None:
        """Each pixel gets its own colour from the image data."""
        img = Image.new("RGB", (2, 1))
        img.putpixel((0, 0), (255, 0, 0))
        img.putpixel((1, 0), (0, 255, 0))
        entities = from_image(img)
        assert len(entities) == 2
        assert entities[0].get_component(Sprite).style.color.name == "#ff0000"
        assert entities[1].get_component(Sprite).style.color.name == "#00ff00"


# ---------------------------------------------------------------------------
# Alpha handling
# ---------------------------------------------------------------------------


class TestFromImageAlpha:
    """Transparent pixel skipping."""

    def test_fully_transparent_skipped_by_default(self) -> None:
        img = Image.new("RGBA", (2, 1))
        img.putpixel((0, 0), (255, 0, 0, 255))
        img.putpixel((1, 0), (0, 255, 0, 0))  # fully transparent
        entities = from_image(img)
        assert len(entities) == 1
        assert entities[0].x == 0

    def test_all_transparent_returns_empty(self) -> None:
        img = Image.new("RGBA", (2, 2), color=(0, 0, 0, 0))
        entities = from_image(img)
        assert entities == []

    def test_skip_alpha_false_includes_transparent(self) -> None:
        img = Image.new("RGBA", (2, 1))
        img.putpixel((0, 0), (255, 0, 0, 255))
        img.putpixel((1, 0), (0, 255, 0, 0))  # fully transparent
        entities = from_image(img, skip_alpha=False)
        assert len(entities) == 2

    def test_alpha_threshold(self) -> None:
        img = Image.new("RGBA", (3, 1))
        img.putpixel((0, 0), (255, 0, 0, 255))  # opaque
        img.putpixel((1, 0), (0, 255, 0, 50))   # semi-transparent
        img.putpixel((2, 0), (0, 0, 255, 10))   # nearly transparent
        entities = from_image(img, alpha_threshold=50)
        # Only the first pixel (alpha 255) remains; alpha 50 and 10 are skipped
        assert len(entities) == 1
        assert entities[0].x == 0

    def test_alpha_threshold_boundary(self) -> None:
        """Pixels at exactly the threshold are skipped (<=)."""
        img = Image.new("RGBA", (2, 1))
        img.putpixel((0, 0), (255, 0, 0, 100))  # at threshold → skipped
        img.putpixel((1, 0), (0, 255, 0, 101))  # above threshold → kept
        entities = from_image(img, alpha_threshold=100)
        assert len(entities) == 1
        assert entities[0].x == 1

    def test_rgb_image_all_opaque(self) -> None:
        """RGB images have no alpha — all pixels produce entities."""
        img = Image.new("RGB", (3, 1), color=(100, 100, 100))
        entities = from_image(img)
        assert len(entities) == 3


# ---------------------------------------------------------------------------
# Origin offset
# ---------------------------------------------------------------------------


class TestFromImageOrigin:
    """Origin offset shifts all entity positions."""

    def test_origin_x(self) -> None:
        img = Image.new("RGB", (2, 1), color=(0, 0, 0))
        entities = from_image(img, origin_x=5)
        assert entities[0].x == 5
        assert entities[1].x == 6

    def test_origin_y(self) -> None:
        img = Image.new("RGB", (1, 2), color=(0, 0, 0))
        entities = from_image(img, origin_y=10)
        assert entities[0].y == 10
        assert entities[1].y == 11

    def test_origin_both(self) -> None:
        img = Image.new("RGB", (1, 1), color=(0, 0, 0))
        entities = from_image(img, origin_x=3, origin_y=7)
        assert entities[0].x == 3
        assert entities[0].y == 7

    def test_negative_origin(self) -> None:
        img = Image.new("RGB", (1, 1), color=(0, 0, 0))
        entities = from_image(img, origin_x=-2, origin_y=-1)
        assert entities[0].x == -2
        assert entities[0].y == -1


# ---------------------------------------------------------------------------
# Custom char
# ---------------------------------------------------------------------------


class TestFromImageChar:
    """Custom character parameter."""

    def test_default_char_is_full_block(self) -> None:
        img = Image.new("RGB", (1, 1), color=(0, 0, 0))
        entities = from_image(img)
        assert entities[0].get_component(Sprite).char == "\u2588"

    def test_custom_char(self) -> None:
        img = Image.new("RGB", (1, 1), color=(0, 0, 0))
        entities = from_image(img, char="#")
        assert entities[0].get_component(Sprite).char == "#"

    def test_wide_char(self) -> None:
        """Wide characters are accepted (CJK ideographs)."""
        img = Image.new("RGB", (1, 1), color=(0, 0, 0))
        entities = from_image(img, char="\u4e16")  # 世
        assert entities[0].get_component(Sprite).char == "\u4e16"


# ---------------------------------------------------------------------------
# Image modes
# ---------------------------------------------------------------------------


class TestFromImageModes:
    """Different Pillow image modes are handled."""

    def test_rgba_mode(self) -> None:
        img = Image.new("RGBA", (2, 1), color=(255, 0, 0, 255))
        entities = from_image(img)
        assert len(entities) == 2

    def test_rgb_mode(self) -> None:
        img = Image.new("RGB", (2, 1), color=(255, 0, 0))
        entities = from_image(img)
        assert len(entities) == 2

    def test_l_greyscale_mode(self) -> None:
        """Greyscale images are converted to RGBA."""
        img = Image.new("L", (2, 1), color=128)
        entities = from_image(img)
        assert len(entities) == 2
        # Grey 128 → #808080
        sprite = entities[0].get_component(Sprite)
        assert sprite.style.color.name == "#808080"

    def test_p_palette_mode(self) -> None:
        """Palette mode images are converted to RGBA."""
        img = Image.new("P", (2, 1))
        entities = from_image(img)
        assert len(entities) == 2

    def test_1_bitmap_mode(self) -> None:
        """1-bit images are converted to RGBA."""
        img = Image.new("1", (2, 1), color=1)
        entities = from_image(img)
        assert len(entities) == 2


# ---------------------------------------------------------------------------
# Quantization (integration-style)
# ---------------------------------------------------------------------------


class TestFromImageQuantization:
    """Quantization reduces unique styles — documented workflow."""

    def test_quantized_image_has_fewer_styles(self) -> None:
        """Quantizing before from_image reduces unique colours."""
        # Create an image with many colours (gradient)
        img = Image.new("RGB", (16, 1))
        for x in range(16):
            img.putpixel((x, 0), (x * 16, 255 - x * 16, 128))

        # Without quantization: potentially 16 unique colours
        entities_raw = from_image(img)
        styles_raw = {
            e.get_component(Sprite).style.color.name for e in entities_raw
        }

        # Quantize to 4 colours, then convert back to RGBA
        quantized = img.quantize(colors=4).convert("RGBA")
        entities_q = from_image(quantized)
        styles_q = {
            e.get_component(Sprite).style.color.name for e in entities_q
        }

        # Same number of entities, fewer unique styles
        assert len(entities_q) == len(entities_raw)
        assert len(styles_q) <= 4
        assert len(styles_q) < len(styles_raw)


# ---------------------------------------------------------------------------
# Validation — errors
# ---------------------------------------------------------------------------


class TestFromImageValidation:
    """Input validation and error handling."""

    def test_rejects_non_image(self) -> None:
        with pytest.raises(TypeError, match="must be a PIL.Image.Image"):
            from_image("not_an_image")  # type: ignore[arg-type]

    def test_rejects_none(self) -> None:
        with pytest.raises(TypeError, match="must be a PIL.Image.Image"):
            from_image(None)  # type: ignore[arg-type]

    def test_rejects_non_int_origin_x(self) -> None:
        img = Image.new("RGB", (1, 1), color=(0, 0, 0))
        with pytest.raises(TypeError, match="origin_x must be an int"):
            from_image(img, origin_x=1.5)  # type: ignore[arg-type]

    def test_rejects_non_int_origin_y(self) -> None:
        img = Image.new("RGB", (1, 1), color=(0, 0, 0))
        with pytest.raises(TypeError, match="origin_y must be an int"):
            from_image(img, origin_y="0")  # type: ignore[arg-type]

    def test_rejects_bool_origin_x(self) -> None:
        img = Image.new("RGB", (1, 1), color=(0, 0, 0))
        with pytest.raises(TypeError, match="origin_x must be an int"):
            from_image(img, origin_x=True)  # type: ignore[arg-type]

    def test_rejects_bool_origin_y(self) -> None:
        img = Image.new("RGB", (1, 1), color=(0, 0, 0))
        with pytest.raises(TypeError, match="origin_y must be an int"):
            from_image(img, origin_y=False)  # type: ignore[arg-type]

    def test_rejects_non_string_char(self) -> None:
        img = Image.new("RGB", (1, 1), color=(0, 0, 0))
        with pytest.raises(TypeError, match="char must be a string"):
            from_image(img, char=42)  # type: ignore[arg-type]

    def test_rejects_multi_char(self) -> None:
        img = Image.new("RGB", (1, 1), color=(0, 0, 0))
        with pytest.raises(ValueError, match="char must be exactly one"):
            from_image(img, char="##")

    def test_rejects_empty_char(self) -> None:
        img = Image.new("RGB", (1, 1), color=(0, 0, 0))
        with pytest.raises(ValueError, match="char must be exactly one"):
            from_image(img, char="")

    def test_rejects_zero_width_char(self) -> None:
        img = Image.new("RGB", (1, 1), color=(0, 0, 0))
        with pytest.raises(ValueError, match="non-zero display width"):
            from_image(img, char="\u0300")  # combining grave accent

    def test_rejects_alpha_threshold_below_zero(self) -> None:
        img = Image.new("RGB", (1, 1), color=(0, 0, 0))
        with pytest.raises(ValueError, match="alpha_threshold must be 0–255"):
            from_image(img, alpha_threshold=-1)

    def test_rejects_alpha_threshold_above_255(self) -> None:
        img = Image.new("RGB", (1, 1), color=(0, 0, 0))
        with pytest.raises(ValueError, match="alpha_threshold must be 0–255"):
            from_image(img, alpha_threshold=256)

    def test_rejects_bool_alpha_threshold(self) -> None:
        img = Image.new("RGB", (1, 1), color=(0, 0, 0))
        with pytest.raises(TypeError, match="alpha_threshold must be an int"):
            from_image(img, alpha_threshold=True)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Ordering
# ---------------------------------------------------------------------------


class TestFromImageOrdering:
    """Entities are ordered top-to-bottom, left-to-right."""

    def test_order_is_row_major(self) -> None:
        img = Image.new("RGB", (3, 2), color=(0, 0, 0))
        entities = from_image(img)
        positions = [(e.x, e.y) for e in entities]
        assert positions == [
            (0, 0), (1, 0), (2, 0),
            (0, 1), (1, 1), (2, 1),
        ]


# ---------------------------------------------------------------------------
# Import from package root
# ---------------------------------------------------------------------------


class TestFromImageImport:
    """from_image is accessible from the wyby package root."""

    def test_import_from_wyby(self) -> None:
        from wyby import from_image as fi
        assert fi is from_image
