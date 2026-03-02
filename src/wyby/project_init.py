"""Utilities for initializing a wyby game project with git and .gitignore.

This module provides functions to scaffold a new wyby game project directory
with a git repository and a .gitignore tailored for Python-based terminal
game development.

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
    - On Windows, ``git init`` may produce paths with backslashes. This
      module normalises paths with ``pathlib`` but does not attempt to
      resolve symlink or junction edge cases.
"""

from __future__ import annotations

import logging
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


def init_project(path: str | Path, *, overwrite_gitignore: bool = False) -> Path:
    """Initialise a wyby game project with a git repo and ``.gitignore``.

    This is a convenience wrapper that calls :func:`init_git_repo` and
    :func:`create_gitignore` in sequence.

    Args:
        path: Directory for the new project.
        overwrite_gitignore: Passed through to :func:`create_gitignore`.

    Returns:
        The resolved ``Path`` of the project directory.

    Raises:
        GitNotFoundError: If git is not available.
        GitError: If ``git init`` fails.
        FileExistsError: If ``.gitignore`` exists and *overwrite_gitignore*
            is ``False``.
    """
    repo_path = init_git_repo(path)
    create_gitignore(repo_path, overwrite=overwrite_gitignore)
    logger.info("Initialised wyby project at %s", repo_path)
    return repo_path
