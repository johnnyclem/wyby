"""Tests for wyby.input_permissions — input permission requirements catalog."""

from __future__ import annotations

import pytest

from wyby.input_permissions import (
    INPUT_PERMISSION_ENTRIES,
    PERMISSION_CATEGORIES,
    InputPermissionEntry,
    format_input_permissions_doc,
    format_input_permissions_for_category,
    get_entries_by_category,
)


# ---------------------------------------------------------------------------
# InputPermissionEntry dataclass
# ---------------------------------------------------------------------------


class TestInputPermissionEntry:
    """InputPermissionEntry frozen dataclass."""

    def test_fields(self) -> None:
        entry = InputPermissionEntry(
            category="no_elevation",
            topic="Test entry",
            description="A test description.",
            caveat="A caveat.",
        )
        assert entry.category == "no_elevation"
        assert entry.topic == "Test entry"
        assert entry.description == "A test description."
        assert entry.caveat == "A caveat."

    def test_caveat_defaults_to_none(self) -> None:
        entry = InputPermissionEntry(
            category="platform",
            topic="No caveat",
            description="desc",
        )
        assert entry.caveat is None

    def test_frozen(self) -> None:
        entry = InputPermissionEntry("a", "b", "c")
        with pytest.raises(AttributeError):
            entry.category = "other"  # type: ignore[misc]

    def test_equality(self) -> None:
        a = InputPermissionEntry("a", "b", "c", "d")
        b = InputPermissionEntry("a", "b", "c", "d")
        assert a == b

    def test_inequality(self) -> None:
        a = InputPermissionEntry("a", "b", "c")
        b = InputPermissionEntry("a", "x", "c")
        assert a != b


# ---------------------------------------------------------------------------
# INPUT_PERMISSION_ENTRIES catalog
# ---------------------------------------------------------------------------


class TestInputPermissionEntriesCatalog:
    """The built-in catalog of input permission entries."""

    def test_is_tuple(self) -> None:
        assert isinstance(INPUT_PERMISSION_ENTRIES, tuple)

    def test_not_empty(self) -> None:
        assert len(INPUT_PERMISSION_ENTRIES) > 0

    def test_all_entries_are_input_permission_entry(self) -> None:
        for entry in INPUT_PERMISSION_ENTRIES:
            assert isinstance(entry, InputPermissionEntry)

    def test_all_have_category(self) -> None:
        for entry in INPUT_PERMISSION_ENTRIES:
            assert entry.category, (
                f"Entry {entry.topic!r} has no category"
            )

    def test_all_have_topic(self) -> None:
        for entry in INPUT_PERMISSION_ENTRIES:
            assert entry.topic, "Entry has empty topic"

    def test_all_have_description(self) -> None:
        for entry in INPUT_PERMISSION_ENTRIES:
            assert entry.description, (
                f"Entry {entry.topic!r} has no description"
            )

    def test_has_no_elevation_entries(self) -> None:
        cats = {entry.category for entry in INPUT_PERMISSION_ENTRIES}
        assert "no_elevation" in cats

    def test_has_keyboard_library_entries(self) -> None:
        cats = {entry.category for entry in INPUT_PERMISSION_ENTRIES}
        assert "keyboard_library" in cats

    def test_has_platform_entries(self) -> None:
        cats = {entry.category for entry in INPUT_PERMISSION_ENTRIES}
        assert "platform" in cats

    def test_has_environment_entries(self) -> None:
        cats = {entry.category for entry in INPUT_PERMISSION_ENTRIES}
        assert "environment" in cats

    def test_documents_no_root_required(self) -> None:
        topics = {entry.topic for entry in INPUT_PERMISSION_ENTRIES}
        assert "No root/sudo required" in topics

    def test_documents_keyboard_root_requirement(self) -> None:
        topics = {entry.topic for entry in INPUT_PERMISSION_ENTRIES}
        assert any("root requirement" in t for t in topics)

    def test_documents_no_device_file_access(self) -> None:
        topics = {entry.topic for entry in INPUT_PERMISSION_ENTRIES}
        assert "No device file access" in topics

    def test_documents_no_system_wide_hooks(self) -> None:
        topics = {entry.topic for entry in INPUT_PERMISSION_ENTRIES}
        assert "No system-wide input hooks" in topics

    def test_documents_docker(self) -> None:
        topics = {entry.topic for entry in INPUT_PERMISSION_ENTRIES}
        assert any("Docker" in t for t in topics)

    def test_documents_ssh(self) -> None:
        topics = {entry.topic for entry in INPUT_PERMISSION_ENTRIES}
        assert any("SSH" in t for t in topics)

    def test_documents_unix_termios(self) -> None:
        topics = {entry.topic for entry in INPUT_PERMISSION_ENTRIES}
        assert any("termios" in t for t in topics)

    def test_documents_windows_msvcrt(self) -> None:
        topics = {entry.topic for entry in INPUT_PERMISSION_ENTRIES}
        assert any("msvcrt" in t for t in topics)


# ---------------------------------------------------------------------------
# PERMISSION_CATEGORIES
# ---------------------------------------------------------------------------


class TestPermissionCategories:
    """PERMISSION_CATEGORIES frozenset."""

    def test_is_frozenset(self) -> None:
        assert isinstance(PERMISSION_CATEGORIES, frozenset)

    def test_not_empty(self) -> None:
        assert len(PERMISSION_CATEGORIES) > 0

    def test_matches_catalog(self) -> None:
        """Every category in the catalog should be in the frozenset."""
        cats_from_catalog = {
            entry.category for entry in INPUT_PERMISSION_ENTRIES
        }
        assert cats_from_catalog == PERMISSION_CATEGORIES

    def test_has_expected_categories(self) -> None:
        expected = {"no_elevation", "keyboard_library", "platform", "environment"}
        assert expected == PERMISSION_CATEGORIES


# ---------------------------------------------------------------------------
# get_entries_by_category
# ---------------------------------------------------------------------------


class TestGetEntriesByCategory:
    """get_entries_by_category() filtering."""

    def test_returns_tuple(self) -> None:
        result = get_entries_by_category("no_elevation")
        assert isinstance(result, tuple)

    def test_all_match_category(self) -> None:
        result = get_entries_by_category("keyboard_library")
        for entry in result:
            assert entry.category == "keyboard_library"

    def test_no_elevation_not_empty(self) -> None:
        result = get_entries_by_category("no_elevation")
        assert len(result) > 0

    def test_keyboard_library_not_empty(self) -> None:
        result = get_entries_by_category("keyboard_library")
        assert len(result) > 0

    def test_platform_not_empty(self) -> None:
        result = get_entries_by_category("platform")
        assert len(result) > 0

    def test_environment_not_empty(self) -> None:
        result = get_entries_by_category("environment")
        assert len(result) > 0

    def test_unknown_category_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown category"):
            get_entries_by_category("nonexistent")

    def test_error_message_lists_known(self) -> None:
        with pytest.raises(ValueError, match="no_elevation"):
            get_entries_by_category("nonexistent")


# ---------------------------------------------------------------------------
# format_input_permissions_for_category
# ---------------------------------------------------------------------------


class TestFormatInputPermissionsForCategory:
    """format_input_permissions_for_category() Markdown output."""

    def test_has_category_header(self) -> None:
        text = format_input_permissions_for_category("no_elevation")
        assert "## No Elevated Permissions Required" in text

    def test_has_topic_headers(self) -> None:
        text = format_input_permissions_for_category("no_elevation")
        assert "### No root/sudo required" in text

    def test_has_caveat_when_present(self) -> None:
        text = format_input_permissions_for_category("keyboard_library")
        assert "**Caveat:**" in text

    def test_keyboard_library_category(self) -> None:
        text = format_input_permissions_for_category("keyboard_library")
        assert "## Why the keyboard Library Is Excluded" in text

    def test_platform_category(self) -> None:
        text = format_input_permissions_for_category("platform")
        assert "## Platform-Specific Permission Notes" in text

    def test_environment_category(self) -> None:
        text = format_input_permissions_for_category("environment")
        assert "## Environment-Specific Notes" in text

    def test_unknown_category_raises(self) -> None:
        with pytest.raises(ValueError):
            format_input_permissions_for_category("nonexistent")


# ---------------------------------------------------------------------------
# format_input_permissions_doc
# ---------------------------------------------------------------------------


class TestFormatInputPermissionsDoc:
    """format_input_permissions_doc() full document output."""

    def test_has_title(self) -> None:
        text = format_input_permissions_doc()
        assert "# Input Permissions" in text

    def test_has_entry_count(self) -> None:
        text = format_input_permissions_doc()
        assert "entries documented" in text

    def test_has_no_elevation_section(self) -> None:
        text = format_input_permissions_doc()
        assert "## No Elevated Permissions Required" in text

    def test_has_keyboard_library_section(self) -> None:
        text = format_input_permissions_doc()
        assert "## Why the keyboard Library Is Excluded" in text

    def test_has_platform_section(self) -> None:
        text = format_input_permissions_doc()
        assert "## Platform-Specific Permission Notes" in text

    def test_has_environment_section(self) -> None:
        text = format_input_permissions_doc()
        assert "## Environment-Specific Notes" in text

    def test_not_empty(self) -> None:
        text = format_input_permissions_doc()
        assert len(text) > 100

    def test_all_categories_present(self) -> None:
        """Every category in the catalog should appear in the output."""
        text = format_input_permissions_doc()
        for cat in PERMISSION_CATEGORIES:
            entries = get_entries_by_category(cat)
            assert any(
                entry.topic in text for entry in entries
            ), f"Category {cat!r} topics not found in document"

    def test_mentions_no_root(self) -> None:
        text = format_input_permissions_doc()
        assert "root" in text.lower()

    def test_mentions_keyboard_library(self) -> None:
        text = format_input_permissions_doc()
        assert "keyboard" in text.lower()

    def test_mentions_stdin(self) -> None:
        text = format_input_permissions_doc()
        assert "stdin" in text


# ---------------------------------------------------------------------------
# Package exports
# ---------------------------------------------------------------------------


class TestPackageExports:
    """Input permissions available from the wyby package."""

    def test_entries_importable(self) -> None:
        from wyby import INPUT_PERMISSION_ENTRIES as E  # noqa: N811
        assert E is INPUT_PERMISSION_ENTRIES

    def test_entry_class_importable(self) -> None:
        from wyby import InputPermissionEntry as C  # noqa: N811
        assert C is InputPermissionEntry

    def test_categories_importable(self) -> None:
        from wyby import PERMISSION_CATEGORIES as C  # noqa: N811
        assert C is PERMISSION_CATEGORIES

    def test_get_entries_by_category_importable(self) -> None:
        from wyby import get_entries_by_category as f
        assert f is get_entries_by_category

    def test_format_doc_importable(self) -> None:
        from wyby import format_input_permissions_doc as f
        assert f is format_input_permissions_doc

    def test_format_for_category_importable(self) -> None:
        from wyby import format_input_permissions_for_category as f
        assert f is format_input_permissions_for_category

    def test_entries_in_all(self) -> None:
        import wyby
        assert "INPUT_PERMISSION_ENTRIES" in wyby.__all__

    def test_entry_class_in_all(self) -> None:
        import wyby
        assert "InputPermissionEntry" in wyby.__all__

    def test_categories_in_all(self) -> None:
        import wyby
        assert "PERMISSION_CATEGORIES" in wyby.__all__

    def test_get_entries_in_all(self) -> None:
        import wyby
        assert "get_entries_by_category" in wyby.__all__

    def test_format_doc_in_all(self) -> None:
        import wyby
        assert "format_input_permissions_doc" in wyby.__all__

    def test_format_for_category_in_all(self) -> None:
        import wyby
        assert "format_input_permissions_for_category" in wyby.__all__
