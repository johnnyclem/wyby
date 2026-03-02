"""Tests for the event system."""

import pytest

from runetui.events import Event, EventQueue, EventType, KeyEvent, MouseEvent


class TestEvents:
    def test_key_event(self):
        e = KeyEvent(key="a")
        assert e.event_type == EventType.KEY
        assert e.key == "a"

    def test_mouse_event(self):
        e = MouseEvent(x=10, y=5, button="left")
        assert e.event_type == EventType.MOUSE
        assert e.x == 10
        assert e.button == "left"

    def test_quit_event(self):
        e = Event(event_type=EventType.QUIT)
        assert e.event_type == EventType.QUIT


class TestEventQueue:
    def test_push_and_poll(self):
        q = EventQueue()
        e = KeyEvent(key="x")
        q.push(e)
        assert len(q) == 1
        result = q.poll()
        assert result is e
        assert len(q) == 0

    def test_poll_empty(self):
        q = EventQueue()
        assert q.poll() is None

    def test_peek(self):
        q = EventQueue()
        e = KeyEvent(key="y")
        q.push(e)
        assert q.peek() is e
        assert len(q) == 1  # not consumed

    def test_clear(self):
        q = EventQueue()
        q.push(KeyEvent(key="a"))
        q.push(KeyEvent(key="b"))
        q.clear()
        assert len(q) == 0

    def test_fifo_order(self):
        q = EventQueue()
        q.push(KeyEvent(key="1"))
        q.push(KeyEvent(key="2"))
        q.push(KeyEvent(key="3"))
        assert q.poll().key == "1"
        assert q.poll().key == "2"
        assert q.poll().key == "3"

    def test_max_size(self):
        q = EventQueue(max_size=3)
        q.push(KeyEvent(key="a"))
        q.push(KeyEvent(key="b"))
        q.push(KeyEvent(key="c"))
        q.push(KeyEvent(key="d"))  # pushes out "a"
        assert len(q) == 3
        assert q.poll().key == "b"

    def test_bool(self):
        q = EventQueue()
        assert not q
        q.push(KeyEvent(key="x"))
        assert q
