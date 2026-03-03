"""Tests for wyby.transforms — tint and flip/rotate transforms."""

from __future__ import annotations

import pytest
from rich.style import Style

from wyby.entity import Entity
from wyby.sprite import Sprite
from wyby.transforms import (
    flip_h,
    flip_v,
    rotate_90,
    rotate_180,
    rotate_270,
    tint,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _entity_at(x: int, y: int, char: str = "@", style: Style | None = None) -> Entity:
    """Create an entity with a Sprite at the given position."""
    e = Entity(x=x, y=y)
    e.add_component(Sprite(char, style))
    return e


def _positions(entities: list[Entity]) -> list[tuple[int, int]]:
    """Extract (x, y) pairs from a list of entities."""
    return [(e.x, e.y) for e in entities]


def _chars(entities: list[Entity]) -> list[str]:
    """Extract sprite chars from a list of entities."""
    return [e.get_component(Sprite).char for e in entities]


# ===========================================================================
# Tint
# ===========================================================================


class TestTint:
    """tint() applies a colour overlay to sprite foregrounds."""

    def test_full_tint_replaces_color(self) -> None:
        entities = [_entity_at(0, 0, style=Style(color="#ff0000"))]
        tint(entities, "#0000ff", strength=1.0)
        sprite = entities[0].get_component(Sprite)
        # Full tint should produce pure blue.
        assert sprite.style.color.name == "#0000ff"

    def test_zero_strength_preserves_color(self) -> None:
        entities = [_entity_at(0, 0, style=Style(color="#ff0000"))]
        tint(entities, "#0000ff", strength=0.0)
        sprite = entities[0].get_component(Sprite)
        assert sprite.style.color.name == "#ff0000"

    def test_half_strength_blends(self) -> None:
        entities = [_entity_at(0, 0, style=Style(color="#000000"))]
        tint(entities, "#ffffff", strength=0.5)
        sprite = entities[0].get_component(Sprite)
        triplet = sprite.style.color.get_truecolor()
        # Midpoint of 0 and 255 with rounding: 128
        assert triplet.red == 128
        assert triplet.green == 128
        assert triplet.blue == 128

    def test_preserves_bold(self) -> None:
        entities = [_entity_at(0, 0, style=Style(color="#ff0000", bold=True))]
        tint(entities, "#00ff00", strength=1.0)
        sprite = entities[0].get_component(Sprite)
        assert sprite.style.bold is True

    def test_preserves_dim(self) -> None:
        entities = [_entity_at(0, 0, style=Style(color="#ff0000", dim=True))]
        tint(entities, "#00ff00", strength=1.0)
        sprite = entities[0].get_component(Sprite)
        assert sprite.style.dim is True

    def test_preserves_bgcolor(self) -> None:
        entities = [_entity_at(0, 0, style=Style(color="#ff0000", bgcolor="#333333"))]
        tint(entities, "#00ff00", strength=1.0)
        sprite = entities[0].get_component(Sprite)
        assert sprite.style.bgcolor.name == "#333333"

    def test_tint_unstyled_sprite(self) -> None:
        """Sprites with no foreground get tinted against white fallback."""
        entities = [_entity_at(0, 0)]
        tint(entities, "#ff0000", strength=1.0)
        sprite = entities[0].get_component(Sprite)
        assert sprite.style.color.name == "#ff0000"

    def test_tint_multiple_entities(self) -> None:
        entities = [
            _entity_at(0, 0, style=Style(color="#ff0000")),
            _entity_at(1, 0, style=Style(color="#00ff00")),
            _entity_at(2, 0, style=Style(color="#0000ff")),
        ]
        tint(entities, "#ffffff", strength=1.0)
        for e in entities:
            sprite = e.get_component(Sprite)
            assert sprite.style.color.name == "#ffffff"

    def test_skips_entities_without_sprite(self) -> None:
        e1 = _entity_at(0, 0, style=Style(color="#ff0000"))
        e2 = Entity(x=1, y=0)  # no Sprite
        tint([e1, e2], "#0000ff", strength=1.0)
        assert e1.get_component(Sprite).style.color.name == "#0000ff"

    def test_empty_list_is_noop(self) -> None:
        tint([], "#ff0000", strength=1.0)  # should not raise

    def test_named_color(self) -> None:
        entities = [_entity_at(0, 0, style=Style(color="#000000"))]
        tint(entities, "red", strength=1.0)
        sprite = entities[0].get_component(Sprite)
        triplet = sprite.style.color.get_truecolor()
        assert triplet.red == 128
        assert triplet.green == 0
        assert triplet.blue == 0

    def test_rejects_invalid_color(self) -> None:
        with pytest.raises(ValueError, match="cannot parse colour"):
            tint([_entity_at(0, 0)], "not_a_color")

    def test_rejects_strength_below_zero(self) -> None:
        with pytest.raises(ValueError, match="between 0.0 and 1.0"):
            tint([_entity_at(0, 0)], "#ff0000", strength=-0.1)

    def test_rejects_strength_above_one(self) -> None:
        with pytest.raises(ValueError, match="between 0.0 and 1.0"):
            tint([_entity_at(0, 0)], "#ff0000", strength=1.5)

    def test_rejects_non_list(self) -> None:
        with pytest.raises(TypeError, match="entities must be a list"):
            tint("not a list", "#ff0000")  # type: ignore[arg-type]


# ===========================================================================
# Flip horizontal
# ===========================================================================


class TestFlipH:
    """flip_h() mirrors entity positions left-right."""

    def test_mirrors_positions(self) -> None:
        entities = [
            _entity_at(0, 0, "A"),
            _entity_at(1, 0, "B"),
            _entity_at(2, 0, "C"),
        ]
        flip_h(entities)
        assert _positions(entities) == [(2, 0), (1, 0), (0, 0)]

    def test_remaps_slash(self) -> None:
        entities = [_entity_at(0, 0, "/"), _entity_at(1, 0, "\\")]
        flip_h(entities)
        assert _chars(entities) == ["\\", "/"]

    def test_remaps_brackets(self) -> None:
        entities = [_entity_at(0, 0, "("), _entity_at(1, 0, ")")]
        flip_h(entities)
        assert _chars(entities) == [")", "("]

    def test_remaps_box_drawing_corners(self) -> None:
        entities = [_entity_at(0, 0, "\u250c"), _entity_at(1, 0, "\u2510")]
        flip_h(entities)
        assert _chars(entities) == ["\u2510", "\u250c"]

    def test_preserves_unmapped_chars(self) -> None:
        entities = [_entity_at(0, 0, "A"), _entity_at(1, 0, "B")]
        flip_h(entities)
        assert _chars(entities) == ["A", "B"]

    def test_2d_layout(self) -> None:
        """Flip a 2D shape: positions mirror around x-axis."""
        entities = [
            _entity_at(0, 0, "#"),
            _entity_at(1, 0, "."),
            _entity_at(0, 1, "."),
            _entity_at(1, 1, "#"),
        ]
        flip_h(entities)
        assert _positions(entities) == [(1, 0), (0, 0), (1, 1), (0, 1)]

    def test_preserves_y_positions(self) -> None:
        entities = [_entity_at(0, 0), _entity_at(2, 1), _entity_at(4, 2)]
        flip_h(entities)
        ys = [e.y for e in entities]
        assert ys == [0, 1, 2]

    def test_single_entity_noop(self) -> None:
        entities = [_entity_at(5, 3, "X")]
        flip_h(entities)
        assert _positions(entities) == [(5, 3)]
        assert _chars(entities) == ["X"]

    def test_empty_list_noop(self) -> None:
        flip_h([])  # should not raise

    def test_rejects_non_list(self) -> None:
        with pytest.raises(TypeError, match="entities must be a list"):
            flip_h("not a list")  # type: ignore[arg-type]

    def test_entities_without_sprite(self) -> None:
        """Entities without Sprite get positions flipped but no char remap."""
        e1 = Entity(x=0, y=0)
        e2 = Entity(x=2, y=0)
        flip_h([e1, e2])
        assert e1.x == 2
        assert e2.x == 0


# ===========================================================================
# Flip vertical
# ===========================================================================


class TestFlipV:
    """flip_v() mirrors entity positions top-bottom."""

    def test_mirrors_positions(self) -> None:
        entities = [
            _entity_at(0, 0, "A"),
            _entity_at(0, 1, "B"),
            _entity_at(0, 2, "C"),
        ]
        flip_v(entities)
        assert _positions(entities) == [(0, 2), (0, 1), (0, 0)]

    def test_remaps_slash(self) -> None:
        entities = [_entity_at(0, 0, "/"), _entity_at(0, 1, "\\")]
        flip_v(entities)
        assert _chars(entities) == ["\\", "/"]

    def test_remaps_half_blocks(self) -> None:
        entities = [_entity_at(0, 0, "\u2580"), _entity_at(0, 1, "\u2584")]
        flip_v(entities)
        assert _chars(entities) == ["\u2584", "\u2580"]

    def test_remaps_box_corners(self) -> None:
        entities = [_entity_at(0, 0, "\u250c"), _entity_at(0, 1, "\u2514")]
        flip_v(entities)
        assert _chars(entities) == ["\u2514", "\u250c"]

    def test_preserves_x_positions(self) -> None:
        entities = [_entity_at(0, 0), _entity_at(1, 1), _entity_at(2, 2)]
        flip_v(entities)
        xs = [e.x for e in entities]
        assert xs == [0, 1, 2]

    def test_single_entity_noop(self) -> None:
        entities = [_entity_at(5, 3)]
        flip_v(entities)
        assert _positions(entities) == [(5, 3)]

    def test_empty_list_noop(self) -> None:
        flip_v([])

    def test_rejects_non_list(self) -> None:
        with pytest.raises(TypeError, match="entities must be a list"):
            flip_v(42)  # type: ignore[arg-type]


# ===========================================================================
# Rotate 90° clockwise
# ===========================================================================


class TestRotate90:
    """rotate_90() rotates entity positions 90° clockwise."""

    def test_horizontal_line_becomes_vertical(self) -> None:
        """A row of 3 entities at y=0 should become a column."""
        entities = [
            _entity_at(0, 0, "A"),
            _entity_at(1, 0, "B"),
            _entity_at(2, 0, "C"),
        ]
        rotate_90(entities)
        assert _positions(entities) == [(0, 0), (0, 1), (0, 2)]

    def test_remaps_line_chars(self) -> None:
        entities = [_entity_at(0, 0, "\u2500"), _entity_at(1, 0, "\u2502")]
        rotate_90(entities)
        assert _chars(entities) == ["\u2502", "\u2500"]

    def test_remaps_box_corners_cycle(self) -> None:
        """Box corners should cycle: ┌→┐→┘→└→┌."""
        entities = [
            _entity_at(0, 0, "\u250c"),  # ┌
            _entity_at(1, 0, "\u2510"),  # ┐
        ]
        rotate_90(entities)
        assert _chars(entities) == ["\u2510", "\u2518"]

    def test_remaps_arrows(self) -> None:
        entities = [_entity_at(0, 0, "^"), _entity_at(1, 0, ">")]
        rotate_90(entities)
        assert _chars(entities) == [">", "v"]

    def test_l_shape(self) -> None:
        """Rotate an L-shape 90° CW."""
        #  ##     #
        #  #   →  ##
        entities = [
            _entity_at(0, 0, "#"),
            _entity_at(1, 0, "#"),
            _entity_at(0, 1, "#"),
        ]
        rotate_90(entities)
        pos = _positions(entities)
        assert (1, 0) in pos
        assert (0, 0) in pos or (1, 1) in pos

    def test_single_entity_noop(self) -> None:
        entities = [_entity_at(5, 3)]
        rotate_90(entities)
        assert _positions(entities) == [(5, 3)]

    def test_empty_list_noop(self) -> None:
        rotate_90([])

    def test_rejects_non_list(self) -> None:
        with pytest.raises(TypeError, match="entities must be a list"):
            rotate_90(42)  # type: ignore[arg-type]

    def test_preserves_min_position(self) -> None:
        """Rotation should anchor at the bounding box min."""
        entities = [
            _entity_at(5, 10, "#"),
            _entity_at(6, 10, "#"),
            _entity_at(7, 10, "#"),
        ]
        rotate_90(entities)
        xs = [e.x for e in entities]
        ys = [e.y for e in entities]
        assert min(xs) == 5
        assert min(ys) == 10


# ===========================================================================
# Rotate 180°
# ===========================================================================


class TestRotate180:
    """rotate_180() rotates entity positions 180°."""

    def test_reverses_horizontal_line(self) -> None:
        entities = [
            _entity_at(0, 0, "A"),
            _entity_at(1, 0, "B"),
            _entity_at(2, 0, "C"),
        ]
        rotate_180(entities)
        assert _positions(entities) == [(2, 0), (1, 0), (0, 0)]

    def test_reverses_vertical_line(self) -> None:
        entities = [
            _entity_at(0, 0, "A"),
            _entity_at(0, 1, "B"),
            _entity_at(0, 2, "C"),
        ]
        rotate_180(entities)
        assert _positions(entities) == [(0, 2), (0, 1), (0, 0)]

    def test_corner_swap(self) -> None:
        """180° should swap ┌↔┘ and ┐↔└."""
        entities = [
            _entity_at(0, 0, "\u250c"),  # ┌
            _entity_at(1, 1, "\u2518"),  # ┘
        ]
        rotate_180(entities)
        assert _chars(entities) == ["\u2518", "\u250c"]

    def test_double_180_is_identity(self) -> None:
        """Rotating 180° twice should restore original positions."""
        entities = [
            _entity_at(0, 0, "#"),
            _entity_at(1, 0, "."),
            _entity_at(0, 1, "."),
            _entity_at(1, 1, "#"),
        ]
        original_positions = _positions(entities)
        rotate_180(entities)
        rotate_180(entities)
        assert _positions(entities) == original_positions

    def test_single_entity_noop(self) -> None:
        entities = [_entity_at(5, 3)]
        rotate_180(entities)
        assert _positions(entities) == [(5, 3)]

    def test_empty_list_noop(self) -> None:
        rotate_180([])

    def test_rejects_non_list(self) -> None:
        with pytest.raises(TypeError, match="entities must be a list"):
            rotate_180("nope")  # type: ignore[arg-type]


# ===========================================================================
# Rotate 270° clockwise (90° counter-clockwise)
# ===========================================================================


class TestRotate270:
    """rotate_270() rotates entity positions 270° CW (= 90° CCW)."""

    def test_horizontal_line_becomes_vertical(self) -> None:
        entities = [
            _entity_at(0, 0, "A"),
            _entity_at(1, 0, "B"),
            _entity_at(2, 0, "C"),
        ]
        rotate_270(entities)
        assert _positions(entities) == [(0, 2), (0, 1), (0, 0)]

    def test_remaps_line_chars(self) -> None:
        entities = [_entity_at(0, 0, "\u2500"), _entity_at(1, 0, "\u2502")]
        rotate_270(entities)
        # 270° CW is inverse of 90° CW: ─→│ under 90°, so ─→│ under 270° too
        # (since ─↔│ is its own inverse in the mapping)
        assert _chars(entities) == ["\u2502", "\u2500"]

    def test_remaps_arrows(self) -> None:
        entities = [_entity_at(0, 0, "^"), _entity_at(1, 0, ">")]
        rotate_270(entities)
        assert _chars(entities) == ["<", "^"]

    def test_90_then_270_is_identity(self) -> None:
        """90° CW followed by 270° CW should restore original."""
        entities = [
            _entity_at(0, 0, "#"),
            _entity_at(1, 0, "."),
            _entity_at(0, 1, "."),
        ]
        original = _positions(entities)
        rotate_90(entities)
        rotate_270(entities)
        assert _positions(entities) == original

    def test_single_entity_noop(self) -> None:
        entities = [_entity_at(5, 3)]
        rotate_270(entities)
        assert _positions(entities) == [(5, 3)]

    def test_empty_list_noop(self) -> None:
        rotate_270([])

    def test_rejects_non_list(self) -> None:
        with pytest.raises(TypeError, match="entities must be a list"):
            rotate_270(3.14)  # type: ignore[arg-type]


# ===========================================================================
# Import from package root
# ===========================================================================


class TestTransformsImport:
    """Transform functions are accessible from the wyby package root."""

    def test_import_tint(self) -> None:
        from wyby import tint as t
        assert t is tint

    def test_import_flip_h(self) -> None:
        from wyby import flip_h as fh
        assert fh is flip_h

    def test_import_flip_v(self) -> None:
        from wyby import flip_v as fv
        assert fv is flip_v

    def test_import_rotate_90(self) -> None:
        from wyby import rotate_90 as r90
        assert r90 is rotate_90

    def test_import_rotate_180(self) -> None:
        from wyby import rotate_180 as r180
        assert r180 is rotate_180

    def test_import_rotate_270(self) -> None:
        from wyby import rotate_270 as r270
        assert r270 is rotate_270
