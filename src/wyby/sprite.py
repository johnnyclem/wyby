"""Sprite component for entity visual appearance.

Provides a :class:`Sprite` component that stores a character and a Rich
:class:`~rich.style.Style`, defining how an entity looks when rendered
into a :class:`~wyby.grid.CellBuffer`.

Also provides :func:`from_text`, a factory function that converts
multi-line ASCII art into positioned :class:`~wyby.entity.Entity`
instances, each carrying a :class:`Sprite` component.

Usage::

    from wyby.entity import Entity
    from wyby.sprite import Sprite, from_text
    from rich.style import Style

    e = Entity(5, 3)
    s = Sprite("@", Style(color="green", bold=True))
    e.add_component(s)

    # Read back
    assert s.char == "@"
    assert s.style.color.name == "green"

    # Load ASCII art as entities
    entities = from_text("###\\n# #\\n###")
    # → 8 entities (the spaces are skipped), positioned at grid coords

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
    from wyby.entity import Entity

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


def from_text(
    text: str,
    *,
    origin_x: int = 0,
    origin_y: int = 0,
    style: Style | None = None,
    skip_whitespace: bool = True,
) -> list[Entity]:
    """Create entities with Sprite components from a multi-line text block.

    Each visible character in *text* becomes a separate
    :class:`~wyby.entity.Entity` at the character's grid coordinates
    (offset by *origin_x*, *origin_y*), with a :class:`Sprite` component
    carrying that character and the given *style*.

    This is the primary way to load ASCII art into a scene::

        from wyby.sprite import from_text

        entities = from_text(
            "###\\n"
            "# #\\n"
            "###",
            origin_x=5, origin_y=2,
            style=Style(color="green"),
        )
        for e in entities:
            scene.add_entity(e)

    Args:
        text: The text block to convert.  Lines are split on ``'\\n'``.
            Carriage returns (``'\\r'``) are stripped.
        origin_x: X offset added to every entity's x position.
            Defaults to 0.
        origin_y: Y offset added to every entity's y position.
            Defaults to 0.
        style: Optional :class:`~rich.style.Style` applied to every
            Sprite.  Defaults to ``Style.null()`` (terminal defaults).
        skip_whitespace: If ``True`` (the default), space characters
            (``' '``) do not produce entities.  Set to ``False`` to
            create entities for spaces (useful for opaque backgrounds
            or overwriting underlying content).

    Returns:
        A list of :class:`~wyby.entity.Entity` instances, each with a
        :class:`Sprite` component.  Entities are ordered top-to-bottom,
        left-to-right (row 0 first, then row 1, etc.).  The list is
        empty if the text contains no qualifying characters.

    Raises:
        TypeError: If *text* is not a string.
        TypeError: If *origin_x* or *origin_y* is not an int.
        ValueError: If *text* is empty or contains only whitespace.

    Caveats:
        - **Each character becomes a separate entity.**  A 10×5 block of
          text can produce up to 50 entities.  For large ASCII art (maps,
          backgrounds), this may be more entities than you want.  Consider
          drawing large static text directly into the
          :class:`~wyby.grid.CellBuffer` via :meth:`~wyby.grid.CellBuffer.put_text`
          instead, and reserve ``from_text`` for small game objects
          (sprites, UI elements, decorations).
        - **Zero-width characters are skipped.**  Combining marks, control
          characters, and other zero-width codepoints (as determined by
          :func:`~wyby.unicode.char_width`) cannot occupy a terminal cell
          and are silently skipped.  They will not produce entities.
        - **Wide characters (CJK) advance by 2 columns.**  A wide
          character placed at column *x* causes the next character to be
          placed at *x + 2*, matching how :meth:`~wyby.grid.CellBuffer.put_text`
          handles wide characters.  The entity's ``x`` position reflects
          the character's left column.
        - **Tab characters are not expanded.**  Tabs (``'\\t'``) are
          treated as single characters.  If your text contains tabs,
          expand them to spaces before calling ``from_text``
          (e.g. ``text.expandtabs(4)``).
        - **Trailing whitespace matters.**  Lines are not stripped.  If a
          line has trailing spaces and *skip_whitespace* is ``False``,
          those spaces become entities.  Use ``textwrap.dedent`` and
          ``str.strip`` to normalise indentation if needed.
        - **Entities have auto-assigned IDs.**  Each entity gets a unique
          ID from the module-level counter.  IDs are not deterministic
          across calls — if you need stable IDs (for save/load), assign
          them explicitly after creation.
        - **No built-in per-character styling.**  All entities share the
          same *style*.  For multi-colour ASCII art, call ``from_text``
          once per colour region, or modify individual Sprite styles after
          creation.
        - **Newline handling.**  Only ``'\\n'`` is recognised as a line
          separator.  ``'\\r\\n'`` (Windows) is handled by stripping
          ``'\\r'``.  Bare ``'\\r'`` (old Mac) is also stripped, but does
          not act as a line separator on its own.
    """
    if not isinstance(text, str):
        raise TypeError(
            f"text must be a string, got {type(text).__name__}"
        )
    if not isinstance(origin_x, int) or isinstance(origin_x, bool):
        raise TypeError(
            f"origin_x must be an int, got {type(origin_x).__name__}"
        )
    if not isinstance(origin_y, int) or isinstance(origin_y, bool):
        raise TypeError(
            f"origin_y must be an int, got {type(origin_y).__name__}"
        )

    # Strip carriage returns for cross-platform compatibility.
    cleaned = text.replace("\r", "")
    if not cleaned or cleaned.isspace():
        raise ValueError("text must not be empty or contain only whitespace")

    from wyby.entity import Entity as _Entity
    from wyby.unicode import char_width as _char_width

    entities: list[_Entity] = []
    lines = cleaned.split("\n")

    for row, line in enumerate(lines):
        col = 0
        for char in line:
            w = _char_width(char)

            # Skip zero-width characters — they can't fill a cell.
            if w == 0:
                continue

            # Skip spaces if requested.
            if skip_whitespace and char == " ":
                col += w
                continue

            entity = _Entity(
                x=origin_x + col,
                y=origin_y + row,
            )
            entity.add_component(Sprite(char, style))
            entities.append(entity)

            col += w

    _logger.debug(
        "from_text created %d entities from %d lines",
        len(entities), len(lines),
    )
    return entities
