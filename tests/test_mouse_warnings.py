"""Tests for wyby mouse hover/drag consistency warnings."""

from __future__ import annotations

import logging
from unittest.mock import patch

import pytest

from wyby.mouse_warnings import (
    _DRAG_GENERAL_WARNING,
    _HOVER_GENERAL_WARNING,
    _LIMITED_DRAG_TERMINALS,
    _LIMITED_HOVER_TERMINALS,
    check_mouse_drag_warning,
    check_mouse_hover_warning,
    log_mouse_warnings,
)


# ---------------------------------------------------------------------------
# check_mouse_hover_warning
# ---------------------------------------------------------------------------


class TestCheckMouseHoverWarning:
    """Tests for check_mouse_hover_warning()."""

    def test_none_terminal_returns_general_warning(self) -> None:
        """Unknown terminal (None) returns the general hover warning."""
        result = check_mouse_hover_warning(None)
        assert result == _HOVER_GENERAL_WARNING

    def test_apple_terminal_returns_specific_warning(self) -> None:
        """macOS Terminal.app returns its specific hover limitation."""
        result = check_mouse_hover_warning("Apple_Terminal")
        assert result is not None
        assert "Terminal.app" in result
        assert result == _LIMITED_HOVER_TERMINALS["Apple_Terminal"]

    def test_linux_console_returns_specific_warning(self) -> None:
        """Linux virtual console returns its specific warning."""
        result = check_mouse_hover_warning("linux")
        assert result is not None
        assert "virtual console" in result
        assert result == _LIMITED_HOVER_TERMINALS["linux"]

    def test_well_supported_terminal_returns_none(self) -> None:
        """Well-known terminals with good support return None."""
        for terminal in ("iTerm2.app", "kitty", "Alacritty", "WezTerm"):
            assert check_mouse_hover_warning(terminal) is None

    def test_general_warning_mentions_key_issues(self) -> None:
        """The general warning covers the main problem areas."""
        warning = check_mouse_hover_warning(None)
        assert warning is not None
        assert "mode 1003" in warning
        assert "Terminal.app" in warning
        assert "tmux" in warning


# ---------------------------------------------------------------------------
# check_mouse_drag_warning
# ---------------------------------------------------------------------------


class TestCheckMouseDragWarning:
    """Tests for check_mouse_drag_warning()."""

    def test_none_terminal_returns_general_warning(self) -> None:
        """Unknown terminal (None) returns the general drag warning."""
        result = check_mouse_drag_warning(None)
        assert result == _DRAG_GENERAL_WARNING

    def test_apple_terminal_returns_specific_warning(self) -> None:
        """macOS Terminal.app returns its specific drag limitation."""
        result = check_mouse_drag_warning("Apple_Terminal")
        assert result is not None
        assert "Terminal.app" in result
        assert result == _LIMITED_DRAG_TERMINALS["Apple_Terminal"]

    def test_linux_console_returns_specific_warning(self) -> None:
        """Linux virtual console returns its specific warning."""
        result = check_mouse_drag_warning("linux")
        assert result is not None
        assert "virtual console" in result

    def test_well_supported_terminal_returns_none(self) -> None:
        """Well-known terminals with good support return None."""
        for terminal in ("iTerm2.app", "kitty", "Alacritty", "WezTerm"):
            assert check_mouse_drag_warning(terminal) is None

    def test_general_warning_mentions_key_issues(self) -> None:
        """The general drag warning covers main problem areas."""
        warning = check_mouse_drag_warning(None)
        assert warning is not None
        assert "button='none'" in warning
        assert "timeout" in warning
        assert "outside" in warning


# ---------------------------------------------------------------------------
# log_mouse_warnings
# ---------------------------------------------------------------------------


class TestLogMouseWarnings:
    """Tests for log_mouse_warnings()."""

    def test_returns_true_when_drag_warning_logged(self) -> None:
        """Returns True when drag warning is issued (unknown terminal)."""
        result = log_mouse_warnings(None, motion_enabled=False)
        assert result is True

    def test_returns_true_when_both_warnings_logged(self) -> None:
        """Returns True when both hover and drag warnings are issued."""
        result = log_mouse_warnings(None, motion_enabled=True)
        assert result is True

    def test_returns_false_for_well_supported_terminal_no_motion(self) -> None:
        """Returns False for well-supported terminal without motion."""
        result = log_mouse_warnings("kitty", motion_enabled=False)
        assert result is False

    def test_returns_false_for_well_supported_terminal_with_motion(self) -> None:
        """Returns False for well-supported terminal even with motion."""
        result = log_mouse_warnings("kitty", motion_enabled=True)
        assert result is False

    def test_returns_true_for_apple_terminal(self) -> None:
        """Returns True for Apple Terminal (known-limited)."""
        result = log_mouse_warnings("Apple_Terminal", motion_enabled=False)
        assert result is True

    def test_hover_warning_skipped_without_motion(self) -> None:
        """Hover warning is not checked when motion is disabled."""
        # For a well-supported terminal, drag returns None, and hover
        # is skipped — result should be False.
        result = log_mouse_warnings("kitty", motion_enabled=False)
        assert result is False

    def test_hover_warning_included_with_motion(self) -> None:
        """Hover warning is checked when motion is enabled."""
        # For unknown terminal, both drag and hover warnings fire.
        result = log_mouse_warnings(None, motion_enabled=True)
        assert result is True

    def test_logs_warning_level_for_known_bad_terminal(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """WARNING-level log is emitted for known-limited terminals."""
        with caplog.at_level(logging.WARNING, logger="wyby.mouse_warnings"):
            log_mouse_warnings("Apple_Terminal", motion_enabled=True)
        warning_messages = [
            r.message for r in caplog.records if r.levelno == logging.WARNING
        ]
        assert len(warning_messages) >= 1
        assert any("drag" in msg.lower() for msg in warning_messages)

    def test_logs_debug_level_for_well_supported_terminal(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """DEBUG-level log is emitted for well-supported terminals."""
        with caplog.at_level(logging.DEBUG, logger="wyby.mouse_warnings"):
            log_mouse_warnings("kitty", motion_enabled=True)
        debug_messages = [
            r.message for r in caplog.records if r.levelno == logging.DEBUG
        ]
        assert len(debug_messages) >= 1


# ---------------------------------------------------------------------------
# Integration: InputManager logs warnings on start
# ---------------------------------------------------------------------------


class _MockBackend:
    """A fake InputBackend for unit testing."""

    def __init__(self) -> None:
        self._raw = False

    def enter_raw_mode(self) -> None:
        self._raw = True

    def exit_raw_mode(self) -> None:
        self._raw = False

    def has_input(self) -> bool:
        return False

    def read_bytes(self) -> bytes:
        return b""

    @property
    def is_raw(self) -> bool:
        return self._raw


class TestInputManagerMouseWarnings:
    """InputManager.start() logs mouse warnings when mouse is enabled."""

    def test_mouse_mode_logs_drag_warning(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Mouse mode triggers drag warning (terminal unknown in tests)."""
        from wyby.input import InputManager

        backend = _MockBackend()
        with patch("wyby.input.sys.stdout"):
            with caplog.at_level(logging.WARNING, logger="wyby.mouse_warnings"):
                mgr = InputManager(backend=backend, mouse=True)
                mgr.start()
                mgr.stop()
        warning_messages = [
            r.message for r in caplog.records if r.levelno == logging.WARNING
        ]
        assert any("drag" in msg.lower() for msg in warning_messages)

    def test_mouse_motion_logs_hover_warning(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Mouse motion mode triggers hover warning."""
        from wyby.input import InputManager

        backend = _MockBackend()
        with patch("wyby.input.sys.stdout"):
            with caplog.at_level(logging.WARNING, logger="wyby.mouse_warnings"):
                mgr = InputManager(
                    backend=backend, mouse=True, mouse_motion=True
                )
                mgr.start()
                mgr.stop()
        warning_messages = [
            r.message for r in caplog.records if r.levelno == logging.WARNING
        ]
        assert any("hover" in msg.lower() for msg in warning_messages)

    def test_no_mouse_no_warnings(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """No mouse mode means no mouse warnings."""
        from wyby.input import InputManager

        backend = _MockBackend()
        with patch("wyby.input.sys.stdout"):
            with caplog.at_level(logging.WARNING, logger="wyby.mouse_warnings"):
                mgr = InputManager(backend=backend, mouse=False)
                mgr.start()
                mgr.stop()
        warning_messages = [
            r.message
            for r in caplog.records
            if r.levelno == logging.WARNING
            and r.name == "wyby.mouse_warnings"
        ]
        assert len(warning_messages) == 0


# ---------------------------------------------------------------------------
# Import from top-level package
# ---------------------------------------------------------------------------


class TestMouseWarningImports:
    """Mouse warning functions should be importable from wyby."""

    def test_check_mouse_hover_warning_importable(self) -> None:
        from wyby import check_mouse_hover_warning as fn

        assert fn is check_mouse_hover_warning

    def test_check_mouse_drag_warning_importable(self) -> None:
        from wyby import check_mouse_drag_warning as fn

        assert fn is check_mouse_drag_warning

    def test_log_mouse_warnings_importable(self) -> None:
        from wyby import log_mouse_warnings as fn

        assert fn is log_mouse_warnings

    def test_in_all(self) -> None:
        import wyby

        assert "check_mouse_hover_warning" in wyby.__all__
        assert "check_mouse_drag_warning" in wyby.__all__
        assert "log_mouse_warnings" in wyby.__all__
