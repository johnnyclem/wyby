"""Tests for wyby.installation_from_source — installation guide catalog."""

from __future__ import annotations

import pytest

from wyby.installation_from_source import (
    INSTALLATION_CATEGORIES,
    INSTALLATION_ENTRIES,
    InstallationEntry,
    format_installation_for_category,
    format_installation_guide,
    get_entries_by_category,
)


# ---------------------------------------------------------------------------
# InstallationEntry dataclass
# ---------------------------------------------------------------------------


class TestInstallationEntry:
    """InstallationEntry frozen dataclass."""

    def test_fields(self) -> None:
        entry = InstallationEntry(
            category="prerequisites",
            topic="Test entry",
            description="A test description.",
            caveat="A caveat.",
        )
        assert entry.category == "prerequisites"
        assert entry.topic == "Test entry"
        assert entry.description == "A test description."
        assert entry.caveat == "A caveat."

    def test_caveat_defaults_to_none(self) -> None:
        entry = InstallationEntry(
            category="basic_install",
            topic="No caveat",
            description="desc",
        )
        assert entry.caveat is None

    def test_frozen(self) -> None:
        entry = InstallationEntry("a", "b", "c")
        with pytest.raises(AttributeError):
            entry.category = "other"  # type: ignore[misc]

    def test_equality(self) -> None:
        a = InstallationEntry("a", "b", "c", "d")
        b = InstallationEntry("a", "b", "c", "d")
        assert a == b

    def test_inequality(self) -> None:
        a = InstallationEntry("a", "b", "c")
        b = InstallationEntry("a", "x", "c")
        assert a != b


# ---------------------------------------------------------------------------
# INSTALLATION_ENTRIES catalog
# ---------------------------------------------------------------------------


class TestInstallationEntriesCatalog:
    """The built-in catalog of installation entries."""

    def test_is_tuple(self) -> None:
        assert isinstance(INSTALLATION_ENTRIES, tuple)

    def test_not_empty(self) -> None:
        assert len(INSTALLATION_ENTRIES) > 0

    def test_all_entries_are_installation_entry(self) -> None:
        for entry in INSTALLATION_ENTRIES:
            assert isinstance(entry, InstallationEntry)

    def test_all_have_category(self) -> None:
        for entry in INSTALLATION_ENTRIES:
            assert entry.category, (
                f"Entry {entry.topic!r} has no category"
            )

    def test_all_have_topic(self) -> None:
        for entry in INSTALLATION_ENTRIES:
            assert entry.topic, "Entry has empty topic"

    def test_all_have_description(self) -> None:
        for entry in INSTALLATION_ENTRIES:
            assert entry.description, (
                f"Entry {entry.topic!r} has no description"
            )

    def test_has_prerequisites_entries(self) -> None:
        cats = {entry.category for entry in INSTALLATION_ENTRIES}
        assert "prerequisites" in cats

    def test_has_basic_install_entries(self) -> None:
        cats = {entry.category for entry in INSTALLATION_ENTRIES}
        assert "basic_install" in cats

    def test_has_optional_extras_entries(self) -> None:
        cats = {entry.category for entry in INSTALLATION_ENTRIES}
        assert "optional_extras" in cats

    def test_has_virtual_environment_entries(self) -> None:
        cats = {entry.category for entry in INSTALLATION_ENTRIES}
        assert "virtual_environment" in cats

    def test_has_verification_entries(self) -> None:
        cats = {entry.category for entry in INSTALLATION_ENTRIES}
        assert "verification" in cats

    def test_has_caveats_entries(self) -> None:
        cats = {entry.category for entry in INSTALLATION_ENTRIES}
        assert "caveats" in cats

    def test_documents_python_requirement(self) -> None:
        topics = {entry.topic for entry in INSTALLATION_ENTRIES}
        assert any("Python" in t for t in topics)

    def test_documents_git_requirement(self) -> None:
        topics = {entry.topic for entry in INSTALLATION_ENTRIES}
        assert any("Git" in t for t in topics)

    def test_documents_editable_install(self) -> None:
        topics = {entry.topic for entry in INSTALLATION_ENTRIES}
        assert any("editable" in t.lower() for t in topics)

    def test_documents_not_on_pypi(self) -> None:
        topics = {entry.topic for entry in INSTALLATION_ENTRIES}
        assert any("PyPI" in t for t in topics)

    def test_documents_cairo(self) -> None:
        topics = {entry.topic for entry in INSTALLATION_ENTRIES}
        assert any("Cairo" in t for t in topics)

    def test_documents_image_extra(self) -> None:
        topics = {entry.topic for entry in INSTALLATION_ENTRIES}
        assert any("image" in t.lower() for t in topics)

    def test_documents_svg_extra(self) -> None:
        topics = {entry.topic for entry in INSTALLATION_ENTRIES}
        assert any("svg" in t.lower() or "SVG" in t for t in topics)

    def test_documents_virtual_environment(self) -> None:
        topics = {entry.topic for entry in INSTALLATION_ENTRIES}
        assert any("virtual environment" in t.lower() for t in topics)


# ---------------------------------------------------------------------------
# INSTALLATION_CATEGORIES
# ---------------------------------------------------------------------------


class TestInstallationCategories:
    """INSTALLATION_CATEGORIES frozenset."""

    def test_is_frozenset(self) -> None:
        assert isinstance(INSTALLATION_CATEGORIES, frozenset)

    def test_not_empty(self) -> None:
        assert len(INSTALLATION_CATEGORIES) > 0

    def test_matches_catalog(self) -> None:
        """Every category in the catalog should be in the frozenset."""
        cats_from_catalog = {
            entry.category for entry in INSTALLATION_ENTRIES
        }
        assert cats_from_catalog == INSTALLATION_CATEGORIES

    def test_has_expected_categories(self) -> None:
        expected = {
            "prerequisites",
            "basic_install",
            "optional_extras",
            "virtual_environment",
            "verification",
            "caveats",
        }
        assert expected == INSTALLATION_CATEGORIES


# ---------------------------------------------------------------------------
# get_entries_by_category
# ---------------------------------------------------------------------------


class TestGetEntriesByCategory:
    """get_entries_by_category() filtering."""

    def test_returns_tuple(self) -> None:
        result = get_entries_by_category("prerequisites")
        assert isinstance(result, tuple)

    def test_all_match_category(self) -> None:
        result = get_entries_by_category("basic_install")
        for entry in result:
            assert entry.category == "basic_install"

    def test_prerequisites_not_empty(self) -> None:
        result = get_entries_by_category("prerequisites")
        assert len(result) > 0

    def test_basic_install_not_empty(self) -> None:
        result = get_entries_by_category("basic_install")
        assert len(result) > 0

    def test_optional_extras_not_empty(self) -> None:
        result = get_entries_by_category("optional_extras")
        assert len(result) > 0

    def test_virtual_environment_not_empty(self) -> None:
        result = get_entries_by_category("virtual_environment")
        assert len(result) > 0

    def test_verification_not_empty(self) -> None:
        result = get_entries_by_category("verification")
        assert len(result) > 0

    def test_caveats_not_empty(self) -> None:
        result = get_entries_by_category("caveats")
        assert len(result) > 0

    def test_unknown_category_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown category"):
            get_entries_by_category("nonexistent")

    def test_error_message_lists_known(self) -> None:
        with pytest.raises(ValueError, match="prerequisites"):
            get_entries_by_category("nonexistent")


# ---------------------------------------------------------------------------
# format_installation_for_category
# ---------------------------------------------------------------------------


class TestFormatInstallationForCategory:
    """format_installation_for_category() Markdown output."""

    def test_has_category_header(self) -> None:
        text = format_installation_for_category("prerequisites")
        assert "## Prerequisites" in text

    def test_has_topic_headers(self) -> None:
        text = format_installation_for_category("prerequisites")
        assert "### Python >= 3.10 required" in text

    def test_has_caveat_when_present(self) -> None:
        text = format_installation_for_category("caveats")
        assert "**Caveat:**" in text

    def test_basic_install_category(self) -> None:
        text = format_installation_for_category("basic_install")
        assert "## Basic Installation" in text

    def test_optional_extras_category(self) -> None:
        text = format_installation_for_category("optional_extras")
        assert "## Optional Extras" in text

    def test_virtual_environment_category(self) -> None:
        text = format_installation_for_category("virtual_environment")
        assert "## Virtual Environment" in text

    def test_verification_category(self) -> None:
        text = format_installation_for_category("verification")
        assert "## Verification" in text

    def test_caveats_category(self) -> None:
        text = format_installation_for_category("caveats")
        assert "## Caveats & Known Issues" in text

    def test_unknown_category_raises(self) -> None:
        with pytest.raises(ValueError):
            format_installation_for_category("nonexistent")


# ---------------------------------------------------------------------------
# format_installation_guide
# ---------------------------------------------------------------------------


class TestFormatInstallationGuide:
    """format_installation_guide() full document output."""

    def test_has_title(self) -> None:
        text = format_installation_guide()
        assert "# Installing wyby from Source" in text

    def test_has_entry_count(self) -> None:
        text = format_installation_guide()
        assert "entries documented" in text

    def test_has_prerequisites_section(self) -> None:
        text = format_installation_guide()
        assert "## Prerequisites" in text

    def test_has_basic_install_section(self) -> None:
        text = format_installation_guide()
        assert "## Basic Installation" in text

    def test_has_optional_extras_section(self) -> None:
        text = format_installation_guide()
        assert "## Optional Extras" in text

    def test_has_virtual_environment_section(self) -> None:
        text = format_installation_guide()
        assert "## Virtual Environment" in text

    def test_has_verification_section(self) -> None:
        text = format_installation_guide()
        assert "## Verification" in text

    def test_has_caveats_section(self) -> None:
        text = format_installation_guide()
        assert "## Caveats & Known Issues" in text

    def test_not_empty(self) -> None:
        text = format_installation_guide()
        assert len(text) > 100

    def test_all_categories_present(self) -> None:
        """Every category in the catalog should appear in the output."""
        text = format_installation_guide()
        for cat in INSTALLATION_CATEGORIES:
            entries = get_entries_by_category(cat)
            assert any(
                entry.topic in text for entry in entries
            ), f"Category {cat!r} topics not found in document"

    def test_mentions_pypi(self) -> None:
        text = format_installation_guide()
        assert "PyPI" in text

    def test_mentions_pip(self) -> None:
        text = format_installation_guide()
        assert "pip" in text

    def test_mentions_rich(self) -> None:
        text = format_installation_guide()
        assert "rich" in text.lower()

    def test_mentions_editable(self) -> None:
        text = format_installation_guide()
        assert "editable" in text.lower()


# ---------------------------------------------------------------------------
# Package exports
# ---------------------------------------------------------------------------


class TestPackageExports:
    """Installation from source available from the wyby package."""

    def test_entries_importable(self) -> None:
        from wyby import INSTALLATION_ENTRIES as E  # noqa: N811
        assert E is INSTALLATION_ENTRIES

    def test_entry_class_importable(self) -> None:
        from wyby import InstallationEntry as C  # noqa: N811
        assert C is InstallationEntry

    def test_categories_importable(self) -> None:
        from wyby import INSTALLATION_CATEGORIES as C  # noqa: N811
        assert C is INSTALLATION_CATEGORIES

    def test_get_entries_by_category_importable(self) -> None:
        from wyby import get_installation_entries_by_category as f
        assert callable(f)

    def test_format_guide_importable(self) -> None:
        from wyby import format_installation_guide as f
        assert f is format_installation_guide

    def test_format_for_category_importable(self) -> None:
        from wyby import format_installation_for_category as f
        assert f is format_installation_for_category

    def test_entries_in_all(self) -> None:
        import wyby
        assert "INSTALLATION_ENTRIES" in wyby.__all__

    def test_entry_class_in_all(self) -> None:
        import wyby
        assert "InstallationEntry" in wyby.__all__

    def test_categories_in_all(self) -> None:
        import wyby
        assert "INSTALLATION_CATEGORIES" in wyby.__all__

    def test_get_entries_in_all(self) -> None:
        import wyby
        assert "get_installation_entries_by_category" in wyby.__all__

    def test_format_guide_in_all(self) -> None:
        import wyby
        assert "format_installation_guide" in wyby.__all__

    def test_format_for_category_in_all(self) -> None:
        import wyby
        assert "format_installation_for_category" in wyby.__all__
