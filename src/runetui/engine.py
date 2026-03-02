"""Core game engine for RuneTUI.

The Engine manages the game loop, scene stack, input, and rendering.
It uses a fixed-timestep update with variable rendering, which provides
consistent game logic regardless of frame rate.

Caveat: Actual frame rates depend heavily on terminal emulator performance,
Rich Live rendering overhead, and scene complexity. There are no guarantees
on frame rate consistency.
"""

from __future__ import annotations

import logging
import os
import signal
import time
from dataclasses import dataclass, field
from typing import Optional

from rich.console import Console
from rich.style import Style

from runetui.events import Event, EventQueue, EventType, KeyEvent
from runetui.input_manager import InputManager
from runetui.renderer import Layer, Renderer
from runetui.scene import Scene

logger = logging.getLogger(__name__)


@dataclass
class EngineConfig:
    """Configuration for the game engine."""

    title: str = "RuneTUI Game"
    width: int = 80
    height: int = 24
    target_fps: int = 30
    fixed_dt: float = 1.0 / 60.0
    debug: bool = False
    alt_screen: bool = True
    quit_keys: list[str] = field(default_factory=lambda: ["ESCAPE", "q"])
    show_fps: bool = False


class Engine:
    """Main game engine that drives the game loop.

    Usage::

        engine = Engine(EngineConfig(title="My Game", width=80, height=24))
        engine.push_scene(MyGameScene())
        engine.run()

    The game loop follows the input-update-render pattern:
    1. Poll input events
    2. Handle events in the active scene
    3. Update game logic with fixed timestep
    4. Render to the virtual buffer
    5. Present buffer to terminal

    Caveat: The loop uses time.sleep() for frame pacing, which has
    platform-dependent precision (typically 1-15ms). Combined with Rich
    Live rendering overhead, actual FPS may be lower than target_fps.
    """

    def __init__(self, config: Optional[EngineConfig] = None) -> None:
        self.config = config or EngineConfig()
        self._running = False
        self._scene_stack: list[Scene] = []

        # Set up console
        self._console = Console()

        # Core subsystems
        self.event_queue = EventQueue()
        self.renderer = Renderer(
            self.config.width, self.config.height, console=self._console
        )
        self.input_manager = InputManager(self.event_queue)

        # Timing
        self._frame_time: float = 1.0 / self.config.target_fps
        self._accumulator: float = 0.0
        self._last_time: float = 0.0
        self._fps: float = 0.0
        self._frame_count: int = 0
        self._fps_timer: float = 0.0

        logger.info("Engine initialized: %s (%dx%d)", self.config.title, self.config.width, self.config.height)

    @property
    def current_scene(self) -> Optional[Scene]:
        """The top scene on the stack, or None if empty."""
        if self._scene_stack:
            return self._scene_stack[-1]
        return None

    @property
    def fps(self) -> float:
        """Current frames per second (updated once per second)."""
        return self._fps

    # --- Scene stack management ---

    def push_scene(self, scene: Scene) -> None:
        """Push a scene onto the stack. It becomes the active scene.

        Calls on_exit on the previously active scene (if any) and
        on_enter on the new scene.
        """
        if self._scene_stack:
            self._scene_stack[-1].on_exit()
        scene.engine = self
        self._scene_stack.append(scene)
        scene.on_enter()
        logger.debug("Scene pushed: %s (stack depth: %d)", type(scene).__name__, len(self._scene_stack))

    def pop_scene(self) -> Optional[Scene]:
        """Remove and return the top scene. The next scene becomes active.

        Calls on_exit on the removed scene and on_enter on the new top scene.
        If the stack becomes empty, the engine will stop.
        """
        if not self._scene_stack:
            return None
        scene = self._scene_stack.pop()
        scene.on_exit()
        scene.engine = None
        if self._scene_stack:
            self._scene_stack[-1].on_enter()
        else:
            logger.info("Scene stack empty — engine will stop")
            self._running = False
        logger.debug("Scene popped: %s (stack depth: %d)", type(scene).__name__, len(self._scene_stack))
        return scene

    def replace_scene(self, scene: Scene) -> None:
        """Replace the top scene with a new one.

        Equivalent to pop + push but without triggering the intermediate
        on_enter of the scene below.
        """
        if self._scene_stack:
            old = self._scene_stack.pop()
            old.on_exit()
            old.engine = None
        scene.engine = self
        self._scene_stack.append(scene)
        scene.on_enter()
        logger.debug("Scene replaced with: %s", type(scene).__name__)

    # --- Game loop ---

    def run(self) -> None:
        """Start the game loop.

        Blocks until the engine is stopped (via quit key, empty scene stack,
        or exception). Handles graceful shutdown including terminal restoration.
        """
        if not self._scene_stack:
            logger.error("Cannot run: no scenes on the stack")
            return

        self._running = True
        self._last_time = time.monotonic()

        # Install resize handler
        self._install_resize_handler()

        try:
            self.input_manager.start()
            self.renderer.hide_cursor()
            self.renderer.start()

            logger.info("Game loop started")
            while self._running:
                self._tick()

        except KeyboardInterrupt:
            logger.info("KeyboardInterrupt received — shutting down")
        except Exception:
            logger.exception("Unhandled exception in game loop")
        finally:
            self._shutdown()

    def stop(self) -> None:
        """Signal the engine to stop after the current frame."""
        self._running = False

    def _tick(self) -> None:
        """Execute one frame: input -> update -> render."""
        now = time.monotonic()
        dt = now - self._last_time
        self._last_time = now

        # Cap delta to avoid spiral of death
        if dt > 0.25:
            dt = 0.25

        # --- Input phase ---
        self.input_manager.poll()
        self._process_events()

        # --- Update phase (fixed timestep) ---
        self._accumulator += dt
        while self._accumulator >= self.config.fixed_dt:
            scene = self.current_scene
            if scene:
                scene.update(self.config.fixed_dt)
                scene.remove_dead_entities()
            self._accumulator -= self.config.fixed_dt

        # --- Render phase ---
        self.renderer.clear_buffer()
        scene = self.current_scene
        if scene:
            scene.render(self.renderer)

        # FPS counter overlay
        if self.config.show_fps or self.config.debug:
            self._draw_fps()

        self.renderer.present()

        # --- FPS tracking ---
        self._frame_count += 1
        self._fps_timer += dt
        if self._fps_timer >= 1.0:
            self._fps = self._frame_count / self._fps_timer
            self._frame_count = 0
            self._fps_timer = 0.0

        # --- Frame pacing ---
        elapsed = time.monotonic() - now
        sleep_time = self._frame_time - elapsed
        if sleep_time > 0:
            time.sleep(sleep_time)

    def _process_events(self) -> None:
        """Drain the event queue and route events to the active scene."""
        scene = self.current_scene
        while self.event_queue:
            event = self.event_queue.poll()
            if event is None:
                break

            # Check for quit
            if event.event_type == EventType.QUIT:
                self._running = False
                return

            if isinstance(event, KeyEvent) and event.key in self.config.quit_keys:
                self._running = False
                return

            # Handle Ctrl+C
            if isinstance(event, KeyEvent) and event.key == "\x03":
                self._running = False
                return

            # Route to scene
            if scene:
                scene.handle_event(event)

    def _draw_fps(self) -> None:
        """Draw FPS counter in the top-right corner."""
        fps_text = f"FPS: {self._fps:.0f}"
        x = self.config.width - len(fps_text) - 1
        self.renderer.draw_text(
            x, 0, fps_text,
            style=Style(color="yellow", bold=True),
            layer=Layer.UI,
        )

    def _install_resize_handler(self) -> None:
        """Install SIGWINCH handler for terminal resize events.

        Caveat: SIGWINCH is Unix-only. On Windows, resize detection is not
        automatically handled. Some terminal multiplexers (tmux, screen)
        may delay or suppress resize signals.
        """
        try:
            def _on_resize(signum, frame):
                try:
                    size = os.get_terminal_size()
                    scene = self.current_scene
                    if scene:
                        scene.on_resize(size.columns, size.lines)
                except Exception:
                    pass

            signal.signal(signal.SIGWINCH, _on_resize)
        except (AttributeError, OSError):
            # SIGWINCH not available (e.g., Windows)
            pass

    def _shutdown(self) -> None:
        """Clean up all subsystems."""
        self.renderer.stop()
        self.renderer.show_cursor()
        self.input_manager.stop()
        logger.info("Engine shut down")
