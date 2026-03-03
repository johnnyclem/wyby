"""Example: Minimal hello-world scene.

The simplest possible wyby scene — renders "Hello, World!" centred on
a :class:`~wyby.grid.CellBuffer` with a single styled entity.  This is
the recommended starting point for new users exploring the framework.

Run this example::

    python examples/hello_world.py

Caveats:
    - This example requires a real terminal (TTY) for keyboard input.
      It will not work when stdin is piped or in CI environments
      without a TTY.  Press ``q`` or ``Escape`` to quit, or use
      Ctrl+C.
    - The greeting text is rendered via :meth:`CellBuffer.put_text`,
      which writes individual character cells.  Terminal cells are
      roughly 1:2 aspect ratio (taller than wide), so the text
      occupies a wider visual area horizontally than you might expect
      from the column count.
    - ``Scene.render()`` writes to a CellBuffer stored as an attribute
      on the scene.  The Engine's tick loop calls ``render()`` each
      tick but does **not** automatically present the buffer to the
      terminal — that wiring is the game's responsibility via callbacks
      or a future renderer integration.  This example uses the
      Engine's built-in LiveDisplay for frame output.
    - The buffer is cleared and fully redrawn every frame.  For a
      static scene like this the cost is negligible, but be aware
      that wyby does not perform dirty-region tracking.
    - AltScreen is not used here for simplicity.  In a real game,
      wrap the run loop in ``with AltScreen():`` to restore the
      terminal buffer on exit.
"""

from __future__ import annotations

from wyby.app import Engine, QuitSignal
from wyby.grid import CellBuffer
from wyby.input import InputManager, KeyEvent
from wyby.scene import Scene


class HelloWorldScene(Scene):
    """A minimal scene that displays a centred greeting.

    Renders "Hello, World!" in bright green text at the centre of the
    buffer, with a brief instruction line below.

    Args:
        width: Buffer width in character columns.
        height: Buffer height in character rows.
        message: The greeting text to display.  Defaults to
            ``"Hello, World!"``.

    Caveats:
        - The message is centred by computing ``(width - len(message)) // 2``.
          This uses Python ``len()``, which counts codepoints, not display
          columns.  For ASCII text this is correct.  For strings containing
          wide characters (CJK, emoji), use :func:`wyby.unicode.string_width`
          for accurate centring.
        - The scene does not handle terminal resize.  If the terminal
          is smaller than the buffer, content will be clipped by
          CellBuffer's silent out-of-bounds behaviour.
        - There is no game state or entity management here.  This is
          intentionally the simplest possible scene to demonstrate the
          scene lifecycle (``update`` + ``render``).
    """

    def __init__(
        self,
        width: int = 40,
        height: int = 12,
        message: str = "Hello, World!",
    ) -> None:
        super().__init__()
        self._width = width
        self._height = height
        self._message = message
        self.buffer = CellBuffer(width, height)

    @property
    def message(self) -> str:
        """The greeting text displayed by this scene."""
        return self._message

    def handle_events(self, events: list) -> None:
        """Quit on ``q``, ``Escape``, or Ctrl+C.

        Caveats:
            - ``QuitSignal`` is raised directly from ``handle_events``,
              which propagates through the engine's tick and triggers
              a clean shutdown.  This is acceptable for quit handling
              but avoid mutating the scene stack from ``handle_events``
              — use ``update()`` for that.
            - Only ``KeyEvent`` instances are inspected; all other
              event types are silently ignored.
        """
        for event in events:
            if isinstance(event, KeyEvent) and event.key in ("q", "escape"):
                raise QuitSignal

    def update(self, dt: float) -> None:
        """No-op — this scene has no dynamic state."""

    def render(self) -> None:
        """Draw the greeting text centred in the buffer.

        Caveats:
            - ``render()`` must not modify game state — it is a pure
              read of the scene's current state.
            - The buffer is cleared every frame.  For a static message
              this is redundant work but keeps the pattern consistent
              with dynamic scenes.
        """
        self.buffer.clear()

        # Centre the greeting horizontally and vertically.
        msg = self._message
        msg_x = max(0, (self._width - len(msg)) // 2)
        msg_y = self._height // 2
        self.buffer.put_text(msg_x, msg_y, msg, fg="bright_green", bold=True)

        # Instruction line below the greeting.
        hint = "Press q or Esc to quit"
        hint_x = max(0, (self._width - len(hint)) // 2)
        self.buffer.put_text(hint_x, msg_y + 2, hint, fg="bright_black")


def main() -> None:
    """Run the hello-world example.

    Creates an Engine, pushes a :class:`HelloWorldScene`, and starts
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
        title="hello world", width=40, height=12, tps=30, input_manager=input_manager
    )
    scene = HelloWorldScene(width=40, height=12)
    engine.push_scene(scene)

    try:
        engine.run()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
