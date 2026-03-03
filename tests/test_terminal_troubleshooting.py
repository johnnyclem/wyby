"""Tests for wyby.terminal_troubleshooting — troubleshooting guide and diagnostics."""

from __future__ import annotations

import pytest

from wyby.terminal_troubleshooting import (
    TROUBLESHOOTING_CATEGORIES,
    TROUBLESHOOTING_ENTRIES,
    DiagnosticResult,
    TroubleshootingEntry,
    diagnose_terminal,
    format_diagnostic_report,
    format_troubleshooting_for_category,
    format_troubleshooting_guide,
    get_entries_by_category,
)
from wyby.diagnostics import (
    ColorSupport,
    TerminalCapabilities,
)


# ---------------------------------------------------------------------------
# TroubleshootingEntry dataclass
# ---------------------------------------------------------------------------


class TestTroubleshootingEntry:
    """TroubleshootingEntry frozen dataclass."""

    def test_fields(self) -> None:
        entry = TroubleshootingEntry(
            category="display",
            symptom="Test symptom",
            cause="A cause.",
            fix="A fix.",
            caveat="A caveat.",
        )
        assert entry.category == "display"
        assert entry.symptom == "Test symptom"
        assert entry.cause == "A cause."
        assert entry.fix == "A fix."
        assert entry.caveat == "A caveat."

    def test_caveat_defaults_to_none(self) -> None:
        entry = TroubleshootingEntry(
            category="input",
            symptom="No caveat",
            cause="cause",
            fix="fix",
        )
        assert entry.caveat is None

    def test_frozen(self) -> None:
        entry = TroubleshootingEntry("a", "b", "c", "d")
        with pytest.raises(AttributeError):
            entry.category = "other"  # type: ignore[misc]

    def test_equality(self) -> None:
        a = TroubleshootingEntry("a", "b", "c", "d", "e")
        b = TroubleshootingEntry("a", "b", "c", "d", "e")
        assert a == b

    def test_inequality(self) -> None:
        a = TroubleshootingEntry("a", "b", "c", "d")
        b = TroubleshootingEntry("a", "x", "c", "d")
        assert a != b


# ---------------------------------------------------------------------------
# DiagnosticResult dataclass
# ---------------------------------------------------------------------------


class TestDiagnosticResult:
    """DiagnosticResult frozen dataclass."""

    def test_fields(self) -> None:
        result = DiagnosticResult(
            check="tty",
            passed=True,
            message="stdout is a TTY.",
            suggestion=None,
        )
        assert result.check == "tty"
        assert result.passed is True
        assert result.message == "stdout is a TTY."
        assert result.suggestion is None

    def test_suggestion_defaults_to_none(self) -> None:
        result = DiagnosticResult(
            check="test",
            passed=True,
            message="ok",
        )
        assert result.suggestion is None

    def test_frozen(self) -> None:
        result = DiagnosticResult("a", True, "b")
        with pytest.raises(AttributeError):
            result.check = "other"  # type: ignore[misc]

    def test_equality(self) -> None:
        a = DiagnosticResult("a", True, "b", "c")
        b = DiagnosticResult("a", True, "b", "c")
        assert a == b

    def test_inequality(self) -> None:
        a = DiagnosticResult("a", True, "b")
        b = DiagnosticResult("a", False, "b")
        assert a != b


# ---------------------------------------------------------------------------
# TROUBLESHOOTING_ENTRIES catalog
# ---------------------------------------------------------------------------


class TestTroubleshootingEntriesCatalog:
    """The built-in catalog of troubleshooting entries."""

    def test_is_tuple(self) -> None:
        assert isinstance(TROUBLESHOOTING_ENTRIES, tuple)

    def test_not_empty(self) -> None:
        assert len(TROUBLESHOOTING_ENTRIES) > 0

    def test_all_entries_are_troubleshooting_entry(self) -> None:
        for entry in TROUBLESHOOTING_ENTRIES:
            assert isinstance(entry, TroubleshootingEntry)

    def test_all_have_category(self) -> None:
        for entry in TROUBLESHOOTING_ENTRIES:
            assert entry.category, f"Empty category in {entry.symptom}"

    def test_all_have_symptom(self) -> None:
        for entry in TROUBLESHOOTING_ENTRIES:
            assert entry.symptom, f"Empty symptom in {entry}"

    def test_all_have_cause(self) -> None:
        for entry in TROUBLESHOOTING_ENTRIES:
            assert entry.cause, f"Empty cause in {entry.symptom}"

    def test_all_have_fix(self) -> None:
        for entry in TROUBLESHOOTING_ENTRIES:
            assert entry.fix, f"Empty fix in {entry.symptom}"

    def test_expected_categories_present(self) -> None:
        """All major issue areas should be represented."""
        categories = {e.category for e in TROUBLESHOOTING_ENTRIES}
        assert "display" in categories
        assert "color" in categories
        assert "input" in categories
        assert "performance" in categories
        assert "environment" in categories

    def test_no_duplicate_symptoms(self) -> None:
        """Each symptom should be unique within a category."""
        seen: set[tuple[str, str]] = set()
        for entry in TROUBLESHOOTING_ENTRIES:
            key = (entry.category, entry.symptom)
            assert key not in seen, f"Duplicate entry: {key}"
            seen.add(key)


# ---------------------------------------------------------------------------
# TROUBLESHOOTING_CATEGORIES constant
# ---------------------------------------------------------------------------


class TestTroubleshootingCategories:
    """The TROUBLESHOOTING_CATEGORIES frozenset."""

    def test_is_frozenset(self) -> None:
        assert isinstance(TROUBLESHOOTING_CATEGORIES, frozenset)

    def test_matches_catalog(self) -> None:
        catalog_categories = {e.category for e in TROUBLESHOOTING_ENTRIES}
        assert TROUBLESHOOTING_CATEGORIES == catalog_categories

    def test_minimum_count(self) -> None:
        assert len(TROUBLESHOOTING_CATEGORIES) >= 5


# ---------------------------------------------------------------------------
# get_entries_by_category
# ---------------------------------------------------------------------------


class TestGetEntriesByCategory:
    """Filtering troubleshooting entries by category."""

    def test_returns_tuple(self) -> None:
        result = get_entries_by_category("display")
        assert isinstance(result, tuple)

    def test_all_same_category(self) -> None:
        result = get_entries_by_category("display")
        for entry in result:
            assert entry.category == "display"

    def test_display_has_entries(self) -> None:
        result = get_entries_by_category("display")
        assert len(result) > 0

    def test_color_has_entries(self) -> None:
        result = get_entries_by_category("color")
        assert len(result) > 0

    def test_input_has_entries(self) -> None:
        result = get_entries_by_category("input")
        assert len(result) > 0

    def test_performance_has_entries(self) -> None:
        result = get_entries_by_category("performance")
        assert len(result) > 0

    def test_environment_has_entries(self) -> None:
        result = get_entries_by_category("environment")
        assert len(result) > 0

    def test_unknown_category_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown category"):
            get_entries_by_category("nonexistent")

    def test_error_message_includes_known_categories(self) -> None:
        with pytest.raises(ValueError, match="Known categories"):
            get_entries_by_category("invalid")

    def test_all_categories_retrievable(self) -> None:
        for cat in TROUBLESHOOTING_CATEGORIES:
            result = get_entries_by_category(cat)
            assert len(result) > 0, f"Category {cat!r} returned empty"


# ---------------------------------------------------------------------------
# diagnose_terminal
# ---------------------------------------------------------------------------


class TestDiagnoseTerminal:
    """Automated terminal diagnostics."""

    def _make_caps(self, **overrides: object) -> TerminalCapabilities:
        """Build a TerminalCapabilities with sensible defaults."""
        defaults = {
            "color_support": ColorSupport.TRUECOLOR,
            "utf8_supported": True,
            "is_tty": True,
            "terminal_program": "iTerm2",
            "columns": 80,
            "rows": 24,
            "colorterm_env": "truecolor",
            "term_env": "xterm-256color",
        }
        defaults.update(overrides)
        return TerminalCapabilities(**defaults)

    def test_returns_list(self) -> None:
        caps = self._make_caps()
        results = diagnose_terminal(caps)
        assert isinstance(results, list)

    def test_all_results_are_diagnostic_result(self) -> None:
        caps = self._make_caps()
        results = diagnose_terminal(caps)
        for result in results:
            assert isinstance(result, DiagnosticResult)

    def test_has_tty_check(self) -> None:
        caps = self._make_caps()
        results = diagnose_terminal(caps)
        checks = {r.check for r in results}
        assert "tty" in checks

    def test_has_color_check(self) -> None:
        caps = self._make_caps()
        results = diagnose_terminal(caps)
        checks = {r.check for r in results}
        assert "color" in checks

    def test_has_utf8_check(self) -> None:
        caps = self._make_caps()
        results = diagnose_terminal(caps)
        checks = {r.check for r in results}
        assert "utf8" in checks

    def test_has_size_check(self) -> None:
        caps = self._make_caps()
        results = diagnose_terminal(caps)
        checks = {r.check for r in results}
        assert "size" in checks

    def test_has_terminal_id_check(self) -> None:
        caps = self._make_caps()
        results = diagnose_terminal(caps)
        checks = {r.check for r in results}
        assert "terminal_id" in checks

    def test_has_multiplexer_check(self) -> None:
        caps = self._make_caps()
        results = diagnose_terminal(caps)
        checks = {r.check for r in results}
        assert "multiplexer" in checks

    # -- TTY check -----------------------------------------------------------

    def test_tty_passes_when_connected(self) -> None:
        caps = self._make_caps(is_tty=True)
        results = diagnose_terminal(caps)
        tty = next(r for r in results if r.check == "tty")
        assert tty.passed is True

    def test_tty_fails_when_not_connected(self) -> None:
        caps = self._make_caps(is_tty=False)
        results = diagnose_terminal(caps)
        tty = next(r for r in results if r.check == "tty")
        assert tty.passed is False
        assert tty.suggestion is not None

    # -- Colour check --------------------------------------------------------

    def test_color_passes_with_truecolor(self) -> None:
        caps = self._make_caps(color_support=ColorSupport.TRUECOLOR)
        results = diagnose_terminal(caps)
        color = next(r for r in results if r.check == "color")
        assert color.passed is True

    def test_color_passes_with_256color(self) -> None:
        caps = self._make_caps(color_support=ColorSupport.EXTENDED)
        results = diagnose_terminal(caps)
        color = next(r for r in results if r.check == "color")
        assert color.passed is True
        # Should suggest upgrading to truecolor.
        assert color.suggestion is not None

    def test_color_fails_with_16color(self) -> None:
        caps = self._make_caps(color_support=ColorSupport.STANDARD)
        results = diagnose_terminal(caps)
        color = next(r for r in results if r.check == "color")
        assert color.passed is False
        assert color.suggestion is not None

    def test_color_fails_with_no_color(self) -> None:
        caps = self._make_caps(color_support=ColorSupport.NONE)
        results = diagnose_terminal(caps)
        color = next(r for r in results if r.check == "color")
        assert color.passed is False

    # -- UTF-8 check ---------------------------------------------------------

    def test_utf8_passes_when_supported(self) -> None:
        caps = self._make_caps(utf8_supported=True)
        results = diagnose_terminal(caps)
        utf8 = next(r for r in results if r.check == "utf8")
        assert utf8.passed is True

    def test_utf8_fails_when_not_supported(self) -> None:
        caps = self._make_caps(utf8_supported=False)
        results = diagnose_terminal(caps)
        utf8 = next(r for r in results if r.check == "utf8")
        assert utf8.passed is False
        assert utf8.suggestion is not None

    # -- Size check ----------------------------------------------------------

    def test_size_passes_with_adequate_terminal(self) -> None:
        caps = self._make_caps(columns=80, rows=24)
        results = diagnose_terminal(caps)
        size = next(r for r in results if r.check == "size")
        assert size.passed is True

    def test_size_passes_at_minimum(self) -> None:
        caps = self._make_caps(columns=40, rows=12)
        results = diagnose_terminal(caps)
        size = next(r for r in results if r.check == "size")
        assert size.passed is True

    def test_size_fails_when_too_narrow(self) -> None:
        caps = self._make_caps(columns=30, rows=24)
        results = diagnose_terminal(caps)
        size = next(r for r in results if r.check == "size")
        assert size.passed is False

    def test_size_fails_when_too_short(self) -> None:
        caps = self._make_caps(columns=80, rows=8)
        results = diagnose_terminal(caps)
        size = next(r for r in results if r.check == "size")
        assert size.passed is False

    # -- Terminal identification ----------------------------------------------

    def test_terminal_id_passes_when_identified(self) -> None:
        caps = self._make_caps(terminal_program="iTerm2")
        results = diagnose_terminal(caps)
        tid = next(r for r in results if r.check == "terminal_id")
        assert tid.passed is True
        assert "iTerm2" in tid.message

    def test_terminal_id_passes_when_unidentified(self) -> None:
        caps = self._make_caps(terminal_program=None)
        results = diagnose_terminal(caps)
        tid = next(r for r in results if r.check == "terminal_id")
        # Unidentified is OK — still passes.
        assert tid.passed is True

    # -- Multiplexer detection -----------------------------------------------

    def test_multiplexer_detects_tmux(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TMUX", "/tmp/tmux-1000/default,12345,0")
        monkeypatch.delenv("STY", raising=False)
        caps = self._make_caps()
        results = diagnose_terminal(caps)
        mux = next(r for r in results if r.check == "multiplexer")
        assert "tmux" in mux.message

    def test_multiplexer_detects_screen(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("TMUX", raising=False)
        monkeypatch.setenv("STY", "12345.pts-0.host")
        caps = self._make_caps()
        results = diagnose_terminal(caps)
        mux = next(r for r in results if r.check == "multiplexer")
        assert "screen" in mux.message

    def test_multiplexer_not_detected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("TMUX", raising=False)
        monkeypatch.delenv("STY", raising=False)
        caps = self._make_caps()
        results = diagnose_terminal(caps)
        mux = next(r for r in results if r.check == "multiplexer")
        assert "not running" in mux.message.lower() or "Not running" in mux.message

    # -- Healthy terminal produces all passes --------------------------------

    def test_healthy_terminal_all_pass(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("TMUX", raising=False)
        monkeypatch.delenv("STY", raising=False)
        caps = self._make_caps(
            color_support=ColorSupport.TRUECOLOR,
            utf8_supported=True,
            is_tty=True,
            terminal_program="iTerm2",
            columns=80,
            rows=24,
        )
        results = diagnose_terminal(caps)
        for result in results:
            assert result.passed is True, (
                f"Check {result.check!r} failed: {result.message}"
            )

    def test_calls_detect_capabilities_when_none(self) -> None:
        """diagnose_terminal(None) should not crash."""
        results = diagnose_terminal(None)
        assert isinstance(results, list)
        assert len(results) > 0


# ---------------------------------------------------------------------------
# format_diagnostic_report
# ---------------------------------------------------------------------------


class TestFormatDiagnosticReport:
    """The diagnostic report formatter."""

    def test_returns_string(self) -> None:
        results = [
            DiagnosticResult("tty", True, "stdout is a TTY."),
        ]
        report = format_diagnostic_report(results)
        assert isinstance(report, str)

    def test_contains_header(self) -> None:
        results = [
            DiagnosticResult("tty", True, "ok"),
        ]
        report = format_diagnostic_report(results)
        assert "diagnostic report" in report.lower()

    def test_contains_check_count(self) -> None:
        results = [
            DiagnosticResult("tty", True, "ok"),
            DiagnosticResult("color", False, "bad", "fix it"),
        ]
        report = format_diagnostic_report(results)
        assert "1/2 passed" in report

    def test_shows_ok_for_passed(self) -> None:
        results = [
            DiagnosticResult("tty", True, "stdout is a TTY."),
        ]
        report = format_diagnostic_report(results)
        assert "[OK]" in report

    def test_shows_warning_for_failed(self) -> None:
        results = [
            DiagnosticResult("tty", False, "not a TTY", "fix"),
        ]
        report = format_diagnostic_report(results)
        assert "[!!]" in report

    def test_shows_suggestion_for_failed(self) -> None:
        results = [
            DiagnosticResult("tty", False, "not a TTY", "Run in terminal"),
        ]
        report = format_diagnostic_report(results)
        assert "Run in terminal" in report

    def test_calls_diagnose_when_none(self) -> None:
        """format_diagnostic_report(None) should not crash."""
        report = format_diagnostic_report(None)
        assert isinstance(report, str)
        assert len(report) > 0


# ---------------------------------------------------------------------------
# format_troubleshooting_for_category
# ---------------------------------------------------------------------------


class TestFormatTroubleshootingForCategory:
    """Formatting a single category."""

    def test_returns_string(self) -> None:
        result = format_troubleshooting_for_category("display")
        assert isinstance(result, str)

    def test_contains_category_header(self) -> None:
        result = format_troubleshooting_for_category("display")
        assert "## Display Issues" in result

    def test_contains_symptom_headers(self) -> None:
        result = format_troubleshooting_for_category("display")
        assert "###" in result

    def test_contains_cause_label(self) -> None:
        result = format_troubleshooting_for_category("display")
        assert "**Cause:**" in result

    def test_contains_fix_label(self) -> None:
        result = format_troubleshooting_for_category("display")
        assert "**Fix:**" in result

    def test_unknown_category_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown category"):
            format_troubleshooting_for_category("nonexistent")

    def test_all_categories_formattable(self) -> None:
        for cat in TROUBLESHOOTING_CATEGORIES:
            result = format_troubleshooting_for_category(cat)
            assert len(result) > 0


# ---------------------------------------------------------------------------
# format_troubleshooting_guide
# ---------------------------------------------------------------------------


class TestFormatTroubleshootingGuide:
    """The full troubleshooting guide formatter."""

    def test_returns_string(self) -> None:
        guide = format_troubleshooting_guide()
        assert isinstance(guide, str)

    def test_not_empty(self) -> None:
        guide = format_troubleshooting_guide()
        assert len(guide) > 0

    def test_contains_title(self) -> None:
        guide = format_troubleshooting_guide()
        assert "# wyby Terminal Troubleshooting Guide" in guide

    def test_contains_issue_count(self) -> None:
        guide = format_troubleshooting_guide()
        assert f"{len(TROUBLESHOOTING_ENTRIES)} issues documented" in guide

    def test_contains_all_categories(self) -> None:
        guide = format_troubleshooting_guide()
        for cat in TROUBLESHOOTING_CATEGORIES:
            from wyby.terminal_troubleshooting import _CATEGORY_LABELS
            label = _CATEGORY_LABELS.get(
                cat, cat.replace("_", " ").title(),
            )
            assert f"## {label}" in guide

    def test_contains_all_symptoms(self) -> None:
        guide = format_troubleshooting_guide()
        for entry in TROUBLESHOOTING_ENTRIES:
            assert entry.symptom in guide


# ---------------------------------------------------------------------------
# Package-level exports
# ---------------------------------------------------------------------------


class TestTroubleshootingExports:
    """Troubleshooting types should be importable from the top-level package."""

    def test_troubleshooting_entry_importable(self) -> None:
        from wyby import TroubleshootingEntry as TE
        assert TE is TroubleshootingEntry

    def test_diagnostic_result_importable(self) -> None:
        from wyby import DiagnosticResult as DR
        assert DR is DiagnosticResult

    def test_entries_importable(self) -> None:
        from wyby import TROUBLESHOOTING_ENTRIES as TE
        assert TE is TROUBLESHOOTING_ENTRIES

    def test_categories_importable(self) -> None:
        from wyby import TROUBLESHOOTING_CATEGORIES as TC
        assert TC is TROUBLESHOOTING_CATEGORIES

    def test_get_entries_importable(self) -> None:
        from wyby import get_troubleshooting_entries_by_category
        assert get_troubleshooting_entries_by_category is get_entries_by_category

    def test_diagnose_terminal_importable(self) -> None:
        from wyby import diagnose_terminal as dt
        assert dt is diagnose_terminal

    def test_format_guide_importable(self) -> None:
        from wyby import format_troubleshooting_guide as ftg
        assert ftg is format_troubleshooting_guide

    def test_format_category_importable(self) -> None:
        from wyby import format_troubleshooting_for_category as ftc
        assert ftc is format_troubleshooting_for_category

    def test_format_diagnostic_report_importable(self) -> None:
        from wyby import format_diagnostic_report as fdr
        assert fdr is format_diagnostic_report

    def test_in_all(self) -> None:
        import wyby
        assert "TroubleshootingEntry" in wyby.__all__
        assert "DiagnosticResult" in wyby.__all__
        assert "TROUBLESHOOTING_ENTRIES" in wyby.__all__
        assert "TROUBLESHOOTING_CATEGORIES" in wyby.__all__
        assert "diagnose_terminal" in wyby.__all__
        assert "format_troubleshooting_guide" in wyby.__all__
        assert "format_troubleshooting_for_category" in wyby.__all__
        assert "format_diagnostic_report" in wyby.__all__
        assert "get_troubleshooting_entries_by_category" in wyby.__all__
