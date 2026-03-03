"""Tests for wyby.rich_live_tradeoffs — Rich Live display tradeoffs catalog."""

from __future__ import annotations

import pytest

from wyby.rich_live_tradeoffs import (
    TRADEOFF_CATEGORIES,
    TRADEOFF_ENTRIES,
    RichLiveTradeoff,
    format_rich_live_tradeoffs_doc,
    format_tradeoffs_for_category,
    get_tradeoffs_by_category,
)


# ---------------------------------------------------------------------------
# RichLiveTradeoff dataclass
# ---------------------------------------------------------------------------


class TestRichLiveTradeoff:
    """RichLiveTradeoff frozen dataclass."""

    def test_fields(self) -> None:
        entry = RichLiveTradeoff(
            category="advantage",
            topic="Test entry",
            description="A test description.",
            caveat="A caveat.",
        )
        assert entry.category == "advantage"
        assert entry.topic == "Test entry"
        assert entry.description == "A test description."
        assert entry.caveat == "A caveat."

    def test_caveat_defaults_to_none(self) -> None:
        entry = RichLiveTradeoff(
            category="limitation",
            topic="No caveat",
            description="desc",
        )
        assert entry.caveat is None

    def test_frozen(self) -> None:
        entry = RichLiveTradeoff("a", "b", "c")
        with pytest.raises(AttributeError):
            entry.category = "other"  # type: ignore[misc]

    def test_equality(self) -> None:
        a = RichLiveTradeoff("a", "b", "c", "d")
        b = RichLiveTradeoff("a", "b", "c", "d")
        assert a == b

    def test_inequality(self) -> None:
        a = RichLiveTradeoff("a", "b", "c")
        b = RichLiveTradeoff("a", "x", "c")
        assert a != b


# ---------------------------------------------------------------------------
# TRADEOFF_ENTRIES catalog
# ---------------------------------------------------------------------------


class TestTradeoffEntriesCatalog:
    """The built-in catalog of Rich Live tradeoff entries."""

    def test_is_tuple(self) -> None:
        assert isinstance(TRADEOFF_ENTRIES, tuple)

    def test_not_empty(self) -> None:
        assert len(TRADEOFF_ENTRIES) > 0

    def test_all_entries_are_rich_live_tradeoff(self) -> None:
        for entry in TRADEOFF_ENTRIES:
            assert isinstance(entry, RichLiveTradeoff)

    def test_all_have_category(self) -> None:
        for entry in TRADEOFF_ENTRIES:
            assert entry.category, (
                f"Entry {entry.topic!r} has no category"
            )

    def test_all_have_topic(self) -> None:
        for entry in TRADEOFF_ENTRIES:
            assert entry.topic, "Entry has empty topic"

    def test_all_have_description(self) -> None:
        for entry in TRADEOFF_ENTRIES:
            assert entry.description, (
                f"Entry {entry.topic!r} has no description"
            )

    def test_has_advantage_entries(self) -> None:
        cats = {entry.category for entry in TRADEOFF_ENTRIES}
        assert "advantage" in cats

    def test_has_limitation_entries(self) -> None:
        cats = {entry.category for entry in TRADEOFF_ENTRIES}
        assert "limitation" in cats

    def test_has_performance_entries(self) -> None:
        cats = {entry.category for entry in TRADEOFF_ENTRIES}
        assert "performance" in cats

    def test_has_guidance_entries(self) -> None:
        cats = {entry.category for entry in TRADEOFF_ENTRIES}
        assert "guidance" in cats

    def test_documents_no_double_buffering(self) -> None:
        topics = {entry.topic for entry in TRADEOFF_ENTRIES}
        assert "No double buffering" in topics

    def test_documents_cross_platform(self) -> None:
        topics = {entry.topic for entry in TRADEOFF_ENTRIES}
        assert any("cross-platform" in t.lower() for t in topics)

    def test_documents_flicker(self) -> None:
        topics = {entry.topic for entry in TRADEOFF_ENTRIES}
        assert any("flicker" in t.lower() for t in topics)

    def test_documents_frame_rate(self) -> None:
        topics = {entry.topic for entry in TRADEOFF_ENTRIES}
        assert any("frame rate" in t.lower() for t in topics)

    def test_documents_windows(self) -> None:
        topics = {entry.topic for entry in TRADEOFF_ENTRIES}
        assert any("Windows" in t for t in topics)

    def test_documents_fps_counter(self) -> None:
        topics = {entry.topic for entry in TRADEOFF_ENTRIES}
        assert any("FPSCounter" in t for t in topics)

    def test_documents_grid_size_guidance(self) -> None:
        topics = {entry.topic for entry in TRADEOFF_ENTRIES}
        assert any("4,800" in t for t in topics)


# ---------------------------------------------------------------------------
# TRADEOFF_CATEGORIES
# ---------------------------------------------------------------------------


class TestTradeoffCategories:
    """TRADEOFF_CATEGORIES frozenset."""

    def test_is_frozenset(self) -> None:
        assert isinstance(TRADEOFF_CATEGORIES, frozenset)

    def test_not_empty(self) -> None:
        assert len(TRADEOFF_CATEGORIES) > 0

    def test_matches_catalog(self) -> None:
        """Every category in the catalog should be in the frozenset."""
        cats_from_catalog = {
            entry.category for entry in TRADEOFF_ENTRIES
        }
        assert cats_from_catalog == TRADEOFF_CATEGORIES

    def test_has_expected_categories(self) -> None:
        expected = {"advantage", "limitation", "performance", "guidance"}
        assert expected == TRADEOFF_CATEGORIES


# ---------------------------------------------------------------------------
# get_tradeoffs_by_category
# ---------------------------------------------------------------------------


class TestGetTradeoffsByCategory:
    """get_tradeoffs_by_category() filtering."""

    def test_returns_tuple(self) -> None:
        result = get_tradeoffs_by_category("advantage")
        assert isinstance(result, tuple)

    def test_all_match_category(self) -> None:
        result = get_tradeoffs_by_category("limitation")
        for entry in result:
            assert entry.category == "limitation"

    def test_advantage_not_empty(self) -> None:
        result = get_tradeoffs_by_category("advantage")
        assert len(result) > 0

    def test_limitation_not_empty(self) -> None:
        result = get_tradeoffs_by_category("limitation")
        assert len(result) > 0

    def test_performance_not_empty(self) -> None:
        result = get_tradeoffs_by_category("performance")
        assert len(result) > 0

    def test_guidance_not_empty(self) -> None:
        result = get_tradeoffs_by_category("guidance")
        assert len(result) > 0

    def test_unknown_category_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown category"):
            get_tradeoffs_by_category("nonexistent")

    def test_error_message_lists_known(self) -> None:
        with pytest.raises(ValueError, match="advantage"):
            get_tradeoffs_by_category("nonexistent")


# ---------------------------------------------------------------------------
# format_tradeoffs_for_category
# ---------------------------------------------------------------------------


class TestFormatTradeoffsForCategory:
    """format_tradeoffs_for_category() Markdown output."""

    def test_advantage_header(self) -> None:
        text = format_tradeoffs_for_category("advantage")
        assert "## What Rich Gives Us" in text

    def test_limitation_header(self) -> None:
        text = format_tradeoffs_for_category("limitation")
        assert "## What Rich Does Not Give Us" in text

    def test_performance_header(self) -> None:
        text = format_tradeoffs_for_category("performance")
        assert "## Performance Characteristics" in text

    def test_guidance_header(self) -> None:
        text = format_tradeoffs_for_category("guidance")
        assert "## Practical Guidance" in text

    def test_has_topic_headers(self) -> None:
        text = format_tradeoffs_for_category("limitation")
        assert "### No double buffering" in text

    def test_has_caveat_when_present(self) -> None:
        text = format_tradeoffs_for_category("limitation")
        assert "**Caveat:**" in text

    def test_unknown_category_raises(self) -> None:
        with pytest.raises(ValueError):
            format_tradeoffs_for_category("nonexistent")


# ---------------------------------------------------------------------------
# format_rich_live_tradeoffs_doc
# ---------------------------------------------------------------------------


class TestFormatRichLiveTradeoffsDoc:
    """format_rich_live_tradeoffs_doc() full document output."""

    def test_has_title(self) -> None:
        text = format_rich_live_tradeoffs_doc()
        assert "# Rich Live Display Tradeoffs" in text

    def test_has_entry_count(self) -> None:
        text = format_rich_live_tradeoffs_doc()
        assert "tradeoffs documented" in text

    def test_has_advantage_section(self) -> None:
        text = format_rich_live_tradeoffs_doc()
        assert "## What Rich Gives Us" in text

    def test_has_limitation_section(self) -> None:
        text = format_rich_live_tradeoffs_doc()
        assert "## What Rich Does Not Give Us" in text

    def test_has_performance_section(self) -> None:
        text = format_rich_live_tradeoffs_doc()
        assert "## Performance Characteristics" in text

    def test_has_guidance_section(self) -> None:
        text = format_rich_live_tradeoffs_doc()
        assert "## Practical Guidance" in text

    def test_not_empty(self) -> None:
        text = format_rich_live_tradeoffs_doc()
        assert len(text) > 100

    def test_all_categories_present(self) -> None:
        """Every category in the catalog should appear in the output."""
        text = format_rich_live_tradeoffs_doc()
        for cat in TRADEOFF_CATEGORIES:
            entries = get_tradeoffs_by_category(cat)
            assert any(
                entry.topic in text for entry in entries
            ), f"Category {cat!r} topics not found in document"

    def test_mentions_curses(self) -> None:
        text = format_rich_live_tradeoffs_doc()
        assert "curses" in text

    def test_mentions_rich(self) -> None:
        text = format_rich_live_tradeoffs_doc()
        assert "Rich" in text

    def test_mentions_double_buffering(self) -> None:
        text = format_rich_live_tradeoffs_doc()
        assert "double" in text.lower()

    def test_mentions_flicker(self) -> None:
        text = format_rich_live_tradeoffs_doc()
        assert "flicker" in text.lower()


# ---------------------------------------------------------------------------
# Package exports
# ---------------------------------------------------------------------------


class TestPackageExports:
    """Rich Live tradeoffs available from the wyby package."""

    def test_entries_importable(self) -> None:
        from wyby import TRADEOFF_ENTRIES as E  # noqa: N811
        assert E is TRADEOFF_ENTRIES

    def test_entry_class_importable(self) -> None:
        from wyby import RichLiveTradeoff as C  # noqa: N811
        assert C is RichLiveTradeoff

    def test_categories_importable(self) -> None:
        from wyby import TRADEOFF_CATEGORIES as C  # noqa: N811
        assert C is TRADEOFF_CATEGORIES

    def test_get_tradeoffs_by_category_importable(self) -> None:
        from wyby import get_tradeoffs_by_category as f
        assert f is get_tradeoffs_by_category

    def test_format_doc_importable(self) -> None:
        from wyby import format_rich_live_tradeoffs_doc as f
        assert f is format_rich_live_tradeoffs_doc

    def test_format_for_category_importable(self) -> None:
        from wyby import format_tradeoffs_for_category as f
        assert f is format_tradeoffs_for_category

    def test_entries_in_all(self) -> None:
        import wyby
        assert "TRADEOFF_ENTRIES" in wyby.__all__

    def test_entry_class_in_all(self) -> None:
        import wyby
        assert "RichLiveTradeoff" in wyby.__all__

    def test_categories_in_all(self) -> None:
        import wyby
        assert "TRADEOFF_CATEGORIES" in wyby.__all__

    def test_get_tradeoffs_in_all(self) -> None:
        import wyby
        assert "get_tradeoffs_by_category" in wyby.__all__

    def test_format_doc_in_all(self) -> None:
        import wyby
        assert "format_rich_live_tradeoffs_doc" in wyby.__all__

    def test_format_for_category_in_all(self) -> None:
        import wyby
        assert "format_tradeoffs_for_category" in wyby.__all__
