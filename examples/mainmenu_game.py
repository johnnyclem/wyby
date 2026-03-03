"""Example: Main menu and game scene with scene-stack transitions.

Demonstrates how to build a simple two-scene game using wyby's scene
system.  A :class:`MainMenuScene` presents a title and selectable menu
options; selecting "New Game" pushes a :class:`GameScene` onto the
stack where the player can move an ``@`` around a grid.  Pressing
Escape in the game scene pops back to the menu.

Run this example::

    python examples/mainmenu_game.py

Caveats:
    - This example requires a real terminal (TTY) for keyboard input.
      It will not work when stdin is piped or in CI environments
      without a TTY.  The Engine falls back gracefully on
      KeyboardInterrupt (Ctrl+C).
    - The ``@`` player character is rendered via CellBuffer, which
      uses single-character cells.  Terminal cells are roughly 1:2
      aspect ratio (taller than wide), so movement may appear faster
      vertically than horizontally.  No aspect-ratio correction is
      applied.
    - Scene transitions (menu -> game, game -> menu) are instantaneous.
      wyby v0.1 has transition stubs but no animation system.
    - The main menu passes an ``on_start_game`` callback to avoid
      coupling the scene to the Engine directly.  An alternative is
      to pass the Engine reference, but callbacks keep scenes testable
      without a running engine.
    - CellBuffer rendering goes through Rich's Live display.  On slow
      terminals or over SSH, flicker is possible.  See
      :mod:`wyby.render_warnings` for diagnostics.
"""

from __future__ import annotations

from wyby.app import Engine, QuitSignal
from wyby.grid import CellBuffer
from wyby.input import InputManager, KeyEvent
from wyby.scene import Scene


class MainMenuScene(Scene):
    """A simple main menu with selectable options.

    The menu renders a title and a list of options.  Arrow keys move
    the selection cursor; Enter activates the selected option.

    Args:
        on_start_game: Callback invoked when the player selects
            "New Game".  Typically this pushes a GameScene onto the
            engine's scene stack.

    Caveats:
        - The menu does not handle terminal resize.  If the terminal
          is smaller than the menu layout, text will be clipped by the
          CellBuffer's silent out-of-bounds behaviour.  Override
          ``on_resize`` to re-center the menu if needed.
        - Only up/down arrows and Enter are handled.  Mouse input is
          ignored.  Extend ``handle_events`` with ``isinstance``
          checks for ``MouseEvent`` if mouse support is desired.
        - Input is processed in ``handle_events`` and state changes
          (like starting the game) are deferred to ``update`` via a
          flag.  This follows the recommended pattern of not mutating
          the scene stack during event handling.  See
          :meth:`Scene.handle_events` caveats.
    """

    TITLE = "WYBY EXAMPLE GAME"
    OPTIONS = ("New Game", "Quit")

    def __init__(
        self,
        on_start_game: callable | None = None,
        width: int = 40,
        height: int = 15,
    ) -> None:
        super().__init__()
        self._on_start_game = on_start_game
        self._selected: int = 0
        self._activate: bool = False
        self._width = width
        self._height = height
        self.buffer = CellBuffer(width, height)

    @property
    def selected(self) -> int:
        """Index of the currently highlighted menu option."""
        return self._selected

    def handle_events(self, events: list) -> None:
        """Process keyboard input for menu navigation.

        Caveats:
            - Only ``KeyEvent`` instances are inspected; all other
              event types (mouse, custom) are silently ignored.
            - The ``_activate`` flag is set here but acted on in
              ``update()``.  This avoids mutating the scene stack
              mid-event-handling, which can cause unexpected behaviour
              in the same tick.
        """
        for event in events:
            if not isinstance(event, KeyEvent):
                continue
            if event.key == "up":
                self._selected = (self._selected - 1) % len(self.OPTIONS)
            elif event.key == "down":
                self._selected = (self._selected + 1) % len(self.OPTIONS)
            elif event.key == "enter":
                self._activate = True

    def update(self, dt: float) -> None:
        """Act on the selected menu option if Enter was pressed.

        Caveats:
            - ``QuitSignal`` is raised directly from ``update()`` —
              this is the recommended way to quit without needing a
              reference to the Engine.
            - If ``on_start_game`` is ``None``, selecting "New Game"
              is a no-op.  This allows testing the menu in isolation.
        """
        if not self._activate:
            return
        self._activate = False

        option = self.OPTIONS[self._selected]
        if option == "Quit":
            raise QuitSignal
        if option == "New Game" and self._on_start_game is not None:
            self._on_start_game()

    def render(self) -> None:
        """Draw the menu title and options to the cell buffer.

        Caveats:
            - ``render()`` must not modify game state — it is a pure
              read of the scene's current state.
            - The buffer is cleared every frame.  This is simple but
              means every cell is rewritten even if nothing changed.
              For a menu with static layout this is negligible.
        """
        self.buffer.clear()

        # Title centered on row 2.
        title_x = max(0, (self._width - len(self.TITLE)) // 2)
        self.buffer.put_text(title_x, 2, self.TITLE, fg="bright_cyan", bold=True)

        # Menu options starting at row 5.
        for i, option in enumerate(self.OPTIONS):
            y = 5 + i * 2
            if i == self._selected:
                label = f"> {option} <"
                self.buffer.put_text(2, y, label, fg="bright_white", bold=True)
            else:
                label = f"  {option}"
                self.buffer.put_text(2, y, label, fg="white")

        # Navigation hint at the bottom.
        hint = "Arrow keys: select  Enter: confirm"
        self.buffer.put_text(2, self._height - 2, hint, fg="bright_black")


class GameScene(Scene):
    """A minimal game scene with a movable player character.

    The player is represented by ``@`` on a bordered grid.  Arrow keys
    move the player; Escape pops back to the main menu.

    Args:
        on_return_to_menu: Callback invoked when the player presses
            Escape.  Typically this pops the game scene off the stack.
        width: Grid width in columns.
        height: Grid height in rows.

    Caveats:
        - The player position is clamped to the interior of the border
          (1 to width-2 for x, 1 to height-2 for y).  The border is
          drawn with box-drawing characters which are single-codepoint
          Unicode and work on all modern terminals.
        - Movement speed is one cell per key press, not per unit time.
          Holding a key repeats at the OS key-repeat rate, which
          varies by platform.  For smoother movement, accumulate
          velocity in ``update()`` instead.
        - This scene does not use ``updates_when_paused`` or
          ``renders_when_paused`` (both default to ``False``).  If a
          pause overlay were pushed on top, this scene would freeze.
          Set ``renders_when_paused = True`` to keep it visible behind
          a transparent overlay.
        - The grid does not adapt to terminal resize.  If the terminal
          shrinks below the grid size, output will be clipped.
    """

    PLAYER_CHAR = "@"
    BORDER_H = "\u2500"  # ─
    BORDER_V = "\u2502"  # │
    CORNER_TL = "\u250c"  # ┌
    CORNER_TR = "\u2510"  # ┐
    CORNER_BL = "\u2514"  # └
    CORNER_BR = "\u2518"  # ┘

    def __init__(
        self,
        on_return_to_menu: callable | None = None,
        width: int = 40,
        height: int = 15,
    ) -> None:
        super().__init__()
        self._on_return_to_menu = on_return_to_menu
        self._width = width
        self._height = height
        self.buffer = CellBuffer(width, height)

        # Player starts in the center of the playable area.
        self.player_x: int = width // 2
        self.player_y: int = height // 2
        self._wants_menu: bool = False

    def handle_events(self, events: list) -> None:
        """Handle arrow keys for movement and Escape for menu return.

        Caveats:
            - Movement is applied immediately to player position during
              event handling, not deferred to update.  This is acceptable
              because position changes don't affect the scene stack.
              Stack mutations (like returning to menu) are deferred.
            - Multiple arrow key events in the same tick are all
              processed, so the player can move multiple cells per tick
              if keys were buffered.
        """
        for event in events:
            if not isinstance(event, KeyEvent):
                continue
            if event.key == "escape":
                self._wants_menu = True
            elif event.key == "up":
                self.player_y = max(1, self.player_y - 1)
            elif event.key == "down":
                self.player_y = min(self._height - 2, self.player_y + 1)
            elif event.key == "left":
                self.player_x = max(1, self.player_x - 1)
            elif event.key == "right":
                self.player_x = min(self._width - 2, self.player_x + 1)

    def update(self, dt: float) -> None:
        """Check if the player wants to return to the menu.

        Caveats:
            - The menu return is triggered by a flag set in
              ``handle_events``, not by directly mutating the stack
              during event handling.  This is the recommended pattern.
        """
        if self._wants_menu:
            self._wants_menu = False
            if self._on_return_to_menu is not None:
                self._on_return_to_menu()

    def render(self) -> None:
        """Draw the game grid with border and player.

        Caveats:
            - The entire buffer is cleared and redrawn each frame.
              For larger grids, consider dirty-region tracking to
              reduce work (not implemented in wyby v0.1).
            - Box-drawing characters (``\\u2500``, ``\\u2502``, etc.)
              are narrow (1-column) Unicode characters that work
              reliably across modern terminals.  Avoid using emoji
              for borders — emoji width is terminal-dependent.
        """
        self.buffer.clear()

        # Draw border.
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

        # Draw player.
        self.buffer.put_text(
            self.player_x,
            self.player_y,
            self.PLAYER_CHAR,
            fg="bright_yellow",
            bold=True,
        )

        # HUD line above the border.
        pos_text = f"Pos: ({self.player_x}, {self.player_y})"
        self.buffer.put_text(2, self._height - 1, pos_text, fg="bright_black")

        # Instructions inside the top border.
        hint = " Arrow keys: move  Esc: menu "
        self.buffer.put_text(2, 0, hint, fg="bright_black")


def main() -> None:
    """Run the example game.

    Creates an Engine, wires up MainMenuScene and GameScene with
    callbacks for scene transitions, and starts the game loop.

    Caveats:
        - Requires a real terminal.  Will raise RuntimeError in
          non-TTY environments unless InputManager fallback is
          configured.
        - The engine's ``run()`` blocks until quit.  Use Ctrl+C or
          select "Quit" from the menu.
        - AltScreen is not used here for simplicity.  In a real game,
          wrap the run loop in ``with AltScreen():`` to restore the
          terminal buffer on exit.
    """
    input_manager = InputManager()
    engine = Engine(
        title="wyby example", width=40, height=15, tps=30, input_manager=input_manager
    )

    def start_game() -> None:
        """Push GameScene onto the stack."""
        game_scene = GameScene(
            on_return_to_menu=lambda: engine.pop_scene(),
            width=40,
            height=15,
        )
        engine.push_scene(game_scene)

    menu = MainMenuScene(on_start_game=start_game, width=40, height=15)
    engine.push_scene(menu)

    try:
        engine.run()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
