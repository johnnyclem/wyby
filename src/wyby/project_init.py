"""Utilities for initializing a wyby game project with git, .gitignore, pyproject.toml, pre-commit config, and LICENSE.

This module provides functions to scaffold a new wyby game project directory
with a git repository, a .gitignore tailored for Python-based terminal
game development, a ``pyproject.toml`` declaring the project's metadata
and dependencies, a ``.pre-commit-config.yaml`` for code-quality hooks,
and an MIT ``LICENSE`` file.

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


def init_project(
    path: str | Path,
    project_name: str | None = None,
    *,
    copyright_holder: str = "<your name>",
    overwrite_gitignore: bool = False,
    overwrite_pyproject: bool = False,
    overwrite_precommit: bool = False,
    overwrite_license: bool = False,
) -> Path:
    """Initialise a wyby game project with git, ``.gitignore``, ``pyproject.toml``, pre-commit config, and LICENSE.

    This is a convenience wrapper that calls :func:`init_git_repo`,
    :func:`create_gitignore`, :func:`create_pyproject_toml`,
    :func:`create_precommit_config`, and :func:`create_license_file`
    in sequence.

    Args:
        path: Directory for the new project.
        project_name: Name for the project in ``pyproject.toml``. If
            ``None``, defaults to the directory name of *path*.
        copyright_holder: Passed through to :func:`create_license_file`.
        overwrite_gitignore: Passed through to :func:`create_gitignore`.
        overwrite_pyproject: Passed through to :func:`create_pyproject_toml`.
        overwrite_precommit: Passed through to :func:`create_precommit_config`.
        overwrite_license: Passed through to :func:`create_license_file`.

    Returns:
        The resolved ``Path`` of the project directory.

    Raises:
        GitNotFoundError: If git is not available.
        GitError: If ``git init`` fails.
        FileExistsError: If ``.gitignore``, ``pyproject.toml``,
            ``.pre-commit-config.yaml``, or ``LICENSE`` exists and the
            corresponding *overwrite_** flag is ``False``.
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

    logger.info("Initialised wyby project at %s", repo_path)
    return repo_path
