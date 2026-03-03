"""Tests for the wyby package structure.

Verifies that all planned modules exist, are importable, and contain
module-level docstrings with the expected caveats.
"""

from __future__ import annotations

import importlib
import pkgutil

import pytest

import wyby


# The modules defined in SCOPE.md's "Proposed Package Structure".
# _platform is internal (prefixed with _); the rest are public.
EXPECTED_PUBLIC_MODULES = [
    "input",
    "entity",
    "renderer",
    "grid",
    "color",
    "save",
]

EXPECTED_INTERNAL_MODULES = [
    "_platform",
]

# Modules that have real implementations (no longer stubs).
EXPECTED_EXISTING_MODULES = [
    "app",
    "diagnostics",
    "project_init",
    "scene",
]

ALL_EXPECTED_MODULES = (
    EXPECTED_PUBLIC_MODULES + EXPECTED_INTERNAL_MODULES + EXPECTED_EXISTING_MODULES
)


# ---------------------------------------------------------------------------
# Package-level tests
# ---------------------------------------------------------------------------


class TestPackageImport:
    """The wyby package itself should be importable and well-documented."""

    def test_wyby_is_importable(self) -> None:
        assert wyby is not None

    def test_package_has_docstring(self) -> None:
        assert wyby.__doc__ is not None
        assert "terminal-rendered 2D games" in wyby.__doc__

    def test_package_docstring_notes_pre_release(self) -> None:
        assert "Pre-release" in wyby.__doc__

    def test_package_docstring_lists_modules(self) -> None:
        """The __init__.py docstring should list the planned package layout."""
        for module_name in EXPECTED_PUBLIC_MODULES:
            assert module_name in wyby.__doc__, (
                f"{module_name} not mentioned in package docstring"
            )


# ---------------------------------------------------------------------------
# Module existence and importability
# ---------------------------------------------------------------------------


class TestModuleImports:
    """Every planned module should be importable."""

    @pytest.mark.parametrize("module_name", ALL_EXPECTED_MODULES)
    def test_module_is_importable(self, module_name: str) -> None:
        mod = importlib.import_module(f"wyby.{module_name}")
        assert mod is not None

    def test_all_expected_modules_discovered_by_pkgutil(self) -> None:
        """pkgutil should find all modules in the wyby package."""
        discovered = {
            name
            for _importer, name, _ispkg in pkgutil.iter_modules(
                wyby.__path__, prefix=""
            )
        }
        for module_name in ALL_EXPECTED_MODULES:
            assert module_name in discovered, (
                f"Module {module_name} not discovered by pkgutil"
            )


# ---------------------------------------------------------------------------
# Module docstrings
# ---------------------------------------------------------------------------


class TestModuleDocstrings:
    """Every module should have a docstring describing its purpose."""

    @pytest.mark.parametrize("module_name", ALL_EXPECTED_MODULES)
    def test_module_has_docstring(self, module_name: str) -> None:
        mod = importlib.import_module(f"wyby.{module_name}")
        assert mod.__doc__ is not None, (
            f"wyby.{module_name} is missing a module docstring"
        )
        assert len(mod.__doc__.strip()) > 0

    @pytest.mark.parametrize(
        "module_name",
        EXPECTED_PUBLIC_MODULES + EXPECTED_INTERNAL_MODULES,
    )
    def test_stub_modules_note_not_yet_implemented(self, module_name: str) -> None:
        """Stub modules should clearly state they are not yet implemented."""
        mod = importlib.import_module(f"wyby.{module_name}")
        assert "Not yet implemented" in mod.__doc__, (
            f"wyby.{module_name} docstring should note it is not yet implemented"
        )

    @pytest.mark.parametrize(
        "module_name",
        EXPECTED_PUBLIC_MODULES + EXPECTED_INTERNAL_MODULES,
    )
    def test_stub_modules_contain_caveats(self, module_name: str) -> None:
        """Stub modules should include a Caveats section."""
        mod = importlib.import_module(f"wyby.{module_name}")
        assert "Caveat" in mod.__doc__, (
            f"wyby.{module_name} docstring should include caveats"
        )


# ---------------------------------------------------------------------------
# Module-specific caveat checks
# ---------------------------------------------------------------------------


class TestModuleCaveats:
    """Key design decisions should be documented as caveats in the right modules."""

    def test_input_excludes_keyboard_library(self) -> None:
        mod = importlib.import_module("wyby.input")
        assert "keyboard" in mod.__doc__.lower()

    def test_save_excludes_pickle(self) -> None:
        mod = importlib.import_module("wyby.save")
        assert "pickle" in mod.__doc__.lower()

    def test_renderer_mentions_rich(self) -> None:
        mod = importlib.import_module("wyby.renderer")
        assert "Rich" in mod.__doc__

    def test_platform_is_internal(self) -> None:
        mod = importlib.import_module("wyby._platform")
        assert "internal" in mod.__doc__.lower()

    def test_grid_mentions_aspect_ratio(self) -> None:
        mod = importlib.import_module("wyby.grid")
        assert "aspect ratio" in mod.__doc__.lower()

    def test_color_mentions_truecolor(self) -> None:
        mod = importlib.import_module("wyby.color")
        assert "truecolor" in mod.__doc__.lower() or "Truecolor" in mod.__doc__

    def test_diagnostics_mentions_fps(self) -> None:
        mod = importlib.import_module("wyby.diagnostics")
        assert "FPS" in mod.__doc__ or "fps" in mod.__doc__

    def test_app_mentions_game_loop(self) -> None:
        mod = importlib.import_module("wyby.app")
        assert "game loop" in mod.__doc__.lower()

    def test_entity_mentions_not_full_ecs(self) -> None:
        mod = importlib.import_module("wyby.entity")
        assert "ECS" in mod.__doc__
