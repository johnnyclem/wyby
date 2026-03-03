"""Animation frame list component for sprite animation.

Provides :class:`AnimationFrame` (a single frame's visual state) and
:class:`Animation` (a :class:`~wyby.component.Component` that cycles
through a list of frames, updating the entity's :class:`~wyby.sprite.Sprite`
each tick).

Usage::

    from rich.style import Style
    from wyby.entity import Entity
    from wyby.sprite import Sprite
    from wyby.animation import Animation, AnimationFrame

    e = Entity(5, 3)
    e.add_component(Sprite("@"))

    frames = [
        AnimationFrame("/", duration=0.1),
        AnimationFrame("-", duration=0.1),
        AnimationFrame("\\\\", duration=0.1),
        AnimationFrame("|", duration=0.1),
    ]
    anim = Animation(frames, loop=True)
    e.add_component(anim)

    # In your game loop:
    anim.update(dt)  # Advances the animation and updates the Sprite

Caveats:
    - **Requires a Sprite component.**  The :class:`Animation` component
      updates the entity's :class:`~wyby.sprite.Sprite` char and style
      each tick.  If the entity does not have a Sprite when ``update``
      is called, the frame is advanced but no visual change occurs.
      Attach a Sprite before (or at the same time as) the Animation.
    - **Not called automatically.**  Like all wyby components, ``update(dt)``
      must be called explicitly by your scene or game loop.  The engine
      does not auto-update components.
    - **Per-frame durations.**  Each :class:`AnimationFrame` has its own
      ``duration``.  Frames with longer durations hold longer.  This
      allows variable-speed animations (e.g. a slow wind-up followed by
      a fast strike) without needing a separate timeline.
    - **Style is optional per frame.**  If a frame's ``style`` is ``None``,
      the Sprite's existing style is preserved for that frame — only the
      character changes.  This is useful when only the shape animates
      but the colour stays constant.
    - **One-shot animations stop on the last frame.**  When ``loop=False``,
      the animation plays through once and stops with :attr:`finished`
      set to ``True``.  The last frame remains visible.  Call
      :meth:`reset` to replay.
    - **Frame list is stored by reference.**  The ``frames`` list passed
      to the constructor is copied shallowly.  Mutating the original
      list after construction has no effect.  However, mutating
      individual :class:`AnimationFrame` objects *does* affect the
      animation since they are mutable.
    - **Thread safety.**  Animation state mutation is not thread-safe.
      The game loop is expected to be single-threaded.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from wyby.component import Component

if TYPE_CHECKING:
    from rich.style import Style

_logger = logging.getLogger(__name__)


class AnimationFrame:
    """A single frame in an animation sequence.

    Holds the visual state (character and optional style) and how long
    the frame should be displayed.

    Args:
        char: A single character string for this frame.
        style: Optional :class:`~rich.style.Style`.  If ``None``, the
            Sprite's current style is preserved when this frame is
            applied — only the character changes.
        duration: How long this frame is displayed, in seconds.
            Must be positive.  Defaults to ``0.1`` (100 ms).

    Raises:
        TypeError: If *char* is not a string.
        ValueError: If *char* is not exactly one character.
        ValueError: If *char* is a zero-width character.
        TypeError: If *style* is not a :class:`~rich.style.Style` or ``None``.
        TypeError: If *duration* is not a number.
        ValueError: If *duration* is not positive.

    Caveats:
        - **Mutable.**  All attributes can be changed after creation.
          Changes take effect on the next ``Animation.update`` call
          that lands on this frame.
        - **Duration precision.**  At 30 ticks/second the minimum
          distinguishable duration is ~33 ms.  Setting duration below
          the tick interval effectively makes the frame last one tick.
    """

    __slots__ = ("char", "style", "duration")

    def __init__(
        self,
        char: str,
        style: Style | None = None,
        duration: float = 0.1,
    ) -> None:
        # Validate char.
        if not isinstance(char, str):
            raise TypeError(
                f"char must be a string, got {type(char).__name__}"
            )
        if len(char) != 1:
            raise ValueError(
                f"char must be exactly one character, got {char!r} "
                f"(length {len(char)})"
            )
        from wyby.unicode import char_width as _char_width
        if _char_width(char) == 0:
            raise ValueError(
                f"char must have non-zero display width, got {char!r} "
                f"(a zero-width character cannot occupy a terminal cell)"
            )

        # Validate style.
        if style is not None:
            from rich.style import Style as _Style
            if not isinstance(style, _Style):
                raise TypeError(
                    f"style must be a rich.style.Style instance or None, "
                    f"got {type(style).__name__}"
                )

        # Validate duration.
        if not isinstance(duration, (int, float)):
            raise TypeError(
                f"duration must be a number, got {type(duration).__name__}"
            )
        if duration <= 0:
            raise ValueError(
                f"duration must be positive, got {duration}"
            )

        self.char = char
        self.style = style
        self.duration = duration

    def __repr__(self) -> str:
        return (
            f"AnimationFrame(char={self.char!r}, "
            f"duration={self.duration})"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, AnimationFrame):
            return NotImplemented
        return (
            self.char == other.char
            and self.style == other.style
            and self.duration == other.duration
        )


class Animation(Component):
    """Component that cycles through animation frames on an entity's Sprite.

    Each tick, :meth:`update` advances the internal clock and applies the
    current frame's character (and optionally style) to the entity's
    :class:`~wyby.sprite.Sprite` component.

    Args:
        frames: A non-empty list of :class:`AnimationFrame` instances.
            The list is copied shallowly.
        loop: If ``True`` (the default), the animation restarts from
            frame 0 after the last frame.  If ``False``, the animation
            plays once and stops on the last frame.

    Raises:
        TypeError: If *frames* is not a list.
        ValueError: If *frames* is empty.
        TypeError: If any element of *frames* is not an
            :class:`AnimationFrame`.

    Caveats:
        - **Requires a Sprite on the entity.**  If the entity has no
          Sprite when ``update`` is called, time still advances but
          no visual change occurs.
        - **update() is not called automatically.**  Your game loop
          must call ``animation.update(dt)`` each tick.
        - **Modifying frames after construction.**  The internal list
          is a shallow copy.  To change the frame sequence at runtime,
          use :meth:`set_frames`.  Mutating individual
          :class:`AnimationFrame` objects (char, style, duration) is
          fine and takes effect immediately.
        - **Large frame lists.**  There is no upper bound on frame
          count, but very long animations consume memory proportional
          to the frame count.  For procedural animation (computed per
          tick), consider modifying the Sprite directly instead.
    """

    __slots__ = ("_frames", "_elapsed", "_frame_index", "_playing", "_loop")

    def __init__(
        self,
        frames: list[AnimationFrame],
        *,
        loop: bool = True,
    ) -> None:
        super().__init__()

        # Validate frames.
        if not isinstance(frames, list):
            raise TypeError(
                f"frames must be a list, got {type(frames).__name__}"
            )
        if len(frames) == 0:
            raise ValueError("frames must not be empty")
        for i, frame in enumerate(frames):
            if not isinstance(frame, AnimationFrame):
                raise TypeError(
                    f"frames[{i}] must be an AnimationFrame, "
                    f"got {type(frame).__name__}"
                )

        self._frames: list[AnimationFrame] = list(frames)  # shallow copy
        self._elapsed: float = 0.0
        self._frame_index: int = 0
        self._playing: bool = True
        self._loop: bool = loop

    @property
    def frames(self) -> list[AnimationFrame]:
        """The animation frame sequence (read-only copy).

        Returns a shallow copy.  To modify the sequence, use
        :meth:`set_frames`.
        """
        return list(self._frames)

    @property
    def frame_count(self) -> int:
        """Number of frames in the animation."""
        return len(self._frames)

    @property
    def frame_index(self) -> int:
        """Index of the currently active frame (0-based)."""
        return self._frame_index

    @property
    def current_frame(self) -> AnimationFrame:
        """The currently active :class:`AnimationFrame`."""
        return self._frames[self._frame_index]

    @property
    def playing(self) -> bool:
        """Whether the animation is currently advancing."""
        return self._playing

    @property
    def loop(self) -> bool:
        """Whether the animation loops after the last frame."""
        return self._loop

    @loop.setter
    def loop(self, value: bool) -> None:
        self._loop = value

    @property
    def elapsed(self) -> float:
        """Time elapsed within the current frame, in seconds."""
        return self._elapsed

    @property
    def total_duration(self) -> float:
        """Sum of all frame durations, in seconds."""
        return sum(f.duration for f in self._frames)

    @property
    def finished(self) -> bool:
        """``True`` if a non-looping animation has completed.

        Always ``False`` for looping animations.
        """
        if self._loop:
            return False
        return (
            self._frame_index == len(self._frames) - 1
            and self._elapsed >= self._frames[self._frame_index].duration
        )

    def play(self) -> None:
        """Resume playback (or start if paused)."""
        self._playing = True

    def pause(self) -> None:
        """Pause playback.  The current frame remains visible."""
        self._playing = False

    def reset(self) -> None:
        """Reset to the first frame and resume playback."""
        self._frame_index = 0
        self._elapsed = 0.0
        self._playing = True

    def set_frames(self, frames: list[AnimationFrame]) -> None:
        """Replace the frame sequence.

        Resets playback to the first frame.

        Args:
            frames: A non-empty list of :class:`AnimationFrame` instances.

        Raises:
            TypeError: If *frames* is not a list.
            ValueError: If *frames* is empty.
            TypeError: If any element is not an :class:`AnimationFrame`.
        """
        if not isinstance(frames, list):
            raise TypeError(
                f"frames must be a list, got {type(frames).__name__}"
            )
        if len(frames) == 0:
            raise ValueError("frames must not be empty")
        for i, frame in enumerate(frames):
            if not isinstance(frame, AnimationFrame):
                raise TypeError(
                    f"frames[{i}] must be an AnimationFrame, "
                    f"got {type(frame).__name__}"
                )
        self._frames = list(frames)
        self._frame_index = 0
        self._elapsed = 0.0

    def update(self, dt: float) -> None:
        """Advance the animation by *dt* seconds and update the Sprite.

        If the animation is paused or finished, this method does nothing.

        Args:
            dt: Time elapsed since the last tick, in seconds.

        Caveats:
            - If the entity has no :class:`~wyby.sprite.Sprite` component,
              time still advances but no visual change occurs.
            - Large *dt* values (e.g. after a pause) may skip multiple
              frames in a single call.  This is intentional — the
              animation catches up to the correct frame for the elapsed
              time rather than playing every frame sequentially.
        """
        if not self._playing:
            return
        if self.finished:
            return

        self._elapsed += dt

        # Advance through frames as needed (may skip multiple frames
        # if dt is large relative to frame durations).
        while self._elapsed >= self._frames[self._frame_index].duration:
            self._elapsed -= self._frames[self._frame_index].duration

            if self._frame_index < len(self._frames) - 1:
                self._frame_index += 1
            elif self._loop:
                self._frame_index = 0
            else:
                # Non-looping: clamp to last frame.
                self._elapsed = self._frames[self._frame_index].duration
                break

        # Apply the current frame to the entity's Sprite.
        self._apply_frame()

    def _apply_frame(self) -> None:
        """Write the current frame's char/style to the entity's Sprite."""
        if self._entity is None:
            return

        from wyby.sprite import Sprite

        sprite = self._entity.get_component(Sprite)
        if sprite is None:
            return

        frame = self._frames[self._frame_index]
        sprite.char = frame.char

        # Only update style if the frame specifies one.
        if frame.style is not None:
            sprite.style = frame.style

    def __repr__(self) -> str:
        entity_info = (
            f"entity_id={self._entity.id}" if self._entity is not None
            else "detached"
        )
        return (
            f"Animation(frames={len(self._frames)}, "
            f"frame_index={self._frame_index}, "
            f"{entity_info})"
        )
