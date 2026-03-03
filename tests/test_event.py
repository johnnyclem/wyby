"""Tests for wyby.event — minimal event queue."""

from __future__ import annotations

import logging

import pytest

from wyby.event import Event, EventQueue


# ---------------------------------------------------------------------------
# Event base class
# ---------------------------------------------------------------------------


class TestEventBase:
    """Event should be a lightweight base class for all game events."""

    def test_can_instantiate(self) -> None:
        event = Event()
        assert isinstance(event, Event)

    def test_repr(self) -> None:
        assert repr(Event()) == "Event()"

    def test_subclass_repr_uses_subclass_name(self) -> None:
        class MyEvent(Event):
            __slots__ = ()

        assert repr(MyEvent()) == "MyEvent()"

    def test_identity_equality(self) -> None:
        """Events use identity equality by default."""
        a = Event()
        b = Event()
        assert a is not b
        assert a == a  # noqa: PLR0124

    def test_subclass_isinstance(self) -> None:
        class CustomEvent(Event):
            __slots__ = ()

        event = CustomEvent()
        assert isinstance(event, Event)
        assert isinstance(event, CustomEvent)


# ---------------------------------------------------------------------------
# EventQueue construction
# ---------------------------------------------------------------------------


class TestEventQueueInit:
    """EventQueue construction and validation."""

    def test_default_max_size(self) -> None:
        eq = EventQueue()
        assert eq.max_size == 1024

    def test_custom_max_size(self) -> None:
        eq = EventQueue(max_size=10)
        assert eq.max_size == 10

    def test_min_max_size(self) -> None:
        eq = EventQueue(max_size=1)
        assert eq.max_size == 1

    def test_max_max_size(self) -> None:
        eq = EventQueue(max_size=65536)
        assert eq.max_size == 65536

    def test_rejects_zero_max_size(self) -> None:
        with pytest.raises(ValueError, match="max_size must be between"):
            EventQueue(max_size=0)

    def test_rejects_negative_max_size(self) -> None:
        with pytest.raises(ValueError, match="max_size must be between"):
            EventQueue(max_size=-1)

    def test_rejects_too_large_max_size(self) -> None:
        with pytest.raises(ValueError, match="max_size must be between"):
            EventQueue(max_size=65537)

    def test_rejects_float_max_size(self) -> None:
        with pytest.raises(TypeError, match="max_size must be an int"):
            EventQueue(max_size=10.0)  # type: ignore[arg-type]

    def test_rejects_bool_max_size(self) -> None:
        with pytest.raises(TypeError, match="max_size must be an int"):
            EventQueue(max_size=True)  # type: ignore[arg-type]

    def test_rejects_string_max_size(self) -> None:
        with pytest.raises(TypeError, match="max_size must be an int"):
            EventQueue(max_size="10")  # type: ignore[arg-type]

    def test_starts_empty(self) -> None:
        eq = EventQueue()
        assert len(eq) == 0
        assert eq.is_empty is True

    def test_drop_count_starts_at_zero(self) -> None:
        eq = EventQueue()
        assert eq.drop_count == 0


# ---------------------------------------------------------------------------
# EventQueue.post
# ---------------------------------------------------------------------------


class TestEventQueuePost:
    """Posting events to the queue."""

    def test_post_single_event(self) -> None:
        eq = EventQueue()
        result = eq.post(Event())
        assert result is True
        assert len(eq) == 1

    def test_post_multiple_events(self) -> None:
        eq = EventQueue()
        for _ in range(5):
            eq.post(Event())
        assert len(eq) == 5

    def test_post_returns_true_when_accepted(self) -> None:
        eq = EventQueue(max_size=10)
        assert eq.post(Event()) is True

    def test_post_rejects_non_event(self) -> None:
        eq = EventQueue()
        with pytest.raises(TypeError, match="event must be an Event instance"):
            eq.post("not an event")  # type: ignore[arg-type]

    def test_post_rejects_none(self) -> None:
        eq = EventQueue()
        with pytest.raises(TypeError, match="event must be an Event instance"):
            eq.post(None)  # type: ignore[arg-type]

    def test_post_rejects_dict(self) -> None:
        eq = EventQueue()
        with pytest.raises(TypeError, match="event must be an Event instance"):
            eq.post({"type": "key"})  # type: ignore[arg-type]

    def test_post_accepts_event_subclass(self) -> None:
        class MyEvent(Event):
            __slots__ = ()

        eq = EventQueue()
        assert eq.post(MyEvent()) is True
        assert len(eq) == 1


# ---------------------------------------------------------------------------
# EventQueue capacity and dropping
# ---------------------------------------------------------------------------


class TestEventQueueCapacity:
    """Bounded queue behaviour when full."""

    def test_is_full_when_at_capacity(self) -> None:
        eq = EventQueue(max_size=3)
        eq.post(Event())
        eq.post(Event())
        assert eq.is_full is False
        eq.post(Event())
        assert eq.is_full is True

    def test_post_drops_when_full(self) -> None:
        eq = EventQueue(max_size=2)
        eq.post(Event())
        eq.post(Event())
        result = eq.post(Event())
        assert result is False
        assert len(eq) == 2

    def test_drop_count_increments(self) -> None:
        eq = EventQueue(max_size=1)
        eq.post(Event())
        eq.post(Event())
        eq.post(Event())
        assert eq.drop_count == 2

    def test_drop_logs_warning(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        eq = EventQueue(max_size=1)
        eq.post(Event())
        with caplog.at_level(logging.WARNING, logger="wyby.event"):
            eq.post(Event())
        assert any("full" in r.message.lower() for r in caplog.records)

    def test_drop_count_is_cumulative(self) -> None:
        eq = EventQueue(max_size=1)
        eq.post(Event())
        eq.post(Event())  # dropped
        eq.drain()
        eq.post(Event())
        eq.post(Event())  # dropped again
        assert eq.drop_count == 2


# ---------------------------------------------------------------------------
# EventQueue.drain
# ---------------------------------------------------------------------------


class TestEventQueueDrain:
    """Draining events from the queue."""

    def test_drain_empty_queue(self) -> None:
        eq = EventQueue()
        result = eq.drain()
        assert result == []

    def test_drain_returns_all_events(self) -> None:
        eq = EventQueue()
        events = [Event() for _ in range(3)]
        for e in events:
            eq.post(e)
        drained = eq.drain()
        assert drained == events

    def test_drain_preserves_fifo_order(self) -> None:
        class A(Event):
            __slots__ = ()

        class B(Event):
            __slots__ = ()

        class C(Event):
            __slots__ = ()

        eq = EventQueue()
        a, b, c = A(), B(), C()
        eq.post(a)
        eq.post(b)
        eq.post(c)
        drained = eq.drain()
        assert drained[0] is a
        assert drained[1] is b
        assert drained[2] is c

    def test_drain_clears_queue(self) -> None:
        eq = EventQueue()
        eq.post(Event())
        eq.post(Event())
        eq.drain()
        assert len(eq) == 0
        assert eq.is_empty is True

    def test_drain_returns_list(self) -> None:
        eq = EventQueue()
        eq.post(Event())
        result = eq.drain()
        assert isinstance(result, list)

    def test_successive_drains(self) -> None:
        eq = EventQueue()
        eq.post(Event())
        first = eq.drain()
        assert len(first) == 1

        eq.post(Event())
        eq.post(Event())
        second = eq.drain()
        assert len(second) == 2

        third = eq.drain()
        assert len(third) == 0


# ---------------------------------------------------------------------------
# EventQueue.peek
# ---------------------------------------------------------------------------


class TestEventQueuePeek:
    """Peeking at the front of the queue."""

    def test_peek_empty(self) -> None:
        eq = EventQueue()
        assert eq.peek() is None

    def test_peek_returns_front(self) -> None:
        eq = EventQueue()
        first = Event()
        eq.post(first)
        eq.post(Event())
        assert eq.peek() is first

    def test_peek_does_not_remove(self) -> None:
        eq = EventQueue()
        eq.post(Event())
        eq.peek()
        assert len(eq) == 1


# ---------------------------------------------------------------------------
# EventQueue.clear
# ---------------------------------------------------------------------------


class TestEventQueueClear:
    """Clearing the queue."""

    def test_clear_empty_queue(self) -> None:
        eq = EventQueue()
        eq.clear()  # should not raise
        assert len(eq) == 0

    def test_clear_removes_all_events(self) -> None:
        eq = EventQueue()
        for _ in range(5):
            eq.post(Event())
        eq.clear()
        assert len(eq) == 0
        assert eq.is_empty is True

    def test_clear_does_not_affect_drop_count(self) -> None:
        eq = EventQueue(max_size=1)
        eq.post(Event())
        eq.post(Event())  # dropped
        eq.clear()
        assert eq.drop_count == 1  # not reset

    def test_clear_logs_debug(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        eq = EventQueue()
        eq.post(Event())
        with caplog.at_level(logging.DEBUG, logger="wyby.event"):
            eq.clear()
        assert any("cleared" in r.message.lower() for r in caplog.records)


# ---------------------------------------------------------------------------
# EventQueue __len__, __bool__, __repr__
# ---------------------------------------------------------------------------


class TestEventQueueDunder:
    """Dunder method behaviour."""

    def test_len_empty(self) -> None:
        assert len(EventQueue()) == 0

    def test_len_after_post(self) -> None:
        eq = EventQueue()
        eq.post(Event())
        assert len(eq) == 1

    def test_bool_empty_is_false(self) -> None:
        assert not EventQueue()

    def test_bool_nonempty_is_true(self) -> None:
        eq = EventQueue()
        eq.post(Event())
        assert eq

    def test_repr(self) -> None:
        eq = EventQueue(max_size=10)
        assert repr(eq) == "EventQueue(len=0, max_size=10)"

    def test_repr_after_post(self) -> None:
        eq = EventQueue(max_size=10)
        eq.post(Event())
        assert repr(eq) == "EventQueue(len=1, max_size=10)"


# ---------------------------------------------------------------------------
# Import from top-level package
# ---------------------------------------------------------------------------


class TestEventImports:
    """Event and EventQueue should be importable from the wyby package."""

    def test_event_importable(self) -> None:
        from wyby import Event as EventFromInit

        assert EventFromInit is Event

    def test_event_queue_importable(self) -> None:
        from wyby import EventQueue as EQFromInit

        assert EQFromInit is EventQueue

    def test_event_in_all(self) -> None:
        import wyby

        assert "Event" in wyby.__all__

    def test_event_queue_in_all(self) -> None:
        import wyby

        assert "EventQueue" in wyby.__all__
