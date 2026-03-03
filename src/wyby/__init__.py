"""wyby — a Python framework for terminal-rendered 2D games.

wyby lets you define a grid of styled character cells, handle keyboard
input with a cross-platform abstraction, and organise game objects,
scenes, and state without building your own framework.

**Status: Pre-release (v0.1.0dev0).** The API is unstable and subject
to breaking changes. Nothing is available on PyPI yet.

Package structure::

    wyby/
        __init__.py      # This file — package root
        _logging.py      # Logging configuration (internal)
        app.py           # Application entry point, game loop
        input.py         # Keyboard input abstraction
        scene.py         # Scene base class, scene stack
        entity.py        # Entity container, spatial queries
        renderer.py      # Cell buffer, Rich renderable generation
        grid.py          # Grid/cell types, coordinate helpers
        color.py         # Colour utilities, palette management
        save.py          # Schema-based save/load helpers
        diagnostics.py   # FPS counter, tick timing, capability reporting
        _platform.py     # Platform-specific input backends (internal)
        project_init.py  # Project scaffolding utilities

Most modules above are stubs awaiting implementation. Currently
``project_init``, ``_logging``, ``app``, ``scene``, ``resize``,
and ``renderer`` are functional.
"""

from wyby._logging import configure_logging, setup_null_handler
from wyby.alt_screen import AltScreen, disable_alt_screen, enable_alt_screen
from wyby.cursor import HiddenCursor, hide_cursor, is_cursor_hidden, show_cursor
from wyby.app import Engine, EngineConfig, QuitSignal
from wyby.color import (
    color_system_for_support,
    downgrade_color,
    nearest_ansi16,
    nearest_ansi256,
    parse_color,
)
from wyby.diagnostics import (
    ColorSupport,
    FPSCounter,
    RenderTimer,
    TerminalCapabilities,
    detect_capabilities,
)
from wyby.event import Event, EventQueue
from wyby.input import InputManager, InputMode, KeyEvent, MouseEvent, parse_input_events, parse_key_events
from wyby.grid import Cell, CellBuffer, DoubleBuffer, clip_to_terminal
from wyby.unicode import (
    char_width,
    contains_emoji,
    grapheme_string_width,
    grapheme_width,
    is_wide_char,
    iter_grapheme_clusters,
    string_width,
)
from wyby.layer import Layer, LayerStack
from wyby.mouse_warnings import (
    check_mouse_drag_warning,
    check_mouse_hover_warning,
    log_mouse_warnings,
)
from wyby.render_warnings import (
    RenderCost,
    check_emoji_warning,
    check_flicker_risk,
    estimate_render_cost,
    log_emoji_warning,
    log_render_cost,
)
from wyby.renderer import LiveDisplay, Renderer, create_console
from wyby.resize import ResizeHandler, get_terminal_size
from wyby.scene import Scene, SceneStack
from wyby.terminal_test import (
    TERMINAL_CAVEATS,
    TestCard,
    build_test_card,
    format_report,
)

# Attach a NullHandler so that wyby's internal log messages are silently
# discarded unless the application (game) configures logging. This follows
# the Python library best practice:
# https://docs.python.org/3/howto/logging.html#configuring-logging-for-a-library
setup_null_handler()

__all__ = [
    "AltScreen",
    "HiddenCursor",
    "Cell",
    "CellBuffer",
    "clip_to_terminal",
    "ColorSupport",
    "Engine",
    "EngineConfig",
    "Event",
    "EventQueue",
    "InputManager",
    "InputMode",
    "KeyEvent",
    "MouseEvent",
    "FPSCounter",
    "Layer",
    "LayerStack",
    "LiveDisplay",
    "QuitSignal",
    "RenderCost",
    "Renderer",
    "RenderTimer",
    "ResizeHandler",
    "Scene",
    "SceneStack",
    "TerminalCapabilities",
    "char_width",
    "check_emoji_warning",
    "color_system_for_support",
    "contains_emoji",
    "grapheme_string_width",
    "grapheme_width",
    "check_flicker_risk",
    "check_mouse_drag_warning",
    "check_mouse_hover_warning",
    "configure_logging",
    "create_console",
    "detect_capabilities",
    "DoubleBuffer",
    "disable_alt_screen",
    "downgrade_color",
    "enable_alt_screen",
    "estimate_render_cost",
    "get_terminal_size",
    "hide_cursor",
    "is_cursor_hidden",
    "is_wide_char",
    "iter_grapheme_clusters",
    "log_emoji_warning",
    "log_mouse_warnings",
    "log_render_cost",
    "nearest_ansi16",
    "nearest_ansi256",
    "parse_input_events",
    "parse_key_events",
    "parse_color",
    "show_cursor",
    "string_width",
    "TERMINAL_CAVEATS",
    "TestCard",
    "build_test_card",
    "format_report",
]
