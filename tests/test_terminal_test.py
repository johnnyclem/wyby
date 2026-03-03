"""Tests for wyby.terminal_test — manual test-card for terminal emulator verification."""

from __future__ import annotations

import pytest

from wyby.diagnostics import ColorSupport, TerminalCapabilities
from wyby.grid import CellBuffer
from wyby.terminal_test import (
    TERMINAL_CAVEATS,
    TestCard,
    _CARD_HEIGHT,
    _CARD_WIDTH,
    build_test_card,
    format_report,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_caps(
    *,
    terminal_program: str | None = "TestTerm",
    color_support: ColorSupport = ColorSupport.TRUECOLOR,
    utf8_supported: bool = True,
    is_tty: bool = True,
    columns: int = 80,
    rows: int = 24,
    colorterm_env: str = "truecolor",
    term_env: str = "xterm-256color",
) -> TerminalCapabilities:
    """Create a TerminalCapabilities with controllable values."""
    return TerminalCapabilities(
        color_support=color_support,
        utf8_supported=utf8_supported,
        is_tty=is_tty,
        terminal_program=terminal_program,
        columns=columns,
        rows=rows,
        colorterm_env=colorterm_env,
        term_env=term_env,
    )


# ---------------------------------------------------------------------------
# TestCard construction
# ---------------------------------------------------------------------------


class TestTestCardConstruction:
    """Tests for TestCard instantiation."""

    def test_default_caps_detected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When caps is None, detect_capabilities is called."""
        monkeypatch.setenv("TERM_PROGRAM", "FakeTerminal")
        card = TestCard()
        # Should have detected something (exact value depends on env).
        assert card.capabilities is not None

    def test_explicit_caps_used(self) -> None:
        caps = _make_caps(terminal_program="MyTerm")
        card = TestCard(caps=caps)
        assert card.capabilities is caps
        assert card.capabilities.terminal_program == "MyTerm"

    def test_default_dimensions(self) -> None:
        caps = _make_caps()
        card = TestCard(caps=caps)
        assert card.width == _CARD_WIDTH
        assert card.height == _CARD_HEIGHT

    def test_custom_dimensions(self) -> None:
        caps = _make_caps()
        card = TestCard(caps=caps, width=40, height=10)
        assert card.width == 40
        assert card.height == 10

    def test_width_clamped_to_minimum(self) -> None:
        caps = _make_caps()
        card = TestCard(caps=caps, width=0)
        assert card.width >= 1

    def test_height_clamped_to_minimum(self) -> None:
        caps = _make_caps()
        card = TestCard(caps=caps, height=-5)
        assert card.height >= 1


# ---------------------------------------------------------------------------
# TestCard.build()
# ---------------------------------------------------------------------------


class TestTestCardBuild:
    """Tests for TestCard.build() output."""

    def test_returns_cell_buffer(self) -> None:
        caps = _make_caps()
        card = TestCard(caps=caps)
        buf = card.build()
        assert isinstance(buf, CellBuffer)

    def test_buffer_dimensions_match(self) -> None:
        caps = _make_caps()
        card = TestCard(caps=caps, width=60, height=20)
        buf = card.build()
        assert buf.width == 60
        assert buf.height == 20

    def test_default_buffer_dimensions(self) -> None:
        caps = _make_caps()
        card = TestCard(caps=caps)
        buf = card.build()
        assert buf.width == _CARD_WIDTH
        assert buf.height == _CARD_HEIGHT

    def test_header_contains_terminal_name(self) -> None:
        """The first row should contain the terminal program name."""
        caps = _make_caps(terminal_program="FancyTerm")
        card = TestCard(caps=caps)
        buf = card.build()
        row = buf.row(0)
        assert row is not None
        text = "".join(c.char for c in row).strip()
        assert "FancyTerm" in text

    def test_header_contains_size(self) -> None:
        """The first row should contain the terminal dimensions."""
        caps = _make_caps(columns=120, rows=40)
        card = TestCard(caps=caps)
        buf = card.build()
        row = buf.row(0)
        assert row is not None
        text = "".join(c.char for c in row).strip()
        assert "120x40" in text

    def test_buffer_has_non_blank_content(self) -> None:
        """The test card should have non-space content."""
        caps = _make_caps()
        card = TestCard(caps=caps)
        buf = card.build()
        non_blank = False
        for y in range(buf.height):
            row = buf.row(y)
            assert row is not None
            for cell in row:
                if cell.char != " ":
                    non_blank = True
                    break
            if non_blank:
                break
        assert non_blank, "Test card buffer is entirely blank"

    def test_contains_box_drawing_characters(self) -> None:
        """Buffer should contain box-drawing characters."""
        caps = _make_caps()
        card = TestCard(caps=caps)
        buf = card.build()
        box_chars = set("─│┌┐└┘├┤┬┴┼╔═╦╗║╠╬╣╚╩╝")
        found = set()
        for y in range(buf.height):
            row = buf.row(y)
            assert row is not None
            for cell in row:
                if cell.char in box_chars:
                    found.add(cell.char)
        assert len(found) > 0, "No box-drawing characters found"

    def test_contains_block_elements(self) -> None:
        """Buffer should contain block element characters."""
        caps = _make_caps()
        card = TestCard(caps=caps)
        buf = card.build()
        block_chars = set("█▓▒░▀▄▌▐")
        found = set()
        for y in range(buf.height):
            row = buf.row(y)
            assert row is not None
            for cell in row:
                if cell.char in block_chars:
                    found.add(cell.char)
        assert len(found) > 0, "No block element characters found"

    def test_contains_styled_cells(self) -> None:
        """Buffer should have cells with fg/bg colours or bold/dim."""
        caps = _make_caps()
        card = TestCard(caps=caps)
        buf = card.build()
        styled = False
        for y in range(buf.height):
            row = buf.row(y)
            assert row is not None
            for cell in row:
                if cell.fg or cell.bg or cell.bold or cell.dim:
                    styled = True
                    break
            if styled:
                break
        assert styled, "No styled cells found"

    def test_contains_bold_cells(self) -> None:
        """Buffer should have at least one bold cell."""
        caps = _make_caps()
        card = TestCard(caps=caps)
        buf = card.build()
        found = any(
            cell.bold
            for y in range(buf.height)
            for cell in (buf.row(y) or [])
        )
        assert found, "No bold cells found"

    def test_contains_dim_cells(self) -> None:
        """Buffer should have at least one dim cell."""
        caps = _make_caps()
        card = TestCard(caps=caps)
        buf = card.build()
        found = any(
            cell.dim
            for y in range(buf.height)
            for cell in (buf.row(y) or [])
        )
        assert found, "No dim cells found"

    def test_contains_bg_coloured_cells(self) -> None:
        """Buffer should have cells with background colours set."""
        caps = _make_caps()
        card = TestCard(caps=caps)
        buf = card.build()
        found = any(
            cell.bg is not None
            for y in range(buf.height)
            for cell in (buf.row(y) or [])
        )
        assert found, "No background-coloured cells found"

    def test_contains_truecolor_cells(self) -> None:
        """Buffer should have hex-colour cells from the truecolor gradient."""
        caps = _make_caps()
        card = TestCard(caps=caps)
        buf = card.build()
        found = any(
            cell.bg is not None and cell.bg.startswith("#")
            for y in range(buf.height)
            for cell in (buf.row(y) or [])
        )
        assert found, "No truecolor (hex) cells found"

    def test_contains_wide_chars(self) -> None:
        """Buffer should contain CJK wide characters."""
        caps = _make_caps()
        card = TestCard(caps=caps)
        buf = card.build()
        cjk_chars = set("漢字テスト中文")
        found = any(
            cell.char in cjk_chars
            for y in range(buf.height)
            for cell in (buf.row(y) or [])
        )
        assert found, "No CJK wide characters found"


# ---------------------------------------------------------------------------
# include_emoji option
# ---------------------------------------------------------------------------


class TestIncludeEmoji:
    """Tests for the include_emoji parameter."""

    def test_emoji_included_by_default(self) -> None:
        caps = _make_caps()
        card = TestCard(caps=caps)
        buf = card.build()
        # Check for symbol characters used in the emoji row.
        symbols = set("★♠♣♥♦")
        found = any(
            cell.char in symbols
            for y in range(buf.height)
            for cell in (buf.row(y) or [])
        )
        assert found, "Emoji row symbols not found (default should include)"

    def test_emoji_excluded_when_disabled(self) -> None:
        caps = _make_caps()
        card = TestCard(caps=caps, include_emoji=False)
        buf = card.build()
        symbols = set("★♠♣♥♦")
        found = any(
            cell.char in symbols
            for y in range(buf.height)
            for cell in (buf.row(y) or [])
        )
        assert not found, "Emoji row symbols found but include_emoji=False"


# ---------------------------------------------------------------------------
# TestCard.report()
# ---------------------------------------------------------------------------


class TestTestCardReport:
    """Tests for TestCard.report()."""

    def test_report_returns_string(self) -> None:
        caps = _make_caps()
        card = TestCard(caps=caps)
        report = card.report()
        assert isinstance(report, str)

    def test_report_contains_terminal_program(self) -> None:
        caps = _make_caps(terminal_program="FancyTerm")
        card = TestCard(caps=caps)
        report = card.report()
        assert "FancyTerm" in report

    def test_report_contains_color_support(self) -> None:
        caps = _make_caps(color_support=ColorSupport.TRUECOLOR)
        card = TestCard(caps=caps)
        report = card.report()
        assert "TRUECOLOR" in report

    def test_report_contains_utf8_status(self) -> None:
        caps = _make_caps(utf8_supported=True)
        card = TestCard(caps=caps)
        report = card.report()
        assert "True" in report

    def test_report_contains_terminal_size(self) -> None:
        caps = _make_caps(columns=132, rows=50)
        card = TestCard(caps=caps)
        report = card.report()
        assert "132x50" in report

    def test_report_contains_caveat_for_known_terminal(self) -> None:
        caps = _make_caps(terminal_program="iTerm2")
        card = TestCard(caps=caps)
        report = card.report()
        assert "truecolor" in report.lower() or "ligature" in report.lower()

    def test_report_contains_caveat_for_unknown_terminal(self) -> None:
        caps = _make_caps(terminal_program=None)
        card = TestCard(caps=caps)
        report = card.report()
        assert "not identified" in report.lower()

    def test_report_mentions_tmux_caveat(self) -> None:
        """The report should note tmux/screen caveat in the footer."""
        caps = _make_caps()
        card = TestCard(caps=caps)
        report = card.report()
        assert "tmux" in report.lower()

    def test_report_shows_unknown_for_none_program(self) -> None:
        caps = _make_caps(terminal_program=None)
        card = TestCard(caps=caps)
        report = card.report()
        assert "(unknown)" in report

    def test_report_shows_unset_for_empty_colorterm(self) -> None:
        caps = _make_caps(colorterm_env="")
        card = TestCard(caps=caps)
        report = card.report()
        assert "(unset)" in report


# ---------------------------------------------------------------------------
# TERMINAL_CAVEATS
# ---------------------------------------------------------------------------


class TestTerminalCaveats:
    """Tests for the TERMINAL_CAVEATS mapping."""

    def test_is_dict(self) -> None:
        assert isinstance(TERMINAL_CAVEATS, dict)

    def test_has_none_key(self) -> None:
        """Should have a caveat for unidentified terminals."""
        assert None in TERMINAL_CAVEATS

    def test_has_iterm2(self) -> None:
        assert "iTerm2" in TERMINAL_CAVEATS

    def test_has_apple_terminal(self) -> None:
        assert "Apple_Terminal" in TERMINAL_CAVEATS

    def test_has_kitty(self) -> None:
        assert "kitty" in TERMINAL_CAVEATS

    def test_has_windows_terminal(self) -> None:
        assert "Windows Terminal" in TERMINAL_CAVEATS

    def test_has_tmux(self) -> None:
        assert "tmux" in TERMINAL_CAVEATS

    def test_has_screen(self) -> None:
        assert "screen" in TERMINAL_CAVEATS

    def test_values_are_strings(self) -> None:
        for key, value in TERMINAL_CAVEATS.items():
            assert isinstance(value, str), f"Caveat for {key!r} is not a string"

    def test_values_are_non_empty(self) -> None:
        for key, value in TERMINAL_CAVEATS.items():
            assert len(value) > 0, f"Caveat for {key!r} is empty"


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------


class TestBuildTestCard:
    """Tests for the build_test_card() convenience function."""

    def test_returns_cell_buffer(self) -> None:
        buf = build_test_card()
        assert isinstance(buf, CellBuffer)

    def test_default_dimensions(self) -> None:
        buf = build_test_card()
        assert buf.width == _CARD_WIDTH
        assert buf.height == _CARD_HEIGHT

    def test_custom_dimensions(self) -> None:
        buf = build_test_card(width=40, height=12)
        assert buf.width == 40
        assert buf.height == 12

    def test_no_emoji_option(self) -> None:
        buf = build_test_card(include_emoji=False)
        assert isinstance(buf, CellBuffer)


class TestFormatReport:
    """Tests for the format_report() convenience function."""

    def test_returns_string(self) -> None:
        caps = _make_caps()
        report = format_report(caps)
        assert isinstance(report, str)

    def test_auto_detects_when_none(self) -> None:
        report = format_report()
        assert isinstance(report, str)
        assert "wyby terminal test report" in report

    def test_contains_header(self) -> None:
        caps = _make_caps()
        report = format_report(caps)
        assert "wyby terminal test report" in report


# ---------------------------------------------------------------------------
# Small buffer edge cases
# ---------------------------------------------------------------------------


class TestSmallBufferEdgeCases:
    """Test card gracefully handles very small buffer dimensions."""

    def test_1x1_buffer(self) -> None:
        """Should not crash with a 1x1 buffer."""
        caps = _make_caps()
        card = TestCard(caps=caps, width=1, height=1)
        buf = card.build()
        assert buf.width == 1
        assert buf.height == 1

    def test_narrow_buffer(self) -> None:
        """Should not crash with a very narrow buffer."""
        caps = _make_caps()
        card = TestCard(caps=caps, width=5, height=20)
        buf = card.build()
        assert buf.width == 5

    def test_short_buffer(self) -> None:
        """Should not crash with a very short buffer."""
        caps = _make_caps()
        card = TestCard(caps=caps, width=80, height=3)
        buf = card.build()
        assert buf.height == 3


# ---------------------------------------------------------------------------
# Rich renderable protocol
# ---------------------------------------------------------------------------


class TestRichRenderable:
    """Test that the built CellBuffer works with Rich rendering."""

    def test_buffer_renders_to_rich(self) -> None:
        """CellBuffer from TestCard should implement __rich_console__."""
        import io

        from rich.console import Console

        caps = _make_caps()
        card = TestCard(caps=caps)
        buf = card.build()

        console = Console(
            file=io.StringIO(), force_terminal=True, width=80, height=30,
        )
        # Should not raise — CellBuffer implements __rich_console__.
        console.print(buf)
        output = console.file.getvalue()
        assert len(output) > 0, "Rich rendering produced no output"

    def test_buffer_renders_with_ansi(self) -> None:
        """The rendered output should contain ANSI escape sequences."""
        import io

        from rich.console import Console

        caps = _make_caps()
        card = TestCard(caps=caps)
        buf = card.build()

        console = Console(
            file=io.StringIO(), force_terminal=True, width=80, height=30,
            color_system="truecolor",
        )
        console.print(buf)
        output = console.file.getvalue()
        # ANSI escape sequences start with ESC (0x1b).
        assert "\x1b" in output, "No ANSI escape sequences in output"


# ---------------------------------------------------------------------------
# Package exports
# ---------------------------------------------------------------------------


class TestPackageExports:
    """Tests that terminal_test is exported from the wyby package."""

    def test_test_card_importable(self) -> None:
        from wyby import TestCard as TC
        assert TC is TestCard

    def test_build_test_card_importable(self) -> None:
        from wyby import build_test_card as btc
        assert btc is build_test_card

    def test_format_report_importable(self) -> None:
        from wyby import format_report as fr
        assert fr is format_report

    def test_terminal_caveats_importable(self) -> None:
        from wyby import TERMINAL_CAVEATS as tc
        assert tc is TERMINAL_CAVEATS

    def test_test_card_in_all(self) -> None:
        import wyby
        assert "TestCard" in wyby.__all__

    def test_build_test_card_in_all(self) -> None:
        import wyby
        assert "build_test_card" in wyby.__all__

    def test_format_report_in_all(self) -> None:
        import wyby
        assert "format_report" in wyby.__all__

    def test_terminal_caveats_in_all(self) -> None:
        import wyby
        assert "TERMINAL_CAVEATS" in wyby.__all__
