"""Tests for wyby.input — keyboard input abstraction."""

from __future__ import annotations

import pytest

from wyby.event import Event
from wyby.input import InputManager, KeyEvent, parse_key_events


# ---------------------------------------------------------------------------
# KeyEvent dataclass
# ---------------------------------------------------------------------------


class TestKeyEvent:
    """KeyEvent construction and properties."""

    def test_simple_key(self) -> None:
        e = KeyEvent(key="a")
        assert e.key == "a"
        assert e.ctrl is False

    def test_ctrl_modifier(self) -> None:
        e = KeyEvent(key="c", ctrl=True)
        assert e.key == "c"
        assert e.ctrl is True

    def test_is_event_subclass(self) -> None:
        e = KeyEvent(key="x")
        assert isinstance(e, Event)

    def test_frozen(self) -> None:
        e = KeyEvent(key="a")
        with pytest.raises(AttributeError):
            e.key = "b"  # type: ignore[misc]

    def test_repr_no_ctrl(self) -> None:
        e = KeyEvent(key="a")
        assert repr(e) == "KeyEvent(key='a')"

    def test_repr_with_ctrl(self) -> None:
        e = KeyEvent(key="c", ctrl=True)
        assert repr(e) == "KeyEvent(key='c', ctrl=True)"

    def test_equality(self) -> None:
        """Frozen dataclass with slots gives value-based equality."""
        a = KeyEvent(key="up")
        b = KeyEvent(key="up")
        assert a == b

    def test_inequality(self) -> None:
        a = KeyEvent(key="up")
        b = KeyEvent(key="down")
        assert a != b

    def test_ctrl_affects_equality(self) -> None:
        a = KeyEvent(key="a", ctrl=False)
        b = KeyEvent(key="a", ctrl=True)
        assert a != b


# ---------------------------------------------------------------------------
# ANSI escape sequence parsing — arrow keys
# ---------------------------------------------------------------------------


class TestParseArrowKeys:
    """Arrow keys produce CSI sequences: ESC [ A/B/C/D."""

    def test_up_arrow(self) -> None:
        events = parse_key_events(b"\x1b[A")
        assert events == [KeyEvent(key="up")]

    def test_down_arrow(self) -> None:
        events = parse_key_events(b"\x1b[B")
        assert events == [KeyEvent(key="down")]

    def test_right_arrow(self) -> None:
        events = parse_key_events(b"\x1b[C")
        assert events == [KeyEvent(key="right")]

    def test_left_arrow(self) -> None:
        events = parse_key_events(b"\x1b[D")
        assert events == [KeyEvent(key="left")]

    def test_multiple_arrows(self) -> None:
        events = parse_key_events(b"\x1b[A\x1b[B")
        assert events == [KeyEvent(key="up"), KeyEvent(key="down")]


# ---------------------------------------------------------------------------
# ANSI escape sequence parsing — home, end, insert, delete, page keys
# ---------------------------------------------------------------------------


class TestParseExtendedKeys:
    """Extended CSI sequences using tilde notation."""

    def test_home_via_csi_h(self) -> None:
        events = parse_key_events(b"\x1b[H")
        assert events == [KeyEvent(key="home")]

    def test_end_via_csi_f(self) -> None:
        events = parse_key_events(b"\x1b[F")
        assert events == [KeyEvent(key="end")]

    def test_home_via_tilde(self) -> None:
        events = parse_key_events(b"\x1b[1~")
        assert events == [KeyEvent(key="home")]

    def test_insert(self) -> None:
        events = parse_key_events(b"\x1b[2~")
        assert events == [KeyEvent(key="insert")]

    def test_delete(self) -> None:
        events = parse_key_events(b"\x1b[3~")
        assert events == [KeyEvent(key="delete")]

    def test_end_via_tilde(self) -> None:
        events = parse_key_events(b"\x1b[4~")
        assert events == [KeyEvent(key="end")]

    def test_pageup(self) -> None:
        events = parse_key_events(b"\x1b[5~")
        assert events == [KeyEvent(key="pageup")]

    def test_pagedown(self) -> None:
        events = parse_key_events(b"\x1b[6~")
        assert events == [KeyEvent(key="pagedown")]


# ---------------------------------------------------------------------------
# Simple character parsing
# ---------------------------------------------------------------------------


class TestParseSimpleCharacters:
    """Single printable ASCII characters."""

    def test_lowercase_letter(self) -> None:
        events = parse_key_events(b"a")
        assert events == [KeyEvent(key="a")]

    def test_uppercase_letter(self) -> None:
        events = parse_key_events(b"A")
        assert events == [KeyEvent(key="A")]

    def test_digit(self) -> None:
        events = parse_key_events(b"5")
        assert events == [KeyEvent(key="5")]

    def test_punctuation(self) -> None:
        events = parse_key_events(b"/")
        assert events == [KeyEvent(key="/")]

    def test_space(self) -> None:
        events = parse_key_events(b" ")
        assert events == [KeyEvent(key="space")]

    def test_multiple_characters(self) -> None:
        events = parse_key_events(b"abc")
        assert events == [
            KeyEvent(key="a"),
            KeyEvent(key="b"),
            KeyEvent(key="c"),
        ]


# ---------------------------------------------------------------------------
# Special keys
# ---------------------------------------------------------------------------


class TestParseSpecialKeys:
    """Enter, Tab, Backspace, Escape."""

    def test_enter_cr(self) -> None:
        """Carriage return (0x0d) maps to enter."""
        events = parse_key_events(b"\r")
        assert events == [KeyEvent(key="enter")]

    def test_enter_lf(self) -> None:
        """Newline (0x0a) also maps to enter."""
        events = parse_key_events(b"\n")
        assert events == [KeyEvent(key="enter")]

    def test_tab(self) -> None:
        events = parse_key_events(b"\t")
        assert events == [KeyEvent(key="tab")]

    def test_backspace_0x7f(self) -> None:
        """Most terminals send 0x7f for backspace."""
        events = parse_key_events(b"\x7f")
        assert events == [KeyEvent(key="backspace")]

    def test_backspace_0x08(self) -> None:
        """Some terminals send 0x08 for backspace."""
        events = parse_key_events(b"\x08")
        assert events == [KeyEvent(key="backspace")]

    def test_escape_standalone(self) -> None:
        """Standalone ESC (not followed by [) is the Escape key."""
        events = parse_key_events(b"\x1b")
        assert events == [KeyEvent(key="escape")]

    def test_escape_at_end_of_buffer(self) -> None:
        """ESC at end of buffer with no following bytes."""
        events = parse_key_events(b"a\x1b")
        assert events == [KeyEvent(key="a"), KeyEvent(key="escape")]


# ---------------------------------------------------------------------------
# Ctrl+key detection
# ---------------------------------------------------------------------------


class TestParseCtrlKeys:
    """Ctrl+letter detection via byte values 0x01–0x1a."""

    def test_ctrl_a(self) -> None:
        events = parse_key_events(b"\x01")
        assert events == [KeyEvent(key="a", ctrl=True)]

    def test_ctrl_b(self) -> None:
        events = parse_key_events(b"\x02")
        assert events == [KeyEvent(key="b", ctrl=True)]

    def test_ctrl_d(self) -> None:
        events = parse_key_events(b"\x04")
        assert events == [KeyEvent(key="d", ctrl=True)]

    def test_ctrl_z(self) -> None:
        events = parse_key_events(b"\x1a")
        assert events == [KeyEvent(key="z", ctrl=True)]

    def test_ctrl_c_raises_keyboard_interrupt(self) -> None:
        """Ctrl+C (0x03) raises KeyboardInterrupt."""
        with pytest.raises(KeyboardInterrupt):
            parse_key_events(b"\x03")

    def test_tab_is_not_ctrl_i(self) -> None:
        """Tab (0x09) is reported as 'tab', not Ctrl+I."""
        events = parse_key_events(b"\x09")
        assert events == [KeyEvent(key="tab")]

    def test_enter_is_not_ctrl_m(self) -> None:
        """Enter (0x0d) is reported as 'enter', not Ctrl+M."""
        events = parse_key_events(b"\x0d")
        assert events == [KeyEvent(key="enter")]

    def test_enter_lf_is_not_ctrl_j(self) -> None:
        """Newline (0x0a) is reported as 'enter', not Ctrl+J."""
        events = parse_key_events(b"\x0a")
        assert events == [KeyEvent(key="enter")]


# ---------------------------------------------------------------------------
# Mixed input sequences
# ---------------------------------------------------------------------------


class TestParseMixedInput:
    """Parsing buffers with mixed key types."""

    def test_letters_then_arrow(self) -> None:
        events = parse_key_events(b"ab\x1b[A")
        assert events == [
            KeyEvent(key="a"),
            KeyEvent(key="b"),
            KeyEvent(key="up"),
        ]

    def test_arrow_then_letter(self) -> None:
        events = parse_key_events(b"\x1b[Bx")
        assert events == [KeyEvent(key="down"), KeyEvent(key="x")]

    def test_enter_then_escape(self) -> None:
        events = parse_key_events(b"\r\x1b")
        assert events == [KeyEvent(key="enter"), KeyEvent(key="escape")]

    def test_ctrl_then_letter(self) -> None:
        events = parse_key_events(b"\x01a")
        assert events == [
            KeyEvent(key="a", ctrl=True),
            KeyEvent(key="a"),
        ]


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestParseEdgeCases:
    """Edge cases and error handling in parsing."""

    def test_empty_input(self) -> None:
        events = parse_key_events(b"")
        assert events == []

    def test_unrecognised_csi_dropped(self) -> None:
        """Unknown CSI sequences are silently dropped."""
        events = parse_key_events(b"\x1b[Z")
        assert events == []

    def test_incomplete_csi_at_end(self) -> None:
        """ESC [ at end of buffer with no final byte."""
        events = parse_key_events(b"\x1b[")
        assert events == []

    def test_utf8_two_byte(self) -> None:
        """Two-byte UTF-8 character (e.g., ñ = 0xc3 0xb1)."""
        events = parse_key_events("ñ".encode("utf-8"))
        assert events == [KeyEvent(key="ñ")]

    def test_utf8_three_byte(self) -> None:
        """Three-byte UTF-8 character (e.g., € = 0xe2 0x82 0xac)."""
        events = parse_key_events("€".encode("utf-8"))
        assert events == [KeyEvent(key="€")]

    def test_ctrl_c_mid_buffer_raises(self) -> None:
        """Ctrl+C raises even if preceded by other bytes."""
        with pytest.raises(KeyboardInterrupt):
            parse_key_events(b"ab\x03cd")


# ---------------------------------------------------------------------------
# InputManager with mock backend
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


class TestInputManager:
    """InputManager lifecycle and poll behaviour."""

    def test_start_enters_raw_mode(self) -> None:
        backend = _MockBackend()
        mgr = InputManager(backend=backend)
        mgr.start()
        assert backend.is_raw is True
        mgr.stop()

    def test_stop_exits_raw_mode(self) -> None:
        backend = _MockBackend()
        mgr = InputManager(backend=backend)
        mgr.start()
        mgr.stop()
        assert backend.is_raw is False

    def test_double_start_is_noop(self) -> None:
        backend = _MockBackend()
        mgr = InputManager(backend=backend)
        mgr.start()
        mgr.start()  # should not raise
        assert mgr.is_started is True
        mgr.stop()

    def test_double_stop_is_noop(self) -> None:
        backend = _MockBackend()
        mgr = InputManager(backend=backend)
        mgr.start()
        mgr.stop()
        mgr.stop()  # should not raise
        assert mgr.is_started is False

    def test_poll_returns_key_events(self) -> None:
        backend = _MockBackend()
        mgr = InputManager(backend=backend)
        mgr.start()
        backend.feed(b"abc")
        events = mgr.poll()
        assert events == [
            KeyEvent(key="a"),
            KeyEvent(key="b"),
            KeyEvent(key="c"),
        ]
        mgr.stop()

    def test_poll_empty_returns_empty_list(self) -> None:
        backend = _MockBackend()
        mgr = InputManager(backend=backend)
        mgr.start()
        events = mgr.poll()
        assert events == []
        mgr.stop()

    def test_poll_before_start_raises(self) -> None:
        backend = _MockBackend()
        mgr = InputManager(backend=backend)
        with pytest.raises(RuntimeError, match="poll.*before start"):
            mgr.poll()

    def test_poll_arrow_keys(self) -> None:
        backend = _MockBackend()
        mgr = InputManager(backend=backend)
        mgr.start()
        backend.feed(b"\x1b[A\x1b[D")
        events = mgr.poll()
        assert events == [KeyEvent(key="up"), KeyEvent(key="left")]
        mgr.stop()

    def test_context_manager(self) -> None:
        backend = _MockBackend()
        with InputManager(backend=backend) as mgr:
            assert mgr.is_started is True
            backend.feed(b"x")
            events = mgr.poll()
            assert events == [KeyEvent(key="x")]
        assert mgr.is_started is False

    def test_context_manager_restores_on_exception(self) -> None:
        backend = _MockBackend()
        with pytest.raises(ValueError, match="test error"):
            with InputManager(backend=backend):
                raise ValueError("test error")
        assert backend.is_raw is False

    def test_repr(self) -> None:
        backend = _MockBackend()
        mgr = InputManager(backend=backend)
        assert repr(mgr) == "InputManager(started=False)"
        mgr.start()
        assert repr(mgr) == "InputManager(started=True)"
        mgr.stop()


# ---------------------------------------------------------------------------
# Import from top-level package
# ---------------------------------------------------------------------------


class TestInputImports:
    """KeyEvent and InputManager should be importable from wyby."""

    def test_key_event_importable(self) -> None:
        from wyby import KeyEvent as KEFromInit

        assert KEFromInit is KeyEvent

    def test_input_manager_importable(self) -> None:
        from wyby import InputManager as IMFromInit

        assert IMFromInit is InputManager

    def test_key_event_in_all(self) -> None:
        import wyby

        assert "KeyEvent" in wyby.__all__

    def test_input_manager_in_all(self) -> None:
        import wyby

        assert "InputManager" in wyby.__all__
