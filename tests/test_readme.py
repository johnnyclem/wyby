"""Tests for README.md content.

Verifies that the project README exists, contains the required disclaimer,
and documents the key caveats from SCOPE.md and the PRD.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# The repository root is one level above the tests/ directory.
REPO_ROOT = Path(__file__).resolve().parent.parent
README_PATH = REPO_ROOT / "README.md"


@pytest.fixture()
def readme_text() -> str:
    """Read and return the full README.md content."""
    assert README_PATH.exists(), "README.md must exist at the repository root"
    return README_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Existence and basic structure
# ---------------------------------------------------------------------------


class TestReadmeExists:
    """README.md should exist and be non-trivial."""

    def test_readme_file_exists(self) -> None:
        assert README_PATH.exists()

    def test_readme_is_not_empty(self, readme_text: str) -> None:
        assert len(readme_text.strip()) > 0


# ---------------------------------------------------------------------------
# Disclaimer
# ---------------------------------------------------------------------------


class TestReadmeDisclaimer:
    """The README must contain a prominent pre-release disclaimer."""

    def test_contains_disclaimer_keyword(self, readme_text: str) -> None:
        assert "Disclaimer" in readme_text

    def test_notes_pre_release_status(self, readme_text: str) -> None:
        lower = readme_text.lower()
        assert "pre-release" in lower or "pre release" in lower

    def test_notes_api_instability(self, readme_text: str) -> None:
        assert "unstable" in readme_text.lower()

    def test_warns_not_on_pypi(self, readme_text: str) -> None:
        assert "PyPI" in readme_text

    def test_warns_not_production(self, readme_text: str) -> None:
        assert "production" in readme_text.lower()


# ---------------------------------------------------------------------------
# Caveats
# ---------------------------------------------------------------------------


class TestReadmeCaveats:
    """Key design caveats from SCOPE.md must appear in the README."""

    def test_mentions_no_frame_rate_guarantee(self, readme_text: str) -> None:
        lower = readme_text.lower()
        assert "frame rate" in lower or "frame-rate" in lower

    def test_mentions_rich_rendering_tradeoff(self, readme_text: str) -> None:
        assert "Rich" in readme_text

    def test_mentions_terminal_cell_aspect_ratio(self, readme_text: str) -> None:
        assert "aspect ratio" in readme_text.lower()

    def test_mentions_no_keyboard_library(self, readme_text: str) -> None:
        assert "keyboard" in readme_text.lower()

    def test_mentions_no_pickle(self, readme_text: str) -> None:
        assert "pickle" in readme_text.lower()

    def test_mentions_no_networking(self, readme_text: str) -> None:
        lower = readme_text.lower()
        assert "network" in lower or "multiplayer" in lower

    def test_mentions_unicode_emoji_variability(self, readme_text: str) -> None:
        lower = readme_text.lower()
        assert "unicode" in lower or "emoji" in lower


# ---------------------------------------------------------------------------
# Essential sections
# ---------------------------------------------------------------------------


class TestReadmeSections:
    """The README should contain key informational sections."""

    def test_has_project_name_heading(self, readme_text: str) -> None:
        assert readme_text.startswith("# wyby")

    def test_mentions_python_version_requirement(self, readme_text: str) -> None:
        assert "3.10" in readme_text

    def test_mentions_rich_dependency(self, readme_text: str) -> None:
        assert "rich" in readme_text.lower()

    def test_mentions_license(self, readme_text: str) -> None:
        assert "GPL-3.0" in readme_text or "GPL" in readme_text
