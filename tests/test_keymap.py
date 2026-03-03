"""Tests for wyby.keymap — key mapping configuration."""

from __future__ import annotations

import json

import pytest

from wyby.input import KeyEvent
from wyby.keymap import KeyBinding, KeyMap, _parse_key_spec


# ── _parse_key_spec ──────────────────────────────────────────────────


class TestParseKeySpec:
    """Tests for the _parse_key_spec helper."""

    def test_plain_string(self) -> None:
        assert _parse_key_spec("w") == ("w", False)

    def test_tuple_with_ctrl(self) -> None:
        assert _parse_key_spec(("s", True)) == ("s", True)

    def test_tuple_without_ctrl(self) -> None:
        assert _parse_key_spec(("a", False)) == ("a", False)

    def test_list_form_from_json(self) -> None:
        """Lists are accepted for JSON round-trip compatibility."""
        assert _parse_key_spec(["s", True]) == ("s", True)

    def test_empty_string_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            _parse_key_spec("")

    def test_empty_key_in_tuple_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            _parse_key_spec(("", True))

    def test_invalid_type_raises(self) -> None:
        with pytest.raises(TypeError, match="key spec"):
            _parse_key_spec(42)  # type: ignore[arg-type]

    def test_wrong_length_tuple_raises(self) -> None:
        with pytest.raises(TypeError, match="key spec"):
            _parse_key_spec(("a", True, "extra"))  # type: ignore[arg-type]


# ── KeyBinding ───────────────────────────────────────────────────────


class TestKeyBinding:
    """Tests for the KeyBinding dataclass."""

    def test_matches_plain_key(self) -> None:
        binding = KeyBinding(key="w", ctrl=False, action="move_up")
        assert binding.matches(KeyEvent(key="w"))
        assert not binding.matches(KeyEvent(key="s"))

    def test_matches_ctrl_key(self) -> None:
        binding = KeyBinding(key="s", ctrl=True, action="save")
        assert binding.matches(KeyEvent(key="s", ctrl=True))
        assert not binding.matches(KeyEvent(key="s", ctrl=False))

    def test_ctrl_binding_does_not_match_plain_press(self) -> None:
        binding = KeyBinding(key="s", ctrl=True, action="save")
        assert not binding.matches(KeyEvent(key="s"))

    def test_to_spec_plain(self) -> None:
        binding = KeyBinding(key="w", ctrl=False, action="move_up")
        assert binding.to_spec() == "w"

    def test_to_spec_ctrl(self) -> None:
        binding = KeyBinding(key="s", ctrl=True, action="save")
        assert binding.to_spec() == ("s", True)

    def test_frozen(self) -> None:
        binding = KeyBinding(key="w", ctrl=False, action="move_up")
        with pytest.raises(AttributeError):
            binding.key = "x"  # type: ignore[misc]

    def test_equality(self) -> None:
        a = KeyBinding(key="w", ctrl=False, action="move_up")
        b = KeyBinding(key="w", ctrl=False, action="move_up")
        assert a == b

    def test_inequality(self) -> None:
        a = KeyBinding(key="w", ctrl=False, action="move_up")
        b = KeyBinding(key="w", ctrl=True, action="move_up")
        assert a != b


# ── KeyMap construction ──────────────────────────────────────────────


class TestKeyMapConstruction:
    """Tests for KeyMap creation and validation."""

    def test_empty_keymap(self) -> None:
        km = KeyMap()
        assert len(km) == 0

    def test_from_dict_arg(self) -> None:
        km = KeyMap({"move_up": ["w", "up"]})
        assert len(km) == 2
        assert "move_up" in km

    def test_ctrl_spec_in_constructor(self) -> None:
        km = KeyMap({"save": [("s", True)]})
        assert len(km) == 1
        event = KeyEvent(key="s", ctrl=True)
        assert km.lookup(event) == "save"

    def test_invalid_bindings_type(self) -> None:
        with pytest.raises(TypeError, match="dict"):
            KeyMap("not a dict")  # type: ignore[arg-type]

    def test_invalid_action_type(self) -> None:
        with pytest.raises(TypeError, match="string"):
            KeyMap({42: ["w"]})  # type: ignore[dict-item]

    def test_invalid_specs_type(self) -> None:
        with pytest.raises(TypeError, match="list"):
            KeyMap({"move": "w"})  # type: ignore[dict-item]

    def test_empty_key_in_constructor_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            KeyMap({"move": [""]})


# ── KeyMap.lookup ────────────────────────────────────────────────────


class TestKeyMapLookup:
    """Tests for KeyMap.lookup and lookup_all."""

    def test_lookup_returns_action(self) -> None:
        km = KeyMap({"move_up": ["w", "up"]})
        assert km.lookup(KeyEvent(key="w")) == "move_up"
        assert km.lookup(KeyEvent(key="up")) == "move_up"

    def test_lookup_returns_none_for_unbound_key(self) -> None:
        km = KeyMap({"move_up": ["w"]})
        assert km.lookup(KeyEvent(key="x")) is None

    def test_lookup_respects_ctrl(self) -> None:
        km = KeyMap({"save": [("s", True)], "move_down": ["s"]})
        assert km.lookup(KeyEvent(key="s", ctrl=True)) == "save"
        assert km.lookup(KeyEvent(key="s")) == "move_down"

    def test_lookup_first_binding_wins(self) -> None:
        """When same key is bound to multiple actions, first wins."""
        km = KeyMap()
        km.bind("action_a", "x")
        km.bind("action_b", "x")
        assert km.lookup(KeyEvent(key="x")) == "action_a"

    def test_lookup_all_returns_all_matches(self) -> None:
        km = KeyMap()
        km.bind("action_a", "x")
        km.bind("action_b", "x")
        assert km.lookup_all(KeyEvent(key="x")) == ["action_a", "action_b"]

    def test_lookup_all_empty_for_unbound(self) -> None:
        km = KeyMap({"move": ["w"]})
        assert km.lookup_all(KeyEvent(key="z")) == []

    def test_lookup_special_keys(self) -> None:
        km = KeyMap({
            "confirm": ["enter"],
            "cancel": ["escape"],
            "jump": ["space"],
        })
        assert km.lookup(KeyEvent(key="enter")) == "confirm"
        assert km.lookup(KeyEvent(key="escape")) == "cancel"
        assert km.lookup(KeyEvent(key="space")) == "jump"

    def test_lookup_arrow_keys(self) -> None:
        km = KeyMap({
            "up": ["up"],
            "down": ["down"],
            "left": ["left"],
            "right": ["right"],
        })
        assert km.lookup(KeyEvent(key="up")) == "up"
        assert km.lookup(KeyEvent(key="down")) == "down"

    def test_lookup_uppercase_is_case_sensitive(self) -> None:
        """Uppercase 'A' and lowercase 'a' are distinct keys."""
        km = KeyMap({"sprint": ["A"], "walk": ["a"]})
        assert km.lookup(KeyEvent(key="A")) == "sprint"
        assert km.lookup(KeyEvent(key="a")) == "walk"


# ── KeyMap.bind / unbind ─────────────────────────────────────────────


class TestKeyMapBindUnbind:
    """Tests for runtime binding and unbinding."""

    def test_bind_adds_binding(self) -> None:
        km = KeyMap()
        km.bind("jump", "space")
        assert km.lookup(KeyEvent(key="space")) == "jump"

    def test_bind_with_ctrl(self) -> None:
        km = KeyMap()
        km.bind("save", "s", ctrl=True)
        assert km.lookup(KeyEvent(key="s", ctrl=True)) == "save"
        assert km.lookup(KeyEvent(key="s")) is None

    def test_bind_duplicate_is_noop(self) -> None:
        km = KeyMap()
        km.bind("jump", "space")
        km.bind("jump", "space")
        assert len(km) == 1

    def test_bind_empty_key_raises(self) -> None:
        km = KeyMap()
        with pytest.raises(ValueError, match="key.*empty"):
            km.bind("jump", "")

    def test_bind_empty_action_raises(self) -> None:
        km = KeyMap()
        with pytest.raises(ValueError, match="action.*empty"):
            km.bind("", "space")

    def test_unbind_removes_binding(self) -> None:
        km = KeyMap({"jump": ["space"]})
        assert km.unbind("jump", "space") is True
        assert km.lookup(KeyEvent(key="space")) is None

    def test_unbind_nonexistent_returns_false(self) -> None:
        km = KeyMap()
        assert km.unbind("jump", "space") is False

    def test_unbind_action_removes_all(self) -> None:
        km = KeyMap({"move_up": ["w", "up"]})
        removed = km.unbind_action("move_up")
        assert removed == 2
        assert len(km) == 0

    def test_unbind_action_nonexistent(self) -> None:
        km = KeyMap({"move": ["w"]})
        assert km.unbind_action("nonexistent") == 0

    def test_unbind_key_removes_all_actions(self) -> None:
        km = KeyMap()
        km.bind("action_a", "x")
        km.bind("action_b", "x")
        removed = km.unbind_key("x")
        assert removed == 2
        assert km.lookup(KeyEvent(key="x")) is None

    def test_unbind_key_with_ctrl(self) -> None:
        km = KeyMap()
        km.bind("save", "s", ctrl=True)
        km.bind("move_down", "s")
        # Only remove the Ctrl+S binding.
        removed = km.unbind_key("s", ctrl=True)
        assert removed == 1
        # Plain 's' should still work.
        assert km.lookup(KeyEvent(key="s")) == "move_down"


# ── KeyMap.keys_for_action / actions ─────────────────────────────────


class TestKeyMapQueries:
    """Tests for querying bindings."""

    def test_keys_for_action(self) -> None:
        km = KeyMap({"move_up": ["w", "up"]})
        keys = km.keys_for_action("move_up")
        assert len(keys) == 2
        assert keys[0].key == "w"
        assert keys[1].key == "up"

    def test_keys_for_unknown_action(self) -> None:
        km = KeyMap({"move": ["w"]})
        assert km.keys_for_action("nonexistent") == []

    def test_actions_preserves_order(self) -> None:
        km = KeyMap({
            "move_up": ["w"],
            "move_down": ["s"],
            "quit": ["q"],
        })
        assert km.actions() == ["move_up", "move_down", "quit"]

    def test_actions_deduplicates(self) -> None:
        """Each action appears once even if bound to multiple keys."""
        km = KeyMap({"move_up": ["w", "up"]})
        assert km.actions() == ["move_up"]

    def test_contains(self) -> None:
        km = KeyMap({"jump": ["space"]})
        assert "jump" in km
        assert "fly" not in km


# ── KeyMap serialisation ─────────────────────────────────────────────


class TestKeyMapSerialisation:
    """Tests for to_dict / from_dict round-tripping."""

    def test_round_trip(self) -> None:
        original = KeyMap({
            "move_up": ["w", "up"],
            "save": [("s", True)],
            "quit": ["q", "escape"],
        })
        data = original.to_dict()
        restored = KeyMap.from_dict(data)
        assert restored.to_dict() == data

    def test_json_round_trip(self) -> None:
        """Serialise through JSON and back."""
        original = KeyMap({
            "move_up": ["w"],
            "save": [("s", True)],
        })
        json_str = json.dumps(original.to_dict())
        data = json.loads(json_str)
        restored = KeyMap.from_dict(data)

        assert restored.lookup(KeyEvent(key="w")) == "move_up"
        assert restored.lookup(KeyEvent(key="s", ctrl=True)) == "save"

    def test_to_dict_ctrl_uses_list(self) -> None:
        """Ctrl specs are serialised as [key, true] for JSON compat."""
        km = KeyMap({"save": [("s", True)]})
        data = km.to_dict()
        assert data["save"] == [["s", True]]

    def test_from_dict_invalid_type(self) -> None:
        with pytest.raises(TypeError, match="dict"):
            KeyMap.from_dict("not a dict")  # type: ignore[arg-type]

    def test_from_dict_invalid_specs_type(self) -> None:
        with pytest.raises(TypeError, match="list"):
            KeyMap.from_dict({"move": "w"})  # type: ignore[dict-item]

    def test_from_dict_invalid_spec_entry(self) -> None:
        with pytest.raises(TypeError, match="invalid key spec"):
            KeyMap.from_dict({"move": [42]})  # type: ignore[list-item]

    def test_empty_round_trip(self) -> None:
        km = KeyMap()
        assert KeyMap.from_dict(km.to_dict()).to_dict() == {}


# ── KeyMap __repr__ / __len__ ────────────────────────────────────────


class TestKeyMapRepr:
    """Tests for repr and len."""

    def test_len(self) -> None:
        km = KeyMap({"a": ["w", "up"], "b": ["s"]})
        assert len(km) == 3

    def test_repr_few_actions(self) -> None:
        km = KeyMap({"move": ["w"], "quit": ["q"]})
        r = repr(km)
        assert "KeyMap" in r
        assert "move" in r
        assert "quit" in r

    def test_repr_many_actions(self) -> None:
        km = KeyMap({
            "a": ["1"],
            "b": ["2"],
            "c": ["3"],
            "d": ["4"],
        })
        r = repr(km)
        assert "4 total" in r


# ── Integration: KeyMap with parse_input_events ──────────────────────


class TestKeyMapIntegration:
    """Integration tests: KeyMap with parsed KeyEvents."""

    def test_arrow_keys_from_parsed_input(self) -> None:
        """Verify KeyMap works with keys produced by the input parser."""
        from wyby.input import parse_input_events

        km = KeyMap({
            "move_up": ["up"],
            "move_down": ["down"],
        })

        # Simulate \x1b[A (up arrow).
        events = parse_input_events(b"\x1b[A")
        assert len(events) == 1
        assert km.lookup(events[0]) == "move_up"  # type: ignore[arg-type]

    def test_ctrl_key_from_parsed_input(self) -> None:
        from wyby.input import parse_input_events

        km = KeyMap({"save": [("s", True)]})

        # Ctrl+S = byte 0x13.
        events = parse_input_events(b"\x13")
        assert len(events) == 1
        assert km.lookup(events[0]) == "save"  # type: ignore[arg-type]

    def test_printable_char_from_parsed_input(self) -> None:
        from wyby.input import parse_input_events

        km = KeyMap({"quit": ["q"]})
        events = parse_input_events(b"q")
        assert len(events) == 1
        assert km.lookup(events[0]) == "quit"  # type: ignore[arg-type]


# ── Edge cases ───────────────────────────────────────────────────────


class TestKeyMapEdgeCases:
    """Edge cases and caveat coverage."""

    def test_rebind_key_to_different_action(self) -> None:
        """Unbind then bind to a new action."""
        km = KeyMap({"move_up": ["w"]})
        km.unbind("move_up", "w")
        km.bind("jump", "w")
        assert km.lookup(KeyEvent(key="w")) == "jump"

    def test_multiple_actions_same_key(self) -> None:
        """Multiple actions on same key — lookup returns first."""
        km = KeyMap()
        km.bind("primary", "space")
        km.bind("secondary", "space")
        assert km.lookup(KeyEvent(key="space")) == "primary"
        assert km.lookup_all(KeyEvent(key="space")) == ["primary", "secondary"]

    def test_case_sensitive_actions(self) -> None:
        """Action names are case-sensitive."""
        km = KeyMap({"Quit": ["Q"], "quit": ["q"]})
        assert km.lookup(KeyEvent(key="Q")) == "Quit"
        assert km.lookup(KeyEvent(key="q")) == "quit"

    def test_special_key_names(self) -> None:
        """Verify binding to all special key names."""
        special_keys = [
            "enter", "escape", "tab", "backspace", "space",
            "home", "end", "insert", "delete", "pageup", "pagedown",
            "up", "down", "left", "right",
        ]
        bindings = {f"action_{k}": [k] for k in special_keys}
        km = KeyMap(bindings)
        for k in special_keys:
            assert km.lookup(KeyEvent(key=k)) == f"action_{k}"

    def test_unicode_key(self) -> None:
        """Unicode characters can be bound as keys."""
        km = KeyMap({"special": ["é"]})
        assert km.lookup(KeyEvent(key="é")) == "special"
