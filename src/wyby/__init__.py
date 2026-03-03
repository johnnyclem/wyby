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
        platform_info.py # Platform differences catalog (Windows vs Unix)
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
from wyby.animation import Animation, AnimationFrame
from wyby.component import Component
from wyby.dithering import (
    CELL_ASPECT_RATIO,
    correct_aspect_ratio,
    load_svg,
    prepare_for_terminal,
    quantize_for_terminal,
)
from wyby.entity import Entity
from wyby.position import Position
from wyby.sprite import Sprite, from_image, from_text
from wyby.transforms import (
    flip_h,
    flip_v,
    rotate_90,
    rotate_180,
    rotate_270,
    tint,
)
from wyby.velocity import Velocity
from wyby.diagnostics import (
    ColorSupport,
    FPSCounter,
    RenderTimer,
    TerminalCapabilities,
    detect_capabilities,
)
from wyby.event import Event, EventQueue
from wyby.input import InputManager, InputMode, KeyEvent, MouseEvent, parse_input_events, parse_key_events
from wyby.input_context import InputContext, InputContextStack
from wyby.keymap import KeyBinding, KeyMap
from wyby.grid import Cell, CellBuffer, DoubleBuffer, clip_to_terminal
from wyby.unicode import (
    char_width,
    contains_emoji,
    grapheme_string_width,
    grapheme_width,
    is_single_grapheme,
    is_wide_char,
    iter_grapheme_clusters,
    string_width,
)
from wyby.layer import Layer, LayerStack
from wyby.platform_info import (
    CATEGORIES as PLATFORM_CATEGORIES,
    PLATFORM_DIFFERENCES,
    PlatformDifference,
    PlatformInfo,
    format_platform_report,
    get_differences_by_category,
    get_platform_info,
)
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
from wyby.signal_handlers import SignalHandler
from wyby.transition import Cut, FadeTransition, SlideTransition, Transition
from wyby.font_variance import (
    DEFAULT_CELL_ASPECT_RATIO,
    FONT_VARIANCE_ISSUES,
    ISSUE_CATEGORIES as FONT_VARIANCE_CATEGORIES,
    CellGeometry,
    FontVarianceIssue,
    check_font_variance_warnings,
    estimate_cell_aspect_ratio,
    format_font_variance_report,
    get_issues_by_category as get_font_issues_by_category,
    get_issues_for_terminal,
    log_font_variance_warnings,
)
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
    "Animation",
    "AnimationFrame",
    "AltScreen",
    "HiddenCursor",
    "CELL_ASPECT_RATIO",
    "Cell",
    "CellBuffer",
    "correct_aspect_ratio",
    "clip_to_terminal",
    "Component",
    "ColorSupport",
    "Engine",
    "EngineConfig",
    "Entity",
    "Position",
    "Event",
    "EventQueue",
    "InputContext",
    "InputContextStack",
    "InputManager",
    "InputMode",
    "KeyBinding",
    "KeyEvent",
    "KeyMap",
    "MouseEvent",
    "FPSCounter",
    "Layer",
    "LayerStack",
    "LiveDisplay",
    "quantize_for_terminal",
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
    "is_single_grapheme",
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
    "prepare_for_terminal",
    "PLATFORM_CATEGORIES",
    "PLATFORM_DIFFERENCES",
    "PlatformDifference",
    "PlatformInfo",
    "show_cursor",
    "SignalHandler",
    "Sprite",
    "from_image",
    "from_text",
    "load_svg",
    "string_width",
    "Cut",
    "FadeTransition",
    "SlideTransition",
    "Transition",
    "Velocity",
    "flip_h",
    "flip_v",
    "rotate_90",
    "rotate_180",
    "rotate_270",
    "tint",
    "TERMINAL_CAVEATS",
    "TestCard",
    "build_test_card",
    "format_report",
    "format_platform_report",
    "get_differences_by_category",
    "get_platform_info",
    "CellGeometry",
    "DEFAULT_CELL_ASPECT_RATIO",
    "FontVarianceIssue",
    "FONT_VARIANCE_ISSUES",
    "FONT_VARIANCE_CATEGORIES",
    "check_font_variance_warnings",
    "estimate_cell_aspect_ratio",
    "format_font_variance_report",
    "get_font_issues_by_category",
    "get_issues_for_terminal",
    "log_font_variance_warnings",
]
