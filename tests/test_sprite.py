"""Tests for wyby.sprite — Sprite component for entity visual appearance."""

from __future__ import annotations

import pytest
from rich.style import Style

from wyby.component import Component
from wyby.entity import Entity
from wyby.sprite import Sprite


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestSpriteConstruction:
    """Sprite creation and default state."""

    def test_default_char_is_at_sign(self) -> None:
        s = Sprite()
        assert s.char == "@"

    def test_default_style_is_null(self) -> None:
        s = Sprite()
        assert s.style == Style.null()

    def test_custom_char(self) -> None:
        s = Sprite("#")
        assert s.char == "#"

    def test_custom_style(self) -> None:
        style = Style(color="red", bold=True)
        s = Sprite("X", style)
        assert s.style.color.name == "red"
        assert s.style.bold is True

    def test_wide_char_accepted(self) -> None:
        """CJK characters are valid sprite chars (they occupy 2 cells)."""
        s = Sprite("\u4e16")  # 世
        assert s.char == "\u4e16"

    def test_box_drawing_char(self) -> None:
        s = Sprite("\u2588")  # █ full block
        assert s.char == "\u2588"

    def test_is_component_subclass(self) -> None:
        s = Sprite()
        assert isinstance(s, Component)

    def test_detached_by_default(self) -> None:
        s = Sprite()
        assert s.entity is None


# ---------------------------------------------------------------------------
# Validation — char
# ---------------------------------------------------------------------------


class TestSpriteCharValidation:
    """Char parameter validation on construction."""

    def test_rejects_non_string(self) -> None:
        with pytest.raises(TypeError, match="char must be a string"):
            Sprite(42)  # type: ignore[arg-type]

    def test_rejects_empty_string(self) -> None:
        with pytest.raises(ValueError, match="exactly one character"):
            Sprite("")

    def test_rejects_multi_char_string(self) -> None:
        with pytest.raises(ValueError, match="exactly one character"):
            Sprite("AB")

    def test_rejects_none_char(self) -> None:
        with pytest.raises(TypeError, match="char must be a string"):
            Sprite(None)  # type: ignore[arg-type]

    def test_rejects_zero_width_char(self) -> None:
        """Combining marks have zero display width and can't fill a cell."""
        with pytest.raises(ValueError, match="non-zero display width"):
            Sprite("\u0300")  # combining grave accent


# ---------------------------------------------------------------------------
# Validation — style
# ---------------------------------------------------------------------------


class TestSpriteStyleValidation:
    """Style parameter validation on construction."""

    def test_rejects_non_style(self) -> None:
        with pytest.raises(TypeError, match="rich.style.Style instance"):
            Sprite("@", "red")  # type: ignore[arg-type]

    def test_rejects_dict_as_style(self) -> None:
        with pytest.raises(TypeError, match="rich.style.Style instance"):
            Sprite("@", {"color": "red"})  # type: ignore[arg-type]

    def test_none_style_gives_null(self) -> None:
        """Passing None explicitly produces Style.null()."""
        s = Sprite("@", None)
        assert s.style == Style.null()


# ---------------------------------------------------------------------------
# Char property (getter/setter)
# ---------------------------------------------------------------------------


class TestSpriteCharProperty:
    """The char property with getter and setter."""

    def test_get_char(self) -> None:
        s = Sprite("X")
        assert s.char == "X"

    def test_set_char(self) -> None:
        s = Sprite("X")
        s.char = "#"
        assert s.char == "#"

    def test_set_rejects_non_string(self) -> None:
        s = Sprite()
        with pytest.raises(TypeError, match="char must be a string"):
            s.char = 5  # type: ignore[assignment]

    def test_set_rejects_empty(self) -> None:
        s = Sprite()
        with pytest.raises(ValueError, match="exactly one character"):
            s.char = ""

    def test_set_rejects_multi_char(self) -> None:
        s = Sprite()
        with pytest.raises(ValueError, match="exactly one character"):
            s.char = "AB"

    def test_set_rejects_zero_width(self) -> None:
        s = Sprite()
        with pytest.raises(ValueError, match="non-zero display width"):
            s.char = "\u0300"

    def test_set_accepts_wide_char(self) -> None:
        s = Sprite()
        s.char = "\u4e16"  # 世
        assert s.char == "\u4e16"


# ---------------------------------------------------------------------------
# Style property (getter/setter)
# ---------------------------------------------------------------------------


class TestSpriteStyleProperty:
    """The style property with getter and setter."""

    def test_get_style(self) -> None:
        style = Style(color="blue")
        s = Sprite("@", style)
        assert s.style is style

    def test_set_style(self) -> None:
        s = Sprite()
        new_style = Style(color="green", dim=True)
        s.style = new_style
        assert s.style is new_style

    def test_set_rejects_non_style(self) -> None:
        s = Sprite()
        with pytest.raises(TypeError, match="rich.style.Style instance"):
            s.style = "red"  # type: ignore[assignment]

    def test_set_rejects_none(self) -> None:
        s = Sprite()
        with pytest.raises(TypeError, match="rich.style.Style instance"):
            s.style = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Entity integration
# ---------------------------------------------------------------------------


class TestSpriteEntityIntegration:
    """Sprite as a component attached to entities."""

    def test_attach_to_entity(self) -> None:
        e = Entity(entity_id=42)
        s = Sprite("@", Style(color="red"))
        e.add_component(s)
        assert s.entity is e

    def test_get_component_from_entity(self) -> None:
        e = Entity(entity_id=42)
        s = Sprite("#")
        e.add_component(s)
        assert e.get_component(Sprite) is s

    def test_has_component(self) -> None:
        e = Entity(entity_id=42)
        assert not e.has_component(Sprite)
        e.add_component(Sprite())
        assert e.has_component(Sprite)

    def test_remove_component(self) -> None:
        e = Entity(entity_id=42)
        s = Sprite()
        e.add_component(s)
        removed = e.remove_component(Sprite)
        assert removed is s
        assert s.entity is None

    def test_one_sprite_per_entity(self) -> None:
        """Only one Sprite component per entity (one-per-type rule)."""
        e = Entity(entity_id=42)
        e.add_component(Sprite("@"))
        with pytest.raises(ValueError, match="already has a"):
            e.add_component(Sprite("#"))

    def test_reattach_after_detach(self) -> None:
        e1 = Entity(entity_id=1)
        e2 = Entity(entity_id=2)
        s = Sprite()
        e1.add_component(s)
        e1.remove_component(Sprite)
        e2.add_component(s)
        assert s.entity is e2


# ---------------------------------------------------------------------------
# Repr
# ---------------------------------------------------------------------------


class TestSpriteRepr:
    """__repr__ output."""

    def test_repr_when_detached(self) -> None:
        s = Sprite("#")
        assert repr(s) == "Sprite(char='#', detached)"

    def test_repr_when_attached(self) -> None:
        e = Entity(entity_id=99)
        s = Sprite("X")
        e.add_component(s)
        assert repr(s) == "Sprite(char='X', entity_id=99)"

    def test_repr_default(self) -> None:
        s = Sprite()
        assert repr(s) == "Sprite(char='@', detached)"


# ---------------------------------------------------------------------------
# Slots
# ---------------------------------------------------------------------------


class TestSpriteSlots:
    """Sprite uses __slots__ for memory efficiency."""

    def test_uses_slots(self) -> None:
        assert "__slots__" in Sprite.__dict__
        assert "_char" in Sprite.__slots__
        assert "_style" in Sprite.__slots__


# ---------------------------------------------------------------------------
# Import from package root
# ---------------------------------------------------------------------------


class TestSpriteImport:
    """Sprite is accessible from the wyby package root."""

    def test_import_from_wyby(self) -> None:
        from wyby import Sprite as S
        assert S is Sprite
