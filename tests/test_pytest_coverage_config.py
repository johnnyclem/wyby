"""Tests for pytest and coverage configuration.

Verifies that pyproject.toml contains the expected pytest and coverage
settings and that pytest-cov is available as a dev dependency.

Caveat: These tests validate the *declared* configuration, not runtime
coverage thresholds. fail_under is intentionally unset during pre-release
since most modules are stubs. Revisit when core modules have real
implementations.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

# The repository root is one level above the tests/ directory.
REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"


@pytest.fixture()
def pyproject_text() -> str:
    """Read and return the full pyproject.toml content."""
    assert PYPROJECT_PATH.exists(), "pyproject.toml must exist at the repository root"
    return PYPROJECT_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# pytest-cov availability
# ---------------------------------------------------------------------------


class TestPytestCovInstalled:
    """pytest-cov must be importable in the dev environment."""

    def test_pytest_cov_importable(self) -> None:
        mod = importlib.import_module("pytest_cov")
        assert mod is not None

    def test_coverage_importable(self) -> None:
        mod = importlib.import_module("coverage")
        assert mod is not None


# ---------------------------------------------------------------------------
# pyproject.toml — dev dependencies
# ---------------------------------------------------------------------------


class TestDevDependencies:
    """pytest-cov should be declared as a dev dependency."""

    def test_pytest_cov_in_dev_extras(self, pyproject_text: str) -> None:
        assert "pytest-cov" in pyproject_text

    def test_pytest_in_dev_extras(self, pyproject_text: str) -> None:
        assert "pytest>=" in pyproject_text


# ---------------------------------------------------------------------------
# pyproject.toml — [tool.pytest.ini_options]
# ---------------------------------------------------------------------------


class TestPytestIniOptions:
    """The [tool.pytest.ini_options] section should configure test discovery and coverage."""

    def test_testpaths_configured(self, pyproject_text: str) -> None:
        assert 'testpaths = ["tests"]' in pyproject_text

    def test_strict_markers_enabled(self, pyproject_text: str) -> None:
        assert "--strict-markers" in pyproject_text

    def test_cov_flag_targets_wyby(self, pyproject_text: str) -> None:
        assert "--cov=wyby" in pyproject_text

    def test_branch_coverage_enabled_in_addopts(self, pyproject_text: str) -> None:
        assert "--cov-branch" in pyproject_text

    def test_term_missing_report(self, pyproject_text: str) -> None:
        assert "--cov-report=term-missing" in pyproject_text

    def test_html_report(self, pyproject_text: str) -> None:
        assert "--cov-report=html" in pyproject_text


# ---------------------------------------------------------------------------
# pyproject.toml — [tool.coverage.*]
# ---------------------------------------------------------------------------


class TestCoverageRunConfig:
    """The [tool.coverage.run] section should set source and branch."""

    def test_coverage_source(self, pyproject_text: str) -> None:
        assert '[tool.coverage.run]' in pyproject_text
        assert 'source = ["wyby"]' in pyproject_text

    def test_coverage_branch(self, pyproject_text: str) -> None:
        assert "branch = true" in pyproject_text


class TestCoverageReportConfig:
    """The [tool.coverage.report] section should configure display and exclusions."""

    def test_show_missing(self, pyproject_text: str) -> None:
        assert "[tool.coverage.report]" in pyproject_text
        assert "show_missing = true" in pyproject_text

    def test_excludes_pragma_no_cover(self, pyproject_text: str) -> None:
        assert "pragma: no cover" in pyproject_text

    def test_excludes_type_checking(self, pyproject_text: str) -> None:
        assert "if TYPE_CHECKING:" in pyproject_text

    def test_excludes_not_implemented(self, pyproject_text: str) -> None:
        assert "raise NotImplementedError" in pyproject_text

    def test_fail_under_commented_out(self, pyproject_text: str) -> None:
        """fail_under should be commented out during pre-release development."""
        assert "# fail_under" in pyproject_text


class TestCoverageHtmlConfig:
    """The [tool.coverage.html] section should point to htmlcov/."""

    def test_html_directory(self, pyproject_text: str) -> None:
        assert "[tool.coverage.html]" in pyproject_text
        assert 'directory = "htmlcov"' in pyproject_text


# ---------------------------------------------------------------------------
# .gitignore — coverage artifacts
# ---------------------------------------------------------------------------


class TestGitignoreCoverageArtifacts:
    """Coverage artifacts should be excluded from version control."""

    def test_coverage_data_file_ignored(self) -> None:
        gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
        assert ".coverage" in gitignore

    def test_htmlcov_directory_ignored(self) -> None:
        gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
        assert "htmlcov/" in gitignore
