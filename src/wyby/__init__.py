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

Most modules above are stubs awaiting implementation. Currently only
``project_init``, ``_logging``, ``app``, ``scene``, and ``resize``
are functional.
"""

from wyby._logging import configure_logging, setup_null_handler
from wyby.alt_screen import AltScreen, disable_alt_screen, enable_alt_screen
from wyby.app import Engine, QuitSignal
from wyby.diagnostics import FPSCounter
from wyby.event import Event, EventQueue
from wyby.resize import ResizeHandler, get_terminal_size
from wyby.scene import Scene, SceneStack

# Attach a NullHandler so that wyby's internal log messages are silently
# discarded unless the application (game) configures logging. This follows
# the Python library best practice:
# https://docs.python.org/3/howto/logging.html#configuring-logging-for-a-library
setup_null_handler()

__all__ = [
    "AltScreen",
    "Engine",
    "Event",
    "EventQueue",
    "FPSCounter",
    "QuitSignal",
    "ResizeHandler",
    "Scene",
    "SceneStack",
    "configure_logging",
    "disable_alt_screen",
    "enable_alt_screen",
    "get_terminal_size",
]
