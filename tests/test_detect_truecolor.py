"""Tests for wyby.diagnostics.detect_truecolor."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from wyby.diagnostics import (
    _rich_detects_truecolor,
    detect_truecolor,
)


# ---------------------------------------------------------------------------
# detect_truecolor — $COLORTERM fast path
# ---------------------------------------------------------------------------


class TestDetectTruecolorEnvVar:
    """detect_truecolor() should return True when $COLORTERM indicates truecolor."""

    def test_colorterm_truecolor(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("COLORTERM", "truecolor")
        assert detect_truecolor() is True

    def test_colorterm_24bit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("COLORTERM", "24bit")
        assert detect_truecolor() is True

    def test_colorterm_case_insensitive(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("COLORTERM", "TrueColor")
        assert detect_truecolor() is True

    def test_colorterm_24bit_uppercase(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("COLORTERM", "24BIT")
        assert detect_truecolor() is True

    def test_colorterm_truecolor_skips_rich_fallback(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When $COLORTERM is set, Rich detection should not be called."""
        monkeypatch.setenv("COLORTERM", "truecolor")
        with patch(
            "wyby.diagnostics._rich_detects_truecolor"
        ) as mock_rich:
            result = detect_truecolor()
            assert result is True
            mock_rich.assert_not_called()


# ---------------------------------------------------------------------------
# detect_truecolor — Rich fallback
# ---------------------------------------------------------------------------


class TestDetectTruecolorRichFallback:
    """detect_truecolor() should fall back to Rich when $COLORTERM is not set."""

    def test_falls_back_to_rich_when_colorterm_unset(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("COLORTERM", raising=False)
        with patch(
            "wyby.diagnostics._rich_detects_truecolor", return_value=True
        ) as mock_rich:
            result = detect_truecolor()
            assert result is True
            mock_rich.assert_called_once()

    def test_falls_back_to_rich_when_colorterm_not_truecolor(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """$COLORTERM set to a non-truecolor value should trigger Rich fallback."""
        monkeypatch.setenv("COLORTERM", "yes")
        with patch(
            "wyby.diagnostics._rich_detects_truecolor", return_value=False
        ) as mock_rich:
            result = detect_truecolor()
            assert result is False
            mock_rich.assert_called_once()

    def test_returns_false_when_rich_says_no(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("COLORTERM", raising=False)
        with patch(
            "wyby.diagnostics._rich_detects_truecolor", return_value=False
        ):
            assert detect_truecolor() is False

    def test_returns_true_when_rich_says_yes(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("COLORTERM", raising=False)
        with patch(
            "wyby.diagnostics._rich_detects_truecolor", return_value=True
        ):
            assert detect_truecolor() is True

    def test_empty_colorterm_triggers_rich_fallback(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("COLORTERM", "")
        with patch(
            "wyby.diagnostics._rich_detects_truecolor", return_value=False
        ) as mock_rich:
            detect_truecolor()
            mock_rich.assert_called_once()


# ---------------------------------------------------------------------------
# _rich_detects_truecolor
# ---------------------------------------------------------------------------


class TestRichDetectsTruecolor:
    """_rich_detects_truecolor() should query Rich's Console color_system."""

    def test_returns_true_when_rich_reports_truecolor(self) -> None:
        mock_console = MagicMock()
        mock_console.color_system = "truecolor"
        with patch(
            "rich.console.Console", return_value=mock_console
        ):
            assert _rich_detects_truecolor() is True

    def test_returns_false_when_rich_reports_256(self) -> None:
        mock_console = MagicMock()
        mock_console.color_system = "256"
        with patch(
            "rich.console.Console", return_value=mock_console
        ):
            assert _rich_detects_truecolor() is False

    def test_returns_false_when_rich_reports_standard(self) -> None:
        mock_console = MagicMock()
        mock_console.color_system = "standard"
        with patch(
            "rich.console.Console", return_value=mock_console
        ):
            assert _rich_detects_truecolor() is False

    def test_returns_false_when_rich_reports_none(self) -> None:
        mock_console = MagicMock()
        mock_console.color_system = None
        with patch(
            "rich.console.Console", return_value=mock_console
        ):
            assert _rich_detects_truecolor() is False

    def test_returns_false_on_import_error(self) -> None:
        """If Rich cannot be imported, should return False gracefully."""
        with patch(
            "builtins.__import__", side_effect=ImportError("no rich")
        ):
            assert _rich_detects_truecolor() is False

    def test_returns_false_on_unexpected_exception(self) -> None:
        """Any unexpected error should return False, not propagate."""
        with patch(
            "rich.console.Console", side_effect=RuntimeError("boom")
        ):
            assert _rich_detects_truecolor() is False


# ---------------------------------------------------------------------------
# Package-level exports
# ---------------------------------------------------------------------------


class TestDetectTruecolorExports:
    """detect_truecolor should be importable from the top-level package."""

    def test_importable_from_wyby(self) -> None:
        from wyby import detect_truecolor as dt

        assert dt is detect_truecolor

    def test_in_all(self) -> None:
        import wyby

        assert "detect_truecolor" in wyby.__all__
