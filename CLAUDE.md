# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

wyby is a Python framework for building terminal-rendered 2D games. It uses Rich for rendering styled character grids and targets roguelikes, puzzle games, and interactive terminal demos. **Pre-release status** — very early development (v0.1.0dev0).

## Build & Development

```bash
# Activate the virtualenv (Python 3.14)
source .venv/bin/activate

# Install the package in editable mode
pip install -e .

# Run all tests
pytest

# Run a single test file
pytest tests/test_project_init.py

# Run a single test by name
pytest tests/test_project_init.py::TestInitGitRepo::test_creates_directory_and_git_repo

# Lint with ruff (available in .venv)
ruff check src/ tests/
```

## Architecture

Uses `src` layout (`src/wyby/`). Build system is setuptools with `pyproject.toml`.

**Planned runtime architecture** (from SCOPE.md — most modules don't exist yet):
```
Input  -->  Game Logic  -->  Scene/Entity State  -->  Renderer  -->  Terminal
```

Layers: Input (stdin keyboard polling) → Game Loop (fixed-timestep) → Scene Stack (push/pop scenes) → Entity Model (simple container, not full ECS) → Renderer (cell buffer → Rich `Live` display).

**Currently implemented:**
- `src/wyby/project_init.py` — Git repo initialization and .gitignore scaffolding for new game projects. Custom exceptions: `GitNotFoundError`, `GitError`.

**Planned modules** (see `SCOPE.md` for full details): `app.py`, `input.py`, `scene.py`, `entity.py`, `renderer.py`, `grid.py`, `color.py`, `save.py`, `diagnostics.py`, `_platform.py`.

## Key Design Decisions

- **Rich over curses**: Trades curses' efficient differential updates for Rich's cross-platform styling, Windows support without `windows-curses`, and composability with Rich renderables.
- **No system-wide input hooks**: Only reads from the process's own stdin. The `keyboard` library is explicitly excluded.
- **No pickle for save/load**: Games must implement explicit `to_save_data()`/`from_save_data()` with JSON or msgpack.
- **No networking in MVP**.

## Dependencies

- Runtime: Python >= 3.10, `rich` (not yet in pyproject.toml dependencies)
- Dev: `pytest`, `ruff`
- License: GPL-3.0-only
