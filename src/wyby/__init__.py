"""wyby — a Python framework for terminal-rendered 2D games.

wyby lets you define a grid of styled character cells, handle keyboard
input with a cross-platform abstraction, and organise game objects,
scenes, and state without building your own framework.

**Status: Pre-release (v0.1.0dev0).** The API is unstable and subject
to breaking changes. Nothing is available on PyPI yet.

Package structure::

    wyby/
        __init__.py      # This file — package root
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
``project_init`` is functional.
"""
