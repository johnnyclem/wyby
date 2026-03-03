# Dithering and Aspect Ratio in Terminal Image Conversion

This document covers the challenges and caveats of converting raster images
(PNG, JPEG, etc.) to terminal character grids in wyby. Terminal cells are not
pixels — they have different dimensions, limited colour support, and low
resolution. Understanding these constraints helps you produce the best
possible terminal art.

## The Aspect Ratio Problem

### Why images look stretched

Terminal character cells are **not square**. A typical monospace font produces
cells that are roughly **twice as tall as they are wide** (approximately 1:2
width-to-height ratio, or a cell aspect ratio of ~2.0).

When image pixels are mapped 1:1 to terminal cells, the result appears
**vertically stretched** — a circle becomes a tall oval, a square becomes
a tall rectangle.

```
Original image (8×8 pixels):    Terminal output (8×8 cells):

  ########                        ########
  #      #                        #      #
  #      #                        #      #
  #      #                        #      #
  ########                        #      #
                                  #      #
                                  #      #
                                  ########

  (square on screen)              (tall rectangle on screen)
```

### Correcting aspect ratio

To compensate, **halve the image height** before converting to cells. The
`correct_aspect_ratio()` function does this automatically:

```python
from PIL import Image
from wyby.dithering import correct_aspect_ratio
from wyby.sprite import from_image

img = Image.open("icon.png")
img = correct_aspect_ratio(img)  # Halves height by default
entities = from_image(img)
```

### Caveats

- **The default ratio of 2.0 is approximate.** The exact ratio varies by
  terminal emulator and font. Some terminals with tight line spacing may be
  closer to 1.7; others with generous spacing may be 2.2 or higher.

- **There is no reliable way to auto-detect the cell aspect ratio.** Terminal
  emulators do not expose cell pixel dimensions through standard escape
  sequences in a universally supported way. The default of 2.0 works well
  for most setups.

- **Half-block characters can double vertical resolution.** Using `▀` (U+2580)
  or `▄` (U+2584) with separate foreground and background colours packs two
  vertical "pixels" into one cell, effectively making cells square. wyby does
  not implement this mode in `from_image()`, but it is a technique to be aware
  of for custom renderers.

## Colour Quantization

### The problem

A typical photograph may contain tens of thousands of unique colours. Terminal
colour support is limited:

| Level      | Colours      | Detection                  |
|-----------|-------------|----------------------------|
| Truecolor  | 16 million   | `$COLORTERM=truecolor`     |
| 256-colour | 256          | Most modern terminals      |
| 16-colour  | 16           | Basic terminals, `linux` VC |

Even with truecolor, each unique colour creates a separate Rich `Style` object
in wyby's rendering pipeline. Thousands of unique styles increase memory usage
and slow down frame rendering.

### Quantizing colours

Reduce the palette **before** converting to entities:

```python
from wyby.dithering import quantize_for_terminal
from wyby.sprite import from_image

img = Image.open("landscape.png").resize((60, 30))
img = quantize_for_terminal(img, colors=64)  # 64-colour palette
entities = from_image(img)
```

The `colors` parameter sets the maximum palette size. Good starting points:

- **16 colours** — matches ANSI 16 palette, very fast rendering, posterised look
- **64 colours** — good balance of quality and performance
- **256 colours** — maximum for 8-bit terminals, high quality on truecolor

### Caveats

- **Quantization is lossy and irreversible.** Subtle gradients and tonal
  variation are discarded. The result looks like terminal art, not a photograph.

- **The adaptive palette differs from ANSI palettes.** Pillow's median-cut
  quantizer selects colours based on the image's actual colour distribution,
  not the standard ANSI palette. For exact ANSI palette matching, use
  `wyby.color.nearest_ansi16()` or `nearest_ansi256()` on individual colours.

- **Small colour-critical details may be lost.** If a single important red
  pixel sits in a field of blue, the quantizer may exclude red from the
  palette entirely.

## Dithering

### What it is

Dithering distributes quantization error across neighbouring pixels, creating
the illusion of intermediate colours through spatial mixing. Floyd-Steinberg
is the standard error-diffusion algorithm.

### When to use it

```python
# With dithering (default) — better for photographs and gradients
img = quantize_for_terminal(img, colors=16, dither=True)

# Without dithering — better for pixel art and crisp sprites
img = quantize_for_terminal(img, colors=16, dither=False)
```

**Use dithering when:**
- The image has smooth gradients (sky, shadows, skin tones)
- The image is photographic
- Banding (visible colour steps) is more objectionable than noise

**Disable dithering when:**
- The image is pixel art with intentionally flat colours
- The terminal grid is very small (< 20 columns) — noise dominates
- You want clean, crisp colour boundaries
- The image will be used as a game sprite where clarity matters

### Caveats

- **Dithering looks chaotic at low resolution.** Terminal grids are typically
  20–120 columns wide. At these resolutions, the speckled dithering pattern is
  clearly visible as noise rather than blending smoothly as it would in a
  300 DPI print. This is a fundamental limitation of the medium.

- **Floyd-Steinberg is the only supported method.** Pillow's `quantize()`
  supports Floyd-Steinberg or no dithering. Other algorithms (ordered/Bayer,
  blue noise, Atkinson) would need custom implementation.

- **Dithering adds visual complexity to rendering.** More unique adjacent
  colours means more style transitions per row, which increases the size
  of the ANSI output. This is rarely a bottleneck but is worth noting for
  very large grids.

## The Complete Pipeline

The recommended preparation order:

```
Source image
    │
    ▼
1. Resize to target terminal width
    │  img.resize((target_cols, calculated_rows))
    ▼
2. Correct aspect ratio
    │  correct_aspect_ratio(img)  — halves height
    ▼
3. Quantize colours
    │  quantize_for_terminal(img, colors=N, dither=True/False)
    ▼
4. Convert to entities
    │  from_image(img)
    ▼
Terminal display
```

Or use `prepare_for_terminal()` for steps 1–3:

```python
from wyby.dithering import prepare_for_terminal
from wyby.sprite import from_image

img = Image.open("hero.png")
img = prepare_for_terminal(img, target_width=16, colors=16, dither=False)
entities = from_image(img)
```

### Performance

- **Convert images offline, not per-frame.** Resizing, quantization, and
  dithering are computationally expensive. Do them once at load time and
  cache the resulting entity list.

- **Keep sprite sizes small.** A 40×20 image produces 800 entities. A 16×8
  sprite produces 128 — much more manageable. Terminal games work best with
  small, stylised sprites.

- **Fewer colours = faster rendering.** Each unique colour requires a
  separate Rich `Style`. Quantizing to 16 colours means at most 16 styles,
  regardless of image size.

## Summary of Caveats

| Issue | Impact | Mitigation |
|-------|--------|------------|
| Cells are ~2:1 aspect ratio | Images stretched vertically | `correct_aspect_ratio()` |
| Aspect ratio varies by terminal | Correction imperfect | Accept ~2.0 default or tune per-terminal |
| Cannot auto-detect cell dimensions | No perfect correction | Manual tuning if needed |
| Limited terminal colour palettes | Colour loss in images | `quantize_for_terminal()` before conversion |
| Floyd-Steinberg noisy at low res | Speckled appearance | Disable dithering for small/pixel-art sprites |
| Quantization is lossy | Detail loss | Inherent to medium — design for it |
| Conversion is expensive | Frame rate impact | Convert once at load time, cache results |
| Each pixel = one entity | Memory/performance | Keep sprite images small (< 40×20) |
