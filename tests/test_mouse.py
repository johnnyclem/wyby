"""Tests for wyby mouse event support."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from wyby.event import Event
from wyby.input import (
    InputManager,
    KeyEvent,
    MouseEvent,
    _parse_sgr_mouse,
    parse_input_events,
    parse_key_events,
)


# ---------------------------------------------------------------------------
# MouseEvent dataclass
# ---------------------------------------------------------------------------


class TestMouseEvent:
    """MouseEvent construction and properties."""

    def test_basic_construction(self) -> None:
        e = MouseEvent(x=10, y=5, button="left", action="press")
        assert e.x == 10
        assert e.y == 5
        assert e.button == "left"
        assert e.action == "press"

    def test_is_event_subclass(self) -> None:
        e = MouseEvent(x=0, y=0, button="left", action="press")
        assert isinstance(e, Event)

    def test_frozen(self) -> None:
        e = MouseEvent(x=0, y=0, button="left", action="press")
        with pytest.raises(AttributeError):
            e.x = 5  # type: ignore[misc]

    def test_repr(self) -> None:
        e = MouseEvent(x=3, y=7, button="right", action="release")
        assert repr(e) == "MouseEvent(x=3, y=7, button='right', action='release')"

    def test_equality(self) -> None:
        a = MouseEvent(x=1, y=2, button="left", action="press")
        b = MouseEvent(x=1, y=2, button="left", action="press")
        assert a == b

    def test_inequality_position(self) -> None:
        a = MouseEvent(x=1, y=2, button="left", action="press")
        b = MouseEvent(x=3, y=2, button="left", action="press")
        assert a != b

    def test_inequality_button(self) -> None:
        a = MouseEvent(x=1, y=2, button="left", action="press")
        b = MouseEvent(x=1, y=2, button="right", action="press")
        assert a != b

    def test_inequality_action(self) -> None:
        a = MouseEvent(x=1, y=2, button="left", action="press")
        b = MouseEvent(x=1, y=2, button="left", action="release")
        assert a != b


# ---------------------------------------------------------------------------
# SGR mouse sequence parsing — _parse_sgr_mouse
# ---------------------------------------------------------------------------


class TestParseSgrMouse:
    """Direct tests for the SGR mouse parameter parser."""

    def test_left_press(self) -> None:
        e = _parse_sgr_mouse("0;10;5", "M")
        assert e == MouseEvent(x=9, y=4, button="left", action="press")

    def test_left_release(self) -> None:
        e = _parse_sgr_mouse("0;10;5", "m")
        assert e == MouseEvent(x=9, y=4, button="left", action="release")

    def test_middle_press(self) -> None:
        e = _parse_sgr_mouse("1;15;20", "M")
        assert e == MouseEvent(x=14, y=19, button="middle", action="press")

    def test_right_press(self) -> None:
        e = _parse_sgr_mouse("2;1;1", "M")
        assert e == MouseEvent(x=0, y=0, button="right", action="press")

    def test_right_release(self) -> None:
        e = _parse_sgr_mouse("2;1;1", "m")
        assert e == MouseEvent(x=0, y=0, button="right", action="release")

    def test_scroll_up(self) -> None:
        e = _parse_sgr_mouse("64;5;10", "M")
        assert e == MouseEvent(x=4, y=9, button="scroll_up", action="scroll")

    def test_scroll_down(self) -> None:
        e = _parse_sgr_mouse("65;5;10", "M")
        assert e == MouseEvent(x=4, y=9, button="scroll_down", action="scroll")

    def test_motion_with_left_button(self) -> None:
        # Button 0 + motion bit (32) = 32
        e = _parse_sgr_mouse("32;20;30", "M")
        assert e == MouseEvent(x=19, y=29, button="left", action="move")

    def test_motion_no_button(self) -> None:
        # Button 3 + motion bit (32) = 35 — button 3 maps to "none"
        e = _parse_sgr_mouse("35;20;30", "M")
        assert e == MouseEvent(x=19, y=29, button="none", action="move")

    def test_malformed_too_few_parts(self) -> None:
        assert _parse_sgr_mouse("0;10", "M") is None

    def test_malformed_non_numeric(self) -> None:
        assert _parse_sgr_mouse("a;b;c", "M") is None

    def test_malformed_empty(self) -> None:
        assert _parse_sgr_mouse("", "M") is None

    def test_large_coordinates(self) -> None:
        """SGR mode supports coordinates > 223 (unlike X10 mode)."""
        e = _parse_sgr_mouse("0;300;200", "M")
        assert e == MouseEvent(x=299, y=199, button="left", action="press")


# ---------------------------------------------------------------------------
# parse_input_events — SGR mouse escape sequences
# ---------------------------------------------------------------------------


class TestParseInputEventsMouse:
    """Parsing SGR mouse escape sequences via parse_input_events."""

    def test_left_click(self) -> None:
        # ESC [ < 0 ; 10 ; 5 M
        data = b"\x1b[<0;10;5M"
        events = parse_input_events(data)
        assert events == [MouseEvent(x=9, y=4, button="left", action="press")]

    def test_left_release(self) -> None:
        data = b"\x1b[<0;10;5m"
        events = parse_input_events(data)
        assert events == [MouseEvent(x=9, y=4, button="left", action="release")]

    def test_right_click(self) -> None:
        data = b"\x1b[<2;1;1M"
        events = parse_input_events(data)
        assert events == [MouseEvent(x=0, y=0, button="right", action="press")]

    def test_scroll_up(self) -> None:
        data = b"\x1b[<64;5;10M"
        events = parse_input_events(data)
        assert events == [MouseEvent(x=4, y=9, button="scroll_up", action="scroll")]

    def test_scroll_down(self) -> None:
        data = b"\x1b[<65;5;10M"
        events = parse_input_events(data)
        assert events == [MouseEvent(x=4, y=9, button="scroll_down", action="scroll")]

    def test_mouse_then_key(self) -> None:
        """Mouse event followed by a key press in the same buffer."""
        data = b"\x1b[<0;5;3Ma"
        events = parse_input_events(data)
        assert len(events) == 2
        assert isinstance(events[0], MouseEvent)
        assert isinstance(events[1], KeyEvent)
        assert events[0] == MouseEvent(x=4, y=2, button="left", action="press")
        assert events[1] == KeyEvent(key="a")

    def test_key_then_mouse(self) -> None:
        """Key press followed by a mouse event."""
        data = b"x\x1b[<2;1;1M"
        events = parse_input_events(data)
        assert len(events) == 2
        assert events[0] == KeyEvent(key="x")
        assert events[1] == MouseEvent(x=0, y=0, button="right", action="press")

    def test_multiple_mouse_events(self) -> None:
        """Multiple mouse events in one buffer."""
        data = b"\x1b[<0;5;5M\x1b[<0;5;5m"
        events = parse_input_events(data)
        assert len(events) == 2
        assert events[0] == MouseEvent(x=4, y=4, button="left", action="press")
        assert events[1] == MouseEvent(x=4, y=4, button="left", action="release")

    def test_incomplete_mouse_sequence(self) -> None:
        """Incomplete SGR mouse sequence at end of buffer."""
        data = b"\x1b[<0;5;5"
        events = parse_input_events(data)
        assert events == []

    def test_keyboard_events_unchanged(self) -> None:
        """Regular key events still parse correctly."""
        data = b"\x1b[Aa\r"
        events = parse_input_events(data)
        assert events == [
            KeyEvent(key="up"),
            KeyEvent(key="a"),
            KeyEvent(key="enter"),
        ]

    def test_arrow_key_interleaved_with_mouse(self) -> None:
        data = b"\x1b[A\x1b[<0;1;1M\x1b[B"
        events = parse_input_events(data)
        assert len(events) == 3
        assert events[0] == KeyEvent(key="up")
        assert events[1] == MouseEvent(x=0, y=0, button="left", action="press")
        assert events[2] == KeyEvent(key="down")


# ---------------------------------------------------------------------------
# parse_key_events backward compat — filters out mouse events
# ---------------------------------------------------------------------------


class TestParseKeyEventsBackwardCompat:
    """parse_key_events filters out MouseEvent, keeping only KeyEvent."""

    def test_pure_keyboard_unchanged(self) -> None:
        events = parse_key_events(b"abc")
        assert events == [
            KeyEvent(key="a"),
            KeyEvent(key="b"),
            KeyEvent(key="c"),
        ]

    def test_mouse_events_filtered(self) -> None:
        data = b"\x1b[<0;1;1Ma"
        events = parse_key_events(data)
        assert events == [KeyEvent(key="a")]

    def test_only_mouse_returns_empty(self) -> None:
        data = b"\x1b[<0;1;1M"
        events = parse_key_events(data)
        assert events == []


# ---------------------------------------------------------------------------
# InputManager with mouse support
# ---------------------------------------------------------------------------


class _MockBackend:
    """A fake InputBackend for unit testing without a real terminal."""

    def __init__(self) -> None:
        self._raw = False
        self._data: bytes = b""

    def enter_raw_mode(self) -> None:
        self._raw = True

    def exit_raw_mode(self) -> None:
        self._raw = False

    def has_input(self) -> bool:
        return len(self._data) > 0

    def read_bytes(self) -> bytes:
        data = self._data
        self._data = b""
        return data

    @property
    def is_raw(self) -> bool:
        return self._raw

    def feed(self, data: bytes) -> None:
        """Stage bytes for the next read_bytes() call."""
        self._data += data


class TestInputManagerMouse:
    """InputManager with mouse mode enabled."""

    def test_mouse_events_in_poll(self) -> None:
        """poll() returns MouseEvent objects when mouse data arrives."""
        backend = _MockBackend()
        with patch("wyby.input.sys.stdout"):
            mgr = InputManager(backend=backend, mouse=True)
            mgr.start()
            backend.feed(b"\x1b[<0;5;3M")
            events = mgr.poll()
            assert len(events) == 1
            assert isinstance(events[0], MouseEvent)
            assert events[0] == MouseEvent(
                x=4, y=2, button="left", action="press"
            )
            mgr.stop()

    def test_mouse_and_key_events_mixed(self) -> None:
        """poll() returns both MouseEvent and KeyEvent."""
        backend = _MockBackend()
        with patch("wyby.input.sys.stdout"):
            mgr = InputManager(backend=backend, mouse=True)
            mgr.start()
            backend.feed(b"a\x1b[<0;1;1M")
            events = mgr.poll()
            assert len(events) == 2
            assert isinstance(events[0], KeyEvent)
            assert isinstance(events[1], MouseEvent)
            mgr.stop()

    def test_mouse_enable_writes_escape_sequences(self) -> None:
        """start() writes mouse enable sequences to stdout."""
        backend = _MockBackend()
        with patch("wyby.input.sys.stdout") as mock_stdout:
            mgr = InputManager(backend=backend, mouse=True)
            mgr.start()
            # Check that enable sequences were written.
            written = "".join(
                call.args[0]
                for call in mock_stdout.write.call_args_list
            )
            assert "\x1b[?1000h" in written  # basic mouse
            assert "\x1b[?1006h" in written  # SGR mode
            mgr.stop()

    def test_mouse_disable_writes_escape_sequences(self) -> None:
        """stop() writes mouse disable sequences to stdout."""
        backend = _MockBackend()
        with patch("wyby.input.sys.stdout") as mock_stdout:
            mgr = InputManager(backend=backend, mouse=True)
            mgr.start()
            mock_stdout.write.reset_mock()
            mgr.stop()
            written = "".join(
                call.args[0]
                for call in mock_stdout.write.call_args_list
            )
            assert "\x1b[?1000l" in written  # basic mouse disable
            assert "\x1b[?1006l" in written  # SGR mode disable

    def test_mouse_motion_enables_mode_1003(self) -> None:
        """mouse_motion=True enables all-motion tracking."""
        backend = _MockBackend()
        with patch("wyby.input.sys.stdout") as mock_stdout:
            mgr = InputManager(
                backend=backend, mouse=True, mouse_motion=True
            )
            mgr.start()
            written = "".join(
                call.args[0]
                for call in mock_stdout.write.call_args_list
            )
            assert "\x1b[?1003h" in written
            mock_stdout.write.reset_mock()
            mgr.stop()
            written = "".join(
                call.args[0]
                for call in mock_stdout.write.call_args_list
            )
            assert "\x1b[?1003l" in written

    def test_mouse_disabled_by_default(self) -> None:
        """Mouse mode is off by default — no escape sequences written."""
        backend = _MockBackend()
        with patch("wyby.input.sys.stdout") as mock_stdout:
            mgr = InputManager(backend=backend)
            mgr.start()
            # No mouse enable sequences should be written.
            mock_stdout.write.assert_not_called()
            mgr.stop()

    def test_context_manager_with_mouse(self) -> None:
        """Context manager enables/disables mouse mode."""
        backend = _MockBackend()
        with patch("wyby.input.sys.stdout"):
            with InputManager(backend=backend, mouse=True) as mgr:
                assert mgr.is_started is True
                backend.feed(b"\x1b[<0;1;1M")
                events = mgr.poll()
                assert len(events) == 1
                assert isinstance(events[0], MouseEvent)
            assert mgr.is_started is False


# ---------------------------------------------------------------------------
# Fallback mode with mouse — graceful degradation
# ---------------------------------------------------------------------------


class _FailingBackend:
    """A backend that always fails to enter raw mode."""

    def __init__(self) -> None:
        self._raw = False

    def enter_raw_mode(self) -> None:
        raise RuntimeError("stdin is not a TTY")

    def exit_raw_mode(self) -> None:
        self._raw = False

    def has_input(self) -> bool:
        return False

    def read_bytes(self) -> bytes:
        return b""

    @property
    def is_raw(self) -> bool:
        return self._raw


class TestMouseFallbackMode:
    """Mouse mode in fallback (non-TTY) environments."""

    def test_mouse_ignored_in_fallback(self) -> None:
        """Mouse flag is silently ignored when in fallback mode."""
        backend = _FailingBackend()
        with patch("wyby.input.sys.stdout") as mock_stdout:
            mgr = InputManager(
                backend=backend, allow_fallback=True, mouse=True
            )
            mgr.start()
            assert mgr.is_started is True
            assert mgr.is_fallback is True
            # No mouse sequences should be written in fallback mode.
            mock_stdout.write.assert_not_called()
            mgr.stop()


# ---------------------------------------------------------------------------
# Import from top-level package
# ---------------------------------------------------------------------------


class TestMouseImports:
    """MouseEvent should be importable from wyby."""

    def test_mouse_event_importable(self) -> None:
        from wyby import MouseEvent as MEFromInit

        assert MEFromInit is MouseEvent

    def test_mouse_event_in_all(self) -> None:
        import wyby

        assert "MouseEvent" in wyby.__all__

    def test_parse_input_events_importable(self) -> None:
        from wyby import parse_input_events

        assert parse_input_events is not None

    def test_parse_input_events_in_all(self) -> None:
        import wyby

        assert "parse_input_events" in wyby.__all__
