"""Sprite system for RuneTUI.

Sprites are visual representations that can be drawn into the renderer buffer.
They can be created from text strings or converted from images using Pillow.

Caveat: Image-to-text conversion involves quantization and dithering, producing
approximations that vary by terminal font and cell size. Emoji rendering is
inconsistent across terminals due to variation selectors and font support.
SVG support requires the optional cairosvg dependency.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from rich.style import Style

from runetui.renderer import Layer, Renderer

logger = logging.getLogger(__name__)


@dataclass
class SpriteFrame:
    """A single frame of a sprite: lines of (char, style) pairs."""

    lines: list[list[tuple[str, Style]]] = field(default_factory=list)

    @property
    def width(self) -> int:
        if not self.lines:
            return 0
        return max(len(line) for line in self.lines)

    @property
    def height(self) -> int:
        return len(self.lines)


class Sprite:
    """A drawable sprite with one or more animation frames.

    Create sprites from text via from_text(), or from images via from_image()
    (requires Pillow). Animation is frame-index-based — advance manually or
    use a timer.
    """

    def __init__(self, frames: Optional[list[SpriteFrame]] = None) -> None:
        self.frames: list[SpriteFrame] = frames or []
        self.current_frame: int = 0
        self.flip_h: bool = False

    @classmethod
    def from_text(cls, text: str, style: Optional[Style] = None) -> Sprite:
        """Create a sprite from a text string.

        Each line of the text becomes a row in the sprite.
        """
        resolved_style = style or Style()
        lines: list[list[tuple[str, Style]]] = []
        for line in text.split("\n"):
            lines.append([(ch, resolved_style) for ch in line])
        frame = SpriteFrame(lines=lines)
        return cls(frames=[frame])

    @classmethod
    def from_image(
        cls,
        path: str,
        width: int = 40,
        char: str = "\u2588",
    ) -> Sprite:
        """Create a sprite from an image file using Pillow.

        The image is resized and quantized to fit the given width in terminal
        cells. Each pixel becomes a colored character.

        Caveat: Terminal cells are typically ~2:1 aspect ratio (taller than wide).
        The image height is halved to compensate, but results will not be
        pixel-perfect. Color accuracy depends on terminal color support
        (truecolor, 256, 16). Dithering is not applied — colors are mapped
        to the nearest representable value by Rich.

        Requires: pip install runetui[images]
        """
        try:
            from PIL import Image
        except ImportError:
            logger.error(
                "Pillow is required for image sprites. "
                "Install with: pip install runetui[images]"
            )
            return cls.from_text("[IMG]", Style(color="red"))

        try:
            img = Image.open(path).convert("RGB")
        except Exception as exc:
            logger.error("Failed to load image %s: %s", path, exc)
            return cls.from_text("[IMG?]", Style(color="red"))

        # Resize maintaining aspect, halving height for cell ratio
        ratio = width / img.width
        new_height = max(1, int(img.height * ratio / 2))
        img = img.resize((width, new_height), Image.Resampling.NEAREST)

        lines: list[list[tuple[str, Style]]] = []
        for y in range(img.height):
            row: list[tuple[str, Style]] = []
            for x in range(img.width):
                r, g, b = img.getpixel((x, y))
                row.append((char, Style(color=f"rgb({r},{g},{b})")))
            lines.append(row)

        frame = SpriteFrame(lines=lines)
        return cls(frames=[frame])

    @classmethod
    def from_svg(cls, path: str, width: int = 40) -> Sprite:
        """Create a sprite from an SVG file.

        Requires: pip install runetui[svg]
        Caveat: SVG rendering uses cairosvg to rasterize to PNG first,
        then converts like a normal image. Complex SVGs may not render well.
        """
        try:
            import cairosvg
            from PIL import Image
            import io
        except ImportError:
            logger.error(
                "cairosvg and Pillow are required for SVG sprites. "
                "Install with: pip install runetui[svg]"
            )
            return cls.from_text("[SVG]", Style(color="red"))

        try:
            png_data = cairosvg.svg2png(url=path, output_width=width * 2)
            img = Image.open(io.BytesIO(png_data)).convert("RGB")
            # Save temp and load via from_image logic
            # Instead, inline the conversion
            new_height = max(1, img.height // 2)
            img = img.resize((width, new_height), Image.Resampling.NEAREST)

            lines: list[list[tuple[str, Style]]] = []
            for y in range(img.height):
                row: list[tuple[str, Style]] = []
                for x in range(img.width):
                    r, g, b = img.getpixel((x, y))
                    row.append(("\u2588", Style(color=f"rgb({r},{g},{b})")))
                lines.append(row)

            frame = SpriteFrame(lines=lines)
            return cls(frames=[frame])
        except Exception as exc:
            logger.error("Failed to convert SVG %s: %s", path, exc)
            return cls.from_text("[SVG?]", Style(color="red"))

    @property
    def frame(self) -> SpriteFrame:
        """Get the current animation frame."""
        if not self.frames:
            return SpriteFrame()
        return self.frames[self.current_frame % len(self.frames)]

    def advance_frame(self) -> None:
        """Move to the next animation frame (wraps around)."""
        if self.frames:
            self.current_frame = (self.current_frame + 1) % len(self.frames)

    def draw(self, renderer: Renderer, x: int, y: int, layer: Layer = Layer.ENTITIES) -> None:
        """Draw the current frame into the renderer buffer at (x, y)."""
        frame = self.frame
        for row_idx, line in enumerate(frame.lines):
            draw_line = line
            if self.flip_h:
                draw_line = list(reversed(line))
            for col_idx, (char, style) in enumerate(draw_line):
                renderer.draw_text(x + col_idx, y + row_idx, char, style=style, layer=layer)
