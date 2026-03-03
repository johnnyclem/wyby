"""Tests for wyby.transition — scene transition stubs."""

from __future__ import annotations

import logging

import pytest

from wyby.scene import Scene
from wyby.transition import (
    Cut,
    FadeTransition,
    SlideTransition,
    Transition,
    _MAX_DURATION,
    _VALID_DIRECTIONS,
)


# ---------------------------------------------------------------------------
# Concrete Scene subclass for testing
# ---------------------------------------------------------------------------


class DummyScene(Scene):
    """Minimal concrete Scene for transition testing."""

    def __init__(self, name: str = "dummy") -> None:
        super().__init__()
        self.name = name

    def update(self, dt: float) -> None:
        pass

    def render(self) -> None:
        pass

    def __repr__(self) -> str:
        return f"DummyScene({self.name!r})"


# ---------------------------------------------------------------------------
# Transition ABC
# ---------------------------------------------------------------------------


class TestTransitionABC:
    """Transition is abstract and requires duration property."""

    def test_cannot_instantiate_directly(self) -> None:
        with pytest.raises(TypeError):
            Transition()  # type: ignore[abstract]

    def test_must_implement_duration(self) -> None:
        class NoDuration(Transition):
            pass

        with pytest.raises(TypeError):
            NoDuration()  # type: ignore[abstract]

    def test_concrete_subclass_works(self) -> None:
        class Minimal(Transition):
            @property
            def duration(self) -> float:
                return 0.0

        t = Minimal()
        assert t.duration == 0.0
        assert t.is_complete is True
        assert t.progress == 1.0


# ---------------------------------------------------------------------------
# Cut
# ---------------------------------------------------------------------------


class TestCut:
    """Cut is an instant transition with zero duration."""

    def test_duration_is_zero(self) -> None:
        t = Cut()
        assert t.duration == 0.0

    def test_is_complete_immediately(self) -> None:
        t = Cut()
        assert t.is_complete is True

    def test_progress_is_one(self) -> None:
        t = Cut()
        assert t.progress == 1.0

    def test_start_does_not_raise(self) -> None:
        t = Cut()
        out = DummyScene("out")
        inc = DummyScene("in")
        t.start(out, inc)  # should not raise

    def test_start_with_none_scenes(self) -> None:
        t = Cut()
        t.start(None, DummyScene("in"))
        t.start(DummyScene("out"), None)
        t.start(None, None)

    def test_update_is_noop(self) -> None:
        t = Cut()
        t.start(DummyScene("out"), DummyScene("in"))
        t.update(1 / 30)  # should not raise
        assert t.is_complete is True

    def test_render_is_noop(self) -> None:
        t = Cut()
        t.start(DummyScene("out"), DummyScene("in"))
        t.render()  # should not raise

    def test_repr(self) -> None:
        t = Cut()
        assert "Cut" in repr(t)
        assert "0.0" in repr(t)


# ---------------------------------------------------------------------------
# FadeTransition
# ---------------------------------------------------------------------------


class TestFadeTransition:
    """FadeTransition stores duration but behaves as a stub."""

    def test_default_duration(self) -> None:
        t = FadeTransition()
        assert t.duration == 0.5

    def test_custom_duration(self) -> None:
        t = FadeTransition(duration=2.0)
        assert t.duration == 2.0

    def test_int_duration_accepted(self) -> None:
        t = FadeTransition(duration=1)
        assert t.duration == 1.0
        assert isinstance(t.duration, float)

    def test_zero_duration(self) -> None:
        t = FadeTransition(duration=0.0)
        assert t.duration == 0.0

    def test_max_duration(self) -> None:
        t = FadeTransition(duration=_MAX_DURATION)
        assert t.duration == _MAX_DURATION

    def test_negative_duration_rejected(self) -> None:
        with pytest.raises(ValueError, match="duration must be between"):
            FadeTransition(duration=-0.1)

    def test_excessive_duration_rejected(self) -> None:
        with pytest.raises(ValueError, match="duration must be between"):
            FadeTransition(duration=_MAX_DURATION + 0.1)

    def test_string_duration_rejected(self) -> None:
        with pytest.raises(TypeError, match="duration must be a number"):
            FadeTransition(duration="fast")  # type: ignore[arg-type]

    def test_none_duration_rejected(self) -> None:
        with pytest.raises(TypeError, match="duration must be a number"):
            FadeTransition(duration=None)  # type: ignore[arg-type]

    def test_bool_duration_rejected(self) -> None:
        with pytest.raises(TypeError, match="duration must be a number"):
            FadeTransition(duration=True)  # type: ignore[arg-type]

    def test_is_complete_immediately(self) -> None:
        t = FadeTransition(duration=2.0)
        assert t.is_complete is True

    def test_progress_is_one(self) -> None:
        t = FadeTransition(duration=2.0)
        assert t.progress == 1.0

    def test_start_does_not_raise(self) -> None:
        t = FadeTransition()
        t.start(DummyScene("out"), DummyScene("in"))

    def test_update_is_noop(self) -> None:
        t = FadeTransition()
        t.start(DummyScene("out"), DummyScene("in"))
        t.update(1 / 30)
        assert t.is_complete is True
        assert t.progress == 1.0

    def test_render_is_noop(self) -> None:
        t = FadeTransition()
        t.render()

    def test_repr(self) -> None:
        t = FadeTransition(duration=1.5)
        assert "FadeTransition" in repr(t)
        assert "1.5" in repr(t)


# ---------------------------------------------------------------------------
# SlideTransition
# ---------------------------------------------------------------------------


class TestSlideTransition:
    """SlideTransition stores direction and duration but behaves as a stub."""

    def test_default_direction_and_duration(self) -> None:
        t = SlideTransition()
        assert t.direction == "left"
        assert t.duration == 0.3

    def test_custom_direction(self) -> None:
        for d in _VALID_DIRECTIONS:
            t = SlideTransition(direction=d)
            assert t.direction == d

    def test_custom_duration(self) -> None:
        t = SlideTransition(duration=1.0)
        assert t.duration == 1.0

    def test_int_duration_accepted(self) -> None:
        t = SlideTransition(duration=2)
        assert t.duration == 2.0
        assert isinstance(t.duration, float)

    def test_invalid_direction_rejected(self) -> None:
        with pytest.raises(ValueError, match="direction must be one of"):
            SlideTransition(direction="diagonal")

    def test_non_string_direction_rejected(self) -> None:
        with pytest.raises(TypeError, match="direction must be a string"):
            SlideTransition(direction=42)  # type: ignore[arg-type]

    def test_negative_duration_rejected(self) -> None:
        with pytest.raises(ValueError, match="duration must be between"):
            SlideTransition(duration=-1.0)

    def test_excessive_duration_rejected(self) -> None:
        with pytest.raises(ValueError, match="duration must be between"):
            SlideTransition(duration=_MAX_DURATION + 1.0)

    def test_string_duration_rejected(self) -> None:
        with pytest.raises(TypeError, match="duration must be a number"):
            SlideTransition(duration="slow")  # type: ignore[arg-type]

    def test_bool_duration_rejected(self) -> None:
        with pytest.raises(TypeError, match="duration must be a number"):
            SlideTransition(duration=False)  # type: ignore[arg-type]

    def test_is_complete_immediately(self) -> None:
        t = SlideTransition(duration=2.0)
        assert t.is_complete is True

    def test_progress_is_one(self) -> None:
        t = SlideTransition(duration=2.0)
        assert t.progress == 1.0

    def test_start_does_not_raise(self) -> None:
        t = SlideTransition()
        t.start(DummyScene("out"), DummyScene("in"))

    def test_update_is_noop(self) -> None:
        t = SlideTransition()
        t.start(DummyScene("out"), DummyScene("in"))
        t.update(1 / 30)
        assert t.is_complete is True

    def test_render_is_noop(self) -> None:
        t = SlideTransition()
        t.render()

    def test_repr(self) -> None:
        t = SlideTransition(direction="right", duration=0.5)
        r = repr(t)
        assert "SlideTransition" in r
        assert "right" in r
        assert "0.5" in r


# ---------------------------------------------------------------------------
# Stub behaviour invariants (all transitions)
# ---------------------------------------------------------------------------


class TestStubBehaviour:
    """All v0.1 transitions share stub behaviour: instant completion."""

    @pytest.fixture(
        params=[
            Cut(),
            FadeTransition(),
            FadeTransition(duration=5.0),
            SlideTransition(),
            SlideTransition(direction="up", duration=3.0),
        ],
        ids=[
            "cut",
            "fade-default",
            "fade-5s",
            "slide-default",
            "slide-up-3s",
        ],
    )
    def transition(self, request: pytest.FixtureRequest) -> Transition:
        return request.param

    def test_is_complete_before_start(self, transition: Transition) -> None:
        assert transition.is_complete is True

    def test_is_complete_after_start(self, transition: Transition) -> None:
        transition.start(DummyScene("out"), DummyScene("in"))
        assert transition.is_complete is True

    def test_progress_always_one(self, transition: Transition) -> None:
        assert transition.progress == 1.0
        transition.start(DummyScene("out"), DummyScene("in"))
        transition.update(1 / 30)
        assert transition.progress == 1.0

    def test_update_does_not_change_state(self, transition: Transition) -> None:
        transition.start(DummyScene("out"), DummyScene("in"))
        for _ in range(100):
            transition.update(1 / 30)
        assert transition.is_complete is True

    def test_render_does_not_raise(self, transition: Transition) -> None:
        transition.start(DummyScene("out"), DummyScene("in"))
        transition.render()

    def test_duration_is_non_negative(self, transition: Transition) -> None:
        assert transition.duration >= 0.0


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------


class TestTransitionLogging:
    """Transition.start() logs debug messages."""

    def test_start_logs_scene_names(self, caplog: pytest.LogCaptureFixture) -> None:
        t = Cut()
        with caplog.at_level(logging.DEBUG, logger="wyby.transition"):
            t.start(DummyScene("out"), DummyScene("in"))
        assert any("Cut.start" in r.message for r in caplog.records)
        assert any("DummyScene" in r.message for r in caplog.records)

    def test_start_logs_none_scenes(self, caplog: pytest.LogCaptureFixture) -> None:
        t = FadeTransition()
        with caplog.at_level(logging.DEBUG, logger="wyby.transition"):
            t.start(None, None)
        assert any("None" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# Package-level imports
# ---------------------------------------------------------------------------


class TestPackageExports:
    """Transition classes are importable from the wyby package."""

    def test_import_transition(self) -> None:
        from wyby import Transition
        assert Transition is not None

    def test_import_cut(self) -> None:
        from wyby import Cut
        assert Cut is not None

    def test_import_fade(self) -> None:
        from wyby import FadeTransition
        assert FadeTransition is not None

    def test_import_slide(self) -> None:
        from wyby import SlideTransition
        assert SlideTransition is not None

    def test_exports_in_all(self) -> None:
        import wyby
        assert "Transition" in wyby.__all__
        assert "Cut" in wyby.__all__
        assert "FadeTransition" in wyby.__all__
        assert "SlideTransition" in wyby.__all__
