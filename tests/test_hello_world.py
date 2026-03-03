"""Tests for the hello-world example scene."""

from __future__ import annotations

import pytest

from wyby.app import QuitSignal
from wyby.grid import CellBuffer
from wyby.input import KeyEvent

# Import from the examples directory.
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "examples"))
from hello_world import HelloWorldScene


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestHelloWorldSceneConstruction:
    """HelloWorldScene initialisation and defaults."""

    def test_default_dimensions(self) -> None:
        scene = HelloWorldScene()
        assert scene.buffer.width == 40
        assert scene.buffer.height == 12

    def test_custom_dimensions(self) -> None:
        scene = HelloWorldScene(width=80, height=24)
        assert scene.buffer.width == 80
        assert scene.buffer.height == 24

    def test_default_message(self) -> None:
        scene = HelloWorldScene()
        assert scene.message == "Hello, World!"

    def test_custom_message(self) -> None:
        scene = HelloWorldScene(message="Greetings!")
        assert scene.message == "Greetings!"

    def test_buffer_is_cellbuffer(self) -> None:
        scene = HelloWorldScene()
        assert isinstance(scene.buffer, CellBuffer)


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


class TestHelloWorldSceneRender:
    """HelloWorldScene.render() writes the greeting to the buffer."""

    def test_render_writes_message_to_buffer(self) -> None:
        """After render(), the greeting text should appear in the buffer."""
        scene = HelloWorldScene(width=40, height=12, message="Hello, World!")
        scene.render()

        # The message should be centred at row 6 (height // 2).
        # Read characters from the buffer at the expected position.
        msg = "Hello, World!"
        msg_x = (40 - len(msg)) // 2
        msg_y = 6

        extracted = ""
        for i in range(len(msg)):
            cell = scene.buffer.get(msg_x + i, msg_y)
            assert cell is not None
            extracted += cell.char

        assert extracted == msg

    def test_render_message_is_bright_green_bold(self) -> None:
        """The greeting should be styled bright_green and bold."""
        scene = HelloWorldScene(width=40, height=12)
        scene.render()

        msg = "Hello, World!"
        msg_x = (40 - len(msg)) // 2
        msg_y = 6

        cell = scene.buffer.get(msg_x, msg_y)
        assert cell is not None
        assert cell.fg == "bright_green"
        assert cell.bold is True

    def test_render_hint_text_present(self) -> None:
        """The quit hint should appear below the greeting."""
        scene = HelloWorldScene(width=40, height=12)
        scene.render()

        hint = "Press q or Esc to quit"
        hint_x = (40 - len(hint)) // 2
        # Hint is 2 rows below the message (msg_y=6, hint_y=8).
        hint_y = 8

        extracted = ""
        for i in range(len(hint)):
            cell = scene.buffer.get(hint_x + i, hint_y)
            assert cell is not None
            extracted += cell.char

        assert extracted == hint

    def test_render_clears_buffer_each_frame(self) -> None:
        """render() should clear the buffer before drawing."""
        scene = HelloWorldScene(width=40, height=12)

        # Write something to the buffer at an unrelated position.
        from wyby.grid import Cell
        scene.buffer.put(0, 0, Cell(char="X", fg="red"))

        scene.render()

        # The X should be gone (buffer was cleared).
        cell = scene.buffer.get(0, 0)
        assert cell is not None
        assert cell.char == " "

    def test_render_custom_message(self) -> None:
        """A custom message should appear centred."""
        msg = "Hi!"
        scene = HelloWorldScene(width=20, height=8, message=msg)
        scene.render()

        msg_x = (20 - len(msg)) // 2
        msg_y = 4

        extracted = ""
        for i in range(len(msg)):
            cell = scene.buffer.get(msg_x + i, msg_y)
            assert cell is not None
            extracted += cell.char

        assert extracted == msg


# ---------------------------------------------------------------------------
# Update (no-op)
# ---------------------------------------------------------------------------


class TestHelloWorldSceneUpdate:
    """HelloWorldScene.update() is a no-op."""

    def test_update_does_not_raise(self) -> None:
        scene = HelloWorldScene()
        # Should not raise for any dt value.
        scene.update(0.033)
        scene.update(0.0)
        scene.update(1.0)


# ---------------------------------------------------------------------------
# Event handling
# ---------------------------------------------------------------------------


class TestHelloWorldSceneEvents:
    """HelloWorldScene.handle_events() quits on q or Escape."""

    def test_quit_on_q(self) -> None:
        scene = HelloWorldScene()
        with pytest.raises(QuitSignal):
            scene.handle_events([KeyEvent(key="q")])

    def test_quit_on_escape(self) -> None:
        scene = HelloWorldScene()
        with pytest.raises(QuitSignal):
            scene.handle_events([KeyEvent(key="escape")])

    def test_no_quit_on_other_key(self) -> None:
        """Non-quit keys should not raise."""
        scene = HelloWorldScene()
        # Should not raise.
        scene.handle_events([KeyEvent(key="a")])
        scene.handle_events([KeyEvent(key="up")])
        scene.handle_events([KeyEvent(key="enter")])

    def test_empty_events_no_raise(self) -> None:
        """Empty event list should be fine."""
        scene = HelloWorldScene()
        scene.handle_events([])

    def test_non_key_events_ignored(self) -> None:
        """Non-KeyEvent objects in the list should be silently ignored."""
        scene = HelloWorldScene()
        # Pass a plain string — not a KeyEvent. Should be ignored.
        scene.handle_events(["not a key event"])
