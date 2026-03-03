"""Tests for wyby.platform_info — platform differences catalog and detection."""

from __future__ import annotations

import signal
import sys

import pytest

from wyby.platform_info import (
    CATEGORIES,
    PLATFORM_DIFFERENCES,
    PlatformDifference,
    PlatformInfo,
    format_platform_report,
    get_differences_by_category,
    get_platform_info,
)


# ---------------------------------------------------------------------------
# PlatformDifference dataclass
# ---------------------------------------------------------------------------


class TestPlatformDifference:
    """PlatformDifference frozen dataclass."""

    def test_fields(self) -> None:
        diff = PlatformDifference(
            category="input",
            feature="raw_mode",
            unix_behaviour="uses termios",
            windows_behaviour="uses msvcrt",
            caveat="restore on exit",
        )
        assert diff.category == "input"
        assert diff.feature == "raw_mode"
        assert diff.unix_behaviour == "uses termios"
        assert diff.windows_behaviour == "uses msvcrt"
        assert diff.caveat == "restore on exit"

    def test_frozen(self) -> None:
        diff = PlatformDifference(
            category="input",
            feature="raw_mode",
            unix_behaviour="uses termios",
            windows_behaviour="uses msvcrt",
            caveat="",
        )
        with pytest.raises(AttributeError):
            diff.category = "other"  # type: ignore[misc]

    def test_equality(self) -> None:
        diff1 = PlatformDifference("a", "b", "c", "d", "e")
        diff2 = PlatformDifference("a", "b", "c", "d", "e")
        assert diff1 == diff2

    def test_inequality(self) -> None:
        diff1 = PlatformDifference("a", "b", "c", "d", "e")
        diff2 = PlatformDifference("a", "x", "c", "d", "e")
        assert diff1 != diff2


# ---------------------------------------------------------------------------
# PLATFORM_DIFFERENCES catalog
# ---------------------------------------------------------------------------


class TestPlatformDifferencesCatalog:
    """The built-in catalog of platform differences."""

    def test_is_tuple(self) -> None:
        assert isinstance(PLATFORM_DIFFERENCES, tuple)

    def test_not_empty(self) -> None:
        assert len(PLATFORM_DIFFERENCES) > 0

    def test_all_entries_are_platform_difference(self) -> None:
        for diff in PLATFORM_DIFFERENCES:
            assert isinstance(diff, PlatformDifference)

    def test_all_fields_non_empty(self) -> None:
        """Every entry should have all fields populated."""
        for diff in PLATFORM_DIFFERENCES:
            assert diff.category, f"Empty category in {diff.feature}"
            assert diff.feature, f"Empty feature in {diff}"
            assert diff.unix_behaviour, f"Empty unix_behaviour in {diff.feature}"
            assert diff.windows_behaviour, f"Empty windows_behaviour in {diff.feature}"
            # caveat can be empty but in our catalog it's always populated.
            assert diff.caveat, f"Empty caveat in {diff.feature}"

    def test_expected_categories_present(self) -> None:
        """All major subsystems should be represented."""
        categories = {d.category for d in PLATFORM_DIFFERENCES}
        assert "input" in categories
        assert "resize" in categories
        assert "terminal" in categories
        assert "timing" in categories
        assert "signals" in categories

    def test_expected_features_present(self) -> None:
        """Key features should be documented."""
        features = {d.feature for d in PLATFORM_DIFFERENCES}
        assert "raw_mode" in features
        assert "sigwinch" in features
        assert "alt_screen" in features
        assert "special_key_encoding" in features
        assert "available_signals" in features

    def test_no_duplicate_features(self) -> None:
        """Each category+feature pair should be unique."""
        seen: set[tuple[str, str]] = set()
        for diff in PLATFORM_DIFFERENCES:
            key = (diff.category, diff.feature)
            assert key not in seen, f"Duplicate entry: {key}"
            seen.add(key)


# ---------------------------------------------------------------------------
# CATEGORIES constant
# ---------------------------------------------------------------------------


class TestCategories:
    """The CATEGORIES frozenset."""

    def test_is_frozenset(self) -> None:
        assert isinstance(CATEGORIES, frozenset)

    def test_matches_catalog(self) -> None:
        """CATEGORIES should contain exactly the categories in the catalog."""
        catalog_categories = {d.category for d in PLATFORM_DIFFERENCES}
        assert CATEGORIES == catalog_categories

    def test_minimum_count(self) -> None:
        assert len(CATEGORIES) >= 5


# ---------------------------------------------------------------------------
# get_differences_by_category
# ---------------------------------------------------------------------------


class TestGetDifferencesByCategory:
    """Filtering platform differences by category."""

    def test_returns_tuple(self) -> None:
        result = get_differences_by_category("input")
        assert isinstance(result, tuple)

    def test_all_same_category(self) -> None:
        result = get_differences_by_category("input")
        for diff in result:
            assert diff.category == "input"

    def test_input_has_entries(self) -> None:
        result = get_differences_by_category("input")
        assert len(result) > 0

    def test_resize_has_entries(self) -> None:
        result = get_differences_by_category("resize")
        assert len(result) > 0

    def test_terminal_has_entries(self) -> None:
        result = get_differences_by_category("terminal")
        assert len(result) > 0

    def test_timing_has_entries(self) -> None:
        result = get_differences_by_category("timing")
        assert len(result) > 0

    def test_signals_has_entries(self) -> None:
        result = get_differences_by_category("signals")
        assert len(result) > 0

    def test_unknown_category_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown category"):
            get_differences_by_category("nonexistent")

    def test_error_message_includes_known_categories(self) -> None:
        with pytest.raises(ValueError, match="Known categories"):
            get_differences_by_category("invalid")

    def test_all_categories_retrievable(self) -> None:
        """Every category in CATEGORIES should be retrievable."""
        for cat in CATEGORIES:
            result = get_differences_by_category(cat)
            assert len(result) > 0, f"Category {cat!r} returned empty"


# ---------------------------------------------------------------------------
# PlatformInfo dataclass
# ---------------------------------------------------------------------------


class TestPlatformInfo:
    """PlatformInfo frozen dataclass."""

    def _make_info(self, **overrides: object) -> PlatformInfo:
        defaults = {
            "platform": "linux",
            "is_windows": False,
            "is_unix": True,
            "has_termios": True,
            "has_msvcrt": False,
            "has_sigwinch": True,
            "has_sigtstp": True,
            "has_sigcont": True,
            "input_backend": "UnixInputBackend",
            "resize_mechanism": "sigwinch+poll",
        }
        defaults.update(overrides)
        return PlatformInfo(**defaults)

    def test_fields(self) -> None:
        info = self._make_info()
        assert info.platform == "linux"
        assert info.is_windows is False
        assert info.is_unix is True
        assert info.has_termios is True
        assert info.has_msvcrt is False
        assert info.has_sigwinch is True
        assert info.has_sigtstp is True
        assert info.has_sigcont is True
        assert info.input_backend == "UnixInputBackend"
        assert info.resize_mechanism == "sigwinch+poll"

    def test_frozen(self) -> None:
        info = self._make_info()
        with pytest.raises(AttributeError):
            info.platform = "win32"  # type: ignore[misc]

    def test_summary_contains_platform(self) -> None:
        info = self._make_info(platform="darwin")
        summary = info.summary()
        assert "darwin" in summary

    def test_summary_contains_unix(self) -> None:
        info = self._make_info(is_windows=False)
        summary = info.summary()
        assert "Unix" in summary

    def test_summary_contains_windows_when_windows(self) -> None:
        info = self._make_info(is_windows=True, is_unix=False)
        summary = info.summary()
        assert "Windows" in summary

    def test_summary_contains_backend(self) -> None:
        info = self._make_info(input_backend="UnixInputBackend")
        summary = info.summary()
        assert "UnixInputBackend" in summary

    def test_summary_contains_resize_mechanism(self) -> None:
        info = self._make_info(resize_mechanism="sigwinch+poll")
        summary = info.summary()
        assert "sigwinch+poll" in summary

    def test_summary_shows_available_for_true_flags(self) -> None:
        info = self._make_info(has_termios=True)
        summary = info.summary()
        # At least one "available" for termios.
        assert "available" in summary

    def test_summary_shows_unavailable_for_false_flags(self) -> None:
        info = self._make_info(has_msvcrt=False)
        summary = info.summary()
        assert "unavailable" in summary

    def test_equality(self) -> None:
        info1 = self._make_info()
        info2 = self._make_info()
        assert info1 == info2

    def test_inequality(self) -> None:
        info1 = self._make_info(platform="linux")
        info2 = self._make_info(platform="win32")
        assert info1 != info2


# ---------------------------------------------------------------------------
# get_platform_info (runtime detection)
# ---------------------------------------------------------------------------


class TestGetPlatformInfo:
    """Runtime platform detection."""

    def test_returns_platform_info(self) -> None:
        info = get_platform_info()
        assert isinstance(info, PlatformInfo)

    def test_platform_matches_sys_platform(self) -> None:
        info = get_platform_info()
        assert info.platform == sys.platform

    def test_is_windows_correct(self) -> None:
        info = get_platform_info()
        assert info.is_windows == (sys.platform == "win32")

    def test_is_unix_correct(self) -> None:
        info = get_platform_info()
        assert info.is_unix == (sys.platform != "win32")

    def test_is_windows_and_is_unix_are_exclusive(self) -> None:
        info = get_platform_info()
        assert info.is_windows != info.is_unix

    def test_sigwinch_matches_signal_module(self) -> None:
        info = get_platform_info()
        assert info.has_sigwinch == hasattr(signal, "SIGWINCH")

    def test_sigtstp_matches_signal_module(self) -> None:
        info = get_platform_info()
        assert info.has_sigtstp == hasattr(signal, "SIGTSTP")

    def test_sigcont_matches_signal_module(self) -> None:
        info = get_platform_info()
        assert info.has_sigcont == hasattr(signal, "SIGCONT")

    def test_input_backend_is_string(self) -> None:
        info = get_platform_info()
        assert isinstance(info.input_backend, str)
        assert len(info.input_backend) > 0

    def test_resize_mechanism_is_string(self) -> None:
        info = get_platform_info()
        assert isinstance(info.resize_mechanism, str)
        assert info.resize_mechanism in ("sigwinch+poll", "poll")

    def test_unix_has_termios(self) -> None:
        """On a Unix system (where tests typically run), termios should exist."""
        info = get_platform_info()
        if info.is_unix:
            assert info.has_termios is True

    def test_unix_has_sigwinch(self) -> None:
        """On Unix, SIGWINCH should be available."""
        info = get_platform_info()
        if info.is_unix:
            assert info.has_sigwinch is True

    def test_unix_resize_mechanism(self) -> None:
        """On Unix, resize should use sigwinch+poll."""
        info = get_platform_info()
        if info.is_unix:
            assert info.resize_mechanism == "sigwinch+poll"

    def test_backend_name_valid(self) -> None:
        info = get_platform_info()
        valid_names = {"UnixInputBackend", "WindowsInputBackend", "FallbackInputBackend"}
        assert info.input_backend in valid_names


# ---------------------------------------------------------------------------
# format_platform_report
# ---------------------------------------------------------------------------


class TestFormatPlatformReport:
    """The comprehensive platform report formatter."""

    def test_returns_string(self) -> None:
        report = format_platform_report()
        assert isinstance(report, str)

    def test_not_empty(self) -> None:
        report = format_platform_report()
        assert len(report) > 0

    def test_contains_platform_info_header(self) -> None:
        report = format_platform_report()
        assert "wyby platform info" in report

    def test_contains_sys_platform(self) -> None:
        report = format_platform_report()
        assert sys.platform in report

    def test_contains_category_headers(self) -> None:
        report = format_platform_report()
        for cat in CATEGORIES:
            assert f"[{cat}]" in report

    def test_contains_unix_label(self) -> None:
        report = format_platform_report()
        assert "Unix:" in report

    def test_contains_windows_label(self) -> None:
        report = format_platform_report()
        assert "Windows:" in report

    def test_marks_current_platform(self) -> None:
        """The current platform's entries should have '>' markers."""
        report = format_platform_report()
        # On any platform, at least one line should have '>' before Unix or Windows.
        assert "> " in report

    def test_contains_caveat_label(self) -> None:
        report = format_platform_report()
        assert "Caveat:" in report


# ---------------------------------------------------------------------------
# Package-level exports
# ---------------------------------------------------------------------------


class TestPlatformInfoExports:
    """New types should be importable from the top-level package."""

    def test_platform_difference_importable(self) -> None:
        from wyby import PlatformDifference as PD

        assert PD is PlatformDifference

    def test_platform_info_importable(self) -> None:
        from wyby import PlatformInfo as PI

        assert PI is PlatformInfo

    def test_platform_differences_importable(self) -> None:
        from wyby import PLATFORM_DIFFERENCES as PD

        assert PD is PLATFORM_DIFFERENCES

    def test_platform_categories_importable(self) -> None:
        from wyby import PLATFORM_CATEGORIES

        assert PLATFORM_CATEGORIES is CATEGORIES

    def test_get_platform_info_importable(self) -> None:
        from wyby import get_platform_info as gpi

        assert gpi is get_platform_info

    def test_get_differences_by_category_importable(self) -> None:
        from wyby import get_differences_by_category as gdbc

        assert gdbc is get_differences_by_category

    def test_format_platform_report_importable(self) -> None:
        from wyby import format_platform_report as fpr

        assert fpr is format_platform_report

    def test_in_all(self) -> None:
        import wyby

        assert "PlatformDifference" in wyby.__all__
        assert "PlatformInfo" in wyby.__all__
        assert "PLATFORM_DIFFERENCES" in wyby.__all__
        assert "PLATFORM_CATEGORIES" in wyby.__all__
        assert "get_platform_info" in wyby.__all__
        assert "get_differences_by_category" in wyby.__all__
        assert "format_platform_report" in wyby.__all__
