"""Render-cost estimation and flicker/latency risk advisories.

This module provides utilities for estimating the rendering cost of a
:class:`~wyby.grid.CellBuffer` frame and warning when grid dimensions
or style complexity are likely to cause visible flicker or latency.

Why flicker happens in wyby
---------------------------
Rich's :class:`~rich.live.Live` display is **not** double-buffered.
Each call to :meth:`~wyby.renderer.Renderer.present` serialises the
entire renderable to ANSI escape sequences and writes them to stdout
in a single pass.  The terminal emulator then parses, rasterises, and
composites the text.  If that pipeline takes longer than the frame
interval (~33 ms at 30 tps), the user may see a partially drawn frame
— this is **flicker**.

Latency sources (from fastest to slowest)
------------------------------------------
1. **Python-side serialisation.**  Rich walks the renderable tree,
   allocates :class:`~rich.style.Style` objects for each styled cell,
   and builds an ANSI string.  Cost is *O(width × height)* with a
   per-cell constant proportional to the number of styled attributes.
2. **stdout write.**  The ANSI string is written to the file descriptor
   in one ``write()`` call (or a small number of calls if the string
   is very large).  On local terminals this is fast; over SSH or serial
   connections it is limited by link bandwidth.
3. **Terminal parsing and rendering.**  The terminal emulator parses
   escape sequences, performs text shaping and glyph rasterisation,
   and composites the result (typically on the GPU).  Performance
   varies enormously between terminal emulators — kitty and WezTerm
   are fast; Windows ``cmd.exe`` and legacy ``conhost`` are slow.
4. **VSync / display refresh.**  The terminal's compositor may wait
   for VSync before presenting the frame.  At 60 Hz this adds up to
   ~16 ms of latency that is entirely outside wyby's control.

Thresholds
----------
The constants below define empirical cell-count thresholds where
rendering cost transitions from negligible to noticeable.  These are
guidelines, not hard limits — actual performance depends on terminal
emulator, hardware, OS, and whether the connection is local or remote.

- **LIGHT** (< 2 000 cells): No perceptible overhead on any modern
  terminal.  Typical for small game grids (e.g., 40×24, puzzle games).
- **MODERATE** (2 000 – 4 800 cells): Comfortable for 30 FPS on fast
  terminals (iTerm2, WezTerm, kitty, Windows Terminal).  May drop
  below 30 FPS on slow terminals or over SSH.  This range includes
  the standard 80×24 grid (1 920 cells) and a dense 80×60 grid.
- **HEAVY** (4 800 – 12 000 cells): 15–30 FPS on fast terminals.
  Flicker becomes possible on Windows ``cmd.exe`` and over SSH.
  This range includes 120×40 (4 800) and 200×60 (12 000).
- **EXTREME** (> 12 000 cells): Single-digit FPS is likely on most
  terminals.  Not recommended for real-time gameplay — consider
  reducing grid size or using sparse rendering.

Caveats
-------
- These thresholds assume **per-cell styling** (each cell gets its own
  :class:`~rich.style.Style`).  A large grid of uniform-styled cells
  is significantly cheaper because Rich can batch adjacent characters
  with the same style.  The :func:`estimate_render_cost` function
  accepts a ``styled_fraction`` parameter to account for this.
- The thresholds are based on testing with Rich 13.x on macOS and
  Linux.  Different Rich versions, Python implementations (CPython
  vs. PyPy), and OS terminal stacks may shift the boundaries.
- **SSH latency** is additive and dominates all other costs.  Over a
  100 ms round-trip SSH connection, even a small grid will feel laggy
  because each frame's ANSI output must traverse the network.
  Compression (``ssh -C``) helps for large frames but adds CPU cost.
- **tmux** and **screen** add an extra rendering layer.  The
  multiplexer receives wyby's ANSI output, re-renders it into its own
  virtual screen, and then writes *that* to the outer terminal.  This
  roughly doubles rendering latency.
"""

from __future__ import annotations

import enum
import logging

from wyby.unicode import contains_emoji

_logger = logging.getLogger(__name__)


class RenderCost(enum.Enum):
    """Estimated rendering cost category for a frame.

    Values are ordered from cheapest to most expensive.  Use comparison
    operators (``>=``, ``<``) to check threshold levels::

        cost = estimate_render_cost(120, 40)
        if cost >= RenderCost.HEAVY:
            # consider reducing grid size or style density
            ...

    Caveats:
        - These are **estimates**, not measurements.  Actual render time
          depends on terminal emulator, hardware, and connection type.
        - ``EXTREME`` does not mean "impossible" — it means flicker and
          latency are very likely at typical refresh rates (30 tps).
    """

    LIGHT = 0
    """< 2 000 cells.  No perceptible overhead on any modern terminal."""

    MODERATE = 1
    """2 000 – 4 800 cells.  Comfortable on fast terminals at 30 FPS."""

    HEAVY = 2
    """4 800 – 12 000 cells.  Flicker possible on slow terminals / SSH."""

    EXTREME = 3
    """> 12 000 cells.  Single-digit FPS likely.  Not recommended."""

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, RenderCost):
            return NotImplemented
        return self.value >= other.value

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, RenderCost):
            return NotImplemented
        return self.value > other.value

    def __le__(self, other: object) -> bool:
        if not isinstance(other, RenderCost):
            return NotImplemented
        return self.value <= other.value

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, RenderCost):
            return NotImplemented
        return self.value < other.value


# -- Threshold constants ----------------------------------------------------

# Cell-count boundaries for render-cost categories.  These assume each
# cell is independently styled (worst case).  Uniform-style grids are
# cheaper because Rich batches same-style character runs.

LIGHT_CELL_LIMIT = 2_000
"""Maximum cell count considered LIGHT (no perceptible overhead)."""

MODERATE_CELL_LIMIT = 4_800
"""Maximum cell count considered MODERATE (comfortable at 30 FPS on fast
terminals).  Equals a 120×40 grid — a common size for roguelikes."""

HEAVY_CELL_LIMIT = 12_000
"""Maximum cell count considered HEAVY (15–30 FPS on fast terminals,
flicker possible on slow terminals and SSH).  Equals a 200×60 grid."""


def estimate_render_cost(
    width: int,
    height: int,
    styled_fraction: float = 1.0,
) -> RenderCost:
    """Estimate the rendering cost for a grid of the given dimensions.

    Returns a :class:`RenderCost` category based on the effective number
    of styled cells.  The ``styled_fraction`` parameter adjusts for
    grids where most cells use the default style (space, no colour) and
    thus skip :class:`~rich.style.Style` allocation.

    Args:
        width: Grid width in columns.  Must be >= 1.
        height: Grid height in rows.  Must be >= 1.
        styled_fraction: Fraction of cells that have non-default styling,
            between 0.0 (all default) and 1.0 (all styled).  Defaults
            to 1.0 (worst case: every cell is styled).

    Returns:
        A :class:`RenderCost` enum member indicating the estimated cost.

    Raises:
        ValueError: If *width* or *height* is less than 1, or if
            *styled_fraction* is not between 0.0 and 1.0.

    Caveats:
        - This is a **static estimate** based on cell count.  It does
          not measure actual rendering time.  Use
          :class:`~wyby.diagnostics.FPSCounter` for runtime measurements.
        - The estimate assumes Rich's default rendering path (one
          ``Style`` per non-default cell).  Custom renderables that
          bypass ``CellBuffer`` may have different cost profiles.
        - ``styled_fraction=0.0`` always returns ``LIGHT`` because
          unstyled cells are nearly free to render (no ``Style`` objects,
          minimal ANSI output).
    """
    if width < 1:
        raise ValueError(f"width must be >= 1, got {width}")
    if height < 1:
        raise ValueError(f"height must be >= 1, got {height}")
    if not (0.0 <= styled_fraction <= 1.0):
        raise ValueError(
            f"styled_fraction must be between 0.0 and 1.0, "
            f"got {styled_fraction}"
        )

    total_cells = width * height
    effective_cells = total_cells * styled_fraction

    if effective_cells < LIGHT_CELL_LIMIT:
        return RenderCost.LIGHT
    if effective_cells < MODERATE_CELL_LIMIT:
        return RenderCost.MODERATE
    if effective_cells < HEAVY_CELL_LIMIT:
        return RenderCost.HEAVY
    return RenderCost.EXTREME


def check_flicker_risk(
    width: int,
    height: int,
    styled_fraction: float = 1.0,
) -> str | None:
    """Return a human-readable warning if flicker risk is elevated, else ``None``.

    Convenience wrapper around :func:`estimate_render_cost` that returns
    an advisory string for ``HEAVY`` and ``EXTREME`` cost levels, or
    ``None`` for ``LIGHT`` and ``MODERATE`` levels.

    Args:
        width: Grid width in columns.
        height: Grid height in rows.
        styled_fraction: Fraction of non-default-styled cells (0.0–1.0).

    Returns:
        A warning string describing the flicker risk and mitigation
        suggestions, or ``None`` if the risk is acceptably low.

    Caveats:
        - A ``None`` return does **not** guarantee flicker-free rendering.
          Even small grids can flicker on very slow terminals, over SSH
          with high latency, or when the system is under heavy CPU load.
        - The warning text is intended for developer diagnostics (logs,
          debug overlays), not for end-user display.
    """
    cost = estimate_render_cost(width, height, styled_fraction)
    total = width * height

    if cost == RenderCost.HEAVY:
        return (
            f"Grid {width}x{height} ({total:,} cells) is in the HEAVY "
            f"render range. Flicker may occur on slow terminals (Windows "
            f"cmd.exe, legacy conhost) and over SSH. Consider reducing "
            f"grid dimensions or the number of individually styled cells. "
            f"Use FPSCounter to measure actual throughput."
        )
    if cost == RenderCost.EXTREME:
        return (
            f"Grid {width}x{height} ({total:,} cells) is in the EXTREME "
            f"render range. Single-digit FPS is likely on most terminals. "
            f"Reduce grid size, minimize per-cell styling, or accept "
            f"lower frame rates. Terminal rendering is the bottleneck — "
            f"no amount of Python optimization will help."
        )
    return None


def log_render_cost(
    width: int,
    height: int,
    styled_fraction: float = 1.0,
) -> RenderCost:
    """Estimate render cost and log a warning if flicker risk is elevated.

    Combines :func:`estimate_render_cost` with :func:`check_flicker_risk`
    and logs the result at an appropriate level:

    - ``LIGHT`` / ``MODERATE``: logged at ``DEBUG``.
    - ``HEAVY``: logged at ``WARNING``.
    - ``EXTREME``: logged at ``WARNING``.

    Returns the :class:`RenderCost` so callers can take further action.

    Args:
        width: Grid width in columns.
        height: Grid height in rows.
        styled_fraction: Fraction of non-default-styled cells (0.0–1.0).

    Returns:
        The estimated :class:`RenderCost` category.
    """
    cost = estimate_render_cost(width, height, styled_fraction)
    total = width * height

    if cost <= RenderCost.MODERATE:
        _logger.debug(
            "Render cost estimate: %s for %dx%d grid (%d cells, "
            "%.0f%% styled)",
            cost.name, width, height, total, styled_fraction * 100,
        )
    else:
        warning = check_flicker_risk(width, height, styled_fraction)
        if warning:
            _logger.warning(warning)

    return cost


# -- Emoji rendering warnings -----------------------------------------------

# Emoji rendering in terminal emulators is notoriously inconsistent.
# The core problems are:
#
# 1. **Width disagreement.**  The Unicode standard assigns most emoji a
#    width of 2 (East Asian Width "W"), but terminals disagree.  Some
#    render emoji at 1 column, others at 2, and some vary by codepoint.
#    This causes grid misalignment: if wyby assumes width 2 but the
#    terminal renders at width 1, subsequent cells shift left by one
#    column — corrupting the entire row.
#
# 2. **Multi-codepoint sequences.**  ZWJ sequences (👨‍👩‍👧‍👦), flag emoji
#    (🇺🇸 = two regional indicators), skin tone modifiers (👋🏽), and
#    keycap sequences (3️⃣) are composed of multiple codepoints.  wyby's
#    Cell model stores one character per cell, so multi-codepoint emoji
#    cannot be represented faithfully.  Even if stored as a grapheme
#    cluster in a single cell, the terminal may render it at an
#    unexpected width (1, 2, or more columns).
#
# 3. **Font fallback.**  Emoji rendering depends on the terminal's font
#    stack.  If the font lacks a glyph for a particular emoji, the
#    terminal may show a replacement character (□ or ?), a blank cell,
#    or a text-style fallback — each potentially at a different width.
#
# 4. **Text vs. emoji presentation.**  Characters like ☀ (U+2600) have
#    both text and emoji presentations.  Adding VS16 (U+FE0F) requests
#    emoji presentation, but not all terminals honour this.  The
#    resulting width may be 1 or 2 depending on the terminal's decision.
#
# For reliable game rendering, use ASCII, box-drawing (─│┌┐└┘├┤┬┴┼),
# block elements (█▓▒░▀▄▌▐), and simple Unicode symbols.


_EMOJI_WARNING = (
    "Text contains emoji characters, which render inconsistently across "
    "terminal emulators. Problems include: (1) width disagreement — some "
    "terminals display emoji as 1 column, others as 2, causing grid "
    "misalignment; (2) multi-codepoint sequences (ZWJ, flags, skin tones) "
    "cannot be faithfully stored in wyby's one-character-per-cell model; "
    "(3) missing font glyphs may produce replacement characters at "
    "unexpected widths. For reliable rendering, use ASCII, box-drawing, "
    "block elements, and simple Unicode symbols instead."
)


def check_emoji_warning(text: str) -> str | None:
    """Return a warning string if *text* contains emoji, else ``None``.

    Scans *text* for emoji characters and multi-codepoint emoji sequences.
    If any are found, returns a human-readable advisory explaining why
    emoji rendering is unreliable in terminal grids.

    This is intended for developer diagnostics — call it when loading
    tile sets, sprite definitions, or user-supplied text that will be
    rendered in a :class:`~wyby.grid.CellBuffer`.

    Args:
        text: The string to scan for emoji.

    Returns:
        A warning string describing emoji rendering risks, or ``None``
        if no emoji characters were detected.

    Caveats:
        - A ``None`` return does **not** guarantee correct rendering.
          Some non-emoji Unicode characters also render inconsistently
          across terminals (e.g. Ambiguous-width characters in CJK
          locales).  This function only checks for emoji specifically.
        - Detection is heuristic-based (Unicode range checks) and may
          flag some non-emoji characters that share blocks with emoji.
          See :func:`~wyby.unicode.contains_emoji` for details.
    """
    if contains_emoji(text):
        return _EMOJI_WARNING
    return None


def log_emoji_warning(text: str) -> bool:
    """Log a warning if *text* contains emoji characters.

    Convenience wrapper around :func:`check_emoji_warning` that logs the
    advisory at ``WARNING`` level if emoji are detected, or at ``DEBUG``
    level if the text is clean.

    Args:
        text: The string to scan for emoji.

    Returns:
        ``True`` if emoji were detected (and a warning was logged),
        ``False`` otherwise.
    """
    warning = check_emoji_warning(text)
    if warning:
        _logger.warning(warning)
        return True
    _logger.debug("No emoji detected in text — rendering should be consistent.")
    return False


# -- Image conversion cost --------------------------------------------------

# Image-to-entity conversion creates one Entity (with a Sprite component and
# a Rich Style) per non-transparent pixel.  The cost has three components:
#
# 1. **Pixel iteration.**  from_image() walks every pixel in the RGBA image.
#    This is O(width × height) with a Pillow pixel-access constant.
#
# 2. **Entity allocation.**  Each pixel becomes an Entity + Sprite + Style.
#    Object creation in CPython is relatively fast (~1 µs per entity), but
#    at 800 entities (a 40×20 image) the cumulative cost is measurable.
#    At 10 000+ entities it dominates load time.
#
# 3. **Pre-processing (dithering pipeline).**  If the caller uses
#    prepare_for_terminal() or quantize_for_terminal() before from_image(),
#    the resizing, quantization, and optional dithering add further CPU
#    cost — typically more than from_image() itself for large images.
#
# These costs are paid at *load time*, not per frame.  The critical guidance
# is: **convert once, cache the entity list, reuse every frame.**

class ImageConversionCost(enum.Enum):
    """Estimated cost category for converting an image to entities.

    Values are ordered from cheapest to most expensive.  Use comparison
    operators to check threshold levels::

        cost = estimate_image_conversion_cost(40, 20)
        if cost >= ImageConversionCost.HEAVY:
            # consider resizing the image first
            ...

    Caveats:
        - These are **estimates** based on pixel count, not measurements.
          Actual conversion time depends on CPU speed, Pillow version, and
          Python implementation.
        - The cost applies to the *initial conversion* only.  Once converted,
          the entity list can be reused every frame at no additional cost.
    """

    LIGHT = 0
    """< 256 pixels.  Negligible — suitable for small sprites and icons."""

    MODERATE = 1
    """256 – 1 024 pixels.  Fast but measurable.  Typical for medium sprites."""

    HEAVY = 2
    """1 024 – 4 096 pixels.  Noticeable pause on first load.  Pre-process
    offline or show a loading indicator."""

    EXTREME = 3
    """> 4 096 pixels.  Slow conversion producing thousands of entities.
    Will also impact rendering performance (see RenderCost).  Resize the
    image before conversion."""

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, ImageConversionCost):
            return NotImplemented
        return self.value >= other.value

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, ImageConversionCost):
            return NotImplemented
        return self.value > other.value

    def __le__(self, other: object) -> bool:
        if not isinstance(other, ImageConversionCost):
            return NotImplemented
        return self.value <= other.value

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, ImageConversionCost):
            return NotImplemented
        return self.value < other.value


# Cell-count boundaries for image conversion cost categories.
# These reflect the number of *pixels* (each becoming an entity).

IMAGE_LIGHT_PIXEL_LIMIT = 256
"""Maximum pixel count considered LIGHT (< 16×16 sprite)."""

IMAGE_MODERATE_PIXEL_LIMIT = 1_024
"""Maximum pixel count considered MODERATE (< 32×32 sprite)."""

IMAGE_HEAVY_PIXEL_LIMIT = 4_096
"""Maximum pixel count considered HEAVY (< 64×64 image).  Beyond this,
conversion time and entity count become significant."""


def estimate_image_conversion_cost(
    width: int,
    height: int,
    *,
    has_alpha: bool = False,
    alpha_coverage: float = 1.0,
) -> ImageConversionCost:
    """Estimate the cost of converting an image to entities via ``from_image()``.

    Returns an :class:`ImageConversionCost` category based on the effective
    number of pixels that will become entities.  Use this before calling
    :func:`~wyby.sprite.from_image` to decide whether to resize first.

    Args:
        width: Image width in pixels.  Must be >= 1.
        height: Image height in pixels.  Must be >= 1.
        has_alpha: If ``True``, the image has an alpha channel and some
            pixels may be transparent (skipped by ``from_image``).
        alpha_coverage: Fraction of pixels that are opaque (0.0–1.0).
            Only used when *has_alpha* is ``True``.  Defaults to 1.0
            (all pixels opaque — worst case).

    Returns:
        An :class:`ImageConversionCost` enum member.

    Raises:
        ValueError: If *width* or *height* is less than 1, or if
            *alpha_coverage* is not between 0.0 and 1.0.

    Caveats:
        - This estimates **conversion cost** (CPU time to create entities),
          not **rendering cost** (frame-rate impact).  A HEAVY conversion
          may produce entities that are only MODERATE to render if many
          share the same style.  Use :func:`estimate_render_cost` for
          rendering budgets.
        - The estimate does not account for pre-processing steps
          (``prepare_for_terminal``, ``quantize_for_terminal``).  Those
          add their own CPU cost proportional to image size.
    """
    if width < 1:
        raise ValueError(f"width must be >= 1, got {width}")
    if height < 1:
        raise ValueError(f"height must be >= 1, got {height}")
    if not (0.0 <= alpha_coverage <= 1.0):
        raise ValueError(
            f"alpha_coverage must be between 0.0 and 1.0, "
            f"got {alpha_coverage}"
        )

    total_pixels = width * height
    if has_alpha:
        effective_pixels = total_pixels * alpha_coverage
    else:
        effective_pixels = float(total_pixels)

    if effective_pixels < IMAGE_LIGHT_PIXEL_LIMIT:
        return ImageConversionCost.LIGHT
    if effective_pixels < IMAGE_MODERATE_PIXEL_LIMIT:
        return ImageConversionCost.MODERATE
    if effective_pixels < IMAGE_HEAVY_PIXEL_LIMIT:
        return ImageConversionCost.HEAVY
    return ImageConversionCost.EXTREME


def check_image_conversion_warning(
    width: int,
    height: int,
    *,
    has_alpha: bool = False,
    alpha_coverage: float = 1.0,
) -> str | None:
    """Return a warning if image conversion cost is HEAVY or EXTREME, else ``None``.

    Convenience wrapper around :func:`estimate_image_conversion_cost` that
    returns a human-readable advisory for high-cost conversions.

    Args:
        width: Image width in pixels.
        height: Image height in pixels.
        has_alpha: Whether the image has an alpha channel.
        alpha_coverage: Fraction of opaque pixels (0.0–1.0).

    Returns:
        A warning string with performance advice, or ``None`` if cost is
        acceptably low (LIGHT or MODERATE).

    Caveats:
        - A ``None`` return does **not** guarantee fast conversion.  Even
          small images take measurable time if the system is under load.
        - The warning text is for developer diagnostics, not end-user display.
    """
    cost = estimate_image_conversion_cost(
        width, height, has_alpha=has_alpha, alpha_coverage=alpha_coverage,
    )
    total = width * height

    if cost == ImageConversionCost.HEAVY:
        return (
            f"Image {width}x{height} ({total:,} pixels) will create up to "
            f"{total:,} entities. This is in the HEAVY conversion range. "
            f"Conversion will take a noticeable pause — call from_image() "
            f"at load time, not per-frame. Consider resizing to a smaller "
            f"dimension (e.g. 32x16 or less) for real-time sprite use."
        )
    if cost == ImageConversionCost.EXTREME:
        return (
            f"Image {width}x{height} ({total:,} pixels) will create up to "
            f"{total:,} entities. This is in the EXTREME conversion range. "
            f"Conversion will be slow and the resulting entity count will "
            f"also impact rendering performance. Resize the image before "
            f"converting (e.g. img.resize((32, 16))) and quantize colours "
            f"with quantize_for_terminal() to reduce unique styles."
        )
    return None


def log_image_conversion_cost(
    width: int,
    height: int,
    *,
    has_alpha: bool = False,
    alpha_coverage: float = 1.0,
) -> ImageConversionCost:
    """Estimate image conversion cost and log a warning if elevated.

    Combines :func:`estimate_image_conversion_cost` with
    :func:`check_image_conversion_warning` and logs at the appropriate
    level:

    - ``LIGHT`` / ``MODERATE``: logged at ``DEBUG``.
    - ``HEAVY`` / ``EXTREME``: logged at ``WARNING``.

    Returns the :class:`ImageConversionCost` so callers can take action.

    Args:
        width: Image width in pixels.
        height: Image height in pixels.
        has_alpha: Whether the image has an alpha channel.
        alpha_coverage: Fraction of opaque pixels (0.0–1.0).

    Returns:
        The estimated :class:`ImageConversionCost` category.
    """
    cost = estimate_image_conversion_cost(
        width, height, has_alpha=has_alpha, alpha_coverage=alpha_coverage,
    )
    total = width * height

    if cost <= ImageConversionCost.MODERATE:
        _logger.debug(
            "Image conversion cost estimate: %s for %dx%d image "
            "(%d pixels)",
            cost.name, width, height, total,
        )
    else:
        warning = check_image_conversion_warning(
            width, height, has_alpha=has_alpha, alpha_coverage=alpha_coverage,
        )
        if warning:
            _logger.warning(warning)

    return cost
