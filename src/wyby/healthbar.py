"""HealthBar widget for terminal UI overlays.

This module provides a :class:`HealthBar` widget that renders a horizontal
bar showing current/max health (or any bounded value) into a
:class:`~wyby.grid.CellBuffer`.  The bar uses Unicode block characters
for filled (``█``) and empty (``░``) segments, with colour that changes
based on the fill percentage.

Usage::

    from wyby.healthbar import HealthBar
    from wyby.grid import CellBuffer

    bar = HealthBar(current=75, maximum=100, x=2, y=0, bar_width=20)

    # In your game loop:
    buf = CellBuffer(80, 24)
    bar.draw(buf)

    # Update health:
    bar.current = 50

Caveats:
    - **Block characters are narrow (1-column) Unicode.**  ``█`` (U+2588)
      and ``░`` (U+2591) are reliably rendered across modern terminals
      (macOS Terminal, iTerm2, Windows Terminal, GNOME Terminal, etc.).
      However, on very old terminals or bitmap-font configurations, they
      may render as replacement characters or with inconsistent widths.
      Test on your target terminal.
    - **Colour thresholds are hardcoded.**  The default colour scheme
      (green > 50%, yellow 25–50%, red < 25%) is a common convention but
      cannot be customized without subclassing.  Override
      :meth:`_bar_color` to change the thresholds or colours.
    - **No smooth sub-cell fill.**  Each cell is either filled or empty —
      there are no half-block characters for fractional fill.  This means
      the visual resolution of the bar equals ``bar_width`` cells.  A
      20-cell bar has 5% granularity per cell.  For finer resolution, use
      a wider bar.
    - **Label is optional and fixed-format.**  When ``show_label=True``,
      the bar renders ``HP: 75/100 ████████████████░░░░`` (label then
      bar).  The label format is ``{current}/{maximum}`` with a
      configurable prefix (default ``"HP"``).  For custom formatting,
      subclass and override :meth:`_format_label`.
    - **Widget width includes the label.**  The widget's ``width`` is
      computed as ``bar_width`` plus label length (if shown).  Changing
      ``bar_width``, ``show_label``, ``label_prefix``, ``current``, or
      ``maximum`` updates the widget width automatically.
    - **Terminal cell aspect ratio applies.**  The bar is 1 row tall.
      Terminal cells are ~1:2 aspect (taller than wide), so the bar
      appears short and wide.  This is normal for terminal UIs.
    - **No animation.**  Value changes are reflected immediately on the
      next ``draw()`` call.  There is no lerp/tween for smooth health
      transitions.  Implement animation in game code by incrementally
      updating ``current`` each frame.
    - **Single-threaded.**  Like all wyby widgets, mutation is not
      thread-safe.  Update ``current`` only from the game loop thread.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from wyby.widget import Widget

if TYPE_CHECKING:
    from wyby.grid import CellBuffer

_logger = logging.getLogger(__name__)

# Unicode block characters for the bar.
# U+2588 FULL BLOCK — reliably 1-column wide on modern terminals.
# U+2591 LIGHT SHADE — used for the empty portion of the bar.
# Caveat: some bitmap fonts render these with inconsistent widths.
# If that happens on your target terminal, swap to ASCII alternatives
# like '#' and '.' (set FILLED_CHAR / EMPTY_CHAR on the instance).
FILLED_CHAR = "\u2588"  # █
EMPTY_CHAR = "\u2591"   # ░

# Default colour thresholds.
# Caveat: these are percentage-based (0.0–1.0).  The colours are Rich
# colour strings passed to CellBuffer.put_text(fg=...).
_COLOR_HIGH = "green"       # > 50%
_COLOR_MEDIUM = "yellow"    # 25%–50%
_COLOR_LOW = "red"          # < 25%

# Gap between label and bar (in columns).
_LABEL_GAP = 1


class HealthBar(Widget):
    """A horizontal health bar widget with colour-coded fill.

    Renders a bar like ``HP: 75/100 ████████████████░░░░`` where the
    filled portion uses ``█`` and the empty portion uses ``░``.  The bar
    colour changes based on the fill percentage: green above 50%, yellow
    between 25–50%, and red below 25%.

    Args:
        current: Current health value.  Clamped to [0, *maximum*].
        maximum: Maximum health value.  Must be >= 1.
        x: Column position of the widget's top-left corner.
        y: Row position of the widget's top-left corner.
        bar_width: Width of the bar portion in columns (not including
            the label).  Clamped to [1, 1000].
        show_label: Whether to show the ``HP: 75/100`` label before
            the bar.  Default ``True``.
        label_prefix: Text prefix for the label.  Default ``"HP"``.

    Raises:
        TypeError: If *current*, *maximum*, or *bar_width* are not
            integers, or if *label_prefix* is not a string.
        ValueError: If *maximum* < 1.

    Caveats:
        - ``current`` is clamped to [0, ``maximum``] on set.  Negative
          health silently becomes 0; values above ``maximum`` silently
          become ``maximum``.  This prevents visual glitches but means
          over-healing or negative damage is not reflected visually.
        - ``maximum`` must be >= 1.  A zero-max bar is nonsensical and
          would cause division-by-zero in percentage calculation.
        - The widget ``height`` is always 1.  Multi-row health bars are
          not supported by this widget.
    """

    __slots__ = (
        "_current", "_maximum", "_bar_width",
        "_show_label", "_label_prefix",
        "_filled_char", "_empty_char",
    )

    def __init__(
        self,
        current: int = 100,
        maximum: int = 100,
        x: int = 0,
        y: int = 0,
        bar_width: int = 20,
        show_label: bool = True,
        label_prefix: str = "HP",
    ) -> None:
        if not isinstance(current, int) or isinstance(current, bool):
            msg = f"current must be an int, got {type(current).__name__}"
            raise TypeError(msg)
        if not isinstance(maximum, int) or isinstance(maximum, bool):
            msg = f"maximum must be an int, got {type(maximum).__name__}"
            raise TypeError(msg)
        if not isinstance(bar_width, int) or isinstance(bar_width, bool):
            msg = f"bar_width must be an int, got {type(bar_width).__name__}"
            raise TypeError(msg)
        if not isinstance(label_prefix, str):
            msg = f"label_prefix must be a str, got {type(label_prefix).__name__}"
            raise TypeError(msg)
        if maximum < 1:
            msg = f"maximum must be >= 1, got {maximum}"
            raise ValueError(msg)

        self._maximum = maximum
        self._current = max(0, min(current, maximum))
        self._bar_width = max(1, min(bar_width, 1000))
        self._show_label = bool(show_label)
        self._label_prefix = label_prefix
        self._filled_char = FILLED_CHAR
        self._empty_char = EMPTY_CHAR

        total_width = self._compute_total_width()
        super().__init__(x=x, y=y, width=total_width, height=1)

    # -- Width computation --------------------------------------------------

    def _compute_total_width(self) -> int:
        """Compute the total widget width (label + gap + bar).

        Caveat: this must be called after every change to ``_current``,
        ``_maximum``, ``_bar_width``, ``_show_label``, or
        ``_label_prefix`` to keep the widget width in sync.  The
        property setters handle this automatically.
        """
        if self._show_label:
            label = self._format_label()
            return len(label) + _LABEL_GAP + self._bar_width
        return self._bar_width

    def _update_width(self) -> None:
        """Recalculate and set the widget width."""
        self.width = self._compute_total_width()

    # -- Properties ---------------------------------------------------------

    @property
    def current(self) -> int:
        """Current health value, clamped to [0, maximum]."""
        return self._current

    @current.setter
    def current(self, value: int) -> None:
        if not isinstance(value, int) or isinstance(value, bool):
            msg = f"current must be an int, got {type(value).__name__}"
            raise TypeError(msg)
        self._current = max(0, min(value, self._maximum))
        self._update_width()

    @property
    def maximum(self) -> int:
        """Maximum health value.  Must be >= 1."""
        return self._maximum

    @maximum.setter
    def maximum(self, value: int) -> None:
        if not isinstance(value, int) or isinstance(value, bool):
            msg = f"maximum must be an int, got {type(value).__name__}"
            raise TypeError(msg)
        if value < 1:
            msg = f"maximum must be >= 1, got {value}"
            raise ValueError(msg)
        self._maximum = value
        # Re-clamp current to the new maximum.
        self._current = max(0, min(self._current, self._maximum))
        self._update_width()

    @property
    def bar_width(self) -> int:
        """Width of the bar portion in columns."""
        return self._bar_width

    @bar_width.setter
    def bar_width(self, value: int) -> None:
        if not isinstance(value, int) or isinstance(value, bool):
            msg = f"bar_width must be an int, got {type(value).__name__}"
            raise TypeError(msg)
        self._bar_width = max(1, min(value, 1000))
        self._update_width()

    @property
    def show_label(self) -> bool:
        """Whether the label (e.g. ``HP: 75/100``) is shown."""
        return self._show_label

    @show_label.setter
    def show_label(self, value: bool) -> None:
        self._show_label = bool(value)
        self._update_width()

    @property
    def label_prefix(self) -> str:
        """Text prefix for the label (default ``"HP"``)."""
        return self._label_prefix

    @label_prefix.setter
    def label_prefix(self, value: str) -> None:
        if not isinstance(value, str):
            msg = f"label_prefix must be a str, got {type(value).__name__}"
            raise TypeError(msg)
        self._label_prefix = value
        self._update_width()

    @property
    def percentage(self) -> float:
        """Fill percentage as a float in [0.0, 1.0].

        Caveat: this is computed from integer division, so for small
        ``maximum`` values the result may not match expectations
        (e.g., ``current=1, maximum=3`` gives ``0.333...``, which
        fills 6 of 20 cells — 30%, not 33%).
        """
        return self._current / self._maximum

    # -- Label formatting ---------------------------------------------------

    def _format_label(self) -> str:
        """Format the label string (e.g. ``HP: 75/100``).

        Override in subclasses for custom label formatting.
        """
        return f"{self._label_prefix}: {self._current}/{self._maximum}"

    # -- Colour selection ---------------------------------------------------

    def _bar_color(self) -> str:
        """Return the Rich colour string for the current fill level.

        Default thresholds:
            - Green (``"green"``) when > 50% full
            - Yellow (``"yellow"``) when 25–50% full
            - Red (``"red"``) when < 25% full

        Override in subclasses for custom colour logic.

        Caveat: the thresholds are checked with ``>``, ``>=``, and
        implicit else, so exactly 50% is yellow and exactly 25% is
        yellow.  Adjust in a subclass if you need different boundary
        behaviour.
        """
        pct = self.percentage
        if pct > 0.5:
            return _COLOR_HIGH
        if pct >= 0.25:
            return _COLOR_MEDIUM
        return _COLOR_LOW

    # -- Drawing ------------------------------------------------------------

    def draw(self, buffer: CellBuffer) -> None:
        """Render the health bar into *buffer*.

        Draws an optional label followed by a bar made of filled and
        empty block characters.  The bar colour changes based on the
        fill percentage.

        Skips drawing if ``self.visible`` is ``False``.

        Caveats:
            - Drawing relies on CellBuffer's silent clipping for
              out-of-bounds writes.  A health bar positioned partially
              off-screen will be truncated without error.
            - The bar uses ``put_text`` for each segment (label, filled,
              empty).  For very wide bars (100+ cells), this is still
              fast — ``put_text`` is O(n) in characters written.
            - The empty portion of the bar uses dim styling for visual
              contrast.  On terminals that don't support dim (rare),
              the empty portion will render at normal brightness.
        """
        if not self.visible:
            return

        col = self._x
        color = self._bar_color()

        # Draw label if enabled.
        if self._show_label:
            label = self._format_label()
            buffer.put_text(col, self._y, label, fg=color, bold=self._focused)
            col += len(label) + _LABEL_GAP

        # Compute filled vs empty cells.
        filled = round(self.percentage * self._bar_width)
        empty = self._bar_width - filled

        # Draw filled portion.
        if filled > 0:
            buffer.put_text(
                col, self._y,
                self._filled_char * filled,
                fg=color, bold=self._focused,
            )
        # Draw empty portion.
        if empty > 0:
            buffer.put_text(
                col + filled, self._y,
                self._empty_char * empty,
                fg=color, dim=True,
            )

    # -- Repr ---------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"HealthBar("
            f"{self._current}/{self._maximum}, "
            f"x={self._x}, y={self._y}, "
            f"bar_width={self._bar_width}"
            f"{', visible=False' if not self._visible else ''}"
            f"{', focused' if self._focused else ''}"
            f")"
        )
