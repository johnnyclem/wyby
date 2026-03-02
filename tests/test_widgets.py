"""Tests for UI widgets."""

import pytest

from rich.style import Style

from runetui.events import KeyEvent, MouseEvent
from runetui.renderer import Renderer
from runetui.widgets import Button, HealthBar


class TestButton:
    def test_creation(self):
        btn = Button(x=0, y=0, label="OK")
        assert btn.label == "OK"
        assert btn.width == len("OK") + 4

    def test_contains(self):
        btn = Button(x=5, y=5, label="Test")
        assert btn.contains(6, 6) is True
        assert btn.contains(0, 0) is False

    def test_click_handler(self):
        clicked = []
        btn = Button(x=0, y=0, label="Click", on_click=lambda: clicked.append(True))
        event = MouseEvent(x=2, y=1, button="left")
        btn.handle_event(event)
        assert len(clicked) == 1

    def test_keyboard_activation(self):
        clicked = []
        btn = Button(x=0, y=0, label="Press", on_click=lambda: clicked.append(True))
        btn.focused = True
        event = KeyEvent(key="\r")
        btn.handle_event(event)
        assert len(clicked) == 1

    def test_render(self):
        btn = Button(x=0, y=0, label="OK")
        r = Renderer(20, 5)
        btn.render(r)
        # Check that the label appears in the buffer
        row = r._buffer[1]  # middle row of 3-high button
        chars = "".join(c.char for c in row)
        assert "OK" in chars


class TestHealthBar:
    def test_full_health(self):
        bar = HealthBar(x=0, y=0, width=10, current=100, maximum=100)
        assert bar.fraction == 1.0

    def test_half_health(self):
        bar = HealthBar(x=0, y=0, width=10, current=50, maximum=100)
        assert abs(bar.fraction - 0.5) < 0.001

    def test_zero_health(self):
        bar = HealthBar(x=0, y=0, width=10, current=0, maximum=100)
        assert bar.fraction == 0.0

    def test_zero_max(self):
        bar = HealthBar(x=0, y=0, width=10, current=50, maximum=0)
        assert bar.fraction == 0.0

    def test_render(self):
        bar = HealthBar(x=0, y=0, width=10, current=50, maximum=100)
        r = Renderer(20, 3)
        bar.render(r)
        # Should not raise
