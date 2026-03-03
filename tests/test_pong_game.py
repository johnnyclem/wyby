"""Tests for the pong game example scene."""

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
from pong_game import (
    PADDLE_SPEED,
    PongScene,
)


# ---------------------------------------------------------------------------
# Helper — deterministic scene with seeded RNG
# ---------------------------------------------------------------------------


def _make_scene(
    width: int = 60,
    height: int = 24,
    paddle_height: int = 5,
    winning_score: int = 5,
    ball_speed_x: float = 20.0,
    ball_speed_y: float = 12.0,
    seed: int = 42,
) -> PongScene:
    """Create a PongScene with a seeded RNG for reproducible tests."""
    return PongScene(
        width=width,
        height=height,
        paddle_height=paddle_height,
        winning_score=winning_score,
        ball_speed_x=ball_speed_x,
        ball_speed_y=ball_speed_y,
        rng=random.Random(seed),
    )


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestPongSceneConstruction:
    """PongScene initialisation and defaults."""

    def test_default_dimensions(self) -> None:
        scene = _make_scene()
        assert scene.buffer.width == 60
        assert scene.buffer.height == 24

    def test_custom_dimensions(self) -> None:
        scene = _make_scene(width=80, height=30)
        assert scene.buffer.width == 80
        assert scene.buffer.height == 30

    def test_buffer_is_cellbuffer(self) -> None:
        scene = _make_scene()
        assert isinstance(scene.buffer, CellBuffer)

    def test_initial_scores_are_zero(self) -> None:
        scene = _make_scene()
        assert scene.score_p1 == 0
        assert scene.score_p2 == 0

    def test_initial_game_over_is_false(self) -> None:
        scene = _make_scene()
        assert scene.game_over is False

    def test_initial_winner_is_zero(self) -> None:
        scene = _make_scene()
        assert scene.winner == 0

    def test_paddles_start_centred(self) -> None:
        scene = _make_scene(width=60, height=24, paddle_height=5)
        centre_y = 24 // 2
        expected_top = centre_y - 5 // 2
        assert scene._p1_y == expected_top
        assert scene._p2_y == expected_top

    def test_paddle_x_positions(self) -> None:
        scene = _make_scene(width=60)
        assert scene._p1_x == 2
        assert scene._p2_x == 57  # width - 3

    def test_ball_starts_at_centre(self) -> None:
        scene = _make_scene(width=60, height=24)
        assert scene._ball_x == 30.0  # width / 2
        assert scene._ball_y == 12.0  # height / 2

    def test_ball_has_velocity(self) -> None:
        scene = _make_scene()
        assert scene._ball_vx != 0
        assert scene._ball_vy != 0


# ---------------------------------------------------------------------------
# Paddle movement
# ---------------------------------------------------------------------------


class TestPaddleMovement:
    """Paddle movement via keyboard input."""

    def test_p1_moves_up_with_w(self) -> None:
        scene = _make_scene()
        old_y = scene._p1_y
        scene.handle_events([KeyEvent(key="w")])
        assert scene._p1_y == old_y - PADDLE_SPEED

    def test_p1_moves_down_with_s(self) -> None:
        scene = _make_scene()
        old_y = scene._p1_y
        scene.handle_events([KeyEvent(key="s")])
        assert scene._p1_y == old_y + PADDLE_SPEED

    def test_p2_moves_up_with_arrow(self) -> None:
        scene = _make_scene()
        old_y = scene._p2_y
        scene.handle_events([KeyEvent(key="up")])
        assert scene._p2_y == old_y - PADDLE_SPEED

    def test_p2_moves_down_with_arrow(self) -> None:
        scene = _make_scene()
        old_y = scene._p2_y
        scene.handle_events([KeyEvent(key="down")])
        assert scene._p2_y == old_y + PADDLE_SPEED

    def test_p1_clamped_at_top(self) -> None:
        scene = _make_scene()
        scene._p1_y = 1  # At top border.
        scene.handle_events([KeyEvent(key="w")])
        assert scene._p1_y == 1  # Should not go above.

    def test_p1_clamped_at_bottom(self) -> None:
        scene = _make_scene(height=24, paddle_height=5)
        # Bottom of playable area is row 22 (height - 2).
        # Paddle top can be at most 22 - 5 + 1 = 18.
        scene._p1_y = 18
        scene.handle_events([KeyEvent(key="s")])
        assert scene._p1_y == 18

    def test_p2_clamped_at_top(self) -> None:
        scene = _make_scene()
        scene._p2_y = 1
        scene.handle_events([KeyEvent(key="up")])
        assert scene._p2_y == 1

    def test_p2_clamped_at_bottom(self) -> None:
        scene = _make_scene(height=24, paddle_height=5)
        scene._p2_y = 18
        scene.handle_events([KeyEvent(key="down")])
        assert scene._p2_y == 18

    def test_no_movement_during_game_over(self) -> None:
        scene = _make_scene()
        scene.game_over = True
        old_p1_y = scene._p1_y
        old_p2_y = scene._p2_y
        scene.handle_events([KeyEvent(key="w"), KeyEvent(key="up")])
        assert scene._p1_y == old_p1_y
        assert scene._p2_y == old_p2_y

    def test_unrelated_keys_do_not_move_paddles(self) -> None:
        scene = _make_scene()
        old_p1_y = scene._p1_y
        old_p2_y = scene._p2_y
        scene.handle_events([KeyEvent(key="a"), KeyEvent(key="enter")])
        assert scene._p1_y == old_p1_y
        assert scene._p2_y == old_p2_y


# ---------------------------------------------------------------------------
# Ball movement
# ---------------------------------------------------------------------------


class TestBallMovement:
    """Ball physics in update()."""

    def test_ball_moves_on_update(self) -> None:
        scene = _make_scene()
        old_x = scene._ball_x
        old_y = scene._ball_y
        dt = 1.0 / 30.0
        scene.update(dt)
        assert scene._ball_x != old_x or scene._ball_y != old_y

    def test_ball_moves_in_velocity_direction(self) -> None:
        scene = _make_scene()
        scene._ball_vx = 20.0
        scene._ball_vy = 0.0
        old_x = scene._ball_x
        scene.update(1.0 / 30.0)
        assert scene._ball_x > old_x

    def test_ball_does_not_move_when_game_over(self) -> None:
        scene = _make_scene()
        scene.game_over = True
        old_x = scene._ball_x
        old_y = scene._ball_y
        scene.update(1.0 / 30.0)
        assert scene._ball_x == old_x
        assert scene._ball_y == old_y


# ---------------------------------------------------------------------------
# Wall collision
# ---------------------------------------------------------------------------


class TestWallCollision:
    """Ball bouncing off top and bottom walls."""

    def test_ball_bounces_off_top_wall(self) -> None:
        scene = _make_scene()
        # Position ball near top, moving up.
        scene._ball_x = 30.0
        scene._ball_y = 1.1
        scene._ball_vx = 20.0
        scene._ball_vy = -12.0
        scene.update(1.0 / 30.0)
        # After bouncing, vy should be positive.
        assert scene._ball_vy > 0

    def test_ball_bounces_off_bottom_wall(self) -> None:
        scene = _make_scene(height=24)
        # Position ball near bottom, moving down.
        scene._ball_x = 30.0
        scene._ball_y = 21.9  # play_bottom = 22
        scene._ball_vx = 20.0
        scene._ball_vy = 12.0
        scene.update(1.0 / 30.0)
        # After bouncing, vy should be negative.
        assert scene._ball_vy < 0

    def test_ball_clamped_to_top_boundary(self) -> None:
        scene = _make_scene()
        scene._ball_x = 30.0
        scene._ball_y = 0.5  # Below top border.
        scene._ball_vx = 20.0
        scene._ball_vy = -50.0  # Fast enough to overshoot.
        scene.update(1.0 / 30.0)
        assert scene._ball_y >= scene._play_top

    def test_ball_clamped_to_bottom_boundary(self) -> None:
        scene = _make_scene(height=24)
        scene._ball_x = 30.0
        scene._ball_y = 21.5
        scene._ball_vx = 20.0
        scene._ball_vy = 50.0
        scene.update(1.0 / 30.0)
        assert scene._ball_y <= scene._play_bottom


# ---------------------------------------------------------------------------
# Paddle collision
# ---------------------------------------------------------------------------


class TestPaddleCollision:
    """Ball bouncing off paddles."""

    def test_ball_bounces_off_p1_paddle(self) -> None:
        scene = _make_scene()
        # Place ball exactly at P1's paddle.
        scene._ball_x = float(scene._p1_x) + 0.3
        scene._ball_y = float(scene._p1_y + 2)  # Middle of paddle.
        scene._ball_vx = -20.0  # Moving toward P1.
        scene._ball_vy = 0.0
        scene.update(1.0 / 30.0)
        # After collision, ball should be moving right.
        assert scene._ball_vx > 0

    def test_ball_bounces_off_p2_paddle(self) -> None:
        scene = _make_scene()
        # Place ball exactly at P2's paddle.
        scene._ball_x = float(scene._p2_x) - 0.3
        scene._ball_y = float(scene._p2_y + 2)  # Middle of paddle.
        scene._ball_vx = 20.0  # Moving toward P2.
        scene._ball_vy = 0.0
        scene.update(1.0 / 30.0)
        # After collision, ball should be moving left.
        assert scene._ball_vx < 0

    def test_ball_misses_paddle_above(self) -> None:
        """Ball passing above a paddle should not bounce."""
        scene = _make_scene()
        scene._ball_x = float(scene._p1_x) + 0.3
        scene._ball_y = float(scene._p1_y - 2)  # Above paddle.
        scene._ball_vx = -20.0
        scene._ball_vy = 0.0
        scene.update(1.0 / 30.0)
        # Ball should still be moving left (no bounce).
        assert scene._ball_vx < 0

    def test_ball_misses_paddle_below(self) -> None:
        """Ball passing below a paddle should not bounce."""
        scene = _make_scene(paddle_height=5)
        scene._ball_x = float(scene._p1_x) + 0.3
        scene._ball_y = float(scene._p1_y + 7)  # Below paddle.
        scene._ball_vx = -20.0
        scene._ball_vy = 0.0
        scene.update(1.0 / 30.0)
        assert scene._ball_vx < 0


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


class TestScoring:
    """Scoring when ball passes a paddle."""

    def test_p2_scores_when_ball_passes_left(self) -> None:
        scene = _make_scene()
        # Position ball at left edge, moving left.
        scene._ball_x = 1.5
        scene._ball_y = 12.0
        scene._ball_vx = -60.0  # Fast enough to pass in one frame.
        scene._ball_vy = 0.0
        scene.update(1.0 / 30.0)
        assert scene.score_p2 == 1

    def test_p1_scores_when_ball_passes_right(self) -> None:
        scene = _make_scene(width=60)
        # Position ball at right edge, moving right.
        scene._ball_x = 57.5
        scene._ball_y = 12.0
        scene._ball_vx = 60.0
        scene._ball_vy = 0.0
        scene.update(1.0 / 30.0)
        assert scene.score_p1 == 1

    def test_ball_resets_after_p2_scores(self) -> None:
        scene = _make_scene()
        scene._ball_x = 1.5
        scene._ball_y = 12.0
        scene._ball_vx = -60.0
        scene._ball_vy = 0.0
        scene.update(1.0 / 30.0)
        # Ball should be back near centre.
        assert abs(scene._ball_x - scene._width / 2.0) < 1.0

    def test_ball_resets_after_p1_scores(self) -> None:
        scene = _make_scene(width=60)
        scene._ball_x = 57.5
        scene._ball_y = 12.0
        scene._ball_vx = 60.0
        scene._ball_vy = 0.0
        scene.update(1.0 / 30.0)
        assert abs(scene._ball_x - scene._width / 2.0) < 1.0

    def test_serve_direction_after_p2_scores(self) -> None:
        """After P2 scores, ball should serve right (toward P2)."""
        scene = _make_scene()
        scene._ball_x = 1.5
        scene._ball_y = 12.0
        scene._ball_vx = -60.0
        scene._ball_vy = 0.0
        scene.update(1.0 / 30.0)
        # Serve toward P2 means vx > 0.
        assert scene._ball_vx > 0

    def test_serve_direction_after_p1_scores(self) -> None:
        """After P1 scores, ball should serve left (toward P1)."""
        scene = _make_scene(width=60)
        scene._ball_x = 57.5
        scene._ball_y = 12.0
        scene._ball_vx = 60.0
        scene._ball_vy = 0.0
        scene.update(1.0 / 30.0)
        # Serve toward P1 means vx < 0.
        assert scene._ball_vx < 0


# ---------------------------------------------------------------------------
# Game over
# ---------------------------------------------------------------------------


class TestGameOver:
    """Winning condition triggers game over."""

    def test_p2_wins_at_winning_score(self) -> None:
        scene = _make_scene(winning_score=5)
        scene.score_p2 = 4  # One away from winning.
        scene._ball_x = 1.5
        scene._ball_y = 12.0
        scene._ball_vx = -60.0
        scene._ball_vy = 0.0
        scene.update(1.0 / 30.0)
        assert scene.game_over is True
        assert scene.winner == 2

    def test_p1_wins_at_winning_score(self) -> None:
        scene = _make_scene(width=60, winning_score=5)
        scene.score_p1 = 4
        scene._ball_x = 57.5
        scene._ball_y = 12.0
        scene._ball_vx = 60.0
        scene._ball_vy = 0.0
        scene.update(1.0 / 30.0)
        assert scene.game_over is True
        assert scene.winner == 1

    def test_no_game_over_before_winning_score(self) -> None:
        scene = _make_scene(winning_score=5)
        scene.score_p2 = 3
        scene._ball_x = 1.5
        scene._ball_y = 12.0
        scene._ball_vx = -60.0
        scene._ball_vy = 0.0
        scene.update(1.0 / 30.0)
        assert scene.game_over is False

    def test_no_ball_movement_after_game_over(self) -> None:
        scene = _make_scene()
        scene.game_over = True
        old_x = scene._ball_x
        old_y = scene._ball_y
        scene.update(1.0 / 30.0)
        assert scene._ball_x == old_x
        assert scene._ball_y == old_y


# ---------------------------------------------------------------------------
# Restart
# ---------------------------------------------------------------------------


class TestPongRestart:
    """Restarting the game after game over."""

    def test_restart_resets_game_over(self) -> None:
        scene = _make_scene()
        scene.game_over = True
        scene.handle_events([KeyEvent(key="r")])
        assert scene.game_over is False

    def test_restart_resets_scores(self) -> None:
        scene = _make_scene()
        scene.score_p1 = 3
        scene.score_p2 = 4
        scene.game_over = True
        scene.handle_events([KeyEvent(key="r")])
        assert scene.score_p1 == 0
        assert scene.score_p2 == 0

    def test_restart_resets_winner(self) -> None:
        scene = _make_scene()
        scene.game_over = True
        scene.winner = 2
        scene.handle_events([KeyEvent(key="r")])
        assert scene.winner == 0

    def test_restart_resets_paddle_positions(self) -> None:
        scene = _make_scene(height=24, paddle_height=5)
        scene.game_over = True
        scene._p1_y = 1
        scene._p2_y = 18
        scene.handle_events([KeyEvent(key="r")])
        centre_y = 24 // 2
        expected_top = centre_y - 5 // 2
        assert scene._p1_y == expected_top
        assert scene._p2_y == expected_top

    def test_restart_ignored_when_not_game_over(self) -> None:
        scene = _make_scene()
        old_p1_score = scene.score_p1
        scene.handle_events([KeyEvent(key="r")])
        assert scene.score_p1 == old_p1_score
        assert scene.game_over is False


# ---------------------------------------------------------------------------
# Event handling — quit
# ---------------------------------------------------------------------------


class TestPongEvents:
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


class TestPongRendering:
    """PongScene.render() writes to the buffer correctly."""

    def test_render_clears_buffer(self) -> None:
        from wyby.grid import Cell

        scene = _make_scene()
        scene.buffer.put(5, 5, Cell(char="X", fg="red"))
        scene.render()
        cell = scene.buffer.get(5, 5)
        # Should be overwritten by something (not X).
        assert cell is not None
        assert cell.char != "X"

    def test_render_draws_border_corners(self) -> None:
        scene = _make_scene(width=60, height=24)
        scene.render()

        tl = scene.buffer.get(0, 0)
        tr = scene.buffer.get(59, 0)
        bl = scene.buffer.get(0, 23)
        br = scene.buffer.get(59, 23)

        assert tl is not None and tl.char == "\u250c"
        assert tr is not None and tr.char == "\u2510"
        assert bl is not None and bl.char == "\u2514"
        assert br is not None and br.char == "\u2518"

    def test_render_draws_p1_paddle(self) -> None:
        scene = _make_scene(paddle_height=5)
        scene.render()

        # Check that paddle cells are drawn.
        for dy in range(5):
            cell = scene.buffer.get(scene._p1_x, scene._p1_y + dy)
            assert cell is not None
            assert cell.char == "\u2588"
            assert cell.fg == "bright_white"

    def test_render_draws_p2_paddle(self) -> None:
        scene = _make_scene(paddle_height=5)
        scene.render()

        for dy in range(5):
            cell = scene.buffer.get(scene._p2_x, scene._p2_y + dy)
            assert cell is not None
            assert cell.char == "\u2588"
            assert cell.fg == "bright_white"

    def test_render_draws_ball(self) -> None:
        scene = _make_scene()
        # Place ball at a known position.
        scene._ball_x = 20.0
        scene._ball_y = 10.0
        scene.render()

        cell = scene.buffer.get(20, 10)
        assert cell is not None
        assert cell.char == "\u25cf"
        assert cell.fg == "bright_yellow"
        assert cell.bold is True

    def test_render_draws_centre_net(self) -> None:
        scene = _make_scene(width=60, height=24)
        scene.render()

        net_x = 30  # width // 2
        # Net is drawn on even rows only.
        net_cell = scene.buffer.get(net_x, 2)
        assert net_cell is not None
        assert net_cell.char == "\u2502"

        # Odd row should not have net char (unless paddle/ball there).
        odd_cell = scene.buffer.get(net_x, 3)
        # The cell at an odd row should be blank (space).
        assert odd_cell is not None
        assert odd_cell.char == " "

    def test_render_draws_scores(self) -> None:
        scene = _make_scene(width=60)
        scene.score_p1 = 3
        scene.score_p2 = 2
        scene.render()

        # Extract score text from row 0.
        score_text = f" {scene.score_p1}  |  {scene.score_p2} "
        score_x = (60 - len(score_text)) // 2
        extracted = ""
        for i in range(len(score_text)):
            cell = scene.buffer.get(score_x + i, 0)
            if cell is not None:
                extracted += cell.char
        assert "3" in extracted
        assert "2" in extracted

    def test_render_game_over_message(self) -> None:
        scene = _make_scene(width=60, height=24)
        scene.game_over = True
        scene.winner = 1
        scene.render()

        msg = "PLAYER 1 WINS!"
        msg_x = (60 - len(msg)) // 2
        msg_y = 12  # height // 2

        extracted = ""
        for i in range(len(msg)):
            cell = scene.buffer.get(msg_x + i, msg_y)
            assert cell is not None
            extracted += cell.char

        assert extracted == "PLAYER 1 WINS!"

    def test_render_no_game_over_when_playing(self) -> None:
        scene = _make_scene(width=60, height=24)
        scene.game_over = False
        scene.render()

        msg = "PLAYER 1 WINS!"
        msg_x = (60 - len(msg)) // 2
        msg_y = 12

        extracted = ""
        for i in range(len(msg)):
            cell = scene.buffer.get(msg_x + i, msg_y)
            if cell is not None:
                extracted += cell.char

        assert extracted != "PLAYER 1 WINS!"
