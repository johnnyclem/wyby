"""Headless renderer for testing game logic without a terminal.

This module provides :class:`TestRendererBuffer` — a renderer that captures
frames to an in-memory buffer instead of writing to the terminal.  It
implements the same public interface as :class:`~wyby.renderer.Renderer`
(start/stop lifecycle, ``present()``, overlay management, frame counting)
so that game code under test can use it as a drop-in substitute.

Typical usage in tests::

    from wyby.test_renderer import TestRendererBuffer
    from wyby.grid import Cell, CellBuffer

    renderer = TestRendererBuffer(width=20, height=10)
    renderer.start()
    buf = CellBuffer(20, 10)
    buf.put_text(0, 0, "Score: 42", fg="green")
    renderer.present(buf)

    # Inspect what was rendered:
    assert renderer.last_frame is not None
    cell = renderer.last_frame.get(0, 0)
    assert cell.char == "S"
    assert cell.fg == "green"
    assert renderer.frame_count == 1

    # Check frame history:
    assert len(renderer.frame_history) == 1
    renderer.stop()

Why a separate test renderer?
    The production :class:`~wyby.renderer.Renderer` wraps Rich's
    ``Live`` display, which writes ANSI escape sequences to stdout.
    This makes assertions on rendered content difficult — test code
    would need to parse escape sequences to check what was drawn.
    ``TestRendererBuffer`` bypasses Rich entirely and stores
    :class:`~wyby.grid.CellBuffer` snapshots, giving tests direct
    access to cell data (characters, colours, bold/dim) without
    parsing terminal output.

Caveats:
    - **Not a production renderer.**  ``TestRendererBuffer`` does not
      write anything to the terminal.  It is intended exclusively for
      unit tests.  Using it in production would display nothing.
    - **Only captures CellBuffer frames.**  When ``present()`` receives
      a :class:`~wyby.grid.CellBuffer`, it stores a deep copy as the
      frame snapshot.  For non-CellBuffer renderables (strings, Rich
      ``Text``, etc.), no snapshot is stored — :attr:`last_frame` will
      be ``None`` for that frame.  This mirrors the production
      renderer's overlay limitation: overlays are only composited onto
      CellBuffer renderables.
    - **Frame history grows unbounded.**  Each ``present()`` call with
      a CellBuffer appends a copy to :attr:`frame_history`.  For long
      test runs with many frames, this consumes memory proportional to
      ``frame_count × width × height``.  Call :meth:`clear_history` to
      free captured frames if needed.
    - **Deep copies on capture.**  Each captured frame is a full
      deep copy of the CellBuffer at the time of ``present()``.
      Subsequent mutations to the original buffer do not affect
      captured frames.  The copy cost is O(width × height) per frame.
    - **Overlay draw order matches production.**  Overlays registered
      via :meth:`add_overlay` are drawn into the CellBuffer in
      ascending ``z_index`` order before the frame is captured, exactly
      as the production ``Renderer`` does.  The captured frame includes
      overlay content.
    - **No Rich dependency.**  Unlike the production ``Renderer``, this
      class does not use Rich's ``Console`` or ``Live`` display.  It
      can be used in test environments where Rich is not configured or
      where stdout is not a TTY.
    - **No render timing.**  The :attr:`render_timer` property returns
      a :class:`~wyby.diagnostics.RenderTimer` instance, but recorded
      times are near-zero (no terminal I/O).  Do not use
      ``TestRendererBuffer`` to measure rendering performance.
    - **Thread safety.**  Like the production renderer, this class is
      not thread-safe.  All calls must come from the same thread.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from wyby.diagnostics import RenderTimer
from wyby.grid import CellBuffer
from wyby.widget import Widget

if TYPE_CHECKING:
    pass

_logger = logging.getLogger(__name__)


def _overlay_z_key(widget: Widget) -> int:
    """Sort key for overlay draw order — ascending z_index."""
    return widget.z_index


class TestRendererBuffer:
    """Headless renderer that captures frames for test assertions.

    .. note:: ``__test__ = False`` prevents pytest from collecting this
       class as a test suite.  The ``Test`` prefix is intentional —
       this class is *for* testing, not *a* test.

    Implements the same public interface as
    :class:`~wyby.renderer.Renderer` — ``start()``, ``stop()``,
    ``present()``, overlay management — but writes nothing to the
    terminal.  Instead, each ``present()`` call with a
    :class:`~wyby.grid.CellBuffer` stores a deep copy of the buffer
    in :attr:`frame_history`.

    Args:
        width: Default buffer width for :attr:`last_frame` queries.
            This does **not** constrain what can be presented — any
            size CellBuffer is accepted.  The width is only used if
            the test renderer needs to create an internal buffer
            (e.g. for non-CellBuffer renderables).  Defaults to 80.
        height: Default buffer height.  Defaults to 24.

    Caveats:
        - **Not for production use.**  This renderer displays nothing.
        - **Only CellBuffer renderables are captured.**  Strings and
          other Rich renderables are accepted by ``present()`` but
          produce no frame snapshot.
        - **Frame history is unbounded.**  Call :meth:`clear_history`
          in long-running test scenarios.
    """

    # Prevent pytest from collecting this as a test class.
    __test__ = False

    __slots__ = (
        "_width",
        "_height",
        "_started",
        "_frame_count",
        "_render_timer",
        "_overlays",
        "_last_frame",
        "_frame_history",
        "_non_buffer_frames",
    )

    def __init__(
        self,
        width: int = 80,
        height: int = 24,
    ) -> None:
        if not isinstance(width, int) or width < 1:
            raise ValueError(
                f"width must be a positive integer, got {width!r}"
            )
        if not isinstance(height, int) or height < 1:
            raise ValueError(
                f"height must be a positive integer, got {height!r}"
            )
        self._width = width
        self._height = height
        self._started: bool = False
        self._frame_count: int = 0
        self._render_timer = RenderTimer()
        self._overlays: list[Widget] = []
        self._last_frame: CellBuffer | None = None
        self._frame_history: list[CellBuffer] = []
        # Track non-CellBuffer renderables for basic presence checks.
        self._non_buffer_frames: list[Any] = []

    # -- Properties ---------------------------------------------------------

    @property
    def width(self) -> int:
        """Default buffer width."""
        return self._width

    @property
    def height(self) -> int:
        """Default buffer height."""
        return self._height

    @property
    def is_started(self) -> bool:
        """Whether the renderer is currently active."""
        return self._started

    @property
    def frame_count(self) -> int:
        """Number of frames presented since the last :meth:`start`.

        Reset to 0 on each ``start()`` call.  Not incremented by
        ``present()`` calls made while the renderer is stopped.
        """
        return self._frame_count

    @property
    def render_timer(self) -> RenderTimer:
        """Render timer (near-zero times — no real rendering occurs).

        Caveat:
            Recorded times reflect Python-side copy overhead only, not
            terminal rendering.  Do not use for performance measurement.
        """
        return self._render_timer

    @property
    def last_frame(self) -> CellBuffer | None:
        """The most recently captured CellBuffer frame, or ``None``.

        Returns ``None`` if:
        - No frames have been presented yet.
        - The most recent ``present()`` call received a non-CellBuffer
          renderable.
        - :meth:`clear_history` was called since the last ``present()``.

        The returned buffer is a deep copy taken at ``present()`` time.
        Mutating it does not affect the test renderer's internal state.
        """
        return self._last_frame

    @property
    def frame_history(self) -> list[CellBuffer]:
        """All captured CellBuffer frames since the last :meth:`start`.

        Returns the internal list directly (not a copy) for efficiency
        in test assertions.  Do not mutate this list — use
        :meth:`clear_history` to reset it.

        Caveat:
            Grows by one entry per ``present()`` call with a CellBuffer.
            For long test runs, call :meth:`clear_history` periodically.
        """
        return self._frame_history

    @property
    def non_buffer_frames(self) -> list[Any]:
        """Non-CellBuffer renderables passed to ``present()``.

        Useful for checking that string or Rich renderable frames were
        presented, even though they don't produce cell-level snapshots.
        """
        return self._non_buffer_frames

    # -- Overlay management -------------------------------------------------

    @property
    def overlays(self) -> list[Widget]:
        """Read-only copy of registered overlay widgets."""
        return list(self._overlays)

    @property
    def overlay_count(self) -> int:
        """Number of currently registered overlays."""
        return len(self._overlays)

    def add_overlay(self, widget: Widget) -> None:
        """Register a widget overlay (same semantics as Renderer).

        Raises:
            TypeError: If *widget* is not a Widget instance.
        """
        if not isinstance(widget, Widget):
            raise TypeError(
                f"widget must be a Widget, got {type(widget).__name__}"
            )
        if widget in self._overlays:
            return
        self._overlays.append(widget)

    def remove_overlay(self, widget: Widget) -> None:
        """Remove a previously registered overlay widget.

        Raises:
            ValueError: If *widget* is not currently registered.
        """
        try:
            self._overlays.remove(widget)
        except ValueError:
            raise ValueError(
                f"{widget!r} is not a registered overlay"
            ) from None

    def clear_overlays(self) -> None:
        """Remove all registered overlay widgets."""
        self._overlays.clear()

    # -- Lifecycle ----------------------------------------------------------

    def start(self) -> None:
        """Start the test renderer.

        Resets :attr:`frame_count`, :attr:`frame_history`, and
        :attr:`last_frame`.  Calling ``start()`` when already started
        is a no-op.

        Unlike the production renderer, this does not write any escape
        sequences or interact with the terminal.
        """
        if self._started:
            return
        self._frame_count = 0
        self._render_timer.reset()
        self._last_frame = None
        self._frame_history = []
        self._non_buffer_frames = []
        self._started = True
        _logger.debug("TestRendererBuffer started (%dx%d)", self._width, self._height)

    def stop(self) -> None:
        """Stop the test renderer.

        Idempotent — safe to call multiple times or when not started.
        Does not clear frame history (it remains accessible for
        post-run assertions).
        """
        if not self._started:
            return
        self._started = False
        _logger.debug(
            "TestRendererBuffer stopped (frames=%d)", self._frame_count
        )

    def clear_buffer(self) -> None:
        """Clear the display (no-op in test renderer).

        In the production renderer, this pushes an empty frame to
        blank the Live display region.  Here it is a no-op to match
        the interface, but it does not affect frame history or
        :attr:`last_frame`.

        No-op if not started.  Does not affect :attr:`frame_count`.
        """
        if not self._started:
            return
        # Intentional no-op — there is no terminal display to clear.
        _logger.debug("TestRendererBuffer.clear_buffer() (no-op)")

    def present(self, renderable: Any) -> None:
        """Capture a frame for test inspection.

        If *renderable* is a :class:`~wyby.grid.CellBuffer`:
        1. Registered overlays are drawn into the buffer (mutating it,
           same as production).
        2. A deep copy of the buffer is stored in :attr:`frame_history`
           and :attr:`last_frame`.

        If *renderable* is not a CellBuffer, it is stored in
        :attr:`non_buffer_frames` for basic presence checks, but no
        cell-level snapshot is created.

        No-op if the renderer is not started.

        Args:
            renderable: Any renderable — CellBuffer, string, Rich Text,
                etc.

        Caveats:
            - Overlays mutate the caller's CellBuffer, same as
              production.  Pass a copy if you need the original
              unmodified.
            - Deep copy cost is O(width x height) per CellBuffer frame.
        """
        if not self._started:
            return

        if isinstance(renderable, CellBuffer):
            # Draw overlays into the buffer, matching production behaviour.
            if self._overlays:
                for overlay in sorted(self._overlays, key=_overlay_z_key):
                    if overlay.visible:
                        overlay.draw(renderable)

            # Deep-copy the buffer so later mutations don't affect the
            # captured frame.
            snapshot = _copy_cellbuffer(renderable)
            self._last_frame = snapshot
            self._frame_history.append(snapshot)
        else:
            self._non_buffer_frames.append(renderable)

        self._frame_count += 1

    # -- History management -------------------------------------------------

    def clear_history(self) -> None:
        """Discard all captured frames.

        Resets :attr:`frame_history`, :attr:`non_buffer_frames`, and
        :attr:`last_frame` to empty/None.  Does **not** reset
        :attr:`frame_count`.
        """
        self._frame_history.clear()
        self._non_buffer_frames.clear()
        self._last_frame = None

    # -- Convenience methods for test assertions ----------------------------

    def get_cell(self, x: int, y: int) -> Any | None:
        """Return the cell at (x, y) in the last captured frame.

        Shorthand for ``renderer.last_frame.get(x, y)``.

        Returns ``None`` if no CellBuffer frame has been captured or
        if the coordinates are out of bounds.
        """
        if self._last_frame is None:
            return None
        return self._last_frame.get(x, y)

    def get_text(self, x: int, y: int, length: int) -> str:
        """Extract a string of characters from the last captured frame.

        Reads *length* characters starting at (*x*, *y*) from
        :attr:`last_frame`.  Returns an empty string if no frame has
        been captured.

        Caveat:
            This reads raw cell characters.  Wide-character filler
            sentinels (``\\x00``) are included in the result.  For
            display-accurate text, filter them out.
        """
        if self._last_frame is None:
            return ""
        chars: list[str] = []
        for col in range(x, x + length):
            cell = self._last_frame.get(col, y)
            if cell is None:
                break
            chars.append(cell.char)
        return "".join(chars)

    # -- Context manager ----------------------------------------------------

    def __enter__(self) -> TestRendererBuffer:
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object | None,
    ) -> None:
        self.stop()

    def __repr__(self) -> str:
        return (
            f"TestRendererBuffer("
            f"started={self._started}, "
            f"frame_count={self._frame_count}, "
            f"overlays={len(self._overlays)}, "
            f"size={self._width}x{self._height})"
        )


def _copy_cellbuffer(source: CellBuffer) -> CellBuffer:
    """Create a deep copy of a CellBuffer.

    Each Cell is copied individually so the snapshot is fully
    independent of the original.  Uses the public ``get``/``put``
    API to avoid reaching into private attributes.

    Cost: O(width × height) — one Cell copy per grid position.
    """
    from wyby.grid import Cell

    result = CellBuffer(source.width, source.height)
    for y in range(source.height):
        row = source.row(y)
        if row is None:
            continue
        for x, cell in enumerate(row):
            # Copy each cell to avoid shared references.
            result.put(x, y, Cell(
                char=cell.char,
                fg=cell.fg,
                bg=cell.bg,
                bold=cell.bold,
                dim=cell.dim,
            ))
    return result
