"""Integration tests for EventQueue with KeyEvent and MouseEvent.

These tests verify that the concrete event types (KeyEvent, MouseEvent)
flow correctly through the EventQueue — posting, draining, peeking,
and mixed-type ordering.  The individual classes are tested in
test_event.py, test_input.py, and test_mouse.py; this module focuses
on the integration between them.
"""

from __future__ import annotations

import logging

import pytest

from wyby.event import Event, EventQueue
from wyby.input import KeyEvent, MouseEvent


# ---------------------------------------------------------------------------
# Posting KeyEvent to EventQueue
# ---------------------------------------------------------------------------


class TestEventQueueKeyEvent:
    """KeyEvent objects should post and drain correctly."""

    def test_post_key_event(self) -> None:
        eq = EventQueue()
        ke = KeyEvent(key="a")
        assert eq.post(ke) is True
        assert len(eq) == 1

    def test_drain_key_event(self) -> None:
        eq = EventQueue()
        ke = KeyEvent(key="up")
        eq.post(ke)
        events = eq.drain()
        assert len(events) == 1
        assert events[0] is ke
        assert isinstance(events[0], KeyEvent)
        assert isinstance(events[0], Event)

    def test_key_event_with_ctrl(self) -> None:
        eq = EventQueue()
        ke = KeyEvent(key="c", ctrl=True)
        eq.post(ke)
        events = eq.drain()
        assert events[0] == KeyEvent(key="c", ctrl=True)

    def test_multiple_key_events_fifo(self) -> None:
        eq = EventQueue()
        keys = [KeyEvent(key=k) for k in ("up", "down", "left", "right")]
        for ke in keys:
            eq.post(ke)
        drained = eq.drain()
        assert drained == keys

    def test_peek_returns_key_event(self) -> None:
        eq = EventQueue()
        ke = KeyEvent(key="enter")
        eq.post(ke)
        assert eq.peek() is ke


# ---------------------------------------------------------------------------
# Posting MouseEvent to EventQueue
# ---------------------------------------------------------------------------


class TestEventQueueMouseEvent:
    """MouseEvent objects should post and drain correctly."""

    def test_post_mouse_event(self) -> None:
        eq = EventQueue()
        me = MouseEvent(x=10, y=5, button="left", action="press")
        assert eq.post(me) is True
        assert len(eq) == 1

    def test_drain_mouse_event(self) -> None:
        eq = EventQueue()
        me = MouseEvent(x=0, y=0, button="right", action="release")
        eq.post(me)
        events = eq.drain()
        assert len(events) == 1
        assert events[0] is me
        assert isinstance(events[0], MouseEvent)
        assert isinstance(events[0], Event)

    def test_scroll_events(self) -> None:
        eq = EventQueue()
        up = MouseEvent(x=5, y=5, button="scroll_up", action="scroll")
        down = MouseEvent(x=5, y=5, button="scroll_down", action="scroll")
        eq.post(up)
        eq.post(down)
        events = eq.drain()
        assert events == [up, down]

    def test_move_event(self) -> None:
        """Motion events (drag/hover) post and drain normally.

        Caveat: motion tracking (mode 1003) generates high event
        volume.  Games that enable it should monitor EventQueue
        drop_count to detect if max_size is too small.
        """
        eq = EventQueue()
        me = MouseEvent(x=15, y=20, button="left", action="move")
        eq.post(me)
        assert eq.drain() == [me]

    def test_peek_returns_mouse_event(self) -> None:
        eq = EventQueue()
        me = MouseEvent(x=3, y=7, button="middle", action="press")
        eq.post(me)
        assert eq.peek() is me


# ---------------------------------------------------------------------------
# Mixed KeyEvent + MouseEvent ordering
# ---------------------------------------------------------------------------


class TestEventQueueMixedTypes:
    """Mixed event types maintain FIFO order through the queue."""

    def test_key_then_mouse(self) -> None:
        eq = EventQueue()
        ke = KeyEvent(key="w")
        me = MouseEvent(x=1, y=2, button="left", action="press")
        eq.post(ke)
        eq.post(me)
        events = eq.drain()
        assert len(events) == 2
        assert events[0] is ke
        assert events[1] is me

    def test_mouse_then_key(self) -> None:
        eq = EventQueue()
        me = MouseEvent(x=1, y=2, button="left", action="press")
        ke = KeyEvent(key="escape")
        eq.post(me)
        eq.post(ke)
        events = eq.drain()
        assert events[0] is me
        assert events[1] is ke

    def test_interleaved_events(self) -> None:
        """Simulates a realistic input buffer: key, mouse, key, mouse."""
        eq = EventQueue()
        events_in = [
            KeyEvent(key="a"),
            MouseEvent(x=5, y=10, button="left", action="press"),
            KeyEvent(key="b"),
            MouseEvent(x=5, y=10, button="left", action="release"),
        ]
        for e in events_in:
            eq.post(e)
        events_out = eq.drain()
        assert events_out == events_in

    def test_filter_key_events_after_drain(self) -> None:
        """Callers can filter drained events by type with isinstance.

        This is the intended pattern — the EventQueue is type-agnostic
        and does not provide built-in type filtering.  Callers use
        isinstance checks after draining.
        """
        eq = EventQueue()
        eq.post(KeyEvent(key="up"))
        eq.post(MouseEvent(x=0, y=0, button="left", action="press"))
        eq.post(KeyEvent(key="down"))
        events = eq.drain()
        key_events = [e for e in events if isinstance(e, KeyEvent)]
        mouse_events = [e for e in events if isinstance(e, MouseEvent)]
        assert len(key_events) == 2
        assert len(mouse_events) == 1

    def test_mixed_with_plain_event(self) -> None:
        """Custom Event subclasses coexist with KeyEvent/MouseEvent."""

        class QuitRequestEvent(Event):
            __slots__ = ()

        eq = EventQueue()
        eq.post(KeyEvent(key="q"))
        eq.post(QuitRequestEvent())
        eq.post(MouseEvent(x=0, y=0, button="left", action="press"))
        events = eq.drain()
        assert len(events) == 3
        assert isinstance(events[0], KeyEvent)
        assert isinstance(events[1], QuitRequestEvent)
        assert isinstance(events[2], MouseEvent)


# ---------------------------------------------------------------------------
# Capacity behaviour with concrete event types
# ---------------------------------------------------------------------------


class TestEventQueueCapacityWithEvents:
    """Bounded queue behaviour when posting KeyEvent/MouseEvent."""

    def test_key_events_dropped_when_full(self) -> None:
        eq = EventQueue(max_size=2)
        eq.post(KeyEvent(key="a"))
        eq.post(KeyEvent(key="b"))
        result = eq.post(KeyEvent(key="c"))
        assert result is False
        assert eq.drop_count == 1
        events = eq.drain()
        assert events == [KeyEvent(key="a"), KeyEvent(key="b")]

    def test_mouse_events_dropped_when_full(self) -> None:
        eq = EventQueue(max_size=1)
        eq.post(MouseEvent(x=0, y=0, button="left", action="press"))
        result = eq.post(MouseEvent(x=1, y=1, button="left", action="press"))
        assert result is False
        assert eq.drop_count == 1

    def test_drop_warning_includes_event_repr(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Drop warning log includes the repr of the dropped event."""
        eq = EventQueue(max_size=1)
        eq.post(KeyEvent(key="a"))
        with caplog.at_level(logging.WARNING, logger="wyby.event"):
            eq.post(KeyEvent(key="b"))
        assert any("KeyEvent" in r.message for r in caplog.records)

    def test_mixed_drops_preserve_fifo(self) -> None:
        """When mixed types overflow, only newest events are dropped."""
        eq = EventQueue(max_size=3)
        eq.post(KeyEvent(key="a"))
        eq.post(MouseEvent(x=0, y=0, button="left", action="press"))
        eq.post(KeyEvent(key="b"))
        # Queue is now full — next post is dropped.
        eq.post(MouseEvent(x=1, y=1, button="right", action="press"))
        events = eq.drain()
        assert len(events) == 3
        assert isinstance(events[0], KeyEvent)
        assert isinstance(events[1], MouseEvent)
        assert isinstance(events[2], KeyEvent)

    def test_high_volume_mouse_motion(self) -> None:
        """Simulates high-volume motion events flooding the queue.

        Caveat: motion tracking (mode 1003) can generate an event for
        every pixel of mouse movement.  With a small max_size, many
        events will be dropped.  Games should monitor drop_count and
        consider increasing max_size or debouncing motion events.
        """
        eq = EventQueue(max_size=10)
        posted = 0
        for i in range(50):
            if eq.post(MouseEvent(x=i, y=0, button="none", action="move")):
                posted += 1
        assert posted == 10
        assert eq.drop_count == 40
        events = eq.drain()
        # Only the first 10 events survived — the queue is FIFO with
        # drop-newest-on-overflow, so these are the earliest events.
        assert all(isinstance(e, MouseEvent) for e in events)
        assert events[0].x == 0
        assert events[9].x == 9


# ---------------------------------------------------------------------------
# Clear and successive drains with concrete types
# ---------------------------------------------------------------------------


class TestEventQueueClearWithEvents:
    """Clear and drain cycles with concrete event types."""

    def test_clear_discards_key_and_mouse_events(self) -> None:
        eq = EventQueue()
        eq.post(KeyEvent(key="a"))
        eq.post(MouseEvent(x=0, y=0, button="left", action="press"))
        eq.clear()
        assert eq.is_empty
        assert eq.drain() == []

    def test_post_after_clear(self) -> None:
        eq = EventQueue()
        eq.post(KeyEvent(key="a"))
        eq.clear()
        me = MouseEvent(x=5, y=5, button="right", action="press")
        eq.post(me)
        events = eq.drain()
        assert events == [me]

    def test_successive_drains_with_mixed_types(self) -> None:
        eq = EventQueue()

        # First tick: key events.
        eq.post(KeyEvent(key="up"))
        eq.post(KeyEvent(key="space"))
        first = eq.drain()
        assert len(first) == 2

        # Second tick: mouse events.
        eq.post(MouseEvent(x=10, y=10, button="left", action="press"))
        second = eq.drain()
        assert len(second) == 1
        assert isinstance(second[0], MouseEvent)

        # Third tick: empty.
        third = eq.drain()
        assert third == []
