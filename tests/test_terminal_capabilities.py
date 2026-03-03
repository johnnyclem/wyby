"""Tests for terminal capability detection in wyby.diagnostics."""

from __future__ import annotations

import os

import pytest

from wyby.diagnostics import (
    ColorSupport,
    TerminalCapabilities,
    _detect_color_support,
    _detect_terminal_program,
    _detect_terminal_size,
    _detect_utf8,
    detect_capabilities,
)


# ---------------------------------------------------------------------------
# ColorSupport enum
# ---------------------------------------------------------------------------


class TestColorSupport:
    """ColorSupport enum values and ordering."""

    def test_ordering_values(self) -> None:
        assert ColorSupport.NONE.value == 0
        assert ColorSupport.STANDARD.value == 1
        assert ColorSupport.EXTENDED.value == 2
        assert ColorSupport.TRUECOLOR.value == 3

    def test_comparison_ge(self) -> None:
        assert ColorSupport.TRUECOLOR >= ColorSupport.EXTENDED
        assert ColorSupport.TRUECOLOR >= ColorSupport.TRUECOLOR
        assert not (ColorSupport.STANDARD >= ColorSupport.EXTENDED)

    def test_comparison_gt(self) -> None:
        assert ColorSupport.TRUECOLOR > ColorSupport.EXTENDED
        assert not (ColorSupport.TRUECOLOR > ColorSupport.TRUECOLOR)

    def test_comparison_le(self) -> None:
        assert ColorSupport.NONE <= ColorSupport.STANDARD
        assert ColorSupport.NONE <= ColorSupport.NONE
        assert not (ColorSupport.EXTENDED <= ColorSupport.STANDARD)

    def test_comparison_lt(self) -> None:
        assert ColorSupport.NONE < ColorSupport.STANDARD
        assert not (ColorSupport.NONE < ColorSupport.NONE)

    def test_comparison_with_non_enum_returns_not_implemented(self) -> None:
        assert ColorSupport.TRUECOLOR.__ge__(42) is NotImplemented
        assert ColorSupport.TRUECOLOR.__gt__(42) is NotImplemented
        assert ColorSupport.TRUECOLOR.__le__(42) is NotImplemented
        assert ColorSupport.TRUECOLOR.__lt__(42) is NotImplemented


# ---------------------------------------------------------------------------
# _detect_color_support
# ---------------------------------------------------------------------------


class TestDetectColorSupport:
    """Colour depth detection from $COLORTERM and $TERM."""

    def test_colorterm_truecolor(self) -> None:
        assert _detect_color_support("truecolor", "") == ColorSupport.TRUECOLOR

    def test_colorterm_24bit(self) -> None:
        assert _detect_color_support("24bit", "") == ColorSupport.TRUECOLOR

    def test_colorterm_case_insensitive(self) -> None:
        assert _detect_color_support("TrueColor", "") == ColorSupport.TRUECOLOR
        assert _detect_color_support("24BIT", "") == ColorSupport.TRUECOLOR

    def test_term_256color(self) -> None:
        assert _detect_color_support("", "xterm-256color") == ColorSupport.EXTENDED

    def test_term_256color_variants(self) -> None:
        assert _detect_color_support("", "screen-256color") == ColorSupport.EXTENDED
        assert _detect_color_support("", "tmux-256color") == ColorSupport.EXTENDED

    def test_term_dumb(self) -> None:
        assert _detect_color_support("", "dumb") == ColorSupport.NONE

    def test_term_empty(self) -> None:
        assert _detect_color_support("", "") == ColorSupport.NONE

    def test_term_standard(self) -> None:
        assert _detect_color_support("", "xterm") == ColorSupport.STANDARD
        assert _detect_color_support("", "linux") == ColorSupport.STANDARD
        assert _detect_color_support("", "vt100") == ColorSupport.STANDARD

    def test_colorterm_takes_precedence_over_term(self) -> None:
        """$COLORTERM=truecolor should win even if $TERM is 'dumb'."""
        assert _detect_color_support("truecolor", "dumb") == ColorSupport.TRUECOLOR


# ---------------------------------------------------------------------------
# _detect_utf8
# ---------------------------------------------------------------------------


class TestDetectUtf8:
    """UTF-8 detection from locale environment variables."""

    def test_lc_all_utf8(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LC_ALL", "en_US.UTF-8")
        monkeypatch.delenv("LC_CTYPE", raising=False)
        monkeypatch.delenv("LANG", raising=False)
        assert _detect_utf8() is True

    def test_lc_ctype_utf8(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("LC_ALL", raising=False)
        monkeypatch.setenv("LC_CTYPE", "en_US.UTF-8")
        monkeypatch.delenv("LANG", raising=False)
        assert _detect_utf8() is True

    def test_lang_utf8(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("LC_ALL", raising=False)
        monkeypatch.delenv("LC_CTYPE", raising=False)
        monkeypatch.setenv("LANG", "en_US.UTF-8")
        assert _detect_utf8() is True

    def test_utf8_lowercase(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LC_ALL", "en_US.utf-8")
        monkeypatch.delenv("LC_CTYPE", raising=False)
        monkeypatch.delenv("LANG", raising=False)
        assert _detect_utf8() is True

    def test_utf8_without_hyphen(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Some systems use 'utf8' without the hyphen."""
        monkeypatch.setenv("LANG", "en_US.utf8")
        monkeypatch.delenv("LC_ALL", raising=False)
        monkeypatch.delenv("LC_CTYPE", raising=False)
        assert _detect_utf8() is True

    def test_no_utf8(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("LC_ALL", raising=False)
        monkeypatch.delenv("LC_CTYPE", raising=False)
        monkeypatch.setenv("LANG", "C")
        assert _detect_utf8() is False

    def test_all_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("LC_ALL", raising=False)
        monkeypatch.delenv("LC_CTYPE", raising=False)
        monkeypatch.delenv("LANG", raising=False)
        assert _detect_utf8() is False

    def test_lc_all_priority_over_lang(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """$LC_ALL should be checked before $LANG."""
        monkeypatch.setenv("LC_ALL", "en_US.UTF-8")
        monkeypatch.delenv("LC_CTYPE", raising=False)
        monkeypatch.setenv("LANG", "C")
        assert _detect_utf8() is True


# ---------------------------------------------------------------------------
# _detect_terminal_program
# ---------------------------------------------------------------------------


class TestDetectTerminalProgram:
    """Terminal emulator identification."""

    def test_term_program(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TERM_PROGRAM", "iTerm.app")
        assert _detect_terminal_program() == "iTerm.app"

    def test_terminal_emulator(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("TERM_PROGRAM", raising=False)
        monkeypatch.setenv("TERMINAL_EMULATOR", "JetBrains-JediTerm")
        monkeypatch.delenv("WT_SESSION", raising=False)
        monkeypatch.delenv("KITTY_WINDOW_ID", raising=False)
        assert _detect_terminal_program() == "JetBrains-JediTerm"

    def test_windows_terminal(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("TERM_PROGRAM", raising=False)
        monkeypatch.delenv("TERMINAL_EMULATOR", raising=False)
        monkeypatch.setenv("WT_SESSION", "some-guid")
        monkeypatch.delenv("KITTY_WINDOW_ID", raising=False)
        assert _detect_terminal_program() == "Windows Terminal"

    def test_kitty_via_window_id(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("TERM_PROGRAM", raising=False)
        monkeypatch.delenv("TERMINAL_EMULATOR", raising=False)
        monkeypatch.delenv("WT_SESSION", raising=False)
        monkeypatch.setenv("KITTY_WINDOW_ID", "1")
        assert _detect_terminal_program() == "kitty"

    def test_unknown(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("TERM_PROGRAM", raising=False)
        monkeypatch.delenv("TERMINAL_EMULATOR", raising=False)
        monkeypatch.delenv("WT_SESSION", raising=False)
        monkeypatch.delenv("KITTY_WINDOW_ID", raising=False)
        assert _detect_terminal_program() is None

    def test_term_program_takes_precedence(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("TERM_PROGRAM", "Apple_Terminal")
        monkeypatch.setenv("WT_SESSION", "some-guid")
        assert _detect_terminal_program() == "Apple_Terminal"


# ---------------------------------------------------------------------------
# _detect_terminal_size
# ---------------------------------------------------------------------------


class TestDetectTerminalSize:
    """Terminal size detection with fallback."""

    def test_fallback_when_not_tty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When os.get_terminal_size() raises, fall back to 80x24."""
        # Patch the module-level reference so pytest's own terminal
        # detection (which also calls os.get_terminal_size) is unaffected.
        import wyby.diagnostics as _diag

        monkeypatch.setattr(
            _diag.os, "get_terminal_size", lambda *_args: (_ for _ in ()).throw(OSError)
        )
        assert _detect_terminal_size() == (80, 24)

    def test_returns_actual_size(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import wyby.diagnostics as _diag

        monkeypatch.setattr(
            _diag.os, "get_terminal_size", lambda *_args: os.terminal_size((120, 40))
        )
        assert _detect_terminal_size() == (120, 40)


# ---------------------------------------------------------------------------
# TerminalCapabilities
# ---------------------------------------------------------------------------


class TestTerminalCapabilities:
    """TerminalCapabilities dataclass-like properties."""

    def _make_caps(self, **overrides: object) -> TerminalCapabilities:
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

    def test_properties(self) -> None:
        caps = self._make_caps()
        assert caps.color_support == ColorSupport.TRUECOLOR
        assert caps.utf8_supported is True
        assert caps.is_tty is True
        assert caps.terminal_program == "iTerm.app"
        assert caps.columns == 120
        assert caps.rows == 40
        assert caps.colorterm_env == "truecolor"
        assert caps.term_env == "xterm-256color"

    def test_repr(self) -> None:
        caps = self._make_caps()
        r = repr(caps)
        assert "TerminalCapabilities" in r
        assert "TRUECOLOR" in r
        assert "120x40" in r
        assert "iTerm.app" in r

    def test_equality(self) -> None:
        caps1 = self._make_caps()
        caps2 = self._make_caps()
        assert caps1 == caps2

    def test_inequality(self) -> None:
        caps1 = self._make_caps(color_support=ColorSupport.TRUECOLOR)
        caps2 = self._make_caps(color_support=ColorSupport.STANDARD)
        assert caps1 != caps2

    def test_equality_with_non_caps_returns_not_implemented(self) -> None:
        caps = self._make_caps()
        assert caps.__eq__(42) is NotImplemented


# ---------------------------------------------------------------------------
# detect_capabilities (integration)
# ---------------------------------------------------------------------------


class TestDetectCapabilities:
    """Integration test for detect_capabilities()."""

    def test_returns_terminal_capabilities(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("COLORTERM", "truecolor")
        monkeypatch.setenv("TERM", "xterm-256color")
        monkeypatch.setenv("TERM_PROGRAM", "iTerm.app")
        monkeypatch.setenv("LANG", "en_US.UTF-8")
        monkeypatch.delenv("LC_ALL", raising=False)
        monkeypatch.delenv("LC_CTYPE", raising=False)

        caps = detect_capabilities()
        assert isinstance(caps, TerminalCapabilities)
        assert caps.color_support == ColorSupport.TRUECOLOR
        assert caps.utf8_supported is True
        assert caps.terminal_program == "iTerm.app"
        assert caps.colorterm_env == "truecolor"
        assert caps.term_env == "xterm-256color"

    def test_no_color_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("COLORTERM", raising=False)
        monkeypatch.setenv("TERM", "dumb")
        monkeypatch.delenv("TERM_PROGRAM", raising=False)
        monkeypatch.delenv("TERMINAL_EMULATOR", raising=False)
        monkeypatch.delenv("WT_SESSION", raising=False)
        monkeypatch.delenv("KITTY_WINDOW_ID", raising=False)
        monkeypatch.delenv("LC_ALL", raising=False)
        monkeypatch.delenv("LC_CTYPE", raising=False)
        monkeypatch.setenv("LANG", "C")

        caps = detect_capabilities()
        assert caps.color_support == ColorSupport.NONE
        assert caps.utf8_supported is False
        assert caps.terminal_program is None

    def test_columns_and_rows_populated(self) -> None:
        caps = detect_capabilities()
        assert isinstance(caps.columns, int)
        assert isinstance(caps.rows, int)
        assert caps.columns > 0
        assert caps.rows > 0

    def test_is_tty_is_bool(self) -> None:
        caps = detect_capabilities()
        assert isinstance(caps.is_tty, bool)


# ---------------------------------------------------------------------------
# Package-level exports
# ---------------------------------------------------------------------------


class TestCapabilityExports:
    """New types should be importable from the top-level package."""

    def test_color_support_importable(self) -> None:
        from wyby import ColorSupport as CS

        assert CS is ColorSupport

    def test_terminal_capabilities_importable(self) -> None:
        from wyby import TerminalCapabilities as TC

        assert TC is TerminalCapabilities

    def test_detect_capabilities_importable(self) -> None:
        from wyby import detect_capabilities as dc

        assert dc is detect_capabilities

    def test_in_all(self) -> None:
        import wyby

        assert "ColorSupport" in wyby.__all__
        assert "TerminalCapabilities" in wyby.__all__
        assert "detect_capabilities" in wyby.__all__
