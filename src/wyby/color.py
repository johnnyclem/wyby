"""Colour utilities and palette management.

Provides functions for downgrading colours to match terminal capabilities.
When a terminal does not support truecolor (24-bit) output, colours must
be mapped to the closest available value in the 256-colour or 16-colour
palette.

The main entry points are:

- :func:`color_system_for_support` — maps a
  :class:`~wyby.diagnostics.ColorSupport` level to the corresponding Rich
  ``color_system`` string, so that :func:`~wyby.renderer.create_console`
  can be configured to match detected terminal capabilities.
- :func:`downgrade_color` — converts a Rich colour string (hex, ``rgb()``,
  or named) to an equivalent string suitable for a lower colour depth.
- :func:`nearest_ansi256` and :func:`nearest_ansi16` — find the closest
  palette entry for an arbitrary RGB triplet.

Caveats:
    - Nearest-colour matching uses Euclidean distance in sRGB space, which
      is **not perceptually uniform**.  Two colours that are numerically
      close in RGB may look quite different on screen (especially in the
      blue–green range).  For palette-critical applications, define explicit
      fallback mappings rather than relying on automatic nearest-colour
      search.
    - The ANSI 16-colour palette values used here follow the **xterm
      defaults**.  Terminal emulators allow users to customise these colours
      via themes (Solarized, Dracula, Gruvbox, etc.).  What this module
      considers "nearest red" may render as a completely different hue if
      the user's terminal theme remaps colour 1.
    - The 256-colour palette (indices 16–255) is standardised by xterm and
      is consistent across virtually all modern terminals.  Indices 0–15
      (the "system colours") are the exception — they are subject to the
      same theme-override caveat as the 16-colour palette.
    - ``None`` (terminal default colour) passes through all conversion
      functions unchanged.  It does not participate in fallback logic.
    - Rich named colours (``"red"``, ``"bright_cyan"``, etc.) that map
      directly to ANSI 16 colours are not downgraded further — they are
      already at the lowest addressable level.
"""

from __future__ import annotations

import logging
import re

from wyby.diagnostics import ColorSupport

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ColorSupport → Rich color_system mapping
# ---------------------------------------------------------------------------

# Rich's Console accepts: "standard" (4-bit, 16 colours), "256" (8-bit),
# "truecolor" (24-bit), or None (no colour).  "auto" is also accepted
# and means Rich will detect the terminal's capabilities itself.
_COLOR_SYSTEM_MAP: dict[ColorSupport, str | None] = {
    ColorSupport.NONE: None,
    ColorSupport.STANDARD: "standard",
    ColorSupport.EXTENDED: "256",
    ColorSupport.TRUECOLOR: "truecolor",
}


def color_system_for_support(support: ColorSupport) -> str | None:
    """Map a :class:`~wyby.diagnostics.ColorSupport` to a Rich ``color_system`` string.

    Returns the ``color_system`` keyword argument to pass to
    :func:`~wyby.renderer.create_console` (or directly to
    ``rich.console.Console``) so that Rich's output matches the detected
    terminal capability.

    Args:
        support: The detected colour depth level.

    Returns:
        ``"truecolor"``, ``"256"``, ``"standard"``, or ``None``.

    Example::

        caps = detect_capabilities()
        console = create_console(
            color_system=color_system_for_support(caps.color_support),
        )

    Caveats:
        - Rich's ``"standard"`` mode targets 8 base colours plus bold
          (effectively 16), matching the ANSI 4-bit colour model.  Some
          terminals support more or fewer colours than what this mapping
          implies.
        - Returning ``None`` disables Rich colour output entirely.  Text
          will still render, but without any ANSI colour escape sequences.
          Use this for dumb terminals or when stdout is piped to a file.
        - Rich's ``"auto"`` mode (the default for ``create_console``) does
          its own terminal detection.  Use this function when you want
          wyby's :func:`~wyby.diagnostics.detect_capabilities` result to
          drive the colour system instead of Rich's separate detection.
    """
    return _COLOR_SYSTEM_MAP[support]


# ---------------------------------------------------------------------------
# ANSI 16-colour palette (xterm defaults)
# ---------------------------------------------------------------------------

# Caveat: these RGB values are the xterm *defaults*.  Most terminal
# emulators allow users to override them via colour schemes/themes.
# If the user has a custom theme (Solarized, Dracula, etc.), the
# actual rendered colours will differ from these reference values.
# The names and indices remain correct regardless of theme.

_ANSI_16_COLORS: tuple[tuple[int, int, int], ...] = (
    # Standard colours (indices 0–7)
    (0, 0, 0),        # 0: black
    (128, 0, 0),      # 1: red
    (0, 128, 0),      # 2: green
    (128, 128, 0),    # 3: yellow
    (0, 0, 128),      # 4: blue
    (128, 0, 128),    # 5: magenta
    (0, 128, 128),    # 6: cyan
    (192, 192, 192),  # 7: white
    # Bright colours (indices 8–15)
    (128, 128, 128),  # 8: bright_black (dark grey)
    (255, 0, 0),      # 9: bright_red
    (0, 255, 0),      # 10: bright_green
    (255, 255, 0),    # 11: bright_yellow
    (0, 0, 255),      # 12: bright_blue
    (255, 0, 255),    # 13: bright_magenta
    (0, 255, 255),    # 14: bright_cyan
    (255, 255, 255),  # 15: bright_white
)

# Rich colour names for the ANSI 16 palette.
_ANSI_16_NAMES: tuple[str, ...] = (
    "black", "red", "green", "yellow",
    "blue", "magenta", "cyan", "white",
    "bright_black", "bright_red", "bright_green", "bright_yellow",
    "bright_blue", "bright_magenta", "bright_cyan", "bright_white",
)

_ANSI_16_NAME_SET: frozenset[str] = frozenset(_ANSI_16_NAMES)


# ---------------------------------------------------------------------------
# xterm 256-colour palette
# ---------------------------------------------------------------------------


def _build_ansi256_palette() -> tuple[tuple[int, int, int], ...]:
    """Build the full xterm 256-colour palette as RGB tuples.

    The palette is divided into three regions:

    - **0–15**: System colours (same as ANSI 16, subject to terminal
      theme overrides).
    - **16–231**: 6×6×6 colour cube.  Each axis uses the values
      ``[0, 95, 135, 175, 215, 255]``.
    - **232–255**: Greyscale ramp from ``rgb(8, 8, 8)`` to
      ``rgb(238, 238, 238)`` in steps of 10.
    """
    palette: list[tuple[int, int, int]] = []

    # Region 1: system colours (0–15)
    palette.extend(_ANSI_16_COLORS)

    # Region 2: 6×6×6 colour cube (16–231)
    cube_values = (0, 95, 135, 175, 215, 255)
    for r_idx in range(6):
        for g_idx in range(6):
            for b_idx in range(6):
                palette.append((
                    cube_values[r_idx],
                    cube_values[g_idx],
                    cube_values[b_idx],
                ))

    # Region 3: greyscale ramp (232–255)
    for i in range(24):
        v = 8 + 10 * i
        palette.append((v, v, v))

    return tuple(palette)


# Pre-computed at module load time.
_ANSI_256_PALETTE: tuple[tuple[int, int, int], ...] = _build_ansi256_palette()


# ---------------------------------------------------------------------------
# Colour parsing
# ---------------------------------------------------------------------------

_HEX_RE = re.compile(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
_RGB_RE = re.compile(
    r"^rgb\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*\)$"
)
_COLOR_N_RE = re.compile(r"^color\(\s*(\d{1,3})\s*\)$")


def parse_color(color: str) -> tuple[int, int, int] | None:
    """Parse a colour string to an ``(R, G, B)`` tuple.

    Supports:

    - Hex: ``"#ff0000"``, ``"#f00"``
    - RGB: ``"rgb(255, 0, 0)"``
    - Named ANSI: ``"red"``, ``"bright_cyan"``, etc.
    - Indexed: ``"color(196)"``

    Returns ``None`` if the string cannot be parsed.

    Caveats:
        - Named colours are resolved against the xterm default palette.
          If the user's terminal theme overrides these colours, the
          returned RGB values will not match what is actually displayed.
        - Only the 16 standard ANSI colour names are recognised.  Rich
          supports additional named colours (e.g., ``"dark_orange"``)
          that are **not** handled here — they will return ``None``.
        - ``"color(N)"`` for N in 0–15 returns the xterm default RGB
          for that system colour, which may differ from the terminal's
          actual rendering.
    """
    if not color:
        return None

    # Hex: #RGB or #RRGGBB
    m = _HEX_RE.match(color)
    if m:
        hex_str = m.group(1)
        if len(hex_str) == 3:
            r = int(hex_str[0] * 2, 16)
            g = int(hex_str[1] * 2, 16)
            b = int(hex_str[2] * 2, 16)
        else:
            r = int(hex_str[0:2], 16)
            g = int(hex_str[2:4], 16)
            b = int(hex_str[4:6], 16)
        return (r, g, b)

    # rgb(R, G, B)
    m = _RGB_RE.match(color)
    if m:
        r, g, b = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if r <= 255 and g <= 255 and b <= 255:
            return (r, g, b)
        return None

    # color(N)
    m = _COLOR_N_RE.match(color)
    if m:
        idx = int(m.group(1))
        if 0 <= idx <= 255:
            return _ANSI_256_PALETTE[idx]
        return None

    # Named ANSI colour
    lower = color.lower()
    if lower in _ANSI_16_NAME_SET:
        idx = _ANSI_16_NAMES.index(lower)
        return _ANSI_16_COLORS[idx]

    return None


# ---------------------------------------------------------------------------
# Nearest-colour search
# ---------------------------------------------------------------------------


def _sq_distance(
    c1: tuple[int, int, int], c2: tuple[int, int, int],
) -> int:
    """Squared Euclidean distance between two RGB colours."""
    return (c1[0] - c2[0]) ** 2 + (c1[1] - c2[1]) ** 2 + (c1[2] - c2[2]) ** 2


def nearest_ansi16(r: int, g: int, b: int) -> str:
    """Find the nearest ANSI 16 colour name for an RGB triplet.

    Uses Euclidean distance in sRGB space to find the closest match
    among the 16 standard ANSI colours.

    Args:
        r: Red component (0–255).
        g: Green component (0–255).
        b: Blue component (0–255).

    Returns:
        A Rich colour name string (e.g., ``"red"``, ``"bright_cyan"``).

    Caveats:
        - Euclidean distance in sRGB is not perceptually uniform.
          Colours that are numerically close may look visually different,
          especially in the blue–green range.  For games with specific
          colour requirements, define explicit palette mappings instead.
        - The match is against xterm default palette values.  If the
          user's terminal theme overrides ANSI colours, the "nearest"
          colour may render very differently than expected.
    """
    target = (r, g, b)
    best_idx = 0
    best_dist = _sq_distance(target, _ANSI_16_COLORS[0])
    for i in range(1, 16):
        d = _sq_distance(target, _ANSI_16_COLORS[i])
        if d < best_dist:
            best_dist = d
            best_idx = i
    return _ANSI_16_NAMES[best_idx]


def nearest_ansi256(r: int, g: int, b: int) -> int:
    """Find the nearest xterm 256-colour palette index for an RGB triplet.

    Searches the full 256-colour palette (system colours 0–15, the
    6×6×6 colour cube 16–231, and the greyscale ramp 232–255) using
    Euclidean distance in sRGB space.

    Args:
        r: Red component (0–255).
        g: Green component (0–255).
        b: Blue component (0–255).

    Returns:
        A palette index (0–255).

    Caveats:
        - Indices 0–15 (system colours) are included in the search.
          These are subject to terminal theme overrides, so the
          "nearest" match may include a system colour whose actual
          appearance differs from its xterm default RGB value.
        - Same perceptual-uniformity caveat as :func:`nearest_ansi16`.
    """
    target = (r, g, b)
    best_idx = 0
    best_dist = _sq_distance(target, _ANSI_256_PALETTE[0])
    for i in range(1, 256):
        d = _sq_distance(target, _ANSI_256_PALETTE[i])
        if d < best_dist:
            best_dist = d
            best_idx = i
    return best_idx


# ---------------------------------------------------------------------------
# Colour downgrade
# ---------------------------------------------------------------------------


def downgrade_color(
    color: str | None, target: ColorSupport,
) -> str | None:
    """Downgrade a colour string to the specified capability level.

    Converts a Rich colour string (hex, ``rgb()``, named, or indexed)
    to an equivalent string that is representable at the *target*
    colour depth.  If the colour is already at or below the target
    level, it is returned unchanged.

    Args:
        color: A Rich colour string (``"#ff0000"``, ``"rgb(255,0,0)"``,
            ``"red"``, ``"color(196)"``, etc.), or ``None`` for the
            terminal default.
        target: The target :class:`~wyby.diagnostics.ColorSupport` level.

    Returns:
        A colour string suitable for the target level, or ``None`` if
        the input is ``None`` or the target is ``NONE``.

    Caveats:
        - Named ANSI colours (``"red"``, ``"bright_cyan"``, etc.) are
          considered STANDARD-level and pass through unchanged for any
          target >= STANDARD.
        - ``"color(N)"`` strings are considered EXTENDED-level and pass
          through for target >= EXTENDED.  For target == STANDARD, the
          indexed colour is resolved to RGB and matched to the nearest
          ANSI 16 name.
        - Hex and ``rgb()`` colours are considered truecolor and are
          downgraded to ``"color(N)"`` for EXTENDED or to a named ANSI
          colour for STANDARD.
        - Unrecognised colour strings (e.g., Rich extended names like
          ``"dark_orange"``) are returned unchanged with a debug log
          warning.  They may cause Rich rendering issues at lower
          colour depths.
        - ``NONE`` target returns ``None``, discarding the colour
          entirely.  The terminal default foreground/background will
          be used instead.
    """
    if color is None:
        return None

    if target == ColorSupport.NONE:
        return None

    # Named ANSI colours are already STANDARD-level.
    if color.lower() in _ANSI_16_NAME_SET:
        return color

    # color(N) — already EXTENDED-level.
    color_n_match = _COLOR_N_RE.match(color)
    if color_n_match:
        if target >= ColorSupport.EXTENDED:
            return color
        # Downgrade to STANDARD: resolve to RGB, find nearest ANSI 16.
        idx = int(color_n_match.group(1))
        if 0 <= idx <= 255:
            rgb = _ANSI_256_PALETTE[idx]
            return nearest_ansi16(*rgb)
        return color

    # Parse to RGB for downgrade.
    rgb = parse_color(color)
    if rgb is None:
        _logger.debug("Cannot parse colour for downgrade: %r", color)
        return color

    if target >= ColorSupport.TRUECOLOR:
        return color
    elif target == ColorSupport.EXTENDED:
        idx = nearest_ansi256(*rgb)
        return f"color({idx})"
    else:
        return nearest_ansi16(*rgb)
