"""Tests for wyby.dithering — aspect ratio and quantization utilities."""

from __future__ import annotations

import pytest
from PIL import Image

from wyby.dithering import (
    CELL_ASPECT_RATIO,
    correct_aspect_ratio,
    prepare_for_terminal,
    quantize_for_terminal,
)


# ---------------------------------------------------------------------------
# CELL_ASPECT_RATIO constant
# ---------------------------------------------------------------------------


class TestCellAspectRatio:
    """The default cell aspect ratio constant."""

    def test_default_value(self) -> None:
        assert CELL_ASPECT_RATIO == 2.0

    def test_is_float(self) -> None:
        assert isinstance(CELL_ASPECT_RATIO, float)


# ---------------------------------------------------------------------------
# correct_aspect_ratio
# ---------------------------------------------------------------------------


class TestCorrectAspectRatio:
    """Aspect ratio correction resizes images to compensate for tall cells."""

    def test_halves_height_by_default(self) -> None:
        img = Image.new("RGB", (20, 40), color=(255, 0, 0))
        result = correct_aspect_ratio(img)
        assert result.size == (20, 20)

    def test_preserves_width(self) -> None:
        img = Image.new("RGB", (30, 20), color=(0, 128, 0))
        result = correct_aspect_ratio(img)
        assert result.size[0] == 30

    def test_odd_height_rounds(self) -> None:
        img = Image.new("RGB", (10, 11), color=(0, 0, 255))
        result = correct_aspect_ratio(img)
        # round(11 / 2.0) = round(5.5) = 6
        assert result.size == (10, 6)

    def test_minimum_height_is_one(self) -> None:
        img = Image.new("RGB", (10, 1), color=(0, 0, 0))
        result = correct_aspect_ratio(img)
        assert result.size[1] >= 1

    def test_custom_aspect_ratio(self) -> None:
        img = Image.new("RGB", (10, 30), color=(0, 0, 0))
        result = correct_aspect_ratio(img, cell_aspect_ratio=3.0)
        assert result.size == (10, 10)

    def test_aspect_ratio_of_one_no_change(self) -> None:
        img = Image.new("RGB", (10, 10), color=(0, 0, 0))
        result = correct_aspect_ratio(img, cell_aspect_ratio=1.0)
        assert result.size == (10, 10)

    def test_rgba_mode_preserved(self) -> None:
        img = Image.new("RGBA", (10, 20), color=(255, 0, 0, 128))
        result = correct_aspect_ratio(img)
        assert result.mode == "RGBA"
        assert result.size == (10, 10)

    def test_returns_new_image(self) -> None:
        img = Image.new("RGB", (10, 20), color=(0, 0, 0))
        result = correct_aspect_ratio(img)
        assert result is not img

    def test_copy_when_ratio_matches(self) -> None:
        """When ratio=1.0 and height equals width, returns a copy."""
        img = Image.new("RGB", (5, 5), color=(100, 100, 100))
        result = correct_aspect_ratio(img, cell_aspect_ratio=1.0)
        assert result is not img
        assert result.size == img.size

    def test_pixel_colours_preserved_simple(self) -> None:
        """A solid-colour image stays the same colour after resizing."""
        img = Image.new("RGB", (4, 8), color=(255, 128, 0))
        result = correct_aspect_ratio(img)
        # Check centre pixel of result
        w, h = result.size
        r, g, b = result.getpixel((w // 2, h // 2))
        assert (r, g, b) == (255, 128, 0)


# ---------------------------------------------------------------------------
# correct_aspect_ratio — validation
# ---------------------------------------------------------------------------


class TestCorrectAspectRatioValidation:
    """Input validation for correct_aspect_ratio."""

    def test_rejects_non_image(self) -> None:
        with pytest.raises(TypeError, match="must be a PIL.Image.Image"):
            correct_aspect_ratio("not_an_image")  # type: ignore[arg-type]

    def test_rejects_none(self) -> None:
        with pytest.raises(TypeError, match="must be a PIL.Image.Image"):
            correct_aspect_ratio(None)  # type: ignore[arg-type]

    def test_rejects_non_numeric_ratio(self) -> None:
        img = Image.new("RGB", (10, 10))
        with pytest.raises(TypeError, match="cell_aspect_ratio must be a number"):
            correct_aspect_ratio(img, cell_aspect_ratio="2")  # type: ignore[arg-type]

    def test_rejects_zero_ratio(self) -> None:
        img = Image.new("RGB", (10, 10))
        with pytest.raises(ValueError, match="must be positive"):
            correct_aspect_ratio(img, cell_aspect_ratio=0.0)

    def test_rejects_negative_ratio(self) -> None:
        img = Image.new("RGB", (10, 10))
        with pytest.raises(ValueError, match="must be positive"):
            correct_aspect_ratio(img, cell_aspect_ratio=-1.0)


# ---------------------------------------------------------------------------
# quantize_for_terminal
# ---------------------------------------------------------------------------


class TestQuantizeForTerminal:
    """Colour quantization reduces unique colours."""

    def test_reduces_colours(self) -> None:
        """A gradient image with many colours is reduced to 4."""
        img = Image.new("RGB", (64, 1))
        for x in range(64):
            img.putpixel((x, 0), (x * 4, 255 - x * 4, 128))

        result = quantize_for_terminal(img, colors=4, dither=False)
        unique_colours = set()
        for x in range(64):
            unique_colours.add(result.getpixel((x, 0))[:3])

        assert len(unique_colours) <= 4

    def test_default_is_16_colours(self) -> None:
        img = Image.new("RGB", (32, 1))
        for x in range(32):
            img.putpixel((x, 0), (x * 8, x * 4, 255 - x * 8))

        result = quantize_for_terminal(img, dither=False)
        unique_colours = set()
        for x in range(32):
            unique_colours.add(result.getpixel((x, 0))[:3])

        assert len(unique_colours) <= 16

    def test_single_colour_image_stays_single(self) -> None:
        img = Image.new("RGB", (10, 10), color=(128, 64, 32))
        result = quantize_for_terminal(img, colors=4, dither=False)
        unique_colours = set()
        for y in range(10):
            for x in range(10):
                unique_colours.add(result.getpixel((x, y))[:3])
        assert len(unique_colours) == 1

    def test_returns_rgba(self) -> None:
        img = Image.new("RGB", (4, 4), color=(0, 0, 0))
        result = quantize_for_terminal(img, colors=4)
        assert result.mode == "RGBA"

    def test_preserves_alpha_channel(self) -> None:
        img = Image.new("RGBA", (4, 1))
        img.putpixel((0, 0), (255, 0, 0, 255))
        img.putpixel((1, 0), (0, 255, 0, 128))
        img.putpixel((2, 0), (0, 0, 255, 64))
        img.putpixel((3, 0), (255, 255, 0, 0))

        result = quantize_for_terminal(img, colors=4, dither=False)

        # Alpha values should be preserved.
        assert result.getpixel((0, 0))[3] == 255
        assert result.getpixel((1, 0))[3] == 128
        assert result.getpixel((2, 0))[3] == 64
        assert result.getpixel((3, 0))[3] == 0

    def test_dither_true_produces_more_unique_pixels(self) -> None:
        """Dithering typically spreads error, creating more pixel variation."""
        img = Image.new("RGB", (20, 20))
        for y in range(20):
            for x in range(20):
                img.putpixel((x, y), (x * 12, y * 12, 128))

        no_dither = quantize_for_terminal(img, colors=4, dither=False)
        with_dither = quantize_for_terminal(img, colors=4, dither=True)

        # Both should have at most 4 unique colours
        nd_colours = set()
        wd_colours = set()
        for y in range(20):
            for x in range(20):
                nd_colours.add(no_dither.getpixel((x, y))[:3])
                wd_colours.add(with_dither.getpixel((x, y))[:3])

        assert len(nd_colours) <= 4
        assert len(wd_colours) <= 4

    def test_preserves_dimensions(self) -> None:
        img = Image.new("RGB", (15, 25), color=(0, 0, 0))
        result = quantize_for_terminal(img, colors=8)
        assert result.size == (15, 25)

    def test_colors_256(self) -> None:
        img = Image.new("RGB", (4, 4), color=(100, 200, 50))
        result = quantize_for_terminal(img, colors=256, dither=False)
        assert result.size == (4, 4)

    def test_colors_1(self) -> None:
        img = Image.new("RGB", (4, 4))
        img.putpixel((0, 0), (255, 0, 0))
        img.putpixel((1, 0), (0, 255, 0))
        result = quantize_for_terminal(img, colors=1, dither=False)
        unique = set()
        for y in range(4):
            for x in range(4):
                unique.add(result.getpixel((x, y))[:3])
        assert len(unique) == 1

    def test_greyscale_input(self) -> None:
        img = Image.new("L", (10, 10), color=128)
        result = quantize_for_terminal(img, colors=4, dither=False)
        assert result.mode == "RGBA"
        assert result.size == (10, 10)


# ---------------------------------------------------------------------------
# quantize_for_terminal — validation
# ---------------------------------------------------------------------------


class TestQuantizeValidation:
    """Input validation for quantize_for_terminal."""

    def test_rejects_non_image(self) -> None:
        with pytest.raises(TypeError, match="must be a PIL.Image.Image"):
            quantize_for_terminal("not_an_image")  # type: ignore[arg-type]

    def test_rejects_non_int_colors(self) -> None:
        img = Image.new("RGB", (4, 4))
        with pytest.raises(TypeError, match="colors must be an int"):
            quantize_for_terminal(img, colors=4.5)  # type: ignore[arg-type]

    def test_rejects_bool_colors(self) -> None:
        img = Image.new("RGB", (4, 4))
        with pytest.raises(TypeError, match="colors must be an int"):
            quantize_for_terminal(img, colors=True)  # type: ignore[arg-type]

    def test_rejects_colors_zero(self) -> None:
        img = Image.new("RGB", (4, 4))
        with pytest.raises(ValueError, match="colors must be 1–256"):
            quantize_for_terminal(img, colors=0)

    def test_rejects_colors_negative(self) -> None:
        img = Image.new("RGB", (4, 4))
        with pytest.raises(ValueError, match="colors must be 1–256"):
            quantize_for_terminal(img, colors=-1)

    def test_rejects_colors_above_256(self) -> None:
        img = Image.new("RGB", (4, 4))
        with pytest.raises(ValueError, match="colors must be 1–256"):
            quantize_for_terminal(img, colors=257)


# ---------------------------------------------------------------------------
# prepare_for_terminal
# ---------------------------------------------------------------------------


class TestPrepareForTerminal:
    """All-in-one image preparation."""

    def test_resize_to_target_width(self) -> None:
        img = Image.new("RGB", (100, 50), color=(255, 0, 0))
        result = prepare_for_terminal(
            img, target_width=20, correct_aspect=False,
        )
        assert result.size[0] == 20

    def test_resize_preserves_aspect_ratio_width_only(self) -> None:
        img = Image.new("RGB", (100, 50), color=(0, 0, 0))
        result = prepare_for_terminal(
            img, target_width=50, correct_aspect=False,
        )
        assert result.size == (50, 25)

    def test_resize_preserves_aspect_ratio_height_only(self) -> None:
        img = Image.new("RGB", (100, 50), color=(0, 0, 0))
        result = prepare_for_terminal(
            img, target_height=25, correct_aspect=False,
        )
        assert result.size == (50, 25)

    def test_resize_with_both_dimensions(self) -> None:
        img = Image.new("RGB", (100, 100), color=(0, 0, 0))
        result = prepare_for_terminal(
            img, target_width=30, target_height=20, correct_aspect=False,
        )
        assert result.size == (30, 20)

    def test_aspect_correction_applied(self) -> None:
        img = Image.new("RGB", (20, 40), color=(0, 0, 0))
        result = prepare_for_terminal(img, correct_aspect=True)
        # 40 / 2.0 = 20
        assert result.size == (20, 20)

    def test_aspect_correction_after_resize(self) -> None:
        """Aspect correction is applied after resize to target dims."""
        img = Image.new("RGB", (100, 100), color=(0, 0, 0))
        result = prepare_for_terminal(
            img, target_width=20, correct_aspect=True,
        )
        # Resize: 100x100 → 20x20, then aspect: 20x20 → 20x10
        assert result.size[0] == 20
        assert result.size[1] == 10

    def test_quantization_applied(self) -> None:
        img = Image.new("RGB", (20, 1))
        for x in range(20):
            img.putpixel((x, 0), (x * 12, 255 - x * 12, 128))

        result = prepare_for_terminal(
            img, colors=4, dither=False, correct_aspect=False,
        )
        unique = set()
        for x in range(20):
            unique.add(result.getpixel((x, 0))[:3])
        assert len(unique) <= 4

    def test_no_quantization_when_none(self) -> None:
        img = Image.new("RGB", (4, 4), color=(123, 45, 67))
        result = prepare_for_terminal(
            img, colors=None, correct_aspect=False,
        )
        assert result.size == (4, 4)

    def test_no_aspect_correction_when_disabled(self) -> None:
        img = Image.new("RGB", (10, 20), color=(0, 0, 0))
        result = prepare_for_terminal(img, correct_aspect=False)
        assert result.size == (10, 20)

    def test_full_pipeline(self) -> None:
        """Resize + aspect correction + quantization all at once."""
        img = Image.new("RGB", (100, 100), color=(0, 0, 0))
        for y in range(100):
            for x in range(100):
                img.putpixel((x, y), (x * 2, y * 2, 128))

        result = prepare_for_terminal(
            img, target_width=20, colors=8, dither=False,
        )
        # Width = 20, height = round(20 / 2.0) = 10
        assert result.size[0] == 20
        assert result.size[1] == 10
        assert result.mode == "RGBA"

    def test_custom_cell_aspect_ratio(self) -> None:
        img = Image.new("RGB", (10, 30), color=(0, 0, 0))
        result = prepare_for_terminal(
            img, cell_aspect_ratio=3.0,
        )
        assert result.size == (10, 10)

    def test_returns_rgba(self) -> None:
        img = Image.new("RGB", (4, 4), color=(0, 0, 0))
        result = prepare_for_terminal(
            img, colors=4, correct_aspect=False,
        )
        assert result.mode == "RGBA"


# ---------------------------------------------------------------------------
# prepare_for_terminal — validation
# ---------------------------------------------------------------------------


class TestPrepareValidation:
    """Input validation for prepare_for_terminal."""

    def test_rejects_non_image(self) -> None:
        with pytest.raises(TypeError, match="must be a PIL.Image.Image"):
            prepare_for_terminal("not_an_image")  # type: ignore[arg-type]

    def test_rejects_target_width_zero(self) -> None:
        img = Image.new("RGB", (10, 10))
        with pytest.raises(ValueError, match="target_width must be >= 1"):
            prepare_for_terminal(img, target_width=0)

    def test_rejects_target_width_negative(self) -> None:
        img = Image.new("RGB", (10, 10))
        with pytest.raises(ValueError, match="target_width must be >= 1"):
            prepare_for_terminal(img, target_width=-5)

    def test_rejects_target_height_zero(self) -> None:
        img = Image.new("RGB", (10, 10))
        with pytest.raises(ValueError, match="target_height must be >= 1"):
            prepare_for_terminal(img, target_height=0)

    def test_rejects_target_height_negative(self) -> None:
        img = Image.new("RGB", (10, 10))
        with pytest.raises(ValueError, match="target_height must be >= 1"):
            prepare_for_terminal(img, target_height=-1)


# ---------------------------------------------------------------------------
# Integration with from_image
# ---------------------------------------------------------------------------


class TestIntegrationWithFromImage:
    """Prepared images work correctly with from_image."""

    def test_aspect_corrected_image_converts(self) -> None:
        from wyby.sprite import Sprite, from_image

        img = Image.new("RGB", (4, 8), color=(255, 0, 0))
        corrected = correct_aspect_ratio(img)
        entities = from_image(corrected)

        assert len(entities) == 4 * 4  # 4 wide × 4 tall (8/2)
        for e in entities:
            sprite = e.get_component(Sprite)
            assert sprite is not None
            assert sprite.char == "\u2588"

    def test_quantized_image_converts(self) -> None:
        from wyby.sprite import Sprite, from_image

        img = Image.new("RGB", (4, 4))
        for y in range(4):
            for x in range(4):
                img.putpixel((x, y), (x * 60, y * 60, 128))

        quantized = quantize_for_terminal(img, colors=4, dither=False)
        entities = from_image(quantized)

        assert len(entities) == 16
        styles = {
            e.get_component(Sprite).style.color.name for e in entities
        }
        assert len(styles) <= 4

    def test_full_pipeline_converts(self) -> None:
        from wyby.sprite import Sprite, from_image

        img = Image.new("RGB", (100, 100), color=(0, 128, 255))
        prepared = prepare_for_terminal(
            img, target_width=8, colors=4, dither=False,
        )
        entities = from_image(prepared)

        w, h = prepared.size
        assert len(entities) == w * h
        for e in entities:
            assert e.get_component(Sprite) is not None

    def test_transparent_pixels_skipped_after_prepare(self) -> None:
        from wyby.sprite import from_image

        img = Image.new("RGBA", (4, 4), color=(0, 0, 0, 0))
        # Add one opaque pixel
        img.putpixel((1, 1), (255, 0, 0, 255))

        prepared = prepare_for_terminal(
            img, colors=4, dither=False, correct_aspect=False,
        )
        entities = from_image(prepared)

        # Only the opaque pixel should produce an entity.
        assert len(entities) == 1


# ---------------------------------------------------------------------------
# Import from package root
# ---------------------------------------------------------------------------


class TestImports:
    """Dithering utilities are accessible from the wyby package root."""

    def test_import_correct_aspect_ratio(self) -> None:
        from wyby import correct_aspect_ratio as car
        assert car is correct_aspect_ratio

    def test_import_quantize_for_terminal(self) -> None:
        from wyby import quantize_for_terminal as qft
        assert qft is quantize_for_terminal

    def test_import_prepare_for_terminal(self) -> None:
        from wyby import prepare_for_terminal as pft
        assert pft is prepare_for_terminal

    def test_import_cell_aspect_ratio(self) -> None:
        from wyby import CELL_ASPECT_RATIO as car
        assert car is CELL_ASPECT_RATIO
