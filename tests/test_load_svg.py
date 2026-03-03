"""Tests for wyby.dithering.load_svg — SVG rasterization via cairosvg."""

from __future__ import annotations

import os
import tempfile
from unittest import mock

import pytest
from PIL import Image

from wyby.dithering import load_svg


# Minimal valid SVG used across tests.
_SIMPLE_SVG = (
    b'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">'
    b'<rect width="10" height="10" fill="red"/>'
    b"</svg>"
)

_TRANSPARENT_SVG = (
    b'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">'
    b'<rect width="10" height="10" fill="none"/>'
    b"</svg>"
)


# ---------------------------------------------------------------------------
# Basic functionality
# ---------------------------------------------------------------------------


class TestLoadSvgBasic:
    """Core load_svg behaviour with simple SVGs."""

    def test_bytes_input_returns_image(self) -> None:
        img = load_svg(_SIMPLE_SVG)
        assert isinstance(img, Image.Image)

    def test_output_mode_is_rgba(self) -> None:
        img = load_svg(_SIMPLE_SVG)
        assert img.mode == "RGBA"

    def test_dimensions_match_svg_viewbox(self) -> None:
        img = load_svg(_SIMPLE_SVG)
        assert img.width == 10
        assert img.height == 10

    def test_red_fill_produces_red_pixels(self) -> None:
        img = load_svg(_SIMPLE_SVG)
        r, g, b, a = img.getpixel((5, 5))
        assert r == 255
        assert g == 0
        assert b == 0
        assert a == 255

    def test_transparent_svg_has_zero_alpha(self) -> None:
        img = load_svg(_TRANSPARENT_SVG)
        _, _, _, a = img.getpixel((5, 5))
        assert a == 0

    def test_file_path_input(self) -> None:
        with tempfile.NamedTemporaryFile(
            suffix=".svg", delete=False,
        ) as f:
            f.write(_SIMPLE_SVG)
            path = f.name
        try:
            img = load_svg(path)
            assert isinstance(img, Image.Image)
            assert img.width == 10
            assert img.height == 10
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# Scaling and dimensions
# ---------------------------------------------------------------------------


class TestLoadSvgScaling:
    """Tests for scale, output_width, and output_height parameters."""

    def test_scale_doubles_dimensions(self) -> None:
        img = load_svg(_SIMPLE_SVG, scale=2.0)
        assert img.width == 20
        assert img.height == 20

    def test_output_width_overrides_intrinsic(self) -> None:
        img = load_svg(_SIMPLE_SVG, output_width=50)
        assert img.width == 50

    def test_output_height_overrides_intrinsic(self) -> None:
        img = load_svg(_SIMPLE_SVG, output_height=30)
        assert img.height == 30

    def test_output_width_preserves_aspect_ratio(self) -> None:
        svg = (
            b'<svg xmlns="http://www.w3.org/2000/svg" width="20" height="10">'
            b'<rect width="20" height="10" fill="blue"/>'
            b"</svg>"
        )
        img = load_svg(svg, output_width=40)
        assert img.width == 40
        assert img.height == 20  # 2:1 ratio preserved

    def test_both_dimensions_specified(self) -> None:
        img = load_svg(_SIMPLE_SVG, output_width=30, output_height=50)
        assert img.width == 30
        assert img.height == 50


# ---------------------------------------------------------------------------
# Pipeline integration
# ---------------------------------------------------------------------------


class TestLoadSvgPipeline:
    """Tests that load_svg output integrates with the image pipeline."""

    def test_prepare_for_terminal_accepts_svg_output(self) -> None:
        from wyby.dithering import prepare_for_terminal

        img = load_svg(_SIMPLE_SVG)
        result = prepare_for_terminal(img, target_width=5, colors=4)
        assert isinstance(result, Image.Image)
        assert result.width == 5

    def test_from_image_accepts_svg_output(self) -> None:
        from wyby.sprite import Sprite, from_image

        img = load_svg(_SIMPLE_SVG)
        entities = from_image(img)
        assert len(entities) > 0
        sprite = entities[0].get_component(Sprite)
        assert sprite is not None


# ---------------------------------------------------------------------------
# Validation and error handling
# ---------------------------------------------------------------------------


class TestLoadSvgValidation:
    """Input validation for load_svg."""

    def test_rejects_non_str_non_bytes(self) -> None:
        with pytest.raises(TypeError, match="str path or bytes"):
            load_svg(12345)  # type: ignore[arg-type]

    def test_rejects_list_input(self) -> None:
        with pytest.raises(TypeError, match="str path or bytes"):
            load_svg(["not", "svg"])  # type: ignore[arg-type]

    def test_rejects_nonexistent_file(self) -> None:
        with pytest.raises(FileNotFoundError, match="SVG file not found"):
            load_svg("/nonexistent/path/to/file.svg")

    def test_rejects_zero_scale(self) -> None:
        with pytest.raises(ValueError, match="scale must be positive"):
            load_svg(_SIMPLE_SVG, scale=0)

    def test_rejects_negative_scale(self) -> None:
        with pytest.raises(ValueError, match="scale must be positive"):
            load_svg(_SIMPLE_SVG, scale=-1.0)

    def test_rejects_zero_output_width(self) -> None:
        with pytest.raises(ValueError, match="output_width must be >= 1"):
            load_svg(_SIMPLE_SVG, output_width=0)

    def test_rejects_negative_output_height(self) -> None:
        with pytest.raises(ValueError, match="output_height must be >= 1"):
            load_svg(_SIMPLE_SVG, output_height=-5)


# ---------------------------------------------------------------------------
# Import guarding
# ---------------------------------------------------------------------------


class TestLoadSvgImportGuards:
    """Tests that clear ImportErrors are raised when dependencies are missing."""

    def test_missing_cairosvg_raises_import_error(self) -> None:
        import builtins

        real_import = builtins.__import__

        def mock_import(name: str, *args: object, **kwargs: object) -> object:
            if name == "cairosvg":
                raise ImportError("No module named 'cairosvg'")
            return real_import(name, *args, **kwargs)

        with mock.patch("builtins.__import__", side_effect=mock_import):
            with pytest.raises(ImportError, match="pip install wyby\\[svg\\]"):
                load_svg(_SIMPLE_SVG)

    def test_missing_pillow_raises_import_error(self) -> None:
        import builtins

        real_import = builtins.__import__

        def mock_import(name: str, *args: object, **kwargs: object) -> object:
            if name == "PIL":
                raise ImportError("No module named 'PIL'")
            return real_import(name, *args, **kwargs)

        with mock.patch("builtins.__import__", side_effect=mock_import):
            with pytest.raises(ImportError, match="pip install wyby\\[image\\]"):
                load_svg(_SIMPLE_SVG)


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


class TestLoadSvgExport:
    """Tests that load_svg is accessible from the public API."""

    def test_importable_from_dithering(self) -> None:
        from wyby.dithering import load_svg as _fn

        assert callable(_fn)

    def test_importable_from_package(self) -> None:
        from wyby import load_svg as _fn

        assert callable(_fn)

    def test_in_package_all(self) -> None:
        import wyby

        assert "load_svg" in wyby.__all__
