"""Tests for wyby.layer — Layer enum and LayerStack compositing."""

from __future__ import annotations

import pytest

from wyby.grid import Cell, CellBuffer, _DEFAULT_CHAR
from wyby.layer import Layer, LayerStack, _is_transparent


# ---------------------------------------------------------------------------
# Layer enum
# ---------------------------------------------------------------------------


class TestLayerEnum:
    """Layer enum defines the three rendering layers in draw order."""

    def test_has_three_members(self) -> None:
        assert len(Layer) == 3

    def test_background_is_lowest(self) -> None:
        assert Layer.BACKGROUND < Layer.ENTITIES
        assert Layer.BACKGROUND < Layer.UI

    def test_entities_is_middle(self) -> None:
        assert Layer.ENTITIES > Layer.BACKGROUND
        assert Layer.ENTITIES < Layer.UI

    def test_ui_is_highest(self) -> None:
        assert Layer.UI > Layer.BACKGROUND
        assert Layer.UI > Layer.ENTITIES

    def test_sorted_order(self) -> None:
        assert sorted(Layer) == [Layer.BACKGROUND, Layer.ENTITIES, Layer.UI]

    def test_values_are_ints(self) -> None:
        """IntEnum members should be usable as plain integers."""
        assert int(Layer.BACKGROUND) == 0
        assert int(Layer.ENTITIES) == 1
        assert int(Layer.UI) == 2


# ---------------------------------------------------------------------------
# _is_transparent
# ---------------------------------------------------------------------------


class TestIsTransparent:
    """Transparency detection for compositing."""

    def test_default_cell_is_transparent(self) -> None:
        assert _is_transparent(Cell()) is True

    def test_space_with_no_style_is_transparent(self) -> None:
        assert _is_transparent(Cell(char=" ")) is True

    def test_non_space_char_is_opaque(self) -> None:
        assert _is_transparent(Cell(char="@")) is False

    def test_fg_colour_is_opaque(self) -> None:
        assert _is_transparent(Cell(fg="red")) is False

    def test_bg_colour_is_opaque(self) -> None:
        assert _is_transparent(Cell(bg="blue")) is False

    def test_bold_is_opaque(self) -> None:
        assert _is_transparent(Cell(bold=True)) is False

    def test_dim_is_opaque(self) -> None:
        assert _is_transparent(Cell(dim=True)) is False

    def test_space_with_fg_is_opaque(self) -> None:
        """A space with colour is intentionally styled, not transparent."""
        assert _is_transparent(Cell(char=" ", fg="red")) is False

    def test_space_with_bg_is_opaque(self) -> None:
        assert _is_transparent(Cell(char=" ", bg="blue")) is False


# ---------------------------------------------------------------------------
# LayerStack — Initialisation
# ---------------------------------------------------------------------------


class TestLayerStackInit:
    """LayerStack creates one CellBuffer per layer."""

    def test_width_and_height(self) -> None:
        stack = LayerStack(80, 24)
        assert stack.width == 80
        assert stack.height == 24

    def test_each_layer_exists(self) -> None:
        stack = LayerStack(10, 5)
        for layer in Layer:
            buf = stack[layer]
            assert isinstance(buf, CellBuffer)

    def test_each_layer_has_correct_dimensions(self) -> None:
        stack = LayerStack(10, 5)
        for layer in Layer:
            buf = stack[layer]
            assert buf.width == 10
            assert buf.height == 5

    def test_layers_are_independent_buffers(self) -> None:
        """Each layer must be a separate CellBuffer instance."""
        stack = LayerStack(5, 5)
        bg = stack[Layer.BACKGROUND]
        ent = stack[Layer.ENTITIES]
        ui = stack[Layer.UI]
        assert bg is not ent
        assert bg is not ui
        assert ent is not ui

    def test_dimension_clamping(self) -> None:
        """Dimensions are clamped by CellBuffer's validation."""
        stack = LayerStack(0, -1)
        assert stack.width == 1
        assert stack.height == 1

    def test_rejects_non_int_width(self) -> None:
        with pytest.raises(TypeError):
            LayerStack("80", 24)  # type: ignore[arg-type]

    def test_rejects_non_int_height(self) -> None:
        with pytest.raises(TypeError):
            LayerStack(80, 24.0)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# LayerStack — __getitem__
# ---------------------------------------------------------------------------


class TestLayerStackGetItem:
    """Accessing layers by Layer enum."""

    def test_access_background(self) -> None:
        stack = LayerStack(5, 5)
        buf = stack[Layer.BACKGROUND]
        assert isinstance(buf, CellBuffer)

    def test_access_entities(self) -> None:
        stack = LayerStack(5, 5)
        buf = stack[Layer.ENTITIES]
        assert isinstance(buf, CellBuffer)

    def test_access_ui(self) -> None:
        stack = LayerStack(5, 5)
        buf = stack[Layer.UI]
        assert isinstance(buf, CellBuffer)

    def test_invalid_key_raises_keyerror(self) -> None:
        stack = LayerStack(5, 5)
        with pytest.raises(KeyError):
            stack[99]  # type: ignore[index]


# ---------------------------------------------------------------------------
# LayerStack.clear / clear_layer
# ---------------------------------------------------------------------------


class TestLayerStackClear:
    """clear() and clear_layer() reset cells to defaults."""

    def test_clear_resets_all_layers(self) -> None:
        stack = LayerStack(5, 3)
        stack[Layer.BACKGROUND].fill(Cell(char="."))
        stack[Layer.ENTITIES].put(2, 1, Cell(char="@"))
        stack[Layer.UI].put_text(0, 0, "HP:10", fg="red")

        stack.clear()

        for layer in Layer:
            for y in range(3):
                for x in range(5):
                    cell = stack[layer].get(x, y)
                    assert cell is not None
                    assert cell.char == _DEFAULT_CHAR
                    assert cell.fg is None

    def test_clear_layer_resets_one_layer(self) -> None:
        stack = LayerStack(5, 3)
        stack[Layer.BACKGROUND].fill(Cell(char="."))
        stack[Layer.ENTITIES].put(2, 1, Cell(char="@"))

        stack.clear_layer(Layer.ENTITIES)

        # ENTITIES should be cleared.
        cell = stack[Layer.ENTITIES].get(2, 1)
        assert cell is not None
        assert cell.char == _DEFAULT_CHAR

        # BACKGROUND should be untouched.
        cell = stack[Layer.BACKGROUND].get(0, 0)
        assert cell is not None
        assert cell.char == "."

    def test_clear_layer_invalid_key_raises(self) -> None:
        stack = LayerStack(5, 5)
        with pytest.raises(KeyError):
            stack.clear_layer(99)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# LayerStack.flatten — basic compositing
# ---------------------------------------------------------------------------


class TestLayerStackFlatten:
    """flatten() composites layers bottom-to-top."""

    def test_empty_layers_produce_blank_buffer(self) -> None:
        stack = LayerStack(5, 3)
        result = stack.flatten()
        assert isinstance(result, CellBuffer)
        assert result.width == 5
        assert result.height == 3
        for y in range(3):
            for x in range(5):
                cell = result.get(x, y)
                assert cell is not None
                assert cell.char == _DEFAULT_CHAR

    def test_background_only(self) -> None:
        stack = LayerStack(5, 1)
        stack[Layer.BACKGROUND].fill(Cell(char="."))

        result = stack.flatten()
        for x in range(5):
            cell = result.get(x, 0)
            assert cell is not None
            assert cell.char == "."

    def test_entity_over_background(self) -> None:
        """Entity cell overwrites background at the same position."""
        stack = LayerStack(5, 1)
        stack[Layer.BACKGROUND].fill(Cell(char="."))
        stack[Layer.ENTITIES].put(2, 0, Cell(char="@", fg="green"))

        result = stack.flatten()

        # Position 2 should be the entity.
        cell = result.get(2, 0)
        assert cell is not None
        assert cell.char == "@"
        assert cell.fg == "green"

        # Adjacent positions should show background.
        cell = result.get(1, 0)
        assert cell is not None
        assert cell.char == "."

    def test_ui_over_entity_over_background(self) -> None:
        """UI overwrites entity which overwrites background."""
        stack = LayerStack(5, 1)
        stack[Layer.BACKGROUND].fill(Cell(char="."))
        stack[Layer.ENTITIES].put(2, 0, Cell(char="@", fg="green"))
        stack[Layer.UI].put(2, 0, Cell(char="#", fg="white"))

        result = stack.flatten()

        # Position 2 should be the UI cell (highest layer).
        cell = result.get(2, 0)
        assert cell is not None
        assert cell.char == "#"
        assert cell.fg == "white"

    def test_transparent_ui_shows_entity(self) -> None:
        """Transparent (default) cells on UI layer let entities show."""
        stack = LayerStack(5, 1)
        stack[Layer.ENTITIES].put(2, 0, Cell(char="@"))

        result = stack.flatten()

        cell = result.get(2, 0)
        assert cell is not None
        assert cell.char == "@"

    def test_transparent_entity_shows_background(self) -> None:
        """Transparent entity cells let background show through."""
        stack = LayerStack(5, 1)
        stack[Layer.BACKGROUND].fill(Cell(char="~", fg="blue"))

        result = stack.flatten()

        cell = result.get(0, 0)
        assert cell is not None
        assert cell.char == "~"
        assert cell.fg == "blue"

    def test_flatten_returns_new_buffer(self) -> None:
        """flatten() should return a new CellBuffer each call."""
        stack = LayerStack(5, 3)
        a = stack.flatten()
        b = stack.flatten()
        assert a is not b

    def test_flatten_does_not_modify_layers(self) -> None:
        """Source layer buffers should be unchanged after flatten."""
        stack = LayerStack(5, 1)
        stack[Layer.BACKGROUND].fill(Cell(char="."))
        stack[Layer.ENTITIES].put(2, 0, Cell(char="@"))

        stack.flatten()

        # Background should still have dots everywhere.
        for x in range(5):
            cell = stack[Layer.BACKGROUND].get(x, 0)
            assert cell is not None
            assert cell.char == "."

        # Entity at (2,0) should still be there.
        cell = stack[Layer.ENTITIES].get(2, 0)
        assert cell is not None
        assert cell.char == "@"


# ---------------------------------------------------------------------------
# LayerStack.flatten — edge cases
# ---------------------------------------------------------------------------


class TestLayerStackFlattenEdgeCases:
    """Edge cases for layer compositing."""

    def test_all_layers_opaque_at_same_position(self) -> None:
        """Topmost (UI) layer wins when all layers have opaque cells."""
        stack = LayerStack(1, 1)
        stack[Layer.BACKGROUND].put(0, 0, Cell(char="B"))
        stack[Layer.ENTITIES].put(0, 0, Cell(char="E"))
        stack[Layer.UI].put(0, 0, Cell(char="U"))

        result = stack.flatten()
        cell = result.get(0, 0)
        assert cell is not None
        assert cell.char == "U"

    def test_only_ui_layer_has_content(self) -> None:
        """UI content shows even when lower layers are empty."""
        stack = LayerStack(5, 1)
        stack[Layer.UI].put_text(0, 0, "MENU", fg="yellow")

        result = stack.flatten()
        cell = result.get(0, 0)
        assert cell is not None
        assert cell.char == "M"
        assert cell.fg == "yellow"

    def test_styled_space_is_opaque(self) -> None:
        """A space with bg colour is opaque and overwrites lower layers."""
        stack = LayerStack(3, 1)
        stack[Layer.BACKGROUND].fill(Cell(char=".", fg="grey"))
        # Entity layer has a styled space (e.g., a highlight).
        stack[Layer.ENTITIES].put(1, 0, Cell(char=" ", bg="red"))

        result = stack.flatten()

        cell = result.get(1, 0)
        assert cell is not None
        # The styled space overwrites the background dot.
        assert cell.char == " "
        assert cell.bg == "red"

    def test_1x1_buffer(self) -> None:
        """Minimum size buffer works correctly."""
        stack = LayerStack(1, 1)
        stack[Layer.BACKGROUND].put(0, 0, Cell(char="#"))

        result = stack.flatten()
        cell = result.get(0, 0)
        assert cell is not None
        assert cell.char == "#"

    def test_large_buffer_dimensions(self) -> None:
        """Larger buffer dimensions work without errors."""
        stack = LayerStack(100, 50)
        stack[Layer.BACKGROUND].fill(Cell(char="."))
        stack[Layer.ENTITIES].put(50, 25, Cell(char="@"))

        result = stack.flatten()
        cell = result.get(50, 25)
        assert cell is not None
        assert cell.char == "@"

        cell = result.get(0, 0)
        assert cell is not None
        assert cell.char == "."


# ---------------------------------------------------------------------------
# LayerStack.flatten — style preservation
# ---------------------------------------------------------------------------


class TestLayerStackFlattenStyles:
    """Compositing preserves cell style attributes."""

    def test_preserves_fg_colour(self) -> None:
        stack = LayerStack(3, 1)
        stack[Layer.ENTITIES].put(1, 0, Cell(char="@", fg="green"))

        result = stack.flatten()
        cell = result.get(1, 0)
        assert cell is not None
        assert cell.fg == "green"

    def test_preserves_bg_colour(self) -> None:
        stack = LayerStack(3, 1)
        stack[Layer.BACKGROUND].put(0, 0, Cell(char=".", bg="#333333"))

        result = stack.flatten()
        cell = result.get(0, 0)
        assert cell is not None
        assert cell.bg == "#333333"

    def test_preserves_bold(self) -> None:
        stack = LayerStack(3, 1)
        stack[Layer.UI].put(0, 0, Cell(char="!", bold=True))

        result = stack.flatten()
        cell = result.get(0, 0)
        assert cell is not None
        assert cell.bold is True

    def test_preserves_dim(self) -> None:
        stack = LayerStack(3, 1)
        stack[Layer.BACKGROUND].put(0, 0, Cell(char=".", dim=True))

        result = stack.flatten()
        cell = result.get(0, 0)
        assert cell is not None
        assert cell.dim is True


# ---------------------------------------------------------------------------
# LayerStack — full frame integration
# ---------------------------------------------------------------------------


class TestLayerStackFullFrame:
    """Simulate a typical game frame using the layer stack."""

    def test_roguelike_frame(self) -> None:
        """Simulate a small roguelike room with all three layers."""
        stack = LayerStack(10, 5)

        # Background: floor tiles.
        stack[Layer.BACKGROUND].fill(Cell(char=".", fg="grey"))
        # Walls on top and bottom rows.
        for x in range(10):
            stack[Layer.BACKGROUND].put(x, 0, Cell(char="#", fg="white"))
            stack[Layer.BACKGROUND].put(x, 4, Cell(char="#", fg="white"))
        for y in range(1, 4):
            stack[Layer.BACKGROUND].put(0, y, Cell(char="#", fg="white"))
            stack[Layer.BACKGROUND].put(9, y, Cell(char="#", fg="white"))

        # Entities: player and an enemy.
        stack[Layer.ENTITIES].put(3, 2, Cell(char="@", fg="green", bold=True))
        stack[Layer.ENTITIES].put(7, 2, Cell(char="g", fg="red"))

        # UI: health bar in top-left corner (over the wall).
        stack[Layer.UI].put_text(0, 0, "HP:10", fg="yellow", bold=True)

        result = stack.flatten()

        # Player should be visible.
        player = result.get(3, 2)
        assert player is not None
        assert player.char == "@"
        assert player.fg == "green"
        assert player.bold is True

        # Enemy should be visible.
        enemy = result.get(7, 2)
        assert enemy is not None
        assert enemy.char == "g"
        assert enemy.fg == "red"

        # UI overwrites the wall at (0,0).
        ui = result.get(0, 0)
        assert ui is not None
        assert ui.char == "H"
        assert ui.fg == "yellow"
        assert ui.bold is True

        # Floor tile at (5, 2) — no entity or UI there.
        floor = result.get(5, 2)
        assert floor is not None
        assert floor.char == "."
        assert floor.fg == "grey"

        # Wall at (9, 0) — no UI there.
        wall = result.get(9, 0)
        assert wall is not None
        assert wall.char == "#"
        assert wall.fg == "white"


# ---------------------------------------------------------------------------
# LayerStack.__repr__
# ---------------------------------------------------------------------------


class TestLayerStackRepr:
    """repr should be informative."""

    def test_repr_contains_dimensions(self) -> None:
        stack = LayerStack(80, 24)
        r = repr(stack)
        assert "80" in r
        assert "24" in r

    def test_repr_contains_layer_names(self) -> None:
        stack = LayerStack(10, 5)
        r = repr(stack)
        assert "BACKGROUND" in r
        assert "ENTITIES" in r
        assert "UI" in r
