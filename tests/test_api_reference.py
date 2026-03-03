"""Tests for the api_reference module."""

from __future__ import annotations

from wyby.api_reference import (
    API_CAVEATS,
    API_MODULES,
    ApiCaveat,
    ApiEntry,
    ModuleInfo,
    caveats_by_category,
    format_api_caveats,
    format_api_reference,
    generate_api_reference,
    modules_by_category,
)


# ---------------------------------------------------------------------------
# ModuleInfo
# ---------------------------------------------------------------------------


class TestModuleInfo:
    """ModuleInfo construction, repr, and equality."""

    def test_attributes(self) -> None:
        mod = ModuleInfo(
            name="app", description="Game loop.", category="core",
        )
        assert mod.name == "app"
        assert mod.description == "Game loop."
        assert mod.category == "core"

    def test_repr(self) -> None:
        mod = ModuleInfo(
            name="scene", description="Scene stack.", category="core",
        )
        text = repr(mod)
        assert "scene" in text
        assert "core" in text

    def test_equality(self) -> None:
        a = ModuleInfo(name="app", description="desc", category="core")
        b = ModuleInfo(name="app", description="desc", category="core")
        assert a == b

    def test_inequality(self) -> None:
        a = ModuleInfo(name="app", description="desc", category="core")
        b = ModuleInfo(name="scene", description="desc", category="core")
        assert a != b

    def test_inequality_different_type(self) -> None:
        mod = ModuleInfo(name="app", description="desc", category="core")
        assert mod != "not a module"


# ---------------------------------------------------------------------------
# API_MODULES catalog
# ---------------------------------------------------------------------------


class TestApiModulesCatalog:
    """API_MODULES catalog completeness and structure."""

    def test_not_empty(self) -> None:
        assert len(API_MODULES) > 0

    def test_all_are_module_info(self) -> None:
        for mod in API_MODULES:
            assert isinstance(mod, ModuleInfo)

    def test_core_modules_present(self) -> None:
        names = {m.name for m in API_MODULES if m.category == "core"}
        assert "app" in names
        assert "scene" in names
        assert "entity" in names

    def test_rendering_modules_present(self) -> None:
        names = {m.name for m in API_MODULES if m.category == "rendering"}
        assert "renderer" in names
        assert "grid" in names
        assert "color" in names

    def test_input_modules_present(self) -> None:
        names = {m.name for m in API_MODULES if m.category == "input"}
        assert "input" in names

    def test_ui_modules_present(self) -> None:
        names = {m.name for m in API_MODULES if m.category == "ui"}
        assert "widget" in names
        assert "button" in names

    def test_physics_modules_present(self) -> None:
        names = {m.name for m in API_MODULES if m.category == "physics"}
        assert "collision" in names
        assert "physics" in names

    def test_platform_modules_present(self) -> None:
        names = {m.name for m in API_MODULES if m.category == "platform"}
        assert "diagnostics" in names
        assert "resize" in names

    def test_all_have_descriptions(self) -> None:
        for mod in API_MODULES:
            assert mod.description, f"Module {mod.name!r} has no description"

    def test_all_have_categories(self) -> None:
        for mod in API_MODULES:
            assert mod.category, f"Module {mod.name!r} has no category"

    def test_no_internal_modules(self) -> None:
        """Internal modules (prefixed with _) should not be in the catalog."""
        for mod in API_MODULES:
            assert not mod.name.startswith("_"), (
                f"Internal module {mod.name!r} in API_MODULES"
            )


# ---------------------------------------------------------------------------
# modules_by_category
# ---------------------------------------------------------------------------


class TestModulesByCategory:
    """modules_by_category() grouping."""

    def test_returns_dict(self) -> None:
        result = modules_by_category()
        assert isinstance(result, dict)

    def test_has_expected_categories(self) -> None:
        result = modules_by_category()
        assert "core" in result
        assert "rendering" in result
        assert "input" in result
        assert "ui" in result
        assert "physics" in result
        assert "platform" in result

    def test_all_modules_accounted_for(self) -> None:
        result = modules_by_category()
        total = sum(len(v) for v in result.values())
        assert total == len(API_MODULES)


# ---------------------------------------------------------------------------
# ApiCaveat
# ---------------------------------------------------------------------------


class TestApiCaveat:
    """ApiCaveat construction, repr, and equality."""

    def test_attributes(self) -> None:
        caveat = ApiCaveat(
            topic="Pre-release", description="Unstable.", category="stability",
        )
        assert caveat.topic == "Pre-release"
        assert caveat.description == "Unstable."
        assert caveat.category == "stability"

    def test_repr(self) -> None:
        caveat = ApiCaveat(
            topic="No pickle", description="...", category="architecture",
        )
        text = repr(caveat)
        assert "No pickle" in text
        assert "architecture" in text

    def test_equality(self) -> None:
        a = ApiCaveat(topic="A", description="desc", category="stability")
        b = ApiCaveat(topic="A", description="desc", category="stability")
        assert a == b

    def test_inequality(self) -> None:
        a = ApiCaveat(topic="A", description="desc", category="stability")
        b = ApiCaveat(topic="B", description="desc", category="stability")
        assert a != b

    def test_inequality_different_type(self) -> None:
        caveat = ApiCaveat(
            topic="A", description="desc", category="stability",
        )
        assert caveat != "not a caveat"


# ---------------------------------------------------------------------------
# API_CAVEATS catalog
# ---------------------------------------------------------------------------


class TestApiCaveatsCatalog:
    """API_CAVEATS catalog completeness and structure."""

    def test_not_empty(self) -> None:
        assert len(API_CAVEATS) > 0

    def test_all_are_api_caveat(self) -> None:
        for caveat in API_CAVEATS:
            assert isinstance(caveat, ApiCaveat)

    def test_has_stability_caveats(self) -> None:
        cats = {c.category for c in API_CAVEATS}
        assert "stability" in cats

    def test_has_rendering_caveats(self) -> None:
        cats = {c.category for c in API_CAVEATS}
        assert "rendering" in cats

    def test_has_input_caveats(self) -> None:
        cats = {c.category for c in API_CAVEATS}
        assert "input" in cats

    def test_has_architecture_caveats(self) -> None:
        cats = {c.category for c in API_CAVEATS}
        assert "architecture" in cats

    def test_has_platform_caveats(self) -> None:
        cats = {c.category for c in API_CAVEATS}
        assert "platform" in cats

    def test_all_have_topics(self) -> None:
        for caveat in API_CAVEATS:
            assert caveat.topic, f"Caveat has no topic: {caveat!r}"

    def test_all_have_descriptions(self) -> None:
        for caveat in API_CAVEATS:
            assert caveat.description, f"Caveat has no description: {caveat!r}"

    def test_pre_release_documented(self) -> None:
        topics = {c.topic for c in API_CAVEATS}
        assert "Pre-release API" in topics

    def test_no_pickle_documented(self) -> None:
        topics = {c.topic for c in API_CAVEATS}
        assert "No pickle for save/load" in topics

    def test_no_networking_documented(self) -> None:
        topics = {c.topic for c in API_CAVEATS}
        assert "No networking" in topics


# ---------------------------------------------------------------------------
# caveats_by_category
# ---------------------------------------------------------------------------


class TestCaveatsByCategory:
    """caveats_by_category() grouping."""

    def test_returns_dict(self) -> None:
        result = caveats_by_category()
        assert isinstance(result, dict)

    def test_has_expected_categories(self) -> None:
        result = caveats_by_category()
        assert "stability" in result
        assert "rendering" in result
        assert "input" in result
        assert "architecture" in result
        assert "platform" in result

    def test_all_caveats_accounted_for(self) -> None:
        result = caveats_by_category()
        total = sum(len(v) for v in result.values())
        assert total == len(API_CAVEATS)


# ---------------------------------------------------------------------------
# ApiEntry
# ---------------------------------------------------------------------------


class TestApiEntry:
    """ApiEntry construction, repr, and equality."""

    def test_attributes(self) -> None:
        entry = ApiEntry(
            name="Engine",
            kind="class",
            module="app",
            summary="Game loop engine.",
            category="core",
        )
        assert entry.name == "Engine"
        assert entry.kind == "class"
        assert entry.module == "app"
        assert entry.summary == "Game loop engine."
        assert entry.category == "core"

    def test_repr(self) -> None:
        entry = ApiEntry(
            name="CellBuffer",
            kind="class",
            module="grid",
            summary="Grid buffer.",
            category="rendering",
        )
        text = repr(entry)
        assert "CellBuffer" in text
        assert "class" in text
        assert "grid" in text

    def test_equality(self) -> None:
        a = ApiEntry(
            name="E", kind="class", module="m", summary="s", category="c",
        )
        b = ApiEntry(
            name="E", kind="class", module="m", summary="s", category="c",
        )
        assert a == b

    def test_inequality(self) -> None:
        a = ApiEntry(
            name="A", kind="class", module="m", summary="s", category="c",
        )
        b = ApiEntry(
            name="B", kind="class", module="m", summary="s", category="c",
        )
        assert a != b

    def test_inequality_different_type(self) -> None:
        entry = ApiEntry(
            name="X", kind="class", module="m", summary="s", category="c",
        )
        assert entry != "not an entry"


# ---------------------------------------------------------------------------
# generate_api_reference
# ---------------------------------------------------------------------------


class TestGenerateApiReference:
    """generate_api_reference() introspects the live package."""

    def test_returns_list(self) -> None:
        result = generate_api_reference()
        assert isinstance(result, list)

    def test_not_empty(self) -> None:
        result = generate_api_reference()
        assert len(result) > 0

    def test_all_are_api_entry(self) -> None:
        result = generate_api_reference()
        for entry in result:
            assert isinstance(entry, ApiEntry)

    def test_contains_engine(self) -> None:
        result = generate_api_reference()
        names = {e.name for e in result}
        assert "Engine" in names

    def test_contains_scene(self) -> None:
        result = generate_api_reference()
        names = {e.name for e in result}
        assert "Scene" in names

    def test_contains_cell_buffer(self) -> None:
        result = generate_api_reference()
        names = {e.name for e in result}
        assert "CellBuffer" in names

    def test_contains_input_manager(self) -> None:
        result = generate_api_reference()
        names = {e.name for e in result}
        assert "InputManager" in names

    def test_engine_is_class(self) -> None:
        result = generate_api_reference()
        engine_entries = [e for e in result if e.name == "Engine"]
        assert len(engine_entries) == 1
        assert engine_entries[0].kind == "class"

    def test_parse_input_events_is_function(self) -> None:
        result = generate_api_reference()
        entries = [e for e in result if e.name == "parse_input_events"]
        assert len(entries) == 1
        assert entries[0].kind == "function"

    def test_entries_have_summaries(self) -> None:
        result = generate_api_reference()
        for entry in result:
            assert entry.summary, f"Entry {entry.name!r} has no summary"

    def test_entries_have_modules(self) -> None:
        result = generate_api_reference()
        for entry in result:
            assert entry.module, f"Entry {entry.name!r} has no module"

    def test_sorted_by_category_then_name(self) -> None:
        """Entries should be sorted by category order, then alphabetically."""
        result = generate_api_reference()
        # Verify entries within the same category are alphabetically sorted.
        prev_cat = ""
        prev_name = ""
        for entry in result:
            if entry.category == prev_cat:
                assert entry.name >= prev_name, (
                    f"{entry.name!r} should come after {prev_name!r} "
                    f"in category {entry.category!r}"
                )
            prev_cat = entry.category
            prev_name = entry.name


# ---------------------------------------------------------------------------
# format_api_reference
# ---------------------------------------------------------------------------


class TestFormatApiReference:
    """format_api_reference() produces Markdown output."""

    def test_empty_entries(self) -> None:
        assert format_api_reference([]) == "No API entries found."

    def test_has_header(self) -> None:
        entries = generate_api_reference()
        text = format_api_reference(entries)
        assert "## API Reference" in text

    def test_has_pre_release_disclaimer(self) -> None:
        entries = generate_api_reference()
        text = format_api_reference(entries)
        assert "Pre-release" in text

    def test_has_module_overview(self) -> None:
        entries = generate_api_reference()
        text = format_api_reference(entries)
        assert "### Module Overview" in text

    def test_has_symbols_section(self) -> None:
        entries = generate_api_reference()
        text = format_api_reference(entries)
        assert "### Symbols by Category" in text

    def test_has_category_sections(self) -> None:
        entries = generate_api_reference()
        text = format_api_reference(entries)
        assert "#### Core" in text
        assert "#### Rendering" in text
        assert "#### Input" in text

    def test_has_module_table(self) -> None:
        entries = generate_api_reference()
        text = format_api_reference(entries)
        assert "| Module | Description |" in text
        assert "`wyby.app`" in text

    def test_has_symbol_table(self) -> None:
        entries = generate_api_reference()
        text = format_api_reference(entries)
        assert "| Symbol | Kind | Module | Summary |" in text
        assert "`Engine`" in text

    def test_has_caveats_section(self) -> None:
        entries = generate_api_reference()
        text = format_api_reference(entries)
        assert "### API Caveats" in text

    def test_single_entry(self) -> None:
        entries = [
            ApiEntry(
                name="Foo",
                kind="class",
                module="bar",
                summary="A foo class.",
                category="core",
            ),
        ]
        text = format_api_reference(entries)
        assert "## API Reference" in text
        assert "`Foo`" in text
        assert "class" in text

    def test_live_reference_not_empty(self) -> None:
        """Formatting the live API reference should produce substantial output."""
        entries = generate_api_reference()
        text = format_api_reference(entries)
        # Should be a substantial document.
        assert len(text) > 500


# ---------------------------------------------------------------------------
# format_api_caveats
# ---------------------------------------------------------------------------


class TestFormatApiCaveats:
    """format_api_caveats() output."""

    def test_not_empty(self) -> None:
        text = format_api_caveats()
        assert len(text) > 0

    def test_has_stability_section(self) -> None:
        text = format_api_caveats()
        assert "**Stability & Installation**" in text

    def test_has_rendering_section(self) -> None:
        text = format_api_caveats()
        assert "**Rendering**" in text

    def test_has_input_section(self) -> None:
        text = format_api_caveats()
        assert "**Input**" in text

    def test_has_architecture_section(self) -> None:
        text = format_api_caveats()
        assert "**Architecture**" in text

    def test_has_platform_section(self) -> None:
        text = format_api_caveats()
        assert "**Platform & Performance**" in text

    def test_includes_caveat_topics(self) -> None:
        text = format_api_caveats()
        assert "Pre-release API" in text
        assert "No pickle" in text
        assert "No networking" in text

    def test_includes_bold_topics(self) -> None:
        text = format_api_caveats()
        assert "**Pre-release API**" in text


# ---------------------------------------------------------------------------
# Integration: module catalog matches __init__.py imports
# ---------------------------------------------------------------------------


class TestCatalogConsistency:
    """API_MODULES should cover all public modules imported by __init__.py."""

    def test_catalog_module_names_are_unique(self) -> None:
        names = [m.name for m in API_MODULES]
        assert len(names) == len(set(names)), "Duplicate module names in API_MODULES"

    def test_generated_entries_cover_key_symbols(self) -> None:
        """Key symbols from __all__ should appear in generated entries."""
        entries = generate_api_reference()
        entry_names = {e.name for e in entries}
        # Check a representative sample of important symbols.
        key_symbols = [
            "Engine", "Scene", "Entity", "CellBuffer", "InputManager",
            "Renderer", "Widget", "AABB",
        ]
        for sym in key_symbols:
            assert sym in entry_names, (
                f"{sym!r} from wyby.__all__ not in generated entries"
            )
