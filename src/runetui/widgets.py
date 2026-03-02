"""UI widget layer for RuneTUI.

Widgets are drawn on the UI layer (above game entities). They handle mouse/key
focus and provide basic interactive elements like buttons and health bars.

Caveat: Layout is manual (absolute positioning). There is no flex/grid layout
system in the MVP. Widget rendering uses the same buffer as the game, so
widgets must be drawn after game entities to appear on top.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Callable, Optional

from rich.style import Style

from runetui.events import Event, EventType, KeyEvent, MouseEvent
from runetui.renderer import Layer, Renderer

logger = logging.getLogger(__name__)


class Widget(ABC):
    """Base class for UI widgets.

    Widgets have a position, size, and can be focused for input routing.
    """

    def __init__(self, x: int, y: int, width: int, height: int) -> None:
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.focused: bool = False
        self.visible: bool = True

    def contains(self, px: int, py: int) -> bool:
        """Check if a point is within this widget's bounds."""
        return self.x <= px < self.x + self.width and self.y <= py < self.y + self.height

    @abstractmethod
    def handle_event(self, event: Event) -> bool:
        """Process an event. Return True if the event was consumed."""
        ...

    @abstractmethod
    def render(self, renderer: Renderer) -> None:
        """Draw this widget into the renderer buffer on the UI layer."""
        ...


class Button(Widget):
    """A clickable text button.

    Renders a labeled rectangle. Triggers on_click when clicked with mouse
    or when focused and Enter/Space is pressed.
    """

    def __init__(
        self,
        x: int,
        y: int,
        label: str,
        on_click: Optional[Callable[[], None]] = None,
        style: Optional[Style] = None,
        focused_style: Optional[Style] = None,
    ) -> None:
        super().__init__(x, y, width=len(label) + 4, height=3)
        self.label = label
        self.on_click = on_click
        self.style = style or Style(color="white", bgcolor="blue")
        self.focused_style = focused_style or Style(color="white", bgcolor="cyan", bold=True)

    def handle_event(self, event: Event) -> bool:
        if isinstance(event, MouseEvent):
            if self.contains(event.x, event.y) and event.button == "left":
                if self.on_click:
                    self.on_click()
                return True
        elif isinstance(event, KeyEvent) and self.focused:
            if event.key in ("\r", "\n", " "):
                if self.on_click:
                    self.on_click()
                return True
        return False

    def render(self, renderer: Renderer) -> None:
        if not self.visible:
            return
        current_style = self.focused_style if self.focused else self.style
        # Draw button background
        renderer.draw_rect(
            self.x, self.y, self.width, self.height, char=" ", style=current_style, layer=Layer.UI
        )
        # Draw label centered
        label_x = self.x + (self.width - len(self.label)) // 2
        label_y = self.y + self.height // 2
        renderer.draw_text(label_x, label_y, self.label, style=current_style, layer=Layer.UI)


class HealthBar(Widget):
    """A horizontal health/progress bar.

    Displays current/max as a filled bar with optional label.
    """

    def __init__(
        self,
        x: int,
        y: int,
        width: int,
        current: float = 100.0,
        maximum: float = 100.0,
        fill_char: str = "\u2588",
        empty_char: str = "\u2591",
        fill_style: Optional[Style] = None,
        empty_style: Optional[Style] = None,
        label: str = "",
    ) -> None:
        super().__init__(x, y, width, height=1)
        self.current = current
        self.maximum = maximum
        self.fill_char = fill_char
        self.empty_char = empty_char
        self.fill_style = fill_style or Style(color="green")
        self.empty_style = empty_style or Style(color="red")
        self.label = label

    def handle_event(self, event: Event) -> bool:
        return False

    @property
    def fraction(self) -> float:
        if self.maximum <= 0:
            return 0.0
        return max(0.0, min(1.0, self.current / self.maximum))

    def render(self, renderer: Renderer) -> None:
        if not self.visible:
            return
        bar_width = self.width
        if self.label:
            renderer.draw_text(self.x, self.y, self.label, layer=Layer.UI)
            bar_start = self.x + len(self.label) + 1
            bar_width = self.width - len(self.label) - 1
        else:
            bar_start = self.x

        filled = int(bar_width * self.fraction)
        empty = bar_width - filled
        renderer.draw_text(
            bar_start, self.y, self.fill_char * filled, style=self.fill_style, layer=Layer.UI
        )
        renderer.draw_text(
            bar_start + filled,
            self.y,
            self.empty_char * empty,
            style=self.empty_style,
            layer=Layer.UI,
        )
