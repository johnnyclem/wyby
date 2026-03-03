"""Tests for wyby.animation — Animation frame list component."""

from __future__ import annotations

import pytest
from rich.style import Style

from wyby.animation import Animation, AnimationFrame
from wyby.component import Component
from wyby.entity import Entity
from wyby.sprite import Sprite


# ---------------------------------------------------------------------------
# AnimationFrame — Construction
# ---------------------------------------------------------------------------


class TestAnimationFrameConstruction:
    """AnimationFrame creation and defaults."""

    def test_basic_construction(self) -> None:
        f = AnimationFrame("/")
        assert f.char == "/"
        assert f.style is None
        assert f.duration == 0.1

    def test_custom_style(self) -> None:
        style = Style(color="red")
        f = AnimationFrame("#", style=style)
        assert f.style is style

    def test_custom_duration(self) -> None:
        f = AnimationFrame("X", duration=0.5)
        assert f.duration == 0.5

    def test_int_duration_accepted(self) -> None:
        f = AnimationFrame("X", duration=1)
        assert f.duration == 1

    def test_wide_char_accepted(self) -> None:
        f = AnimationFrame("\u4e16")  # 世
        assert f.char == "\u4e16"


# ---------------------------------------------------------------------------
# AnimationFrame — Validation
# ---------------------------------------------------------------------------


class TestAnimationFrameValidation:
    """AnimationFrame parameter validation."""

    def test_rejects_non_string_char(self) -> None:
        with pytest.raises(TypeError, match="char must be a string"):
            AnimationFrame(42)  # type: ignore[arg-type]

    def test_rejects_empty_char(self) -> None:
        with pytest.raises(ValueError, match="exactly one character"):
            AnimationFrame("")

    def test_rejects_multi_char(self) -> None:
        with pytest.raises(ValueError, match="exactly one character"):
            AnimationFrame("AB")

    def test_rejects_zero_width_char(self) -> None:
        with pytest.raises(ValueError, match="non-zero display width"):
            AnimationFrame("\u0300")  # combining grave accent

    def test_rejects_non_style(self) -> None:
        with pytest.raises(TypeError, match="rich.style.Style instance"):
            AnimationFrame("@", style="red")  # type: ignore[arg-type]

    def test_rejects_non_number_duration(self) -> None:
        with pytest.raises(TypeError, match="duration must be a number"):
            AnimationFrame("@", duration="fast")  # type: ignore[arg-type]

    def test_rejects_zero_duration(self) -> None:
        with pytest.raises(ValueError, match="duration must be positive"):
            AnimationFrame("@", duration=0)

    def test_rejects_negative_duration(self) -> None:
        with pytest.raises(ValueError, match="duration must be positive"):
            AnimationFrame("@", duration=-0.1)


# ---------------------------------------------------------------------------
# AnimationFrame — Repr and Equality
# ---------------------------------------------------------------------------


class TestAnimationFrameReprEquality:
    """AnimationFrame __repr__ and __eq__."""

    def test_repr(self) -> None:
        f = AnimationFrame("/", duration=0.2)
        assert repr(f) == "AnimationFrame(char='/', duration=0.2)"

    def test_equality_same(self) -> None:
        f1 = AnimationFrame("/", duration=0.1)
        f2 = AnimationFrame("/", duration=0.1)
        assert f1 == f2

    def test_equality_different_char(self) -> None:
        f1 = AnimationFrame("/")
        f2 = AnimationFrame("-")
        assert f1 != f2

    def test_equality_different_duration(self) -> None:
        f1 = AnimationFrame("/", duration=0.1)
        f2 = AnimationFrame("/", duration=0.2)
        assert f1 != f2

    def test_equality_different_style(self) -> None:
        f1 = AnimationFrame("/", style=Style(color="red"))
        f2 = AnimationFrame("/", style=Style(color="blue"))
        assert f1 != f2

    def test_equality_not_implemented_for_other_types(self) -> None:
        f = AnimationFrame("/")
        assert f != "not a frame"

    def test_slots(self) -> None:
        assert "__slots__" in AnimationFrame.__dict__
        assert "char" in AnimationFrame.__slots__
        assert "style" in AnimationFrame.__slots__
        assert "duration" in AnimationFrame.__slots__


# ---------------------------------------------------------------------------
# Animation — Construction
# ---------------------------------------------------------------------------


class TestAnimationConstruction:
    """Animation creation and defaults."""

    def test_basic_construction(self) -> None:
        frames = [AnimationFrame("/"), AnimationFrame("-")]
        anim = Animation(frames)
        assert anim.frame_count == 2
        assert anim.frame_index == 0
        assert anim.playing is True
        assert anim.loop is True

    def test_non_looping(self) -> None:
        frames = [AnimationFrame("/")]
        anim = Animation(frames, loop=False)
        assert anim.loop is False

    def test_is_component_subclass(self) -> None:
        frames = [AnimationFrame("/")]
        anim = Animation(frames)
        assert isinstance(anim, Component)

    def test_detached_by_default(self) -> None:
        frames = [AnimationFrame("/")]
        anim = Animation(frames)
        assert anim.entity is None

    def test_frames_are_copied(self) -> None:
        """The internal frame list is a shallow copy of the input."""
        frames = [AnimationFrame("/"), AnimationFrame("-")]
        anim = Animation(frames)
        frames.append(AnimationFrame("|"))
        assert anim.frame_count == 2  # Not affected by external mutation


# ---------------------------------------------------------------------------
# Animation — Validation
# ---------------------------------------------------------------------------


class TestAnimationValidation:
    """Animation constructor validation."""

    def test_rejects_non_list_frames(self) -> None:
        with pytest.raises(TypeError, match="frames must be a list"):
            Animation(("a",))  # type: ignore[arg-type]

    def test_rejects_empty_frames(self) -> None:
        with pytest.raises(ValueError, match="frames must not be empty"):
            Animation([])

    def test_rejects_non_animationframe_elements(self) -> None:
        with pytest.raises(TypeError, match="frames\\[1\\] must be an AnimationFrame"):
            Animation([AnimationFrame("/"), "bad"])  # type: ignore[list-item]


# ---------------------------------------------------------------------------
# Animation — Properties
# ---------------------------------------------------------------------------


class TestAnimationProperties:
    """Animation read-only properties."""

    def test_current_frame(self) -> None:
        f1 = AnimationFrame("/")
        f2 = AnimationFrame("-")
        anim = Animation([f1, f2])
        assert anim.current_frame is f1

    def test_elapsed_starts_at_zero(self) -> None:
        anim = Animation([AnimationFrame("/")])
        assert anim.elapsed == 0.0

    def test_total_duration(self) -> None:
        frames = [
            AnimationFrame("/", duration=0.1),
            AnimationFrame("-", duration=0.2),
            AnimationFrame("|", duration=0.3),
        ]
        anim = Animation(frames)
        assert anim.total_duration == pytest.approx(0.6)

    def test_finished_false_for_looping(self) -> None:
        anim = Animation([AnimationFrame("/")], loop=True)
        assert anim.finished is False

    def test_finished_false_at_start(self) -> None:
        anim = Animation([AnimationFrame("/")], loop=False)
        assert anim.finished is False

    def test_frames_returns_copy(self) -> None:
        f = AnimationFrame("/")
        anim = Animation([f])
        returned = anim.frames
        returned.append(AnimationFrame("-"))
        assert anim.frame_count == 1  # Internal list not affected

    def test_loop_setter(self) -> None:
        anim = Animation([AnimationFrame("/")])
        assert anim.loop is True
        anim.loop = False
        assert anim.loop is False


# ---------------------------------------------------------------------------
# Animation — Playback control
# ---------------------------------------------------------------------------


class TestAnimationPlayback:
    """Play, pause, and reset."""

    def test_pause_stops_advancing(self) -> None:
        frames = [AnimationFrame("/", duration=0.1), AnimationFrame("-", duration=0.1)]
        anim = Animation(frames)
        anim.pause()
        anim.update(0.2)
        assert anim.frame_index == 0  # Did not advance

    def test_play_resumes(self) -> None:
        frames = [AnimationFrame("/", duration=0.1), AnimationFrame("-", duration=0.1)]
        anim = Animation(frames)
        anim.pause()
        anim.play()
        anim.update(0.15)
        assert anim.frame_index == 1

    def test_reset_returns_to_start(self) -> None:
        frames = [AnimationFrame("/", duration=0.1), AnimationFrame("-", duration=0.1)]
        anim = Animation(frames)
        anim.update(0.15)
        assert anim.frame_index == 1
        anim.reset()
        assert anim.frame_index == 0
        assert anim.elapsed == 0.0
        assert anim.playing is True


# ---------------------------------------------------------------------------
# Animation — update() frame advancement
# ---------------------------------------------------------------------------


class TestAnimationUpdate:
    """Animation.update() advances frames correctly."""

    def test_stays_on_first_frame_within_duration(self) -> None:
        frames = [AnimationFrame("/", duration=0.1), AnimationFrame("-", duration=0.1)]
        anim = Animation(frames)
        anim.update(0.05)
        assert anim.frame_index == 0

    def test_advances_to_next_frame(self) -> None:
        frames = [AnimationFrame("/", duration=0.1), AnimationFrame("-", duration=0.1)]
        anim = Animation(frames)
        anim.update(0.15)
        assert anim.frame_index == 1

    def test_loops_back_to_start(self) -> None:
        frames = [AnimationFrame("/", duration=0.1), AnimationFrame("-", duration=0.1)]
        anim = Animation(frames, loop=True)
        anim.update(0.25)  # Past both frames
        assert anim.frame_index == 0

    def test_non_loop_stops_on_last_frame(self) -> None:
        frames = [AnimationFrame("/", duration=0.1), AnimationFrame("-", duration=0.1)]
        anim = Animation(frames, loop=False)
        anim.update(0.25)
        assert anim.frame_index == 1
        assert anim.finished is True

    def test_finished_animation_does_not_advance(self) -> None:
        frames = [AnimationFrame("/", duration=0.1)]
        anim = Animation(frames, loop=False)
        anim.update(0.2)
        assert anim.finished is True
        # Further updates do nothing.
        anim.update(1.0)
        assert anim.frame_index == 0
        assert anim.finished is True

    def test_large_dt_skips_multiple_frames(self) -> None:
        frames = [
            AnimationFrame("1", duration=0.1),
            AnimationFrame("2", duration=0.1),
            AnimationFrame("3", duration=0.1),
            AnimationFrame("4", duration=0.1),
        ]
        anim = Animation(frames, loop=False)
        anim.update(0.35)  # Skips frames 1, 2, 3, lands on 4
        assert anim.frame_index == 3

    def test_single_frame_loops(self) -> None:
        """A single-frame looping animation stays on frame 0."""
        anim = Animation([AnimationFrame("/", duration=0.1)], loop=True)
        anim.update(1.0)
        assert anim.frame_index == 0

    def test_variable_duration_frames(self) -> None:
        frames = [
            AnimationFrame("a", duration=0.05),
            AnimationFrame("b", duration=0.2),
            AnimationFrame("c", duration=0.05),
        ]
        anim = Animation(frames, loop=False)
        # After 0.06s: past frame 0 (0.05), into frame 1
        anim.update(0.06)
        assert anim.frame_index == 1
        # After another 0.1s: still in frame 1 (needs 0.2 total)
        anim.update(0.1)
        assert anim.frame_index == 1
        # After another 0.15s: past frame 1, into frame 2
        anim.update(0.15)
        assert anim.frame_index == 2


# ---------------------------------------------------------------------------
# Animation — Sprite integration
# ---------------------------------------------------------------------------


class TestAnimationSpriteIntegration:
    """Animation updates the entity's Sprite."""

    def test_updates_sprite_char(self) -> None:
        e = Entity(entity_id=1)
        e.add_component(Sprite("@"))

        frames = [AnimationFrame("/", duration=0.1), AnimationFrame("-", duration=0.1)]
        anim = Animation(frames)
        e.add_component(anim)

        # Initial frame applied on first update.
        anim.update(0.0)
        assert e.get_component(Sprite).char == "/"

        anim.update(0.15)
        assert e.get_component(Sprite).char == "-"

    def test_updates_sprite_style(self) -> None:
        e = Entity(entity_id=1)
        e.add_component(Sprite("@"))

        red = Style(color="red")
        blue = Style(color="blue")
        frames = [
            AnimationFrame("@", style=red, duration=0.1),
            AnimationFrame("@", style=blue, duration=0.1),
        ]
        anim = Animation(frames)
        e.add_component(anim)

        anim.update(0.0)
        assert e.get_component(Sprite).style == red

        anim.update(0.15)
        assert e.get_component(Sprite).style == blue

    def test_none_style_preserves_existing(self) -> None:
        """When frame.style is None, the Sprite's style is not changed."""
        original_style = Style(color="green")
        e = Entity(entity_id=1)
        e.add_component(Sprite("@", original_style))

        frames = [AnimationFrame("/", style=None, duration=0.1)]
        anim = Animation(frames)
        e.add_component(anim)

        anim.update(0.0)
        assert e.get_component(Sprite).char == "/"
        assert e.get_component(Sprite).style is original_style

    def test_no_sprite_does_not_crash(self) -> None:
        """If entity has no Sprite, update still advances time."""
        e = Entity(entity_id=1)
        frames = [AnimationFrame("/", duration=0.1), AnimationFrame("-", duration=0.1)]
        anim = Animation(frames)
        e.add_component(anim)

        anim.update(0.15)  # Should not raise
        assert anim.frame_index == 1

    def test_detached_does_not_crash(self) -> None:
        """An animation not attached to an entity can still update."""
        frames = [AnimationFrame("/", duration=0.1), AnimationFrame("-", duration=0.1)]
        anim = Animation(frames)

        anim.update(0.15)  # Should not raise
        assert anim.frame_index == 1

    def test_entity_integration_attach_detach(self) -> None:
        e = Entity(entity_id=42)
        frames = [AnimationFrame("/")]
        anim = Animation(frames)
        e.add_component(anim)
        assert anim.entity is e
        assert e.get_component(Animation) is anim

        e.remove_component(Animation)
        assert anim.entity is None


# ---------------------------------------------------------------------------
# Animation — set_frames
# ---------------------------------------------------------------------------


class TestAnimationSetFrames:
    """Replacing the frame sequence at runtime."""

    def test_set_frames_replaces_sequence(self) -> None:
        anim = Animation([AnimationFrame("/")])
        anim.set_frames([AnimationFrame("-"), AnimationFrame("|")])
        assert anim.frame_count == 2
        assert anim.current_frame.char == "-"

    def test_set_frames_resets_playback(self) -> None:
        frames = [AnimationFrame("/", duration=0.1), AnimationFrame("-", duration=0.1)]
        anim = Animation(frames)
        anim.update(0.15)
        assert anim.frame_index == 1

        anim.set_frames([AnimationFrame("X"), AnimationFrame("Y")])
        assert anim.frame_index == 0
        assert anim.elapsed == 0.0

    def test_set_frames_validates(self) -> None:
        anim = Animation([AnimationFrame("/")])
        with pytest.raises(ValueError, match="frames must not be empty"):
            anim.set_frames([])
        with pytest.raises(TypeError, match="frames must be a list"):
            anim.set_frames(("a",))  # type: ignore[arg-type]
        with pytest.raises(TypeError, match="frames\\[0\\] must be an AnimationFrame"):
            anim.set_frames(["bad"])  # type: ignore[list-item]


# ---------------------------------------------------------------------------
# Animation — Repr
# ---------------------------------------------------------------------------


class TestAnimationRepr:
    """Animation __repr__ output."""

    def test_repr_detached(self) -> None:
        frames = [AnimationFrame("/"), AnimationFrame("-")]
        anim = Animation(frames)
        assert repr(anim) == "Animation(frames=2, frame_index=0, detached)"

    def test_repr_attached(self) -> None:
        e = Entity(entity_id=99)
        frames = [AnimationFrame("/")]
        anim = Animation(frames)
        e.add_component(anim)
        assert repr(anim) == "Animation(frames=1, frame_index=0, entity_id=99)"


# ---------------------------------------------------------------------------
# Animation — Slots
# ---------------------------------------------------------------------------


class TestAnimationSlots:
    """Animation uses __slots__ for memory efficiency."""

    def test_uses_slots(self) -> None:
        assert "__slots__" in Animation.__dict__
        assert "_frames" in Animation.__slots__
        assert "_elapsed" in Animation.__slots__
        assert "_frame_index" in Animation.__slots__
        assert "_playing" in Animation.__slots__
        assert "_loop" in Animation.__slots__


# ---------------------------------------------------------------------------
# Import from package root
# ---------------------------------------------------------------------------


class TestAnimationImport:
    """Animation and AnimationFrame are accessible from the wyby package root."""

    def test_import_animation(self) -> None:
        from wyby import Animation as A
        assert A is Animation

    def test_import_animation_frame(self) -> None:
        from wyby import AnimationFrame as AF
        assert AF is AnimationFrame
