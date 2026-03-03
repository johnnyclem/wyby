"""Tests for the compatibility_matrix module.

Validates the terminal compatibility matrix data model, lookup helpers,
filtering, and Markdown formatting.

Caveats:
    - These tests validate structure and consistency of the catalog
      data, not actual terminal capabilities.  The matrix is manually
      maintained — these tests catch structural errors (missing
      features, invalid support levels) but cannot verify that the
      catalogued support levels are accurate.
"""

from __future__ import annotations

import pytest

from wyby.compatibility_matrix import (
    FEATURES,
    SUPPORT_LEVELS,
    TERMINALS,
    TerminalInfo,
    format_compatibility_matrix,
    get_fully_supported_terminals,
    get_support,
    get_terminal,
    get_terminals_by_platform,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


class TestConstants:
    """FEATURES, SUPPORT_LEVELS, and TERMINALS constants."""

    def test_features_is_tuple(self) -> None:
        assert isinstance(FEATURES, tuple)

    def test_features_non_empty(self) -> None:
        assert len(FEATURES) > 0

    def test_features_contains_truecolor(self) -> None:
        assert "truecolor" in FEATURES

    def test_features_contains_alt_screen(self) -> None:
        assert "alt_screen" in FEATURES

    def test_features_contains_mouse_click(self) -> None:
        assert "mouse_click" in FEATURES

    def test_features_contains_key_sequences(self) -> None:
        assert "key_sequences" in FEATURES

    def test_support_levels_is_frozenset(self) -> None:
        assert isinstance(SUPPORT_LEVELS, frozenset)

    def test_support_levels_values(self) -> None:
        assert SUPPORT_LEVELS == {"full", "partial", "none"}

    def test_terminals_is_tuple(self) -> None:
        assert isinstance(TERMINALS, tuple)

    def test_terminals_non_empty(self) -> None:
        assert len(TERMINALS) > 0


# ---------------------------------------------------------------------------
# TerminalInfo data model
# ---------------------------------------------------------------------------


class TestTerminalInfo:
    """TerminalInfo construction and attributes."""

    def test_attributes(self) -> None:
        t = TerminalInfo(
            id="test",
            name="Test Terminal",
            platform="linux",
            support={"truecolor": "full"},
        )
        assert t.id == "test"
        assert t.name == "Test Terminal"
        assert t.platform == "linux"
        assert t.support["truecolor"] == "full"

    def test_default_notes(self) -> None:
        t = TerminalInfo(
            id="test",
            name="Test",
            platform="linux",
            support={},
        )
        assert t.notes == {}

    def test_default_general_notes(self) -> None:
        t = TerminalInfo(
            id="test",
            name="Test",
            platform="linux",
            support={},
        )
        assert t.general_notes == ""

    def test_frozen(self) -> None:
        t = TerminalInfo(
            id="test",
            name="Test",
            platform="linux",
            support={},
        )
        with pytest.raises(AttributeError):
            t.id = "changed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Catalog consistency
# ---------------------------------------------------------------------------


class TestCatalogConsistency:
    """Every terminal in TERMINALS has valid, complete data."""

    def test_all_terminals_have_unique_ids(self) -> None:
        ids = [t.id for t in TERMINALS]
        assert len(ids) == len(set(ids)), (
            f"Duplicate terminal IDs: "
            f"{[x for x in ids if ids.count(x) > 1]}"
        )

    def test_all_terminals_cover_all_features(self) -> None:
        """Every terminal must have a support entry for every feature."""
        for terminal in TERMINALS:
            for feature in FEATURES:
                assert feature in terminal.support, (
                    f"Terminal {terminal.id!r} missing feature "
                    f"{feature!r} in support dict"
                )

    def test_all_support_values_valid(self) -> None:
        """Every support value must be one of the valid levels."""
        for terminal in TERMINALS:
            for feature, level in terminal.support.items():
                assert level in SUPPORT_LEVELS, (
                    f"Terminal {terminal.id!r} feature {feature!r} has "
                    f"invalid support level {level!r}"
                )

    def test_all_note_keys_are_valid_features(self) -> None:
        """Note keys must correspond to known features."""
        for terminal in TERMINALS:
            for key in terminal.notes:
                assert key in FEATURES, (
                    f"Terminal {terminal.id!r} has note for unknown "
                    f"feature {key!r}"
                )

    def test_all_terminals_have_platform(self) -> None:
        valid_platforms = {"linux", "macos", "windows", "cross-platform"}
        for terminal in TERMINALS:
            assert terminal.platform in valid_platforms, (
                f"Terminal {terminal.id!r} has invalid platform "
                f"{terminal.platform!r}"
            )

    def test_all_terminals_have_name(self) -> None:
        for terminal in TERMINALS:
            assert terminal.name, (
                f"Terminal {terminal.id!r} has empty name"
            )


# ---------------------------------------------------------------------------
# get_terminal
# ---------------------------------------------------------------------------


class TestGetTerminal:
    """get_terminal() lookup by ID."""

    def test_known_terminal(self) -> None:
        t = get_terminal("kitty")
        assert t.id == "kitty"
        assert t.name == "kitty"

    def test_windows_terminal(self) -> None:
        t = get_terminal("windows_terminal")
        assert t.name == "Windows Terminal"

    def test_unknown_terminal_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown terminal"):
            get_terminal("nonexistent")

    def test_all_catalog_terminals_findable(self) -> None:
        for terminal in TERMINALS:
            found = get_terminal(terminal.id)
            assert found is terminal


# ---------------------------------------------------------------------------
# get_support
# ---------------------------------------------------------------------------


class TestGetSupport:
    """get_support() queries terminal + feature pairs."""

    def test_known_pair(self) -> None:
        level = get_support("kitty", "truecolor")
        assert level == "full"

    def test_partial_support(self) -> None:
        level = get_support("macos_terminal", "truecolor")
        assert level == "partial"

    def test_no_support(self) -> None:
        level = get_support("conhost", "truecolor")
        assert level == "none"

    def test_unknown_terminal_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown terminal"):
            get_support("fake_terminal", "truecolor")

    def test_unknown_feature_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown feature"):
            get_support("kitty", "fake_feature")


# ---------------------------------------------------------------------------
# get_terminals_by_platform
# ---------------------------------------------------------------------------


class TestGetTerminalsByPlatform:
    """get_terminals_by_platform() filtering."""

    def test_linux_returns_terminals(self) -> None:
        result = get_terminals_by_platform("linux")
        assert len(result) > 0
        for t in result:
            assert t.platform == "linux"

    def test_macos_returns_terminals(self) -> None:
        result = get_terminals_by_platform("macos")
        assert len(result) > 0
        for t in result:
            assert t.platform == "macos"

    def test_windows_returns_terminals(self) -> None:
        result = get_terminals_by_platform("windows")
        assert len(result) > 0
        for t in result:
            assert t.platform == "windows"

    def test_cross_platform_returns_terminals(self) -> None:
        result = get_terminals_by_platform("cross-platform")
        assert len(result) > 0
        for t in result:
            assert t.platform == "cross-platform"

    def test_unknown_platform_returns_empty(self) -> None:
        result = get_terminals_by_platform("freebsd")
        assert result == ()

    def test_returns_tuple(self) -> None:
        result = get_terminals_by_platform("linux")
        assert isinstance(result, tuple)


# ---------------------------------------------------------------------------
# get_fully_supported_terminals
# ---------------------------------------------------------------------------


class TestGetFullySupportedTerminals:
    """get_fully_supported_terminals() filtering."""

    def test_truecolor_full_support(self) -> None:
        result = get_fully_supported_terminals("truecolor")
        assert len(result) > 0
        for t in result:
            assert t.support["truecolor"] == "full"

    def test_excludes_partial(self) -> None:
        result = get_fully_supported_terminals("truecolor")
        ids = {t.id for t in result}
        # macOS Terminal.app has partial truecolor.
        assert "macos_terminal" not in ids

    def test_excludes_none(self) -> None:
        result = get_fully_supported_terminals("truecolor")
        ids = {t.id for t in result}
        # conhost has no truecolor.
        assert "conhost" not in ids

    def test_unknown_feature_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown feature"):
            get_fully_supported_terminals("nonexistent_feature")

    def test_returns_tuple(self) -> None:
        result = get_fully_supported_terminals("alt_screen")
        assert isinstance(result, tuple)


# ---------------------------------------------------------------------------
# format_compatibility_matrix
# ---------------------------------------------------------------------------


class TestFormatCompatibilityMatrix:
    """format_compatibility_matrix() Markdown output."""

    def test_returns_string(self) -> None:
        result = format_compatibility_matrix()
        assert isinstance(result, str)

    def test_contains_title(self) -> None:
        result = format_compatibility_matrix()
        assert "# wyby Terminal Compatibility Matrix" in result

    def test_contains_caveats_section(self) -> None:
        result = format_compatibility_matrix()
        assert "## Important Caveats" in result

    def test_contains_support_matrix_section(self) -> None:
        result = format_compatibility_matrix()
        assert "## Support Matrix" in result

    def test_contains_terminal_details_section(self) -> None:
        result = format_compatibility_matrix()
        assert "## Terminal Details" in result

    def test_contains_recommendations_section(self) -> None:
        result = format_compatibility_matrix()
        assert "## Recommendations" in result

    def test_contains_all_terminal_names(self) -> None:
        result = format_compatibility_matrix()
        for terminal in TERMINALS:
            assert terminal.name in result, (
                f"Terminal {terminal.name!r} not found in output"
            )

    def test_contains_markdown_table(self) -> None:
        result = format_compatibility_matrix()
        assert "| Terminal |" in result
        # Check for table separator row.
        assert "|---" in result

    def test_contains_feature_labels(self) -> None:
        result = format_compatibility_matrix()
        assert "Truecolor" in result
        assert "Alt Screen" in result
        assert "Mouse Click" in result

    def test_contains_support_symbols(self) -> None:
        result = format_compatibility_matrix()
        assert "Yes" in result
        assert "Partial" in result
        assert "No" in result

    def test_contains_best_terminals(self) -> None:
        result = format_compatibility_matrix()
        assert "Best terminals for wyby" in result

    def test_contains_terminals_to_avoid(self) -> None:
        result = format_compatibility_matrix()
        assert "Terminals to avoid" in result

    def test_contains_cross_platform_tips(self) -> None:
        result = format_compatibility_matrix()
        assert "cross-platform games" in result

    def test_non_empty_output(self) -> None:
        result = format_compatibility_matrix()
        assert len(result) > 500


# ---------------------------------------------------------------------------
# Package-level exports
# ---------------------------------------------------------------------------


class TestCompatibilityMatrixExports:
    """New types should be importable from the top-level package."""

    def test_terminal_info_importable(self) -> None:
        from wyby import TerminalInfo as TI

        assert TI is TerminalInfo

    def test_terminals_importable(self) -> None:
        from wyby import TERMINALS as T

        assert T is TERMINALS

    def test_features_importable(self) -> None:
        from wyby import MATRIX_FEATURES

        assert MATRIX_FEATURES is FEATURES

    def test_support_levels_importable(self) -> None:
        from wyby import SUPPORT_LEVELS as SL

        assert SL is SUPPORT_LEVELS

    def test_get_terminal_importable(self) -> None:
        from wyby import get_terminal as gt

        assert gt is get_terminal

    def test_get_support_importable(self) -> None:
        from wyby import get_support as gs

        assert gs is get_support

    def test_get_terminals_by_platform_importable(self) -> None:
        from wyby import get_terminals_by_platform as gtp

        assert gtp is get_terminals_by_platform

    def test_get_fully_supported_terminals_importable(self) -> None:
        from wyby import get_fully_supported_terminals as gfst

        assert gfst is get_fully_supported_terminals

    def test_format_compatibility_matrix_importable(self) -> None:
        from wyby import format_compatibility_matrix as fcm

        assert fcm is format_compatibility_matrix

    def test_in_all(self) -> None:
        import wyby

        expected = [
            "MATRIX_FEATURES",
            "SUPPORT_LEVELS",
            "TERMINALS",
            "TerminalInfo",
            "format_compatibility_matrix",
            "get_fully_supported_terminals",
            "get_support",
            "get_terminal",
            "get_terminals_by_platform",
        ]
        for name in expected:
            assert name in wyby.__all__, (
                f"{name!r} not found in wyby.__all__"
            )
