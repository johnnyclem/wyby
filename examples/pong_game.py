"""Example: Classic Pong game in the terminal.

A two-player Pong game demonstrating wyby's game loop, input handling,
collision detection, and cell buffer rendering.  Player 1 (left paddle)
uses ``w``/``s`` keys; Player 2 (right paddle) uses ``up``/``down``
arrow keys.  First player to reach the winning score wins.

Run this example::

    python examples/pong_game.py

Caveats:
    - This example requires a real terminal (TTY) for keyboard input.
      It will not work when stdin is piped or in CI environments
      without a TTY.  Press ``q`` or ``Escape`` to quit at any time,
      or use Ctrl+C.
    - The ball uses float-precision position and velocity internally,
      but rendering snaps to integer cell coordinates each frame.
      At low speeds this can make movement look jerky — the default
      ball speed (20 cells/sec horizontal) is fast enough to appear
      smooth at 30 TPS.
    - Terminal cells are roughly 1:2 aspect ratio (taller than wide).
      The ball speed is the same in cells/sec for both axes, but
      *visually* vertical movement appears roughly twice as fast.
      No aspect-ratio correction is applied — this is a common
      trade-off in terminal games.
    - Paddle movement is immediate (no acceleration or inertia).
      Paddles move one cell per event, so holding a key fires at the
      terminal's key repeat rate, which varies by OS and terminal.
    - The ball bounces off the top and bottom walls and off paddles.
      When a ball hits a paddle, the horizontal velocity reverses.
      There is no spin, angle variation, or speed increase — this is
      a minimal Pong implementation.
    - The ball resets to the centre after each point with a random
      vertical direction.  The horizontal direction alternates to
      serve toward the player who was scored on.
    - Collision detection checks the ball's integer position against
      paddle column and row ranges.  At high ball speeds (or very
      low tick rates), the ball could skip past a paddle in a single
      frame.  The default speed and 30 TPS avoid this.
    - The game-over state is handled with a simple flag — the scene
      stops processing ball/paddle movement but continues rendering.
      Press ``r`` to restart or ``q``/Escape to quit.
    - The buffer is cleared and fully redrawn every frame.  wyby does
      not perform dirty-region tracking.
    - AltScreen is not used here for simplicity.  In a real game,
      wrap the run loop in ``with AltScreen():`` to restore the
      terminal buffer on exit.
"""

from __future__ import annotations

import random

from wyby.app import Engine, QuitSignal
from wyby.grid import CellBuffer
from wyby.input import KeyEvent
from wyby.scene import Scene


# Paddle movement step in cells.
PADDLE_SPEED = 1


class PongScene(Scene):
    """A classic two-player Pong game scene.

    Player 1 (left) uses ``w``/``s`` keys.  Player 2 (right) uses
    ``up``/``down`` arrow keys.  The ball bounces off walls and paddles.
    Missing the ball awards a point to the opponent.

    Args:
        width: Buffer width in character columns.
        height: Buffer height in character rows.
        paddle_height: Height of each paddle in cells.
        winning_score: Points needed to win.

    Caveats:
        - The playable area is the interior of the border: columns
          1 to ``width - 2``, rows 1 to ``height - 2``.  The border
          itself occupies the outermost ring of cells.
        - Paddle height should be odd for symmetric appearance.
          Even values work but the paddle won't be perfectly centred.
        - Ball velocity is in cells per second.  The default
          (vx=20, vy=12) gives a diagonal trajectory that is
          comfortable to track at 30 TPS.
    """

    BORDER_H = "\u2500"  # ─
    BORDER_V = "\u2502"  # │
    CORNER_TL = "\u250c"  # ┌
    CORNER_TR = "\u2510"  # ┐
    CORNER_BL = "\u2514"  # └
    CORNER_BR = "\u2518"  # ┘

    PADDLE_CHAR = "\u2588"  # █
    BALL_CHAR = "\u25cf"  # ●
    NET_CHAR = "\u2502"  # │ (dashed centre line)

    def __init__(
        self,
        width: int = 60,
        height: int = 24,
        paddle_height: int = 5,
        winning_score: int = 5,
        *,
        ball_speed_x: float = 20.0,
        ball_speed_y: float = 12.0,
        rng: random.Random | None = None,
    ) -> None:
        super().__init__()
        self._width = width
        self._height = height
        self._paddle_height = paddle_height
        self._winning_score = winning_score
        self._ball_speed_x = ball_speed_x
        self._ball_speed_y = ball_speed_y
        self._rng = rng or random.Random()
        self.buffer = CellBuffer(width, height)
        self._reset_state()

    def _reset_state(self) -> None:
        """Initialise or re-initialise all game state.

        Caveats:
            - Paddles start centred vertically.  The ball starts at the
              centre of the playable area, moving right with a random
              vertical direction.
        """
        # Playable area boundaries (inside the border).
        self._play_top = 1
        self._play_bottom = self._height - 2  # inclusive
        self._play_left = 1
        self._play_right = self._width - 2  # inclusive

        # Paddle positions — stored as the top cell of each paddle.
        # Player 1 (left) at column 2, Player 2 (right) at column width-3.
        self._p1_x = 2
        self._p2_x = self._width - 3
        centre_y = self._height // 2
        self._p1_y = centre_y - self._paddle_height // 2
        self._p2_y = centre_y - self._paddle_height // 2

        # Ball position (float for smooth movement).
        self._ball_x: float = self._width / 2.0
        self._ball_y: float = self._height / 2.0

        # Ball velocity (cells per second).
        self._ball_vx: float = self._ball_speed_x
        vy_sign = self._rng.choice([-1, 1])
        self._ball_vy: float = self._ball_speed_y * vy_sign

        # Scores.
        self.score_p1: int = 0
        self.score_p2: int = 0

        # Game state.
        self.game_over: bool = False
        self.winner: int = 0  # 1 or 2 when game_over is True.

    def _reset_ball(self, serve_direction: int) -> None:
        """Reset ball to centre after a point is scored.

        Args:
            serve_direction: ``1`` to serve right (toward P2),
                ``-1`` to serve left (toward P1).

        Caveats:
            - The ball always starts from the centre.  The horizontal
              direction is ``serve_direction``; the vertical direction
              is random.
        """
        self._ball_x = self._width / 2.0
        self._ball_y = self._height / 2.0
        self._ball_vx = self._ball_speed_x * serve_direction
        vy_sign = self._rng.choice([-1, 1])
        self._ball_vy = self._ball_speed_y * vy_sign

    def handle_events(self, events: list) -> None:
        """Process keyboard input for paddle movement and meta keys.

        Caveats:
            - Paddle movement is clamped to the playable area.  Pressing
              a direction key when the paddle is at the boundary does
              nothing.
            - ``q`` and ``Escape`` quit immediately via ``QuitSignal``.
            - ``r`` restarts the game when in game-over state.
            - Both players' inputs are processed from the same event
              stream.  On a single keyboard this works naturally.
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

            # Player 1: w/s keys.
            if event.key == "w":
                self._p1_y = max(self._play_top, self._p1_y - PADDLE_SPEED)
            elif event.key == "s":
                self._p1_y = min(
                    self._play_bottom - self._paddle_height + 1,
                    self._p1_y + PADDLE_SPEED,
                )
            # Player 2: arrow keys.
            elif event.key == "up":
                self._p2_y = max(self._play_top, self._p2_y - PADDLE_SPEED)
            elif event.key == "down":
                self._p2_y = min(
                    self._play_bottom - self._paddle_height + 1,
                    self._p2_y + PADDLE_SPEED,
                )

    def update(self, dt: float) -> None:
        """Advance ball position and check collisions.

        Caveats:
            - Ball movement uses simple Euler integration:
              ``pos += vel * dt``.  This is frame-rate dependent in
              theory, but with a fixed timestep engine the dt is
              constant and the behaviour is deterministic.
            - Wall bounces reverse the vertical velocity.  The ball is
              clamped to the playable area to prevent it from escaping
              on large dt values.
            - Paddle collision checks the ball's integer position
              against the paddle column and row range.  At very high
              speeds the ball could tunnel through a paddle — the
              default speed and tick rate prevent this.
            - When a point is scored, the ball resets to the centre and
              serves toward the player who was scored on.
        """
        if self.game_over:
            return

        # Move ball.
        self._ball_x += self._ball_vx * dt
        self._ball_y += self._ball_vy * dt

        # Wall collision (top and bottom borders).
        if self._ball_y <= self._play_top:
            self._ball_y = self._play_top
            self._ball_vy = abs(self._ball_vy)
        elif self._ball_y >= self._play_bottom:
            self._ball_y = self._play_bottom
            self._ball_vy = -abs(self._ball_vy)

        # Snap ball to integer for collision checks.
        bx = int(round(self._ball_x))
        by = int(round(self._ball_y))

        # Paddle collision — Player 1 (left).
        if (
            self._ball_vx < 0
            and bx == self._p1_x
            and self._p1_y <= by <= self._p1_y + self._paddle_height - 1
        ):
            self._ball_vx = abs(self._ball_vx)
            # Nudge ball off the paddle to prevent re-triggering.
            self._ball_x = self._p1_x + 1

        # Paddle collision — Player 2 (right).
        if (
            self._ball_vx > 0
            and bx == self._p2_x
            and self._p2_y <= by <= self._p2_y + self._paddle_height - 1
        ):
            self._ball_vx = -abs(self._ball_vx)
            self._ball_x = self._p2_x - 1

        # Scoring — ball passed left or right edge.
        if self._ball_x < self._play_left:
            self.score_p2 += 1
            if self.score_p2 >= self._winning_score:
                self.game_over = True
                self.winner = 2
            else:
                self._reset_ball(serve_direction=1)
        elif self._ball_x > self._play_right:
            self.score_p1 += 1
            if self.score_p1 >= self._winning_score:
                self.game_over = True
                self.winner = 1
            else:
                self._reset_ball(serve_direction=-1)

    def render(self) -> None:
        """Draw the border, paddles, ball, net, and HUD to the buffer.

        Caveats:
            - The entire buffer is cleared and redrawn each frame.
            - Draw order: border, net, paddles, ball, HUD, game-over
              overlay.  The ball is drawn after paddles so it appears
              on top if overlapping.
            - Box-drawing characters are single-codepoint Unicode and
              work reliably across modern terminals.
        """
        self.buffer.clear()

        # -- Border --
        self.buffer.put_text(0, 0, self.CORNER_TL, fg="bright_black")
        self.buffer.put_text(self._width - 1, 0, self.CORNER_TR, fg="bright_black")
        self.buffer.put_text(
            0, self._height - 1, self.CORNER_BL, fg="bright_black"
        )
        self.buffer.put_text(
            self._width - 1, self._height - 1, self.CORNER_BR, fg="bright_black"
        )
        for x in range(1, self._width - 1):
            self.buffer.put_text(x, 0, self.BORDER_H, fg="bright_black")
            self.buffer.put_text(
                x, self._height - 1, self.BORDER_H, fg="bright_black"
            )
        for y in range(1, self._height - 1):
            self.buffer.put_text(0, y, self.BORDER_V, fg="bright_black")
            self.buffer.put_text(
                self._width - 1, y, self.BORDER_V, fg="bright_black"
            )

        # -- Centre net --
        net_x = self._width // 2
        for y in range(1, self._height - 1):
            if y % 2 == 0:
                self.buffer.put_text(net_x, y, self.NET_CHAR, fg="bright_black")

        # -- Paddles --
        for dy in range(self._paddle_height):
            self.buffer.put_text(
                self._p1_x, self._p1_y + dy, self.PADDLE_CHAR, fg="bright_white"
            )
            self.buffer.put_text(
                self._p2_x, self._p2_y + dy, self.PADDLE_CHAR, fg="bright_white"
            )

        # -- Ball --
        bx = int(round(self._ball_x))
        by = int(round(self._ball_y))
        # Clamp to playable area for rendering.
        bx = max(self._play_left, min(self._play_right, bx))
        by = max(self._play_top, min(self._play_bottom, by))
        self.buffer.put_text(bx, by, self.BALL_CHAR, fg="bright_yellow", bold=True)

        # -- Scores --
        score_text = f" {self.score_p1}  |  {self.score_p2} "
        score_x = max(0, (self._width - len(score_text)) // 2)
        self.buffer.put_text(score_x, 0, score_text, fg="bright_white")

        # -- Controls hint --
        hint = " W/S:P1  \u2191/\u2193:P2  Q:quit "
        self.buffer.put_text(2, self._height - 1, hint, fg="bright_black")

        # -- Game over overlay --
        if self.game_over:
            msg = f"PLAYER {self.winner} WINS!"
            msg_x = max(0, (self._width - len(msg)) // 2)
            msg_y = self._height // 2
            self.buffer.put_text(msg_x, msg_y, msg, fg="bright_green", bold=True)

            restart_hint = "R: restart  Q: quit"
            hint_x = max(0, (self._width - len(restart_hint)) // 2)
            self.buffer.put_text(
                hint_x, msg_y + 1, restart_hint, fg="bright_white"
            )


def main() -> None:
    """Run the Pong game example.

    Creates an Engine, pushes a :class:`PongScene`, and starts
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
    engine = Engine(title="pong", width=60, height=24, tps=30)
    scene = PongScene(width=60, height=24)
    engine.push_scene(scene)

    try:
        engine.run()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
