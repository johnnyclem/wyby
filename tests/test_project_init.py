"""Tests for wyby.project_init — git, .gitignore, and pyproject.toml initialisation."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from wyby.project_init import (
    GITIGNORE_TEMPLATE,
    PYPROJECT_TEMPLATE,
    GitError,
    GitNotFoundError,
    _normalise_project_name,
    create_gitignore,
    create_pyproject_toml,
    init_git_repo,
    init_project,
)


# ---------------------------------------------------------------------------
# init_git_repo
# ---------------------------------------------------------------------------


class TestInitGitRepo:
    """Tests for init_git_repo()."""

    def test_creates_directory_and_git_repo(self, tmp_path: Path) -> None:
        target = tmp_path / "new_project"
        result = init_git_repo(target)

        assert result == target.resolve()
        assert (target / ".git").is_dir()

    def test_existing_empty_directory(self, tmp_path: Path) -> None:
        target = tmp_path / "existing"
        target.mkdir()
        result = init_git_repo(target)

        assert result == target.resolve()
        assert (target / ".git").is_dir()

    def test_already_a_git_repo_is_safe(self, tmp_path: Path) -> None:
        """git init on an existing repo is a no-op — no data loss."""
        target = tmp_path / "repo"
        target.mkdir()
        subprocess.run(["git", "init", str(target)], check=True, capture_output=True)
        # Create a file and commit so we can verify history is preserved.
        (target / "hello.txt").write_text("hello")
        subprocess.run(
            ["git", "-C", str(target), "add", "."], check=True, capture_output=True
        )
        subprocess.run(
            ["git", "-C", str(target), "commit", "-m", "initial"],
            check=True,
            capture_output=True,
            env=_git_env(),
        )

        # Re-initialise — should not destroy the commit.
        init_git_repo(target)

        log = subprocess.run(
            ["git", "-C", str(target), "log", "--oneline"],
            capture_output=True,
            text=True,
        )
        assert "initial" in log.stdout

    def test_nested_directory_creation(self, tmp_path: Path) -> None:
        target = tmp_path / "a" / "b" / "c"
        result = init_git_repo(target)

        assert result == target.resolve()
        assert (target / ".git").is_dir()

    def test_returns_resolved_path(self, tmp_path: Path) -> None:
        target = tmp_path / "project" / ".." / "project"
        result = init_git_repo(target)

        assert result == (tmp_path / "project").resolve()

    def test_git_not_found_raises(self, tmp_path: Path) -> None:
        with patch("wyby.project_init.shutil.which", return_value=None):
            with pytest.raises(GitNotFoundError, match="not installed"):
                init_git_repo(tmp_path / "nope")

    def test_git_init_failure_raises_git_error(self, tmp_path: Path) -> None:
        with patch("wyby.project_init.subprocess.run") as mock_run:
            # First call: rev-parse (existing repo check) — say "not a repo"
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=128, stdout="", stderr="not a git repo"
            )
            # We need the second call to also fail
            mock_run.side_effect = [
                # rev-parse call
                subprocess.CompletedProcess(
                    args=[], returncode=128, stdout="", stderr=""
                ),
                # git init call
                subprocess.CompletedProcess(
                    args=[], returncode=1, stdout="", stderr="init failed"
                ),
            ]

            with pytest.raises(GitError, match="git init failed"):
                init_git_repo(tmp_path / "fail")

    def test_logs_warning_for_existing_repo(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        target = tmp_path / "repo"
        target.mkdir()
        subprocess.run(["git", "init", str(target)], check=True, capture_output=True)

        import logging

        with caplog.at_level(logging.WARNING):
            init_git_repo(target)

        assert any(
            "already inside a git repository" in r.message for r in caplog.records
        )

    def test_logs_info_on_success(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        import logging

        with caplog.at_level(logging.INFO):
            init_git_repo(tmp_path / "proj")

        assert any("Initialised git repository" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# create_gitignore
# ---------------------------------------------------------------------------


class TestCreateGitignore:
    """Tests for create_gitignore()."""

    def test_creates_gitignore_in_existing_dir(self, tmp_path: Path) -> None:
        result = create_gitignore(tmp_path)
        gitignore = tmp_path / ".gitignore"

        assert result == gitignore
        assert gitignore.exists()

    def test_gitignore_content_matches_template(self, tmp_path: Path) -> None:
        create_gitignore(tmp_path)
        content = (tmp_path / ".gitignore").read_text(encoding="utf-8")

        assert content == GITIGNORE_TEMPLATE

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        target = tmp_path / "x" / "y"
        result = create_gitignore(target)

        assert result.exists()
        assert target.is_dir()

    def test_refuses_to_overwrite_by_default(self, tmp_path: Path) -> None:
        (tmp_path / ".gitignore").write_text("custom content")

        with pytest.raises(FileExistsError, match="already exists"):
            create_gitignore(tmp_path)

    def test_existing_content_preserved_when_not_overwriting(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / ".gitignore").write_text("custom content")

        with pytest.raises(FileExistsError):
            create_gitignore(tmp_path)

        assert (tmp_path / ".gitignore").read_text() == "custom content"

    def test_overwrite_replaces_content(self, tmp_path: Path) -> None:
        (tmp_path / ".gitignore").write_text("old content")
        create_gitignore(tmp_path, overwrite=True)

        content = (tmp_path / ".gitignore").read_text(encoding="utf-8")
        assert content == GITIGNORE_TEMPLATE

    def test_template_includes_python_patterns(self) -> None:
        assert "__pycache__/" in GITIGNORE_TEMPLATE
        assert "*.py[cod]" in GITIGNORE_TEMPLATE
        assert "*.egg-info/" in GITIGNORE_TEMPLATE

    def test_template_includes_venv_patterns(self) -> None:
        assert ".venv/" in GITIGNORE_TEMPLATE
        assert "venv/" in GITIGNORE_TEMPLATE

    def test_template_includes_ide_patterns(self) -> None:
        assert ".idea/" in GITIGNORE_TEMPLATE
        assert ".vscode/" in GITIGNORE_TEMPLATE

    def test_template_includes_wyby_specific_patterns(self) -> None:
        assert "saves/" in GITIGNORE_TEMPLATE
        assert "*.save.json" in GITIGNORE_TEMPLATE
        assert "*.log" in GITIGNORE_TEMPLATE

    def test_template_includes_env_file(self) -> None:
        assert ".env" in GITIGNORE_TEMPLATE


# ---------------------------------------------------------------------------
# _normalise_project_name
# ---------------------------------------------------------------------------


class TestNormaliseProjectName:
    """Tests for _normalise_project_name()."""

    def test_lowercase_simple_name(self) -> None:
        assert _normalise_project_name("MyGame") == "mygame"

    def test_preserves_hyphens(self) -> None:
        assert _normalise_project_name("my-game") == "my-game"

    def test_preserves_underscores(self) -> None:
        assert _normalise_project_name("my_game") == "my_game"

    def test_preserves_dots(self) -> None:
        assert _normalise_project_name("my.game") == "my.game"

    def test_single_character_name(self) -> None:
        assert _normalise_project_name("x") == "x"

    def test_empty_name_raises(self) -> None:
        with pytest.raises(ValueError, match="must not be empty"):
            _normalise_project_name("")

    def test_spaces_raise(self) -> None:
        with pytest.raises(ValueError, match="Invalid project name"):
            _normalise_project_name("my game")

    def test_leading_hyphen_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid project name"):
            _normalise_project_name("-mygame")

    def test_trailing_hyphen_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid project name"):
            _normalise_project_name("mygame-")

    def test_special_characters_raise(self) -> None:
        with pytest.raises(ValueError, match="Invalid project name"):
            _normalise_project_name("my@game!")


# ---------------------------------------------------------------------------
# create_pyproject_toml
# ---------------------------------------------------------------------------


class TestCreatePyprojectToml:
    """Tests for create_pyproject_toml()."""

    def test_creates_file_in_existing_dir(self, tmp_path: Path) -> None:
        result = create_pyproject_toml(tmp_path, "mygame")
        toml_path = tmp_path / "pyproject.toml"

        assert result == toml_path
        assert toml_path.exists()

    def test_content_includes_project_name(self, tmp_path: Path) -> None:
        create_pyproject_toml(tmp_path, "mygame")
        content = (tmp_path / "pyproject.toml").read_text(encoding="utf-8")

        assert 'name = "mygame"' in content

    def test_content_includes_wyby_dependency(self, tmp_path: Path) -> None:
        create_pyproject_toml(tmp_path, "mygame")
        content = (tmp_path / "pyproject.toml").read_text(encoding="utf-8")

        assert '"wyby>=0.1.0"' in content

    def test_content_includes_build_system(self, tmp_path: Path) -> None:
        create_pyproject_toml(tmp_path, "mygame")
        content = (tmp_path / "pyproject.toml").read_text(encoding="utf-8")

        assert "[build-system]" in content
        assert 'build-backend = "setuptools.build_meta"' in content

    def test_content_includes_python_requires(self, tmp_path: Path) -> None:
        create_pyproject_toml(tmp_path, "mygame")
        content = (tmp_path / "pyproject.toml").read_text(encoding="utf-8")

        assert 'requires-python = ">=3.10"' in content

    def test_name_is_normalised_to_lowercase(self, tmp_path: Path) -> None:
        create_pyproject_toml(tmp_path, "MyGame")
        content = (tmp_path / "pyproject.toml").read_text(encoding="utf-8")

        assert 'name = "mygame"' in content

    def test_hyphenated_name_produces_underscored_module(
        self, tmp_path: Path
    ) -> None:
        create_pyproject_toml(tmp_path, "my-cool-game")
        content = (tmp_path / "pyproject.toml").read_text(encoding="utf-8")

        # Project name preserves hyphens
        assert 'name = "my-cool-game"' in content
        # Console script comment uses underscored form
        assert "my_cool_game.main:main" in content

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        target = tmp_path / "a" / "b"
        result = create_pyproject_toml(target, "mygame")

        assert result.exists()
        assert target.is_dir()

    def test_refuses_to_overwrite_by_default(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("custom content")

        with pytest.raises(FileExistsError, match="already exists"):
            create_pyproject_toml(tmp_path, "mygame")

    def test_existing_content_preserved_when_not_overwriting(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "pyproject.toml").write_text("custom content")

        with pytest.raises(FileExistsError):
            create_pyproject_toml(tmp_path, "mygame")

        assert (tmp_path / "pyproject.toml").read_text() == "custom content"

    def test_overwrite_replaces_content(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("old content")
        create_pyproject_toml(tmp_path, "mygame", overwrite=True)

        content = (tmp_path / "pyproject.toml").read_text(encoding="utf-8")
        assert 'name = "mygame"' in content
        assert "old content" not in content

    def test_invalid_name_raises_value_error(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="Invalid project name"):
            create_pyproject_toml(tmp_path, "my game!")

    def test_empty_name_raises_value_error(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="must not be empty"):
            create_pyproject_toml(tmp_path, "")

    def test_template_includes_caveat_comments(self) -> None:
        """The template should include inline caveats about pinning and pre-release."""
        assert "pre-release" in PYPROJECT_TEMPLATE
        assert "wyby>=0.1.0" in PYPROJECT_TEMPLATE

    def test_logs_info_on_success(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        import logging

        with caplog.at_level(logging.INFO):
            create_pyproject_toml(tmp_path, "mygame")

        assert any("Created pyproject.toml" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# init_project
# ---------------------------------------------------------------------------


class TestInitProject:
    """Tests for init_project() — the convenience wrapper."""

    def test_creates_repo_gitignore_and_pyproject(self, tmp_path: Path) -> None:
        target = tmp_path / "game"
        result = init_project(target)

        assert result == target.resolve()
        assert (target / ".git").is_dir()
        assert (target / ".gitignore").exists()
        assert (target / "pyproject.toml").exists()

    def test_gitignore_has_correct_content(self, tmp_path: Path) -> None:
        target = tmp_path / "game"
        init_project(target)

        content = (target / ".gitignore").read_text(encoding="utf-8")
        assert content == GITIGNORE_TEMPLATE

    def test_pyproject_uses_directory_name_by_default(self, tmp_path: Path) -> None:
        target = tmp_path / "mygame"
        init_project(target)

        content = (target / "pyproject.toml").read_text(encoding="utf-8")
        assert 'name = "mygame"' in content

    def test_pyproject_uses_explicit_project_name(self, tmp_path: Path) -> None:
        target = tmp_path / "somedir"
        init_project(target, "cool-game")

        content = (target / "pyproject.toml").read_text(encoding="utf-8")
        assert 'name = "cool-game"' in content

    def test_refuses_overwrite_by_default(self, tmp_path: Path) -> None:
        target = tmp_path / "game"
        target.mkdir()
        subprocess.run(["git", "init", str(target)], check=True, capture_output=True)
        (target / ".gitignore").write_text("custom")

        with pytest.raises(FileExistsError):
            init_project(target)

    def test_overwrite_gitignore_flag(self, tmp_path: Path) -> None:
        target = tmp_path / "game"
        target.mkdir()
        subprocess.run(["git", "init", str(target)], check=True, capture_output=True)
        (target / ".gitignore").write_text("custom")

        init_project(target, overwrite_gitignore=True)

        content = (target / ".gitignore").read_text(encoding="utf-8")
        assert content == GITIGNORE_TEMPLATE

    def test_overwrite_pyproject_flag(self, tmp_path: Path) -> None:
        target = tmp_path / "game"
        target.mkdir()
        subprocess.run(["git", "init", str(target)], check=True, capture_output=True)
        (target / "pyproject.toml").write_text("old")

        init_project(target, overwrite_pyproject=True)

        content = (target / "pyproject.toml").read_text(encoding="utf-8")
        assert 'name = "game"' in content

    def test_git_not_found_propagates(self, tmp_path: Path) -> None:
        with patch("wyby.project_init.shutil.which", return_value=None):
            with pytest.raises(GitNotFoundError):
                init_project(tmp_path / "nope")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _git_env() -> dict[str, str]:
    """Return env vars so git commit works without user config."""
    import os

    env = os.environ.copy()
    env["GIT_AUTHOR_NAME"] = "Test"
    env["GIT_AUTHOR_EMAIL"] = "test@test.com"
    env["GIT_COMMITTER_NAME"] = "Test"
    env["GIT_COMMITTER_EMAIL"] = "test@test.com"
    return env
