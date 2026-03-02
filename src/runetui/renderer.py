"""Rendering system for RuneTUI using Rich.

Caveat: Rich's Live display refresh can introduce flicker, latency, and CPU
overhead, especially with complex styling or large buffers. Performance depends
heavily on the terminal emulator. True double-buffering is not possible in a
terminal — this implementation uses a virtual buffer that is composited and
pushed via Live.update() each frame.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional

from rich.console import Console
from rich.live import Live
from rich.style import Style
from rich.text import Text

logger = logging.getLogger(__name__)


class Layer(IntEnum):
    """Render layer ordering. Lower values render first (behind)."""

    BACKGROUND = 0
    ENTITIES = 10
    UI = 20


@dataclass
class Cell:
    """A single cell in the virtual buffer."""

    char: str = " "
    style: Style = field(default_factory=Style)
    layer: Layer = Layer.BACKGROUND


class Renderer:
    """Manages a virtual character buffer and presents it via Rich Live.

    The buffer is a 2D grid of Cell objects. Each frame:
    1. clear_buffer() resets all cells
    2. draw_text() / draw calls write into the buffer
    3. present() composites the buffer into a Rich Text and pushes to Live

    Caveat: Live.update() has inherent overhead. Complex scenes with many styled
    cells will be slower. Terminal emulators vary in rendering speed.
    """

    def __init__(self, width: int, height: int, console: Optional[Console] = None) -> None:
        self.width = width
        self.height = height
        self.console = console or Console()
        self._live: Optional[Live] = None
        self._buffer: list[list[Cell]] = []
        self._render_time: float = 0.0
        self.clear_buffer()

    def _detect_color_support(self) -> str:
        """Detect terminal color support level.

        Caveat: Detection is best-effort. Some terminals misreport capabilities.
        Rich handles most fallback internally, but visual output may differ
        from expectations.
        """
        if self.console.color_system == "truecolor":
            return "truecolor"
        elif self.console.color_system == "256":
            return "256"
        elif self.console.color_system == "standard":
            return "16"
        return "none"

    def clear_buffer(self) -> None:
        """Reset the virtual buffer to empty space."""
        self._buffer = [
            [Cell() for _ in range(self.width)] for _ in range(self.height)
        ]

    def draw_text(
        self,
        x: int,
        y: int,
        text: str,
        style: Optional[Style] = None,
        layer: Layer = Layer.ENTITIES,
    ) -> None:
        """Write text into the buffer at a position.

        Characters outside the buffer bounds are clipped silently.
        Caveat: Wide Unicode characters (CJK, emoji) may occupy two cells but
        this method treats each character as one cell. Use with care for
        non-ASCII content.
        """
        if y < 0 or y >= self.height:
            return
        resolved_style = style or Style()
        for i, ch in enumerate(text):
            col = x + i
            if 0 <= col < self.width:
                cell = self._buffer[y][col]
                # Only overwrite if the new draw is on a higher or equal layer
                if layer >= cell.layer:
                    cell.char = ch
                    cell.style = resolved_style
                    cell.layer = layer

    def draw_rect(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        char: str = " ",
        style: Optional[Style] = None,
        layer: Layer = Layer.BACKGROUND,
    ) -> None:
        """Fill a rectangle in the buffer."""
        resolved_style = style or Style()
        for row in range(y, y + height):
            for col in range(x, x + width):
                if 0 <= row < self.height and 0 <= col < self.width:
                    cell = self._buffer[row][col]
                    if layer >= cell.layer:
                        cell.char = char
                        cell.style = resolved_style
                        cell.layer = layer

    def _compose_buffer(self) -> Text:
        """Convert the virtual buffer into a Rich Text object for display."""
        output = Text()
        for row_idx, row in enumerate(self._buffer):
            for cell in row:
                output.append(cell.char, style=cell.style)
            if row_idx < self.height - 1:
                output.append("\n")
        return output

    def start(self) -> None:
        """Begin Live display. Call before the game loop."""
        self._live = Live(
            console=self.console,
            refresh_per_second=30,
            screen=True,
        )
        self._live.start()
        logger.debug("Renderer started (color: %s)", self._detect_color_support())

    def present(self) -> None:
        """Push the current buffer to the terminal via Live.update().

        Caveat: This is the main rendering bottleneck. Each call rebuilds
        a Rich Text from the buffer and updates the Live display.
        """
        if self._live is None:
            return
        start = time.monotonic()
        composed = self._compose_buffer()
        self._live.update(composed)
        self._render_time = time.monotonic() - start

    @property
    def last_render_time(self) -> float:
        """Time in seconds for the last present() call."""
        return self._render_time

    def stop(self) -> None:
        """Stop the Live display. Call after the game loop."""
        if self._live is not None:
            self._live.stop()
            self._live = None
            logger.debug("Renderer stopped")

    def hide_cursor(self) -> None:
        """Hide the terminal cursor."""
        self.console.show_cursor(False)

    def show_cursor(self) -> None:
        """Show the terminal cursor."""
        self.console.show_cursor(True)
