"""Tests for the example MainMenuScene and GameScene.

These tests verify the example scenes' logic (input handling, state
transitions, rendering) without requiring a terminal or running the
Engine's game loop.  Scenes are tested in isolation by calling their
methods directly.
"""

from __future__ import annotations

import sys
import os

import pytest

# Add examples directory to path so we can import the example module.
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), os.pardir, "examples")
)

from mainmenu_game import GameScene, MainMenuScene

from wyby.app import QuitSignal
from wyby.input import KeyEvent
from wyby.scene import SceneStack


# ---------------------------------------------------------------------------
# MainMenuScene
# ---------------------------------------------------------------------------


class TestMainMenuScene:
    """Tests for MainMenuScene input handling and state transitions."""

    def test_initial_selection_is_zero(self) -> None:
        menu = MainMenuScene()
        assert menu.selected == 0

    def test_down_arrow_moves_selection(self) -> None:
        menu = MainMenuScene()
        menu.handle_events([KeyEvent(key="down")])
        assert menu.selected == 1

    def test_up_arrow_wraps_to_last(self) -> None:
        menu = MainMenuScene()
        assert menu.selected == 0
        menu.handle_events([KeyEvent(key="up")])
        assert menu.selected == len(MainMenuScene.OPTIONS) - 1

    def test_down_arrow_wraps_to_first(self) -> None:
        menu = MainMenuScene()
        # Move down past the last option.
        for _ in range(len(MainMenuScene.OPTIONS)):
            menu.handle_events([KeyEvent(key="down")])
        assert menu.selected == 0

    def test_enter_on_new_game_calls_callback(self) -> None:
        called = []
        menu = MainMenuScene(on_start_game=lambda: called.append(True))
        # "New Game" is option 0 (already selected).
        menu.handle_events([KeyEvent(key="enter")])
        menu.update(1 / 30)
        assert called == [True]

    def test_enter_on_quit_raises_quit_signal(self) -> None:
        menu = MainMenuScene()
        # Move to "Quit" (option 1).
        menu.handle_events([KeyEvent(key="down")])
        menu.handle_events([KeyEvent(key="enter")])
        with pytest.raises(QuitSignal):
            menu.update(1 / 30)

    def test_enter_without_callback_is_noop(self) -> None:
        """Selecting 'New Game' with no callback does not crash."""
        menu = MainMenuScene(on_start_game=None)
        menu.handle_events([KeyEvent(key="enter")])
        menu.update(1 / 30)  # Should not raise.

    def test_non_key_events_are_ignored(self) -> None:
        """Non-KeyEvent objects in the event list are silently skipped."""
        from wyby.event import Event

        menu = MainMenuScene()
        menu.handle_events([Event()])
        assert menu.selected == 0

    def test_render_does_not_raise(self) -> None:
        menu = MainMenuScene()
        menu.render()  # Should not raise.

    def test_render_writes_title_to_buffer(self) -> None:
        menu = MainMenuScene(width=40, height=15)
        menu.render()
        # Check that the title text appears somewhere in row 2.
        row = menu.buffer.row(2)
        text = "".join(cell.char for cell in row).strip()
        assert MainMenuScene.TITLE in text

    def test_render_highlights_selected_option(self) -> None:
        menu = MainMenuScene(width=40, height=15)
        menu.render()
        # Selected option (index 0) should have the ">" marker.
        row = menu.buffer.row(5)
        text = "".join(cell.char for cell in row).strip()
        assert text.startswith(">")

    def test_activate_flag_resets_after_update(self) -> None:
        """The _activate flag is consumed in update and does not persist."""
        called = []
        menu = MainMenuScene(on_start_game=lambda: called.append(True))
        menu.handle_events([KeyEvent(key="enter")])
        menu.update(1 / 30)
        assert called == [True]
        # Second update should not call the callback again.
        menu.update(1 / 30)
        assert called == [True]


# ---------------------------------------------------------------------------
# GameScene
# ---------------------------------------------------------------------------


class TestGameScene:
    """Tests for GameScene movement, boundaries, and transitions."""

    def test_player_starts_in_center(self) -> None:
        game = GameScene(width=40, height=15)
        assert game.player_x == 20
        assert game.player_y == 7

    def test_move_up(self) -> None:
        game = GameScene(width=40, height=15)
        start_y = game.player_y
        game.handle_events([KeyEvent(key="up")])
        assert game.player_y == start_y - 1

    def test_move_down(self) -> None:
        game = GameScene(width=40, height=15)
        start_y = game.player_y
        game.handle_events([KeyEvent(key="down")])
        assert game.player_y == start_y + 1

    def test_move_left(self) -> None:
        game = GameScene(width=40, height=15)
        start_x = game.player_x
        game.handle_events([KeyEvent(key="left")])
        assert game.player_x == start_x - 1

    def test_move_right(self) -> None:
        game = GameScene(width=40, height=15)
        start_x = game.player_x
        game.handle_events([KeyEvent(key="right")])
        assert game.player_x == start_x + 1

    def test_cannot_move_above_top_border(self) -> None:
        game = GameScene(width=40, height=15)
        game.player_y = 1  # Already at top border.
        game.handle_events([KeyEvent(key="up")])
        assert game.player_y == 1

    def test_cannot_move_below_bottom_border(self) -> None:
        game = GameScene(width=40, height=15)
        game.player_y = 13  # height - 2 = 13, at bottom border.
        game.handle_events([KeyEvent(key="down")])
        assert game.player_y == 13

    def test_cannot_move_past_left_border(self) -> None:
        game = GameScene(width=40, height=15)
        game.player_x = 1  # Already at left border.
        game.handle_events([KeyEvent(key="left")])
        assert game.player_x == 1

    def test_cannot_move_past_right_border(self) -> None:
        game = GameScene(width=40, height=15)
        game.player_x = 38  # width - 2 = 38, at right border.
        game.handle_events([KeyEvent(key="right")])
        assert game.player_x == 38

    def test_escape_triggers_menu_return_callback(self) -> None:
        called = []
        game = GameScene(on_return_to_menu=lambda: called.append(True))
        game.handle_events([KeyEvent(key="escape")])
        game.update(1 / 30)
        assert called == [True]

    def test_escape_without_callback_is_noop(self) -> None:
        """Pressing Escape with no callback does not crash."""
        game = GameScene(on_return_to_menu=None)
        game.handle_events([KeyEvent(key="escape")])
        game.update(1 / 30)  # Should not raise.

    def test_wants_menu_flag_resets(self) -> None:
        """The _wants_menu flag is consumed and does not persist."""
        called = []
        game = GameScene(on_return_to_menu=lambda: called.append(True))
        game.handle_events([KeyEvent(key="escape")])
        game.update(1 / 30)
        assert called == [True]
        game.update(1 / 30)
        assert called == [True]  # Not called again.

    def test_non_key_events_are_ignored(self) -> None:
        from wyby.event import Event

        game = GameScene(width=40, height=15)
        start_x, start_y = game.player_x, game.player_y
        game.handle_events([Event()])
        assert game.player_x == start_x
        assert game.player_y == start_y

    def test_multiple_moves_in_single_tick(self) -> None:
        """Multiple key events in one batch all take effect."""
        game = GameScene(width=40, height=15)
        start_x = game.player_x
        game.handle_events([
            KeyEvent(key="right"),
            KeyEvent(key="right"),
            KeyEvent(key="right"),
        ])
        assert game.player_x == start_x + 3

    def test_render_does_not_raise(self) -> None:
        game = GameScene(width=40, height=15)
        game.render()  # Should not raise.

    def test_render_draws_player_at_position(self) -> None:
        game = GameScene(width=40, height=15)
        game.render()
        cell = game.buffer.get(game.player_x, game.player_y)
        assert cell is not None
        assert cell.char == "@"

    def test_render_draws_border_corners(self) -> None:
        game = GameScene(width=40, height=15)
        game.render()
        assert game.buffer.get(0, 0).char == GameScene.CORNER_TL
        assert game.buffer.get(39, 0).char == GameScene.CORNER_TR
        assert game.buffer.get(0, 14).char == GameScene.CORNER_BL
        assert game.buffer.get(39, 14).char == GameScene.CORNER_BR


# ---------------------------------------------------------------------------
# Scene stack integration
# ---------------------------------------------------------------------------


class TestSceneStackIntegration:
    """Test that the example scenes work correctly with SceneStack."""

    def test_push_menu_then_game(self) -> None:
        stack = SceneStack()
        menu = MainMenuScene()
        stack.push(menu)
        assert stack.peek() is menu

        game = GameScene()
        stack.push(game)
        assert stack.peek() is game
        assert len(stack) == 2

    def test_pop_game_returns_to_menu(self) -> None:
        stack = SceneStack()
        menu = MainMenuScene()
        game = GameScene()
        stack.push(menu)
        stack.push(game)

        popped = stack.pop()
        assert popped is game
        assert stack.peek() is menu

    def test_replace_menu_with_game(self) -> None:
        stack = SceneStack()
        menu = MainMenuScene()
        stack.push(menu)

        game = GameScene()
        replaced = stack.replace(game)
        assert replaced is menu
        assert stack.peek() is game
        assert len(stack) == 1

    def test_menu_starts_game_via_callback(self) -> None:
        """End-to-end: menu callback pushes game scene onto stack."""
        stack = SceneStack()

        def start_game() -> None:
            stack.push(GameScene())

        menu = MainMenuScene(on_start_game=start_game)
        stack.push(menu)

        # Simulate selecting "New Game" and updating.
        menu.handle_events([KeyEvent(key="enter")])
        menu.update(1 / 30)

        assert len(stack) == 2
        assert isinstance(stack.peek(), GameScene)

    def test_game_returns_to_menu_via_callback(self) -> None:
        """End-to-end: escape in game pops back to menu."""
        stack = SceneStack()
        menu = MainMenuScene()
        stack.push(menu)

        game = GameScene(on_return_to_menu=lambda: stack.pop())
        stack.push(game)
        assert len(stack) == 2

        # Simulate pressing Escape and updating.
        game.handle_events([KeyEvent(key="escape")])
        game.update(1 / 30)

        assert len(stack) == 1
        assert stack.peek() is menu
