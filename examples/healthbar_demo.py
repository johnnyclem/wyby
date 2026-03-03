"""Example: HealthBar widget rendering in a terminal game HUD.

Demonstrates how to use :class:`~wyby.healthbar.HealthBar` to display
player stats (HP, MP) alongside a game scene.  The player moves an
``@`` around a bordered grid; pressing ``d`` deals damage and ``h``
heals.  The health bars update each frame.

Run this example::

    python examples/healthbar_demo.py

Caveats:
    - This example requires a real terminal (TTY) for keyboard input.
      It will not work when stdin is piped or in CI environments
      without a TTY.  The Engine falls back gracefully on
      KeyboardInterrupt (Ctrl+C).
    - HealthBar uses Unicode block characters (``█`` U+2588 and ``░``
      U+2591) which are reliably 1-column wide on modern terminals.
      On very old terminals or bitmap-font configurations, they may
      render incorrectly.  Test on your target terminal.
    - The health bar colours (green/yellow/red) are terminal-dependent.
      Most 256-colour and truecolour terminals render these faithfully,
      but 8-colour terminals may map them to the nearest available
      colour.  See :mod:`wyby.color` for colour fallback utilities.
    - HealthBar does not animate value changes.  Damage and healing are
      reflected immediately on the next frame.  For smooth transitions,
      lerp the ``current`` value over multiple frames in ``update()``.
    - The bar width (20 cells) gives 5% granularity per cell.  For
      finer resolution, increase ``bar_width``.
    - Terminal cells are ~1:2 aspect ratio (taller than wide).  The
      health bars appear as thin horizontal strips.  This is normal
      for terminal UIs and cannot be corrected without half-height
      block characters (which are less portable).
"""

from __future__ import annotations

from wyby.app import Engine, QuitSignal
from wyby.grid import CellBuffer
from wyby.healthbar import HealthBar
from wyby.input import KeyEvent
from wyby.scene import Scene


# Damage/heal amount per key press.
_DAMAGE_AMOUNT = 10
_HEAL_AMOUNT = 15


class HealthBarDemoScene(Scene):
    """A game scene with a movable player and health bar HUD.

    The scene renders a bordered play area with a player character
    (``@``) and two health bars (HP and MP) above it.  Arrow keys
    move the player; ``d`` deals damage and ``h`` heals.

    Caveats:
        - The HUD (health bars) is drawn directly into the same
          CellBuffer as the game world.  In a real game, you would
          typically draw the HUD on a separate layer or overlay to
          avoid z-order conflicts.  See :class:`~wyby.layer.LayerStack`
          for layer-based compositing.
        - Input is processed in ``handle_events`` and state changes
          are applied immediately (health changes, movement).  For
          more complex games, defer state mutations to ``update()``.
        - The MP bar is included to show multiple health bars.  It
          uses the same HealthBar widget with a different label prefix.
    """

    PLAYER_CHAR = "@"
    BORDER_H = "\u2500"  # ─
    BORDER_V = "\u2502"  # │
    CORNER_TL = "\u250c"  # ┌
    CORNER_TR = "\u2510"  # ┐
    CORNER_BL = "\u2514"  # └
    CORNER_BR = "\u2518"  # ┘

    def __init__(self, width: int = 40, height: int = 18) -> None:
        super().__init__()
        self._width = width
        self._height = height
        self.buffer = CellBuffer(width, height)

        # Player starts in the center of the play area (below HUD).
        # HUD takes rows 0–1, play area starts at row 2.
        self.player_x: int = width // 2
        self.player_y: int = (height + 3) // 2  # Center of play area

        # Health bars — positioned in the HUD area (rows 0–1).
        # Caveat: bar_width=20 gives 5% granularity per cell.
        # For finer resolution, increase bar_width.
        self.hp_bar = HealthBar(
            current=100, maximum=100,
            x=1, y=0, bar_width=20,
            show_label=True, label_prefix="HP",
        )
        self.mp_bar = HealthBar(
            current=50, maximum=50,
            x=1, y=1, bar_width=20,
            show_label=True, label_prefix="MP",
        )

    def handle_events(self, events: list) -> None:
        """Handle movement, damage, heal, and quit keys.

        Caveats:
            - ``d`` for damage and ``h`` for heal are applied immediately.
              Multiple key events in the same tick stack (e.g. holding
              ``d`` deals damage for each buffered key repeat).
            - The player is clamped to the play area (below the HUD,
              inside the border).
        """
        for event in events:
            if not isinstance(event, KeyEvent):
                continue
            if event.key == "escape" or event.key == "q":
                raise QuitSignal
            elif event.key == "up":
                self.player_y = max(3, self.player_y - 1)
            elif event.key == "down":
                self.player_y = min(self._height - 2, self.player_y + 1)
            elif event.key == "left":
                self.player_x = max(1, self.player_x - 1)
            elif event.key == "right":
                self.player_x = min(self._width - 2, self.player_x + 1)
            elif event.key == "d":
                self.hp_bar.current -= _DAMAGE_AMOUNT
            elif event.key == "h":
                self.hp_bar.current += _HEAL_AMOUNT

    def update(self, dt: float) -> None:
        """No-op — all state changes happen in handle_events."""

    def render(self) -> None:
        """Draw the HUD and game world.

        Caveats:
            - The entire buffer is cleared and redrawn each frame.
            - Health bars are drawn first, then the border, then
              the player.  Draw order determines visual stacking —
              the player is drawn last so it appears on top.
        """
        self.buffer.clear()

        # Draw health bars in the HUD area.
        self.hp_bar.draw(self.buffer)
        self.mp_bar.draw(self.buffer)

        # Draw border around the play area (row 2 to bottom).
        play_top = 2
        self.buffer.put_text(0, play_top, self.CORNER_TL, fg="bright_black")
        self.buffer.put_text(self._width - 1, play_top, self.CORNER_TR, fg="bright_black")
        self.buffer.put_text(0, self._height - 1, self.CORNER_BL, fg="bright_black")
        self.buffer.put_text(
            self._width - 1, self._height - 1, self.CORNER_BR, fg="bright_black",
        )
        for x in range(1, self._width - 1):
            self.buffer.put_text(x, play_top, self.BORDER_H, fg="bright_black")
            self.buffer.put_text(x, self._height - 1, self.BORDER_H, fg="bright_black")
        for y in range(play_top + 1, self._height - 1):
            self.buffer.put_text(0, y, self.BORDER_V, fg="bright_black")
            self.buffer.put_text(self._width - 1, y, self.BORDER_V, fg="bright_black")

        # Draw player.
        self.buffer.put_text(
            self.player_x, self.player_y, self.PLAYER_CHAR,
            fg="bright_yellow", bold=True,
        )

        # Instructions in the bottom border.
        hint = " Arrows:move D:dmg H:heal Q:quit "
        self.buffer.put_text(2, self._height - 1, hint, fg="bright_black")


def main() -> None:
    """Run the health bar demo.

    Caveats:
        - Requires a real terminal.  Will raise RuntimeError in
          non-TTY environments unless InputManager fallback is
          configured.
        - The engine's ``run()`` blocks until quit.  Use Ctrl+C or
          press Q/Escape.
        - AltScreen is not used here for simplicity.  In a real game,
          wrap the run loop in ``with AltScreen():`` to restore the
          terminal buffer on exit.
    """
    engine = Engine(title="healthbar demo", width=40, height=18, tps=30)
    scene = HealthBarDemoScene(width=40, height=18)
    engine.push_scene(scene)

    try:
        engine.run()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
