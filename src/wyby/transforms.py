"""Sprite transforms: tint and flip/rotate.

Provides functions to apply colour tints and spatial transforms (flip,
rotate) to entities carrying :class:`~wyby.sprite.Sprite` components.

The main entry points are:

- :func:`tint` — blend a colour overlay into every Sprite's foreground.
- :func:`flip_h` — mirror entity positions horizontally.
- :func:`flip_v` — mirror entity positions vertically.
- :func:`rotate_90` — rotate entity positions 90° clockwise.
- :func:`rotate_180` — rotate entity positions 180°.
- :func:`rotate_270` — rotate entity positions 270° clockwise.

These operate on lists of entities (as returned by :func:`~wyby.sprite.from_text`
and :func:`~wyby.sprite.from_image`) and mutate positions/styles in place.

Caveats:
    - **Tint blends in sRGB space.**  Linear interpolation in sRGB is
      not perceptually uniform.  Midpoint blends may appear darker than
      expected, especially for saturated colours.  This is acceptable
      for game-style tinting (damage flash, poison overlay) but not
      suitable for colour-accurate workflows.
    - **Tint on unstyled sprites.**  If a sprite has no foreground colour
      (``Style.null()``), tinting sets the foreground to the tint colour
      at the given strength blended against white ``(255, 255, 255)`` as
      a stand-in for the unknown terminal default.  The result may not
      match the actual terminal foreground.
    - **Character remapping is limited.**  Flip and rotate attempt to
      remap directional characters (``/`` ↔ ``\\``, box-drawing corners,
      brackets) to their transformed equivalents.  Most ASCII characters
      have **no** rotational or mirror equivalent — they are left
      unchanged.  The remapping tables cover common roguelike and
      box-drawing characters only.
    - **90° rotation distorts aspect ratio.**  Terminal cells are ~2×
      taller than wide.  Rotating a 10×5 block 90° produces a 5×10
      block, but each cell is still ~1:2, so the rotated shape will
      appear stretched.  There is no automatic aspect-ratio correction.
    - **Positions may become negative.**  Flip and rotate preserve the
      relative shape but reposition entities around the group's bounding
      box.  If the original positions are near zero, transformed
      positions can go negative.  The caller should adjust positions
      afterward if needed.
    - **Empty lists are no-ops.**  Passing an empty entity list to any
      function returns immediately without error.
    - **Entities without Sprite are skipped** for tint and character
      remapping, but their positions are still transformed by flip/rotate.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from wyby.color import parse_color

if TYPE_CHECKING:
    from wyby.entity import Entity
    from wyby.sprite import Sprite

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Colour blending
# ---------------------------------------------------------------------------

# Fallback RGB when a sprite has no foreground colour.  White is a
# reasonable stand-in for typical terminal defaults (light-on-dark or
# dark-on-light themes both tend toward high-contrast foregrounds).
_DEFAULT_FG_RGB = (255, 255, 255)


def _blend_rgb(
    base: tuple[int, int, int],
    overlay: tuple[int, int, int],
    strength: float,
) -> tuple[int, int, int]:
    """Linear interpolation between two RGB colours.

    ``strength=0.0`` returns *base* unchanged; ``strength=1.0`` returns
    *overlay*.  Values in between produce a proportional blend.

    Caveat: blending in sRGB is not perceptually linear.
    """
    r = int(base[0] + (overlay[0] - base[0]) * strength + 0.5)
    g = int(base[1] + (overlay[1] - base[1]) * strength + 0.5)
    b = int(base[2] + (overlay[2] - base[2]) * strength + 0.5)
    return (
        max(0, min(255, r)),
        max(0, min(255, g)),
        max(0, min(255, b)),
    )


def _extract_fg_rgb(sprite: Sprite) -> tuple[int, int, int] | None:
    """Extract foreground RGB from a sprite's style, or None."""
    color = sprite.style.color
    if color is None:
        return None
    try:
        triplet = color.get_truecolor()
        return (triplet.red, triplet.green, triplet.blue)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Tint
# ---------------------------------------------------------------------------


def tint(
    entities: list[Entity],
    color: str,
    strength: float = 1.0,
) -> None:
    """Apply a colour tint to every entity's Sprite foreground.

    Blends each sprite's current foreground colour toward *color* by
    *strength* (0.0 = no change, 1.0 = fully replaced).  Useful for
    damage flashes, poison effects, team colouring, etc.

    Mutates sprites in place — does not create new entities.

    Args:
        entities: List of entities to tint (as returned by
            :func:`~wyby.sprite.from_text` or
            :func:`~wyby.sprite.from_image`).
        color: Target tint colour as a Rich colour string
            (``"#ff0000"``, ``"rgb(255,0,0)"``, ``"red"``, etc.).
            Parsed via :func:`~wyby.color.parse_color`.
        strength: Blend factor from 0.0 (no tint) to 1.0 (full tint).
            Defaults to 1.0.

    Raises:
        ValueError: If *color* cannot be parsed to RGB.
        ValueError: If *strength* is outside 0.0–1.0.
        TypeError: If *entities* is not a list.

    Caveats:
        - **sRGB blending is not perceptually uniform.**  Midpoint
          blends may appear darker than expected.  See module docstring.
        - **Sprites without foreground colour** are tinted against
          white (255, 255, 255) as a fallback.  The result depends
          on terminal theme.
        - **Background colour is not affected.**  Only the foreground
          (``style.color``) is tinted.  To tint the background, modify
          ``style.bgcolor`` directly.
        - **Tinting is lossy.**  Applying a tint discards the original
          colour.  To undo a tint, store the original style before
          tinting, or re-create the entities.
    """
    if not isinstance(entities, list):
        raise TypeError(
            f"entities must be a list, got {type(entities).__name__}"
        )
    if not isinstance(strength, (int, float)):
        raise ValueError(
            f"strength must be a float, got {type(strength).__name__}"
        )
    if strength < 0.0 or strength > 1.0:
        raise ValueError(
            f"strength must be between 0.0 and 1.0, got {strength}"
        )

    tint_rgb = parse_color(color)
    if tint_rgb is None:
        raise ValueError(f"cannot parse colour: {color!r}")

    if not entities:
        return

    from rich.style import Style as _Style
    from wyby.sprite import Sprite as _Sprite

    for entity in entities:
        sprite = entity.get_component(_Sprite)
        if sprite is None:
            continue

        base_rgb = _extract_fg_rgb(sprite)
        if base_rgb is None:
            base_rgb = _DEFAULT_FG_RGB

        blended = _blend_rgb(base_rgb, tint_rgb, strength)
        hex_color = f"#{blended[0]:02x}{blended[1]:02x}{blended[2]:02x}"

        # Preserve existing style attributes (bgcolor, bold, dim) while
        # replacing the foreground colour.
        old = sprite.style
        sprite.style = _Style(
            color=hex_color,
            bgcolor=old.bgcolor,
            bold=old.bold,
            dim=old.dim,
        )

    _logger.debug(
        "tint applied color=%s strength=%.2f to %d entities",
        color, strength, len(entities),
    )


# ---------------------------------------------------------------------------
# Character remapping tables for flip/rotate
# ---------------------------------------------------------------------------

# Horizontal flip: characters that mirror left-right.
_FLIP_H_CHARS: dict[str, str] = {
    "/": "\\", "\\": "/",
    "(": ")", ")": "(",
    "[": "]", "]": "[",
    "{": "}", "}": "{",
    "<": ">", ">": "<",
    # Box-drawing corners
    "\u250c": "\u2510", "\u2510": "\u250c",  # ┌ ↔ ┐
    "\u2514": "\u2518", "\u2518": "\u2514",  # └ ↔ ┘
    # Double-line box-drawing corners
    "\u2554": "\u2557", "\u2557": "\u2554",  # ╔ ↔ ╗
    "\u255a": "\u255d", "\u255d": "\u255a",  # ╚ ↔ ╝
    # T-junctions
    "\u251c": "\u2524", "\u2524": "\u251c",  # ├ ↔ ┤
    "\u2560": "\u2563", "\u2563": "\u2560",  # ╠ ↔ ╣
}

# Vertical flip: characters that mirror top-bottom.
_FLIP_V_CHARS: dict[str, str] = {
    "/": "\\", "\\": "/",
    "^": "v", "v": "^",
    # Box-drawing corners
    "\u250c": "\u2514", "\u2514": "\u250c",  # ┌ ↔ └
    "\u2510": "\u2518", "\u2518": "\u2510",  # ┐ ↔ ┘
    # Double-line box-drawing corners
    "\u2554": "\u255a", "\u255a": "\u2554",  # ╔ ↔ ╚
    "\u2557": "\u255d", "\u255d": "\u2557",  # ╗ ↔ ╝
    # T-junctions
    "\u252c": "\u2534", "\u2534": "\u252c",  # ┬ ↔ ┴
    "\u2566": "\u2569", "\u2569": "\u2566",  # ╦ ↔ ╩
    # Half blocks
    "\u2580": "\u2584", "\u2584": "\u2580",  # ▀ ↔ ▄
}

# 90° clockwise rotation character mapping.
# Caveat: most ASCII characters have no rotational equivalent.
# Only directional and box-drawing characters are mapped.
_ROTATE_90_CHARS: dict[str, str] = {
    # Lines
    "\u2500": "\u2502", "\u2502": "\u2500",  # ─ ↔ │
    "\u2550": "\u2551", "\u2551": "\u2550",  # ═ ↔ ║
    "-": "|", "|": "-",
    # Slashes are preserved — / rotated 90° CW is \ and vice versa
    # (imagine rotating the glyph: / becomes ‒ but closest is \)
    # Actually: rotating / 90° CW gives something like ‒ (horizontal),
    # but for game tiles, the common expectation is / ↔ \.
    # Box-drawing corners: ┌→┐→┘→└→┌ (clockwise cycle)
    "\u250c": "\u2510",  # ┌ → ┐
    "\u2510": "\u2518",  # ┐ → ┘
    "\u2518": "\u2514",  # ┘ → └
    "\u2514": "\u250c",  # └ → ┌
    # Double-line corners: ╔→╗→╝→╚→╔
    "\u2554": "\u2557",  # ╔ → ╗
    "\u2557": "\u255d",  # ╗ → ╝
    "\u255d": "\u255a",  # ╝ → ╚
    "\u255a": "\u2554",  # ╚ → ╔
    # T-junctions: ┬→┤→┴→├→┬
    "\u252c": "\u2524",  # ┬ → ┤
    "\u2524": "\u2534",  # ┤ → ┴
    "\u2534": "\u251c",  # ┴ → ├
    "\u251c": "\u252c",  # ├ → ┬
    # Arrows
    "^": ">", ">": "v", "v": "<", "<": "^",
}


def _remap_char(char: str, table: dict[str, str]) -> str:
    """Look up a character in a remapping table, returning it unchanged
    if no mapping exists."""
    return table.get(char, char)


# ---------------------------------------------------------------------------
# Bounding-box helper
# ---------------------------------------------------------------------------


def _bounding_box(
    entities: list[Entity],
) -> tuple[int, int, int, int]:
    """Return (min_x, min_y, max_x, max_y) of entity positions."""
    min_x = min(e.x for e in entities)
    min_y = min(e.y for e in entities)
    max_x = max(e.x for e in entities)
    max_y = max(e.y for e in entities)
    return min_x, min_y, max_x, max_y


# ---------------------------------------------------------------------------
# Flip
# ---------------------------------------------------------------------------


def flip_h(entities: list[Entity]) -> None:
    """Flip entities horizontally (mirror left-right).

    Mirrors entity positions across the vertical centre line of the
    group's bounding box.  Directional characters (slashes, brackets,
    box-drawing corners) are remapped to their mirrored equivalents.

    Mutates entities in place.

    Args:
        entities: List of entities to flip.

    Raises:
        TypeError: If *entities* is not a list.

    Caveats:
        - **Character remapping is best-effort.**  Only characters with
          known mirror equivalents are remapped (see ``_FLIP_H_CHARS``).
          Most ASCII characters (letters, digits, symbols) have no
          horizontal mirror and are left unchanged.
        - **Positions may shift.**  The flip is relative to the group's
          bounding box.  The leftmost entity becomes the rightmost and
          vice versa, preserving the min_x anchor.
        - **Entities without Sprite** have positions flipped but no
          character remapping.
    """
    if not isinstance(entities, list):
        raise TypeError(
            f"entities must be a list, got {type(entities).__name__}"
        )
    if len(entities) < 2:
        return

    from wyby.sprite import Sprite as _Sprite

    min_x, _, max_x, _ = _bounding_box(entities)

    for entity in entities:
        entity.x = max_x - (entity.x - min_x)

        sprite = entity.get_component(_Sprite)
        if sprite is not None:
            remapped = _remap_char(sprite.char, _FLIP_H_CHARS)
            if remapped != sprite.char:
                sprite.char = remapped


def flip_v(entities: list[Entity]) -> None:
    """Flip entities vertically (mirror top-bottom).

    Mirrors entity positions across the horizontal centre line of the
    group's bounding box.  Directional characters (slashes, half-blocks,
    box-drawing corners) are remapped to their mirrored equivalents.

    Mutates entities in place.

    Args:
        entities: List of entities to flip.

    Raises:
        TypeError: If *entities* is not a list.

    Caveats:
        - Same character-remapping and position caveats as :func:`flip_h`.
    """
    if not isinstance(entities, list):
        raise TypeError(
            f"entities must be a list, got {type(entities).__name__}"
        )
    if len(entities) < 2:
        return

    from wyby.sprite import Sprite as _Sprite

    _, min_y, _, max_y = _bounding_box(entities)

    for entity in entities:
        entity.y = max_y - (entity.y - min_y)

        sprite = entity.get_component(_Sprite)
        if sprite is not None:
            remapped = _remap_char(sprite.char, _FLIP_V_CHARS)
            if remapped != sprite.char:
                sprite.char = remapped


# ---------------------------------------------------------------------------
# Rotate
# ---------------------------------------------------------------------------


def rotate_90(entities: list[Entity]) -> None:
    """Rotate entities 90° clockwise.

    Transforms entity positions by rotating 90° clockwise around the
    group's bounding-box origin.  Directional characters are remapped
    where possible.

    The transformation is: ``(x, y) → (max_y - y + min_x, x - min_x + min_y)``
    which maps the top-left to top-right, etc.

    Mutates entities in place.

    Args:
        entities: List of entities to rotate.

    Raises:
        TypeError: If *entities* is not a list.

    Caveats:
        - **Aspect ratio distortion.**  Terminal cells are ~2× taller
          than wide.  A shape that was 10 wide × 5 tall becomes 5 wide
          × 10 tall after rotation, but each cell is still ~1:2, so the
          rotated shape will appear vertically stretched.  There is no
          automatic correction — adjust entity positions or cell size
          manually if needed.
        - **Character remapping is limited.**  ``─`` ↔ ``│`` and
          box-drawing corners are remapped, but most characters have no
          90° equivalent.  A letter "L" rotated 90° is not "⌐" — it
          stays "L".  For assets that need clean rotation, design
          separate sprite variants for each orientation.
    """
    if not isinstance(entities, list):
        raise TypeError(
            f"entities must be a list, got {type(entities).__name__}"
        )
    if len(entities) < 2:
        return

    from wyby.sprite import Sprite as _Sprite

    min_x, min_y, _, max_y = _bounding_box(entities)

    new_positions: list[tuple[int, int]] = []
    for entity in entities:
        # 90° CW: (x, y) → (max_y - y + min_x, x - min_x + min_y)
        new_x = (max_y - entity.y) + min_x
        new_y = (entity.x - min_x) + min_y
        new_positions.append((new_x, new_y))

    for entity, (nx, ny) in zip(entities, new_positions):
        entity.x = nx
        entity.y = ny

        sprite = entity.get_component(_Sprite)
        if sprite is not None:
            remapped = _remap_char(sprite.char, _ROTATE_90_CHARS)
            if remapped != sprite.char:
                sprite.char = remapped


def rotate_180(entities: list[Entity]) -> None:
    """Rotate entities 180°.

    Equivalent to :func:`flip_h` followed by :func:`flip_v`, but
    applied as a single transformation.  Characters with 180° mappings
    are remapped (which is the composition of the horizontal and
    vertical flip maps).

    Mutates entities in place.

    Args:
        entities: List of entities to rotate.

    Raises:
        TypeError: If *entities* is not a list.

    Caveats:
        - 180° rotation preserves aspect ratio (width and height stay
          the same), unlike 90°/270°.
        - Character remapping: ``┌`` ↔ ``┘``, ``┐`` ↔ ``└``, etc.
          Slashes map to themselves (``/`` rotated 180° is ``/``).
    """
    if not isinstance(entities, list):
        raise TypeError(
            f"entities must be a list, got {type(entities).__name__}"
        )
    if len(entities) < 2:
        return

    from wyby.sprite import Sprite as _Sprite

    min_x, min_y, max_x, max_y = _bounding_box(entities)

    # Build 180° char map as composition of H and V flips.
    rotate_180_chars: dict[str, str] = {}
    all_chars = set(_FLIP_H_CHARS.keys()) | set(_FLIP_V_CHARS.keys())
    for ch in all_chars:
        h_mapped = _FLIP_H_CHARS.get(ch, ch)
        hv_mapped = _FLIP_V_CHARS.get(h_mapped, h_mapped)
        if hv_mapped != ch:
            rotate_180_chars[ch] = hv_mapped

    for entity in entities:
        entity.x = max_x - (entity.x - min_x)
        entity.y = max_y - (entity.y - min_y)

        sprite = entity.get_component(_Sprite)
        if sprite is not None:
            remapped = _remap_char(sprite.char, rotate_180_chars)
            if remapped != sprite.char:
                sprite.char = remapped


def rotate_270(entities: list[Entity]) -> None:
    """Rotate entities 270° clockwise (90° counter-clockwise).

    Transforms entity positions by rotating 270° clockwise around the
    group's bounding-box origin.  Equivalent to three 90° CW rotations.

    Mutates entities in place.

    Args:
        entities: List of entities to rotate.

    Raises:
        TypeError: If *entities* is not a list.

    Caveats:
        - Same aspect-ratio and character-remapping caveats as
          :func:`rotate_90`.
    """
    if not isinstance(entities, list):
        raise TypeError(
            f"entities must be a list, got {type(entities).__name__}"
        )
    if len(entities) < 2:
        return

    from wyby.sprite import Sprite as _Sprite

    min_x, min_y, max_x, _ = _bounding_box(entities)

    # Build 270° CW char map (inverse of 90° CW).
    rotate_270_chars: dict[str, str] = {v: k for k, v in _ROTATE_90_CHARS.items()}

    new_positions: list[tuple[int, int]] = []
    for entity in entities:
        # 270° CW (= 90° CCW): (x, y) → (y - min_y + min_x, max_x - x + min_y)
        new_x = (entity.y - min_y) + min_x
        new_y = (max_x - entity.x) + min_y
        new_positions.append((new_x, new_y))

    for entity, (nx, ny) in zip(entities, new_positions):
        entity.x = nx
        entity.y = ny

        sprite = entity.get_component(_Sprite)
        if sprite is not None:
            remapped = _remap_char(sprite.char, rotate_270_chars)
            if remapped != sprite.char:
                sprite.char = remapped
