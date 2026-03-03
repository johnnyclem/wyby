"""Tests for wyby.alt_screen — alternate screen buffer management."""

from __future__ import annotations

import logging

import pytest

from wyby.alt_screen import (
    AltScreen,
    _DISABLE_SEQ,
    _ENABLE_SEQ,
    disable_alt_screen,
    enable_alt_screen,
    is_active,
)
import wyby.alt_screen as alt_screen_module


@pytest.fixture(autouse=True)
def _reset_alt_screen_state():
    """Ensure alt-screen state is clean before and after each test."""
    alt_screen_module._active = False
    yield
    alt_screen_module._active = False


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

    def test_enable_sequence(self) -> None:
        assert _ENABLE_SEQ == "\033[?1049h"

    def test_disable_sequence(self) -> None:
        assert _DISABLE_SEQ == "\033[?1049l"


# ---------------------------------------------------------------------------
# enable_alt_screen()
# ---------------------------------------------------------------------------


class TestEnableAltScreen:
    """Tests for enable_alt_screen()."""

    def test_writes_enable_sequence_to_stream(self) -> None:
        stream = FakeStream()
        result = enable_alt_screen(stream=stream)
        assert result is True
        assert stream.written == [_ENABLE_SEQ]

    def test_flushes_after_write(self) -> None:
        stream = FakeStream()
        enable_alt_screen(stream=stream)
        assert stream.flushed == 1

    def test_sets_active_flag(self) -> None:
        stream = FakeStream()
        assert is_active() is False
        enable_alt_screen(stream=stream)
        assert is_active() is True

    def test_skips_when_already_active(self) -> None:
        stream = FakeStream()
        enable_alt_screen(stream=stream)
        result = enable_alt_screen(stream=stream)
        assert result is False
        # Only one write should have happened.
        assert len(stream.written) == 1

    def test_returns_true_on_success(self) -> None:
        stream = FakeStream()
        assert enable_alt_screen(stream=stream) is True

    def test_returns_false_when_already_active(self) -> None:
        stream = FakeStream()
        enable_alt_screen(stream=stream)
        assert enable_alt_screen(stream=stream) is False

    def test_skips_when_stdout_not_tty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When no custom stream and stdout is not a TTY, skip."""
        monkeypatch.setattr(alt_screen_module, "_is_tty", lambda: False)
        result = enable_alt_screen()
        assert result is False
        assert is_active() is False

    def test_handles_broken_stream(self) -> None:
        stream = BrokenStream()
        result = enable_alt_screen(stream=stream)
        assert result is False
        assert is_active() is False

    def test_handles_closed_stream(self) -> None:
        stream = ClosedStream()
        result = enable_alt_screen(stream=stream)
        assert result is False
        assert is_active() is False

    def test_logs_on_enable(self, caplog: pytest.LogCaptureFixture) -> None:
        stream = FakeStream()
        with caplog.at_level(logging.DEBUG, logger="wyby.alt_screen"):
            enable_alt_screen(stream=stream)
        messages = [r.message for r in caplog.records]
        assert any("enabled" in m.lower() for m in messages)

    def test_logs_skip_when_active(self, caplog: pytest.LogCaptureFixture) -> None:
        stream = FakeStream()
        enable_alt_screen(stream=stream)
        with caplog.at_level(logging.DEBUG, logger="wyby.alt_screen"):
            enable_alt_screen(stream=stream)
        messages = [r.message for r in caplog.records]
        assert any("already active" in m for m in messages)

    def test_logs_skip_when_not_tty(
        self,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        monkeypatch.setattr(alt_screen_module, "_is_tty", lambda: False)
        with caplog.at_level(logging.DEBUG, logger="wyby.alt_screen"):
            enable_alt_screen()
        messages = [r.message for r in caplog.records]
        assert any("not a TTY" in m for m in messages)


# ---------------------------------------------------------------------------
# disable_alt_screen()
# ---------------------------------------------------------------------------


class TestDisableAltScreen:
    """Tests for disable_alt_screen()."""

    def test_writes_disable_sequence_to_stream(self) -> None:
        stream = FakeStream()
        enable_alt_screen(stream=stream)
        stream.written.clear()
        result = disable_alt_screen(stream=stream)
        assert result is True
        assert stream.written == [_DISABLE_SEQ]

    def test_flushes_after_write(self) -> None:
        stream = FakeStream()
        enable_alt_screen(stream=stream)
        stream.flushed = 0
        disable_alt_screen(stream=stream)
        assert stream.flushed == 1

    def test_clears_active_flag(self) -> None:
        stream = FakeStream()
        enable_alt_screen(stream=stream)
        assert is_active() is True
        disable_alt_screen(stream=stream)
        assert is_active() is False

    def test_skips_when_not_active(self) -> None:
        stream = FakeStream()
        result = disable_alt_screen(stream=stream)
        assert result is False
        assert stream.written == []

    def test_returns_true_on_success(self) -> None:
        stream = FakeStream()
        enable_alt_screen(stream=stream)
        assert disable_alt_screen(stream=stream) is True

    def test_returns_false_when_not_active(self) -> None:
        assert disable_alt_screen(stream=FakeStream()) is False

    def test_handles_broken_stream(self) -> None:
        """Broken stream on disable: flag should still be cleared."""
        stream = FakeStream()
        enable_alt_screen(stream=stream)
        broken = BrokenStream()
        result = disable_alt_screen(stream=broken)
        assert result is False
        # Flag should still be cleared — the terminal session is gone.
        assert is_active() is False

    def test_handles_closed_stream(self) -> None:
        stream = FakeStream()
        enable_alt_screen(stream=stream)
        closed = ClosedStream()
        result = disable_alt_screen(stream=closed)
        assert result is False
        assert is_active() is False

    def test_logs_on_disable(self, caplog: pytest.LogCaptureFixture) -> None:
        stream = FakeStream()
        enable_alt_screen(stream=stream)
        with caplog.at_level(logging.DEBUG, logger="wyby.alt_screen"):
            disable_alt_screen(stream=stream)
        messages = [r.message for r in caplog.records]
        assert any("disabled" in m.lower() for m in messages)

    def test_logs_skip_when_not_active(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.DEBUG, logger="wyby.alt_screen"):
            disable_alt_screen(stream=FakeStream())
        messages = [r.message for r in caplog.records]
        assert any("not active" in m for m in messages)


# ---------------------------------------------------------------------------
# is_active()
# ---------------------------------------------------------------------------


class TestIsActive:
    """Tests for the is_active() query function."""

    def test_false_by_default(self) -> None:
        assert is_active() is False

    def test_true_after_enable(self) -> None:
        enable_alt_screen(stream=FakeStream())
        assert is_active() is True

    def test_false_after_enable_then_disable(self) -> None:
        stream = FakeStream()
        enable_alt_screen(stream=stream)
        disable_alt_screen(stream=stream)
        assert is_active() is False


# ---------------------------------------------------------------------------
# AltScreen context manager
# ---------------------------------------------------------------------------


class TestAltScreenContextManager:
    """Tests for the AltScreen context manager."""

    def test_enables_on_enter(self) -> None:
        stream = FakeStream()
        with AltScreen(stream=stream) as ctx:
            assert is_active() is True
            assert ctx.entered is True
        assert stream.written[0] == _ENABLE_SEQ

    def test_disables_on_exit(self) -> None:
        stream = FakeStream()
        with AltScreen(stream=stream):
            pass
        assert is_active() is False
        assert _DISABLE_SEQ in stream.written

    def test_disables_on_exception(self) -> None:
        stream = FakeStream()
        with pytest.raises(RuntimeError):
            with AltScreen(stream=stream):
                raise RuntimeError("boom")
        assert is_active() is False
        assert _DISABLE_SEQ in stream.written

    def test_entered_false_when_not_tty(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(alt_screen_module, "_is_tty", lambda: False)
        with AltScreen() as ctx:
            assert ctx.entered is False
            assert is_active() is False

    def test_no_disable_when_not_entered(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """If enable was skipped (not a TTY), disable should be skipped too."""
        monkeypatch.setattr(alt_screen_module, "_is_tty", lambda: False)
        # Use default stdout (no custom stream) so the TTY check applies.
        with AltScreen() as ctx:
            assert ctx.entered is False
        assert is_active() is False

    def test_write_order(self) -> None:
        stream = FakeStream()
        with AltScreen(stream=stream):
            pass
        assert stream.written == [_ENABLE_SEQ, _DISABLE_SEQ]

    def test_repr_before_enter(self) -> None:
        ctx = AltScreen()
        assert repr(ctx) == "AltScreen(active=False)"

    def test_repr_inside_context(self) -> None:
        stream = FakeStream()
        with AltScreen(stream=stream) as ctx:
            assert repr(ctx) == "AltScreen(active=True)"

    def test_repr_after_exit(self) -> None:
        stream = FakeStream()
        ctx = AltScreen(stream=stream)
        with ctx:
            pass
        # After __exit__, entered is still True (records that we entered).
        # The repr reflects the entered state, not the current active flag.
        assert "AltScreen(" in repr(ctx)


# ---------------------------------------------------------------------------
# Enable/disable round-trip
# ---------------------------------------------------------------------------


class TestRoundTrip:
    """Verify enable -> disable -> enable works correctly."""

    def test_enable_disable_enable(self) -> None:
        stream = FakeStream()
        assert enable_alt_screen(stream=stream) is True
        assert disable_alt_screen(stream=stream) is True
        assert enable_alt_screen(stream=stream) is True
        assert stream.written == [_ENABLE_SEQ, _DISABLE_SEQ, _ENABLE_SEQ]

    def test_double_disable_is_noop(self) -> None:
        stream = FakeStream()
        enable_alt_screen(stream=stream)
        assert disable_alt_screen(stream=stream) is True
        assert disable_alt_screen(stream=stream) is False

    def test_double_enable_is_noop(self) -> None:
        stream = FakeStream()
        assert enable_alt_screen(stream=stream) is True
        assert enable_alt_screen(stream=stream) is False


# ---------------------------------------------------------------------------
# Public re-export from wyby package
# ---------------------------------------------------------------------------


class TestAltScreenImport:
    """Alt-screen API should be importable from the top-level wyby package."""

    def test_enable_importable(self) -> None:
        from wyby import enable_alt_screen as fn
        assert fn is enable_alt_screen

    def test_disable_importable(self) -> None:
        from wyby import disable_alt_screen as fn
        assert fn is disable_alt_screen

    def test_context_manager_importable(self) -> None:
        from wyby import AltScreen as cls
        assert cls is AltScreen
