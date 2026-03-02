"""RuneTUI - A Python library for developing terminal-based (TUI) games.

RuneTUI provides building blocks to create interactive games in the terminal,
leveraging Rich for rendering. Users should be aware of terminal-specific
behaviors, input library limitations, and rendering inconsistencies across
emulators. No guarantees on frame rates or visual fidelity; performance
depends on terminal, hardware, and complexity of per-frame operations.
"""

__version__ = "0.1.0"

from runetui.engine import Engine, EngineConfig
from runetui.scene import Scene
from runetui.renderer import Renderer
from runetui.input_manager import InputManager
from runetui.entity import Entity
from runetui.components import Component, Position, Velocity
from runetui.sprite import Sprite
from runetui.widgets import Widget, Button, HealthBar
from runetui.collision import AABB, check_aabb_collision
from runetui.events import Event, KeyEvent, MouseEvent, EventQueue

__all__ = [
    "Engine",
    "EngineConfig",
    "Scene",
    "Renderer",
    "InputManager",
    "Entity",
    "Component",
    "Position",
    "Velocity",
    "Sprite",
    "Widget",
    "Button",
    "HealthBar",
    "AABB",
    "check_aabb_collision",
    "Event",
    "KeyEvent",
    "MouseEvent",
    "EventQueue",
]
