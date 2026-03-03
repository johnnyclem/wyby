"""Tests for wyby.resize — terminal resize detection."""

from __future__ import annotations

import logging
import signal
import sys
from unittest.mock import MagicMock, patch

import pytest

from wyby.resize import (
    ResizeHandler,
    _HAS_SIGWINCH,
    get_terminal_size,
)


# ---------------------------------------------------------------------------
# get_terminal_size()
# ---------------------------------------------------------------------------


class TestGetTerminalSize:
    """get_terminal_size() should return a (columns, rows) tuple."""

    def test_returns_tuple_of_two_ints(self) -> None:
        result = get_terminal_size()
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], int)
        assert isinstance(result[1], int)

    def test_values_are_positive(self) -> None:
        cols, rows = get_terminal_size()
        assert cols > 0
        assert rows > 0

    def test_delegates_to_shutil(self) -> None:
        with patch("wyby.resize.shutil.get_terminal_size") as mock:
            mock.return_value = MagicMock(columns=120, lines=40)
            result = get_terminal_size()
        assert result == (120, 40)


# ---------------------------------------------------------------------------
# ResizeHandler construction
# ---------------------------------------------------------------------------


class TestResizeHandlerInit:
    """ResizeHandler() should initialize with current terminal size."""

    def test_columns_positive(self) -> None:
        handler = ResizeHandler()
        assert handler.columns > 0

    def test_rows_positive(self) -> None:
        handler = ResizeHandler()
        assert handler.rows > 0

    def test_size_returns_tuple(self) -> None:
        handler = ResizeHandler()
        assert handler.size == (handler.columns, handler.rows)

    def test_not_pending_after_init(self) -> None:
        handler = ResizeHandler()
        assert handler.resize_pending is False

    def test_not_installed_after_init(self) -> None:
        handler = ResizeHandler()
        assert handler.installed is False

    def test_logs_creation(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.DEBUG, logger="wyby.resize"):
            ResizeHandler()
        messages = [r.message for r in caplog.records]
        assert any("ResizeHandler created" in m for m in messages)


# ---------------------------------------------------------------------------
# Properties are read-only
# ---------------------------------------------------------------------------


class TestResizeHandlerReadOnly:
    """Properties should not be directly settable."""

    def test_columns_is_read_only(self) -> None:
        handler = ResizeHandler()
        with pytest.raises(AttributeError):
            handler.columns = 100  # type: ignore[misc]

    def test_rows_is_read_only(self) -> None:
        handler = ResizeHandler()
        with pytest.raises(AttributeError):
            handler.rows = 50  # type: ignore[misc]

    def test_size_is_read_only(self) -> None:
        handler = ResizeHandler()
        with pytest.raises(AttributeError):
            handler.size = (100, 50)  # type: ignore[misc]

    def test_resize_pending_is_read_only(self) -> None:
        handler = ResizeHandler()
        with pytest.raises(AttributeError):
            handler.resize_pending = True  # type: ignore[misc]

    def test_installed_is_read_only(self) -> None:
        handler = ResizeHandler()
        with pytest.raises(AttributeError):
            handler.installed = True  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Callback management
# ---------------------------------------------------------------------------


class TestResizeHandlerCallbacks:
    """Callback add/remove should validate and manage the callback list."""

    def test_add_callback_accepts_callable(self) -> None:
        handler = ResizeHandler()
        cb = MagicMock()
        handler.add_callback(cb)
        # No error raised.

    def test_add_callback_rejects_non_callable(self) -> None:
        handler = ResizeHandler()
        with pytest.raises(TypeError, match="callback must be callable"):
            handler.add_callback(42)  # type: ignore[arg-type]

    def test_remove_callback_works(self) -> None:
        handler = ResizeHandler()
        cb = MagicMock()
        handler.add_callback(cb)
        handler.remove_callback(cb)
        # No error raised.

    def test_remove_unregistered_callback_raises(self) -> None:
        handler = ResizeHandler()
        cb = MagicMock()
        with pytest.raises(ValueError, match="is not registered"):
            handler.remove_callback(cb)

    def test_add_callback_logs(self, caplog: pytest.LogCaptureFixture) -> None:
        handler = ResizeHandler()
        with caplog.at_level(logging.DEBUG, logger="wyby.resize"):
            handler.add_callback(lambda c, r: None)
        messages = [r.message for r in caplog.records]
        assert any("callback added" in m for m in messages)

    def test_remove_callback_logs(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        handler = ResizeHandler()
        cb = MagicMock()
        handler.add_callback(cb)
        with caplog.at_level(logging.DEBUG, logger="wyby.resize"):
            handler.remove_callback(cb)
        messages = [r.message for r in caplog.records]
        assert any("callback removed" in m for m in messages)


# ---------------------------------------------------------------------------
# poll() — size-change detection
# ---------------------------------------------------------------------------


class TestResizeHandlerPoll:
    """poll() should detect terminal size changes."""

    def test_no_change_no_pending(self) -> None:
        handler = ResizeHandler()
        handler.poll()
        assert handler.resize_pending is False

    def test_detects_size_change(self) -> None:
        handler = ResizeHandler()
        original_cols, original_rows = handler.columns, handler.rows
        new_cols, new_rows = original_cols + 10, original_rows + 5

        with patch(
            "wyby.resize.get_terminal_size", return_value=(new_cols, new_rows)
        ):
            handler.poll()

        assert handler.resize_pending is True
        assert handler.columns == new_cols
        assert handler.rows == new_rows

    def test_no_pending_when_size_unchanged(self) -> None:
        handler = ResizeHandler()
        cols, rows = handler.columns, handler.rows

        with patch(
            "wyby.resize.get_terminal_size", return_value=(cols, rows)
        ):
            handler.poll()

        assert handler.resize_pending is False

    def test_logs_on_size_change(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        handler = ResizeHandler()
        new_size = (handler.columns + 10, handler.rows + 5)

        with caplog.at_level(logging.DEBUG, logger="wyby.resize"):
            with patch(
                "wyby.resize.get_terminal_size", return_value=new_size
            ):
                handler.poll()

        messages = [r.message for r in caplog.records]
        assert any("resize detected via poll" in m for m in messages)


# ---------------------------------------------------------------------------
# consume() — flag clearing and callback dispatch
# ---------------------------------------------------------------------------


class TestResizeHandlerConsume:
    """consume() should clear the pending flag and fire callbacks."""

    def test_returns_false_when_no_resize(self) -> None:
        handler = ResizeHandler()
        assert handler.consume() is False

    def test_returns_true_after_resize(self) -> None:
        handler = ResizeHandler()
        with patch(
            "wyby.resize.get_terminal_size",
            return_value=(handler.columns + 10, handler.rows),
        ):
            handler.poll()
        assert handler.consume() is True

    def test_clears_pending_flag(self) -> None:
        handler = ResizeHandler()
        with patch(
            "wyby.resize.get_terminal_size",
            return_value=(handler.columns + 10, handler.rows),
        ):
            handler.poll()
        handler.consume()
        assert handler.resize_pending is False

    def test_fires_callbacks_with_new_size(self) -> None:
        handler = ResizeHandler()
        cb = MagicMock()
        handler.add_callback(cb)

        new_cols = handler.columns + 10
        new_rows = handler.rows + 5
        with patch(
            "wyby.resize.get_terminal_size",
            return_value=(new_cols, new_rows),
        ):
            handler.poll()
        handler.consume()

        cb.assert_called_once_with(new_cols, new_rows)

    def test_fires_multiple_callbacks_in_order(self) -> None:
        handler = ResizeHandler()
        call_order: list[int] = []
        handler.add_callback(lambda c, r: call_order.append(1))
        handler.add_callback(lambda c, r: call_order.append(2))
        handler.add_callback(lambda c, r: call_order.append(3))

        with patch(
            "wyby.resize.get_terminal_size",
            return_value=(handler.columns + 10, handler.rows),
        ):
            handler.poll()
        handler.consume()

        assert call_order == [1, 2, 3]

    def test_second_consume_returns_false(self) -> None:
        handler = ResizeHandler()
        with patch(
            "wyby.resize.get_terminal_size",
            return_value=(handler.columns + 10, handler.rows),
        ):
            handler.poll()
        handler.consume()
        assert handler.consume() is False

    def test_logs_consume(self, caplog: pytest.LogCaptureFixture) -> None:
        handler = ResizeHandler()
        with patch(
            "wyby.resize.get_terminal_size",
            return_value=(handler.columns + 10, handler.rows),
        ):
            handler.poll()
        with caplog.at_level(logging.DEBUG, logger="wyby.resize"):
            handler.consume()
        messages = [r.message for r in caplog.records]
        assert any("Consuming resize event" in m for m in messages)


# ---------------------------------------------------------------------------
# install() / uninstall() — SIGWINCH handler management
# ---------------------------------------------------------------------------


class TestResizeHandlerInstall:
    """install()/uninstall() should manage SIGWINCH on Unix."""

    @pytest.mark.skipif(
        not _HAS_SIGWINCH, reason="SIGWINCH not available on this platform"
    )
    def test_install_sets_installed_flag(self) -> None:
        handler = ResizeHandler()
        handler.install()
        try:
            assert handler.installed is True
        finally:
            handler.uninstall()

    @pytest.mark.skipif(
        not _HAS_SIGWINCH, reason="SIGWINCH not available on this platform"
    )
    def test_uninstall_clears_installed_flag(self) -> None:
        handler = ResizeHandler()
        handler.install()
        handler.uninstall()
        assert handler.installed is False

    @pytest.mark.skipif(
        not _HAS_SIGWINCH, reason="SIGWINCH not available on this platform"
    )
    def test_install_is_idempotent(self) -> None:
        handler = ResizeHandler()
        handler.install()
        try:
            handler.install()  # Second call is no-op.
            assert handler.installed is True
        finally:
            handler.uninstall()

    @pytest.mark.skipif(
        not _HAS_SIGWINCH, reason="SIGWINCH not available on this platform"
    )
    def test_uninstall_is_idempotent(self) -> None:
        handler = ResizeHandler()
        handler.uninstall()  # Not installed — should be no-op.
        assert handler.installed is False

    @pytest.mark.skipif(
        not _HAS_SIGWINCH, reason="SIGWINCH not available on this platform"
    )
    def test_restores_previous_handler(self) -> None:
        def sentinel(signum: int, frame: object) -> None:
            pass

        old = signal.signal(signal.SIGWINCH, sentinel)
        try:
            handler = ResizeHandler()
            handler.install()
            handler.uninstall()
            current = signal.getsignal(signal.SIGWINCH)
            assert current is sentinel
        finally:
            signal.signal(signal.SIGWINCH, old)

    @pytest.mark.skipif(
        not _HAS_SIGWINCH, reason="SIGWINCH not available on this platform"
    )
    def test_sigwinch_sets_pending(self) -> None:
        """Sending SIGWINCH should set the resize-pending flag."""
        import os

        handler = ResizeHandler()
        handler.install()
        try:
            # Simulate a terminal resize by sending SIGWINCH to self.
            os.kill(os.getpid(), signal.SIGWINCH)
            # The signal handler should have set the flag.
            assert handler.resize_pending is True
        finally:
            handler.uninstall()

    @pytest.mark.skipif(
        not _HAS_SIGWINCH, reason="SIGWINCH not available on this platform"
    )
    def test_install_logs(self, caplog: pytest.LogCaptureFixture) -> None:
        handler = ResizeHandler()
        with caplog.at_level(logging.DEBUG, logger="wyby.resize"):
            handler.install()
        try:
            messages = [r.message for r in caplog.records]
            assert any("handler installed" in m for m in messages)
        finally:
            handler.uninstall()

    @pytest.mark.skipif(
        not _HAS_SIGWINCH, reason="SIGWINCH not available on this platform"
    )
    def test_uninstall_logs(self, caplog: pytest.LogCaptureFixture) -> None:
        handler = ResizeHandler()
        handler.install()
        with caplog.at_level(logging.DEBUG, logger="wyby.resize"):
            handler.uninstall()
        messages = [r.message for r in caplog.records]
        assert any("uninstalled" in m for m in messages)


# ---------------------------------------------------------------------------
# install() fallback on non-main thread
# ---------------------------------------------------------------------------


class TestResizeHandlerThreadSafety:
    """install() from non-main thread should fall back to poll-only."""

    @pytest.mark.skipif(
        not _HAS_SIGWINCH, reason="SIGWINCH not available on this platform"
    )
    def test_install_from_thread_warns(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        import threading

        handler = ResizeHandler()
        error: Exception | None = None

        def thread_target() -> None:
            nonlocal error
            try:
                with caplog.at_level(logging.WARNING, logger="wyby.resize"):
                    handler.install()
            except Exception as exc:
                error = exc

        t = threading.Thread(target=thread_target)
        t.start()
        t.join(timeout=2.0)

        assert error is None  # Should not raise.
        assert handler.installed is False  # Fell back to poll-only.
        messages = [r.message for r in caplog.records]
        assert any("non-main thread" in m for m in messages)


# ---------------------------------------------------------------------------
# _HAS_SIGWINCH platform detection
# ---------------------------------------------------------------------------


class TestHasSigwinch:
    """_HAS_SIGWINCH should reflect platform capabilities."""

    def test_matches_signal_module(self) -> None:
        assert _HAS_SIGWINCH == hasattr(signal, "SIGWINCH")

    @pytest.mark.skipif(
        sys.platform == "win32", reason="Unix-only test"
    )
    def test_true_on_unix(self) -> None:
        assert _HAS_SIGWINCH is True


# ---------------------------------------------------------------------------
# Public re-export from wyby package
# ---------------------------------------------------------------------------


class TestResizeImport:
    """ResizeHandler should be importable from the top-level wyby package."""

    def test_resize_handler_from_wyby(self) -> None:
        from wyby import ResizeHandler as RH

        assert RH is ResizeHandler

    def test_get_terminal_size_from_wyby(self) -> None:
        from wyby import get_terminal_size as gts

        assert gts is get_terminal_size
