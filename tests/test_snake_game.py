"""Tests for the snake game example scene."""

from __future__ import annotations

import random

import pytest

from wyby.app import QuitSignal
from wyby.grid import CellBuffer
from wyby.input import KeyEvent

# Import from the examples directory.
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "examples"))
from snake_game import (
    DOWN,
    LEFT,
    RIGHT,
    UP,
    SnakeGameScene,
)


# ---------------------------------------------------------------------------
# Helper — deterministic scene with seeded RNG
# ---------------------------------------------------------------------------


def _make_scene(
    width: int = 30,
    height: int = 20,
    move_interval: float = 0.12,
    seed: int = 42,
) -> SnakeGameScene:
    """Create a SnakeGameScene with a seeded RNG for reproducible tests."""
    return SnakeGameScene(
        width=width,
        height=height,
        move_interval=move_interval,
        rng=random.Random(seed),
    )


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestSnakeGameSceneConstruction:
    """SnakeGameScene initialisation and defaults."""

    def test_default_dimensions(self) -> None:
        scene = _make_scene()
        assert scene.buffer.width == 30
        assert scene.buffer.height == 20

    def test_custom_dimensions(self) -> None:
        scene = _make_scene(width=40, height=25)
        assert scene.buffer.width == 40
        assert scene.buffer.height == 25

    def test_buffer_is_cellbuffer(self) -> None:
        scene = _make_scene()
        assert isinstance(scene.buffer, CellBuffer)

    def test_initial_snake_length(self) -> None:
        scene = _make_scene()
        assert len(scene.body) == 3

    def test_initial_direction_is_right(self) -> None:
        scene = _make_scene()
        assert scene.direction == RIGHT

    def test_initial_score_is_zero(self) -> None:
        scene = _make_scene()
        assert scene.score == 0

    def test_initial_game_over_is_false(self) -> None:
        scene = _make_scene()
        assert scene.game_over is False

    def test_initial_food_is_placed(self) -> None:
        scene = _make_scene()
        assert scene.food is not None

    def test_initial_food_inside_border(self) -> None:
        scene = _make_scene()
        assert scene.food is not None
        fx, fy = scene.food
        assert 1 <= fx <= 28
        assert 1 <= fy <= 18

    def test_initial_head_at_center(self) -> None:
        scene = _make_scene(width=30, height=20)
        hx, hy = scene.head
        assert hx == 15
        assert hy == 10

    def test_initial_body_extends_left_from_head(self) -> None:
        """The initial body should be 3 segments extending left from center."""
        scene = _make_scene(width=30, height=20)
        hx, hy = scene.head
        assert scene.body == [(hx, hy), (hx - 1, hy), (hx - 2, hy)]


# ---------------------------------------------------------------------------
# Direction changes
# ---------------------------------------------------------------------------


class TestSnakeDirection:
    """Arrow key input changes the snake's direction."""

    def test_change_direction_up(self) -> None:
        scene = _make_scene()
        scene.handle_events([KeyEvent(key="up")])
        scene.update(scene._move_interval)
        assert scene.direction == UP

    def test_change_direction_down(self) -> None:
        scene = _make_scene()
        scene.handle_events([KeyEvent(key="down")])
        scene.update(scene._move_interval)
        assert scene.direction == DOWN

    def test_cannot_reverse_direction(self) -> None:
        """Pressing the opposite of the current direction is ignored.

        The snake starts heading right, so pressing left should not
        change the direction.
        """
        scene = _make_scene()
        assert scene.direction == RIGHT
        scene.handle_events([KeyEvent(key="left")])
        scene.update(scene._move_interval)
        # Direction should still be RIGHT — left is the opposite.
        assert scene.direction == RIGHT

    def test_cannot_reverse_after_turning(self) -> None:
        """After turning up, pressing down should be ignored."""
        scene = _make_scene()
        # Turn up.
        scene.handle_events([KeyEvent(key="up")])
        scene.update(scene._move_interval)
        assert scene.direction == UP
        # Try to reverse to down.
        scene.handle_events([KeyEvent(key="down")])
        scene.update(scene._move_interval)
        assert scene.direction == UP

    def test_non_arrow_keys_do_not_change_direction(self) -> None:
        scene = _make_scene()
        scene.handle_events([KeyEvent(key="a")])
        scene.handle_events([KeyEvent(key="w")])
        scene.handle_events([KeyEvent(key="enter")])
        scene.update(scene._move_interval)
        assert scene.direction == RIGHT


# ---------------------------------------------------------------------------
# Movement
# ---------------------------------------------------------------------------


class TestSnakeMovement:
    """Snake movement via the update timer."""

    def test_snake_moves_after_interval(self) -> None:
        scene = _make_scene()
        old_head = scene.head
        scene.update(scene._move_interval)
        # Moving right: head x should increase by 1.
        new_hx, new_hy = scene.head
        assert new_hx == old_head[0] + 1
        assert new_hy == old_head[1]

    def test_snake_does_not_move_before_interval(self) -> None:
        scene = _make_scene()
        old_head = scene.head
        scene.update(scene._move_interval / 2)
        assert scene.head == old_head

    def test_snake_length_stays_constant_without_food(self) -> None:
        """Without eating, the snake's length should not change."""
        scene = _make_scene()
        # Move food off the path to avoid accidental eating.
        scene.food = (1, 1)
        initial_len = len(scene.body)
        scene.update(scene._move_interval)
        assert len(scene.body) == initial_len

    def test_snake_moves_up(self) -> None:
        scene = _make_scene()
        scene.handle_events([KeyEvent(key="up")])
        old_head = scene.head
        scene.update(scene._move_interval)
        assert scene.head == (old_head[0], old_head[1] - 1)

    def test_snake_moves_down(self) -> None:
        scene = _make_scene()
        scene.handle_events([KeyEvent(key="down")])
        old_head = scene.head
        scene.update(scene._move_interval)
        assert scene.head == (old_head[0], old_head[1] + 1)


# ---------------------------------------------------------------------------
# Food & scoring
# ---------------------------------------------------------------------------


class TestSnakeFood:
    """Food placement and eating behaviour."""

    def test_eating_food_increments_score(self) -> None:
        scene = _make_scene()
        # Place food directly in the snake's path (one cell to the right).
        hx, hy = scene.head
        scene.food = (hx + 1, hy)

        scene.update(scene._move_interval)
        assert scene.score == 1

    def test_eating_food_grows_snake(self) -> None:
        scene = _make_scene()
        hx, hy = scene.head
        scene.food = (hx + 1, hy)
        initial_len = len(scene.body)

        scene.update(scene._move_interval)
        assert len(scene.body) == initial_len + 1

    def test_new_food_placed_after_eating(self) -> None:
        scene = _make_scene()
        hx, hy = scene.head
        scene.food = (hx + 1, hy)

        scene.update(scene._move_interval)
        # Food should be re-placed (not None, and not at the old location).
        assert scene.food is not None

    def test_food_not_on_snake(self) -> None:
        """Freshly placed food should not overlap the snake body."""
        scene = _make_scene()
        hx, hy = scene.head
        scene.food = (hx + 1, hy)
        scene.update(scene._move_interval)

        if scene.food is not None:
            assert scene.food not in scene.body


# ---------------------------------------------------------------------------
# Collision / game over
# ---------------------------------------------------------------------------


class TestSnakeCollision:
    """Wall and self collision triggers game over."""

    def test_wall_collision_right(self) -> None:
        """Moving the head into the right border triggers game over."""
        scene = _make_scene(width=30, height=20)
        # Move food out of the way.
        scene.food = (1, 1)
        # Position head one cell from the right border.
        scene.body = [(28, 10), (27, 10), (26, 10)]
        scene.direction = RIGHT
        scene._next_direction = RIGHT

        scene.update(scene._move_interval)
        assert scene.game_over is True

    def test_wall_collision_left(self) -> None:
        scene = _make_scene(width=30, height=20)
        scene.food = (28, 1)
        scene.body = [(1, 10), (2, 10), (3, 10)]
        scene.direction = LEFT
        scene._next_direction = LEFT

        scene.update(scene._move_interval)
        assert scene.game_over is True

    def test_wall_collision_top(self) -> None:
        scene = _make_scene(width=30, height=20)
        scene.food = (1, 18)
        scene.body = [(15, 1), (15, 2), (15, 3)]
        scene.direction = UP
        scene._next_direction = UP

        scene.update(scene._move_interval)
        assert scene.game_over is True

    def test_wall_collision_bottom(self) -> None:
        scene = _make_scene(width=30, height=20)
        scene.food = (1, 1)
        scene.body = [(15, 18), (15, 17), (15, 16)]
        scene.direction = DOWN
        scene._next_direction = DOWN

        scene.update(scene._move_interval)
        assert scene.game_over is True

    def test_self_collision(self) -> None:
        """Moving into the snake's own body triggers game over."""
        scene = _make_scene(width=30, height=20)
        scene.food = (1, 1)
        # Arrange body in a shape where turning right leads into itself.
        # Snake heading up, body wraps around to the right.
        scene.body = [(10, 5), (10, 6), (11, 6), (11, 5), (11, 4)]
        scene.direction = UP
        scene._next_direction = UP

        scene.update(scene._move_interval)
        # New head would be (10, 4) — not in body, so snake is fine.
        # Let's create a real self-collision scenario.
        scene2 = _make_scene(width=30, height=20)
        scene2.food = (1, 1)
        # Head at (10, 5) heading left. Body at (11, 5), (11, 6), (10, 6), (9, 6), (9, 5).
        # Next move left to (9, 5) — which is already in the body.
        scene2.body = [(10, 5), (11, 5), (11, 6), (10, 6), (9, 6), (9, 5)]
        scene2.direction = LEFT
        scene2._next_direction = LEFT

        scene2.update(scene2._move_interval)
        assert scene2.game_over is True

    def test_no_movement_after_game_over(self) -> None:
        """Once game_over is True, update() should not move the snake."""
        scene = _make_scene()
        scene.game_over = True
        old_body = list(scene.body)
        scene.update(scene._move_interval)
        assert scene.body == old_body


# ---------------------------------------------------------------------------
# Restart
# ---------------------------------------------------------------------------


class TestSnakeRestart:
    """Restarting the game after game over."""

    def test_restart_resets_game_over(self) -> None:
        scene = _make_scene()
        scene.game_over = True
        scene.handle_events([KeyEvent(key="r")])
        assert scene.game_over is False

    def test_restart_resets_score(self) -> None:
        scene = _make_scene()
        scene.score = 5
        scene.game_over = True
        scene.handle_events([KeyEvent(key="r")])
        assert scene.score == 0

    def test_restart_resets_snake_length(self) -> None:
        scene = _make_scene()
        scene.game_over = True
        scene.body = [(5, 5)] * 10  # Artificially long snake.
        scene.handle_events([KeyEvent(key="r")])
        assert len(scene.body) == 3

    def test_restart_ignored_when_not_game_over(self) -> None:
        """Pressing r during active gameplay does nothing."""
        scene = _make_scene()
        old_body = list(scene.body)
        scene.handle_events([KeyEvent(key="r")])
        assert scene.body == old_body
        assert scene.game_over is False


# ---------------------------------------------------------------------------
# Event handling — quit
# ---------------------------------------------------------------------------


class TestSnakeEvents:
    """Quit handling via q and Escape."""

    def test_quit_on_q(self) -> None:
        scene = _make_scene()
        with pytest.raises(QuitSignal):
            scene.handle_events([KeyEvent(key="q")])

    def test_quit_on_escape(self) -> None:
        scene = _make_scene()
        with pytest.raises(QuitSignal):
            scene.handle_events([KeyEvent(key="escape")])

    def test_quit_during_game_over(self) -> None:
        """q and Escape should still quit even in game-over state."""
        scene = _make_scene()
        scene.game_over = True
        with pytest.raises(QuitSignal):
            scene.handle_events([KeyEvent(key="q")])

    def test_empty_events_no_raise(self) -> None:
        scene = _make_scene()
        scene.handle_events([])

    def test_non_key_events_ignored(self) -> None:
        scene = _make_scene()
        scene.handle_events(["not a key event"])


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


class TestSnakeRendering:
    """SnakeGameScene.render() writes to the buffer correctly."""

    def test_render_clears_buffer(self) -> None:
        from wyby.grid import Cell

        scene = _make_scene()
        scene.buffer.put(0, 0, Cell(char="X", fg="red"))
        scene.render()
        # The X should be overwritten by the border corner.
        cell = scene.buffer.get(0, 0)
        assert cell is not None
        assert cell.char != "X"

    def test_render_draws_border_corners(self) -> None:
        scene = _make_scene(width=30, height=20)
        scene.render()

        tl = scene.buffer.get(0, 0)
        tr = scene.buffer.get(29, 0)
        bl = scene.buffer.get(0, 19)
        br = scene.buffer.get(29, 19)

        assert tl is not None and tl.char == "\u250c"
        assert tr is not None and tr.char == "\u2510"
        assert bl is not None and bl.char == "\u2514"
        assert br is not None and br.char == "\u2518"

    def test_render_draws_snake_head(self) -> None:
        scene = _make_scene()
        scene.render()

        hx, hy = scene.head
        cell = scene.buffer.get(hx, hy)
        assert cell is not None
        assert cell.char == "@"
        assert cell.fg == "bright_green"
        assert cell.bold is True

    def test_render_draws_snake_body(self) -> None:
        scene = _make_scene()
        scene.render()

        # Check the second segment (first body segment after head).
        bx, by = scene.body[1]
        cell = scene.buffer.get(bx, by)
        assert cell is not None
        assert cell.char == "o"
        assert cell.fg == "bright_green"

    def test_render_draws_food(self) -> None:
        scene = _make_scene()
        scene.food = (5, 5)
        scene.render()

        cell = scene.buffer.get(5, 5)
        assert cell is not None
        assert cell.char == "*"
        assert cell.fg == "bright_red"

    def test_render_draws_score(self) -> None:
        scene = _make_scene()
        scene.score = 7
        scene.render()

        # Score text starts at column 2, row 0: " Score: 7 "
        # Check for the "S" of "Score"
        extracted = ""
        text = " Score: 7 "
        for i in range(len(text)):
            cell = scene.buffer.get(2 + i, 0)
            if cell is not None:
                extracted += cell.char

        assert "Score: 7" in extracted

    def test_render_game_over_message(self) -> None:
        scene = _make_scene(width=30, height=20)
        scene.game_over = True
        scene.render()

        msg = "GAME OVER"
        msg_x = (30 - len(msg)) // 2
        msg_y = 10

        extracted = ""
        for i in range(len(msg)):
            cell = scene.buffer.get(msg_x + i, msg_y)
            assert cell is not None
            extracted += cell.char

        assert extracted == "GAME OVER"

    def test_render_no_game_over_when_playing(self) -> None:
        """GAME OVER text should not appear during active play."""
        scene = _make_scene(width=30, height=20)
        scene.game_over = False
        scene.render()

        msg = "GAME OVER"
        msg_x = (30 - len(msg)) // 2
        msg_y = 10

        extracted = ""
        for i in range(len(msg)):
            cell = scene.buffer.get(msg_x + i, msg_y)
            if cell is not None:
                extracted += cell.char

        assert extracted != "GAME OVER"
