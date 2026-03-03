"""Tests for wyby.curses_migration — curses-to-wyby migration guide catalog."""

from __future__ import annotations

import pytest

from wyby.curses_migration import (
    MIGRATION_CATEGORIES,
    MIGRATION_ENTRIES,
    MigrationEntry,
    format_migration_for_category,
    format_migration_guide,
    get_entries_by_category,
)


# ---------------------------------------------------------------------------
# MigrationEntry dataclass
# ---------------------------------------------------------------------------


class TestMigrationEntry:
    """MigrationEntry frozen dataclass."""

    def test_fields(self) -> None:
        entry = MigrationEntry(
            category="initialization",
            curses_pattern="curses.initscr()",
            curses_description="Initializes curses.",
            wyby_equivalent="Create an Engine.",
            caveat="A caveat.",
        )
        assert entry.category == "initialization"
        assert entry.curses_pattern == "curses.initscr()"
        assert entry.curses_description == "Initializes curses."
        assert entry.wyby_equivalent == "Create an Engine."
        assert entry.caveat == "A caveat."

    def test_caveat_defaults_to_none(self) -> None:
        entry = MigrationEntry(
            category="rendering",
            curses_pattern="addch()",
            curses_description="desc",
            wyby_equivalent="equiv",
        )
        assert entry.caveat is None

    def test_frozen(self) -> None:
        entry = MigrationEntry("a", "b", "c", "d")
        with pytest.raises(AttributeError):
            entry.category = "other"  # type: ignore[misc]

    def test_equality(self) -> None:
        a = MigrationEntry("a", "b", "c", "d", "e")
        b = MigrationEntry("a", "b", "c", "d", "e")
        assert a == b

    def test_inequality(self) -> None:
        a = MigrationEntry("a", "b", "c", "d")
        b = MigrationEntry("a", "x", "c", "d")
        assert a != b


# ---------------------------------------------------------------------------
# MIGRATION_ENTRIES catalog
# ---------------------------------------------------------------------------


class TestMigrationEntriesCatalog:
    """The built-in catalog of curses migration entries."""

    def test_is_tuple(self) -> None:
        assert isinstance(MIGRATION_ENTRIES, tuple)

    def test_not_empty(self) -> None:
        assert len(MIGRATION_ENTRIES) > 0

    def test_all_entries_are_migration_entry(self) -> None:
        for entry in MIGRATION_ENTRIES:
            assert isinstance(entry, MigrationEntry)

    def test_all_have_category(self) -> None:
        for entry in MIGRATION_ENTRIES:
            assert entry.category, (
                f"Entry {entry.curses_pattern!r} has no category"
            )

    def test_all_have_curses_pattern(self) -> None:
        for entry in MIGRATION_ENTRIES:
            assert entry.curses_pattern, "Entry has empty curses_pattern"

    def test_all_have_curses_description(self) -> None:
        for entry in MIGRATION_ENTRIES:
            assert entry.curses_description, (
                f"Entry {entry.curses_pattern!r} has no curses_description"
            )

    def test_all_have_wyby_equivalent(self) -> None:
        for entry in MIGRATION_ENTRIES:
            assert entry.wyby_equivalent, (
                f"Entry {entry.curses_pattern!r} has no wyby_equivalent"
            )

    def test_has_initialization_entries(self) -> None:
        cats = {entry.category for entry in MIGRATION_ENTRIES}
        assert "initialization" in cats

    def test_has_rendering_entries(self) -> None:
        cats = {entry.category for entry in MIGRATION_ENTRIES}
        assert "rendering" in cats

    def test_has_input_entries(self) -> None:
        cats = {entry.category for entry in MIGRATION_ENTRIES}
        assert "input" in cats

    def test_has_color_entries(self) -> None:
        cats = {entry.category for entry in MIGRATION_ENTRIES}
        assert "color" in cats

    def test_has_lifecycle_entries(self) -> None:
        cats = {entry.category for entry in MIGRATION_ENTRIES}
        assert "lifecycle" in cats

    def test_has_no_equivalent_entries(self) -> None:
        cats = {entry.category for entry in MIGRATION_ENTRIES}
        assert "no_equivalent" in cats

    def test_documents_initscr(self) -> None:
        patterns = {entry.curses_pattern for entry in MIGRATION_ENTRIES}
        assert any("initscr" in p for p in patterns)

    def test_documents_addch(self) -> None:
        patterns = {entry.curses_pattern for entry in MIGRATION_ENTRIES}
        assert any("addch" in p for p in patterns)

    def test_documents_refresh(self) -> None:
        patterns = {entry.curses_pattern for entry in MIGRATION_ENTRIES}
        assert any("refresh" in p for p in patterns)

    def test_documents_getch(self) -> None:
        patterns = {entry.curses_pattern for entry in MIGRATION_ENTRIES}
        assert any("getch" in p for p in patterns)

    def test_documents_color_pair(self) -> None:
        patterns = {entry.curses_pattern for entry in MIGRATION_ENTRIES}
        assert any("init_pair" in p or "start_color" in p for p in patterns)

    def test_documents_endwin(self) -> None:
        patterns = {entry.curses_pattern for entry in MIGRATION_ENTRIES}
        assert any("endwin" in p for p in patterns)

    def test_documents_newpad(self) -> None:
        patterns = {entry.curses_pattern for entry in MIGRATION_ENTRIES}
        assert any("newpad" in p for p in patterns)


# ---------------------------------------------------------------------------
# MIGRATION_CATEGORIES
# ---------------------------------------------------------------------------


class TestMigrationCategories:
    """MIGRATION_CATEGORIES frozenset."""

    def test_is_frozenset(self) -> None:
        assert isinstance(MIGRATION_CATEGORIES, frozenset)

    def test_not_empty(self) -> None:
        assert len(MIGRATION_CATEGORIES) > 0

    def test_matches_catalog(self) -> None:
        """Every category in the catalog should be in the frozenset."""
        cats_from_catalog = {
            entry.category for entry in MIGRATION_ENTRIES
        }
        assert cats_from_catalog == MIGRATION_CATEGORIES

    def test_has_expected_categories(self) -> None:
        expected = {
            "initialization",
            "rendering",
            "input",
            "color",
            "lifecycle",
            "no_equivalent",
        }
        assert expected == MIGRATION_CATEGORIES


# ---------------------------------------------------------------------------
# get_entries_by_category
# ---------------------------------------------------------------------------


class TestGetEntriesByCategory:
    """get_entries_by_category() filtering."""

    def test_returns_tuple(self) -> None:
        result = get_entries_by_category("initialization")
        assert isinstance(result, tuple)

    def test_all_match_category(self) -> None:
        result = get_entries_by_category("rendering")
        for entry in result:
            assert entry.category == "rendering"

    def test_initialization_not_empty(self) -> None:
        result = get_entries_by_category("initialization")
        assert len(result) > 0

    def test_rendering_not_empty(self) -> None:
        result = get_entries_by_category("rendering")
        assert len(result) > 0

    def test_input_not_empty(self) -> None:
        result = get_entries_by_category("input")
        assert len(result) > 0

    def test_color_not_empty(self) -> None:
        result = get_entries_by_category("color")
        assert len(result) > 0

    def test_lifecycle_not_empty(self) -> None:
        result = get_entries_by_category("lifecycle")
        assert len(result) > 0

    def test_no_equivalent_not_empty(self) -> None:
        result = get_entries_by_category("no_equivalent")
        assert len(result) > 0

    def test_unknown_category_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown category"):
            get_entries_by_category("nonexistent")

    def test_error_message_lists_known(self) -> None:
        with pytest.raises(ValueError, match="initialization"):
            get_entries_by_category("nonexistent")


# ---------------------------------------------------------------------------
# format_migration_for_category
# ---------------------------------------------------------------------------


class TestFormatMigrationForCategory:
    """format_migration_for_category() Markdown output."""

    def test_initialization_header(self) -> None:
        text = format_migration_for_category("initialization")
        assert "## Initialization & Setup" in text

    def test_rendering_header(self) -> None:
        text = format_migration_for_category("rendering")
        assert "## Rendering & Drawing" in text

    def test_input_header(self) -> None:
        text = format_migration_for_category("input")
        assert "## Input Handling" in text

    def test_color_header(self) -> None:
        text = format_migration_for_category("color")
        assert "## Color & Styling" in text

    def test_lifecycle_header(self) -> None:
        text = format_migration_for_category("lifecycle")
        assert "## Lifecycle & Terminal Management" in text

    def test_no_equivalent_header(self) -> None:
        text = format_migration_for_category("no_equivalent")
        assert "## Patterns With No Direct Equivalent" in text

    def test_has_curses_label(self) -> None:
        text = format_migration_for_category("initialization")
        assert "**curses:**" in text

    def test_has_wyby_label(self) -> None:
        text = format_migration_for_category("initialization")
        assert "**wyby:**" in text

    def test_has_caveat_when_present(self) -> None:
        text = format_migration_for_category("rendering")
        assert "**Caveat:**" in text

    def test_unknown_category_raises(self) -> None:
        with pytest.raises(ValueError):
            format_migration_for_category("nonexistent")


# ---------------------------------------------------------------------------
# format_migration_guide
# ---------------------------------------------------------------------------


class TestFormatMigrationGuide:
    """format_migration_guide() full document output."""

    def test_has_title(self) -> None:
        text = format_migration_guide()
        assert "# Migrating from curses to wyby" in text

    def test_has_entry_count(self) -> None:
        text = format_migration_guide()
        assert "patterns documented" in text

    def test_has_initialization_section(self) -> None:
        text = format_migration_guide()
        assert "## Initialization & Setup" in text

    def test_has_rendering_section(self) -> None:
        text = format_migration_guide()
        assert "## Rendering & Drawing" in text

    def test_has_input_section(self) -> None:
        text = format_migration_guide()
        assert "## Input Handling" in text

    def test_has_color_section(self) -> None:
        text = format_migration_guide()
        assert "## Color & Styling" in text

    def test_has_lifecycle_section(self) -> None:
        text = format_migration_guide()
        assert "## Lifecycle & Terminal Management" in text

    def test_has_no_equivalent_section(self) -> None:
        text = format_migration_guide()
        assert "## Patterns With No Direct Equivalent" in text

    def test_not_empty(self) -> None:
        text = format_migration_guide()
        assert len(text) > 100

    def test_all_categories_present(self) -> None:
        """Every category in the catalog should appear in the output."""
        text = format_migration_guide()
        for cat in MIGRATION_CATEGORIES:
            entries = get_entries_by_category(cat)
            assert any(
                entry.curses_pattern in text for entry in entries
            ), f"Category {cat!r} patterns not found in document"

    def test_mentions_curses(self) -> None:
        text = format_migration_guide()
        assert "curses" in text

    def test_mentions_rich(self) -> None:
        text = format_migration_guide()
        assert "Rich" in text

    def test_mentions_differential_updates(self) -> None:
        text = format_migration_guide()
        assert "differential" in text.lower()

    def test_mentions_coordinate_difference(self) -> None:
        # Caveat: curses uses (row, col), wyby uses (x, y)
        text = format_migration_guide()
        assert "(x, y)" in text

    def test_mentions_windows_support(self) -> None:
        text = format_migration_guide()
        assert "Windows" in text


# ---------------------------------------------------------------------------
# Package exports
# ---------------------------------------------------------------------------


class TestPackageExports:
    """Curses migration guide available from the wyby package."""

    def test_entries_importable(self) -> None:
        from wyby import MIGRATION_ENTRIES as E  # noqa: N811
        assert E is MIGRATION_ENTRIES

    def test_entry_class_importable(self) -> None:
        from wyby import MigrationEntry as C  # noqa: N811
        assert C is MigrationEntry

    def test_categories_importable(self) -> None:
        from wyby import MIGRATION_CATEGORIES as C  # noqa: N811
        assert C is MIGRATION_CATEGORIES

    def test_get_entries_by_category_importable(self) -> None:
        from wyby import get_migration_entries_by_category as f
        assert f is get_entries_by_category

    def test_format_guide_importable(self) -> None:
        from wyby import format_migration_guide as f
        assert f is format_migration_guide

    def test_format_for_category_importable(self) -> None:
        from wyby import format_migration_for_category as f
        assert f is format_migration_for_category

    def test_entries_in_all(self) -> None:
        import wyby
        assert "MIGRATION_ENTRIES" in wyby.__all__

    def test_entry_class_in_all(self) -> None:
        import wyby
        assert "MigrationEntry" in wyby.__all__

    def test_categories_in_all(self) -> None:
        import wyby
        assert "MIGRATION_CATEGORIES" in wyby.__all__

    def test_get_entries_in_all(self) -> None:
        import wyby
        assert "get_migration_entries_by_category" in wyby.__all__

    def test_format_guide_in_all(self) -> None:
        import wyby
        assert "format_migration_guide" in wyby.__all__

    def test_format_for_category_in_all(self) -> None:
        import wyby
        assert "format_migration_for_category" in wyby.__all__
