"""Tests for wyby.input_context — input context focus management."""

from __future__ import annotations

import pytest

from wyby.input import KeyEvent
from wyby.input_context import InputContext, InputContextStack
from wyby.keymap import KeyMap


# ── InputContext ─────────────────────────────────────────────────────


class TestInputContextInit:
    """Tests for InputContext construction."""

    def test_basic_creation(self) -> None:
        km = KeyMap({"move": ["w"]})
        ctx = InputContext("gameplay", km)
        assert ctx.name == "gameplay"
        assert ctx.keymap is km
        assert ctx.enabled is True
        assert ctx.fallthrough is False

    def test_default_keymap(self) -> None:
        """None keymap creates an empty KeyMap."""
        ctx = InputContext("empty")
        assert len(ctx.keymap) == 0

    def test_enabled_false(self) -> None:
        ctx = InputContext("disabled", enabled=False)
        assert ctx.enabled is False

    def test_fallthrough_true(self) -> None:
        ctx = InputContext("overlay", fallthrough=True)
        assert ctx.fallthrough is True

    def test_empty_name_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            InputContext("")

    def test_non_string_name_raises(self) -> None:
        with pytest.raises(TypeError, match="string"):
            InputContext(42)  # type: ignore[arg-type]

    def test_invalid_keymap_type_raises(self) -> None:
        with pytest.raises(TypeError, match="KeyMap"):
            InputContext("bad", keymap="not a keymap")  # type: ignore[arg-type]


class TestInputContextProperties:
    """Tests for InputContext property access and mutation."""

    def test_enabled_setter(self) -> None:
        ctx = InputContext("test")
        assert ctx.enabled is True
        ctx.enabled = False
        assert ctx.enabled is False
        ctx.enabled = True
        assert ctx.enabled is True

    def test_fallthrough_setter(self) -> None:
        ctx = InputContext("test")
        assert ctx.fallthrough is False
        ctx.fallthrough = True
        assert ctx.fallthrough is True

    def test_enabled_setter_coerces_to_bool(self) -> None:
        ctx = InputContext("test")
        ctx.enabled = 0  # type: ignore[assignment]
        assert ctx.enabled is False
        ctx.enabled = 1  # type: ignore[assignment]
        assert ctx.enabled is True

    def test_repr_basic(self) -> None:
        ctx = InputContext("gameplay", KeyMap({"move": ["w"]}))
        r = repr(ctx)
        assert "gameplay" in r
        assert "InputContext" in r

    def test_repr_disabled(self) -> None:
        ctx = InputContext("test", enabled=False)
        assert "enabled=False" in repr(ctx)

    def test_repr_fallthrough(self) -> None:
        ctx = InputContext("test", fallthrough=True)
        assert "fallthrough=True" in repr(ctx)


class TestInputContextLookup:
    """Tests for InputContext.lookup."""

    def test_lookup_match(self) -> None:
        ctx = InputContext("game", KeyMap({"jump": ["space"]}))
        assert ctx.lookup(KeyEvent(key="space")) == "jump"

    def test_lookup_no_match(self) -> None:
        ctx = InputContext("game", KeyMap({"jump": ["space"]}))
        assert ctx.lookup(KeyEvent(key="w")) is None

    def test_lookup_empty_keymap(self) -> None:
        ctx = InputContext("empty")
        assert ctx.lookup(KeyEvent(key="a")) is None


# ── InputContextStack ────────────────────────────────────────────────


class TestInputContextStackInit:
    """Tests for InputContextStack construction."""

    def test_default_creation(self) -> None:
        stack = InputContextStack()
        assert stack.max_depth == 32
        assert stack.is_empty
        assert len(stack) == 0

    def test_custom_max_depth(self) -> None:
        stack = InputContextStack(max_depth=5)
        assert stack.max_depth == 5

    def test_max_depth_too_low_raises(self) -> None:
        with pytest.raises(ValueError, match="between"):
            InputContextStack(max_depth=0)

    def test_max_depth_too_high_raises(self) -> None:
        with pytest.raises(ValueError, match="between"):
            InputContextStack(max_depth=257)

    def test_max_depth_not_int_raises(self) -> None:
        with pytest.raises(TypeError, match="int"):
            InputContextStack(max_depth="10")  # type: ignore[arg-type]

    def test_max_depth_bool_raises(self) -> None:
        with pytest.raises(TypeError, match="int"):
            InputContextStack(max_depth=True)  # type: ignore[arg-type]


class TestInputContextStackPush:
    """Tests for push/pop/replace/clear operations."""

    def test_push_and_peek(self) -> None:
        stack = InputContextStack()
        ctx = InputContext("game")
        stack.push(ctx)
        assert stack.peek() is ctx
        assert len(stack) == 1
        assert not stack.is_empty

    def test_push_non_context_raises(self) -> None:
        stack = InputContextStack()
        with pytest.raises(TypeError, match="InputContext"):
            stack.push("not a context")  # type: ignore[arg-type]

    def test_push_beyond_max_depth_raises(self) -> None:
        stack = InputContextStack(max_depth=2)
        stack.push(InputContext("a"))
        stack.push(InputContext("b"))
        with pytest.raises(RuntimeError, match="depth limit"):
            stack.push(InputContext("c"))

    def test_pop_returns_top(self) -> None:
        stack = InputContextStack()
        ctx = InputContext("game")
        stack.push(ctx)
        popped = stack.pop()
        assert popped is ctx
        assert stack.is_empty

    def test_pop_empty_raises(self) -> None:
        stack = InputContextStack()
        with pytest.raises(RuntimeError, match="empty"):
            stack.pop()

    def test_push_pop_order(self) -> None:
        """LIFO: last pushed is first popped."""
        stack = InputContextStack()
        a = InputContext("a")
        b = InputContext("b")
        stack.push(a)
        stack.push(b)
        assert stack.pop() is b
        assert stack.pop() is a

    def test_replace(self) -> None:
        stack = InputContextStack()
        old = InputContext("old")
        new = InputContext("new")
        stack.push(old)
        replaced = stack.replace(new)
        assert replaced is old
        assert stack.peek() is new
        assert len(stack) == 1

    def test_replace_empty_raises(self) -> None:
        stack = InputContextStack()
        with pytest.raises(RuntimeError, match="empty"):
            stack.replace(InputContext("new"))

    def test_replace_non_context_raises(self) -> None:
        stack = InputContextStack()
        stack.push(InputContext("old"))
        with pytest.raises(TypeError, match="InputContext"):
            stack.replace("bad")  # type: ignore[arg-type]

    def test_clear(self) -> None:
        stack = InputContextStack()
        stack.push(InputContext("a"))
        stack.push(InputContext("b"))
        stack.clear()
        assert stack.is_empty
        assert len(stack) == 0

    def test_clear_empty_is_noop(self) -> None:
        stack = InputContextStack()
        stack.clear()  # should not raise
        assert stack.is_empty


class TestInputContextStackBool:
    """Tests for __bool__ and __len__."""

    def test_empty_is_falsy(self) -> None:
        assert not InputContextStack()

    def test_non_empty_is_truthy(self) -> None:
        stack = InputContextStack()
        stack.push(InputContext("a"))
        assert stack


class TestInputContextStackLookup:
    """Tests for event lookup through the stack."""

    def test_lookup_top_context(self) -> None:
        stack = InputContextStack()
        stack.push(InputContext("game", KeyMap({"move": ["w"]})))
        assert stack.lookup(KeyEvent(key="w")) == "move"

    def test_lookup_no_match(self) -> None:
        stack = InputContextStack()
        stack.push(InputContext("game", KeyMap({"move": ["w"]})))
        assert stack.lookup(KeyEvent(key="x")) is None

    def test_lookup_empty_stack(self) -> None:
        stack = InputContextStack()
        assert stack.lookup(KeyEvent(key="w")) is None

    def test_top_context_shadows_bottom(self) -> None:
        """Without fallthrough, top context blocks lower ones."""
        stack = InputContextStack()
        stack.push(InputContext("game", KeyMap({"move": ["w"]})))
        stack.push(InputContext("dialog", KeyMap({"confirm": ["enter"]})))
        # "w" is in the bottom context but dialog blocks it.
        assert stack.lookup(KeyEvent(key="w")) is None
        assert stack.lookup(KeyEvent(key="enter")) == "confirm"

    def test_fallthrough_passes_to_lower(self) -> None:
        """With fallthrough, unmatched events reach lower contexts."""
        stack = InputContextStack()
        stack.push(InputContext("game", KeyMap({"move": ["w"]})))
        stack.push(InputContext(
            "hud", KeyMap({"toggle_map": ["m"]}), fallthrough=True
        ))
        # "m" matches in hud.
        assert stack.lookup(KeyEvent(key="m")) == "toggle_map"
        # "w" falls through hud to game.
        assert stack.lookup(KeyEvent(key="w")) == "move"
        # "x" falls through hud, doesn't match game (no fallthrough).
        assert stack.lookup(KeyEvent(key="x")) is None

    def test_fallthrough_chain(self) -> None:
        """Multiple fallthrough contexts stack correctly."""
        stack = InputContextStack()
        stack.push(InputContext("base", KeyMap({"quit": ["q"]})))
        stack.push(InputContext(
            "overlay1", KeyMap({"help": ["h"]}), fallthrough=True
        ))
        stack.push(InputContext(
            "overlay2", KeyMap({"info": ["i"]}), fallthrough=True
        ))
        assert stack.lookup(KeyEvent(key="i")) == "info"
        assert stack.lookup(KeyEvent(key="h")) == "help"
        assert stack.lookup(KeyEvent(key="q")) == "quit"
        assert stack.lookup(KeyEvent(key="x")) is None

    def test_disabled_context_skipped(self) -> None:
        """Disabled contexts are invisible to lookup."""
        stack = InputContextStack()
        stack.push(InputContext("game", KeyMap({"move": ["w"]})))
        dialog = InputContext("dialog", KeyMap({"confirm": ["enter"]}))
        dialog.enabled = False
        stack.push(dialog)
        # Dialog is disabled, so game context handles events.
        assert stack.lookup(KeyEvent(key="w")) == "move"

    def test_disabled_top_with_fallthrough_below(self) -> None:
        """Disabled top + enabled fallthrough below."""
        stack = InputContextStack()
        stack.push(InputContext("base", KeyMap({"quit": ["q"]})))
        stack.push(InputContext(
            "overlay", KeyMap({"help": ["h"]}), fallthrough=True
        ))
        disabled = InputContext("modal", KeyMap({"ok": ["enter"]}))
        disabled.enabled = False
        stack.push(disabled)
        # modal is disabled, overlay is fallthrough, base is not.
        assert stack.lookup(KeyEvent(key="h")) == "help"
        assert stack.lookup(KeyEvent(key="q")) == "quit"

    def test_all_disabled_returns_none(self) -> None:
        stack = InputContextStack()
        ctx = InputContext("a", KeyMap({"x": ["x"]}))
        ctx.enabled = False
        stack.push(ctx)
        assert stack.lookup(KeyEvent(key="x")) is None

    def test_empty_keymap_swallows_input(self) -> None:
        """An empty keymap with fallthrough=False blocks all input."""
        stack = InputContextStack()
        stack.push(InputContext("game", KeyMap({"move": ["w"]})))
        stack.push(InputContext("cutscene"))  # empty, no fallthrough
        assert stack.lookup(KeyEvent(key="w")) is None


class TestInputContextStackLookupAll:
    """Tests for lookup_all through the stack."""

    def test_lookup_all_single_match(self) -> None:
        stack = InputContextStack()
        stack.push(InputContext("game", KeyMap({"move": ["w"]})))
        assert stack.lookup_all(KeyEvent(key="w")) == ["move"]

    def test_lookup_all_no_match(self) -> None:
        stack = InputContextStack()
        stack.push(InputContext("game", KeyMap({"move": ["w"]})))
        assert stack.lookup_all(KeyEvent(key="x")) == []

    def test_lookup_all_with_fallthrough(self) -> None:
        """Collects actions from multiple contexts via fallthrough."""
        stack = InputContextStack()
        # Both contexts bind the same key to different actions.
        stack.push(InputContext("base", KeyMap({"base_action": ["w"]})))
        stack.push(InputContext(
            "overlay", KeyMap({"overlay_action": ["w"]}), fallthrough=True
        ))
        result = stack.lookup_all(KeyEvent(key="w"))
        assert result == ["overlay_action", "base_action"]

    def test_lookup_all_stops_without_fallthrough(self) -> None:
        stack = InputContextStack()
        stack.push(InputContext("base", KeyMap({"base_action": ["w"]})))
        stack.push(InputContext(
            "top", KeyMap({"top_action": ["w"]})  # no fallthrough
        ))
        result = stack.lookup_all(KeyEvent(key="w"))
        assert result == ["top_action"]

    def test_lookup_all_empty_stack(self) -> None:
        stack = InputContextStack()
        assert stack.lookup_all(KeyEvent(key="w")) == []


class TestInputContextStackActiveContext:
    """Tests for active_context."""

    def test_active_context_is_top_enabled(self) -> None:
        stack = InputContextStack()
        ctx = InputContext("game")
        stack.push(ctx)
        assert stack.active_context() is ctx

    def test_active_context_skips_disabled(self) -> None:
        stack = InputContextStack()
        base = InputContext("base")
        top = InputContext("top")
        top.enabled = False
        stack.push(base)
        stack.push(top)
        assert stack.active_context() is base

    def test_active_context_empty_stack(self) -> None:
        stack = InputContextStack()
        assert stack.active_context() is None

    def test_active_context_all_disabled(self) -> None:
        stack = InputContextStack()
        ctx = InputContext("a")
        ctx.enabled = False
        stack.push(ctx)
        assert stack.active_context() is None


class TestInputContextStackRepr:
    """Tests for __repr__."""

    def test_repr_empty(self) -> None:
        stack = InputContextStack()
        r = repr(stack)
        assert "InputContextStack" in r
        assert "[]" in r

    def test_repr_with_contexts(self) -> None:
        stack = InputContextStack()
        stack.push(InputContext("game"))
        stack.push(InputContext("dialog"))
        r = repr(stack)
        assert "game" in r
        assert "dialog" in r


class TestInputContextFocusWorkflow:
    """Integration-style tests for typical focus workflows."""

    def test_dialog_over_gameplay(self) -> None:
        """Simulate pushing a dialog over gameplay and popping it."""
        gameplay = InputContext("gameplay", KeyMap({
            "move_up": ["w", "up"],
            "move_down": ["s", "down"],
            "open_menu": ["escape"],
        }))
        dialog = InputContext("dialog", KeyMap({
            "confirm": ["enter"],
            "cancel": ["escape"],
        }))

        stack = InputContextStack()
        stack.push(gameplay)

        # Gameplay context active.
        assert stack.lookup(KeyEvent(key="w")) == "move_up"
        assert stack.lookup(KeyEvent(key="escape")) == "open_menu"

        # Dialog pushed — gameplay keys blocked.
        stack.push(dialog)
        assert stack.lookup(KeyEvent(key="w")) is None
        assert stack.lookup(KeyEvent(key="escape")) == "cancel"
        assert stack.lookup(KeyEvent(key="enter")) == "confirm"

        # Dialog popped — gameplay restored.
        stack.pop()
        assert stack.lookup(KeyEvent(key="w")) == "move_up"
        assert stack.lookup(KeyEvent(key="escape")) == "open_menu"

    def test_hud_overlay_with_fallthrough(self) -> None:
        """HUD binds a few keys and lets the rest fall through."""
        gameplay = InputContext("gameplay", KeyMap({
            "move_up": ["w"],
            "attack": ["space"],
        }))
        hud = InputContext("hud", KeyMap({
            "toggle_map": ["m"],
            "toggle_inventory": ["i"],
        }), fallthrough=True)

        stack = InputContextStack()
        stack.push(gameplay)
        stack.push(hud)

        # HUD keys work.
        assert stack.lookup(KeyEvent(key="m")) == "toggle_map"
        assert stack.lookup(KeyEvent(key="i")) == "toggle_inventory"
        # Gameplay keys still reachable via fallthrough.
        assert stack.lookup(KeyEvent(key="w")) == "move_up"
        assert stack.lookup(KeyEvent(key="space")) == "attack"
        # Unknown keys return None (gameplay has no fallthrough).
        assert stack.lookup(KeyEvent(key="x")) is None

    def test_cutscene_blocks_all_input(self) -> None:
        """Empty context with no fallthrough blocks everything."""
        gameplay = InputContext("gameplay", KeyMap({"move": ["w"]}))
        cutscene = InputContext("cutscene")  # empty, no fallthrough

        stack = InputContextStack()
        stack.push(gameplay)
        stack.push(cutscene)

        assert stack.lookup(KeyEvent(key="w")) is None
        assert stack.active_context() is cutscene

    def test_disable_reenable_context(self) -> None:
        """Temporarily disable a context during animation."""
        ctx = InputContext("game", KeyMap({"move": ["w"]}))
        stack = InputContextStack()
        stack.push(ctx)

        assert stack.lookup(KeyEvent(key="w")) == "move"

        # Disable during animation.
        ctx.enabled = False
        assert stack.lookup(KeyEvent(key="w")) is None

        # Re-enable.
        ctx.enabled = True
        assert stack.lookup(KeyEvent(key="w")) == "move"

    def test_replace_context_for_mode_switch(self) -> None:
        """Replace top context when switching modes."""
        normal = InputContext("normal", KeyMap({"move": ["w"]}))
        combat = InputContext("combat", KeyMap({"attack": ["w"]}))

        stack = InputContextStack()
        stack.push(normal)
        assert stack.lookup(KeyEvent(key="w")) == "move"

        stack.replace(combat)
        assert stack.lookup(KeyEvent(key="w")) == "attack"
        assert len(stack) == 1
