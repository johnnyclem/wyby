"""Tests for the flappy bird game example scene."""

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
from flappy_bird_game import (
    DEFAULT_FLAP_STRENGTH,
    DEFAULT_GRAVITY,
    DEFAULT_MAX_FALL_SPEED,
    DEFAULT_PIPE_GAP,
    DEFAULT_PIPE_SPACING,
    DEFAULT_PIPE_SPEED,
    FlappyBirdScene,
)


# ---------------------------------------------------------------------------
# Helper — deterministic scene with seeded RNG
# ---------------------------------------------------------------------------


def _make_scene(
    width: int = 40,
    height: int = 20,
    gravity: float = DEFAULT_GRAVITY,
    flap_strength: float = DEFAULT_FLAP_STRENGTH,
    max_fall_speed: float = DEFAULT_MAX_FALL_SPEED,
    pipe_speed: float = DEFAULT_PIPE_SPEED,
    pipe_gap: int = DEFAULT_PIPE_GAP,
    pipe_spacing: int = DEFAULT_PIPE_SPACING,
    seed: int = 42,
) -> FlappyBirdScene:
    """Create a FlappyBirdScene with a seeded RNG for reproducible tests."""
    return FlappyBirdScene(
        width=width,
        height=height,
        gravity=gravity,
        flap_strength=flap_strength,
        max_fall_speed=max_fall_speed,
        pipe_speed=pipe_speed,
        pipe_gap=pipe_gap,
        pipe_spacing=pipe_spacing,
        rng=random.Random(seed),
    )


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestFlappyBirdConstruction:
    """FlappyBirdScene initialisation and defaults."""

    def test_default_dimensions(self) -> None:
        scene = _make_scene()
        assert scene.buffer.width == 40
        assert scene.buffer.height == 20

    def test_custom_dimensions(self) -> None:
        scene = _make_scene(width=60, height=30)
        assert scene.buffer.width == 60
        assert scene.buffer.height == 30

    def test_buffer_is_cellbuffer(self) -> None:
        scene = _make_scene()
        assert isinstance(scene.buffer, CellBuffer)

    def test_initial_score_is_zero(self) -> None:
        scene = _make_scene()
        assert scene.score == 0

    def test_initial_game_over_is_false(self) -> None:
        scene = _make_scene()
        assert scene.game_over is False

    def test_initial_started_is_false(self) -> None:
        scene = _make_scene()
        assert scene.started is False

    def test_bird_starts_centred_vertically(self) -> None:
        scene = _make_scene(height=20)
        assert scene._bird_y == 10.0  # height / 2

    def test_bird_starts_at_fixed_x(self) -> None:
        scene = _make_scene()
        assert scene._bird_x == 8

    def test_bird_initial_velocity_is_zero(self) -> None:
        scene = _make_scene()
        assert scene._bird_vy == 0.0

    def test_pipes_are_pre_populated(self) -> None:
        scene = _make_scene()
        assert len(scene.pipes) > 0

    def test_pipes_start_off_screen_right(self) -> None:
        scene = _make_scene(width=40)
        for pipe in scene.pipes:
            assert pipe[0] > 38  # play_right = width - 2


# ---------------------------------------------------------------------------
# Flap input
# ---------------------------------------------------------------------------


class TestFlappyBirdInput:
    """Flap mechanics via keyboard input."""

    def test_space_triggers_flap(self) -> None:
        scene = _make_scene()
        scene.handle_events([KeyEvent(key="space")])
        assert scene._bird_vy == DEFAULT_FLAP_STRENGTH

    def test_up_arrow_triggers_flap(self) -> None:
        scene = _make_scene()
        scene.handle_events([KeyEvent(key="up")])
        assert scene._bird_vy == DEFAULT_FLAP_STRENGTH

    def test_flap_starts_game(self) -> None:
        scene = _make_scene()
        assert scene.started is False
        scene.handle_events([KeyEvent(key="space")])
        assert scene.started is True

    def test_no_flap_during_game_over(self) -> None:
        scene = _make_scene()
        scene.started = True
        scene.game_over = True
        old_vy = scene._bird_vy
        scene.handle_events([KeyEvent(key="space")])
        assert scene._bird_vy == old_vy

    def test_unrelated_keys_do_not_flap(self) -> None:
        scene = _make_scene()
        scene.handle_events([KeyEvent(key="a"), KeyEvent(key="w")])
        assert scene._bird_vy == 0.0
        assert scene.started is False


# ---------------------------------------------------------------------------
# Bird physics
# ---------------------------------------------------------------------------


class TestBirdPhysics:
    """Gravity and velocity in update()."""

    def test_bird_falls_under_gravity(self) -> None:
        scene = _make_scene()
        scene.started = True
        old_y = scene._bird_y
        scene._bird_vy = 0.0
        dt = 1.0 / 30.0
        scene.update(dt)
        # Gravity should increase vy, then y should increase (fall down).
        assert scene._bird_y > old_y

    def test_bird_does_not_move_before_start(self) -> None:
        scene = _make_scene()
        old_y = scene._bird_y
        scene.update(1.0 / 30.0)
        assert scene._bird_y == old_y

    def test_bird_does_not_move_after_game_over(self) -> None:
        scene = _make_scene()
        scene.started = True
        scene.game_over = True
        old_y = scene._bird_y
        scene.update(1.0 / 30.0)
        assert scene._bird_y == old_y

    def test_flap_makes_bird_rise(self) -> None:
        scene = _make_scene()
        scene.started = True
        scene._bird_y = 10.0
        scene._bird_vy = DEFAULT_FLAP_STRENGTH  # Negative = up.
        dt = 1.0 / 30.0
        scene.update(dt)
        # Bird should have moved up (y decreased) despite gravity, because
        # flap_strength is large enough to overcome one tick of gravity.
        assert scene._bird_y < 10.0

    def test_velocity_capped_at_max_fall_speed(self) -> None:
        scene = _make_scene()
        scene.started = True
        scene._bird_vy = DEFAULT_MAX_FALL_SPEED + 10.0
        scene.update(1.0 / 30.0)
        # vy should be capped after gravity is applied.
        assert scene._bird_vy <= DEFAULT_MAX_FALL_SPEED


# ---------------------------------------------------------------------------
# Ceiling / floor collision
# ---------------------------------------------------------------------------


class TestBirdBoundaryCollision:
    """Bird hitting the ceiling or floor triggers game over."""

    def test_floor_collision(self) -> None:
        scene = _make_scene(height=20)
        scene.started = True
        # Place bird near the floor.
        scene._bird_y = 17.5
        scene._bird_vy = 50.0  # Falling fast.
        # Remove pipes so they don't interfere.
        scene.pipes = []
        scene.update(1.0 / 30.0)
        assert scene.game_over is True

    def test_ceiling_collision(self) -> None:
        scene = _make_scene(height=20)
        scene.started = True
        # Place bird near the ceiling.
        scene._bird_y = 1.5
        scene._bird_vy = -50.0  # Moving up fast.
        scene.pipes = []
        scene.update(1.0 / 30.0)
        assert scene.game_over is True

    def test_no_collision_in_middle(self) -> None:
        scene = _make_scene(height=20)
        scene.started = True
        scene._bird_y = 10.0
        scene._bird_vy = 0.0
        scene.pipes = []
        scene.update(1.0 / 30.0)
        assert scene.game_over is False


# ---------------------------------------------------------------------------
# Pipe collision
# ---------------------------------------------------------------------------


class TestPipeCollision:
    """Bird hitting a pipe triggers game over."""

    def test_collision_above_gap(self) -> None:
        """Bird above the gap in a pipe column should trigger game over."""
        scene = _make_scene(pipe_gap=6)
        scene.started = True
        # Place a pipe exactly at the bird's column.
        gap_y = 10
        scene.pipes = [[float(scene._bird_x), gap_y]]
        # Bird is above the gap.
        scene._bird_y = float(gap_y - 2)
        scene._bird_vy = 0.0
        scene.update(1.0 / 30.0)
        assert scene.game_over is True

    def test_collision_below_gap(self) -> None:
        """Bird below the gap in a pipe column should trigger game over."""
        scene = _make_scene(pipe_gap=6)
        scene.started = True
        gap_y = 5
        scene.pipes = [[float(scene._bird_x), gap_y]]
        # Bird is below the gap (gap ends at gap_y + pipe_gap - 1 = 10).
        scene._bird_y = float(gap_y + 6 + 1)
        scene._bird_vy = 0.0
        scene.update(1.0 / 30.0)
        assert scene.game_over is True

    def test_no_collision_inside_gap(self) -> None:
        """Bird inside the gap should NOT trigger game over."""
        scene = _make_scene(pipe_gap=6)
        scene.started = True
        gap_y = 7
        scene.pipes = [[float(scene._bird_x), gap_y]]
        # Bird is inside the gap.
        scene._bird_y = float(gap_y + 3)
        scene._bird_vy = 0.0
        scene.update(1.0 / 30.0)
        assert scene.game_over is False

    def test_no_collision_when_pipe_not_at_bird_column(self) -> None:
        """Bird should not collide with pipes in other columns."""
        scene = _make_scene(pipe_gap=6)
        scene.started = True
        # Pipe is well to the right of the bird.
        scene.pipes = [[float(scene._bird_x + 10), 5]]
        scene._bird_y = 3.0  # Would be in the pipe column above the gap.
        scene._bird_vy = 0.0
        scene.update(1.0 / 30.0)
        assert scene.game_over is False


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


class TestFlappyBirdScoring:
    """Score increments when bird passes a pipe."""

    def test_score_increments_when_pipe_passes_bird(self) -> None:
        scene = _make_scene(pipe_speed=100.0, pipe_gap=6)
        scene.started = True
        # Place bird safely in the middle.
        scene._bird_y = 10.0
        scene._bird_vy = 0.0
        # Place a pipe just ahead of the bird — it will scroll past.
        scene.pipes = [[float(scene._bird_x + 1), 7]]
        # Large dt so pipe scrolls past the bird.
        scene.update(0.1)
        assert scene.score == 1

    def test_score_does_not_double_count(self) -> None:
        """A pipe that has already been scored should not score again."""
        scene = _make_scene(pipe_speed=10.0, pipe_gap=6)
        scene.started = True
        scene._bird_y = 10.0
        scene._bird_vy = 0.0
        # Pipe already past the bird with "passed" flag set.
        scene.pipes = [[float(scene._bird_x - 5), 7, 1]]
        old_score = scene.score
        scene.update(1.0 / 30.0)
        assert scene.score == old_score

    def test_multiple_pipes_can_score(self) -> None:
        scene = _make_scene(pipe_speed=200.0, pipe_gap=6)
        scene.started = True
        scene._bird_y = 10.0
        scene._bird_vy = 0.0
        # Two pipes just ahead of the bird.
        scene.pipes = [
            [float(scene._bird_x + 1), 7],
            [float(scene._bird_x + 2), 7],
        ]
        # Large dt so both scroll past.
        scene.update(0.1)
        assert scene.score == 2


# ---------------------------------------------------------------------------
# Pipe management
# ---------------------------------------------------------------------------


class TestPipeManagement:
    """Pipe spawning and removal."""

    def test_pipes_removed_when_off_screen(self) -> None:
        scene = _make_scene(pipe_speed=200.0)
        scene.started = True
        scene._bird_y = 10.0
        scene._bird_vy = 0.0
        # Place a pipe at the far left — should be removed after update.
        scene.pipes = [[0.0, 7, 1]]
        scene.update(0.1)
        # The original pipe at x=0 should have been removed.
        old_pipes_at_zero = [p for p in scene.pipes if p[0] <= 0]
        assert len(old_pipes_at_zero) == 0

    def test_new_pipes_spawned_as_needed(self) -> None:
        scene = _make_scene()
        scene.started = True
        scene._bird_y = 10.0
        scene._bird_vy = 0.0
        # Clear all pipes.
        scene.pipes = []
        scene.update(1.0 / 30.0)
        # At least one pipe should have been spawned.
        assert len(scene.pipes) >= 1

    def test_gap_within_playable_area(self) -> None:
        """All generated pipe gaps should fit within the playable area."""
        scene = _make_scene(height=20, pipe_gap=6)
        for pipe in scene.pipes:
            gap_y = int(pipe[1])
            assert gap_y >= scene._play_top + 1
            assert gap_y + scene._pipe_gap - 1 <= scene._play_bottom


# ---------------------------------------------------------------------------
# Restart
# ---------------------------------------------------------------------------


class TestFlappyBirdRestart:
    """Restarting the game after game over."""

    def test_restart_resets_game_over(self) -> None:
        scene = _make_scene()
        scene.game_over = True
        scene.handle_events([KeyEvent(key="r")])
        assert scene.game_over is False

    def test_restart_resets_score(self) -> None:
        scene = _make_scene()
        scene.score = 10
        scene.game_over = True
        scene.handle_events([KeyEvent(key="r")])
        assert scene.score == 0

    def test_restart_resets_started(self) -> None:
        scene = _make_scene()
        scene.started = True
        scene.game_over = True
        scene.handle_events([KeyEvent(key="r")])
        assert scene.started is False

    def test_restart_resets_bird_position(self) -> None:
        scene = _make_scene(height=20)
        scene.game_over = True
        scene._bird_y = 2.0
        scene.handle_events([KeyEvent(key="r")])
        assert scene._bird_y == 10.0  # height / 2

    def test_restart_resets_bird_velocity(self) -> None:
        scene = _make_scene()
        scene.game_over = True
        scene._bird_vy = 15.0
        scene.handle_events([KeyEvent(key="r")])
        assert scene._bird_vy == 0.0

    def test_restart_ignored_when_not_game_over(self) -> None:
        scene = _make_scene()
        old_score = scene.score
        scene.handle_events([KeyEvent(key="r")])
        assert scene.score == old_score
        assert scene.game_over is False


# ---------------------------------------------------------------------------
# Event handling — quit
# ---------------------------------------------------------------------------


class TestFlappyBirdEvents:
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


class TestFlappyBirdRendering:
    """FlappyBirdScene.render() writes to the buffer correctly."""

    def test_render_clears_buffer(self) -> None:
        from wyby.grid import Cell

        scene = _make_scene()
        scene.buffer.put(5, 5, Cell(char="X", fg="red"))
        scene.render()
        cell = scene.buffer.get(5, 5)
        assert cell is not None
        assert cell.char != "X"

    def test_render_draws_border_corners(self) -> None:
        scene = _make_scene(width=40, height=20)
        scene.render()

        tl = scene.buffer.get(0, 0)
        tr = scene.buffer.get(39, 0)
        bl = scene.buffer.get(0, 19)
        br = scene.buffer.get(39, 19)

        assert tl is not None and tl.char == "\u250c"
        assert tr is not None and tr.char == "\u2510"
        assert bl is not None and bl.char == "\u2514"
        assert br is not None and br.char == "\u2518"

    def test_render_draws_bird(self) -> None:
        scene = _make_scene()
        scene._bird_y = 10.0
        scene.render()

        cell = scene.buffer.get(scene._bird_x, 10)
        assert cell is not None
        assert cell.char == "\u25c6"
        assert cell.fg == "bright_yellow"
        assert cell.bold is True

    def test_render_draws_pipe(self) -> None:
        scene = _make_scene(pipe_gap=6)
        # Place a pipe inside the visible area.
        scene.pipes = [[20.0, 7]]
        scene.render()

        # Check a cell above the gap — should be pipe.
        cell_above = scene.buffer.get(20, 3)
        assert cell_above is not None
        assert cell_above.char in ("\u2588", "\u2584")  # PIPE_CHAR or PIPE_CAP

        # Check a cell inside the gap — should be empty (space).
        cell_gap = scene.buffer.get(20, 9)
        assert cell_gap is not None
        assert cell_gap.char == " "

        # Check a cell below the gap — should be pipe.
        cell_below = scene.buffer.get(20, 15)
        assert cell_below is not None
        assert cell_below.char in ("\u2588", "\u2584")

    def test_render_draws_score(self) -> None:
        scene = _make_scene()
        scene.score = 5
        scene.render()

        text = " Score: 5 "
        extracted = ""
        for i in range(len(text)):
            cell = scene.buffer.get(2 + i, 0)
            if cell is not None:
                extracted += cell.char

        assert "Score: 5" in extracted

    def test_render_game_over_message(self) -> None:
        scene = _make_scene(width=40, height=20)
        scene.game_over = True
        scene.render()

        msg = "GAME OVER"
        msg_x = (40 - len(msg)) // 2
        msg_y = 10  # height // 2

        extracted = ""
        for i in range(len(msg)):
            cell = scene.buffer.get(msg_x + i, msg_y)
            assert cell is not None
            extracted += cell.char

        assert extracted == "GAME OVER"

    def test_render_no_game_over_when_playing(self) -> None:
        scene = _make_scene(width=40, height=20)
        scene.game_over = False
        scene.render()

        msg = "GAME OVER"
        msg_x = (40 - len(msg)) // 2
        msg_y = 10

        extracted = ""
        for i in range(len(msg)):
            cell = scene.buffer.get(msg_x + i, msg_y)
            if cell is not None:
                extracted += cell.char

        assert extracted != "GAME OVER"

    def test_render_start_prompt_before_start(self) -> None:
        scene = _make_scene(width=40, height=20)
        scene.started = False
        scene.game_over = False
        scene.render()

        msg = "Press SPACE to start"
        msg_x = (40 - len(msg)) // 2
        msg_y = 12  # height // 2 + 2

        extracted = ""
        for i in range(len(msg)):
            cell = scene.buffer.get(msg_x + i, msg_y)
            if cell is not None:
                extracted += cell.char

        assert extracted == "Press SPACE to start"

    def test_render_no_start_prompt_after_start(self) -> None:
        scene = _make_scene(width=40, height=20)
        scene.started = True
        scene.game_over = False
        scene.render()

        msg = "Press SPACE to start"
        msg_x = (40 - len(msg)) // 2
        msg_y = 12

        extracted = ""
        for i in range(len(msg)):
            cell = scene.buffer.get(msg_x + i, msg_y)
            if cell is not None:
                extracted += cell.char

        assert extracted != "Press SPACE to start"
