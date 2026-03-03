"""Dithering and aspect-ratio utilities for image-to-terminal conversion.

Provides helper functions to prepare raster images (via Pillow) for display
in a terminal character grid.  These utilities address three fundamental
problems of image-to-terminal conversion:

1. **Aspect ratio distortion.**  Terminal cells are not square — they are
   typically ~2× taller than wide (~1:2 width-to-height ratio).  A square
   image mapped 1:1 to cells will appear stretched vertically.
   :func:`correct_aspect_ratio` resizes the image to compensate.

2. **Colour quantization.**  A typical photograph contains thousands of
   unique colours, but terminal colour support is limited (truecolor,
   256-colour, or 16-colour palettes).  Even with truecolor terminals,
   each unique colour creates a distinct Rich :class:`~rich.style.Style`
   object, increasing rendering cost.  :func:`quantize_for_terminal`
   reduces the colour palette before conversion.

3. **Dithering.**  Quantization can produce visible banding in gradients.
   Floyd-Steinberg dithering distributes quantization error across
   neighbouring pixels to simulate smooth transitions.  However, at the
   low resolutions typical of terminal grids (20–80 columns), dithering
   adds visual noise that may look chaotic rather than smooth.
   :func:`quantize_for_terminal` supports optional dithering.

Typical workflow::

    from PIL import Image
    from wyby.dithering import correct_aspect_ratio, quantize_for_terminal
    from wyby.sprite import from_image

    img = Image.open("hero.png")

    # 1. Resize to target terminal width (e.g. 40 columns)
    img = img.resize((40, int(40 * img.height / img.width)))

    # 2. Correct for terminal aspect ratio (halves height)
    img = correct_aspect_ratio(img)

    # 3. Quantize to a limited palette
    img = quantize_for_terminal(img, colors=16)

    # 4. Convert to entities
    entities = from_image(img)

Or use :func:`prepare_for_terminal` as an all-in-one convenience::

    from wyby.dithering import prepare_for_terminal
    from wyby.sprite import from_image

    img = Image.open("hero.png")
    img = prepare_for_terminal(img, target_width=40, colors=16)
    entities = from_image(img)

Requires the ``Pillow`` library (``pip install wyby[image]``).

Caveats:
    - **Terminal cells are not square.**  The exact aspect ratio varies by
      terminal emulator and font.  The default ``CELL_ASPECT_RATIO`` of 2.0
      is a reasonable approximation for most terminals with typical monospace
      fonts, but it will not be pixel-perfect.  Some terminals (e.g. with
      custom line spacing) may need a different value.  There is no reliable
      way to auto-detect the cell aspect ratio.
    - **Floyd-Steinberg dithering adds noise.**  At terminal resolutions
      (typically 20–120 columns), dithering produces speckled patterns that
      may look chaotic rather than smooth.  For pixel-art-style sprites,
      disable dithering (``dither=False``) and use a small, curated palette.
      Dithering is most useful for photographic images where banding is
      worse than noise.
    - **Quantization is lossy.**  Reducing to 16 or even 64 colours
      discards subtle gradients and tonal variation.  The result will look
      like terminal art, not like the original image.  This is inherent to
      the medium and cannot be fixed by better algorithms.
    - **Pillow's quantization uses median-cut.**  The ``Image.quantize()``
      method uses a median-cut algorithm to select the palette.  This
      generally produces good results but may not preserve small
      colour-critical details (e.g. a single red pixel in a sea of blue).
    - **Convert images offline.**  These functions involve non-trivial
      computation (resizing, quantization, dithering).  Call them once at
      load time or as a pre-processing step — not on every frame.  Cache
      the resulting entities or cell data for rendering.
    - **Alpha channel is preserved.**  :func:`correct_aspect_ratio` and
      :func:`quantize_for_terminal` preserve the alpha channel where
      present.  Transparent pixels remain transparent through the pipeline,
      and :func:`~wyby.sprite.from_image` skips them by default.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PIL import Image

_logger = logging.getLogger(__name__)

# Approximate height-to-width ratio of a terminal character cell.
# Most monospace fonts in most terminal emulators produce cells that are
# roughly twice as tall as they are wide.  This value is used by
# correct_aspect_ratio() to halve the image height, compensating for the
# vertical stretch that occurs when pixels are mapped 1:1 to cells.
#
# Caveat: the exact ratio depends on the terminal emulator, font, and
# line-spacing settings.  2.0 is a widely applicable default but will
# not be perfect for all environments.  There is no reliable cross-platform
# way to query the actual cell dimensions in pixels.
CELL_ASPECT_RATIO: float = 2.0


def correct_aspect_ratio(
    image: Image.Image,
    *,
    cell_aspect_ratio: float = CELL_ASPECT_RATIO,
) -> Image.Image:
    """Resize an image to compensate for terminal cell aspect ratio.

    Terminal cells are taller than they are wide (typically ~2:1).  When
    image pixels are mapped 1:1 to cells, the result appears vertically
    stretched.  This function shrinks the image height by the
    *cell_aspect_ratio* factor, so that the displayed output looks
    proportionally correct.

    Args:
        image: A Pillow :class:`~PIL.Image.Image` instance.
        cell_aspect_ratio: The height-to-width ratio of a terminal cell.
            Defaults to :data:`CELL_ASPECT_RATIO` (2.0).  Higher values
            produce a shorter (more compressed) result.

    Returns:
        A new :class:`~PIL.Image.Image` with the same width but adjusted
        height.  The height is ``max(1, round(original_height /
        cell_aspect_ratio))``.  Uses ``Image.LANCZOS`` resampling for
        quality.

    Raises:
        ImportError: If Pillow is not installed.
        TypeError: If *image* is not a :class:`~PIL.Image.Image`.
        TypeError: If *cell_aspect_ratio* is not a number.
        ValueError: If *cell_aspect_ratio* is not positive.
        ValueError: If the image has zero width or height.

    Caveats:
        - **The default ratio (2.0) is approximate.**  The actual cell
          aspect ratio depends on the terminal emulator, font, and
          line-spacing settings.  A ratio of 2.0 works well for most
          setups but may over- or under-correct on some terminals.
        - **Very small images may lose rows.**  For a 4-pixel-tall image
          with ratio 2.0, the result is 2 pixels tall.  For a 1-pixel-tall
          image, the result is clamped to 1 pixel.  Information loss is
          inevitable when shrinking.
        - **Resampling uses LANCZOS.**  This is a high-quality downscale
          filter but may introduce slight blurring and ringing on hard
          edges.  For pixel-art sprites where crisp edges matter, consider
          ``Image.NEAREST`` resampling by calling ``image.resize()``
          directly instead of this function.
        - **Alpha channel is preserved.**  RGBA images stay RGBA after
          resizing.  Transparent regions are interpolated by the resampling
          filter, which may produce semi-transparent edge pixels.
    """
    try:
        from PIL import Image as _PILImage
    except ImportError:
        raise ImportError(
            "Pillow is required for correct_aspect_ratio(). "
            "Install it with: pip install wyby[image]"
        ) from None

    if not isinstance(image, _PILImage.Image):
        raise TypeError(
            f"image must be a PIL.Image.Image instance, "
            f"got {type(image).__name__}"
        )

    if not isinstance(cell_aspect_ratio, (int, float)):
        raise TypeError(
            f"cell_aspect_ratio must be a number, "
            f"got {type(cell_aspect_ratio).__name__}"
        )
    if cell_aspect_ratio <= 0:
        raise ValueError(
            f"cell_aspect_ratio must be positive, got {cell_aspect_ratio}"
        )

    width, height = image.size
    if width == 0 or height == 0:
        raise ValueError(
            f"image must have non-zero dimensions, got {width}x{height}"
        )

    new_height = max(1, round(height / cell_aspect_ratio))

    # No resize needed if height is unchanged.
    if new_height == height:
        return image.copy()

    result = image.resize((width, new_height), _PILImage.LANCZOS)
    _logger.debug(
        "correct_aspect_ratio: %dx%d → %dx%d (ratio=%.2f)",
        width, height, width, new_height, cell_aspect_ratio,
    )
    return result


def quantize_for_terminal(
    image: Image.Image,
    *,
    colors: int = 16,
    dither: bool = True,
) -> Image.Image:
    """Quantize an image to a reduced colour palette for terminal display.

    Reduces the number of unique colours in *image* to *colors* using
    Pillow's median-cut quantization.  This improves rendering performance
    (fewer unique Rich :class:`~rich.style.Style` objects) and produces
    output that maps well to limited terminal palettes.

    Args:
        image: A Pillow :class:`~PIL.Image.Image` instance.
        colors: Maximum number of colours in the resulting palette.
            Defaults to 16 (matches the ANSI 16-colour palette size).
            Range: 1–256.
        dither: If ``True`` (the default), apply Floyd-Steinberg dithering
            during quantization.  Dithering distributes quantization error
            to neighbouring pixels, reducing banding in gradients.  If
            ``False``, each pixel is mapped to its nearest palette colour
            without error diffusion.

    Returns:
        A new :class:`~PIL.Image.Image` in ``"RGBA"`` mode with at most
        *colors* unique colours.

    Raises:
        ImportError: If Pillow is not installed.
        TypeError: If *image* is not a :class:`~PIL.Image.Image`.
        TypeError: If *colors* is not an int.
        ValueError: If *colors* is outside 1–256.
        ValueError: If the image has zero width or height.

    Caveats:
        - **Floyd-Steinberg dithering adds noise at low resolution.**
          Terminal grids are typically 20–120 columns wide.  At these
          resolutions, dithering produces a speckled pattern that may
          look chaotic rather than smooth.  For small sprites and
          pixel art, set ``dither=False`` for cleaner output.  Dithering
          is most beneficial for larger, photographic images where
          colour banding would be more objectionable than noise.
        - **Quantization is irreversible.**  The original colour
          information is lost.  Always quantize a copy if you need the
          original later.
        - **The resulting palette is image-adaptive.**  Pillow's
          median-cut algorithm selects colours based on the image's
          actual colour distribution.  The palette will differ from
          the standard ANSI 16 or 256 palettes.  For exact ANSI
          palette matching, use :func:`~wyby.color.nearest_ansi16` or
          :func:`~wyby.color.nearest_ansi256` on individual colours
          instead.
        - **Alpha channel handling.**  The image is converted to RGB
          for quantization (Pillow's ``quantize()`` does not support
          RGBA directly), then the original alpha channel is reattached.
          Fully transparent pixels may have their RGB values altered
          by the quantizer — this is harmless since they are invisible.
        - **colors=1 produces a single-colour image.**  This is valid
          but likely not useful.  Every pixel will be the same colour.
    """
    try:
        from PIL import Image as _PILImage
    except ImportError:
        raise ImportError(
            "Pillow is required for quantize_for_terminal(). "
            "Install it with: pip install wyby[image]"
        ) from None

    if not isinstance(image, _PILImage.Image):
        raise TypeError(
            f"image must be a PIL.Image.Image instance, "
            f"got {type(image).__name__}"
        )

    if not isinstance(colors, int) or isinstance(colors, bool):
        raise TypeError(
            f"colors must be an int, got {type(colors).__name__}"
        )
    if colors < 1 or colors > 256:
        raise ValueError(
            f"colors must be 1–256, got {colors}"
        )

    width, height = image.size
    if width == 0 or height == 0:
        raise ValueError(
            f"image must have non-zero dimensions, got {width}x{height}"
        )

    # Preserve alpha channel if present.
    has_alpha = image.mode in ("RGBA", "LA", "PA")
    alpha_channel = None
    if has_alpha:
        rgba = image.convert("RGBA")
        alpha_channel = rgba.split()[3]
        rgb = rgba.convert("RGB")
    else:
        rgb = image.convert("RGB")

    # Pillow dithering constants.
    dither_method = (
        _PILImage.Dither.FLOYDSTEINBERG if dither
        else _PILImage.Dither.NONE
    )

    quantized = rgb.quantize(colors=colors, dither=dither_method)
    result = quantized.convert("RGB")

    # Reattach alpha if the original had it.
    if alpha_channel is not None:
        result = result.convert("RGBA")
        result.putalpha(alpha_channel)
    else:
        result = result.convert("RGBA")

    _logger.debug(
        "quantize_for_terminal: %dx%d, colors=%d, dither=%s",
        width, height, colors, dither,
    )
    return result


def prepare_for_terminal(
    image: Image.Image,
    *,
    target_width: int | None = None,
    target_height: int | None = None,
    colors: int | None = None,
    dither: bool = True,
    correct_aspect: bool = True,
    cell_aspect_ratio: float = CELL_ASPECT_RATIO,
) -> Image.Image:
    """All-in-one image preparation for terminal display.

    Combines resizing, aspect ratio correction, and colour quantization
    into a single call.  Operations are applied in the correct order:

    1. Resize to *target_width* / *target_height* (if specified).
    2. Correct aspect ratio (if *correct_aspect* is ``True``).
    3. Quantize colours (if *colors* is specified).

    After this call, the image is ready for :func:`~wyby.sprite.from_image`.

    Args:
        image: A Pillow :class:`~PIL.Image.Image` instance.
        target_width: Desired width in cells/columns.  If specified
            without *target_height*, the height is calculated to preserve
            the image's original aspect ratio (before cell correction).
            If ``None``, the width is not changed.
        target_height: Desired height in cells/rows.  If specified
            without *target_width*, the width is calculated to preserve
            the aspect ratio.  If both *target_width* and *target_height*
            are given, the image is resized to exactly those dimensions
            (aspect ratio may not be preserved).
        colors: Number of colours to quantize to (1–256).  If ``None``
            (the default), no quantization is performed.
        dither: Whether to apply Floyd-Steinberg dithering during
            quantization.  Ignored if *colors* is ``None``.
        correct_aspect: If ``True`` (the default), apply aspect ratio
            correction via :func:`correct_aspect_ratio`.
        cell_aspect_ratio: The cell aspect ratio for correction.
            Defaults to :data:`CELL_ASPECT_RATIO`.

    Returns:
        A new :class:`~PIL.Image.Image` ready for conversion to
        terminal entities.

    Raises:
        ImportError: If Pillow is not installed.
        TypeError: If *image* is not a :class:`~PIL.Image.Image`.
        ValueError: If *target_width* or *target_height* is < 1.
        ValueError: If the image has zero width or height.

    Caveats:
        - **Order matters.**  Aspect ratio correction is applied *after*
          resizing to the target dimensions.  If you specify
          ``target_height=20`` with ``correct_aspect=True``, the final
          height will be ``round(20 / cell_aspect_ratio)`` = 10 (not 20).
          To get exactly 20 rows of output, set ``correct_aspect=False``
          and handle aspect ratio in your target dimensions.
        - **Resize uses LANCZOS resampling.**  Same caveats as
          :func:`correct_aspect_ratio` regarding blurring on hard edges.
        - **All other caveats from** :func:`correct_aspect_ratio` **and**
          :func:`quantize_for_terminal` **apply.**
    """
    try:
        from PIL import Image as _PILImage
    except ImportError:
        raise ImportError(
            "Pillow is required for prepare_for_terminal(). "
            "Install it with: pip install wyby[image]"
        ) from None

    if not isinstance(image, _PILImage.Image):
        raise TypeError(
            f"image must be a PIL.Image.Image instance, "
            f"got {type(image).__name__}"
        )

    width, height = image.size
    if width == 0 or height == 0:
        raise ValueError(
            f"image must have non-zero dimensions, got {width}x{height}"
        )

    result = image

    # Step 1: Resize to target dimensions.
    if target_width is not None or target_height is not None:
        if target_width is not None and target_width < 1:
            raise ValueError(
                f"target_width must be >= 1, got {target_width}"
            )
        if target_height is not None and target_height < 1:
            raise ValueError(
                f"target_height must be >= 1, got {target_height}"
            )

        if target_width is not None and target_height is not None:
            new_w, new_h = target_width, target_height
        elif target_width is not None:
            # Calculate height preserving aspect ratio.
            new_w = target_width
            new_h = max(1, round(height * target_width / width))
        else:
            # target_height is not None
            new_h = target_height
            new_w = max(1, round(width * target_height / height))

        result = result.resize((new_w, new_h), _PILImage.LANCZOS)
        _logger.debug(
            "prepare_for_terminal resize: %dx%d → %dx%d",
            width, height, new_w, new_h,
        )

    # Step 2: Aspect ratio correction.
    if correct_aspect:
        result = correct_aspect_ratio(
            result, cell_aspect_ratio=cell_aspect_ratio,
        )

    # Step 3: Colour quantization.
    if colors is not None:
        result = quantize_for_terminal(
            result, colors=colors, dither=dither,
        )

    return result
