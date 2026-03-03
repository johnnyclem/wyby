"""Tests for input polling integration in the Engine game loop.

These tests verify that the Engine correctly polls an InputManager
each tick, posts events to the event queue, and manages the
InputManager lifecycle (start/stop).
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from wyby._platform import InputBackend
from wyby.app import Engine
from wyby.event import Event, EventQueue
from wyby.input import InputManager, KeyEvent, MouseEvent
from wyby.scene import Scene


# ---------------------------------------------------------------------------
# Fake backend for deterministic input in tests
# ---------------------------------------------------------------------------


class FakeBackend(InputBackend):
    """A test backend that returns pre-configured byte sequences.

    Each call to read_bytes() pops the next entry from a list of
    byte strings.  When the list is exhausted, returns empty bytes.
    """

    def __init__(self, responses: list[bytes] | None = None) -> None:
        self._responses: list[bytes] = responses or []
        self._raw = False

    def enter_raw_mode(self) -> None:
        self._raw = True

    def exit_raw_mode(self) -> None:
        self._raw = False

    def has_input(self) -> bool:
        return len(self._responses) > 0

    def read_bytes(self) -> bytes:
        if self._responses:
            return self._responses.pop(0)
        return b""

    @property
    def is_raw(self) -> bool:
        return self._raw


# ---------------------------------------------------------------------------
# Engine accepts an InputManager
# ---------------------------------------------------------------------------


class TestEngineInputManagerInit:
    """Engine should accept an optional InputManager parameter."""

    def test_input_manager_default_is_none(self) -> None:
        engine = Engine()
        assert engine.input_manager is None

    def test_input_manager_property_returns_same_instance(self) -> None:
        backend = FakeBackend()
        mgr = InputManager(backend=backend)
        engine = Engine(input_manager=mgr)
        assert engine.input_manager is mgr

    def test_input_manager_is_read_only(self) -> None:
        engine = Engine()
        with pytest.raises(AttributeError):
            engine.input_manager = InputManager(  # type: ignore[misc]
                backend=FakeBackend()
            )

    def test_rejects_non_input_manager(self) -> None:
        with pytest.raises(TypeError, match="input_manager must be"):
            Engine(input_manager="not an InputManager")  # type: ignore[arg-type]

    def test_rejects_wrong_type(self) -> None:
        with pytest.raises(TypeError, match="input_manager must be"):
            Engine(input_manager=42)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# InputManager lifecycle (start/stop)
# ---------------------------------------------------------------------------


class TestInputManagerLifecycle:
    """Engine should start the InputManager in run() and stop in shutdown."""

    def test_input_manager_started_during_run(self) -> None:
        backend = FakeBackend()
        mgr = InputManager(backend=backend)
        engine = Engine(input_manager=mgr)
        assert mgr.is_started is False
        engine.run(loop=False)
        # After run() completes, shutdown has stopped it.
        assert mgr.is_started is False

    def test_input_manager_stopped_during_shutdown(self) -> None:
        backend = FakeBackend()
        mgr = InputManager(backend=backend)
        engine = Engine(input_manager=mgr)
        engine.run(loop=False)
        assert mgr.is_started is False
        assert backend.is_raw is False

    def test_input_manager_started_then_stopped(self) -> None:
        """Verify the InputManager is started before tick and stopped after."""
        backend = FakeBackend()
        mgr = InputManager(backend=backend)
        was_started_during_tick = [False]

        class SpyScene(Scene):
            def update(self_, dt: float) -> None:
                was_started_during_tick[0] = mgr.is_started

            def render(self_) -> None:
                pass

        engine = Engine(input_manager=mgr)
        engine.scenes.push(SpyScene())
        engine.run(loop=False)

        assert was_started_during_tick[0] is True
        assert mgr.is_started is False  # stopped after run

    def test_no_crash_without_input_manager(self) -> None:
        """Engine should work fine without an InputManager."""
        engine = Engine()
        engine.run(loop=False)
        assert engine.tick_count == 1


# ---------------------------------------------------------------------------
# Input polling posts events to the queue
# ---------------------------------------------------------------------------


class TestInputPollingPostsEvents:
    """The engine should poll InputManager each tick and post events."""

    def test_key_events_posted_to_queue(self) -> None:
        """Pressing 'a' should produce a KeyEvent posted to the queue."""
        backend = FakeBackend(responses=[b"a"])
        mgr = InputManager(backend=backend)

        posted_events: list[Event] = []
        original_post = EventQueue.post

        def tracking_post(self: EventQueue, event: Event) -> bool:
            posted_events.append(event)
            return original_post(self, event)

        with patch.object(EventQueue, "post", tracking_post):
            engine = Engine(input_manager=mgr)
            engine.run(loop=False)

        key_events = [e for e in posted_events if isinstance(e, KeyEvent)]
        assert len(key_events) == 1
        assert key_events[0].key == "a"

    def test_events_drained_during_tick(self) -> None:
        """Events polled from InputManager should be drained each tick."""
        backend = FakeBackend(responses=[b"ab"])
        mgr = InputManager(backend=backend)

        queue_len_during_update: list[int] = []

        class SpyScene(Scene):
            def update(self_, dt: float) -> None:
                # By update time, events have been posted and drained.
                queue_len_during_update.append(len(engine.events))

            def render(self_) -> None:
                pass

        engine = Engine(input_manager=mgr)
        engine.scenes.push(SpyScene())
        engine.run(loop=False)

        # Events were posted and drained before update().
        assert queue_len_during_update == [0]

    def test_multiple_keys_posted(self) -> None:
        """Multiple keypresses in one poll should all be posted."""
        backend = FakeBackend(responses=[b"abc"])
        mgr = InputManager(backend=backend)

        posted_events: list[Event] = []
        original_post = EventQueue.post

        def tracking_post(self: EventQueue, event: Event) -> bool:
            posted_events.append(event)
            return original_post(self, event)

        with patch.object(EventQueue, "post", tracking_post):
            engine = Engine(input_manager=mgr)
            engine.run(loop=False)

        # 'a', 'b', 'c' should each generate a KeyEvent.
        key_events = [e for e in posted_events if isinstance(e, KeyEvent)]
        assert len(key_events) == 3
        keys = [e.key for e in key_events]
        assert keys == ["a", "b", "c"]

    def test_no_events_when_no_input(self) -> None:
        """With no input available, no events should be posted."""
        backend = FakeBackend(responses=[])
        mgr = InputManager(backend=backend)

        posted_events: list[Event] = []
        original_post = EventQueue.post

        def tracking_post(self: EventQueue, event: Event) -> bool:
            posted_events.append(event)
            return original_post(self, event)

        with patch.object(EventQueue, "post", tracking_post):
            engine = Engine(input_manager=mgr)
            engine.run(loop=False)

        assert len(posted_events) == 0

    def test_arrow_key_events_posted(self) -> None:
        """Arrow key ANSI sequences should produce KeyEvents."""
        # Up arrow: ESC [ A
        backend = FakeBackend(responses=[b"\x1b[A"])
        mgr = InputManager(backend=backend)

        posted_events: list[Event] = []
        original_post = EventQueue.post

        def tracking_post(self: EventQueue, event: Event) -> bool:
            posted_events.append(event)
            return original_post(self, event)

        with patch.object(EventQueue, "post", tracking_post):
            engine = Engine(input_manager=mgr)
            engine.run(loop=False)

        key_events = [e for e in posted_events if isinstance(e, KeyEvent)]
        assert len(key_events) == 1
        assert key_events[0].key == "up"

    def test_mouse_events_posted(self) -> None:
        """SGR mouse sequences should produce MouseEvents."""
        # SGR mouse press: ESC[<0;10;5M (left click at col 10, row 5)
        backend = FakeBackend(responses=[b"\x1b[<0;10;5M"])
        mgr = InputManager(backend=backend, mouse=True)

        posted_events: list[Event] = []
        original_post = EventQueue.post

        def tracking_post(self: EventQueue, event: Event) -> bool:
            posted_events.append(event)
            return original_post(self, event)

        with patch.object(EventQueue, "post", tracking_post):
            engine = Engine(input_manager=mgr)
            engine.run(loop=False)

        mouse_events = [
            e for e in posted_events if isinstance(e, MouseEvent)
        ]
        assert len(mouse_events) == 1
        # SGR coordinates are 1-based; converted to 0-based.
        assert mouse_events[0].x == 9
        assert mouse_events[0].y == 4
        assert mouse_events[0].button == "left"
        assert mouse_events[0].action == "press"


# ---------------------------------------------------------------------------
# Input polling across multiple ticks
# ---------------------------------------------------------------------------


class TestInputPollingMultipleTicks:
    """Input should be polled each tick, not just the first."""

    def test_input_polled_each_tick(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Each tick should poll for new input."""
        # First tick: 'a', second tick: 'b', third tick: nothing.
        backend = FakeBackend(responses=[b"a", b"b"])
        mgr = InputManager(backend=backend)

        posted_events: list[Event] = []
        original_post = EventQueue.post

        def tracking_post(self: EventQueue, event: Event) -> bool:
            posted_events.append(event)
            return original_post(self, event)

        original_tick = Engine._tick
        tick_count = [0]

        def counting_tick(self_: Engine) -> None:
            original_tick(self_)
            tick_count[0] += 1
            if tick_count[0] >= 3:
                self_.stop()

        monkeypatch.setattr(Engine, "_tick", counting_tick)

        with patch.object(EventQueue, "post", tracking_post):
            engine = Engine(input_manager=mgr)
            engine.run(loop=True)

        assert tick_count[0] == 3
        # 'a' from first tick, 'b' from second tick.
        key_events = [e for e in posted_events if isinstance(e, KeyEvent)]
        assert len(key_events) == 2
        keys = [e.key for e in key_events]
        assert keys == ["a", "b"]


# ---------------------------------------------------------------------------
# Manual events still work alongside input polling
# ---------------------------------------------------------------------------


class TestManualEventsWithInputPolling:
    """Events posted manually should coexist with polled input events."""

    def test_manual_and_polled_events_both_drained(self) -> None:
        """Both manually posted and polled events should be processed."""
        backend = FakeBackend(responses=[b"x"])
        mgr = InputManager(backend=backend)

        posted_events: list[Event] = []
        original_post = EventQueue.post

        def tracking_post(self: EventQueue, event: Event) -> bool:
            posted_events.append(event)
            return original_post(self, event)

        with patch.object(EventQueue, "post", tracking_post):
            engine = Engine(input_manager=mgr)

            # Post a manual event before running.
            manual_event = Event()
            engine.events.post(manual_event)

            engine.run(loop=False)

        # Should have the manual event + the polled KeyEvent('x').
        assert len(posted_events) == 2
        assert posted_events[0] is manual_event
        key_events = [e for e in posted_events if isinstance(e, KeyEvent)]
        assert len(key_events) == 1
        assert key_events[0].key == "x"


# ---------------------------------------------------------------------------
# KeyboardInterrupt from input polling
# ---------------------------------------------------------------------------


class TestCtrlCFromInputPolling:
    """Ctrl+C during input polling should stop the engine cleanly."""

    def test_ctrl_c_stops_engine(self) -> None:
        """Ctrl+C (byte 0x03) should raise KeyboardInterrupt and stop."""
        backend = FakeBackend(responses=[b"\x03"])
        mgr = InputManager(backend=backend)

        class StubScene(Scene):
            def update(self_, dt: float) -> None:
                pass

            def render(self_) -> None:
                pass

        engine = Engine(input_manager=mgr)
        engine.scenes.push(StubScene())
        # Should not raise — KeyboardInterrupt is caught by run().
        engine.run(loop=False)
        assert engine.running is False
        # InputManager should be stopped (shutdown cleanup).
        assert mgr.is_started is False
