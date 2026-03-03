"""Tests for wyby.scene — Scene base class and SceneStack."""

from __future__ import annotations

import logging

import pytest

from wyby.event import Event
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
        super().__init__()
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


# ---------------------------------------------------------------------------
# Callback-based enter/exit hooks
# ---------------------------------------------------------------------------


class TestSceneEnterHooks:
    """Callback-based on_enter hooks via add_enter_hook / remove_enter_hook."""

    def test_add_enter_hook_fires_on_push(self) -> None:
        stack = SceneStack()
        scene = DummyScene()
        log: list[str] = []
        scene.add_enter_hook(lambda: log.append("hook_called"))
        stack.push(scene)
        assert "hook_called" in log

    def test_enter_hook_fires_after_on_enter(self) -> None:
        """Registered callbacks fire after the overridden on_enter."""
        stack = SceneStack()
        scene = DummyScene()
        order: list[str] = []
        scene.add_enter_hook(lambda: order.append("hook"))
        # DummyScene.on_enter appends "on_enter" to scene.calls, so
        # we also hook into that to track ordering.
        original_on_enter = scene.on_enter

        def tracking_on_enter() -> None:
            original_on_enter()
            order.append("on_enter")

        scene.on_enter = tracking_on_enter  # type: ignore[assignment]
        stack.push(scene)
        assert order == ["on_enter", "hook"]

    def test_multiple_enter_hooks_fire_in_order(self) -> None:
        stack = SceneStack()
        scene = DummyScene()
        log: list[int] = []
        scene.add_enter_hook(lambda: log.append(1))
        scene.add_enter_hook(lambda: log.append(2))
        scene.add_enter_hook(lambda: log.append(3))
        stack.push(scene)
        assert log == [1, 2, 3]

    def test_enter_hook_fires_on_replace_new_scene(self) -> None:
        stack = SceneStack()
        stack.push(DummyScene("old"))
        new = DummyScene("new")
        log: list[str] = []
        new.add_enter_hook(lambda: log.append("entered"))
        stack.replace(new)
        assert "entered" in log

    def test_remove_enter_hook(self) -> None:
        scene = DummyScene()
        log: list[str] = []
        cb = lambda: log.append("should_not_fire")  # noqa: E731
        scene.add_enter_hook(cb)
        scene.remove_enter_hook(cb)
        scene._fire_enter()
        assert "should_not_fire" not in log

    def test_remove_enter_hook_not_registered_raises(self) -> None:
        scene = DummyScene()
        with pytest.raises(ValueError):
            scene.remove_enter_hook(lambda: None)

    def test_add_enter_hook_rejects_non_callable(self) -> None:
        scene = DummyScene()
        with pytest.raises(TypeError, match="callback must be callable"):
            scene.add_enter_hook(42)  # type: ignore[arg-type]

    def test_same_callback_registered_twice(self) -> None:
        """Same callback registered twice fires twice."""
        scene = DummyScene()
        count: list[int] = []
        cb = lambda: count.append(1)  # noqa: E731
        scene.add_enter_hook(cb)
        scene.add_enter_hook(cb)
        scene._fire_enter()
        assert len(count) == 2

    def test_remove_only_removes_first_registration(self) -> None:
        """remove_enter_hook removes only the first matching registration."""
        scene = DummyScene()
        count: list[int] = []
        cb = lambda: count.append(1)  # noqa: E731
        scene.add_enter_hook(cb)
        scene.add_enter_hook(cb)
        scene.remove_enter_hook(cb)
        scene._fire_enter()
        assert len(count) == 1


class TestSceneExitHooks:
    """Callback-based on_exit hooks via add_exit_hook / remove_exit_hook."""

    def test_add_exit_hook_fires_on_pop(self) -> None:
        stack = SceneStack()
        scene = DummyScene()
        log: list[str] = []
        scene.add_exit_hook(lambda: log.append("hook_called"))
        stack.push(scene)
        stack.pop()
        assert "hook_called" in log

    def test_exit_hook_fires_after_on_exit(self) -> None:
        """Registered callbacks fire after the overridden on_exit."""
        scene = DummyScene()
        order: list[str] = []
        original_on_exit = scene.on_exit

        def tracking_on_exit() -> None:
            original_on_exit()
            order.append("on_exit")

        scene.on_exit = tracking_on_exit  # type: ignore[assignment]
        scene.add_exit_hook(lambda: order.append("hook"))
        scene._fire_exit()
        assert order == ["on_exit", "hook"]

    def test_multiple_exit_hooks_fire_in_order(self) -> None:
        stack = SceneStack()
        scene = DummyScene()
        log: list[int] = []
        scene.add_exit_hook(lambda: log.append(1))
        scene.add_exit_hook(lambda: log.append(2))
        scene.add_exit_hook(lambda: log.append(3))
        stack.push(scene)
        stack.pop()
        assert log == [1, 2, 3]

    def test_exit_hook_fires_on_replace_old_scene(self) -> None:
        stack = SceneStack()
        old = DummyScene("old")
        log: list[str] = []
        old.add_exit_hook(lambda: log.append("exited"))
        stack.push(old)
        stack.replace(DummyScene("new"))
        assert "exited" in log

    def test_exit_hook_fires_on_clear(self) -> None:
        stack = SceneStack()
        scene = DummyScene()
        log: list[str] = []
        scene.add_exit_hook(lambda: log.append("cleared"))
        stack.push(scene)
        stack.clear()
        assert "cleared" in log

    def test_remove_exit_hook(self) -> None:
        scene = DummyScene()
        log: list[str] = []
        cb = lambda: log.append("should_not_fire")  # noqa: E731
        scene.add_exit_hook(cb)
        scene.remove_exit_hook(cb)
        scene._fire_exit()
        assert "should_not_fire" not in log

    def test_remove_exit_hook_not_registered_raises(self) -> None:
        scene = DummyScene()
        with pytest.raises(ValueError):
            scene.remove_exit_hook(lambda: None)

    def test_add_exit_hook_rejects_non_callable(self) -> None:
        scene = DummyScene()
        with pytest.raises(TypeError, match="callback must be callable"):
            scene.add_exit_hook("not callable")  # type: ignore[arg-type]


class TestSceneHooksWithoutSuperInit:
    """Hooks should work even if a subclass forgets super().__init__()."""

    def test_enter_hook_works_without_super_init(self) -> None:
        class NoSuperScene(Scene):
            def __init__(self) -> None:
                # Deliberately not calling super().__init__()
                pass

            def update(self, dt: float) -> None:
                pass

            def render(self) -> None:
                pass

        scene = NoSuperScene()
        log: list[str] = []
        scene.add_enter_hook(lambda: log.append("entered"))
        scene._fire_enter()
        assert log == ["entered"]

    def test_exit_hook_works_without_super_init(self) -> None:
        class NoSuperScene(Scene):
            def __init__(self) -> None:
                pass

            def update(self, dt: float) -> None:
                pass

            def render(self) -> None:
                pass

        scene = NoSuperScene()
        log: list[str] = []
        scene.add_exit_hook(lambda: log.append("exited"))
        scene._fire_exit()
        assert log == ["exited"]

    def test_fire_enter_without_hooks_is_safe(self) -> None:
        """_fire_enter works even if no hooks registered and no super().__init__()."""

        class NoSuperScene(Scene):
            def __init__(self) -> None:
                pass

            def update(self, dt: float) -> None:
                pass

            def render(self) -> None:
                pass

        scene = NoSuperScene()
        scene._fire_enter()  # Should not raise

    def test_fire_exit_without_hooks_is_safe(self) -> None:
        """_fire_exit works even if no hooks registered and no super().__init__()."""

        class NoSuperScene(Scene):
            def __init__(self) -> None:
                pass

            def update(self, dt: float) -> None:
                pass

            def render(self) -> None:
                pass

        scene = NoSuperScene()
        scene._fire_exit()  # Should not raise


# ---------------------------------------------------------------------------
# handle_events
# ---------------------------------------------------------------------------


class TestSceneHandleEvents:
    """Scene.handle_events() — per-tick event delivery."""

    def test_default_handle_events_is_noop_empty_list(self) -> None:
        """Default implementation accepts an empty list without raising."""

        class MinimalScene(Scene):
            def update(self, dt: float) -> None:
                pass

            def render(self) -> None:
                pass

        scene = MinimalScene()
        scene.handle_events([])  # Should not raise.

    def test_default_handle_events_is_noop_with_events(self) -> None:
        """Default implementation accepts events without raising."""

        class MinimalScene(Scene):
            def update(self, dt: float) -> None:
                pass

            def render(self) -> None:
                pass

        scene = MinimalScene()
        scene.handle_events([Event(), Event()])  # Should not raise.

    def test_handle_events_is_not_abstract(self) -> None:
        """A scene that only implements update/render should instantiate
        without overriding handle_events."""

        class MinimalScene(Scene):
            def update(self, dt: float) -> None:
                pass

            def render(self) -> None:
                pass

        scene = MinimalScene()
        assert isinstance(scene, Scene)

    def test_subclass_receives_events(self) -> None:
        """A subclass that overrides handle_events receives the event list."""
        received: list[list[Event]] = []

        class EventScene(Scene):
            def handle_events(self, events: list[Event]) -> None:
                received.append(list(events))

            def update(self, dt: float) -> None:
                pass

            def render(self) -> None:
                pass

        scene = EventScene()
        events = [Event(), Event()]
        scene.handle_events(events)
        assert len(received) == 1
        assert len(received[0]) == 2

    def test_handle_events_called_on_dummy_scene(self) -> None:
        """DummyScene inherits the default no-op handle_events."""
        scene = DummyScene()
        scene.handle_events([Event()])  # Should not raise.


# ---------------------------------------------------------------------------
# updates_when_paused / renders_when_paused properties
# ---------------------------------------------------------------------------


class TestSceneUpdatesWhenPaused:
    """Scene.updates_when_paused flag controls per-scene update policy."""

    def test_default_is_false(self) -> None:
        scene = DummyScene()
        assert scene.updates_when_paused is False

    def test_can_set_to_true(self) -> None:
        scene = DummyScene()
        scene.updates_when_paused = True
        assert scene.updates_when_paused is True

    def test_can_set_back_to_false(self) -> None:
        scene = DummyScene()
        scene.updates_when_paused = True
        scene.updates_when_paused = False
        assert scene.updates_when_paused is False

    def test_coerces_truthy_to_bool(self) -> None:
        scene = DummyScene()
        scene.updates_when_paused = 1  # type: ignore[assignment]
        assert scene.updates_when_paused is True

    def test_coerces_falsy_to_bool(self) -> None:
        scene = DummyScene()
        scene.updates_when_paused = 0  # type: ignore[assignment]
        assert scene.updates_when_paused is False

    def test_works_without_super_init(self) -> None:
        """Property should work even if subclass skips super().__init__()."""

        class NoSuperScene(Scene):
            def __init__(self) -> None:
                pass

            def update(self, dt: float) -> None:
                pass

            def render(self) -> None:
                pass

        scene = NoSuperScene()
        assert scene.updates_when_paused is False
        scene.updates_when_paused = True
        assert scene.updates_when_paused is True


class TestSceneRendersWhenPaused:
    """Scene.renders_when_paused flag controls per-scene render policy."""

    def test_default_is_false(self) -> None:
        scene = DummyScene()
        assert scene.renders_when_paused is False

    def test_can_set_to_true(self) -> None:
        scene = DummyScene()
        scene.renders_when_paused = True
        assert scene.renders_when_paused is True

    def test_can_set_back_to_false(self) -> None:
        scene = DummyScene()
        scene.renders_when_paused = True
        scene.renders_when_paused = False
        assert scene.renders_when_paused is False

    def test_coerces_truthy_to_bool(self) -> None:
        scene = DummyScene()
        scene.renders_when_paused = 1  # type: ignore[assignment]
        assert scene.renders_when_paused is True

    def test_coerces_falsy_to_bool(self) -> None:
        scene = DummyScene()
        scene.renders_when_paused = 0  # type: ignore[assignment]
        assert scene.renders_when_paused is False


# ---------------------------------------------------------------------------
# scenes_to_update / scenes_to_render
# ---------------------------------------------------------------------------


class TestSceneStackScenesToUpdate:
    """SceneStack.scenes_to_update() returns scenes that should update."""

    def test_empty_stack_returns_empty_list(self) -> None:
        stack = SceneStack()
        assert stack.scenes_to_update() == []

    def test_single_scene_returns_that_scene(self) -> None:
        stack = SceneStack()
        scene = DummyScene("a")
        stack.push(scene)
        assert stack.scenes_to_update() == [scene]

    def test_top_scene_always_included(self) -> None:
        stack = SceneStack()
        bottom = DummyScene("bottom")
        top = DummyScene("top")
        stack.push(bottom)
        stack.push(top)
        result = stack.scenes_to_update()
        assert top in result

    def test_paused_scene_excluded_by_default(self) -> None:
        stack = SceneStack()
        bottom = DummyScene("bottom")
        top = DummyScene("top")
        stack.push(bottom)
        stack.push(top)
        assert bottom not in stack.scenes_to_update()

    def test_paused_scene_included_when_flag_set(self) -> None:
        stack = SceneStack()
        bottom = DummyScene("bottom")
        bottom.updates_when_paused = True
        top = DummyScene("top")
        stack.push(bottom)
        stack.push(top)
        result = stack.scenes_to_update()
        assert bottom in result
        assert top in result

    def test_order_is_bottom_to_top(self) -> None:
        stack = SceneStack()
        a = DummyScene("a")
        a.updates_when_paused = True
        b = DummyScene("b")
        b.updates_when_paused = True
        c = DummyScene("c")
        stack.push(a)
        stack.push(b)
        stack.push(c)
        result = stack.scenes_to_update()
        assert result == [a, b, c]

    def test_mixed_flags(self) -> None:
        """Only scenes with the flag set are included (plus top)."""
        stack = SceneStack()
        a = DummyScene("a")
        a.updates_when_paused = True
        b = DummyScene("b")  # default False
        c = DummyScene("c")
        c.updates_when_paused = True
        d = DummyScene("d")  # top
        stack.push(a)
        stack.push(b)
        stack.push(c)
        stack.push(d)
        result = stack.scenes_to_update()
        assert result == [a, c, d]

    def test_returns_snapshot_not_live_view(self) -> None:
        """The returned list should not be affected by later stack mutations."""
        stack = SceneStack()
        scene = DummyScene("a")
        stack.push(scene)
        snapshot = stack.scenes_to_update()
        stack.pop()
        # The snapshot should still contain the scene.
        assert snapshot == [scene]


class TestSceneStackScenesToRender:
    """SceneStack.scenes_to_render() returns scenes that should render."""

    def test_empty_stack_returns_empty_list(self) -> None:
        stack = SceneStack()
        assert stack.scenes_to_render() == []

    def test_single_scene_returns_that_scene(self) -> None:
        stack = SceneStack()
        scene = DummyScene("a")
        stack.push(scene)
        assert stack.scenes_to_render() == [scene]

    def test_top_scene_always_included(self) -> None:
        stack = SceneStack()
        bottom = DummyScene("bottom")
        top = DummyScene("top")
        stack.push(bottom)
        stack.push(top)
        result = stack.scenes_to_render()
        assert top in result

    def test_paused_scene_excluded_by_default(self) -> None:
        stack = SceneStack()
        bottom = DummyScene("bottom")
        top = DummyScene("top")
        stack.push(bottom)
        stack.push(top)
        assert bottom not in stack.scenes_to_render()

    def test_paused_scene_included_when_flag_set(self) -> None:
        stack = SceneStack()
        bottom = DummyScene("bottom")
        bottom.renders_when_paused = True
        top = DummyScene("top")
        stack.push(bottom)
        stack.push(top)
        result = stack.scenes_to_render()
        assert bottom in result
        assert top in result

    def test_order_is_bottom_to_top(self) -> None:
        stack = SceneStack()
        a = DummyScene("a")
        a.renders_when_paused = True
        b = DummyScene("b")
        b.renders_when_paused = True
        c = DummyScene("c")
        stack.push(a)
        stack.push(b)
        stack.push(c)
        result = stack.scenes_to_render()
        assert result == [a, b, c]

    def test_mixed_flags(self) -> None:
        stack = SceneStack()
        a = DummyScene("a")  # default False
        b = DummyScene("b")
        b.renders_when_paused = True
        c = DummyScene("c")  # top
        stack.push(a)
        stack.push(b)
        stack.push(c)
        result = stack.scenes_to_render()
        assert result == [b, c]

    def test_update_and_render_flags_are_independent(self) -> None:
        """updates_when_paused and renders_when_paused are independent."""
        stack = SceneStack()
        bottom = DummyScene("bottom")
        bottom.updates_when_paused = True
        bottom.renders_when_paused = False
        top = DummyScene("top")
        stack.push(bottom)
        stack.push(top)
        assert bottom in stack.scenes_to_update()
        assert bottom not in stack.scenes_to_render()


# ---------------------------------------------------------------------------
# __contains__
# ---------------------------------------------------------------------------


class TestSceneStackContains:
    """SceneStack.__contains__() — identity-based membership check."""

    def test_contains_pushed_scene(self) -> None:
        stack = SceneStack()
        scene = DummyScene()
        stack.push(scene)
        assert scene in stack

    def test_not_contains_unpushed_scene(self) -> None:
        stack = SceneStack()
        scene = DummyScene()
        assert scene not in stack

    def test_not_contains_after_pop(self) -> None:
        stack = SceneStack()
        scene = DummyScene()
        stack.push(scene)
        stack.pop()
        assert scene not in stack

    def test_contains_paused_scene(self) -> None:
        """A scene covered by another is still on the stack."""
        stack = SceneStack()
        bottom = DummyScene("bottom")
        top = DummyScene("top")
        stack.push(bottom)
        stack.push(top)
        assert bottom in stack
        assert top in stack

    def test_contains_uses_identity_not_equality(self) -> None:
        """Two different instances of the same class are distinct."""
        stack = SceneStack()
        a = DummyScene("same_name")
        b = DummyScene("same_name")
        stack.push(a)
        assert a in stack
        assert b not in stack

    def test_contains_non_scene_returns_false(self) -> None:
        """Non-Scene objects should return False, not raise."""
        stack = SceneStack()
        stack.push(DummyScene())
        assert "not a scene" not in stack
        assert 42 not in stack

    def test_empty_stack_contains_nothing(self) -> None:
        stack = SceneStack()
        assert DummyScene() not in stack


# ---------------------------------------------------------------------------
# __iter__
# ---------------------------------------------------------------------------


class TestSceneStackIter:
    """SceneStack.__iter__() — bottom-to-top iteration."""

    def test_iter_empty_stack(self) -> None:
        stack = SceneStack()
        assert list(stack) == []

    def test_iter_single_scene(self) -> None:
        stack = SceneStack()
        scene = DummyScene()
        stack.push(scene)
        assert list(stack) == [scene]

    def test_iter_order_is_bottom_to_top(self) -> None:
        stack = SceneStack()
        a = DummyScene("a")
        b = DummyScene("b")
        c = DummyScene("c")
        stack.push(a)
        stack.push(b)
        stack.push(c)
        assert list(stack) == [a, b, c]

    def test_iter_is_snapshot(self) -> None:
        """Mutating the stack during iteration should not affect the iterator."""
        stack = SceneStack()
        a = DummyScene("a")
        b = DummyScene("b")
        stack.push(a)
        stack.push(b)
        result = []
        for scene in stack:
            result.append(scene)
            if len(result) == 1:
                stack.pop()  # mutate during iteration
        assert result == [a, b]

    def test_iter_supports_multiple_passes(self) -> None:
        stack = SceneStack()
        stack.push(DummyScene("a"))
        stack.push(DummyScene("b"))
        pass1 = list(stack)
        pass2 = list(stack)
        assert pass1 == pass2


# ---------------------------------------------------------------------------
# Callback-based pause/resume hooks
# ---------------------------------------------------------------------------


class TestScenePauseHooks:
    """Callback-based on_pause hooks via add_pause_hook / remove_pause_hook."""

    def test_pause_hook_fires_on_push(self) -> None:
        """Pushing a new scene pauses the old top, firing pause hooks."""
        stack = SceneStack()
        bottom = DummyScene("bottom")
        log: list[str] = []
        bottom.add_pause_hook(lambda: log.append("paused"))
        stack.push(bottom)
        stack.push(DummyScene("top"))
        assert "paused" in log

    def test_pause_hook_fires_after_on_pause(self) -> None:
        """Registered callbacks fire after the overridden on_pause."""
        stack = SceneStack()
        scene = DummyScene()
        order: list[str] = []
        original_on_pause = scene.on_pause

        def tracking_on_pause() -> None:
            original_on_pause()
            order.append("on_pause")

        scene.on_pause = tracking_on_pause  # type: ignore[assignment]
        scene.add_pause_hook(lambda: order.append("hook"))
        stack.push(scene)
        stack.push(DummyScene("overlay"))
        assert order == ["on_pause", "hook"]

    def test_multiple_pause_hooks_fire_in_order(self) -> None:
        stack = SceneStack()
        scene = DummyScene()
        log: list[int] = []
        scene.add_pause_hook(lambda: log.append(1))
        scene.add_pause_hook(lambda: log.append(2))
        scene.add_pause_hook(lambda: log.append(3))
        stack.push(scene)
        stack.push(DummyScene("overlay"))
        assert log == [1, 2, 3]

    def test_remove_pause_hook(self) -> None:
        scene = DummyScene()
        log: list[str] = []
        cb = lambda: log.append("should_not_fire")  # noqa: E731
        scene.add_pause_hook(cb)
        scene.remove_pause_hook(cb)
        scene._fire_pause()
        assert "should_not_fire" not in log

    def test_remove_pause_hook_not_registered_raises(self) -> None:
        scene = DummyScene()
        with pytest.raises(ValueError):
            scene.remove_pause_hook(lambda: None)

    def test_add_pause_hook_rejects_non_callable(self) -> None:
        scene = DummyScene()
        with pytest.raises(TypeError, match="callback must be callable"):
            scene.add_pause_hook(42)  # type: ignore[arg-type]

    def test_same_callback_registered_twice(self) -> None:
        """Same callback registered twice fires twice."""
        scene = DummyScene()
        count: list[int] = []
        cb = lambda: count.append(1)  # noqa: E731
        scene.add_pause_hook(cb)
        scene.add_pause_hook(cb)
        scene._fire_pause()
        assert len(count) == 2

    def test_remove_only_removes_first_registration(self) -> None:
        scene = DummyScene()
        count: list[int] = []
        cb = lambda: count.append(1)  # noqa: E731
        scene.add_pause_hook(cb)
        scene.add_pause_hook(cb)
        scene.remove_pause_hook(cb)
        scene._fire_pause()
        assert len(count) == 1


class TestSceneResumeHooks:
    """Callback-based on_resume hooks via add_resume_hook / remove_resume_hook."""

    def test_resume_hook_fires_on_pop(self) -> None:
        """Popping the top scene resumes the one below, firing resume hooks."""
        stack = SceneStack()
        bottom = DummyScene("bottom")
        log: list[str] = []
        bottom.add_resume_hook(lambda: log.append("resumed"))
        stack.push(bottom)
        stack.push(DummyScene("top"))
        stack.pop()
        assert "resumed" in log

    def test_resume_hook_fires_after_on_resume(self) -> None:
        """Registered callbacks fire after the overridden on_resume."""
        scene = DummyScene()
        order: list[str] = []
        original_on_resume = scene.on_resume

        def tracking_on_resume() -> None:
            original_on_resume()
            order.append("on_resume")

        scene.on_resume = tracking_on_resume  # type: ignore[assignment]
        scene.add_resume_hook(lambda: order.append("hook"))
        scene._fire_resume()
        assert order == ["on_resume", "hook"]

    def test_multiple_resume_hooks_fire_in_order(self) -> None:
        stack = SceneStack()
        bottom = DummyScene("bottom")
        log: list[int] = []
        bottom.add_resume_hook(lambda: log.append(1))
        bottom.add_resume_hook(lambda: log.append(2))
        bottom.add_resume_hook(lambda: log.append(3))
        stack.push(bottom)
        stack.push(DummyScene("top"))
        stack.pop()
        assert log == [1, 2, 3]

    def test_remove_resume_hook(self) -> None:
        scene = DummyScene()
        log: list[str] = []
        cb = lambda: log.append("should_not_fire")  # noqa: E731
        scene.add_resume_hook(cb)
        scene.remove_resume_hook(cb)
        scene._fire_resume()
        assert "should_not_fire" not in log

    def test_remove_resume_hook_not_registered_raises(self) -> None:
        scene = DummyScene()
        with pytest.raises(ValueError):
            scene.remove_resume_hook(lambda: None)

    def test_add_resume_hook_rejects_non_callable(self) -> None:
        scene = DummyScene()
        with pytest.raises(TypeError, match="callback must be callable"):
            scene.add_resume_hook("not callable")  # type: ignore[arg-type]

    def test_same_callback_registered_twice(self) -> None:
        scene = DummyScene()
        count: list[int] = []
        cb = lambda: count.append(1)  # noqa: E731
        scene.add_resume_hook(cb)
        scene.add_resume_hook(cb)
        scene._fire_resume()
        assert len(count) == 2

    def test_remove_only_removes_first_registration(self) -> None:
        scene = DummyScene()
        count: list[int] = []
        cb = lambda: count.append(1)  # noqa: E731
        scene.add_resume_hook(cb)
        scene.add_resume_hook(cb)
        scene.remove_resume_hook(cb)
        scene._fire_resume()
        assert len(count) == 1


class TestScenePauseResumeHooksWithoutSuperInit:
    """Pause/resume hooks should work even if subclass skips super().__init__()."""

    def test_pause_hook_works_without_super_init(self) -> None:
        class NoSuperScene(Scene):
            def __init__(self) -> None:
                pass

            def update(self, dt: float) -> None:
                pass

            def render(self) -> None:
                pass

        scene = NoSuperScene()
        log: list[str] = []
        scene.add_pause_hook(lambda: log.append("paused"))
        scene._fire_pause()
        assert log == ["paused"]

    def test_resume_hook_works_without_super_init(self) -> None:
        class NoSuperScene(Scene):
            def __init__(self) -> None:
                pass

            def update(self, dt: float) -> None:
                pass

            def render(self) -> None:
                pass

        scene = NoSuperScene()
        log: list[str] = []
        scene.add_resume_hook(lambda: log.append("resumed"))
        scene._fire_resume()
        assert log == ["resumed"]

    def test_fire_pause_without_hooks_is_safe(self) -> None:
        class NoSuperScene(Scene):
            def __init__(self) -> None:
                pass

            def update(self, dt: float) -> None:
                pass

            def render(self) -> None:
                pass

        scene = NoSuperScene()
        scene._fire_pause()  # Should not raise

    def test_fire_resume_without_hooks_is_safe(self) -> None:
        class NoSuperScene(Scene):
            def __init__(self) -> None:
                pass

            def update(self, dt: float) -> None:
                pass

            def render(self) -> None:
                pass

        scene = NoSuperScene()
        scene._fire_resume()  # Should not raise


# ---------------------------------------------------------------------------
# Menu/pause workflow integration
# ---------------------------------------------------------------------------


class TestMenuPauseWorkflow:
    """Integration tests for the menu/pause scene stack pattern.

    These tests verify the common workflow of pushing a pause menu
    or overlay scene on top of a gameplay scene, and popping it to
    resume gameplay.
    """

    def test_push_pause_menu_pauses_gameplay(self) -> None:
        """Pushing a pause menu triggers on_pause on the gameplay scene."""
        stack = SceneStack()
        gameplay = DummyScene("gameplay")
        pause_menu = DummyScene("pause")
        stack.push(gameplay)
        gameplay.calls.clear()
        stack.push(pause_menu)
        assert "on_pause" in gameplay.calls
        assert "on_enter" in pause_menu.calls

    def test_pop_pause_menu_resumes_gameplay(self) -> None:
        """Popping the pause menu triggers on_resume on the gameplay scene."""
        stack = SceneStack()
        gameplay = DummyScene("gameplay")
        pause_menu = DummyScene("pause")
        stack.push(gameplay)
        stack.push(pause_menu)
        gameplay.calls.clear()
        stack.pop()
        assert "on_resume" in gameplay.calls

    def test_gameplay_visible_behind_pause_when_flagged(self) -> None:
        """A gameplay scene with renders_when_paused=True renders behind
        a pause overlay."""
        stack = SceneStack()
        gameplay = DummyScene("gameplay")
        gameplay.renders_when_paused = True
        pause_menu = DummyScene("pause")
        stack.push(gameplay)
        stack.push(pause_menu)
        renderable = stack.scenes_to_render()
        assert renderable == [gameplay, pause_menu]

    def test_gameplay_frozen_behind_pause_by_default(self) -> None:
        """By default, a gameplay scene does not update or render when
        a pause menu is on top."""
        stack = SceneStack()
        gameplay = DummyScene("gameplay")
        pause_menu = DummyScene("pause")
        stack.push(gameplay)
        stack.push(pause_menu)
        assert gameplay not in stack.scenes_to_update()
        assert gameplay not in stack.scenes_to_render()

    def test_prevent_double_push_with_contains(self) -> None:
        """Use __contains__ to prevent pushing the same pause menu twice."""
        stack = SceneStack()
        gameplay = DummyScene("gameplay")
        pause_menu = DummyScene("pause")
        stack.push(gameplay)
        stack.push(pause_menu)
        # Simulate pressing pause again — should not push a second time.
        if pause_menu not in stack:
            stack.push(pause_menu)
        assert len(stack) == 2  # Still just 2 scenes

    def test_full_pause_resume_lifecycle(self) -> None:
        """Full lifecycle: gameplay -> push pause -> pop pause -> gameplay."""
        call_log: list[str] = []

        class TrackedScene(Scene):
            def __init__(self, name: str) -> None:
                super().__init__()
                self._name = name

            def update(self, dt: float) -> None:
                call_log.append(f"{self._name}.update")

            def render(self) -> None:
                call_log.append(f"{self._name}.render")

            def on_enter(self) -> None:
                call_log.append(f"{self._name}.on_enter")

            def on_exit(self) -> None:
                call_log.append(f"{self._name}.on_exit")

            def on_pause(self) -> None:
                call_log.append(f"{self._name}.on_pause")

            def on_resume(self) -> None:
                call_log.append(f"{self._name}.on_resume")

        gameplay = TrackedScene("gameplay")
        pause_menu = TrackedScene("pause")

        stack = SceneStack()
        stack.push(gameplay)
        assert call_log == ["gameplay.on_enter"]
        call_log.clear()

        # Push pause menu
        stack.push(pause_menu)
        assert call_log == ["gameplay.on_pause", "pause.on_enter"]
        call_log.clear()

        # Only pause menu updates/renders
        assert stack.scenes_to_update() == [pause_menu]
        assert stack.scenes_to_render() == [pause_menu]

        # Pop pause menu — gameplay resumes
        stack.pop()
        assert call_log == ["pause.on_exit", "gameplay.on_resume"]
        call_log.clear()

        # Gameplay is active again
        assert stack.peek() is gameplay
        assert stack.scenes_to_update() == [gameplay]

    def test_pause_resume_hooks_in_workflow(self) -> None:
        """Pause/resume callback hooks fire during menu push/pop."""
        stack = SceneStack()
        gameplay = DummyScene("gameplay")
        log: list[str] = []
        gameplay.add_pause_hook(lambda: log.append("music_paused"))
        gameplay.add_resume_hook(lambda: log.append("music_resumed"))
        stack.push(gameplay)
        stack.push(DummyScene("pause_menu"))
        assert log == ["music_paused"]
        stack.pop()
        assert log == ["music_paused", "music_resumed"]


# ---------------------------------------------------------------------------
# SceneStack.dispatch_events — input routing to top scene
# ---------------------------------------------------------------------------


class TestDispatchEvents:
    """SceneStack.dispatch_events routes input to the top scene only."""

    def test_delivers_events_to_top_scene(self) -> None:
        """Events are passed to the top scene's handle_events."""
        stack = SceneStack()
        received: list[list[Event]] = []

        class EventScene(Scene):
            def handle_events(self, events: list[Event]) -> None:
                received.append(list(events))

            def update(self, dt: float) -> None:
                pass

            def render(self) -> None:
                pass

        stack.push(EventScene())
        evt1, evt2 = Event(), Event()
        result = stack.dispatch_events([evt1, evt2])

        assert result is True
        assert len(received) == 1
        assert received[0] == [evt1, evt2]

    def test_returns_false_on_empty_stack(self) -> None:
        """dispatch_events returns False when the stack is empty."""
        stack = SceneStack()
        result = stack.dispatch_events([Event()])
        assert result is False

    def test_returns_true_with_scene(self) -> None:
        """dispatch_events returns True when a scene receives events."""
        stack = SceneStack()
        stack.push(DummyScene())
        result = stack.dispatch_events([])
        assert result is True

    def test_empty_events_still_delivered(self) -> None:
        """An empty event list is still passed to handle_events."""
        stack = SceneStack()
        received: list[list[Event]] = []

        class EventScene(Scene):
            def handle_events(self, events: list[Event]) -> None:
                received.append(list(events))

            def update(self, dt: float) -> None:
                pass

            def render(self) -> None:
                pass

        stack.push(EventScene())
        stack.dispatch_events([])

        assert len(received) == 1
        assert received[0] == []

    def test_only_top_scene_receives_events(self) -> None:
        """Paused scenes below the top do not receive events."""
        stack = SceneStack()
        bottom_events: list[list[Event]] = []
        top_events: list[list[Event]] = []

        class BottomScene(Scene):
            def handle_events(self, events: list[Event]) -> None:
                bottom_events.append(list(events))

            def update(self, dt: float) -> None:
                pass

            def render(self) -> None:
                pass

        class TopScene(Scene):
            def handle_events(self, events: list[Event]) -> None:
                top_events.append(list(events))

            def update(self, dt: float) -> None:
                pass

            def render(self) -> None:
                pass

        stack.push(BottomScene())
        stack.push(TopScene())
        evt = Event()
        stack.dispatch_events([evt])

        assert len(top_events) == 1
        assert top_events[0] == [evt]
        assert len(bottom_events) == 0

    def test_paused_scene_with_updates_when_paused_does_not_receive_events(
        self,
    ) -> None:
        """A scene that updates when paused still does not receive events."""
        stack = SceneStack()
        bottom_events: list[list[Event]] = []

        class UpdatingBottomScene(Scene):
            def __init__(self) -> None:
                super().__init__()
                self.updates_when_paused = True

            def handle_events(self, events: list[Event]) -> None:
                bottom_events.append(list(events))

            def update(self, dt: float) -> None:
                pass

            def render(self) -> None:
                pass

        stack.push(UpdatingBottomScene())
        stack.push(DummyScene("top"))
        stack.dispatch_events([Event()])

        assert len(bottom_events) == 0

    def test_events_discarded_on_empty_stack_logged(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Discarded events on empty stack are logged at DEBUG level."""
        stack = SceneStack()
        with caplog.at_level(logging.DEBUG, logger="wyby.scene"):
            stack.dispatch_events([Event(), Event()])

        assert any("discarding 2 event(s)" in r.message for r in caplog.records)

    def test_no_log_when_empty_stack_and_no_events(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """No discard log when stack is empty and events list is also empty."""
        stack = SceneStack()
        with caplog.at_level(logging.DEBUG, logger="wyby.scene"):
            stack.dispatch_events([])

        assert not any("discarding" in r.message for r in caplog.records)

    def test_exception_in_handle_events_propagates(self) -> None:
        """If handle_events raises, the exception propagates through dispatch."""
        stack = SceneStack()

        class CrashingScene(Scene):
            def handle_events(self, events: list[Event]) -> None:
                raise ValueError("boom")

            def update(self, dt: float) -> None:
                pass

            def render(self) -> None:
                pass

        stack.push(CrashingScene())
        with pytest.raises(ValueError, match="boom"):
            stack.dispatch_events([Event()])

    def test_dispatch_after_pop_routes_to_new_top(self) -> None:
        """After popping, dispatch routes to the new top scene."""
        stack = SceneStack()
        bottom_events: list[list[Event]] = []
        top_events: list[list[Event]] = []

        class BottomScene(Scene):
            def handle_events(self, events: list[Event]) -> None:
                bottom_events.append(list(events))

            def update(self, dt: float) -> None:
                pass

            def render(self) -> None:
                pass

        class TopScene(Scene):
            def handle_events(self, events: list[Event]) -> None:
                top_events.append(list(events))

            def update(self, dt: float) -> None:
                pass

            def render(self) -> None:
                pass

        stack.push(BottomScene())
        stack.push(TopScene())
        stack.pop()  # TopScene exits, BottomScene resumes

        evt = Event()
        stack.dispatch_events([evt])

        assert len(bottom_events) == 1
        assert bottom_events[0] == [evt]
        assert len(top_events) == 0

    def test_dispatch_after_replace_routes_to_new_scene(self) -> None:
        """After replace, dispatch routes to the replacement scene."""
        stack = SceneStack()
        old_events: list[list[Event]] = []
        new_events: list[list[Event]] = []

        class OldScene(Scene):
            def handle_events(self, events: list[Event]) -> None:
                old_events.append(list(events))

            def update(self, dt: float) -> None:
                pass

            def render(self) -> None:
                pass

        class NewScene(Scene):
            def handle_events(self, events: list[Event]) -> None:
                new_events.append(list(events))

            def update(self, dt: float) -> None:
                pass

            def render(self) -> None:
                pass

        stack.push(OldScene())
        stack.replace(NewScene())

        evt = Event()
        stack.dispatch_events([evt])

        assert len(new_events) == 1
        assert new_events[0] == [evt]
        assert len(old_events) == 0


# ---------------------------------------------------------------------------
# Scene.on_resize — per-scene resize callback
# ---------------------------------------------------------------------------


class TestSceneOnResize:
    """Scene.on_resize is a no-op by default and can be overridden."""

    def test_default_on_resize_is_noop(self) -> None:
        """The base on_resize does nothing and does not raise."""
        scene = DummyScene()
        scene.on_resize(120, 40)  # Should not raise.

    def test_override_on_resize_receives_dimensions(self) -> None:
        """A subclass can override on_resize to receive (columns, rows)."""
        received: list[tuple[int, int]] = []

        class ResizeScene(Scene):
            def on_resize(self, columns: int, rows: int) -> None:
                received.append((columns, rows))

            def update(self, dt: float) -> None:
                pass

            def render(self) -> None:
                pass

        scene = ResizeScene()
        scene.on_resize(100, 50)
        assert received == [(100, 50)]

    def test_fire_resize_calls_on_resize(self) -> None:
        """_fire_resize invokes on_resize with the given dimensions."""
        received: list[tuple[int, int]] = []

        class ResizeScene(Scene):
            def on_resize(self, columns: int, rows: int) -> None:
                received.append((columns, rows))

            def update(self, dt: float) -> None:
                pass

            def render(self) -> None:
                pass

        scene = ResizeScene()
        scene._fire_resize(80, 24)
        assert received == [(80, 24)]

    def test_fire_resize_calls_hooks_after_on_resize(self) -> None:
        """_fire_resize invokes registered hooks after on_resize."""
        order: list[str] = []

        class ResizeScene(Scene):
            def on_resize(self, columns: int, rows: int) -> None:
                order.append("on_resize")

            def update(self, dt: float) -> None:
                pass

            def render(self) -> None:
                pass

        scene = ResizeScene()
        scene.add_resize_hook(lambda c, r: order.append("hook"))
        scene._fire_resize(80, 24)
        assert order == ["on_resize", "hook"]


# ---------------------------------------------------------------------------
# Scene resize callback hooks (add_resize_hook / remove_resize_hook)
# ---------------------------------------------------------------------------


class TestSceneResizeHooks:
    """Callback-based resize hooks follow the same pattern as other hooks."""

    def test_add_resize_hook_receives_dimensions(self) -> None:
        """Resize hooks receive (columns, rows)."""
        scene = DummyScene()
        received: list[tuple[int, int]] = []
        scene.add_resize_hook(lambda c, r: received.append((c, r)))
        scene._fire_resize(120, 40)
        assert received == [(120, 40)]

    def test_multiple_resize_hooks_fire_in_order(self) -> None:
        scene = DummyScene()
        order: list[int] = []
        scene.add_resize_hook(lambda c, r: order.append(1))
        scene.add_resize_hook(lambda c, r: order.append(2))
        scene.add_resize_hook(lambda c, r: order.append(3))
        scene._fire_resize(80, 24)
        assert order == [1, 2, 3]

    def test_remove_resize_hook(self) -> None:
        scene = DummyScene()
        called = []
        cb = lambda c, r: called.append(True)  # noqa: E731
        scene.add_resize_hook(cb)
        scene.remove_resize_hook(cb)
        scene._fire_resize(80, 24)
        assert called == []

    def test_remove_resize_hook_not_registered_raises(self) -> None:
        scene = DummyScene()
        with pytest.raises(ValueError):
            scene.remove_resize_hook(lambda c, r: None)

    def test_add_resize_hook_rejects_non_callable(self) -> None:
        scene = DummyScene()
        with pytest.raises(TypeError, match="callback must be callable"):
            scene.add_resize_hook(42)  # type: ignore[arg-type]

    def test_same_callback_registered_twice(self) -> None:
        """The same callback can be registered twice and fires twice."""
        scene = DummyScene()
        count: list[int] = []
        cb = lambda c, r: count.append(1)  # noqa: E731
        scene.add_resize_hook(cb)
        scene.add_resize_hook(cb)
        scene._fire_resize(80, 24)
        assert len(count) == 2


# ---------------------------------------------------------------------------
# Scene resize hooks without super().__init__() (lazy init)
# ---------------------------------------------------------------------------


class TestSceneResizeHooksWithoutSuperInit:
    """Resize hooks work even if the subclass doesn't call super().__init__()."""

    def test_resize_hook_works_without_super_init(self) -> None:
        class NoSuperScene(Scene):
            def __init__(self) -> None:
                # Deliberately NOT calling super().__init__()
                pass

            def update(self, dt: float) -> None:
                pass

            def render(self) -> None:
                pass

        scene = NoSuperScene()
        received: list[tuple[int, int]] = []
        scene.add_resize_hook(lambda c, r: received.append((c, r)))
        scene._fire_resize(100, 50)
        assert received == [(100, 50)]

    def test_fire_resize_without_hooks_is_safe(self) -> None:
        """_fire_resize on a scene with no hooks list doesn't crash."""

        class NoSuperScene(Scene):
            def __init__(self) -> None:
                pass

            def update(self, dt: float) -> None:
                pass

            def render(self) -> None:
                pass

        scene = NoSuperScene()
        scene._fire_resize(80, 24)  # Should not raise.


# ---------------------------------------------------------------------------
# SceneStack.dispatch_resize — resize routing to all scenes
# ---------------------------------------------------------------------------


class TestDispatchResize:
    """SceneStack.dispatch_resize notifies all scenes on the stack."""

    def test_notifies_all_scenes(self) -> None:
        """All scenes on the stack receive on_resize, not just the top."""
        stack = SceneStack()
        resizes: dict[str, list[tuple[int, int]]] = {"bottom": [], "top": []}

        class BottomScene(Scene):
            def on_resize(self, columns: int, rows: int) -> None:
                resizes["bottom"].append((columns, rows))

            def update(self, dt: float) -> None:
                pass

            def render(self) -> None:
                pass

        class TopScene(Scene):
            def on_resize(self, columns: int, rows: int) -> None:
                resizes["top"].append((columns, rows))

            def update(self, dt: float) -> None:
                pass

            def render(self) -> None:
                pass

        stack.push(BottomScene())
        stack.push(TopScene())
        result = stack.dispatch_resize(120, 40)

        assert result is True
        assert resizes["bottom"] == [(120, 40)]
        assert resizes["top"] == [(120, 40)]

    def test_returns_false_on_empty_stack(self) -> None:
        stack = SceneStack()
        result = stack.dispatch_resize(80, 24)
        assert result is False

    def test_returns_true_with_scenes(self) -> None:
        stack = SceneStack()
        stack.push(DummyScene())
        result = stack.dispatch_resize(80, 24)
        assert result is True

    def test_dispatch_order_is_bottom_to_top(self) -> None:
        """Resize is dispatched bottom-to-top, matching render order."""
        stack = SceneStack()
        order: list[str] = []

        class OrderScene(Scene):
            def __init__(self, name: str) -> None:
                super().__init__()
                self._name = name

            def on_resize(self, columns: int, rows: int) -> None:
                order.append(self._name)

            def update(self, dt: float) -> None:
                pass

            def render(self) -> None:
                pass

        stack.push(OrderScene("first"))
        stack.push(OrderScene("second"))
        stack.push(OrderScene("third"))
        stack.dispatch_resize(100, 50)

        assert order == ["first", "second", "third"]

    def test_single_scene_receives_resize(self) -> None:
        """A single scene on the stack receives the resize."""
        received: list[tuple[int, int]] = []

        class ResizeScene(Scene):
            def on_resize(self, columns: int, rows: int) -> None:
                received.append((columns, rows))

            def update(self, dt: float) -> None:
                pass

            def render(self) -> None:
                pass

        stack = SceneStack()
        stack.push(ResizeScene())
        stack.dispatch_resize(200, 60)

        assert received == [(200, 60)]

    def test_resize_hooks_also_fire(self) -> None:
        """Callback-based resize hooks fire during dispatch_resize."""
        stack = SceneStack()
        hook_received: list[tuple[int, int]] = []

        scene = DummyScene()
        scene.add_resize_hook(lambda c, r: hook_received.append((c, r)))
        stack.push(scene)
        stack.dispatch_resize(120, 40)

        assert hook_received == [(120, 40)]

    def test_stack_mutation_during_resize_uses_snapshot(self) -> None:
        """If a scene mutates the stack during on_resize, the snapshot
        ensures remaining scenes are still notified."""
        stack = SceneStack()
        notified: list[str] = []

        class MutatingScene(Scene):
            def on_resize(self, columns: int, rows: int) -> None:
                notified.append("mutating")
                # Push a new scene during resize dispatch
                stack.push(DummyScene("pushed_during_resize"))

            def update(self, dt: float) -> None:
                pass

            def render(self) -> None:
                pass

        class StableScene(Scene):
            def on_resize(self, columns: int, rows: int) -> None:
                notified.append("stable")

            def update(self, dt: float) -> None:
                pass

            def render(self) -> None:
                pass

        stack.push(MutatingScene())
        stack.push(StableScene())
        stack.dispatch_resize(80, 24)

        # Both original scenes should be notified despite the mutation.
        assert "mutating" in notified
        assert "stable" in notified

    def test_exception_in_on_resize_propagates(self) -> None:
        """If on_resize raises, the exception propagates."""
        stack = SceneStack()

        class CrashingScene(Scene):
            def on_resize(self, columns: int, rows: int) -> None:
                raise ValueError("resize boom")

            def update(self, dt: float) -> None:
                pass

            def render(self) -> None:
                pass

        stack.push(CrashingScene())
        with pytest.raises(ValueError, match="resize boom"):
            stack.dispatch_resize(80, 24)

    def test_empty_stack_logs_debug(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Dispatching resize to an empty stack logs a debug message."""
        stack = SceneStack()
        with caplog.at_level(logging.DEBUG, logger="wyby.scene"):
            stack.dispatch_resize(80, 24)

        assert any("stack empty" in r.message for r in caplog.records)

    def test_dispatch_logs_scene_count(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Dispatching resize logs the number of scenes notified."""
        stack = SceneStack()
        stack.push(DummyScene("a"))
        stack.push(DummyScene("b"))
        with caplog.at_level(logging.DEBUG, logger="wyby.scene"):
            stack.dispatch_resize(100, 50)

        assert any("2 scene(s)" in r.message for r in caplog.records)
