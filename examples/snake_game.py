"""Example: Classic Snake game in the terminal.

A simple Snake game demonstrating wyby's game loop, input handling, and
cell buffer rendering.  The snake moves continuously in the current
direction; arrow keys change direction.  Eat food (``*``) to grow;
collide with the border or yourself to end the game.

Run this example::

    python examples/snake_game.py

Caveats:
    - This example requires a real terminal (TTY) for keyboard input.
      It will not work when stdin is piped or in CI environments
      without a TTY.  Press ``q`` or ``Escape`` to quit at any time,
      or use Ctrl+C.
    - Snake movement is driven by a timer in ``update(dt)`` — the snake
      advances one cell every ``move_interval`` seconds (default 0.12s).
      This is independent of the engine's tick rate (tps).  If the
      engine's tick rate is lower than 1/move_interval, the snake will
      appear to skip cells.  The default tps=30 is well above this
      threshold.
    - Terminal cells are roughly 1:2 aspect ratio (taller than wide).
      The snake moves at the same speed in cells/sec regardless of
      direction, but *visually* vertical movement appears roughly twice
      as fast because cells are taller than they are wide.  No aspect-
      ratio correction is applied — this is a common trade-off in
      terminal games.
    - Food placement uses ``random.randint`` and does not guarantee
      the food won't land on the snake.  A rejection loop re-rolls if
      the chosen cell is occupied, but in the pathological case where
      the snake fills the entire grid, the loop will exhaust its retry
      budget and skip placement.  On the default 30x20 grid this is
      unlikely until the snake is very long.
    - The game-over state is handled with a simple flag — the scene
      stops processing movement but continues rendering.  Press ``r``
      to restart or ``q``/Escape to quit.
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
from wyby.input import InputManager, KeyEvent
from wyby.scene import Scene


# Direction vectors.
UP = (0, -1)
DOWN = (0, 1)
LEFT = (-1, 0)
RIGHT = (1, 0)

# Map direction to its opposite — used to prevent 180-degree reversal.
_OPPOSITES: dict[tuple[int, int], tuple[int, int]] = {
    UP: DOWN,
    DOWN: UP,
    LEFT: RIGHT,
    RIGHT: LEFT,
}


class SnakeGameScene(Scene):
    """A classic Snake game scene.

    The snake moves continuously in the current direction.  Arrow keys
    change direction (but cannot reverse — pressing the opposite of the
    current direction is ignored).  Eating food (``*``) grows the snake
    by one segment.  Colliding with the border or the snake's own body
    triggers game over.

    Args:
        width: Buffer width in character columns.
        height: Buffer height in character rows.
        move_interval: Seconds between snake moves.  Lower values make
            the snake faster.

    Caveats:
        - The playable area is the interior of the border: columns
          1 to ``width - 2``, rows 1 to ``height - 2``.  The border
          itself occupies the outermost ring of cells.
        - ``move_interval`` controls difficulty.  At 0.12s (default),
          the snake moves ~8 cells/sec which is comfortable.  Below
          0.05s the game becomes very difficult.
        - Direction changes are queued: if multiple arrow keys arrive
          in the same tick (common when keys are buffered), only the
          last valid direction change is applied.  This prevents the
          snake from accidentally reversing when two keys are pressed
          in quick succession.
        - The score is simply the number of food items eaten.  There
          is no score persistence — the game resets on restart.
        - The random seed is not fixed, so food placement varies
          between runs.
    """

    BORDER_H = "\u2500"  # ─
    BORDER_V = "\u2502"  # │
    CORNER_TL = "\u250c"  # ┌
    CORNER_TR = "\u2510"  # ┐
    CORNER_BL = "\u2514"  # └
    CORNER_BR = "\u2518"  # ┘

    SNAKE_HEAD = "@"
    SNAKE_BODY = "o"
    FOOD_CHAR = "*"

    def __init__(
        self,
        width: int = 30,
        height: int = 20,
        move_interval: float = 0.12,
        *,
        rng: random.Random | None = None,
    ) -> None:
        super().__init__()
        self._width = width
        self._height = height
        self._move_interval = move_interval
        self._rng = rng or random.Random()
        self.buffer = CellBuffer(width, height)
        self._reset_state()

    def _reset_state(self) -> None:
        """Initialise or re-initialise all game state.

        Caveats:
            - The snake starts in the centre of the playable area
              heading right, with a length of 3.  The initial body
              extends to the left of the head.
        """
        # Snake body — list of (x, y) tuples, head is body[0].
        cx = self._width // 2
        cy = self._height // 2
        self.body: list[tuple[int, int]] = [
            (cx, cy),
            (cx - 1, cy),
            (cx - 2, cy),
        ]
        self.direction: tuple[int, int] = RIGHT
        self._next_direction: tuple[int, int] = RIGHT

        self.food: tuple[int, int] | None = None
        self.score: int = 0
        self.game_over: bool = False
        self._move_timer: float = 0.0

        self._place_food()

    @property
    def head(self) -> tuple[int, int]:
        """Position of the snake's head."""
        return self.body[0]

    def _place_food(self) -> None:
        """Place food at a random unoccupied cell inside the border.

        Caveats:
            - Uses a rejection loop — picks a random position and
              re-rolls if it overlaps the snake.  Limited to 100
              attempts to avoid an infinite loop if the grid is nearly
              full.  If all attempts fail, ``self.food`` is set to
              ``None`` and no food is displayed until the next eat.
        """
        occupied = set(self.body)
        for _ in range(100):
            x = self._rng.randint(1, self._width - 2)
            y = self._rng.randint(1, self._height - 2)
            if (x, y) not in occupied:
                self.food = (x, y)
                return
        # Grid is nearly full — skip placement.
        self.food = None

    def handle_events(self, events: list) -> None:
        """Process keyboard input for direction changes and meta keys.

        Caveats:
            - Direction changes are validated against the current
              direction to prevent 180-degree reversal.  The check
              uses ``self.direction`` (the committed direction), not
              ``_next_direction``, so rapid key presses within one
              tick can chain (e.g. up then left) as long as each
              intermediate step is valid.
            - ``q`` and Escape quit immediately via ``QuitSignal``.
            - ``r`` restarts the game when in game-over state.
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

            new_dir: tuple[int, int] | None = None
            if event.key == "up":
                new_dir = UP
            elif event.key == "down":
                new_dir = DOWN
            elif event.key == "left":
                new_dir = LEFT
            elif event.key == "right":
                new_dir = RIGHT

            if new_dir is not None and new_dir != _OPPOSITES.get(self.direction):
                self._next_direction = new_dir

    def update(self, dt: float) -> None:
        """Advance the snake by one cell when the move timer fires.

        The move timer accumulates ``dt`` each tick.  When it reaches
        ``move_interval``, the snake moves one cell in the current
        direction and the timer resets.

        Caveats:
            - ``dt`` may vary — the engine uses a fixed-timestep
              accumulator but ``update()`` receives the fixed dt.
              The move timer still works correctly because it simply
              accumulates time.
            - Collision detection is performed after each move.  If
              the head lands on the border or the snake's own body,
              ``game_over`` is set to ``True``.
            - When the snake eats food, the tail is not removed
              (effectively growing the snake by one).  A new food
              item is placed immediately.
        """
        if self.game_over:
            return

        self._move_timer += dt
        if self._move_timer < self._move_interval:
            return
        self._move_timer -= self._move_interval

        # Commit direction.
        self.direction = self._next_direction

        # Compute new head position.
        hx, hy = self.head
        dx, dy = self.direction
        new_head = (hx + dx, hy + dy)
        nx, ny = new_head

        # Check wall collision.
        if nx <= 0 or nx >= self._width - 1 or ny <= 0 or ny >= self._height - 1:
            self.game_over = True
            return

        # Check self collision (exclude the tail tip which is about to
        # move — unless the snake just ate, but in that case the tail
        # stays so we must check the full body).
        if new_head in self.body:
            self.game_over = True
            return

        # Move: insert new head.
        self.body.insert(0, new_head)

        # Check food.
        if self.food is not None and new_head == self.food:
            self.score += 1
            self._place_food()
        else:
            # Remove tail (no growth).
            self.body.pop()

    def render(self) -> None:
        """Draw the border, snake, food, and HUD to the buffer.

        Caveats:
            - The entire buffer is cleared and redrawn each frame.
            - Draw order: border, food, snake body, snake head, HUD.
              The head is drawn last so it appears on top of body
              segments if they overlap (which shouldn't happen during
              normal gameplay).
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

        # -- Food --
        if self.food is not None:
            fx, fy = self.food
            self.buffer.put_text(fx, fy, self.FOOD_CHAR, fg="bright_red", bold=True)

        # -- Snake body (tail to neck — head drawn separately) --
        for segment in self.body[1:]:
            sx, sy = segment
            self.buffer.put_text(sx, sy, self.SNAKE_BODY, fg="bright_green")

        # -- Snake head --
        hx, hy = self.head
        self.buffer.put_text(hx, hy, self.SNAKE_HEAD, fg="bright_green", bold=True)

        # -- HUD --
        score_text = f" Score: {self.score} "
        self.buffer.put_text(2, 0, score_text, fg="bright_white")

        hint = " Arrows:move Q:quit "
        self.buffer.put_text(2, self._height - 1, hint, fg="bright_black")

        # -- Game over overlay --
        if self.game_over:
            msg = "GAME OVER"
            msg_x = max(0, (self._width - len(msg)) // 2)
            msg_y = self._height // 2
            self.buffer.put_text(msg_x, msg_y, msg, fg="bright_red", bold=True)

            restart_hint = "R: restart  Q: quit"
            hint_x = max(0, (self._width - len(restart_hint)) // 2)
            self.buffer.put_text(hint_x, msg_y + 1, restart_hint, fg="bright_white")


def main() -> None:
    """Run the Snake game example.

    Creates an Engine, pushes a :class:`SnakeGameScene`, and starts
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
    input_manager = InputManager()
    engine = Engine(
        title="snake", width=30, height=20, tps=30, input_manager=input_manager
    )
    scene = SnakeGameScene(width=30, height=20)
    engine.push_scene(scene)

    try:
        engine.run()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
