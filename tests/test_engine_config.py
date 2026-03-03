"""Tests for wyby.app — EngineConfig dataclass."""

from __future__ import annotations

import dataclasses

import pytest

from wyby.app import (
    EngineConfig,
    Engine,
    _DEFAULT_HEIGHT,
    _DEFAULT_TITLE,
    _DEFAULT_TPS,
    _DEFAULT_WIDTH,
    _MAX_HEIGHT,
    _MAX_TPS,
    _MAX_WIDTH,
    _MIN_HEIGHT,
    _MIN_TPS,
    _MIN_WIDTH,
)


# ---------------------------------------------------------------------------
# Default construction
# ---------------------------------------------------------------------------


class TestEngineConfigDefaults:
    """EngineConfig() with no arguments should use sensible defaults."""

    def test_default_title(self) -> None:
        cfg = EngineConfig()
        assert cfg.title == _DEFAULT_TITLE

    def test_default_width(self) -> None:
        cfg = EngineConfig()
        assert cfg.width == _DEFAULT_WIDTH

    def test_default_height(self) -> None:
        cfg = EngineConfig()
        assert cfg.height == _DEFAULT_HEIGHT

    def test_default_tps(self) -> None:
        cfg = EngineConfig()
        assert cfg.tps == _DEFAULT_TPS

    def test_default_debug(self) -> None:
        cfg = EngineConfig()
        assert cfg.debug is False

    def test_default_show_fps(self) -> None:
        cfg = EngineConfig()
        assert cfg.show_fps is False


# ---------------------------------------------------------------------------
# Custom construction
# ---------------------------------------------------------------------------


class TestEngineConfigCustom:
    """EngineConfig() with explicit arguments."""

    def test_custom_title(self) -> None:
        cfg = EngineConfig(title="My Roguelike")
        assert cfg.title == "My Roguelike"

    def test_custom_width(self) -> None:
        cfg = EngineConfig(width=120)
        assert cfg.width == 120

    def test_custom_height(self) -> None:
        cfg = EngineConfig(height=40)
        assert cfg.height == 40

    def test_custom_tps(self) -> None:
        cfg = EngineConfig(tps=60)
        assert cfg.tps == 60

    def test_custom_debug(self) -> None:
        cfg = EngineConfig(debug=True)
        assert cfg.debug is True

    def test_custom_show_fps(self) -> None:
        cfg = EngineConfig(show_fps=True)
        assert cfg.show_fps is True

    def test_all_custom(self) -> None:
        cfg = EngineConfig(
            title="Snake", width=40, height=20, tps=60,
            debug=True, show_fps=True,
        )
        assert cfg.title == "Snake"
        assert cfg.width == 40
        assert cfg.height == 20
        assert cfg.tps == 60
        assert cfg.debug is True
        assert cfg.show_fps is True

    def test_minimum_dimensions(self) -> None:
        cfg = EngineConfig(width=_MIN_WIDTH, height=_MIN_HEIGHT)
        assert cfg.width == _MIN_WIDTH
        assert cfg.height == _MIN_HEIGHT

    def test_maximum_dimensions(self) -> None:
        cfg = EngineConfig(width=_MAX_WIDTH, height=_MAX_HEIGHT)
        assert cfg.width == _MAX_WIDTH
        assert cfg.height == _MAX_HEIGHT

    def test_minimum_tps(self) -> None:
        cfg = EngineConfig(tps=_MIN_TPS)
        assert cfg.tps == _MIN_TPS

    def test_maximum_tps(self) -> None:
        cfg = EngineConfig(tps=_MAX_TPS)
        assert cfg.tps == _MAX_TPS


# ---------------------------------------------------------------------------
# Frozen (immutable)
# ---------------------------------------------------------------------------


class TestEngineConfigFrozen:
    """EngineConfig is frozen — fields cannot be reassigned."""

    def test_title_is_frozen(self) -> None:
        cfg = EngineConfig()
        with pytest.raises(dataclasses.FrozenInstanceError):
            cfg.title = "New"  # type: ignore[misc]

    def test_width_is_frozen(self) -> None:
        cfg = EngineConfig()
        with pytest.raises(dataclasses.FrozenInstanceError):
            cfg.width = 100  # type: ignore[misc]

    def test_height_is_frozen(self) -> None:
        cfg = EngineConfig()
        with pytest.raises(dataclasses.FrozenInstanceError):
            cfg.height = 50  # type: ignore[misc]

    def test_tps_is_frozen(self) -> None:
        cfg = EngineConfig()
        with pytest.raises(dataclasses.FrozenInstanceError):
            cfg.tps = 60  # type: ignore[misc]

    def test_debug_is_frozen(self) -> None:
        cfg = EngineConfig()
        with pytest.raises(dataclasses.FrozenInstanceError):
            cfg.debug = True  # type: ignore[misc]

    def test_show_fps_is_frozen(self) -> None:
        cfg = EngineConfig()
        with pytest.raises(dataclasses.FrozenInstanceError):
            cfg.show_fps = True  # type: ignore[misc]


# ---------------------------------------------------------------------------
# dataclasses.replace
# ---------------------------------------------------------------------------


class TestEngineConfigReplace:
    """dataclasses.replace should create modified copies."""

    def test_replace_title(self) -> None:
        cfg = EngineConfig(title="Old")
        new = dataclasses.replace(cfg, title="New")
        assert new.title == "New"
        assert cfg.title == "Old"  # Original unchanged.

    def test_replace_width(self) -> None:
        cfg = EngineConfig()
        new = dataclasses.replace(cfg, width=120)
        assert new.width == 120
        assert cfg.width == _DEFAULT_WIDTH

    def test_replace_validates(self) -> None:
        """replace() should still run __post_init__ validation."""
        cfg = EngineConfig()
        with pytest.raises(ValueError, match="width must be between"):
            dataclasses.replace(cfg, width=0)


# ---------------------------------------------------------------------------
# Title validation
# ---------------------------------------------------------------------------


class TestEngineConfigTitleValidation:
    """Title must be a non-empty string."""

    def test_rejects_non_string(self) -> None:
        with pytest.raises(TypeError, match="title must be a str"):
            EngineConfig(title=42)  # type: ignore[arg-type]

    def test_rejects_none(self) -> None:
        with pytest.raises(TypeError, match="title must be a str"):
            EngineConfig(title=None)  # type: ignore[arg-type]

    def test_rejects_empty(self) -> None:
        with pytest.raises(ValueError, match="must not be empty or blank"):
            EngineConfig(title="")

    def test_rejects_blank(self) -> None:
        with pytest.raises(ValueError, match="must not be empty or blank"):
            EngineConfig(title="   ")


# ---------------------------------------------------------------------------
# Width validation
# ---------------------------------------------------------------------------


class TestEngineConfigWidthValidation:
    """Width must be an int in [1, 1000]."""

    def test_rejects_float(self) -> None:
        with pytest.raises(TypeError, match="width must be an int"):
            EngineConfig(width=80.0)  # type: ignore[arg-type]

    def test_rejects_bool(self) -> None:
        with pytest.raises(TypeError, match="width must be an int"):
            EngineConfig(width=True)  # type: ignore[arg-type]

    def test_rejects_zero(self) -> None:
        with pytest.raises(ValueError, match="width must be between"):
            EngineConfig(width=0)

    def test_rejects_negative(self) -> None:
        with pytest.raises(ValueError, match="width must be between"):
            EngineConfig(width=-1)

    def test_rejects_above_max(self) -> None:
        with pytest.raises(ValueError, match="width must be between"):
            EngineConfig(width=_MAX_WIDTH + 1)


# ---------------------------------------------------------------------------
# Height validation
# ---------------------------------------------------------------------------


class TestEngineConfigHeightValidation:
    """Height must be an int in [1, 1000]."""

    def test_rejects_float(self) -> None:
        with pytest.raises(TypeError, match="height must be an int"):
            EngineConfig(height=24.0)  # type: ignore[arg-type]

    def test_rejects_bool(self) -> None:
        with pytest.raises(TypeError, match="height must be an int"):
            EngineConfig(height=True)  # type: ignore[arg-type]

    def test_rejects_zero(self) -> None:
        with pytest.raises(ValueError, match="height must be between"):
            EngineConfig(height=0)

    def test_rejects_above_max(self) -> None:
        with pytest.raises(ValueError, match="height must be between"):
            EngineConfig(height=_MAX_HEIGHT + 1)


# ---------------------------------------------------------------------------
# TPS validation
# ---------------------------------------------------------------------------


class TestEngineConfigTpsValidation:
    """tps must be an int in [1, 240]."""

    def test_rejects_float(self) -> None:
        with pytest.raises(TypeError, match="tps must be an int"):
            EngineConfig(tps=30.0)  # type: ignore[arg-type]

    def test_rejects_bool(self) -> None:
        with pytest.raises(TypeError, match="tps must be an int"):
            EngineConfig(tps=True)  # type: ignore[arg-type]

    def test_rejects_zero(self) -> None:
        with pytest.raises(ValueError, match="tps must be between"):
            EngineConfig(tps=0)

    def test_rejects_above_max(self) -> None:
        with pytest.raises(ValueError, match="tps must be between"):
            EngineConfig(tps=_MAX_TPS + 1)


# ---------------------------------------------------------------------------
# Bool coercion for debug and show_fps
# ---------------------------------------------------------------------------


class TestEngineConfigBoolCoercion:
    """debug and show_fps should coerce truthy/falsy to strict bool."""

    def test_debug_coerces_truthy(self) -> None:
        cfg = EngineConfig(debug=1)  # type: ignore[arg-type]
        assert cfg.debug is True

    def test_debug_coerces_falsy(self) -> None:
        cfg = EngineConfig(debug=0)  # type: ignore[arg-type]
        assert cfg.debug is False

    def test_show_fps_coerces_truthy(self) -> None:
        cfg = EngineConfig(show_fps=1)  # type: ignore[arg-type]
        assert cfg.show_fps is True

    def test_show_fps_coerces_falsy(self) -> None:
        cfg = EngineConfig(show_fps=0)  # type: ignore[arg-type]
        assert cfg.show_fps is False


# ---------------------------------------------------------------------------
# EngineConfig is a dataclass
# ---------------------------------------------------------------------------


class TestEngineConfigIsDataclass:
    """EngineConfig should be a proper dataclass."""

    def test_is_dataclass(self) -> None:
        assert dataclasses.is_dataclass(EngineConfig)

    def test_has_fields(self) -> None:
        fields = {f.name for f in dataclasses.fields(EngineConfig)}
        assert fields == {"title", "width", "height", "tps", "debug", "show_fps"}

    def test_equality(self) -> None:
        a = EngineConfig(title="Snake", width=40, height=20)
        b = EngineConfig(title="Snake", width=40, height=20)
        assert a == b

    def test_inequality(self) -> None:
        a = EngineConfig(width=40)
        b = EngineConfig(width=80)
        assert a != b


# ---------------------------------------------------------------------------
# Engine constructed from EngineConfig
# ---------------------------------------------------------------------------


class TestEngineFromConfig:
    """Engine(config=...) should use the config's values."""

    def test_engine_uses_config_values(self) -> None:
        cfg = EngineConfig(title="Snake", width=40, height=20, tps=60)
        engine = Engine(config=cfg)
        assert engine.title == "Snake"
        assert engine.width == 40
        assert engine.height == 20
        assert engine.tps == 60

    def test_engine_config_property(self) -> None:
        cfg = EngineConfig(title="Snake")
        engine = Engine(config=cfg)
        assert engine.config is cfg

    def test_engine_config_from_kwargs(self) -> None:
        """Engine constructed with kwargs should also expose a config."""
        engine = Engine(title="Snake", width=40, height=20)
        cfg = engine.config
        assert cfg.title == "Snake"
        assert cfg.width == 40
        assert cfg.height == 20

    def test_config_overrides_kwargs(self) -> None:
        """When both config and kwargs are given, config wins."""
        cfg = EngineConfig(title="Config Title")
        engine = Engine(title="Kwarg Title", config=cfg)
        assert engine.title == "Config Title"

    def test_rejects_non_engine_config(self) -> None:
        with pytest.raises(TypeError, match="config must be an EngineConfig"):
            Engine(config="not a config")  # type: ignore[arg-type]

    def test_config_default_engine(self) -> None:
        """Default Engine() should produce a default EngineConfig."""
        engine = Engine()
        assert engine.config == EngineConfig()

    def test_engine_runs_with_config(self) -> None:
        """Engine constructed from config should run without error."""
        cfg = EngineConfig(tps=60)
        engine = Engine(config=cfg)
        engine.run(loop=False)
        assert engine.tick_count == 1


# ---------------------------------------------------------------------------
# Public import
# ---------------------------------------------------------------------------


class TestEngineConfigImport:
    """EngineConfig should be importable from the top-level wyby package."""

    def test_importable_from_wyby(self) -> None:
        from wyby import EngineConfig as FromInit

        assert FromInit is EngineConfig
