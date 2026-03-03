# Image Conversion Performance

Converting raster images to terminal entities is the most expensive operation
in wyby's sprite pipeline.  This document explains where the cost comes from
and how to keep it manageable.

## Cost Breakdown

The full image-to-terminal pipeline has four stages, each with its own cost:

```
Source image
    │
    ▼
1. Resize                 O(W × H)   — Pillow LANCZOS resampling
    │
    ▼
2. Aspect-ratio correct   O(W × H)   — another resize (halves height)
    │
    ▼
3. Quantize colours       O(W × H)   — median-cut + optional Floyd-Steinberg
    │
    ▼
4. from_image()           O(W × H)   — pixel iteration + entity allocation
    │
    ▼
Entity list (cached for reuse)
```

Stages 1–3 are optional (via `prepare_for_terminal()`) but recommended.
Stage 4 (`from_image()`) is the core conversion.

### Stage 4 in detail: `from_image()`

For each pixel in the image:

1. Read RGBA values via Pillow's pixel-access interface.
2. Skip transparent pixels (if `skip_alpha=True`).
3. Convert the RGB colour to a hex string (`"#rrggbb"`).
4. Allocate a Rich `Style(color=hex_color)`.
5. Allocate an `Entity` at the pixel's grid position.
6. Allocate a `Sprite(char, style)` and attach it to the entity.
7. Append the entity to the result list.

Each opaque pixel produces **three Python objects** (Entity, Sprite, Style).
At CPython's ~1 µs per object allocation, a 40×20 image (800 pixels) takes
roughly 2–3 ms.  A 100×50 image (5 000 pixels) takes 15–20 ms.  At 200×100
(20 000 pixels), conversion alone may take 50–100 ms — noticeable as a stutter
if done during gameplay.

## Cost Categories

The `estimate_image_conversion_cost()` function classifies images by pixel
count:

| Category | Pixel Count    | Typical Size | Guidance                          |
|----------|---------------|-------------|-----------------------------------|
| LIGHT    | < 256         | 16×16       | Negligible — use freely           |
| MODERATE | 256 – 1 024   | 32×32       | Fast, suitable for sprites        |
| HEAVY    | 1 024 – 4 096 | 64×64       | Convert at load time, cache result|
| EXTREME  | > 4 096       | 100×50+     | Resize first; will also impact FPS|

### Example

```python
from wyby.render_warnings import (
    estimate_image_conversion_cost,
    ImageConversionCost,
)

cost = estimate_image_conversion_cost(80, 40)
if cost >= ImageConversionCost.HEAVY:
    print("Consider resizing the image before conversion")
```

## The Golden Rule

**Convert images once at load time.  Cache the entity list.  Reuse every frame.**

```python
# GOOD — convert once, reuse forever
class MyScene(Scene):
    def on_enter(self):
        img = Image.open("hero.png")
        img = prepare_for_terminal(img, target_width=16, colors=16)
        self.hero_entities = from_image(img)  # cached

    def update(self, dt):
        # use self.hero_entities — no reconversion
        ...
```

```python
# BAD — reconverts every frame (wastes CPU, causes stuttering)
class MyScene(Scene):
    def update(self, dt):
        img = Image.open("hero.png")
        img = prepare_for_terminal(img, target_width=16, colors=16)
        entities = from_image(img)  # re-created every frame!
        ...
```

## Pre-Processing Cost

The dithering pipeline (`prepare_for_terminal`) adds cost *before*
`from_image()`:

- **Resize** (LANCZOS): ~1–5 ms for typical sprite sizes.
- **Aspect correction**: Another resize, ~1–3 ms.
- **Quantization** (median-cut): ~5–20 ms depending on image size and
  palette size.  Floyd-Steinberg dithering adds ~50% overhead.

For a 200×200 source image resized to 32×16 with 16-colour quantization, the
full pipeline typically takes 20–50 ms.  This is fine for a one-time load but
unacceptable per-frame.

## Rendering Cost (Downstream)

Conversion cost is only half the picture.  The resulting entities also affect
frame-rate:

- Each entity with a unique colour creates a distinct Rich `Style`.
- More unique styles means more ANSI escape sequences per frame.
- Quantizing to fewer colours (16–64) reduces style diversity and improves FPS.

Use `estimate_render_cost()` alongside `estimate_image_conversion_cost()` to
get the full picture:

```python
from wyby.render_warnings import estimate_render_cost, estimate_image_conversion_cost

# Conversion cost (one-time)
conv = estimate_image_conversion_cost(40, 20)

# Rendering cost (per-frame, assuming image fills the grid)
render = estimate_render_cost(40, 20)
```

## Logging

`from_image()` automatically logs a warning when converting large images.  You
can also log explicitly:

```python
from wyby.render_warnings import log_image_conversion_cost

cost = log_image_conversion_cost(100, 50)
# Logs WARNING: "Image 100x50 (5,000 pixels) will create up to 5,000 entities..."
```

Enable debug logging to see cost estimates for all conversions:

```python
import logging
logging.getLogger("wyby").setLevel(logging.DEBUG)
```

## Summary

| Concern | Mitigation |
|---------|-----------|
| Conversion is O(W×H) | Resize images to sprite-appropriate sizes (≤ 32×32) |
| Each pixel = one entity | Keep sprite images small |
| Pre-processing adds cost | Do full pipeline once at load time |
| Unique colours = unique Styles | Quantize to 16–64 colours before conversion |
| Per-frame conversion | **Never** — convert once, cache, reuse |
