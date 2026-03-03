"""Tests for wyby.cursor — cursor visibility management."""

from __future__ import annotations

import logging

import pytest

from wyby.cursor import (
    HiddenCursor,
    _HIDE_SEQ,
    _SHOW_SEQ,
    hide_cursor,
    is_cursor_hidden,
    show_cursor,
)
import wyby.cursor as cursor_module


@pytest.fixture(autouse=True)
def _reset_cursor_state():
    """Ensure cursor state is clean before and after each test."""
    cursor_module._hidden = False
    yield
    cursor_module._hidden = False


class FakeStream:
    """Minimal writable stream that captures output."""

    def __init__(self) -> None:
        self.written: list[str] = []
        self.flushed: int = 0

    def write(self, data: str) -> int:
        self.written.append(data)
        return len(data)

    def flush(self) -> None:
        self.flushed += 1


class BrokenStream:
    """Stream that raises OSError on write."""

    def write(self, data: str) -> int:
        raise OSError("broken pipe")

    def flush(self) -> None:
        raise OSError("broken pipe")


class ClosedStream:
    """Stream that raises ValueError (closed file) on write."""

    def write(self, data: str) -> int:
        raise ValueError("I/O operation on closed file")

    def flush(self) -> None:
        raise ValueError("I/O operation on closed file")


# ---------------------------------------------------------------------------
# Escape sequence constants
# ---------------------------------------------------------------------------


class TestEscapeSequences:
    """Verify the escape sequence constants are correct."""

    def test_hide_sequence(self) -> None:
        assert _HIDE_SEQ == "\033[?25l"

    def test_show_sequence(self) -> None:
        assert _SHOW_SEQ == "\033[?25h"


# ---------------------------------------------------------------------------
# hide_cursor()
# ---------------------------------------------------------------------------


class TestHideCursor:
    """Tests for hide_cursor()."""

    def test_writes_hide_sequence_to_stream(self) -> None:
        stream = FakeStream()
        result = hide_cursor(stream=stream)
        assert result is True
        assert stream.written == [_HIDE_SEQ]

    def test_flushes_after_write(self) -> None:
        stream = FakeStream()
        hide_cursor(stream=stream)
        assert stream.flushed == 1

    def test_sets_hidden_flag(self) -> None:
        stream = FakeStream()
        assert is_cursor_hidden() is False
        hide_cursor(stream=stream)
        assert is_cursor_hidden() is True

    def test_skips_when_already_hidden(self) -> None:
        stream = FakeStream()
        hide_cursor(stream=stream)
        result = hide_cursor(stream=stream)
        assert result is False
        # Only one write should have happened.
        assert len(stream.written) == 1

    def test_returns_true_on_success(self) -> None:
        stream = FakeStream()
        assert hide_cursor(stream=stream) is True

    def test_returns_false_when_already_hidden(self) -> None:
        stream = FakeStream()
        hide_cursor(stream=stream)
        assert hide_cursor(stream=stream) is False

    def test_skips_when_stdout_not_tty(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When no custom stream and stdout is not a TTY, skip."""
        monkeypatch.setattr(cursor_module, "_is_tty", lambda: False)
        result = hide_cursor()
        assert result is False
        assert is_cursor_hidden() is False

    def test_handles_broken_stream(self) -> None:
        stream = BrokenStream()
        result = hide_cursor(stream=stream)
        assert result is False
        assert is_cursor_hidden() is False

    def test_handles_closed_stream(self) -> None:
        stream = ClosedStream()
        result = hide_cursor(stream=stream)
        assert result is False
        assert is_cursor_hidden() is False

    def test_logs_on_hide(self, caplog: pytest.LogCaptureFixture) -> None:
        stream = FakeStream()
        with caplog.at_level(logging.DEBUG, logger="wyby.cursor"):
            hide_cursor(stream=stream)
        messages = [r.message for r in caplog.records]
        assert any("hidden" in m.lower() for m in messages)

    def test_logs_skip_when_hidden(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        stream = FakeStream()
        hide_cursor(stream=stream)
        with caplog.at_level(logging.DEBUG, logger="wyby.cursor"):
            hide_cursor(stream=stream)
        messages = [r.message for r in caplog.records]
        assert any("already hidden" in m for m in messages)

    def test_logs_skip_when_not_tty(
        self,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        monkeypatch.setattr(cursor_module, "_is_tty", lambda: False)
        with caplog.at_level(logging.DEBUG, logger="wyby.cursor"):
            hide_cursor()
        messages = [r.message for r in caplog.records]
        assert any("not a TTY" in m for m in messages)


# ---------------------------------------------------------------------------
# show_cursor()
# ---------------------------------------------------------------------------


class TestShowCursor:
    """Tests for show_cursor()."""

    def test_writes_show_sequence_to_stream(self) -> None:
        stream = FakeStream()
        hide_cursor(stream=stream)
        stream.written.clear()
        result = show_cursor(stream=stream)
        assert result is True
        assert stream.written == [_SHOW_SEQ]

    def test_flushes_after_write(self) -> None:
        stream = FakeStream()
        hide_cursor(stream=stream)
        stream.flushed = 0
        show_cursor(stream=stream)
        assert stream.flushed == 1

    def test_clears_hidden_flag(self) -> None:
        stream = FakeStream()
        hide_cursor(stream=stream)
        assert is_cursor_hidden() is True
        show_cursor(stream=stream)
        assert is_cursor_hidden() is False

    def test_skips_when_not_hidden(self) -> None:
        stream = FakeStream()
        result = show_cursor(stream=stream)
        assert result is False
        assert stream.written == []

    def test_returns_true_on_success(self) -> None:
        stream = FakeStream()
        hide_cursor(stream=stream)
        assert show_cursor(stream=stream) is True

    def test_returns_false_when_not_hidden(self) -> None:
        assert show_cursor(stream=FakeStream()) is False

    def test_handles_broken_stream(self) -> None:
        """Broken stream on show: flag should still be cleared."""
        stream = FakeStream()
        hide_cursor(stream=stream)
        broken = BrokenStream()
        result = show_cursor(stream=broken)
        assert result is False
        # Flag should still be cleared — the terminal session is gone.
        assert is_cursor_hidden() is False

    def test_handles_closed_stream(self) -> None:
        stream = FakeStream()
        hide_cursor(stream=stream)
        closed = ClosedStream()
        result = show_cursor(stream=closed)
        assert result is False
        assert is_cursor_hidden() is False

    def test_logs_on_show(self, caplog: pytest.LogCaptureFixture) -> None:
        stream = FakeStream()
        hide_cursor(stream=stream)
        with caplog.at_level(logging.DEBUG, logger="wyby.cursor"):
            show_cursor(stream=stream)
        messages = [r.message for r in caplog.records]
        assert any("shown" in m.lower() for m in messages)

    def test_logs_skip_when_not_hidden(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.DEBUG, logger="wyby.cursor"):
            show_cursor(stream=FakeStream())
        messages = [r.message for r in caplog.records]
        assert any("not hidden" in m for m in messages)


# ---------------------------------------------------------------------------
# is_cursor_hidden()
# ---------------------------------------------------------------------------


class TestIsCursorHidden:
    """Tests for the is_cursor_hidden() query function."""

    def test_false_by_default(self) -> None:
        assert is_cursor_hidden() is False

    def test_true_after_hide(self) -> None:
        hide_cursor(stream=FakeStream())
        assert is_cursor_hidden() is True

    def test_false_after_hide_then_show(self) -> None:
        stream = FakeStream()
        hide_cursor(stream=stream)
        show_cursor(stream=stream)
        assert is_cursor_hidden() is False


# ---------------------------------------------------------------------------
# HiddenCursor context manager
# ---------------------------------------------------------------------------


class TestHiddenCursorContextManager:
    """Tests for the HiddenCursor context manager."""

    def test_hides_on_enter(self) -> None:
        stream = FakeStream()
        with HiddenCursor(stream=stream) as ctx:
            assert is_cursor_hidden() is True
            assert ctx.entered is True
        assert stream.written[0] == _HIDE_SEQ

    def test_shows_on_exit(self) -> None:
        stream = FakeStream()
        with HiddenCursor(stream=stream):
            pass
        assert is_cursor_hidden() is False
        assert _SHOW_SEQ in stream.written

    def test_shows_on_exception(self) -> None:
        stream = FakeStream()
        with pytest.raises(RuntimeError):
            with HiddenCursor(stream=stream):
                raise RuntimeError("boom")
        assert is_cursor_hidden() is False
        assert _SHOW_SEQ in stream.written

    def test_entered_false_when_not_tty(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(cursor_module, "_is_tty", lambda: False)
        with HiddenCursor() as ctx:
            assert ctx.entered is False
            assert is_cursor_hidden() is False

    def test_no_show_when_not_entered(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """If hide was skipped (not a TTY), show should be skipped too."""
        monkeypatch.setattr(cursor_module, "_is_tty", lambda: False)
        with HiddenCursor() as ctx:
            assert ctx.entered is False
        assert is_cursor_hidden() is False

    def test_write_order(self) -> None:
        stream = FakeStream()
        with HiddenCursor(stream=stream):
            pass
        assert stream.written == [_HIDE_SEQ, _SHOW_SEQ]

    def test_repr_before_enter(self) -> None:
        ctx = HiddenCursor()
        assert repr(ctx) == "HiddenCursor(hidden=False)"

    def test_repr_inside_context(self) -> None:
        stream = FakeStream()
        with HiddenCursor(stream=stream) as ctx:
            assert repr(ctx) == "HiddenCursor(hidden=True)"

    def test_repr_after_exit(self) -> None:
        stream = FakeStream()
        ctx = HiddenCursor(stream=stream)
        with ctx:
            pass
        assert "HiddenCursor(" in repr(ctx)


# ---------------------------------------------------------------------------
# Hide/show round-trip
# ---------------------------------------------------------------------------


class TestRoundTrip:
    """Verify hide -> show -> hide works correctly."""

    def test_hide_show_hide(self) -> None:
        stream = FakeStream()
        assert hide_cursor(stream=stream) is True
        assert show_cursor(stream=stream) is True
        assert hide_cursor(stream=stream) is True
        assert stream.written == [_HIDE_SEQ, _SHOW_SEQ, _HIDE_SEQ]

    def test_double_show_is_noop(self) -> None:
        stream = FakeStream()
        hide_cursor(stream=stream)
        assert show_cursor(stream=stream) is True
        assert show_cursor(stream=stream) is False

    def test_double_hide_is_noop(self) -> None:
        stream = FakeStream()
        assert hide_cursor(stream=stream) is True
        assert hide_cursor(stream=stream) is False


# ---------------------------------------------------------------------------
# Public re-export from wyby package
# ---------------------------------------------------------------------------


class TestCursorImport:
    """Cursor API should be importable from the top-level wyby package."""

    def test_hide_cursor_importable(self) -> None:
        from wyby import hide_cursor as fn

        assert fn is hide_cursor

    def test_show_cursor_importable(self) -> None:
        from wyby import show_cursor as fn

        assert fn is show_cursor

    def test_is_cursor_hidden_importable(self) -> None:
        from wyby import is_cursor_hidden as fn

        assert fn is is_cursor_hidden

    def test_context_manager_importable(self) -> None:
        from wyby import HiddenCursor as cls

        assert cls is HiddenCursor
