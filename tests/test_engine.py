"""Tests for wyby.app — Engine class initialization."""

from __future__ import annotations

import pytest

from wyby.app import (
    Engine,
    _DEFAULT_HEIGHT,
    _DEFAULT_TITLE,
    _DEFAULT_WIDTH,
    _MAX_HEIGHT,
    _MAX_WIDTH,
    _MIN_HEIGHT,
    _MIN_WIDTH,
)


# ---------------------------------------------------------------------------
# Default construction
# ---------------------------------------------------------------------------


class TestEngineDefaults:
    """Engine() with no arguments should use sensible defaults."""

    def test_default_title(self) -> None:
        engine = Engine()
        assert engine.title == _DEFAULT_TITLE

    def test_default_width(self) -> None:
        engine = Engine()
        assert engine.width == _DEFAULT_WIDTH

    def test_default_height(self) -> None:
        engine = Engine()
        assert engine.height == _DEFAULT_HEIGHT

    def test_default_values_are_standard_terminal(self) -> None:
        """Defaults should match the classic 80x24 terminal size."""
        assert _DEFAULT_WIDTH == 80
        assert _DEFAULT_HEIGHT == 24


# ---------------------------------------------------------------------------
# Custom construction
# ---------------------------------------------------------------------------


class TestEngineCustomInit:
    """Engine() with explicit arguments."""

    def test_custom_title(self) -> None:
        engine = Engine(title="My Roguelike")
        assert engine.title == "My Roguelike"

    def test_custom_width(self) -> None:
        engine = Engine(width=120)
        assert engine.width == 120

    def test_custom_height(self) -> None:
        engine = Engine(height=40)
        assert engine.height == 40

    def test_all_custom(self) -> None:
        engine = Engine(title="Snake", width=40, height=20)
        assert engine.title == "Snake"
        assert engine.width == 40
        assert engine.height == 20

    def test_minimum_dimensions(self) -> None:
        engine = Engine(width=_MIN_WIDTH, height=_MIN_HEIGHT)
        assert engine.width == _MIN_WIDTH
        assert engine.height == _MIN_HEIGHT

    def test_maximum_dimensions(self) -> None:
        engine = Engine(width=_MAX_WIDTH, height=_MAX_HEIGHT)
        assert engine.width == _MAX_WIDTH
        assert engine.height == _MAX_HEIGHT


# ---------------------------------------------------------------------------
# Title validation
# ---------------------------------------------------------------------------


class TestEngineTitleValidation:
    """Title must be a non-empty string."""

    def test_rejects_non_string_title(self) -> None:
        with pytest.raises(TypeError, match="title must be a str"):
            Engine(title=42)  # type: ignore[arg-type]

    def test_rejects_none_title(self) -> None:
        with pytest.raises(TypeError, match="title must be a str"):
            Engine(title=None)  # type: ignore[arg-type]

    def test_rejects_empty_title(self) -> None:
        with pytest.raises(ValueError, match="must not be empty or blank"):
            Engine(title="")

    def test_rejects_blank_title(self) -> None:
        with pytest.raises(ValueError, match="must not be empty or blank"):
            Engine(title="   ")

    def test_allows_whitespace_padded_title(self) -> None:
        """A title with non-whitespace content surrounded by spaces is fine."""
        engine = Engine(title="  My Game  ")
        assert engine.title == "  My Game  "


# ---------------------------------------------------------------------------
# Width validation
# ---------------------------------------------------------------------------


class TestEngineWidthValidation:
    """Width must be an int in [1, 1000]."""

    def test_rejects_float_width(self) -> None:
        with pytest.raises(TypeError, match="width must be an int"):
            Engine(width=80.0)  # type: ignore[arg-type]

    def test_rejects_string_width(self) -> None:
        with pytest.raises(TypeError, match="width must be an int"):
            Engine(width="80")  # type: ignore[arg-type]

    def test_rejects_bool_width(self) -> None:
        with pytest.raises(TypeError, match="width must be an int"):
            Engine(width=True)  # type: ignore[arg-type]

    def test_rejects_zero_width(self) -> None:
        with pytest.raises(ValueError, match="width must be between"):
            Engine(width=0)

    def test_rejects_negative_width(self) -> None:
        with pytest.raises(ValueError, match="width must be between"):
            Engine(width=-1)

    def test_rejects_width_above_max(self) -> None:
        with pytest.raises(ValueError, match="width must be between"):
            Engine(width=_MAX_WIDTH + 1)


# ---------------------------------------------------------------------------
# Height validation
# ---------------------------------------------------------------------------


class TestEngineHeightValidation:
    """Height must be an int in [1, 1000]."""

    def test_rejects_float_height(self) -> None:
        with pytest.raises(TypeError, match="height must be an int"):
            Engine(height=24.0)  # type: ignore[arg-type]

    def test_rejects_string_height(self) -> None:
        with pytest.raises(TypeError, match="height must be an int"):
            Engine(height="24")  # type: ignore[arg-type]

    def test_rejects_bool_height(self) -> None:
        with pytest.raises(TypeError, match="height must be an int"):
            Engine(height=True)  # type: ignore[arg-type]

    def test_rejects_zero_height(self) -> None:
        with pytest.raises(ValueError, match="height must be between"):
            Engine(height=0)

    def test_rejects_negative_height(self) -> None:
        with pytest.raises(ValueError, match="height must be between"):
            Engine(height=-1)

    def test_rejects_height_above_max(self) -> None:
        with pytest.raises(ValueError, match="height must be between"):
            Engine(height=_MAX_HEIGHT + 1)


# ---------------------------------------------------------------------------
# Properties are read-only
# ---------------------------------------------------------------------------


class TestEngineReadOnlyProperties:
    """Engine properties should not be directly settable."""

    def test_title_is_read_only(self) -> None:
        engine = Engine()
        with pytest.raises(AttributeError):
            engine.title = "New Title"  # type: ignore[misc]

    def test_width_is_read_only(self) -> None:
        engine = Engine()
        with pytest.raises(AttributeError):
            engine.width = 100  # type: ignore[misc]

    def test_height_is_read_only(self) -> None:
        engine = Engine()
        with pytest.raises(AttributeError):
            engine.height = 50  # type: ignore[misc]


# ---------------------------------------------------------------------------
# __repr__
# ---------------------------------------------------------------------------


class TestEngineRepr:
    """Engine.__repr__ should be informative and eval-safe."""

    def test_repr_default(self) -> None:
        engine = Engine()
        r = repr(engine)
        assert "Engine(" in r
        assert "'wyby'" in r
        assert "80" in r
        assert "24" in r

    def test_repr_custom(self) -> None:
        engine = Engine(title="Snake", width=40, height=20)
        assert repr(engine) == "Engine(title='Snake', width=40, height=20)"


# ---------------------------------------------------------------------------
# Public re-export from wyby package
# ---------------------------------------------------------------------------


class TestEngineImport:
    """Engine should be importable from the top-level wyby package."""

    def test_importable_from_wyby(self) -> None:
        from wyby import Engine as EngineFromInit

        assert EngineFromInit is Engine
