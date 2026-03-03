"""Sprite component for entity visual appearance.

Provides a :class:`Sprite` component that stores a character and a Rich
:class:`~rich.style.Style`, defining how an entity looks when rendered
into a :class:`~wyby.grid.CellBuffer`.

Also provides :func:`from_text`, a factory function that converts
multi-line ASCII art into positioned :class:`~wyby.entity.Entity`
instances, each carrying a :class:`Sprite` component, and
:func:`from_image`, a factory function that converts a Pillow
:class:`~PIL.Image.Image` into positioned entities with per-pixel
colour styling.

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

    # Load a Pillow image as entities (requires Pillow)
    from PIL import Image
    from wyby.sprite import from_image
    img = Image.new("RGB", (4, 3), color=(255, 0, 0))
    entities = from_image(img, origin_x=5)
    # → 12 entities, each a red "█" block

Caveats:
    - **Single grapheme cluster only.**  The ``char`` must be exactly one
      grapheme cluster — a single user-perceived character, which may
      consist of one or more Unicode codepoints.  Multi-character strings
      that form multiple grapheme clusters are rejected.  For multi-cell
      visuals, use multiple entities or write directly to the
      :class:`~wyby.grid.CellBuffer`.
    - **Emoji with variation selectors are supported.**  Characters like
      ``"❤\\uFE0F"`` (heart + VS16) and ``"⚔\\uFE0F"`` (swords + VS16) are
      accepted as a single grapheme cluster.  VS16 (U+FE0F) requests
      emoji presentation, which most modern terminals render at 2 columns
      wide.  VS15 (U+FE0E) requests text presentation at 1 column.
    - **Emoji width is terminal-dependent and unreliable.**  Different
      terminals render emoji at different widths.  The width reported by
      :func:`~wyby.unicode.grapheme_width` may not match what the user's
      terminal actually displays.  Width mismatches cause column alignment
      issues in the :class:`~wyby.grid.CellBuffer`.  Stick to ASCII and
      simple Unicode for game tiles where alignment matters.  See
      :mod:`wyby.unicode` for full caveats.
    - **Unicode width is not enforced.**  The char is stored as-is.
      Wide characters (CJK ideographs, fullwidth forms) occupy 2
      terminal cells but are stored as a single ``char``.  The
      renderer must account for display width via
      :func:`~wyby.unicode.grapheme_width`.
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
    from PIL import Image
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
        char: A single grapheme cluster string (one user-perceived
            character, which may be multiple Unicode codepoints for
            emoji with variation selectors).  Defaults to ``"@"``.
        style: A :class:`rich.style.Style` instance.  Defaults to
            ``Style.null()`` (no styling — terminal defaults).

    Raises:
        TypeError: If *char* is not a string.
        ValueError: If *char* is not a single grapheme cluster.
        TypeError: If *style* is not a :class:`rich.style.Style` instance.

    Caveats:
        - **Single grapheme cluster only.**  Multi-cluster strings, empty
          strings, and non-string types are rejected.  For multi-cell
          visuals, use multiple entities or draw directly into the
          CellBuffer.
        - **Emoji with variation selectors are accepted.**  Characters
          like ``"❤\\uFE0F"`` (heart + VS16) are valid — they form a
          single grapheme cluster.  VS16 (U+FE0F) requests emoji
          presentation, typically rendered at 2 columns wide.  However,
          **emoji width is terminal-dependent** — the width reported by
          :func:`~wyby.unicode.grapheme_width` may not match the
          terminal's actual rendering.
        - **Zero-width graphemes are rejected.**  Combining marks,
          control characters, and other zero-width codepoints cannot
          occupy a terminal cell and are not valid sprite characters.
        - **Wide characters are allowed but use 2 cells.**  CJK
          ideographs, fullwidth forms, and emoji with VS16 are accepted
          as the char value, but they occupy 2 terminal columns.  The
          renderer must handle the extra width.  See
          :func:`~wyby.unicode.grapheme_width`.
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
        if len(char) == 0:
            raise ValueError("char must not be empty")
        # Accept single grapheme clusters (e.g. emoji + variation selector).
        # Single codepoints are the common case and skip grapheme
        # segmentation for performance.
        if len(char) > 1:
            from wyby.unicode import is_single_grapheme as _is_single_grapheme
            if not _is_single_grapheme(char):
                raise ValueError(
                    f"char must be a single grapheme cluster, got {char!r} "
                    f"(length {len(char)})"
                )

        # Reject zero-width graphemes — they can't occupy a cell.
        from wyby.unicode import grapheme_width as _grapheme_width
        if _grapheme_width(char) == 0:
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
        if len(value) == 0:
            raise ValueError("char must not be empty")
        if len(value) > 1:
            from wyby.unicode import is_single_grapheme as _is_single_grapheme
            if not _is_single_grapheme(value):
                raise ValueError(
                    f"char must be a single grapheme cluster, got {value!r} "
                    f"(length {len(value)})"
                )
        from wyby.unicode import grapheme_width as _grapheme_width
        if _grapheme_width(value) == 0:
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
        - **Emoji with variation selectors are supported.**  Characters
          like ``"❤\\uFE0F"`` (heart + VS16) are treated as single grapheme
          clusters and produce one entity each.  Emoji with VS16 advance
          by 2 columns (emoji presentation width).  However, **emoji
          width is terminal-dependent** — the width reported by
          :func:`~wyby.unicode.grapheme_width` may not match what the
          user's terminal actually displays.
        - **Zero-width characters are skipped.**  Combining marks, control
          characters, and other zero-width codepoints (as determined by
          :func:`~wyby.unicode.grapheme_width`) cannot occupy a terminal
          cell and are silently skipped.  They will not produce entities.
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
    from wyby.unicode import grapheme_width as _grapheme_width
    from wyby.unicode import iter_grapheme_clusters as _iter_clusters

    entities: list[_Entity] = []
    lines = cleaned.split("\n")

    for row, line in enumerate(lines):
        col = 0
        for grapheme in _iter_clusters(line):
            w = _grapheme_width(grapheme)

            # Skip zero-width graphemes — they can't fill a cell.
            if w == 0:
                continue

            # Skip spaces if requested.
            if skip_whitespace and grapheme == " ":
                col += w
                continue

            entity = _Entity(
                x=origin_x + col,
                y=origin_y + row,
            )
            entity.add_component(Sprite(grapheme, style))
            entities.append(entity)

            col += w

    _logger.debug(
        "from_text created %d entities from %d lines",
        len(entities), len(lines),
    )
    return entities


# Default character for from_image — full block fills a terminal cell.
_DEFAULT_IMAGE_CHAR = "\u2588"


def from_image(
    image: Image.Image,
    *,
    origin_x: int = 0,
    origin_y: int = 0,
    char: str = _DEFAULT_IMAGE_CHAR,
    skip_alpha: bool = True,
    alpha_threshold: int = 0,
) -> list[Entity]:
    """Create entities with Sprite components from a Pillow image.

    Each pixel in *image* becomes a separate
    :class:`~wyby.entity.Entity` at the pixel's grid coordinates
    (offset by *origin_x*, *origin_y*), with a :class:`Sprite` component
    carrying *char* styled with the pixel's colour as the foreground.

    Requires the ``Pillow`` library (``pip install wyby[image]``).

    Example::

        from PIL import Image
        from wyby.sprite import from_image

        img = Image.open("hero.png").resize((8, 8))
        entities = from_image(img, origin_x=5, origin_y=2)
        for e in entities:
            scene.add_entity(e)

    Args:
        image: A Pillow :class:`~PIL.Image.Image` instance.  Any mode
            is accepted — the image is converted to ``"RGBA"`` internally.
        origin_x: X offset added to every entity's x position.
            Defaults to 0.
        origin_y: Y offset added to every entity's y position.
            Defaults to 0.
        char: The character used for every pixel's Sprite.  Defaults to
            ``"█"`` (U+2588, full block), which fills a terminal cell
            completely.
        skip_alpha: If ``True`` (the default), fully transparent pixels
            (alpha <= *alpha_threshold*) do not produce entities.  Set to
            ``False`` to create entities for all pixels regardless of
            alpha.
        alpha_threshold: Alpha value at or below which a pixel is
            considered transparent when *skip_alpha* is ``True``.
            Defaults to 0 (only fully transparent pixels are skipped).
            Range: 0–255.

    Returns:
        A list of :class:`~wyby.entity.Entity` instances, each with a
        :class:`Sprite` component.  Entities are ordered top-to-bottom,
        left-to-right (row 0 first, then row 1, etc.).  The list is
        empty if all pixels are transparent and *skip_alpha* is ``True``.

    Raises:
        ImportError: If Pillow is not installed.
        TypeError: If *image* is not a :class:`~PIL.Image.Image` instance.
        TypeError: If *origin_x* or *origin_y* is not an int.
        TypeError: If *char* is not a string.
        ValueError: If *char* is not exactly one character.
        ValueError: If *alpha_threshold* is outside 0–255.
        ValueError: If the image has zero width or height.

    Caveats:
        - **Conversion is expensive — call at load time, not per-frame.**
          This function iterates every pixel, allocates an Entity + Sprite +
          Style per opaque pixel, and converts the image to RGBA internally.
          For a 40×20 image, that is 800 object allocations plus Pillow
          pixel-access overhead.  At 100×50 (5 000 pixels) the cost is
          significant.  **Always** convert once at load time and cache the
          returned entity list.  Never call ``from_image`` inside a game
          loop or per-frame callback.  Use
          :func:`~wyby.render_warnings.estimate_image_conversion_cost` to
          check cost before converting, and
          :func:`~wyby.render_warnings.log_image_conversion_cost` to log
          warnings for large images.
        - **Pre-processing adds further cost.**  If you use
          :func:`~wyby.dithering.prepare_for_terminal` or
          :func:`~wyby.dithering.quantize_for_terminal` before calling
          ``from_image``, those functions perform resizing, colour
          quantization, and optional Floyd-Steinberg dithering — each an
          *O(width × height)* operation.  The full pipeline
          (resize → aspect-correct → quantize → from_image) may take
          hundreds of milliseconds for large images.  Do it once at
          startup or behind a loading screen.
        - **Quantization.**  A typical image may contain thousands of
          unique colours.  Terminals support at most 16 million (truecolor),
          256, or 16 colours depending on capability.  More importantly,
          each unique colour means a unique Rich :class:`~rich.style.Style`
          object.  For large images, reduce the palette *before* calling
          ``from_image`` using Pillow's quantization::

              # Reduce to 16 colours (good for ANSI terminals)
              img = img.quantize(colors=16).convert("RGBA")

              # Or use adaptive palette with dithering
              img = img.quantize(colors=64, dither=Image.Dither.FLOYDSTEINBERG)
              img = img.convert("RGBA")

          Quantizing first keeps entity count the same but dramatically
          reduces the number of distinct styles, which improves rendering
          performance and produces output that maps well to limited terminal
          palettes.  See :mod:`wyby.color` for terminal colour downgrade
          utilities.
        - **Each pixel becomes a separate entity.**  A 40×20 image produces
          up to 800 entities.  For anything larger, consider resizing the
          image first (``image.resize((cols, rows))``) or drawing directly
          into the :class:`~wyby.grid.CellBuffer`.  Reserve ``from_image``
          for small sprites and icons.
        - **Terminal aspect ratio.**  Terminal cells are typically ~2:1
          (taller than wide).  A square image will appear stretched
          vertically.  To compensate, resize the image to half height
          before conversion::

              w, h = img.size
              img = img.resize((w, h // 2))

          Or use a half-block character (``"▀"`` or ``"▄"``) and a
          custom rendering approach for 2-pixel-per-cell output.
        - **Alpha handling.**  Pillow modes without alpha (``"RGB"``,
          ``"L"``, ``"P"`` without transparency) are converted to
          ``"RGBA"`` with alpha=255 (fully opaque).  All pixels will
          produce entities unless *skip_alpha* is ``False``.
        - **Colour format.**  Pixel colours are emitted as hex strings
          (``"#rrggbb"``) in the Rich Style.  These are truecolor values.
          On terminals that do not support truecolor, Rich will
          automatically downgrade to the nearest available colour.  For
          explicit control, use :func:`~wyby.color.downgrade_color` on
          the styles after creation.
        - **Greyscale images.**  Greyscale (``"L"``) and palette (``"P"``)
          images are converted to ``"RGBA"`` before processing.  The
          greyscale value becomes an RGB triplet (e.g. grey 128 becomes
          ``#808080``).
        - **Entities have auto-assigned IDs**, same as :func:`from_text`.
        - **No built-in animation.**  For animated sprites from image
          sequences (GIF frames), call ``from_image`` per frame and swap
          entity lists in your game loop.
    """
    try:
        from PIL import Image as _PILImage
    except ImportError:
        raise ImportError(
            "Pillow is required for from_image(). "
            "Install it with: pip install wyby[image]"
        ) from None

    # Validate image type.
    if not isinstance(image, _PILImage.Image):
        raise TypeError(
            f"image must be a PIL.Image.Image instance, "
            f"got {type(image).__name__}"
        )

    # Validate origin types.
    if not isinstance(origin_x, int) or isinstance(origin_x, bool):
        raise TypeError(
            f"origin_x must be an int, got {type(origin_x).__name__}"
        )
    if not isinstance(origin_y, int) or isinstance(origin_y, bool):
        raise TypeError(
            f"origin_y must be an int, got {type(origin_y).__name__}"
        )

    # Validate char — accepts single grapheme clusters (e.g. emoji
    # with variation selectors like "❤\uFE0F").
    if not isinstance(char, str):
        raise TypeError(
            f"char must be a string, got {type(char).__name__}"
        )
    if len(char) == 0:
        raise ValueError("char must not be empty")
    if len(char) > 1:
        from wyby.unicode import is_single_grapheme as _is_single_grapheme
        if not _is_single_grapheme(char):
            raise ValueError(
                f"char must be a single grapheme cluster, got {char!r} "
                f"(length {len(char)})"
            )
    from wyby.unicode import grapheme_width as _grapheme_width
    if _grapheme_width(char) == 0:
        raise ValueError(
            f"char must have non-zero display width, got {char!r} "
            f"(a zero-width character cannot occupy a terminal cell)"
        )

    # Validate alpha_threshold.
    if not isinstance(alpha_threshold, int) or isinstance(alpha_threshold, bool):
        raise TypeError(
            f"alpha_threshold must be an int, got {type(alpha_threshold).__name__}"
        )
    if alpha_threshold < 0 or alpha_threshold > 255:
        raise ValueError(
            f"alpha_threshold must be 0–255, got {alpha_threshold}"
        )

    # Validate image dimensions.
    width, height = image.size
    if width == 0 or height == 0:
        raise ValueError(
            f"image must have non-zero dimensions, got {width}x{height}"
        )

    # Log a warning if the image is large enough to cause a noticeable
    # conversion pause.  This uses the image conversion cost estimator
    # from render_warnings — the same pattern as log_render_cost() for
    # grid dimensions.
    from wyby.render_warnings import log_image_conversion_cost as _log_conv_cost
    _log_conv_cost(
        width, height,
        has_alpha=skip_alpha and image.mode in ("RGBA", "LA", "PA"),
    )

    # Convert to RGBA for uniform pixel access.
    rgba = image.convert("RGBA")

    from rich.style import Style as _Style
    from wyby.entity import Entity as _Entity

    entities: list[_Entity] = []
    pixels = rgba.load()

    for row in range(height):
        for col in range(width):
            r, g, b, a = pixels[col, row]

            # Skip transparent pixels if requested.
            if skip_alpha and a <= alpha_threshold:
                continue

            hex_color = f"#{r:02x}{g:02x}{b:02x}"
            style = _Style(color=hex_color)

            entity = _Entity(
                x=origin_x + col,
                y=origin_y + row,
            )
            entity.add_component(Sprite(char, style))
            entities.append(entity)

    _logger.debug(
        "from_image created %d entities from %dx%d image",
        len(entities), width, height,
    )
    return entities


def load_sprite_sheet(
    text: str,
    frame_width: int,
    frame_height: int,
    *,
    names: list[str] | None = None,
    origin_x: int = 0,
    origin_y: int = 0,
    style: Style | None = None,
    skip_whitespace: bool = True,
) -> dict[str, list[Entity]]:
    """Extract fixed-size sprite frames from a text-based sprite sheet.

    Treats *text* as a grid of character cells and slices it into
    rectangular frames of *frame_width* × *frame_height*.  Frames are
    read left-to-right, then top-to-bottom (row-major order).  Each
    frame is converted to a list of :class:`~wyby.entity.Entity`
    instances using the same logic as :func:`from_text`.

    Example — a sprite sheet with two 3×3 frames side by side::

        sheet = (
            "###.@.\\n"
            "# #.@.\\n"
            "###.@."
        )
        frames = load_sprite_sheet(sheet, frame_width=3, frame_height=3)
        # frames["0"] → 8 entities (the '#' box)
        # frames["1"] → 3 entities (the '@' column)

    Args:
        text: The sprite sheet text.  Lines are split on ``'\\n'``.
            Carriage returns (``'\\r'``) are stripped.
        frame_width: Width of each frame in columns.  Must be >= 1.
        frame_height: Height of each frame in rows.  Must be >= 1.
        names: Optional list of names for the extracted frames.  If
            provided, its length must match the number of frames in the
            sheet.  If ``None``, frames are named ``"0"``, ``"1"``, etc.
        origin_x: X offset applied to every entity within each frame.
            Defaults to 0.  Entity positions are relative to the
            frame's top-left corner, not the sheet.
        origin_y: Y offset applied to every entity within each frame.
            Defaults to 0.
        style: Optional :class:`~rich.style.Style` applied to every
            Sprite.  Defaults to ``Style.null()`` (terminal defaults).
        skip_whitespace: If ``True`` (the default), space characters
            do not produce entities.  Set to ``False`` to include
            spaces.

    Returns:
        A dict mapping frame name → list of
        :class:`~wyby.entity.Entity`.  Each entity carries a
        :class:`Sprite` component.  Entity positions are relative to
        the frame's own top-left corner (offset by *origin_x*,
        *origin_y*), **not** the sheet coordinates.

    Raises:
        TypeError: If *text* is not a string.
        TypeError: If *frame_width* or *frame_height* is not an int.
        TypeError: If *origin_x* or *origin_y* is not an int.
        ValueError: If *text* is empty.
        ValueError: If *frame_width* or *frame_height* is less than 1.
        ValueError: If *names* length does not match the frame count.

    Caveats:
        - **Frames must tile evenly.**  Columns that don't fill a
          complete frame width are ignored (truncated).  Rows that
          don't fill a complete frame height are ignored.  No warning
          is emitted — check your sheet dimensions if frames are
          missing.
        - **Each character becomes a separate entity.**  The same
          memory caveat as :func:`from_text` applies — a 10×10 frame
          produces up to 100 entities.  For large frames, consider
          drawing directly into the :class:`~wyby.grid.CellBuffer`.
        - **Short lines are padded with spaces.**  If a line in the
          sheet is shorter than the full sheet width, missing columns
          are treated as spaces.  This means frames near the right edge
          of short lines may contain fewer entities than expected.
        - **Wide characters (CJK) advance by 2 columns** within a
          frame, same as :func:`from_text`.  A wide character that
          straddles a frame boundary will be included in the left
          frame.
        - **No per-frame styling.**  All frames share the same *style*.
          To apply different styles per frame, modify the Sprite styles
          on the returned entities after extraction.
        - **Frame names must be unique.**  If *names* contains
          duplicates, later frames overwrite earlier ones in the
          returned dict.
        - **Entities have auto-assigned IDs**, same as :func:`from_text`.
    """
    # --- Validate types ---
    if not isinstance(text, str):
        raise TypeError(
            f"text must be a string, got {type(text).__name__}"
        )
    if not isinstance(frame_width, int) or isinstance(frame_width, bool):
        raise TypeError(
            f"frame_width must be an int, got {type(frame_width).__name__}"
        )
    if not isinstance(frame_height, int) or isinstance(frame_height, bool):
        raise TypeError(
            f"frame_height must be an int, got {type(frame_height).__name__}"
        )
    if not isinstance(origin_x, int) or isinstance(origin_x, bool):
        raise TypeError(
            f"origin_x must be an int, got {type(origin_x).__name__}"
        )
    if not isinstance(origin_y, int) or isinstance(origin_y, bool):
        raise TypeError(
            f"origin_y must be an int, got {type(origin_y).__name__}"
        )

    # --- Validate values ---
    cleaned = text.replace("\r", "")
    if not cleaned:
        raise ValueError("text must not be empty")
    if frame_width < 1:
        raise ValueError(
            f"frame_width must be >= 1, got {frame_width}"
        )
    if frame_height < 1:
        raise ValueError(
            f"frame_height must be >= 1, got {frame_height}"
        )

    from wyby.entity import Entity as _Entity
    from wyby.unicode import grapheme_string_width as _string_width
    from wyby.unicode import grapheme_width as _grapheme_width
    from wyby.unicode import iter_grapheme_clusters as _iter_clusters

    lines = cleaned.split("\n")

    # Determine sheet dimensions in display columns (not codepoints).
    # Wide characters (CJK, emoji) occupy 2 columns, so len() is wrong.
    sheet_width = max(_string_width(line) for line in lines) if lines else 0
    sheet_height = len(lines)

    # Number of frames that fit in each direction.
    cols_of_frames = sheet_width // frame_width
    rows_of_frames = sheet_height // frame_height
    total_frames = cols_of_frames * rows_of_frames

    # Validate names if provided.
    if names is not None:
        if len(names) != total_frames:
            raise ValueError(
                f"names length ({len(names)}) does not match frame count "
                f"({total_frames})"
            )

    frames: dict[str, list[_Entity]] = {}

    for frame_idx in range(total_frames):
        # Grid position of this frame in the sheet.
        fc = frame_idx % cols_of_frames
        fr = frame_idx // cols_of_frames

        # Character offsets into the sheet.
        x_start = fc * frame_width
        y_start = fr * frame_height

        frame_name = names[frame_idx] if names is not None else str(frame_idx)
        entities: list[_Entity] = []

        for row_offset in range(frame_height):
            line_idx = y_start + row_offset
            if line_idx >= len(lines):
                break
            line = lines[line_idx]

            # Walk grapheme clusters to find those within our frame's
            # column range.  We must track column positions because
            # wide characters advance by 2.
            col = 0
            for grapheme in _iter_clusters(line):
                w = _grapheme_width(grapheme)
                if w == 0:
                    continue

                # Check if this grapheme starts within our frame's
                # column range.
                if col >= x_start and col < x_start + frame_width:
                    if not (skip_whitespace and grapheme == " "):
                        entity = _Entity(
                            x=origin_x + (col - x_start),
                            y=origin_y + row_offset,
                        )
                        entity.add_component(Sprite(grapheme, style))
                        entities.append(entity)

                col += w

                # Past this frame's columns — skip rest of line.
                if col >= x_start + frame_width:
                    break

        frames[frame_name] = entities

    _logger.debug(
        "load_sprite_sheet extracted %d frames (%d×%d each) from %d×%d sheet",
        total_frames, frame_width, frame_height, sheet_width, sheet_height,
    )
    return frames
