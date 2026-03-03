"""Tests for wyby.limitations_caveats — comprehensive limitations catalog."""

from __future__ import annotations

import pytest

from wyby.limitations_caveats import (
    LIMITATION_CATEGORIES,
    LIMITATIONS,
    SEVERITIES,
    Limitation,
    format_limitations_doc,
    format_limitations_for_category,
    get_limitations_by_category,
    get_limitations_by_severity,
)


# ---------------------------------------------------------------------------
# Limitation dataclass
# ---------------------------------------------------------------------------


class TestLimitation:
    """Limitation frozen dataclass."""

    def test_fields(self) -> None:
        lim = Limitation(
            category="rendering",
            topic="Test limitation",
            description="A test description.",
            severity="warning",
            workaround="Do something.",
        )
        assert lim.category == "rendering"
        assert lim.topic == "Test limitation"
        assert lim.description == "A test description."
        assert lim.severity == "warning"
        assert lim.workaround == "Do something."

    def test_workaround_defaults_to_none(self) -> None:
        lim = Limitation(
            category="input",
            topic="No workaround",
            description="desc",
            severity="info",
        )
        assert lim.workaround is None

    def test_frozen(self) -> None:
        lim = Limitation("a", "b", "c", "info")
        with pytest.raises(AttributeError):
            lim.category = "other"  # type: ignore[misc]

    def test_equality(self) -> None:
        a = Limitation("a", "b", "c", "info", "w")
        b = Limitation("a", "b", "c", "info", "w")
        assert a == b

    def test_inequality(self) -> None:
        a = Limitation("a", "b", "c", "info")
        b = Limitation("a", "x", "c", "info")
        assert a != b


# ---------------------------------------------------------------------------
# LIMITATIONS catalog
# ---------------------------------------------------------------------------


class TestLimitationsCatalog:
    """The built-in catalog of limitations."""

    def test_is_tuple(self) -> None:
        assert isinstance(LIMITATIONS, tuple)

    def test_not_empty(self) -> None:
        assert len(LIMITATIONS) > 0

    def test_all_entries_are_limitation(self) -> None:
        for lim in LIMITATIONS:
            assert isinstance(lim, Limitation)

    def test_all_have_category(self) -> None:
        for lim in LIMITATIONS:
            assert lim.category, f"Limitation {lim.topic!r} has no category"

    def test_all_have_topic(self) -> None:
        for lim in LIMITATIONS:
            assert lim.topic, "Limitation has empty topic"

    def test_all_have_description(self) -> None:
        for lim in LIMITATIONS:
            assert lim.description, (
                f"Limitation {lim.topic!r} has no description"
            )

    def test_all_have_valid_severity(self) -> None:
        for lim in LIMITATIONS:
            assert lim.severity in SEVERITIES, (
                f"Limitation {lim.topic!r} has invalid severity "
                f"{lim.severity!r}"
            )

    def test_has_rendering_limitations(self) -> None:
        cats = {lim.category for lim in LIMITATIONS}
        assert "rendering" in cats

    def test_has_input_limitations(self) -> None:
        cats = {lim.category for lim in LIMITATIONS}
        assert "input" in cats

    def test_has_physics_limitations(self) -> None:
        cats = {lim.category for lim in LIMITATIONS}
        assert "physics" in cats

    def test_has_entity_model_limitations(self) -> None:
        cats = {lim.category for lim in LIMITATIONS}
        assert "entity_model" in cats

    def test_has_terminal_limitations(self) -> None:
        cats = {lim.category for lim in LIMITATIONS}
        assert "terminal" in cats

    def test_has_networking_limitations(self) -> None:
        cats = {lim.category for lim in LIMITATIONS}
        assert "networking" in cats

    def test_has_save_load_limitations(self) -> None:
        cats = {lim.category for lim in LIMITATIONS}
        assert "save_load" in cats

    def test_has_image_conversion_limitations(self) -> None:
        cats = {lim.category for lim in LIMITATIONS}
        assert "image_conversion" in cats

    def test_has_platform_limitations(self) -> None:
        cats = {lim.category for lim in LIMITATIONS}
        assert "platform" in cats

    def test_has_api_limitations(self) -> None:
        cats = {lim.category for lim in LIMITATIONS}
        assert "api" in cats

    def test_has_mouse_limitations(self) -> None:
        cats = {lim.category for lim in LIMITATIONS}
        assert "mouse" in cats

    def test_no_frame_rate_guarantee_documented(self) -> None:
        topics = {lim.topic for lim in LIMITATIONS}
        assert "No frame rate guarantee" in topics

    def test_no_networking_documented(self) -> None:
        topics = {lim.topic for lim in LIMITATIONS}
        assert "No networking support" in topics

    def test_no_pickle_documented(self) -> None:
        topics = {lim.topic for lim in LIMITATIONS}
        assert "No pickle — by design" in topics

    def test_unstable_api_documented(self) -> None:
        topics = {lim.topic for lim in LIMITATIONS}
        assert "Unstable pre-release API" in topics


# ---------------------------------------------------------------------------
# LIMITATION_CATEGORIES
# ---------------------------------------------------------------------------


class TestLimitationCategories:
    """LIMITATION_CATEGORIES frozenset."""

    def test_is_frozenset(self) -> None:
        assert isinstance(LIMITATION_CATEGORIES, frozenset)

    def test_not_empty(self) -> None:
        assert len(LIMITATION_CATEGORIES) > 0

    def test_matches_catalog(self) -> None:
        """Every category in the catalog should be in the frozenset."""
        cats_from_catalog = {lim.category for lim in LIMITATIONS}
        assert cats_from_catalog == LIMITATION_CATEGORIES


# ---------------------------------------------------------------------------
# SEVERITIES
# ---------------------------------------------------------------------------


class TestSeverities:
    """SEVERITIES frozenset."""

    def test_contains_info(self) -> None:
        assert "info" in SEVERITIES

    def test_contains_warning(self) -> None:
        assert "warning" in SEVERITIES

    def test_contains_critical(self) -> None:
        assert "critical" in SEVERITIES

    def test_exactly_three(self) -> None:
        assert len(SEVERITIES) == 3


# ---------------------------------------------------------------------------
# get_limitations_by_category
# ---------------------------------------------------------------------------


class TestGetLimitationsByCategory:
    """get_limitations_by_category() filtering."""

    def test_returns_tuple(self) -> None:
        result = get_limitations_by_category("rendering")
        assert isinstance(result, tuple)

    def test_all_match_category(self) -> None:
        result = get_limitations_by_category("input")
        for lim in result:
            assert lim.category == "input"

    def test_rendering_not_empty(self) -> None:
        result = get_limitations_by_category("rendering")
        assert len(result) > 0

    def test_unknown_category_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown category"):
            get_limitations_by_category("nonexistent")

    def test_error_message_lists_known(self) -> None:
        with pytest.raises(ValueError, match="rendering"):
            get_limitations_by_category("nonexistent")


# ---------------------------------------------------------------------------
# get_limitations_by_severity
# ---------------------------------------------------------------------------


class TestGetLimitationsBySeverity:
    """get_limitations_by_severity() filtering."""

    def test_returns_tuple(self) -> None:
        result = get_limitations_by_severity("info")
        assert isinstance(result, tuple)

    def test_all_match_severity(self) -> None:
        result = get_limitations_by_severity("warning")
        for lim in result:
            assert lim.severity == "warning"

    def test_info_not_empty(self) -> None:
        result = get_limitations_by_severity("info")
        assert len(result) > 0

    def test_warning_not_empty(self) -> None:
        result = get_limitations_by_severity("warning")
        assert len(result) > 0

    def test_critical_not_empty(self) -> None:
        result = get_limitations_by_severity("critical")
        assert len(result) > 0

    def test_unknown_severity_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown severity"):
            get_limitations_by_severity("fatal")

    def test_error_message_lists_valid(self) -> None:
        with pytest.raises(ValueError, match="info"):
            get_limitations_by_severity("fatal")

    def test_all_severities_covered(self) -> None:
        """Every severity level should have at least one limitation."""
        for sev in SEVERITIES:
            result = get_limitations_by_severity(sev)
            assert len(result) > 0, (
                f"No limitations with severity {sev!r}"
            )


# ---------------------------------------------------------------------------
# format_limitations_for_category
# ---------------------------------------------------------------------------


class TestFormatLimitationsForCategory:
    """format_limitations_for_category() Markdown output."""

    def test_has_category_header(self) -> None:
        text = format_limitations_for_category("rendering")
        assert "## Rendering" in text

    def test_has_topic_headers(self) -> None:
        text = format_limitations_for_category("rendering")
        assert "### No frame rate guarantee" in text

    def test_has_severity(self) -> None:
        text = format_limitations_for_category("rendering")
        assert "**Severity:**" in text

    def test_has_workaround_when_present(self) -> None:
        text = format_limitations_for_category("rendering")
        assert "**Workaround:**" in text

    def test_unknown_category_raises(self) -> None:
        with pytest.raises(ValueError):
            format_limitations_for_category("nonexistent")

    def test_input_category(self) -> None:
        text = format_limitations_for_category("input")
        assert "## Input Handling" in text

    def test_networking_category(self) -> None:
        text = format_limitations_for_category("networking")
        assert "## Networking" in text


# ---------------------------------------------------------------------------
# format_limitations_doc
# ---------------------------------------------------------------------------


class TestFormatLimitationsDoc:
    """format_limitations_doc() full document output."""

    def test_has_title(self) -> None:
        text = format_limitations_doc()
        assert "# wyby Limitations and Caveats" in text

    def test_has_summary_counts(self) -> None:
        text = format_limitations_doc()
        assert "limitations documented" in text
        assert "critical" in text
        assert "warning" in text
        assert "info" in text

    def test_has_rendering_section(self) -> None:
        text = format_limitations_doc()
        assert "## Rendering" in text

    def test_has_input_section(self) -> None:
        text = format_limitations_doc()
        assert "## Input Handling" in text

    def test_has_networking_section(self) -> None:
        text = format_limitations_doc()
        assert "## Networking" in text

    def test_has_physics_section(self) -> None:
        text = format_limitations_doc()
        assert "## Physics" in text

    def test_has_terminal_section(self) -> None:
        text = format_limitations_doc()
        assert "## Terminal Compatibility" in text

    def test_has_platform_section(self) -> None:
        text = format_limitations_doc()
        assert "## Platform Differences" in text

    def test_has_api_section(self) -> None:
        text = format_limitations_doc()
        assert "## API Stability" in text

    def test_not_empty(self) -> None:
        text = format_limitations_doc()
        assert len(text) > 100

    def test_all_categories_present(self) -> None:
        """Every category in the catalog should appear in the output."""
        text = format_limitations_doc()
        for cat in LIMITATION_CATEGORIES:
            lims = get_limitations_by_category(cat)
            # At least one topic from each category should appear.
            assert any(
                lim.topic in text for lim in lims
            ), f"Category {cat!r} topics not found in document"


# ---------------------------------------------------------------------------
# Package exports
# ---------------------------------------------------------------------------


class TestPackageExports:
    """Limitations catalog available from the wyby package."""

    def test_limitations_importable(self) -> None:
        from wyby import LIMITATIONS as L  # noqa: N811
        assert L is LIMITATIONS

    def test_limitation_importable(self) -> None:
        from wyby import Limitation as LC  # noqa: N811
        assert LC is Limitation

    def test_limitation_categories_importable(self) -> None:
        from wyby import LIMITATION_CATEGORIES as LC  # noqa: N811
        assert LC is LIMITATION_CATEGORIES

    def test_get_limitations_by_category_importable(self) -> None:
        from wyby import get_limitations_by_category as f
        assert f is get_limitations_by_category

    def test_get_limitations_by_severity_importable(self) -> None:
        from wyby import get_limitations_by_severity as f
        assert f is get_limitations_by_severity

    def test_format_limitations_doc_importable(self) -> None:
        from wyby import format_limitations_doc as f
        assert f is format_limitations_doc

    def test_limitations_in_all(self) -> None:
        import wyby
        assert "LIMITATIONS" in wyby.__all__

    def test_limitation_in_all(self) -> None:
        import wyby
        assert "Limitation" in wyby.__all__

    def test_limitation_categories_in_all(self) -> None:
        import wyby
        assert "LIMITATION_CATEGORIES" in wyby.__all__

    def test_get_limitations_by_category_in_all(self) -> None:
        import wyby
        assert "get_limitations_by_category" in wyby.__all__

    def test_get_limitations_by_severity_in_all(self) -> None:
        import wyby
        assert "get_limitations_by_severity" in wyby.__all__

    def test_format_limitations_doc_in_all(self) -> None:
        import wyby
        assert "format_limitations_doc" in wyby.__all__
