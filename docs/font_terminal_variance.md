# Font and Terminal Variance

This document explains why the same wyby game can look different across terminal
emulators and fonts, and how to design defensively for these differences.

## Why Terminal Rendering Varies

Terminal emulators are not standardised renderers.  They differ in:

- **Font metrics** — cell width, height, and aspect ratio
- **Character width interpretation** — especially for Ambiguous and emoji chars
- **Glyph coverage** — which Unicode codepoints the font contains
- **Text shaping** — how complex grapheme clusters are rendered
- **Ligature handling** — whether adjacent characters are merged
- **Line spacing** — extra padding between rows

These differences mean that pixel-perfect rendering is not achievable in
terminal games.  wyby is designed to degrade gracefully across terminals, but
game developers should understand the variance to avoid surprises.

## Cell Aspect Ratio

### The core problem

Terminal character cells are **not square**.  A typical monospace font produces
cells approximately **twice as tall as they are wide** (~2:1 height:width ratio).

This means:
- A 10×10 character grid appears as a tall rectangle, not a square
- Images mapped pixel-to-cell appear vertically stretched
- Game maps designed on graph paper will appear distorted

### Variation across fonts

The exact aspect ratio depends on the font:

| Font            | Approximate ratio |
|-----------------|-------------------|
| Menlo           | ~2.0              |
| SF Mono         | ~2.0              |
| Consolas        | ~1.9              |
| DejaVu Sans Mono| ~2.0              |
| Iosevka         | ~2.4              |
| Source Code Pro | ~1.7              |
| Fira Code       | ~1.9              |

The terminal's line-spacing setting further modifies the effective ratio.

### Detection and fallback

There is **no universally reliable way** to auto-detect cell pixel dimensions:

- The `TIOCGWINSZ` ioctl on Unix can report pixel dimensions, but many
  terminals return zeros.  `estimate_cell_aspect_ratio()` attempts this and
  falls back to 2.0.
- Xterm escape sequences (`\e[16t`, `\e[14t`) can query cell size, but support
  is inconsistent and sending queries conflicts with game input handling.
- Inside `tmux`/`screen`, reported dimensions may reflect the multiplexer, not
  the outer terminal.

**Recommendation:** Use the default aspect ratio of 2.0 and provide a
configuration option for users who need to tune it.

### API

```python
from wyby.font_variance import estimate_cell_aspect_ratio, DEFAULT_CELL_ASPECT_RATIO

geometry = estimate_cell_aspect_ratio()
print(f"Aspect ratio: {geometry.aspect_ratio}")
print(f"Detected: {geometry.detected}")
if geometry.detected:
    print(f"Cell size: {geometry.cell_width_px}x{geometry.cell_height_px} px")
```

## Character Width Disagreement

### Ambiguous-width characters

Unicode assigns each character an East Asian Width property.  Characters with
width "Ambiguous" (A) — including some Greek, Cyrillic, and mathematical symbols
— may render at 1 or 2 columns depending on:

- The terminal's locale setting (CJK vs. Western)
- The font's glyph width for that character
- The terminal's width-calculation algorithm

wyby treats Ambiguous characters as width 1 (the Western convention).

### Emoji width

Emoji width is **unreliable across terminals**.  See `wyby.render_warnings` and
`wyby.unicode` for full details.  The short version:

- Some terminals render emoji at 1 column, others at 2
- Multi-codepoint emoji (ZWJ, flags, skin tones) are unpredictable
- Variation selectors (VS15 for text, VS16 for emoji presentation) are not
  always honoured

**Recommendation:** Avoid emoji in game tiles where alignment matters.  Use
ASCII, box-drawing (`─│┌┐└┘├┤┬┴┼`), and block elements (`█▓▒░▀▄▌▐`).

## Glyph Coverage

### Missing glyphs (tofu)

When the terminal's font lacks a glyph for a character, it shows a replacement:
`□`, `?`, or an empty box ("tofu").  The replacement may be a different width
than the intended character, corrupting grid alignment.

### Safe character sets

Characters present in virtually all monospace fonts:

- **ASCII** (U+0020–U+007E): always safe
- **Box-drawing** (U+2500–U+257F): safe in all modern terminals
- **Block elements** (U+2580–U+259F): safe in all modern terminals
- **Braille patterns** (U+2800–U+28FF): widely supported

### Font fallback

Most terminals use a fallback chain: if the primary font lacks a glyph, the
terminal tries secondary fonts.  The fallback font may have different metrics,
causing visual inconsistency.

**Recommendation:** Test with `TestCard` to verify glyph coverage for the
characters you use.

## Ligatures

Programming-ligature fonts (Fira Code, JetBrains Mono, Cascadia Code) may merge
adjacent box-drawing or operator characters into ligature glyphs.  This breaks
cell-grid alignment because what should be separate single-cell characters
becomes a single multi-cell glyph.

**Affected terminals:** iTerm2, kitty, WezTerm, and any terminal with ligature
rendering enabled.

**Recommendation:** Advise users to disable ligatures or use a non-ligature
monospace font when playing terminal games.

## Line Spacing and Cell Padding

### Line spacing

Extra line spacing creates visible gaps between rows.  This is especially
problematic for half-block pixel art (`▀` / `▄`) where seamless row joining is
essential.

### Cell padding

Some terminals (kitty, WezTerm) allow per-cell padding configuration.  Non-zero
padding changes the effective aspect ratio and introduces gaps.

**Recommendation:** Document that line spacing should be 1.0 (100%) and cell
padding should be zero for best results.

## Programmatic Utilities

### Check warnings for current terminal

```python
from wyby.font_variance import check_font_variance_warnings

warnings = check_font_variance_warnings()
for w in warnings:
    print(f"WARNING: {w}")
```

### Generate a full variance report

```python
from wyby.font_variance import format_font_variance_report

print(format_font_variance_report())
```

### Browse the issue catalog

```python
from wyby.font_variance import (
    FONT_VARIANCE_ISSUES,
    ISSUE_CATEGORIES,
    get_issues_by_category,
    get_issues_for_terminal,
)

# All categories
print(sorted(ISSUE_CATEGORIES))

# Issues for a specific category
for issue in get_issues_by_category("ligatures"):
    print(f"{issue.issue}: {issue.description}")

# Issues relevant to a specific terminal
for issue in get_issues_for_terminal("kitty"):
    print(f"{issue.issue}: {issue.mitigation}")
```

## Summary of Caveats

| Issue | Impact | Mitigation |
|-------|--------|------------|
| Cell aspect ratio ~2:1 | Images stretched, maps distorted | `correct_aspect_ratio()`, expose config |
| Aspect ratio varies by font | Correction imperfect | Default 2.0, allow user tuning |
| Cannot auto-detect cell size | No perfect correction | Heuristic + manual config |
| Ambiguous-width chars | Width 1 or 2 depending on locale | Avoid in game tiles |
| Emoji width unreliable | Grid misalignment | Use ASCII/box-drawing/blocks |
| Missing font glyphs | Tofu, alignment corruption | Stick to safe character sets |
| Font fallback metrics | Visual inconsistency | Test with TestCard |
| Ligature merging | Grid alignment broken | Disable ligatures or use non-ligature font |
| Line spacing gaps | Half-block art broken | Set line spacing to 1.0 |
| Cell padding | Aspect ratio change, gaps | Set padding to zero |
