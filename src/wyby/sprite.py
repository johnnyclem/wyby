"""Sprite component for entity visual appearance.

Provides a :class:`Sprite` component that stores a character and a Rich
:class:`~rich.style.Style`, defining how an entity looks when rendered
into a :class:`~wyby.grid.CellBuffer`.

Usage::

    from wyby.entity import Entity
    from wyby.sprite import Sprite
    from rich.style import Style

    e = Entity(5, 3)
    s = Sprite("@", Style(color="green", bold=True))
    e.add_component(s)

    # Read back
    assert s.char == "@"
    assert s.style.color.name == "green"

Caveats:
    - **Single character only.**  The ``char`` must be exactly one
      Python character (one Unicode codepoint).  Multi-character strings
      are rejected.  For multi-cell visuals, use multiple entities or
      write directly to the :class:`~wyby.grid.CellBuffer`.
    - **Unicode width is not enforced.**  The char is stored as-is.
      Wide characters (CJK ideographs, fullwidth forms) occupy 2
      terminal cells but are stored as a single ``char``.  The
      renderer must account for display width via
      :func:`~wyby.unicode.char_width`.  Emoji rendering is
      terminal-dependent and unreliable — stick to ASCII and simple
      Unicode for game tiles.  See :mod:`wyby.unicode` for details.
    - **Style is a Rich object.**  The ``style`` attribute is a
      :class:`rich.style.Style` instance.  Only ``color`` (foreground),
      ``bgcolor`` (background), ``bold``, and ``dim`` are used when
      rendering to a :class:`~wyby.grid.Cell`.  Other Style attributes
      (italic, underline, strikethrough, etc.) are silently ignored by
      the CellBuffer — they cannot be represented in terminal cell
      grids.  If you need those attributes, render directly with Rich
      rather than through CellBuffer.
    - **Style is mutable by reference.**  Rich ``Style`` objects are
      immutable, but replacing ``sprite.style`` with a new ``Style``
      instance is allowed.  There is no observer/notification when the
      style changes — the renderer simply reads the current value each
      frame.
    - **Separate from Entity.x / Entity.y.**  The Sprite defines
      *appearance* only, not position.  Position is determined by the
      Entity's ``x``/``y`` or by a :class:`~wyby.position.Position`
      component.  The renderer combines position and sprite to place
      the character in the CellBuffer.
    - **No built-in animation.**  Sprite holds a single character and
      style.  For animation, swap the char/style from your game logic
      each tick, or implement a dedicated animation component.
    - **Terminal colour support varies.**  The style's colours will be
      downgraded by the renderer to match the terminal's capabilities
      (truecolor, 256-colour, or 16-colour).  What you specify may
      not be what the user sees.  See :mod:`wyby.color` for details
      on colour fallback.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from wyby.component import Component

if TYPE_CHECKING:
    from rich.style import Style

_logger = logging.getLogger(__name__)

# Default character for sprites when none is specified.
_DEFAULT_CHAR = "@"


class Sprite(Component):
    """Visual appearance component: one character plus a Rich Style.

    Stores a single display character and a :class:`~rich.style.Style`
    that defines foreground colour, background colour, bold, dim, etc.
    The renderer reads these values to place the entity in the
    :class:`~wyby.grid.CellBuffer`.

    Args:
        char: A single character string.  Defaults to ``"@"``.
        style: A :class:`rich.style.Style` instance.  Defaults to
            ``Style.null()`` (no styling — terminal defaults).

    Raises:
        TypeError: If *char* is not a string.
        ValueError: If *char* is not exactly one character long.
        TypeError: If *style* is not a :class:`rich.style.Style` instance.

    Caveats:
        - **Single character only.**  Multi-character strings, empty
          strings, and non-string types are rejected.  For multi-cell
          visuals, use multiple entities or draw directly into the
          CellBuffer.
        - **Zero-width characters are rejected.**  Combining marks,
          control characters, and other zero-width codepoints cannot
          occupy a terminal cell and are not valid sprite characters.
        - **Wide characters are allowed but use 2 cells.**  CJK
          ideographs and fullwidth forms are accepted as the char
          value, but they occupy 2 terminal columns.  The renderer
          must handle the extra width.  See :func:`~wyby.unicode.char_width`.
        - **Only some Style attributes are rendered.**  The CellBuffer
          only supports ``color``, ``bgcolor``, ``bold``, and ``dim``.
          Other Rich Style attributes (italic, underline, blink,
          reverse, strike) are silently ignored at render time.
        - **Style.null() is the default.**  An unstyled sprite uses
          the terminal's default foreground and background colours.
          This is usually fine but means the appearance depends on the
          user's terminal theme.
    """

    __slots__ = ("_char", "_style")

    def __init__(
        self,
        char: str = _DEFAULT_CHAR,
        style: Style | None = None,
    ) -> None:
        super().__init__()

        # Validate and store char.
        if not isinstance(char, str):
            raise TypeError(
                f"char must be a string, got {type(char).__name__}"
            )
        if len(char) != 1:
            raise ValueError(
                f"char must be exactly one character, got {char!r} "
                f"(length {len(char)})"
            )

        # Reject zero-width characters — they can't occupy a cell.
        from wyby.unicode import char_width as _char_width
        if _char_width(char) == 0:
            raise ValueError(
                f"char must have non-zero display width, got {char!r} "
                f"(a zero-width character cannot occupy a terminal cell)"
            )

        self._char = char

        # Validate and store style.
        if style is None:
            from rich.style import Style as _Style
            style = _Style.null()
        else:
            from rich.style import Style as _Style
            if not isinstance(style, _Style):
                raise TypeError(
                    f"style must be a rich.style.Style instance, "
                    f"got {type(style).__name__}"
                )
        self._style = style

    @property
    def char(self) -> str:
        """The display character for this sprite."""
        return self._char

    @char.setter
    def char(self, value: str) -> None:
        if not isinstance(value, str):
            raise TypeError(
                f"char must be a string, got {type(value).__name__}"
            )
        if len(value) != 1:
            raise ValueError(
                f"char must be exactly one character, got {value!r} "
                f"(length {len(value)})"
            )
        from wyby.unicode import char_width as _char_width
        if _char_width(value) == 0:
            raise ValueError(
                f"char must have non-zero display width, got {value!r} "
                f"(a zero-width character cannot occupy a terminal cell)"
            )
        self._char = value

    @property
    def style(self) -> Style:
        """The Rich Style for this sprite.

        Caveats:
            - Rich ``Style`` objects are immutable.  To change the
              style, assign a new ``Style`` instance.
            - Only ``color``, ``bgcolor``, ``bold``, and ``dim`` are
              used by the CellBuffer renderer.  Other attributes are
              silently ignored.
        """
        return self._style

    @style.setter
    def style(self, value: Style) -> None:
        from rich.style import Style as _Style
        if not isinstance(value, _Style):
            raise TypeError(
                f"style must be a rich.style.Style instance, "
                f"got {type(value).__name__}"
            )
        self._style = value

    def __repr__(self) -> str:
        entity_info = (
            f"entity_id={self._entity.id}" if self._entity is not None
            else "detached"
        )
        return f"Sprite(char={self._char!r}, {entity_info})"
