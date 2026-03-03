"""Tests for wyby.scene — Scene base class and SceneStack."""

from __future__ import annotations

import logging

import pytest

from wyby.scene import (
    Scene,
    SceneStack,
    _DEFAULT_MAX_DEPTH,
    _MAX_MAX_DEPTH,
    _MIN_MAX_DEPTH,
)


# ---------------------------------------------------------------------------
# Concrete Scene subclass for testing
# ---------------------------------------------------------------------------


class DummyScene(Scene):
    """Minimal concrete Scene for testing lifecycle hooks."""

    def __init__(self, name: str = "dummy") -> None:
        self.name = name
        self.calls: list[str] = []

    def update(self, dt: float) -> None:
        self.calls.append("update")

    def render(self) -> None:
        self.calls.append("render")

    def on_enter(self) -> None:
        self.calls.append("on_enter")

    def on_exit(self) -> None:
        self.calls.append("on_exit")

    def on_pause(self) -> None:
        self.calls.append("on_pause")

    def on_resume(self) -> None:
        self.calls.append("on_resume")

    def __repr__(self) -> str:
        return f"DummyScene({self.name!r})"


# ---------------------------------------------------------------------------
# Scene ABC
# ---------------------------------------------------------------------------


class TestSceneABC:
    """Scene is abstract and requires update() and render()."""

    def test_cannot_instantiate_scene_directly(self) -> None:
        with pytest.raises(TypeError):
            Scene()  # type: ignore[abstract]

    def test_must_implement_update(self) -> None:
        class NoUpdate(Scene):
            def render(self) -> None:
                pass

        with pytest.raises(TypeError):
            NoUpdate()  # type: ignore[abstract]

    def test_must_implement_render(self) -> None:
        class NoRender(Scene):
            def update(self, dt: float) -> None:
                pass

        with pytest.raises(TypeError):
            NoRender()  # type: ignore[abstract]

    def test_concrete_subclass_instantiates(self) -> None:
        scene = DummyScene()
        assert isinstance(scene, Scene)

    def test_lifecycle_hooks_are_optional_noops(self) -> None:
        """Default lifecycle hooks should be callable and do nothing."""

        class MinimalScene(Scene):
            def update(self, dt: float) -> None:
                pass

            def render(self) -> None:
                pass

        scene = MinimalScene()
        # None of these should raise.
        scene.on_enter()
        scene.on_exit()
        scene.on_pause()
        scene.on_resume()


# ---------------------------------------------------------------------------
# SceneStack construction
# ---------------------------------------------------------------------------


class TestSceneStackConstruction:
    """SceneStack construction and max_depth validation."""

    def test_default_max_depth(self) -> None:
        stack = SceneStack()
        assert stack.max_depth == _DEFAULT_MAX_DEPTH

    def test_custom_max_depth(self) -> None:
        stack = SceneStack(max_depth=10)
        assert stack.max_depth == 10

    def test_minimum_max_depth(self) -> None:
        stack = SceneStack(max_depth=_MIN_MAX_DEPTH)
        assert stack.max_depth == _MIN_MAX_DEPTH

    def test_maximum_max_depth(self) -> None:
        stack = SceneStack(max_depth=_MAX_MAX_DEPTH)
        assert stack.max_depth == _MAX_MAX_DEPTH

    def test_rejects_float_max_depth(self) -> None:
        with pytest.raises(TypeError, match="max_depth must be an int"):
            SceneStack(max_depth=10.0)  # type: ignore[arg-type]

    def test_rejects_bool_max_depth(self) -> None:
        with pytest.raises(TypeError, match="max_depth must be an int"):
            SceneStack(max_depth=True)  # type: ignore[arg-type]

    def test_rejects_zero_max_depth(self) -> None:
        with pytest.raises(ValueError, match="max_depth must be between"):
            SceneStack(max_depth=0)

    def test_rejects_negative_max_depth(self) -> None:
        with pytest.raises(ValueError, match="max_depth must be between"):
            SceneStack(max_depth=-1)

    def test_rejects_above_max_max_depth(self) -> None:
        with pytest.raises(ValueError, match="max_depth must be between"):
            SceneStack(max_depth=_MAX_MAX_DEPTH + 1)

    def test_starts_empty(self) -> None:
        stack = SceneStack()
        assert len(stack) == 0
        assert stack.is_empty is True
        assert stack.peek() is None


# ---------------------------------------------------------------------------
# SceneStack __len__ and __bool__
# ---------------------------------------------------------------------------


class TestSceneStackLenBool:
    """len() and bool() on SceneStack."""

    def test_empty_stack_is_falsy(self) -> None:
        stack = SceneStack()
        assert not stack

    def test_nonempty_stack_is_truthy(self) -> None:
        stack = SceneStack()
        stack.push(DummyScene())
        assert stack

    def test_len_tracks_depth(self) -> None:
        stack = SceneStack()
        assert len(stack) == 0
        stack.push(DummyScene("a"))
        assert len(stack) == 1
        stack.push(DummyScene("b"))
        assert len(stack) == 2
        stack.pop()
        assert len(stack) == 1


# ---------------------------------------------------------------------------
# push
# ---------------------------------------------------------------------------


class TestSceneStackPush:
    """Pushing scenes onto the stack."""

    def test_push_single_scene(self) -> None:
        stack = SceneStack()
        scene = DummyScene()
        stack.push(scene)
        assert stack.peek() is scene
        assert len(stack) == 1

    def test_push_calls_on_enter(self) -> None:
        stack = SceneStack()
        scene = DummyScene()
        stack.push(scene)
        assert "on_enter" in scene.calls

    def test_push_pauses_previous_top(self) -> None:
        stack = SceneStack()
        first = DummyScene("first")
        second = DummyScene("second")
        stack.push(first)
        first.calls.clear()
        stack.push(second)
        assert "on_pause" in first.calls

    def test_push_order_pause_before_enter(self) -> None:
        """on_pause on old top should happen before on_enter on new."""
        stack = SceneStack()
        call_log: list[str] = []

        class LoggingScene(Scene):
            def __init__(self, name: str) -> None:
                self._name = name

            def update(self, dt: float) -> None:
                pass

            def render(self) -> None:
                pass

            def on_enter(self) -> None:
                call_log.append(f"{self._name}.on_enter")

            def on_pause(self) -> None:
                call_log.append(f"{self._name}.on_pause")

        first = LoggingScene("first")
        second = LoggingScene("second")
        stack.push(first)
        call_log.clear()
        stack.push(second)
        assert call_log == ["first.on_pause", "second.on_enter"]

    def test_push_multiple_scenes(self) -> None:
        stack = SceneStack()
        scenes = [DummyScene(str(i)) for i in range(5)]
        for s in scenes:
            stack.push(s)
        assert len(stack) == 5
        assert stack.peek() is scenes[-1]

    def test_push_rejects_non_scene(self) -> None:
        stack = SceneStack()
        with pytest.raises(TypeError, match="scene must be a Scene instance"):
            stack.push("not a scene")  # type: ignore[arg-type]

    def test_push_rejects_none(self) -> None:
        stack = SceneStack()
        with pytest.raises(TypeError, match="scene must be a Scene instance"):
            stack.push(None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# pop
# ---------------------------------------------------------------------------


class TestSceneStackPop:
    """Popping scenes from the stack."""

    def test_pop_returns_top_scene(self) -> None:
        stack = SceneStack()
        scene = DummyScene()
        stack.push(scene)
        result = stack.pop()
        assert result is scene

    def test_pop_calls_on_exit(self) -> None:
        stack = SceneStack()
        scene = DummyScene()
        stack.push(scene)
        scene.calls.clear()
        stack.pop()
        assert "on_exit" in scene.calls

    def test_pop_resumes_previous_scene(self) -> None:
        stack = SceneStack()
        first = DummyScene("first")
        second = DummyScene("second")
        stack.push(first)
        stack.push(second)
        first.calls.clear()
        stack.pop()
        assert "on_resume" in first.calls

    def test_pop_order_exit_before_resume(self) -> None:
        """on_exit on popped scene should happen before on_resume on new top."""
        stack = SceneStack()
        call_log: list[str] = []

        class LoggingScene(Scene):
            def __init__(self, name: str) -> None:
                self._name = name

            def update(self, dt: float) -> None:
                pass

            def render(self) -> None:
                pass

            def on_exit(self) -> None:
                call_log.append(f"{self._name}.on_exit")

            def on_resume(self) -> None:
                call_log.append(f"{self._name}.on_resume")

        first = LoggingScene("first")
        second = LoggingScene("second")
        stack.push(first)
        stack.push(second)
        call_log.clear()
        stack.pop()
        assert call_log == ["second.on_exit", "first.on_resume"]

    def test_pop_last_scene_no_resume(self) -> None:
        """Popping the only scene should not call on_resume on anything."""
        stack = SceneStack()
        scene = DummyScene()
        stack.push(scene)
        scene.calls.clear()
        stack.pop()
        assert "on_resume" not in scene.calls
        assert stack.is_empty

    def test_pop_empty_stack_raises(self) -> None:
        stack = SceneStack()
        with pytest.raises(RuntimeError, match="empty scene stack"):
            stack.pop()

    def test_pop_removes_scene(self) -> None:
        stack = SceneStack()
        stack.push(DummyScene())
        stack.pop()
        assert len(stack) == 0
        assert stack.is_empty


# ---------------------------------------------------------------------------
# replace
# ---------------------------------------------------------------------------


class TestSceneStackReplace:
    """Replacing the top scene."""

    def test_replace_returns_old_scene(self) -> None:
        stack = SceneStack()
        old = DummyScene("old")
        new = DummyScene("new")
        stack.push(old)
        result = stack.replace(new)
        assert result is old

    def test_replace_new_scene_is_on_top(self) -> None:
        stack = SceneStack()
        stack.push(DummyScene("old"))
        new = DummyScene("new")
        stack.replace(new)
        assert stack.peek() is new

    def test_replace_calls_on_exit_and_on_enter(self) -> None:
        stack = SceneStack()
        old = DummyScene("old")
        new = DummyScene("new")
        stack.push(old)
        old.calls.clear()
        stack.replace(new)
        assert "on_exit" in old.calls
        assert "on_enter" in new.calls

    def test_replace_does_not_affect_scene_below(self) -> None:
        """Replace should not trigger on_pause/on_resume on scenes below."""
        stack = SceneStack()
        bottom = DummyScene("bottom")
        top = DummyScene("top")
        stack.push(bottom)
        stack.push(top)
        bottom.calls.clear()

        new_top = DummyScene("new_top")
        stack.replace(new_top)

        # bottom should not get on_pause or on_resume from a replace.
        assert "on_pause" not in bottom.calls
        assert "on_resume" not in bottom.calls

    def test_replace_order_exit_before_enter(self) -> None:
        stack = SceneStack()
        call_log: list[str] = []

        class LoggingScene(Scene):
            def __init__(self, name: str) -> None:
                self._name = name

            def update(self, dt: float) -> None:
                pass

            def render(self) -> None:
                pass

            def on_exit(self) -> None:
                call_log.append(f"{self._name}.on_exit")

            def on_enter(self) -> None:
                call_log.append(f"{self._name}.on_enter")

        old = LoggingScene("old")
        new = LoggingScene("new")
        stack.push(old)
        call_log.clear()
        stack.replace(new)
        assert call_log == ["old.on_exit", "new.on_enter"]

    def test_replace_preserves_depth(self) -> None:
        stack = SceneStack()
        stack.push(DummyScene("a"))
        stack.push(DummyScene("b"))
        assert len(stack) == 2
        stack.replace(DummyScene("c"))
        assert len(stack) == 2

    def test_replace_empty_stack_raises(self) -> None:
        stack = SceneStack()
        with pytest.raises(RuntimeError, match="empty scene stack"):
            stack.replace(DummyScene())

    def test_replace_rejects_non_scene(self) -> None:
        stack = SceneStack()
        stack.push(DummyScene())
        with pytest.raises(TypeError, match="scene must be a Scene instance"):
            stack.replace(42)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# clear
# ---------------------------------------------------------------------------


class TestSceneStackClear:
    """Clearing all scenes from the stack."""

    def test_clear_empties_stack(self) -> None:
        stack = SceneStack()
        for i in range(5):
            stack.push(DummyScene(str(i)))
        assert len(stack) == 5
        stack.clear()
        assert len(stack) == 0
        assert stack.is_empty

    def test_clear_calls_on_exit_for_all(self) -> None:
        stack = SceneStack()
        scenes = [DummyScene(str(i)) for i in range(3)]
        for s in scenes:
            stack.push(s)
        for s in scenes:
            s.calls.clear()
        stack.clear()
        for s in scenes:
            assert "on_exit" in s.calls

    def test_clear_exits_top_to_bottom(self) -> None:
        """on_exit should be called in top-to-bottom order."""
        stack = SceneStack()
        exit_order: list[str] = []

        class OrderScene(Scene):
            def __init__(self, name: str) -> None:
                self._name = name

            def update(self, dt: float) -> None:
                pass

            def render(self) -> None:
                pass

            def on_exit(self) -> None:
                exit_order.append(self._name)

        stack.push(OrderScene("a"))
        stack.push(OrderScene("b"))
        stack.push(OrderScene("c"))
        stack.clear()
        assert exit_order == ["c", "b", "a"]

    def test_clear_empty_stack_is_noop(self) -> None:
        stack = SceneStack()
        stack.clear()  # Should not raise.
        assert stack.is_empty

    def test_clear_does_not_call_on_resume(self) -> None:
        """No scene should receive on_resume during clear."""
        stack = SceneStack()
        scenes = [DummyScene(str(i)) for i in range(3)]
        for s in scenes:
            stack.push(s)
        for s in scenes:
            s.calls.clear()
        stack.clear()
        for s in scenes:
            assert "on_resume" not in s.calls


# ---------------------------------------------------------------------------
# Stack depth limits
# ---------------------------------------------------------------------------


class TestSceneStackDepthLimit:
    """Stack depth limit enforcement."""

    def test_push_at_max_depth_raises(self) -> None:
        stack = SceneStack(max_depth=3)
        for i in range(3):
            stack.push(DummyScene(str(i)))
        with pytest.raises(RuntimeError, match="depth limit reached"):
            stack.push(DummyScene("overflow"))

    def test_push_at_max_depth_does_not_corrupt_stack(self) -> None:
        stack = SceneStack(max_depth=2)
        a = DummyScene("a")
        b = DummyScene("b")
        stack.push(a)
        stack.push(b)
        with pytest.raises(RuntimeError):
            stack.push(DummyScene("c"))
        # Stack should be unchanged.
        assert len(stack) == 2
        assert stack.peek() is b

    def test_pop_then_push_under_limit(self) -> None:
        """After popping, pushing should work again."""
        stack = SceneStack(max_depth=2)
        stack.push(DummyScene("a"))
        stack.push(DummyScene("b"))
        stack.pop()
        stack.push(DummyScene("c"))  # Should not raise.
        assert len(stack) == 2

    def test_max_depth_one(self) -> None:
        """A stack with max_depth=1 allows exactly one scene."""
        stack = SceneStack(max_depth=1)
        stack.push(DummyScene())
        with pytest.raises(RuntimeError, match="depth limit"):
            stack.push(DummyScene())

    def test_default_max_depth_value(self) -> None:
        assert _DEFAULT_MAX_DEPTH == 32


# ---------------------------------------------------------------------------
# peek
# ---------------------------------------------------------------------------


class TestSceneStackPeek:
    """Peeking at the top scene."""

    def test_peek_empty_returns_none(self) -> None:
        stack = SceneStack()
        assert stack.peek() is None

    def test_peek_returns_top(self) -> None:
        stack = SceneStack()
        scene = DummyScene()
        stack.push(scene)
        assert stack.peek() is scene

    def test_peek_does_not_remove(self) -> None:
        stack = SceneStack()
        stack.push(DummyScene())
        stack.peek()
        assert len(stack) == 1

    def test_peek_after_push_push(self) -> None:
        stack = SceneStack()
        a = DummyScene("a")
        b = DummyScene("b")
        stack.push(a)
        stack.push(b)
        assert stack.peek() is b


# ---------------------------------------------------------------------------
# __repr__
# ---------------------------------------------------------------------------


class TestSceneStackRepr:
    """SceneStack repr should be informative."""

    def test_repr_empty(self) -> None:
        stack = SceneStack()
        r = repr(stack)
        assert "SceneStack" in r
        assert "[]" in r
        assert "max_depth=32" in r

    def test_repr_with_scenes(self) -> None:
        stack = SceneStack(max_depth=10)
        stack.push(DummyScene("a"))
        stack.push(DummyScene("b"))
        r = repr(stack)
        assert "DummyScene" in r
        assert "max_depth=10" in r


# ---------------------------------------------------------------------------
# is_empty property
# ---------------------------------------------------------------------------


class TestSceneStackIsEmpty:
    """is_empty property."""

    def test_empty_on_creation(self) -> None:
        stack = SceneStack()
        assert stack.is_empty is True

    def test_not_empty_after_push(self) -> None:
        stack = SceneStack()
        stack.push(DummyScene())
        assert stack.is_empty is False

    def test_empty_after_pop_all(self) -> None:
        stack = SceneStack()
        stack.push(DummyScene())
        stack.pop()
        assert stack.is_empty is True


# ---------------------------------------------------------------------------
# max_depth read-only
# ---------------------------------------------------------------------------


class TestSceneStackMaxDepthReadOnly:
    """max_depth should be read-only."""

    def test_max_depth_is_read_only(self) -> None:
        stack = SceneStack()
        with pytest.raises(AttributeError):
            stack.max_depth = 100  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------


class TestSceneStackLogging:
    """SceneStack should log operations at DEBUG level."""

    def test_push_logs(self, caplog: pytest.LogCaptureFixture) -> None:
        stack = SceneStack()
        with caplog.at_level(logging.DEBUG, logger="wyby.scene"):
            stack.push(DummyScene())
        messages = [r.message for r in caplog.records]
        assert any("Pushed" in m for m in messages)

    def test_pop_logs(self, caplog: pytest.LogCaptureFixture) -> None:
        stack = SceneStack()
        stack.push(DummyScene())
        with caplog.at_level(logging.DEBUG, logger="wyby.scene"):
            stack.pop()
        messages = [r.message for r in caplog.records]
        assert any("Popped" in m for m in messages)

    def test_replace_logs(self, caplog: pytest.LogCaptureFixture) -> None:
        stack = SceneStack()
        stack.push(DummyScene())
        with caplog.at_level(logging.DEBUG, logger="wyby.scene"):
            stack.replace(DummyScene())
        messages = [r.message for r in caplog.records]
        assert any("Replacing" in m for m in messages)

    def test_clear_logs(self, caplog: pytest.LogCaptureFixture) -> None:
        stack = SceneStack()
        stack.push(DummyScene())
        with caplog.at_level(logging.DEBUG, logger="wyby.scene"):
            stack.clear()
        messages = [r.message for r in caplog.records]
        assert any("Clearing" in m for m in messages)


# ---------------------------------------------------------------------------
# Public re-export from wyby package
# ---------------------------------------------------------------------------


class TestSceneImport:
    """Scene and SceneStack should be importable from the wyby package."""

    def test_scene_importable_from_wyby(self) -> None:
        from wyby import Scene as SceneFromInit

        assert SceneFromInit is Scene

    def test_scene_stack_importable_from_wyby(self) -> None:
        from wyby import SceneStack as StackFromInit

        assert StackFromInit is SceneStack
