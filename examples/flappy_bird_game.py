"""Example: Flappy Bird clone in the terminal.

A single-player Flappy Bird game demonstrating wyby's game loop, input
handling, gravity physics, and cell buffer rendering.  The bird falls
under gravity; press ``Space`` or ``Up`` to flap.  Navigate through
gaps in scrolling pipes to score points.

Run this example::

    python examples/flappy_bird_game.py

Caveats:
    - This example requires a real terminal (TTY) for keyboard input.
      It will not work when stdin is piped or in CI environments
      without a TTY.  Press ``q`` or ``Escape`` to quit at any time,
      or use Ctrl+C.
    - The bird uses float-precision Y position and velocity internally,
      but rendering snaps to integer cell coordinates each frame.
      At low gravity or flap strength this can make movement look
      jerky — the default values are tuned to feel smooth at 30 TPS.
    - Terminal cells are roughly 1:2 aspect ratio (taller than wide).
      Vertical movement (the bird falling/flapping) appears roughly
      twice as fast visually as horizontal movement (pipes scrolling).
      No aspect-ratio correction is applied — this is a common
      trade-off in terminal games.
    - Pipe gaps are generated at random Y positions within the playable
      area.  The gap height is fixed and does not decrease over time —
      this is a minimal implementation with no difficulty scaling.
    - Collision detection checks the bird's integer position against
      pipe columns and gap ranges.  At very high pipe speeds (or very
      low tick rates), a pipe could skip past the bird in a single
      frame.  The default speed and 30 TPS avoid this.
    - The bird does not start falling until the first flap.  Before
      the first input, the bird hovers at its starting position and
      pipes do not scroll.  This gives the player time to orient.
    - The game-over state is handled with a simple flag — the scene
      stops processing physics but continues rendering.  Press ``r``
      to restart or ``q``/Escape to quit.
    - The buffer is cleared and fully redrawn every frame.  wyby does
      not perform dirty-region tracking.
    - AltScreen is not used here for simplicity.  In a real game,
      wrap the run loop in ``with AltScreen():`` to restore the
      terminal buffer on exit.
    - Pipe spacing is fixed (every ``pipe_spacing`` columns).  Pipes
      are stored as a list of ``(x, gap_y)`` tuples and removed once
      they scroll off the left edge.  New pipes are appended on the
      right as needed.
    - The bird occupies a single cell.  There is no animation or
      sprite variation — the character is always the same regardless
      of whether the bird is ascending or descending.
"""

from __future__ import annotations

import random

from wyby.app import Engine, QuitSignal
from wyby.grid import CellBuffer
from wyby.input import KeyEvent
from wyby.scene import Scene


# Physics constants (cells per second / cells per second^2).
DEFAULT_GRAVITY = 30.0
DEFAULT_FLAP_STRENGTH = -12.0
DEFAULT_MAX_FALL_SPEED = 20.0

# Pipe constants.
DEFAULT_PIPE_SPEED = 10.0
DEFAULT_PIPE_GAP = 6
DEFAULT_PIPE_SPACING = 15


class FlappyBirdScene(Scene):
    """A Flappy Bird clone scene.

    The bird sits at a fixed X column and falls under gravity.
    Pressing ``Space`` or ``Up`` gives the bird an upward velocity
    impulse ("flap").  Pipes scroll from right to left with gaps
    the bird must fly through.  Passing a pipe scores one point.
    Hitting a pipe, the ceiling, or the floor ends the game.

    Args:
        width: Buffer width in character columns.
        height: Buffer height in character rows.
        gravity: Downward acceleration in cells/sec².
        flap_strength: Upward velocity impulse on flap (negative = up).
        max_fall_speed: Terminal velocity cap in cells/sec.
        pipe_speed: Horizontal pipe scroll speed in cells/sec.
        pipe_gap: Height of the gap in each pipe (in cells).
        pipe_spacing: Horizontal distance between pipes (in columns).

    Caveats:
        - The playable area is the interior of the border: columns
          1 to ``width - 2``, rows 1 to ``height - 2``.  The border
          itself occupies the outermost ring of cells.
        - ``gravity`` and ``flap_strength`` are tuned for a 24-row
          buffer at 30 TPS.  Changing the buffer height without
          adjusting physics will affect difficulty.
        - ``pipe_gap`` should be at least 3 to be playable.  Values
          below 3 make it nearly impossible to navigate.
        - The bird's X position is fixed at column 8 (inside the
          border).  This is a design choice — the original Flappy Bird
          also keeps the bird at a fixed horizontal position while
          the world scrolls past.
    """

    BORDER_H = "\u2500"  # ─
    BORDER_V = "\u2502"  # │
    CORNER_TL = "\u250c"  # ┌
    CORNER_TR = "\u2510"  # ┐
    CORNER_BL = "\u2514"  # └
    CORNER_BR = "\u2518"  # ┘

    BIRD_CHAR = "\u25c6"  # ◆
    PIPE_CHAR = "\u2588"  # █
    PIPE_CAP = "\u2584"  # ▄ (cap at the edge of gap)

    def __init__(
        self,
        width: int = 40,
        height: int = 20,
        gravity: float = DEFAULT_GRAVITY,
        flap_strength: float = DEFAULT_FLAP_STRENGTH,
        max_fall_speed: float = DEFAULT_MAX_FALL_SPEED,
        pipe_speed: float = DEFAULT_PIPE_SPEED,
        pipe_gap: int = DEFAULT_PIPE_GAP,
        pipe_spacing: int = DEFAULT_PIPE_SPACING,
        *,
        rng: random.Random | None = None,
    ) -> None:
        super().__init__()
        self._width = width
        self._height = height
        self._gravity = gravity
        self._flap_strength = flap_strength
        self._max_fall_speed = max_fall_speed
        self._pipe_speed = pipe_speed
        self._pipe_gap = pipe_gap
        self._pipe_spacing = pipe_spacing
        self._rng = rng or random.Random()
        self.buffer = CellBuffer(width, height)
        self._reset_state()

    def _reset_state(self) -> None:
        """Initialise or re-initialise all game state.

        Caveats:
            - The bird starts vertically centred in the playable area
              with zero velocity.  Pipes are pre-populated starting
              from the right side of the screen so the player has a
              moment before the first obstacle arrives.
        """
        # Playable area boundaries (inside the border).
        self._play_top = 1
        self._play_bottom = self._height - 2  # inclusive
        self._play_left = 1
        self._play_right = self._width - 2  # inclusive

        # Bird state — fixed X, floating Y.
        self._bird_x = 8
        self._bird_y: float = self._height / 2.0
        self._bird_vy: float = 0.0

        # Pipe list — each entry is (x_float, gap_top_y).
        # gap_top_y is the first row of the gap (inclusive).
        # The gap extends from gap_top_y to gap_top_y + pipe_gap - 1.
        self.pipes: list[list[float | int]] = []
        self._spawn_initial_pipes()

        # Game state.
        self.score: int = 0
        self.game_over: bool = False
        self.started: bool = False

    def _spawn_initial_pipes(self) -> None:
        """Pre-populate pipes starting from the right edge.

        Caveats:
            - The first pipe is placed at ``_play_right + pipe_spacing``
              so the player has time to react after the first flap.
            - Enough pipes are generated to fill the screen plus one
              off-screen buffer pipe.
        """
        x = float(self._play_right + self._pipe_spacing)
        while x < self._play_right + self._pipe_spacing * 3:
            gap_y = self._random_gap_y()
            self.pipes.append([x, gap_y])
            x += self._pipe_spacing

    def _random_gap_y(self) -> int:
        """Pick a random Y for the top of a pipe gap.

        Caveats:
            - The gap is constrained so it fits entirely within the
              playable area.  The minimum gap_y is ``_play_top + 1``
              (one row below the top border) and the maximum is
              ``_play_bottom - pipe_gap`` so the gap doesn't extend
              past the bottom border.
        """
        min_y = self._play_top + 1
        max_y = self._play_bottom - self._pipe_gap
        if max_y < min_y:
            return min_y
        return self._rng.randint(min_y, max_y)

    def handle_events(self, events: list) -> None:
        """Process keyboard input for flapping and meta keys.

        Caveats:
            - ``Space`` and ``Up`` arrow both trigger a flap.  The flap
              sets the bird's vertical velocity to ``flap_strength``
              (a negative value = upward).  Multiple flaps in the same
              tick each reset velocity — they don't stack.
            - ``q`` and ``Escape`` quit immediately via ``QuitSignal``.
            - ``r`` restarts the game when in game-over state.
            - The first flap also sets ``started`` to ``True``, which
              begins pipe scrolling and gravity.
        """
        for event in events:
            if not isinstance(event, KeyEvent):
                continue
            if event.key in ("q", "escape"):
                raise QuitSignal
            if event.key == "r" and self.game_over:
                self._reset_state()
                continue
            if self.game_over:
                continue

            if event.key in ("space", "up"):
                if not self.started:
                    self.started = True
                self._bird_vy = self._flap_strength

    def update(self, dt: float) -> None:
        """Advance bird physics and pipe positions, check collisions.

        Caveats:
            - If ``started`` is False, no physics or pipe movement
              occurs.  The bird hovers at its initial position.
            - Bird physics uses simple Euler integration:
              ``vy += gravity * dt``, ``y += vy * dt``.  The velocity
              is capped at ``max_fall_speed`` to prevent the bird from
              falling through pipes on large dt values.
            - Collision detection runs after movement.  The bird's
              integer position is checked against each pipe's column
              and gap range.  If the bird is in a pipe column but
              outside the gap, ``game_over`` is set.
            - Floor/ceiling collision: if the bird's integer Y is
              at or beyond the border, ``game_over`` is set.
            - Scoring: each pipe tracks whether it has been passed.
              When a pipe's X scrolls past the bird's X, the score
              increments.  This is tracked via a third element in the
              pipe list (0 = not passed, 1 = passed).
            - Pipes that scroll completely off the left edge are
              removed.  A new pipe is appended on the right to
              maintain a steady stream of obstacles.
        """
        if self.game_over or not self.started:
            return

        # Bird physics.
        self._bird_vy += self._gravity * dt
        if self._bird_vy > self._max_fall_speed:
            self._bird_vy = self._max_fall_speed
        self._bird_y += self._bird_vy * dt

        # Snap bird to integer for collision checks.
        by = int(round(self._bird_y))

        # Ceiling / floor collision.
        if by <= self._play_top or by >= self._play_bottom:
            self.game_over = True
            return

        # Move pipes left.
        for pipe in self.pipes:
            pipe[0] -= self._pipe_speed * dt

        # Check pipe collision and scoring.
        for pipe in self.pipes:
            px = int(round(pipe[0]))
            gap_y = int(pipe[1])

            # Is the bird in this pipe's column?
            if px == self._bird_x:
                # Check if bird is outside the gap.
                if by < gap_y or by >= gap_y + self._pipe_gap:
                    self.game_over = True
                    return

            # Score: pipe has just passed the bird.
            if len(pipe) < 3:
                pipe.append(0)
            if pipe[2] == 0 and px < self._bird_x:
                pipe[2] = 1
                self.score += 1

        # Remove pipes that have scrolled off-screen.
        self.pipes = [p for p in self.pipes if p[0] > self._play_left - 2]

        # Spawn new pipe if needed.
        if self.pipes:
            rightmost_x = max(p[0] for p in self.pipes)
        else:
            rightmost_x = float(self._bird_x)
        if rightmost_x < self._play_right + self._pipe_spacing:
            gap_y = self._random_gap_y()
            new_x = rightmost_x + self._pipe_spacing
            self.pipes.append([new_x, gap_y])

    def render(self) -> None:
        """Draw the border, pipes, bird, and HUD to the buffer.

        Caveats:
            - The entire buffer is cleared and redrawn each frame.
            - Draw order: border, pipes, bird, HUD, game-over overlay.
              The bird is drawn after pipes so it appears on top if
              overlapping.
            - Box-drawing characters are single-codepoint Unicode and
              work reliably across modern terminals.
        """
        self.buffer.clear()

        # -- Border --
        self.buffer.put_text(0, 0, self.CORNER_TL, fg="bright_black")
        self.buffer.put_text(self._width - 1, 0, self.CORNER_TR, fg="bright_black")
        self.buffer.put_text(0, self._height - 1, self.CORNER_BL, fg="bright_black")
        self.buffer.put_text(
            self._width - 1, self._height - 1, self.CORNER_BR, fg="bright_black"
        )
        for x in range(1, self._width - 1):
            self.buffer.put_text(x, 0, self.BORDER_H, fg="bright_black")
            self.buffer.put_text(x, self._height - 1, self.BORDER_H, fg="bright_black")
        for y in range(1, self._height - 1):
            self.buffer.put_text(0, y, self.BORDER_V, fg="bright_black")
            self.buffer.put_text(self._width - 1, y, self.BORDER_V, fg="bright_black")

        # -- Pipes --
        for pipe in self.pipes:
            px = int(round(pipe[0]))
            gap_y = int(pipe[1])

            if px < self._play_left or px > self._play_right:
                continue

            # Draw pipe column above gap.
            for y in range(self._play_top, gap_y):
                self.buffer.put_text(px, y, self.PIPE_CHAR, fg="bright_green")
            # Draw cap at bottom of upper pipe.
            if gap_y > self._play_top:
                self.buffer.put_text(px, gap_y - 1, self.PIPE_CAP, fg="green")

            # Draw pipe column below gap.
            gap_bottom = gap_y + self._pipe_gap
            for y in range(gap_bottom, self._play_bottom + 1):
                self.buffer.put_text(px, y, self.PIPE_CHAR, fg="bright_green")
            # Draw cap at top of lower pipe.
            if gap_bottom <= self._play_bottom:
                self.buffer.put_text(px, gap_bottom, self.PIPE_CAP, fg="green")

        # -- Bird --
        by = int(round(self._bird_y))
        by = max(self._play_top, min(self._play_bottom, by))
        self.buffer.put_text(
            self._bird_x, by, self.BIRD_CHAR, fg="bright_yellow", bold=True
        )

        # -- HUD --
        score_text = f" Score: {self.score} "
        self.buffer.put_text(2, 0, score_text, fg="bright_white")

        hint = " Space/\u2191:flap  Q:quit "
        self.buffer.put_text(2, self._height - 1, hint, fg="bright_black")

        # -- Start prompt --
        if not self.started and not self.game_over:
            msg = "Press SPACE to start"
            msg_x = max(0, (self._width - len(msg)) // 2)
            msg_y = self._height // 2 + 2
            self.buffer.put_text(msg_x, msg_y, msg, fg="bright_white", bold=True)

        # -- Game over overlay --
        if self.game_over:
            msg = "GAME OVER"
            msg_x = max(0, (self._width - len(msg)) // 2)
            msg_y = self._height // 2
            self.buffer.put_text(msg_x, msg_y, msg, fg="bright_red", bold=True)

            score_msg = f"Score: {self.score}"
            score_msg_x = max(0, (self._width - len(score_msg)) // 2)
            self.buffer.put_text(
                score_msg_x, msg_y + 1, score_msg, fg="bright_white"
            )

            restart_hint = "R: restart  Q: quit"
            hint_x = max(0, (self._width - len(restart_hint)) // 2)
            self.buffer.put_text(hint_x, msg_y + 2, restart_hint, fg="bright_white")


def main() -> None:
    """Run the Flappy Bird game example.

    Creates an Engine, pushes a :class:`FlappyBirdScene`, and starts
    the game loop.  Press ``q`` or ``Escape`` to exit.

    Caveats:
        - Requires a real terminal.  Will raise RuntimeError in
          non-TTY environments unless InputManager fallback is
          configured.
        - The engine's ``run()`` blocks until quit.
        - AltScreen is not used here for simplicity.  In a real game,
          wrap the run loop in ``with AltScreen():`` to restore the
          terminal buffer on exit.
    """
    engine = Engine(title="flappy_bird", width=40, height=20, tps=30)
    scene = FlappyBirdScene(width=40, height=20)
    engine.push_scene(scene)

    try:
        engine.run()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
