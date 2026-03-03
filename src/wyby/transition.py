"""Scene transition stubs.

This module defines the :class:`Transition` base class and several
concrete stub implementations for scene-to-scene visual transitions.

**v0.1 status: stubs only — no animation.**  All transitions complete
instantly.  The interface exists so that games can declare transition
intent now (e.g., "fade to black between levels") and gain animated
implementations in a future release without changing call sites.

Planned integration (not yet implemented):
    :class:`~wyby.scene.SceneStack` methods (``push``, ``pop``,
    ``replace``) will accept an optional ``transition`` parameter.
    While a transition is active, both the outgoing and incoming scenes
    will be rendered and the transition will composite them.  Until
    then, transitions can be used manually by games that want to
    coordinate their own crossfade or wipe logic.

Caveats:
    - All transitions are synchronous stubs in v0.1.  :attr:`duration`
      stores the *intended* duration for future use, but
      :attr:`is_complete` always returns ``True`` and :meth:`update`
      is a no-op.
    - Transitions do **not** own or manage scenes.  They receive scene
      references in :meth:`start` for rendering purposes only.
    - Transitions are single-use.  Once :meth:`start` is called, the
      transition should not be reused for a different scene pair.
      Create a new instance for each transition.
    - The :meth:`render` method is a no-op stub.  Future versions will
      composite the outgoing and incoming scenes' render output.
    - ``direction`` on :class:`SlideTransition` is stored but not
      validated beyond checking it is one of the four cardinal
      directions.  Diagonal slides are not planned for v0.1.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from wyby.scene import Scene

_logger = logging.getLogger(__name__)

# Valid slide directions for SlideTransition.
_VALID_DIRECTIONS = frozenset({"left", "right", "up", "down"})

# Duration limits (seconds).  Upper bound prevents accidentally
# specifying e.g. milliseconds instead of seconds.
_MIN_DURATION = 0.0
_MAX_DURATION = 10.0


class Transition(ABC):
    """Abstract base class for scene transitions.

    A transition controls the visual changeover between an outgoing
    scene and an incoming scene.  Subclasses define the visual effect
    (fade, slide, wipe, etc.) and its duration.

    In v0.1, all concrete transitions are **stubs** — they complete
    instantly with no visual effect.  The lifecycle methods exist to
    establish the interface contract for future animated versions.

    Lifecycle:
        1. **Create** — instantiate with effect-specific parameters
           (duration, direction, etc.).
        2. **Start** — call :meth:`start` with the outgoing and
           incoming scenes.  This records the scene pair.
        3. **Tick** — call :meth:`update` each tick with ``dt``.  The
           transition advances its internal timer and updates its
           visual state.  (Stubs are no-ops.)
        4. **Render** — call :meth:`render` each tick to draw the
           transition frame.  (Stubs are no-ops.)
        5. **Complete** — when :attr:`is_complete` returns ``True``,
           the transition is done and the incoming scene takes over.

    Caveats:
        - Transitions are **not thread-safe**.  They should only be
          driven from the engine's main loop.
        - Transitions are **single-use**.  Do not call :meth:`start`
          a second time on the same instance.
        - Subclasses must call ``super().__init__()`` if they override
          ``__init__``.
    """

    @property
    @abstractmethod
    def duration(self) -> float:
        """The intended duration of the transition in seconds.

        Returns ``0.0`` for instant transitions (e.g., :class:`Cut`).
        For stub transitions that *will* have a duration in the future,
        this returns the configured duration even though the stub
        completes instantly.

        Caveats:
            - In v0.1, this value is informational only.  The
              transition completes instantly regardless of duration.
        """

    @property
    def is_complete(self) -> bool:
        """Whether the transition has finished.

        Stubs always return ``True`` — the transition is "done" as
        soon as it starts.  Future animated implementations will
        return ``False`` while the animation is in progress.
        """
        # Stubs complete instantly.  Animated subclasses will override.
        return True

    @property
    def progress(self) -> float:
        """Transition progress from 0.0 (just started) to 1.0 (complete).

        Stubs always return ``1.0``.  Future animated implementations
        will return intermediate values based on elapsed time.
        """
        # Stubs are always at 100%.  Animated subclasses will override.
        return 1.0

    def start(self, outgoing: Scene | None, incoming: Scene | None) -> None:
        """Begin the transition between two scenes.

        Args:
            outgoing: The scene being transitioned *from*, or ``None``
                if there is no outgoing scene (e.g., initial push
                onto an empty stack).
            incoming: The scene being transitioned *to*, or ``None``
                if there is no incoming scene (e.g., popping the last
                scene off the stack).

        Caveats:
            - At least one of *outgoing* or *incoming* should be
              non-``None``.  Passing both as ``None`` is allowed but
              meaningless.
            - This method should only be called once per transition
              instance.
        """
        _logger.debug(
            "%s.start(outgoing=%s, incoming=%s)",
            type(self).__name__,
            type(outgoing).__name__ if outgoing is not None else "None",
            type(incoming).__name__ if incoming is not None else "None",
        )

    def update(self, dt: float) -> None:
        """Advance the transition by one timestep.

        Args:
            dt: The fixed timestep duration in seconds.

        Stubs are no-ops.  Future animated implementations will use
        this to advance their internal timer and interpolate visual
        state.
        """

    def render(self) -> None:
        """Render the transition's current visual state.

        Stubs are no-ops.  Future animated implementations will
        composite the outgoing and incoming scenes' render output
        based on :attr:`progress`.

        Caveats:
            - This method must not modify game state — it should be
              a pure visual operation.
        """

    def __repr__(self) -> str:
        return f"{type(self).__name__}(duration={self.duration})"


class Cut(Transition):
    """Instant cut — no visual transition.

    The outgoing scene disappears and the incoming scene appears
    immediately with no animation.  This is the default transition
    behaviour (equivalent to the current SceneStack push/pop/replace
    with no transition specified).

    This is useful as a sentinel value when an API requires a
    :class:`Transition` instance but no visual effect is desired.
    """

    @property
    def duration(self) -> float:
        """Always ``0.0`` — cuts are instant."""
        return 0.0


class FadeTransition(Transition):
    """Stub for a fade-to-black transition.

    **Not yet animated.**  In v0.1 this behaves identically to
    :class:`Cut` — the transition completes instantly.  The
    *duration* parameter is stored for future use when animated
    fades are implemented.

    When animated (future):
        The outgoing scene will fade to black over the first half of
        the duration, then the incoming scene will fade in from black
        over the second half.

    Args:
        duration: Intended fade duration in seconds.  Must be between
            0.0 and 10.0.  Defaults to ``0.5``.

    Raises:
        TypeError: If *duration* is not a number.
        ValueError: If *duration* is outside the allowed range.

    Caveats:
        - Duration is stored but ignored in v0.1.  The transition
          completes instantly.
        - The fade visual (opacity blending) requires renderer
          support that does not yet exist.  When the renderer gains
          compositing, this transition will use it.
    """

    __slots__ = ("_duration",)

    def __init__(self, duration: float = 0.5) -> None:
        if not isinstance(duration, (int, float)) or isinstance(duration, bool):
            raise TypeError(
                f"duration must be a number, got {type(duration).__name__}"
            )
        if not (_MIN_DURATION <= duration <= _MAX_DURATION):
            raise ValueError(
                f"duration must be between {_MIN_DURATION} and "
                f"{_MAX_DURATION}, got {duration}"
            )
        self._duration = float(duration)

    @property
    def duration(self) -> float:
        """The configured fade duration in seconds (informational in v0.1)."""
        return self._duration


class SlideTransition(Transition):
    """Stub for a sliding transition.

    **Not yet animated.**  In v0.1 this behaves identically to
    :class:`Cut` — the transition completes instantly.  The
    *direction* and *duration* parameters are stored for future use.

    When animated (future):
        The incoming scene will slide in from the specified direction,
        pushing the outgoing scene off-screen.

    Args:
        direction: The direction the incoming scene slides in from.
            One of ``"left"``, ``"right"``, ``"up"``, ``"down"``.
            Defaults to ``"left"``.
        duration: Intended slide duration in seconds.  Must be between
            0.0 and 10.0.  Defaults to ``0.3``.

    Raises:
        TypeError: If *direction* is not a string or *duration* is
            not a number.
        ValueError: If *direction* is not a valid direction or
            *duration* is outside the allowed range.

    Caveats:
        - Direction and duration are stored but ignored in v0.1.
          The transition completes instantly.
        - Diagonal directions (e.g., ``"up-left"``) are not supported.
        - The slide visual (offset rendering) requires renderer
          support that does not yet exist.
    """

    __slots__ = ("_direction", "_duration")

    def __init__(
        self, direction: str = "left", duration: float = 0.3
    ) -> None:
        if not isinstance(direction, str):
            raise TypeError(
                f"direction must be a string, got {type(direction).__name__}"
            )
        if direction not in _VALID_DIRECTIONS:
            raise ValueError(
                f"direction must be one of {sorted(_VALID_DIRECTIONS)}, "
                f"got {direction!r}"
            )
        if not isinstance(duration, (int, float)) or isinstance(duration, bool):
            raise TypeError(
                f"duration must be a number, got {type(duration).__name__}"
            )
        if not (_MIN_DURATION <= duration <= _MAX_DURATION):
            raise ValueError(
                f"duration must be between {_MIN_DURATION} and "
                f"{_MAX_DURATION}, got {duration}"
            )
        self._direction = direction
        self._duration = float(duration)

    @property
    def direction(self) -> str:
        """The configured slide direction."""
        return self._direction

    @property
    def duration(self) -> float:
        """The configured slide duration in seconds (informational in v0.1)."""
        return self._duration

    def __repr__(self) -> str:
        return (
            f"SlideTransition(direction={self._direction!r}, "
            f"duration={self._duration})"
        )
