"""Application entry point and game loop.

This module provides the main :class:`Engine` class that will ultimately
drive the fixed-timestep game loop: drain input -> update active scene ->
render frame.

Caveats:
    - **Early implementation.** Only the ``Engine`` constructor is
      functional. The game loop (``run()``) and scene management are not
      yet implemented. See SCOPE.md for the intended design.
    - The game loop will target ~30 ticks per second by default, but
      actual frame rate depends on terminal emulator, grid size, and style
      complexity. Do not assume 60 FPS — that is not a meaningful target
      for terminal output.
    - Rich's ``Live`` display re-renders the full renderable each frame.
      CPU cost scales with frame complexity, and flicker is possible on
      slow terminals (especially Windows ``cmd.exe``).
    - The ``width`` and ``height`` parameters define the logical grid size
      in character cells, **not** pixels. Terminal cells are typically
      ~1:2 aspect ratio (taller than wide), so a "square" grid will
      appear as a tall rectangle. There is no automatic aspect-ratio
      correction — the game is responsible for accounting for cell shape.
    - Grid dimensions are not clamped to the actual terminal size. If
      ``width`` or ``height`` exceeds the terminal's columns or rows, the
      output will wrap or be clipped depending on the terminal emulator.
      Terminal resize detection is an open design question (see SCOPE.md).
    - The engine does not provide networking, audio, or GPU acceleration.
      These are explicitly out of scope for wyby v0.1.
"""

from __future__ import annotations

import logging

_logger = logging.getLogger(__name__)

# Minimum grid dimensions. A 1x1 grid is technically valid but useless
# for any real game. We enforce a floor of 1 to prevent nonsensical
# zero or negative sizes, but practical games will need much larger grids.
_MIN_WIDTH = 1
_MIN_HEIGHT = 1

# Sensible upper bound to guard against accidental huge allocations.
# A 1000x1000 grid of styled cells would be extremely expensive to
# render via Rich's Live display — likely single-digit FPS even on a
# fast terminal. This limit can be raised if a concrete use case demands
# it, but exceeding it almost certainly indicates a bug.
_MAX_WIDTH = 1000
_MAX_HEIGHT = 1000

_DEFAULT_TITLE = "wyby"
_DEFAULT_WIDTH = 80
_DEFAULT_HEIGHT = 24


class Engine:
    """Core engine that manages the game loop and top-level configuration.

    The ``Engine`` holds the game's title and logical grid dimensions.
    Future versions will own the scene stack, input system, and renderer.

    Args:
        title: Window/application title. Used for diagnostic output and
            will be passed to the terminal title escape sequence once the
            renderer is implemented. Defaults to ``"wyby"``.
        width: Logical grid width in character cells. Must be between 1
            and 1000 inclusive. Defaults to 80 (standard terminal width).
        height: Logical grid height in character cells. Must be between 1
            and 1000 inclusive. Defaults to 24 (standard terminal height).

    Raises:
        TypeError: If *title* is not a string, or *width*/*height* are
            not integers.
        ValueError: If *title* is empty or blank, or *width*/*height*
            are outside the allowed range (1–1000).

    Caveats:
        - ``width`` and ``height`` describe the logical game grid, not
          the terminal window size. The engine does not query or enforce
          terminal dimensions. If the grid exceeds the terminal, output
          will wrap or clip.
        - Terminal cells are not square (~1:2 aspect ratio). A grid of
          80x24 will not appear square on screen.
        - The title is stored but not yet written to the terminal. Once
          the renderer is implemented, it will set the terminal title via
          the ``\\033]0;...\\007`` escape sequence, which is supported by
          most modern terminals but silently ignored by some (notably
          the Linux virtual console).
    """

    __slots__ = ("_title", "_width", "_height")

    def __init__(
        self,
        title: str = _DEFAULT_TITLE,
        width: int = _DEFAULT_WIDTH,
        height: int = _DEFAULT_HEIGHT,
    ) -> None:
        if not isinstance(title, str):
            raise TypeError(
                f"title must be a str, got {type(title).__name__}"
            )
        if not title.strip():
            raise ValueError("title must not be empty or blank")

        if not isinstance(width, int) or isinstance(width, bool):
            raise TypeError(
                f"width must be an int, got {type(width).__name__}"
            )
        if not isinstance(height, int) or isinstance(height, bool):
            raise TypeError(
                f"height must be an int, got {type(height).__name__}"
            )

        if not (_MIN_WIDTH <= width <= _MAX_WIDTH):
            raise ValueError(
                f"width must be between {_MIN_WIDTH} and {_MAX_WIDTH}, "
                f"got {width}"
            )
        if not (_MIN_HEIGHT <= height <= _MAX_HEIGHT):
            raise ValueError(
                f"height must be between {_MIN_HEIGHT} and {_MAX_HEIGHT}, "
                f"got {height}"
            )

        self._title = title
        self._width = width
        self._height = height

        _logger.debug(
            "Engine initialized: title=%r, width=%d, height=%d",
            self._title,
            self._width,
            self._height,
        )

    @property
    def title(self) -> str:
        """The game/application title."""
        return self._title

    @property
    def width(self) -> int:
        """Logical grid width in character cells."""
        return self._width

    @property
    def height(self) -> int:
        """Logical grid height in character cells."""
        return self._height

    def __repr__(self) -> str:
        return (
            f"Engine(title={self._title!r}, "
            f"width={self._width!r}, height={self._height!r})"
        )
