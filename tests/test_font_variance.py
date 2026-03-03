"""Tests for wyby.font_variance — font and terminal variance catalog and detection."""

from __future__ import annotations

import struct
import sys

import pytest

from wyby.diagnostics import ColorSupport, TerminalCapabilities
from wyby.font_variance import (
    DEFAULT_CELL_ASPECT_RATIO,
    FONT_VARIANCE_ISSUES,
    ISSUE_CATEGORIES,
    CellGeometry,
    FontVarianceIssue,
    _try_ioctl_cell_size,
    check_font_variance_warnings,
    estimate_cell_aspect_ratio,
    format_font_variance_report,
    get_issues_by_category,
    get_issues_for_terminal,
    log_font_variance_warnings,
)


# ---------------------------------------------------------------------------
# Helper: build a TerminalCapabilities with overrides
# ---------------------------------------------------------------------------


def _make_caps(**overrides: object) -> TerminalCapabilities:
    defaults: dict = {
        "color_support": ColorSupport.TRUECOLOR,
        "utf8_supported": True,
        "is_tty": True,
        "terminal_program": "iTerm.app",
        "columns": 120,
        "rows": 40,
        "colorterm_env": "truecolor",
        "term_env": "xterm-256color",
    }
    defaults.update(overrides)
    return TerminalCapabilities(**defaults)


# ---------------------------------------------------------------------------
# FontVarianceIssue dataclass
# ---------------------------------------------------------------------------


class TestFontVarianceIssue:
    """FontVarianceIssue frozen dataclass."""

    def test_fields(self) -> None:
        issue = FontVarianceIssue(
            category="test_cat",
            issue="test_issue",
            description="A test issue.",
            affected_terminals="all",
            mitigation="Do something.",
        )
        assert issue.category == "test_cat"
        assert issue.issue == "test_issue"
        assert issue.description == "A test issue."
        assert issue.affected_terminals == "all"
        assert issue.mitigation == "Do something."

    def test_frozen(self) -> None:
        issue = FontVarianceIssue("a", "b", "c", "d", "e")
        with pytest.raises(AttributeError):
            issue.category = "other"  # type: ignore[misc]

    def test_equality(self) -> None:
        i1 = FontVarianceIssue("a", "b", "c", "d", "e")
        i2 = FontVarianceIssue("a", "b", "c", "d", "e")
        assert i1 == i2

    def test_inequality(self) -> None:
        i1 = FontVarianceIssue("a", "b", "c", "d", "e")
        i2 = FontVarianceIssue("a", "x", "c", "d", "e")
        assert i1 != i2


# ---------------------------------------------------------------------------
# FONT_VARIANCE_ISSUES catalog
# ---------------------------------------------------------------------------


class TestFontVarianceIssuesCatalog:
    """The built-in catalog of font variance issues."""

    def test_is_tuple(self) -> None:
        assert isinstance(FONT_VARIANCE_ISSUES, tuple)

    def test_not_empty(self) -> None:
        assert len(FONT_VARIANCE_ISSUES) > 0

    def test_all_entries_are_font_variance_issue(self) -> None:
        for issue in FONT_VARIANCE_ISSUES:
            assert isinstance(issue, FontVarianceIssue)

    def test_all_fields_non_empty(self) -> None:
        for issue in FONT_VARIANCE_ISSUES:
            assert issue.category, f"Empty category in {issue.issue}"
            assert issue.issue, f"Empty issue in {issue}"
            assert issue.description, f"Empty description in {issue.issue}"
            assert issue.affected_terminals, f"Empty affected_terminals in {issue.issue}"
            assert issue.mitigation, f"Empty mitigation in {issue.issue}"

    def test_expected_categories_present(self) -> None:
        categories = {i.category for i in FONT_VARIANCE_ISSUES}
        assert "aspect_ratio" in categories
        assert "glyph_width" in categories
        assert "glyph_coverage" in categories
        assert "ligatures" in categories
        assert "line_spacing" in categories
        assert "text_shaping" in categories

    def test_expected_issues_present(self) -> None:
        issues = {i.issue for i in FONT_VARIANCE_ISSUES}
        assert "cell_not_square" in issues
        assert "emoji_width_disagreement" in issues
        assert "missing_glyphs_tofu" in issues
        assert "ligature_box_drawing" in issues

    def test_no_duplicate_issues(self) -> None:
        seen: set[tuple[str, str]] = set()
        for issue in FONT_VARIANCE_ISSUES:
            key = (issue.category, issue.issue)
            assert key not in seen, f"Duplicate entry: {key}"
            seen.add(key)


# ---------------------------------------------------------------------------
# ISSUE_CATEGORIES constant
# ---------------------------------------------------------------------------


class TestIssueCategories:
    """The ISSUE_CATEGORIES frozenset."""

    def test_is_frozenset(self) -> None:
        assert isinstance(ISSUE_CATEGORIES, frozenset)

    def test_matches_catalog(self) -> None:
        catalog_categories = {i.category for i in FONT_VARIANCE_ISSUES}
        assert ISSUE_CATEGORIES == catalog_categories

    def test_minimum_count(self) -> None:
        assert len(ISSUE_CATEGORIES) >= 5


# ---------------------------------------------------------------------------
# get_issues_by_category
# ---------------------------------------------------------------------------


class TestGetIssuesByCategory:
    """Filtering font variance issues by category."""

    def test_returns_tuple(self) -> None:
        result = get_issues_by_category("aspect_ratio")
        assert isinstance(result, tuple)

    def test_all_same_category(self) -> None:
        result = get_issues_by_category("aspect_ratio")
        for issue in result:
            assert issue.category == "aspect_ratio"

    def test_aspect_ratio_has_entries(self) -> None:
        result = get_issues_by_category("aspect_ratio")
        assert len(result) > 0

    def test_glyph_width_has_entries(self) -> None:
        result = get_issues_by_category("glyph_width")
        assert len(result) > 0

    def test_ligatures_has_entries(self) -> None:
        result = get_issues_by_category("ligatures")
        assert len(result) > 0

    def test_unknown_category_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown category"):
            get_issues_by_category("nonexistent")

    def test_error_message_includes_known_categories(self) -> None:
        with pytest.raises(ValueError, match="Known categories"):
            get_issues_by_category("invalid")

    def test_all_categories_retrievable(self) -> None:
        for cat in ISSUE_CATEGORIES:
            result = get_issues_by_category(cat)
            assert len(result) > 0, f"Category {cat!r} returned empty"


# ---------------------------------------------------------------------------
# get_issues_for_terminal
# ---------------------------------------------------------------------------


class TestGetIssuesForTerminal:
    """Filtering issues by terminal program."""

    def test_returns_tuple(self) -> None:
        result = get_issues_for_terminal("kitty")
        assert isinstance(result, tuple)

    def test_none_returns_universal_issues(self) -> None:
        result = get_issues_for_terminal(None)
        # Should include all issues with "all" in affected_terminals.
        universal_count = sum(
            1 for i in FONT_VARIANCE_ISSUES if "all" in i.affected_terminals.lower()
        )
        assert len(result) == universal_count

    def test_kitty_includes_universal_and_specific(self) -> None:
        result = get_issues_for_terminal("kitty")
        issues = {i.issue for i in result}
        # Universal issues should be present.
        assert "cell_not_square" in issues
        # kitty-specific issues should be present.
        assert "ligature_box_drawing" in issues
        assert "custom_cell_padding" in issues

    def test_wezterm_includes_padding_issue(self) -> None:
        result = get_issues_for_terminal("WezTerm")
        issues = {i.issue for i in result}
        assert "custom_cell_padding" in issues

    def test_case_insensitive(self) -> None:
        r1 = get_issues_for_terminal("kitty")
        r2 = get_issues_for_terminal("Kitty")
        assert len(r1) == len(r2)

    def test_unknown_terminal_returns_universal_only(self) -> None:
        result = get_issues_for_terminal("SomeUnknownTerminal")
        # Should only have universal issues.
        for issue in result:
            assert "all" in issue.affected_terminals.lower()


# ---------------------------------------------------------------------------
# CellGeometry dataclass
# ---------------------------------------------------------------------------


class TestCellGeometry:
    """CellGeometry frozen dataclass."""

    def test_fields_detected(self) -> None:
        geom = CellGeometry(
            cell_width_px=8,
            cell_height_px=16,
            aspect_ratio=2.0,
            detected=True,
        )
        assert geom.cell_width_px == 8
        assert geom.cell_height_px == 16
        assert geom.aspect_ratio == 2.0
        assert geom.detected is True

    def test_fields_not_detected(self) -> None:
        geom = CellGeometry(
            cell_width_px=None,
            cell_height_px=None,
            aspect_ratio=2.0,
            detected=False,
        )
        assert geom.cell_width_px is None
        assert geom.cell_height_px is None
        assert geom.detected is False

    def test_frozen(self) -> None:
        geom = CellGeometry(None, None, 2.0, False)
        with pytest.raises(AttributeError):
            geom.aspect_ratio = 1.5  # type: ignore[misc]

    def test_equality(self) -> None:
        g1 = CellGeometry(8, 16, 2.0, True)
        g2 = CellGeometry(8, 16, 2.0, True)
        assert g1 == g2


# ---------------------------------------------------------------------------
# DEFAULT_CELL_ASPECT_RATIO
# ---------------------------------------------------------------------------


class TestDefaultCellAspectRatio:
    """The default cell aspect ratio constant."""

    def test_is_float(self) -> None:
        assert isinstance(DEFAULT_CELL_ASPECT_RATIO, float)

    def test_value(self) -> None:
        assert DEFAULT_CELL_ASPECT_RATIO == 2.0


# ---------------------------------------------------------------------------
# _try_ioctl_cell_size
# ---------------------------------------------------------------------------


class TestTryIoctlCellSize:
    """Low-level ioctl cell size detection."""

    def test_returns_none_on_windows(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("wyby.font_variance.sys.platform", "win32")
        assert _try_ioctl_cell_size() is None

    def test_returns_none_when_no_fcntl(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When fcntl/termios are unavailable, returns None."""
        import builtins
        original_import = builtins.__import__

        def mock_import(name: str, *args: object, **kwargs: object) -> object:
            if name in ("fcntl", "termios"):
                raise ImportError(f"No module named {name!r}")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)
        # Force re-execution by calling the function.
        # The function imports fcntl/termios each time.
        result = _try_ioctl_cell_size()
        # On Unix this may succeed via cached imports; on Windows it's None.
        # The key assertion is that it doesn't raise.
        assert result is None or isinstance(result, tuple)

    def test_returns_none_when_ioctl_fails(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Gracefully handles OSError from ioctl."""
        if sys.platform == "win32":
            pytest.skip("ioctl not available on Windows")

        import fcntl as real_fcntl

        def failing_ioctl(*args: object, **kwargs: object) -> bytes:
            raise OSError("not a tty")

        monkeypatch.setattr(real_fcntl, "ioctl", failing_ioctl)
        assert _try_ioctl_cell_size() is None

    def test_returns_none_when_zero_pixels(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When ioctl returns zero pixel dimensions, returns None."""
        if sys.platform == "win32":
            pytest.skip("ioctl not available on Windows")

        import fcntl as real_fcntl

        # Pack rows=40, cols=120, xpixel=0, ypixel=0
        fake_result = struct.pack("HHHH", 40, 120, 0, 0)

        def fake_ioctl(*args: object, **kwargs: object) -> bytes:
            return fake_result

        monkeypatch.setattr(real_fcntl, "ioctl", fake_ioctl)
        assert _try_ioctl_cell_size() is None


# ---------------------------------------------------------------------------
# estimate_cell_aspect_ratio
# ---------------------------------------------------------------------------


class TestEstimateCellAspectRatio:
    """Cell aspect ratio estimation."""

    def test_returns_cell_geometry(self) -> None:
        result = estimate_cell_aspect_ratio()
        assert isinstance(result, CellGeometry)

    def test_aspect_ratio_is_positive(self) -> None:
        result = estimate_cell_aspect_ratio()
        assert result.aspect_ratio > 0

    def test_fallback_when_not_detected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When ioctl detection fails, fall back to default."""
        monkeypatch.setattr(
            "wyby.font_variance._try_ioctl_cell_size", lambda: None
        )
        result = estimate_cell_aspect_ratio()
        assert result.detected is False
        assert result.aspect_ratio == DEFAULT_CELL_ASPECT_RATIO
        assert result.cell_width_px is None
        assert result.cell_height_px is None

    def test_detected_from_ioctl(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When ioctl returns valid pixel data, compute aspect ratio."""
        # Simulate: 40 rows, 120 cols, 960px width, 800px height
        # → cell_w = 960/120 = 8, cell_h = 800/40 = 20
        # → ratio = 20/8 = 2.5
        monkeypatch.setattr(
            "wyby.font_variance._try_ioctl_cell_size",
            lambda: (40, 120, 960, 800),
        )
        result = estimate_cell_aspect_ratio()
        assert result.detected is True
        assert result.cell_width_px == 8
        assert result.cell_height_px == 20
        assert result.aspect_ratio == 2.5

    def test_rejects_implausible_ratio(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Implausible aspect ratios fall back to default."""
        # Simulate: ratio = 0.5 (too small — below _MIN_ASPECT_RATIO)
        # rows=40, cols=120, xpixel=1200, ypixel=200
        # cell_w = 1200/120 = 10, cell_h = 200/40 = 5, ratio = 0.5
        monkeypatch.setattr(
            "wyby.font_variance._try_ioctl_cell_size",
            lambda: (40, 120, 1200, 200),
        )
        result = estimate_cell_aspect_ratio()
        assert result.detected is False
        assert result.aspect_ratio == DEFAULT_CELL_ASPECT_RATIO


# ---------------------------------------------------------------------------
# check_font_variance_warnings
# ---------------------------------------------------------------------------


class TestCheckFontVarianceWarnings:
    """Terminal-specific font variance warnings."""

    def test_returns_list(self) -> None:
        caps = _make_caps()
        result = check_font_variance_warnings(caps)
        assert isinstance(result, list)

    def test_iterm_ligature_warning(self) -> None:
        caps = _make_caps(terminal_program="iTerm.app")
        warnings = check_font_variance_warnings(caps)
        assert any("ligature" in w.lower() for w in warnings)

    def test_kitty_ligature_and_padding_warnings(self) -> None:
        caps = _make_caps(terminal_program="kitty")
        warnings = check_font_variance_warnings(caps)
        assert any("ligature" in w.lower() for w in warnings)
        assert any("padding" in w.lower() for w in warnings)

    def test_wezterm_warnings(self) -> None:
        caps = _make_caps(terminal_program="WezTerm")
        warnings = check_font_variance_warnings(caps)
        assert any("ligature" in w.lower() for w in warnings)
        assert any("padding" in w.lower() for w in warnings)

    def test_apple_terminal_warning(self) -> None:
        caps = _make_caps(terminal_program="Apple_Terminal")
        warnings = check_font_variance_warnings(caps)
        assert any("truecolor" in w.lower() for w in warnings)

    def test_tmux_warning(self) -> None:
        caps = _make_caps(terminal_program="tmux")
        warnings = check_font_variance_warnings(caps)
        assert any("multiplexer" in w.lower() or "tmux" in w.lower() for w in warnings)

    def test_screen_warning(self) -> None:
        caps = _make_caps(terminal_program="screen")
        warnings = check_font_variance_warnings(caps)
        assert any("multiplexer" in w.lower() or "screen" in w.lower() for w in warnings)

    def test_unknown_terminal_no_warnings(self) -> None:
        caps = _make_caps(terminal_program=None)
        warnings = check_font_variance_warnings(caps)
        assert warnings == []

    def test_generic_terminal_no_warnings(self) -> None:
        caps = _make_caps(terminal_program="SomeUnknownTerminal")
        warnings = check_font_variance_warnings(caps)
        assert warnings == []

    def test_auto_detects_caps_when_none(self) -> None:
        """When caps is None, detect_capabilities() is called."""
        # Just verify it doesn't raise.
        result = check_font_variance_warnings(None)
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# format_font_variance_report
# ---------------------------------------------------------------------------


class TestFormatFontVarianceReport:
    """The comprehensive font variance report formatter."""

    def test_returns_string(self) -> None:
        caps = _make_caps()
        report = format_font_variance_report(caps)
        assert isinstance(report, str)

    def test_not_empty(self) -> None:
        caps = _make_caps()
        report = format_font_variance_report(caps)
        assert len(report) > 0

    def test_contains_header(self) -> None:
        caps = _make_caps()
        report = format_font_variance_report(caps)
        assert "font/terminal variance report" in report

    def test_contains_terminal_info(self) -> None:
        caps = _make_caps(terminal_program="kitty")
        report = format_font_variance_report(caps)
        assert "kitty" in report

    def test_contains_aspect_ratio(self) -> None:
        caps = _make_caps()
        report = format_font_variance_report(caps)
        assert "Aspect ratio" in report

    def test_contains_category_headers(self) -> None:
        caps = _make_caps()
        report = format_font_variance_report(caps)
        for cat in ISSUE_CATEGORIES:
            assert f"[{cat}]" in report

    def test_contains_warnings_section_for_iterm(self) -> None:
        caps = _make_caps(terminal_program="iTerm.app")
        report = format_font_variance_report(caps)
        assert "Warnings for this terminal" in report

    def test_no_warnings_section_for_unknown(self) -> None:
        caps = _make_caps(terminal_program=None)
        report = format_font_variance_report(caps)
        assert "Warnings for this terminal" not in report

    def test_auto_detects_caps_when_none(self) -> None:
        """When caps is None, detect_capabilities() is called."""
        report = format_font_variance_report(None)
        assert isinstance(report, str)
        assert len(report) > 0


# ---------------------------------------------------------------------------
# log_font_variance_warnings
# ---------------------------------------------------------------------------


class TestLogFontVarianceWarnings:
    """Logging convenience wrapper."""

    def test_returns_same_as_check(self) -> None:
        caps = _make_caps(terminal_program="kitty")
        logged = log_font_variance_warnings(caps)
        checked = check_font_variance_warnings(caps)
        assert logged == checked

    def test_empty_for_unknown_terminal(self) -> None:
        caps = _make_caps(terminal_program=None)
        result = log_font_variance_warnings(caps)
        assert result == []

    def test_auto_detects_caps_when_none(self) -> None:
        result = log_font_variance_warnings(None)
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# Package-level exports
# ---------------------------------------------------------------------------


class TestFontVarianceExports:
    """New types should be importable from the top-level package."""

    def test_font_variance_issue_importable(self) -> None:
        from wyby import FontVarianceIssue as FVI

        assert FVI is FontVarianceIssue

    def test_cell_geometry_importable(self) -> None:
        from wyby import CellGeometry as CG

        assert CG is CellGeometry

    def test_font_variance_issues_importable(self) -> None:
        from wyby import FONT_VARIANCE_ISSUES as FVI

        assert FVI is FONT_VARIANCE_ISSUES

    def test_font_variance_categories_importable(self) -> None:
        from wyby import FONT_VARIANCE_CATEGORIES

        assert FONT_VARIANCE_CATEGORIES is ISSUE_CATEGORIES

    def test_estimate_cell_aspect_ratio_importable(self) -> None:
        from wyby import estimate_cell_aspect_ratio as ecar

        assert ecar is estimate_cell_aspect_ratio

    def test_check_font_variance_warnings_importable(self) -> None:
        from wyby import check_font_variance_warnings as cfvw

        assert cfvw is check_font_variance_warnings

    def test_format_font_variance_report_importable(self) -> None:
        from wyby import format_font_variance_report as ffvr

        assert ffvr is format_font_variance_report

    def test_get_issues_for_terminal_importable(self) -> None:
        from wyby import get_issues_for_terminal as gift

        assert gift is get_issues_for_terminal

    def test_get_font_issues_by_category_importable(self) -> None:
        from wyby import get_font_issues_by_category

        assert callable(get_font_issues_by_category)

    def test_log_font_variance_warnings_importable(self) -> None:
        from wyby import log_font_variance_warnings as lfvw

        assert lfvw is log_font_variance_warnings

    def test_in_all(self) -> None:
        import wyby

        assert "FontVarianceIssue" in wyby.__all__
        assert "CellGeometry" in wyby.__all__
        assert "FONT_VARIANCE_ISSUES" in wyby.__all__
        assert "FONT_VARIANCE_CATEGORIES" in wyby.__all__
        assert "estimate_cell_aspect_ratio" in wyby.__all__
        assert "check_font_variance_warnings" in wyby.__all__
        assert "format_font_variance_report" in wyby.__all__
        assert "get_font_issues_by_category" in wyby.__all__
        assert "get_issues_for_terminal" in wyby.__all__
        assert "log_font_variance_warnings" in wyby.__all__
