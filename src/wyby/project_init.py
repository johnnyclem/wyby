"""Utilities for initializing a wyby game project with git, .gitignore, pyproject.toml, pre-commit config, LICENSE, CONTRIBUTING.md, .env.example, .editorconfig, and initial commit.

This module provides functions to scaffold a new wyby game project directory
with a git repository, a .gitignore tailored for Python-based terminal
game development, a ``pyproject.toml`` declaring the project's metadata,
dependencies, and ruff linting/formatting configuration, a
``.pre-commit-config.yaml`` for code-quality hooks, an MIT ``LICENSE``
file, a ``CONTRIBUTING.md`` guide, a ``.env.example`` file documenting
available development flags, and an ``.editorconfig`` for consistent
editor settings.

Caveats:
    - Requires ``git`` to be installed and available on the system PATH.
      On some minimal Docker images or CI environments, git may not be
      present. The functions raise ``GitNotFoundError`` in this case rather
      than producing a confusing subprocess error.
    - Calling ``init_git_repo`` on a path that is already inside a git
      repository is safe — ``git init`` on an existing repo is a no-op
      (it does not destroy history or configuration). A warning is logged
      when this happens so the caller is aware.
    - The generated ``.gitignore`` covers common Python, IDE, OS, and
      wyby-specific patterns. It intentionally does not include language-
      or framework-specific entries beyond Python (e.g., no Node, Rust,
      or Java patterns). Projects that mix languages should extend the
      file manually.
    - The generated ``pyproject.toml`` pins ``wyby`` as a dependency
      without an upper bound (``>=0.1.0``). Because wyby is pre-release
      software, breaking changes may occur. Game projects should pin to a
      specific version (e.g., ``wyby==0.1.0``) once stability matters.
    - The template uses ``setuptools`` as the build backend for
      familiarity, but game projects are not libraries and rarely need to
      be packaged. The ``pyproject.toml`` is primarily useful for
      dependency management via ``pip install -e .`` and for tool
      configuration (pytest, ruff).
    - Project names are normalised to lowercase with hyphens replaced by
      underscores to comply with PEP 508. Invalid characters (anything
      outside ``[a-zA-Z0-9._-]``) cause a ``ValueError``.
    - On Windows, ``git init`` may produce paths with backslashes. This
      module normalises paths with ``pathlib`` but does not attempt to
      resolve symlink or junction edge cases.
    - The generated ``.pre-commit-config.yaml`` references pinned versions
      of ruff and the pre-commit hooks repository. These versions will go
      stale over time — run ``pre-commit autoupdate`` periodically to pull
      the latest releases. The ``pre-commit`` tool itself is *not* a wyby
      dependency; it must be installed separately
      (``pip install pre-commit``) and activated with
      ``pre-commit install`` inside the project's git repo.
    - The generated ``LICENSE`` file uses the MIT license with a
      placeholder copyright holder (``<your name>``). The caller should
      replace this with the actual copyright holder name. The year
      defaults to the current year at generation time. Note that wyby
      itself is GPL-3.0-only — the MIT license is for game projects
      built *with* wyby, not for wyby itself. Game developers are free
      to choose any license compatible with GPL-3.0 for their projects.
    - The generated ``CONTRIBUTING.md`` provides generic contribution
      guidelines for a wyby game project. It references tooling set up
      by other scaffolding functions (pytest, ruff, pre-commit) so it
      should be generated *after* the rest of the project is in place.
      The file includes a caveats section highlighting wyby's pre-release
      status. Game projects with specialised contribution workflows
      (e.g. asset pipelines, playtesting protocols) should extend the
      file to cover those areas.
    - The generated ``.env.example`` documents environment variables
      that control wyby's development and debugging behaviour (log level,
      debug mode, FPS cap, save directory). It is a **template** — the
      actual ``.env`` file is gitignored and must be created by each
      developer by copying ``.env.example``. The ``.env.example`` file
      itself **must not** contain real secrets or credentials; it only
      holds placeholder/default values. wyby does not automatically read
      ``.env`` files at runtime — games must load them explicitly (e.g.
      via ``python-dotenv``) or export the variables in the shell.
    - The generated ``pyproject.toml`` includes ``[tool.ruff]``,
      ``[tool.ruff.lint]``, and ``[tool.ruff.format]`` sections that
      configure ruff as both linter and formatter. Ruff replaces Black
      (formatting) and flake8 (linting) in a single tool — there is no
      need to install Black separately. ``ruff format`` is
      Black-compatible. If both tools are run on the same codebase they
      may fight over minor edge cases; pick one. This template picks
      ruff.
    - The generated ``.editorconfig`` defines whitespace and encoding
      settings for editors that support the EditorConfig standard. It is
      *advisory* only — enforcement comes from ruff and the pre-commit
      hooks. The ``indent_size`` (4 for Python) and ``max_line_length``
      (88) values match ruff's defaults. If you change ruff's
      ``line-length`` or ``indent-width`` in ``pyproject.toml``, update
      ``.editorconfig`` to match so that editors and the formatter agree.
    - The initial commit function (``create_initial_commit``) uses
      ``git add .`` which stages **all** files in the working tree. Call
      it immediately after scaffolding — before adding other files — to
      keep the initial commit clean. It requires ``user.name`` and
      ``user.email`` to be configured in git (globally or locally); the
      function does not set these automatically to avoid overriding user
      preferences. If they are missing, ``git commit`` fails with a
      ``GitError``.
"""

from __future__ import annotations

import datetime
import logging
import re
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

# .gitignore content for a wyby game project.
# Covers Python artefacts, virtual environments, IDE files, OS metadata,
# testing/coverage output, distribution files, and wyby-specific patterns
# (e.g. save-game data that shouldn't be committed).
GITIGNORE_TEMPLATE = """\
# === Python ===
__pycache__/
*.py[cod]
*$py.class
*.so
*.egg-info/
*.egg
dist/
build/
*.whl

# === Virtual environments ===
.venv/
venv/
env/

# === IDE ===
.idea/
.vscode/
*.swp
*.swo
*~

# === OS ===
.DS_Store
Thumbs.db

# === Testing / coverage ===
.pytest_cache/
.coverage
htmlcov/
.mypy_cache/
.ruff_cache/

# === Distribution ===
*.tar.gz
*.zip

# === wyby game-specific ===
# Save files generated at runtime — typically JSON or msgpack.
# Developers should version-control save *schemas*, not save *data*.
saves/
*.save.json
*.save.msgpack

# Log files from wyby diagnostics / debug mode
*.log

# Environment files that may contain local configuration
.env
"""


# Valid PEP 508 project name: letters, digits, hyphens, underscores, dots.
_PROJECT_NAME_RE = re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9._-]*[a-zA-Z0-9])?$")

# pyproject.toml template for a new wyby game project.
#
# Caveats embedded as comments:
# - wyby is pinned with a floor version only (>=0.1.0). Pre-release software
#   may introduce breaking changes; pin tightly when stability matters.
# - The [project.scripts] section is commented out. Most terminal games are
#   run directly (`python -m mygame`) rather than installed as console scripts.
#   Uncomment and adjust if you want `pip install` to create a CLI entry point.
# - The src layout is recommended but not required. If you prefer a flat layout,
#   remove the [tool.setuptools.packages.find] section.
# - requires-python >= 3.10 matches wyby's own requirement. Using an older
#   Python will fail at install time with a clear error from pip.
PYPROJECT_TEMPLATE = """\
[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.build_meta"

[project]
name = "{project_name}"
version = "0.1.0"
description = ""
# wyby requires Python >= 3.10; your game inherits this constraint.
requires-python = ">=3.10"

# wyby is pinned with a minimum version only. Because wyby is pre-release
# software, breaking changes may occur before 1.0. Pin to an exact version
# (e.g. wyby==0.1.0) once you need reproducible builds.
dependencies = [
    "wyby>=0.1.0",
]

# Uncomment to create a console_scripts entry point:
# [project.scripts]
# {project_name} = "{project_name_underscored}.main:main"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]

# --- Ruff (linter + formatter) ---
# Ruff replaces both flake8 (linting) and Black (formatting) in a single tool.
# There is no need to install Black separately — ``ruff format`` is
# Black-compatible and significantly faster.
#
# Caveat: ruff's rule set and defaults evolve across releases. Pin ruff in
# your dev dependencies and review the changelog when upgrading.

[tool.ruff]
# Match wyby's own minimum Python version.
target-version = "py310"
# Line length 88 is the Black/ruff default. If you change this, also update
# .editorconfig so that editors and the formatter agree.
line-length = 88

[tool.ruff.lint]
# E/W = pycodestyle errors/warnings, F = pyflakes, I = isort-compatible
# import sorting, UP = pyupgrade (modernise syntax for target Python version),
# B = flake8-bugbear (common bug patterns).
# Caveat: adding more rule sets (e.g. "S" for bandit security checks) may
# surface new warnings in existing code. Enable incrementally and fix as you go.
select = ["E", "F", "W", "I", "UP", "B"]

[tool.ruff.format]
# Ruff's formatter is Black-compatible. These defaults match Black's style.
# Caveat: ruff format is not *identical* to Black in every edge case, but
# differences are rare and intentional. Do not run both tools on the same
# codebase — pick one. This template picks ruff.
quote-style = "double"
indent-style = "space"
"""


# .pre-commit-config.yaml template for a wyby game project.
#
# Caveats embedded as comments in the generated file:
# - Hook versions are pinned at generation time and will go stale. Run
#   ``pre-commit autoupdate`` periodically to keep them current.
# - ``pre-commit`` is NOT a wyby runtime dependency. It must be installed
#   separately (``pip install pre-commit``) and activated per-repo with
#   ``pre-commit install``.
# - The ruff hook handles both linting and formatting. If the project adds
#   additional tools (mypy, bandit, etc.), they should be added as new
#   repo entries rather than modifying the existing ones.
PRECOMMIT_CONFIG_TEMPLATE = """\
# Pre-commit hooks for wyby game projects.
#
# Caveats:
#   - Hook versions are pinned at file-generation time and will become
#     outdated. Run ``pre-commit autoupdate`` periodically.
#   - pre-commit must be installed separately: pip install pre-commit
#   - Activate hooks in this repo with: pre-commit install
#   - To run all hooks manually: pre-commit run --all-files

repos:
  # General file-hygiene hooks.
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-toml
      - id: check-added-large-files

  # Ruff — fast Python linter and formatter (replaces flake8 + black + isort).
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.8.6
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]
      - id: ruff-format
"""


# MIT license template for wyby game projects.
#
# Caveats:
# - The copyright holder defaults to "<your name>" — replace with the actual
#   author or organisation name. The placeholder is intentional so that
#   generated projects don't ship with an incorrect copyright line.
# - The year defaults to the current year at generation time. For multi-year
#   projects, convention is "2024-2026" but this is not legally required.
# - wyby itself is GPL-3.0-only. The MIT license here applies to game
#   projects built *with* wyby, not to wyby itself. The MIT license is
#   compatible with GPL-3.0: MIT-licensed game code can depend on
#   GPL-licensed wyby without conflict, but distributing the combined
#   work must respect the GPL terms for the wyby portions.
MIT_LICENSE_TEMPLATE = """\
MIT License

Copyright (c) {year} {copyright_holder}

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""


# CONTRIBUTING.md template for wyby game projects.
#
# Caveats:
# - The guide assumes the project was scaffolded with wyby's init_project()
#   and therefore has pyproject.toml, .pre-commit-config.yaml, and a src
#   layout. Projects with a non-standard setup should adjust accordingly.
# - The "Caveats" section in the generated file warns contributors about
#   wyby's pre-release status and the implications for API stability.
# - The file references `pip install pre-commit` and `pre-commit install`.
#   pre-commit is NOT a wyby dependency — contributors must install it
#   separately if they want to use the hooks.
# - The project name placeholder {project_name} is filled at generation
#   time. If the project is later renamed, the CONTRIBUTING.md must be
#   updated manually.
CONTRIBUTING_TEMPLATE = """\
# Contributing to {project_name}

Thank you for considering contributing to **{project_name}**! This document
explains how to set up a development environment and submit changes.

## Getting Started

1. **Clone the repository**

   ```bash
   git clone <repository-url>
   cd {project_name}
   ```

2. **Create a virtual environment**

   ```bash
   python -m venv .venv
   source .venv/bin/activate   # Linux / macOS
   .venv\\\\Scripts\\\\activate      # Windows
   ```

3. **Install in editable mode with dev dependencies**

   ```bash
   pip install -e .
   ```

4. **Install pre-commit hooks** *(optional but recommended)*

   ```bash
   pip install pre-commit
   pre-commit install
   ```

## Running Tests

```bash
pytest
```

## Code Style

This project uses [ruff](https://docs.astral.sh/ruff/) for linting and
formatting. If you installed the pre-commit hooks, ruff runs automatically
on every commit. You can also run it manually:

```bash
ruff check src/ tests/
ruff format src/ tests/
```

## Submitting Changes

1. Create a branch for your change.
2. Write tests for new functionality.
3. Make sure all tests pass and ruff reports no issues.
4. Open a pull request with a clear description of the change.

## Caveats

- **wyby is pre-release software.** The framework API may change without
  notice before version 1.0. If your contribution depends on wyby
  internals, be aware that those interfaces are not yet stable.
- **Licensing.** This project is licensed under MIT (see `LICENSE`), but
  wyby itself is GPL-3.0-only. Contributions to this game project are
  covered by the project's own license, not wyby's. If you copy code
  *from* wyby into this project, the GPL terms apply to that code.
- **Python version.** wyby requires Python >= 3.10. Do not use syntax or
  standard-library features that require a newer version unless the
  project's `requires-python` has been updated accordingly.
- **Save-file format.** wyby does not use pickle. If your contribution
  involves save/load functionality, use explicit serialisation
  (`to_save_data()` / `from_save_data()`) with JSON or msgpack.
- **No networking in MVP.** wyby's first release will not include
  networking support. Contributions that add multiplayer or online
  features should be discussed in an issue first.
"""


# .env.example template for wyby game projects.
#
# Caveats:
# - This file is a TEMPLATE. It documents available environment variables
#   with safe default values. Developers copy it to `.env` (which is
#   gitignored) and customise as needed.
# - wyby does NOT automatically read `.env` files at runtime. Games must
#   load them explicitly (e.g. with `python-dotenv`) or export the
#   variables in their shell before running.
# - NEVER put real secrets, API keys, or credentials in `.env.example`.
#   It is checked into version control and visible to everyone.
# - Variable names use the WYBY_ prefix to avoid collisions with other
#   tools. Game-specific variables should use a different prefix
#   (e.g. MYGAME_) to maintain clear namespacing.
# - The variables listed here correspond to planned wyby features. Some
#   may not be read by the framework yet (wyby is pre-release). They are
#   documented here so that game projects have a consistent pattern to
#   follow as the framework matures.
# .editorconfig template for wyby game projects.
#
# Caveats:
# - EditorConfig settings are only applied if the developer's editor or IDE
#   has EditorConfig support enabled. Most modern editors (VS Code, PyCharm,
#   Sublime Text, Vim/Neovim) support it natively or via a plugin, but there
#   is no guarantee. The settings here are *advisory* — they do not enforce
#   style at build time. Use ruff (or the pre-commit hooks) for enforcement.
# - The indent_size of 4 for Python files matches PEP 8 and ruff's default.
#   If the project changes ruff's indent-width (in pyproject.toml), update
#   the .editorconfig to match so that editors and the formatter agree.
# - The line length (max_line_length = 88) matches ruff's default, which is
#   inherited from Black. If ruff's line-length is changed in pyproject.toml,
#   update .editorconfig accordingly.
# - TOML, YAML, and JSON files use 2-space indentation by convention. This
#   is separate from Python's 4-space standard and should not be changed
#   without good reason.
# - Makefiles *require* tab indentation — this is a syntax rule, not a
#   preference. The tab setting for Makefiles must not be changed.
# - The ``root = true`` directive tells EditorConfig to stop searching
#   parent directories. Without it, settings from a parent project's
#   .editorconfig could leak in and override these values.
EDITORCONFIG_TEMPLATE = """\
# EditorConfig — consistent coding styles across editors and IDEs.
# See https://editorconfig.org for supported editors and plugins.
#
# Caveats:
#   - These settings are advisory. Your editor must support EditorConfig
#     (natively or via plugin) for them to take effect.
#   - For enforcement, rely on ruff (configured in pyproject.toml) and
#     the pre-commit hooks.
#   - If you change ruff's line-length or indent-width in pyproject.toml,
#     update the corresponding values here so editors and the formatter agree.

root = true

[*]
end_of_line = lf
insert_final_newline = true
trim_trailing_whitespace = true
charset = utf-8

[*.py]
indent_style = space
indent_size = 4
max_line_length = 88

[*.{toml,yaml,yml,json}]
indent_style = space
indent_size = 2

[Makefile]
indent_style = tab
"""


ENV_EXAMPLE_TEMPLATE = """\
# wyby development environment flags.
#
# Copy this file to `.env` and adjust values for your local setup.
# The `.env` file is gitignored — do NOT commit it.
#
# IMPORTANT: wyby does not auto-load .env files. Either:
#   - export these variables in your shell, or
#   - use python-dotenv (pip install python-dotenv) in your game's entry point:
#       from dotenv import load_dotenv; load_dotenv()
#
# NEVER put real secrets or credentials in .env.example — this file
# is checked into version control.

# --- Logging ---
# Log level for the wyby logger hierarchy.
# Values: DEBUG, INFO, WARNING, ERROR, CRITICAL
# Default: WARNING
# Caveat: This only takes effect if your game calls wyby.configure_logging()
# or reads this variable and passes it to the logging setup. wyby's library
# logger emits nothing by default (NullHandler).
WYBY_LOG_LEVEL=WARNING

# Optional log file path. When set, wyby.configure_logging() can direct
# output here instead of stderr. Relative paths resolve from the working
# directory. The directory must already exist.
# Caveat: Log files can grow indefinitely during long sessions. The
# generated .gitignore already excludes *.log files.
# WYBY_LOG_FILE=

# --- Debug / diagnostics ---
# Enable debug mode. When "1" or "true", games can enable extra diagnostics
# (e.g. FPS overlay, grid-coordinate display, entity bounding boxes).
# Caveat: Debug mode is advisory — it is up to each game to check this
# variable and act on it. wyby itself does not change behaviour based on
# this flag until the diagnostics module is implemented.
WYBY_DEBUG=0

# --- Rendering ---
# Target frames per second for the game loop.
# Caveat: This is a *cap*, not a guarantee. Actual FPS depends on terminal
# emulator, grid size, and style complexity. See SCOPE.md for realistic
# expectations (15-30 FPS on modern terminals).
WYBY_FPS=30

# --- Save / load ---
# Directory for save-game files (JSON or msgpack).
# Default: ./saves/
# Caveat: wyby does not use pickle for serialisation. Games must implement
# explicit to_save_data()/from_save_data() methods. See SCOPE.md.
WYBY_SAVE_DIR=saves/
"""


def _normalise_project_name(name: str) -> str:
    """Normalise a project name for use in pyproject.toml.

    Validates against PEP 508 naming rules and normalises hyphens to
    underscores for the Python package name.

    Args:
        name: The raw project name.

    Returns:
        The normalised name (lowercase, hyphens preserved for project name).

    Raises:
        ValueError: If *name* is empty or contains invalid characters.
    """
    if not name:
        raise ValueError("Project name must not be empty.")
    if not _PROJECT_NAME_RE.match(name):
        raise ValueError(
            f"Invalid project name {name!r}. Names must start and end with "
            "a letter or digit and contain only letters, digits, hyphens, "
            "underscores, or dots."
        )
    return name.lower()


class GitNotFoundError(Exception):
    """Raised when the ``git`` executable is not found on the system PATH."""


class GitError(Exception):
    """Raised when a ``git`` command fails with a non-zero exit code."""


def _check_git_available() -> str:
    """Return the path to the ``git`` executable, or raise ``GitNotFoundError``.

    Returns:
        The resolved path to the git binary.

    Raises:
        GitNotFoundError: If git is not installed or not on PATH.
    """
    git_path = shutil.which("git")
    if git_path is None:
        raise GitNotFoundError(
            "git is not installed or not found on PATH. "
            "Install git (https://git-scm.com/) and try again."
        )
    return git_path


def init_git_repo(path: str | Path) -> Path:
    """Initialise a git repository at *path*.

    If the directory does not exist it is created. If *path* is already
    inside a git repository, ``git init`` is still called (which is a
    safe no-op) and a warning is logged.

    Args:
        path: Directory in which to initialise the repository.

    Returns:
        The resolved ``Path`` of the initialised repository.

    Raises:
        GitNotFoundError: If git is not available.
        GitError: If ``git init`` exits with a non-zero return code.
    """
    git_bin = _check_git_available()
    repo_path = Path(path).resolve()
    repo_path.mkdir(parents=True, exist_ok=True)

    # Detect whether we are already inside a git repo so we can warn.
    try:
        result = subprocess.run(
            [git_bin, "-C", str(repo_path), "rev-parse", "--git-dir"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            logger.warning(
                "Path '%s' is already inside a git repository. "
                "git init will be a no-op.",
                repo_path,
            )
    except OSError:
        # If rev-parse itself fails to execute, we'll catch the real
        # error in the git-init call below.
        pass

    try:
        result = subprocess.run(
            [git_bin, "init", str(repo_path)],
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        raise GitError(f"Failed to execute git init: {exc}") from exc

    if result.returncode != 0:
        raise GitError(
            f"git init failed (exit {result.returncode}): {result.stderr.strip()}"
        )

    logger.info("Initialised git repository at %s", repo_path)
    return repo_path


def create_gitignore(path: str | Path, *, overwrite: bool = False) -> Path:
    """Write a ``.gitignore`` file suited for a wyby game project.

    The template includes patterns for Python artefacts, virtual
    environments, IDE files, OS metadata, testing output, and
    wyby-specific runtime files (saves, logs).

    Args:
        path: Directory in which to create the ``.gitignore`` file.
        overwrite: If ``True``, replace an existing ``.gitignore``.
            Defaults to ``False`` to avoid accidentally discarding
            user customisations.

    Returns:
        The ``Path`` of the written ``.gitignore`` file.

    Raises:
        FileExistsError: If a ``.gitignore`` already exists and
            *overwrite* is ``False``.
    """
    target_dir = Path(path).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    gitignore_path = target_dir / ".gitignore"

    if gitignore_path.exists() and not overwrite:
        raise FileExistsError(
            f".gitignore already exists at {gitignore_path}. "
            "Pass overwrite=True to replace it."
        )

    gitignore_path.write_text(GITIGNORE_TEMPLATE, encoding="utf-8")
    logger.info("Created .gitignore at %s", gitignore_path)
    return gitignore_path


def create_pyproject_toml(
    path: str | Path,
    project_name: str,
    *,
    overwrite: bool = False,
) -> Path:
    """Write a ``pyproject.toml`` for a wyby game project.

    The generated file declares ``wyby`` as a runtime dependency and uses
    setuptools with a ``src`` layout.

    Args:
        path: Directory in which to create ``pyproject.toml``.
        project_name: Name for the project. Must be a valid PEP 508 name
            (letters, digits, hyphens, underscores, dots). Will be
            normalised to lowercase.
        overwrite: If ``True``, replace an existing ``pyproject.toml``.
            Defaults to ``False`` to avoid discarding user edits.

    Returns:
        The ``Path`` of the written ``pyproject.toml``.

    Raises:
        ValueError: If *project_name* is empty or contains invalid characters.
        FileExistsError: If ``pyproject.toml`` already exists and
            *overwrite* is ``False``.

    Caveats:
        - The generated file pins ``wyby>=0.1.0`` without an upper bound.
          Because wyby is pre-release software, breaking changes may occur.
          Pin to a specific version once stability matters.
        - The ``[project.scripts]`` section is commented out. Uncomment it
          if you want ``pip install`` to create a console entry point.
    """
    normalised = _normalise_project_name(project_name)
    # Underscored form for Python package/module references.
    underscored = normalised.replace("-", "_")

    target_dir = Path(path).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    toml_path = target_dir / "pyproject.toml"

    if toml_path.exists() and not overwrite:
        raise FileExistsError(
            f"pyproject.toml already exists at {toml_path}. "
            "Pass overwrite=True to replace it."
        )

    content = PYPROJECT_TEMPLATE.format(
        project_name=normalised,
        project_name_underscored=underscored,
    )
    toml_path.write_text(content, encoding="utf-8")
    logger.info("Created pyproject.toml at %s", toml_path)
    return toml_path


def create_precommit_config(
    path: str | Path,
    *,
    overwrite: bool = False,
) -> Path:
    """Write a ``.pre-commit-config.yaml`` file for a wyby game project.

    The template configures ruff (linting + formatting) and common
    file-hygiene hooks from the ``pre-commit-hooks`` repository.

    Args:
        path: Directory in which to create the config file.
        overwrite: If ``True``, replace an existing config file.
            Defaults to ``False`` to avoid discarding user customisations.

    Returns:
        The ``Path`` of the written ``.pre-commit-config.yaml`` file.

    Raises:
        FileExistsError: If ``.pre-commit-config.yaml`` already exists
            and *overwrite* is ``False``.

    Caveats:
        - The ``pre-commit`` tool is **not** a wyby dependency. Install it
          separately (``pip install pre-commit``) and run
          ``pre-commit install`` to activate the hooks in your git repo.
        - Hook versions are pinned at generation time. Run
          ``pre-commit autoupdate`` periodically to keep them current.
        - The hooks require a git repository to function. Call
          :func:`init_git_repo` before ``pre-commit install``.
    """
    target_dir = Path(path).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    config_path = target_dir / ".pre-commit-config.yaml"

    if config_path.exists() and not overwrite:
        raise FileExistsError(
            f".pre-commit-config.yaml already exists at {config_path}. "
            "Pass overwrite=True to replace it."
        )

    config_path.write_text(PRECOMMIT_CONFIG_TEMPLATE, encoding="utf-8")
    logger.info("Created .pre-commit-config.yaml at %s", config_path)
    return config_path


def create_license_file(
    path: str | Path,
    *,
    copyright_holder: str = "<your name>",
    year: int | None = None,
    overwrite: bool = False,
) -> Path:
    """Write an MIT ``LICENSE`` file for a wyby game project.

    Args:
        path: Directory in which to create the ``LICENSE`` file.
        copyright_holder: Name of the copyright holder. Defaults to
            ``"<your name>"`` as a placeholder — callers should replace
            this with the actual author or organisation name.
        year: Copyright year. Defaults to the current year.
        overwrite: If ``True``, replace an existing ``LICENSE`` file.
            Defaults to ``False`` to avoid discarding user edits.

    Returns:
        The ``Path`` of the written ``LICENSE`` file.

    Raises:
        FileExistsError: If ``LICENSE`` already exists and *overwrite*
            is ``False``.

    Caveats:
        - wyby itself is GPL-3.0-only. This MIT license is for game
          projects built *with* wyby. MIT-licensed game code can depend
          on GPL-licensed wyby without conflict, but distributing the
          combined work must respect GPL terms for the wyby portions.
        - The default copyright holder ``"<your name>"`` is a placeholder.
          Replace it before publishing or distributing the project.
        - The year is set once at file-generation time and is not
          automatically updated in subsequent years.
    """
    if year is None:
        year = datetime.datetime.now(tz=datetime.timezone.utc).year

    target_dir = Path(path).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    license_path = target_dir / "LICENSE"

    if license_path.exists() and not overwrite:
        raise FileExistsError(
            f"LICENSE already exists at {license_path}. "
            "Pass overwrite=True to replace it."
        )

    content = MIT_LICENSE_TEMPLATE.format(
        year=year,
        copyright_holder=copyright_holder,
    )
    license_path.write_text(content, encoding="utf-8")
    logger.info("Created LICENSE at %s", license_path)
    return license_path


def create_contributing_md(
    path: str | Path,
    project_name: str,
    *,
    overwrite: bool = False,
) -> Path:
    """Write a ``CONTRIBUTING.md`` file for a wyby game project.

    The template provides setup instructions, testing and code-style
    guidance, and a caveats section highlighting wyby's pre-release
    status and licensing considerations.

    Args:
        path: Directory in which to create ``CONTRIBUTING.md``.
        project_name: Name of the project. Must be a valid PEP 508
            name. Will be normalised to lowercase.
        overwrite: If ``True``, replace an existing ``CONTRIBUTING.md``.
            Defaults to ``False`` to avoid discarding user edits.

    Returns:
        The ``Path`` of the written ``CONTRIBUTING.md`` file.

    Raises:
        ValueError: If *project_name* is empty or contains invalid characters.
        FileExistsError: If ``CONTRIBUTING.md`` already exists and
            *overwrite* is ``False``.

    Caveats:
        - The generated file assumes the project was scaffolded with
          wyby's ``init_project()`` (src layout, pyproject.toml,
          pre-commit config). Adjust if using a non-standard setup.
        - The caveats section warns contributors about wyby's
          pre-release API instability and GPL-3.0 licensing of wyby
          itself versus the game project's own license.
        - The file references ``pip install pre-commit`` — pre-commit
          is not a wyby dependency and must be installed separately.
    """
    normalised = _normalise_project_name(project_name)

    target_dir = Path(path).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    contributing_path = target_dir / "CONTRIBUTING.md"

    if contributing_path.exists() and not overwrite:
        raise FileExistsError(
            f"CONTRIBUTING.md already exists at {contributing_path}. "
            "Pass overwrite=True to replace it."
        )

    content = CONTRIBUTING_TEMPLATE.format(project_name=normalised)
    contributing_path.write_text(content, encoding="utf-8")
    logger.info("Created CONTRIBUTING.md at %s", contributing_path)
    return contributing_path


def create_env_example(
    path: str | Path,
    *,
    overwrite: bool = False,
) -> Path:
    """Write a ``.env.example`` file documenting dev flags for a wyby game project.

    The template lists environment variables that control logging, debug
    mode, rendering, and save behaviour. Developers copy this file to
    ``.env`` (which is gitignored) and adjust values for their local setup.

    Args:
        path: Directory in which to create the ``.env.example`` file.
        overwrite: If ``True``, replace an existing ``.env.example``.
            Defaults to ``False`` to avoid discarding user customisations.

    Returns:
        The ``Path`` of the written ``.env.example`` file.

    Raises:
        FileExistsError: If ``.env.example`` already exists and
            *overwrite* is ``False``.

    Caveats:
        - The ``.env.example`` is a **template** checked into version
          control. It must never contain real secrets or credentials.
        - wyby does not auto-load ``.env`` files. Games must load them
          explicitly (e.g. via ``python-dotenv``) or export the variables
          in the shell before running.
        - Some variables correspond to planned features that are not yet
          implemented. They are documented here so that projects have a
          consistent pattern to follow as the framework matures.
    """
    target_dir = Path(path).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    env_example_path = target_dir / ".env.example"

    if env_example_path.exists() and not overwrite:
        raise FileExistsError(
            f".env.example already exists at {env_example_path}. "
            "Pass overwrite=True to replace it."
        )

    env_example_path.write_text(ENV_EXAMPLE_TEMPLATE, encoding="utf-8")
    logger.info("Created .env.example at %s", env_example_path)
    return env_example_path


def create_editorconfig(
    path: str | Path,
    *,
    overwrite: bool = False,
) -> Path:
    """Write an ``.editorconfig`` file for a wyby game project.

    The template defines consistent whitespace, encoding, and indentation
    settings across editors and IDEs that support EditorConfig.

    Args:
        path: Directory in which to create the ``.editorconfig`` file.
        overwrite: If ``True``, replace an existing ``.editorconfig``.
            Defaults to ``False`` to avoid discarding user customisations.

    Returns:
        The ``Path`` of the written ``.editorconfig`` file.

    Raises:
        FileExistsError: If ``.editorconfig`` already exists and
            *overwrite* is ``False``.

    Caveats:
        - EditorConfig is only effective if the developer's editor has
          support enabled. Most modern editors do, but there is no
          guarantee. For *enforcement*, rely on ruff and pre-commit.
        - The ``max_line_length`` and ``indent_size`` values match ruff's
          defaults (88 / 4). If you change ruff's settings in
          ``pyproject.toml``, update ``.editorconfig`` to match.
        - Makefile entries **must** use tab indentation — this is a
          syntax rule, not a preference. Do not change it.
    """
    target_dir = Path(path).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    editorconfig_path = target_dir / ".editorconfig"

    if editorconfig_path.exists() and not overwrite:
        raise FileExistsError(
            f".editorconfig already exists at {editorconfig_path}. "
            "Pass overwrite=True to replace it."
        )

    editorconfig_path.write_text(EDITORCONFIG_TEMPLATE, encoding="utf-8")
    logger.info("Created .editorconfig at %s", editorconfig_path)
    return editorconfig_path


def create_initial_commit(
    path: str | Path,
    *,
    message: str = "Initial commit — wyby project skeleton",
) -> str:
    """Stage all files and create the initial git commit for a scaffolded project.

    This function should be called **after** :func:`init_project` (or the
    individual scaffolding functions) has generated all project files. It
    runs ``git add .`` followed by ``git commit`` with the given message.

    Args:
        path: Root directory of the git repository.
        message: Commit message. Defaults to a descriptive skeleton message.

    Returns:
        The short SHA of the created commit.

    Raises:
        GitNotFoundError: If git is not available.
        GitError: If ``git add`` or ``git commit`` fails (e.g. no files to
            commit, missing user configuration).

    Caveats:
        - Uses ``git add .`` which stages **all** untracked and modified
          files in the working tree. If extra files exist beyond the
          scaffolded ones, they will be included in the commit. Run this
          immediately after scaffolding — before adding other files — to
          keep the initial commit clean.
        - Requires git ``user.name`` and ``user.email`` to be configured
          (globally or locally). The function does **not** set these
          automatically to avoid overriding user preferences. If they are
          not configured, ``git commit`` will fail with a ``GitError``.
        - The commit is made on whatever branch ``git init`` created
          (typically ``main`` or ``master``, depending on the system's
          ``init.defaultBranch`` setting).
        - If the repository already has commits, this function will still
          create a new commit. It does not check for an empty history.
        - An empty commit message is rejected — ``git commit`` will fail.
    """
    git_bin = _check_git_available()
    repo_path = Path(path).resolve()

    if not (repo_path / ".git").is_dir():
        raise GitError(
            f"No git repository at {repo_path}. "
            "Call init_git_repo() or init_project() first."
        )

    # Stage all files.
    try:
        result = subprocess.run(
            [git_bin, "-C", str(repo_path), "add", "."],
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        raise GitError(f"Failed to execute git add: {exc}") from exc

    if result.returncode != 0:
        raise GitError(
            f"git add failed (exit {result.returncode}): "
            f"{result.stderr.strip()}"
        )

    # Create the commit.
    try:
        result = subprocess.run(
            [git_bin, "-C", str(repo_path), "commit", "-m", message],
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        raise GitError(f"Failed to execute git commit: {exc}") from exc

    if result.returncode != 0:
        raise GitError(
            f"git commit failed (exit {result.returncode}): "
            f"{result.stderr.strip()}"
        )

    # Extract the short SHA from the commit.
    try:
        sha_result = subprocess.run(
            [git_bin, "-C", str(repo_path), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
        )
        short_sha = sha_result.stdout.strip()
    except OSError:
        # Non-fatal — the commit was created, we just can't read the SHA.
        short_sha = ""

    logger.info(
        "Created initial commit %s at %s",
        short_sha,
        repo_path,
    )
    return short_sha


def init_project(
    path: str | Path,
    project_name: str | None = None,
    *,
    copyright_holder: str = "<your name>",
    overwrite_gitignore: bool = False,
    overwrite_pyproject: bool = False,
    overwrite_precommit: bool = False,
    overwrite_license: bool = False,
    overwrite_contributing: bool = False,
    overwrite_env_example: bool = False,
    overwrite_editorconfig: bool = False,
    commit: bool = False,
    commit_message: str = "Initial commit — wyby project skeleton",
) -> Path:
    """Initialise a wyby game project with git, config files, and scaffolding.

    Creates a git repository and writes ``.gitignore``, ``pyproject.toml``
    (with ruff linting/formatting configuration), ``.pre-commit-config.yaml``,
    ``LICENSE``, ``CONTRIBUTING.md``, ``.env.example``, and ``.editorconfig``.
    Optionally creates an initial git commit with all scaffolded files.

    This is a convenience wrapper that calls :func:`init_git_repo`,
    :func:`create_gitignore`, :func:`create_pyproject_toml`,
    :func:`create_precommit_config`, :func:`create_license_file`,
    :func:`create_contributing_md`, :func:`create_env_example`,
    :func:`create_editorconfig`, and (when *commit* is ``True``)
    :func:`create_initial_commit` in sequence.

    Args:
        path: Directory for the new project.
        project_name: Name for the project in ``pyproject.toml``. If
            ``None``, defaults to the directory name of *path*.
        copyright_holder: Passed through to :func:`create_license_file`.
        overwrite_gitignore: Passed through to :func:`create_gitignore`.
        overwrite_pyproject: Passed through to :func:`create_pyproject_toml`.
        overwrite_precommit: Passed through to :func:`create_precommit_config`.
        overwrite_license: Passed through to :func:`create_license_file`.
        overwrite_contributing: Passed through to :func:`create_contributing_md`.
        overwrite_env_example: Passed through to :func:`create_env_example`.
        overwrite_editorconfig: Passed through to :func:`create_editorconfig`.
        commit: If ``True``, create an initial git commit after scaffolding.
            Defaults to ``False`` to avoid surprises — the caller may want
            to review or modify files before committing.
        commit_message: Passed through to :func:`create_initial_commit`.

    Returns:
        The resolved ``Path`` of the project directory.

    Raises:
        GitNotFoundError: If git is not available.
        GitError: If ``git init`` fails, or if *commit* is ``True`` and
            the commit fails (e.g. missing ``user.name``/``user.email``).
        FileExistsError: If ``.gitignore``, ``pyproject.toml``,
            ``.pre-commit-config.yaml``, ``LICENSE``,
            ``CONTRIBUTING.md``, ``.env.example``, or ``.editorconfig``
            exists and the corresponding *overwrite_** flag is ``False``.
        ValueError: If *project_name* (or the inferred directory name)
            is not a valid PEP 508 project name.
    """
    repo_path = init_git_repo(path)
    create_gitignore(repo_path, overwrite=overwrite_gitignore)

    name = project_name if project_name is not None else repo_path.name
    create_pyproject_toml(repo_path, name, overwrite=overwrite_pyproject)

    create_precommit_config(repo_path, overwrite=overwrite_precommit)

    create_license_file(
        repo_path,
        copyright_holder=copyright_holder,
        overwrite=overwrite_license,
    )

    create_contributing_md(repo_path, name, overwrite=overwrite_contributing)

    create_env_example(repo_path, overwrite=overwrite_env_example)

    create_editorconfig(repo_path, overwrite=overwrite_editorconfig)

    if commit:
        create_initial_commit(repo_path, message=commit_message)

    logger.info("Initialised wyby project at %s", repo_path)
    return repo_path
