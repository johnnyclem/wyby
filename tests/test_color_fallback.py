"""Tests for wyby.color — colour fallback and palette utilities."""

from __future__ import annotations

from wyby.color import (
    _ANSI_16_COLORS,
    _ANSI_16_NAMES,
    _ANSI_256_PALETTE,
    color_system_for_support,
    downgrade_color,
    nearest_ansi16,
    nearest_ansi256,
    parse_color,
)
from wyby.diagnostics import ColorSupport


# ---------------------------------------------------------------------------
# color_system_for_support
# ---------------------------------------------------------------------------


class TestColorSystemForSupport:
    """Map ColorSupport to Rich color_system strings."""

    def test_none(self) -> None:
        assert color_system_for_support(ColorSupport.NONE) is None

    def test_standard(self) -> None:
        assert color_system_for_support(ColorSupport.STANDARD) == "standard"

    def test_extended(self) -> None:
        assert color_system_for_support(ColorSupport.EXTENDED) == "256"

    def test_truecolor(self) -> None:
        assert color_system_for_support(ColorSupport.TRUECOLOR) == "truecolor"


# ---------------------------------------------------------------------------
# Palette construction
# ---------------------------------------------------------------------------


class TestPalette:
    """Verify the pre-computed palette tables."""

    def test_ansi_16_length(self) -> None:
        assert len(_ANSI_16_COLORS) == 16

    def test_ansi_16_names_length(self) -> None:
        assert len(_ANSI_16_NAMES) == 16

    def test_ansi_256_length(self) -> None:
        assert len(_ANSI_256_PALETTE) == 256

    def test_ansi_256_starts_with_16(self) -> None:
        """First 16 entries of 256 palette should match ANSI 16."""
        for i in range(16):
            assert _ANSI_256_PALETTE[i] == _ANSI_16_COLORS[i]

    def test_ansi_256_cube_origin(self) -> None:
        """Index 16 should be (0, 0, 0) — the cube origin."""
        assert _ANSI_256_PALETTE[16] == (0, 0, 0)

    def test_ansi_256_cube_white(self) -> None:
        """Index 231 should be (255, 255, 255) — the cube maximum."""
        assert _ANSI_256_PALETTE[231] == (255, 255, 255)

    def test_ansi_256_greyscale_start(self) -> None:
        """Index 232 starts the greyscale ramp at rgb(8, 8, 8)."""
        assert _ANSI_256_PALETTE[232] == (8, 8, 8)

    def test_ansi_256_greyscale_end(self) -> None:
        """Index 255 ends the greyscale ramp at rgb(238, 238, 238)."""
        assert _ANSI_256_PALETTE[255] == (238, 238, 238)

    def test_ansi_256_known_cube_value(self) -> None:
        """Index 196 should be pure red in the cube: (255, 0, 0)."""
        # 196 = 16 + 36*5 + 6*0 + 0 = 16 + 180 = 196
        assert _ANSI_256_PALETTE[196] == (255, 0, 0)


# ---------------------------------------------------------------------------
# parse_color
# ---------------------------------------------------------------------------


class TestParseColor:
    """parse_color() should handle hex, rgb(), color(N), and named colours."""

    def test_hex_6_digit(self) -> None:
        assert parse_color("#ff0000") == (255, 0, 0)

    def test_hex_3_digit(self) -> None:
        assert parse_color("#f00") == (255, 0, 0)

    def test_hex_mixed_case(self) -> None:
        assert parse_color("#FF8800") == (255, 136, 0)

    def test_hex_black(self) -> None:
        assert parse_color("#000000") == (0, 0, 0)

    def test_hex_white(self) -> None:
        assert parse_color("#ffffff") == (255, 255, 255)

    def test_rgb_function(self) -> None:
        assert parse_color("rgb(128, 64, 32)") == (128, 64, 32)

    def test_rgb_no_spaces(self) -> None:
        assert parse_color("rgb(128,64,32)") == (128, 64, 32)

    def test_rgb_out_of_range(self) -> None:
        assert parse_color("rgb(256, 0, 0)") is None

    def test_color_index(self) -> None:
        assert parse_color("color(196)") == (255, 0, 0)

    def test_color_index_zero(self) -> None:
        assert parse_color("color(0)") == (0, 0, 0)

    def test_color_index_out_of_range(self) -> None:
        assert parse_color("color(256)") is None

    def test_named_red(self) -> None:
        assert parse_color("red") == (128, 0, 0)

    def test_named_bright_cyan(self) -> None:
        assert parse_color("bright_cyan") == (0, 255, 255)

    def test_named_case_insensitive(self) -> None:
        assert parse_color("Red") == (128, 0, 0)
        assert parse_color("BLUE") == (0, 0, 128)

    def test_empty_string(self) -> None:
        assert parse_color("") is None

    def test_unrecognised(self) -> None:
        assert parse_color("dark_orange") is None

    def test_invalid_hex(self) -> None:
        assert parse_color("#xyz") is None

    def test_hex_wrong_length(self) -> None:
        assert parse_color("#ff00") is None


# ---------------------------------------------------------------------------
# nearest_ansi16
# ---------------------------------------------------------------------------


class TestNearestAnsi16:
    """nearest_ansi16() should return the closest ANSI 16 name."""

    def test_exact_black(self) -> None:
        assert nearest_ansi16(0, 0, 0) == "black"

    def test_exact_bright_white(self) -> None:
        assert nearest_ansi16(255, 255, 255) == "bright_white"

    def test_exact_bright_red(self) -> None:
        assert nearest_ansi16(255, 0, 0) == "bright_red"

    def test_near_red(self) -> None:
        """A colour close to dark red should map to 'red'."""
        assert nearest_ansi16(140, 10, 10) == "red"

    def test_near_bright_green(self) -> None:
        assert nearest_ansi16(10, 240, 10) == "bright_green"

    def test_grey_maps_to_bright_black_or_white(self) -> None:
        """Mid-grey should map to one of the grey entries."""
        result = nearest_ansi16(128, 128, 128)
        assert result in ("bright_black", "white")

    def test_returns_string(self) -> None:
        result = nearest_ansi16(100, 50, 200)
        assert isinstance(result, str)
        assert result in _ANSI_16_NAMES


# ---------------------------------------------------------------------------
# nearest_ansi256
# ---------------------------------------------------------------------------


class TestNearestAnsi256:
    """nearest_ansi256() should return the closest 256-colour index."""

    def test_exact_black(self) -> None:
        # (0,0,0) matches index 0 (black) and index 16 (cube origin).
        # Either is acceptable; both have distance 0.
        idx = nearest_ansi256(0, 0, 0)
        assert _ANSI_256_PALETTE[idx] == (0, 0, 0)

    def test_exact_white(self) -> None:
        idx = nearest_ansi256(255, 255, 255)
        assert _ANSI_256_PALETTE[idx] == (255, 255, 255)

    def test_exact_cube_red(self) -> None:
        """Pure red should match index 196 (cube) or 9 (bright_red)."""
        idx = nearest_ansi256(255, 0, 0)
        assert _ANSI_256_PALETTE[idx] == (255, 0, 0)

    def test_mid_grey(self) -> None:
        """Mid-grey should map to one of the greyscale ramp entries."""
        idx = nearest_ansi256(128, 128, 128)
        # Index 8 is bright_black (128,128,128) — exact match.
        assert _ANSI_256_PALETTE[idx] == (128, 128, 128)

    def test_returns_int_in_range(self) -> None:
        idx = nearest_ansi256(100, 50, 200)
        assert isinstance(idx, int)
        assert 0 <= idx <= 255

    def test_arbitrary_color(self) -> None:
        """An arbitrary colour should return a nearby palette entry."""
        idx = nearest_ansi256(200, 100, 50)
        pr, pg, pb = _ANSI_256_PALETTE[idx]
        # Distance should be reasonable (< 50 per channel on average).
        assert abs(pr - 200) < 60
        assert abs(pg - 100) < 60
        assert abs(pb - 50) < 60


# ---------------------------------------------------------------------------
# downgrade_color
# ---------------------------------------------------------------------------


class TestDowngradeColor:
    """downgrade_color() should convert colours to the target level."""

    # -- None input/output --

    def test_none_input_returns_none(self) -> None:
        assert downgrade_color(None, ColorSupport.TRUECOLOR) is None

    def test_none_target_returns_none(self) -> None:
        assert downgrade_color("#ff0000", ColorSupport.NONE) is None

    def test_none_input_none_target(self) -> None:
        assert downgrade_color(None, ColorSupport.NONE) is None

    # -- Named ANSI colours (already STANDARD) --

    def test_named_at_standard(self) -> None:
        assert downgrade_color("red", ColorSupport.STANDARD) == "red"

    def test_named_at_extended(self) -> None:
        assert downgrade_color("bright_cyan", ColorSupport.EXTENDED) == "bright_cyan"

    def test_named_at_truecolor(self) -> None:
        assert downgrade_color("blue", ColorSupport.TRUECOLOR) == "blue"

    # -- color(N) at various targets --

    def test_color_n_at_extended(self) -> None:
        assert downgrade_color("color(196)", ColorSupport.EXTENDED) == "color(196)"

    def test_color_n_at_truecolor(self) -> None:
        assert downgrade_color("color(42)", ColorSupport.TRUECOLOR) == "color(42)"

    def test_color_n_at_standard(self) -> None:
        """color(196) is (255,0,0) — should downgrade to bright_red."""
        result = downgrade_color("color(196)", ColorSupport.STANDARD)
        assert result == "bright_red"

    def test_color_n_at_standard_blue(self) -> None:
        """color(21) is (0,0,255) — should downgrade to bright_blue."""
        result = downgrade_color("color(21)", ColorSupport.STANDARD)
        assert result == "bright_blue"

    # -- Hex colours at various targets --

    def test_hex_at_truecolor(self) -> None:
        assert downgrade_color("#ff0000", ColorSupport.TRUECOLOR) == "#ff0000"

    def test_hex_at_extended(self) -> None:
        """Hex should be converted to color(N) at EXTENDED level."""
        result = downgrade_color("#ff0000", ColorSupport.EXTENDED)
        assert result is not None
        assert result.startswith("color(")

    def test_hex_at_standard(self) -> None:
        """Hex pure red should map to bright_red at STANDARD level."""
        result = downgrade_color("#ff0000", ColorSupport.STANDARD)
        assert result == "bright_red"

    def test_hex_at_standard_green(self) -> None:
        result = downgrade_color("#00ff00", ColorSupport.STANDARD)
        assert result == "bright_green"

    # -- rgb() colours --

    def test_rgb_at_truecolor(self) -> None:
        assert downgrade_color("rgb(255,0,0)", ColorSupport.TRUECOLOR) == "rgb(255,0,0)"

    def test_rgb_at_extended(self) -> None:
        result = downgrade_color("rgb(255,0,0)", ColorSupport.EXTENDED)
        assert result is not None
        assert result.startswith("color(")

    def test_rgb_at_standard(self) -> None:
        result = downgrade_color("rgb(0,0,255)", ColorSupport.STANDARD)
        assert result == "bright_blue"

    # -- Unrecognised strings --

    def test_unrecognised_passthrough(self) -> None:
        """Unknown colour strings should pass through unchanged."""
        assert downgrade_color("dark_orange", ColorSupport.STANDARD) == "dark_orange"


# ---------------------------------------------------------------------------
# Round-trip consistency
# ---------------------------------------------------------------------------


class TestRoundTrip:
    """Downgrading and re-parsing should produce consistent results."""

    def test_hex_to_256_to_parse(self) -> None:
        """Downgrade hex to 256, then parse the result back to RGB."""
        result = downgrade_color("#c08040", ColorSupport.EXTENDED)
        assert result is not None
        rgb = parse_color(result)
        assert rgb is not None
        # The round-tripped colour should be close to the original.
        assert abs(rgb[0] - 0xc0) < 50
        assert abs(rgb[1] - 0x80) < 50
        assert abs(rgb[2] - 0x40) < 50

    def test_hex_to_16_to_parse(self) -> None:
        """Downgrade hex to 16, then parse the result back to RGB."""
        result = downgrade_color("#ff0000", ColorSupport.STANDARD)
        assert result is not None
        rgb = parse_color(result)
        assert rgb is not None
        # bright_red is (255, 0, 0)
        assert rgb == (255, 0, 0)


# ---------------------------------------------------------------------------
# Package-level exports
# ---------------------------------------------------------------------------


class TestColorExports:
    """New functions should be importable from the top-level package."""

    def test_color_system_for_support_importable(self) -> None:
        from wyby import color_system_for_support as csfs

        assert csfs is color_system_for_support

    def test_downgrade_color_importable(self) -> None:
        from wyby import downgrade_color as dc

        assert dc is downgrade_color

    def test_nearest_ansi16_importable(self) -> None:
        from wyby import nearest_ansi16 as na16

        assert na16 is nearest_ansi16

    def test_nearest_ansi256_importable(self) -> None:
        from wyby import nearest_ansi256 as na256

        assert na256 is nearest_ansi256

    def test_parse_color_importable(self) -> None:
        from wyby import parse_color as pc

        assert pc is parse_color

    def test_in_all(self) -> None:
        import wyby

        for name in (
            "color_system_for_support",
            "downgrade_color",
            "nearest_ansi16",
            "nearest_ansi256",
            "parse_color",
        ):
            assert name in wyby.__all__
