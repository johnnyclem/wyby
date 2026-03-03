# Rendering Performance: Flicker & Latency Risks

wyby uses Rich's `Live` display to push styled character grids to the
terminal.  This document explains the flicker and latency risks inherent
in this approach and offers practical guidance for keeping frame rates
acceptable.

## How Terminal Rendering Works in wyby

Each frame follows this pipeline:

```
CellBuffer → Rich Text objects → ANSI escape string → stdout → Terminal
```

1. **CellBuffer → Rich Text.**  `CellBuffer.__rich_console__()` iterates
   every cell, allocates a `Style` for each non-default cell, and appends
   characters to one `Text` object per row.
2. **Rich Text → ANSI string.**  Rich's console serialises the `Text`
   objects into an ANSI escape sequence string.
3. **ANSI string → stdout.**  The string is written to the stdout file
   descriptor in one pass.
4. **stdout → Terminal display.**  The terminal emulator parses escape
   sequences, rasterises glyphs, and composites the result to screen.

Rich's `Live` display is **not double-buffered**.  Each `present()` call
re-renders the full frame.  There is no differential update or dirty-
region tracking.

## Where Flicker Comes From

Flicker occurs when the terminal displays a partially drawn frame before
the full ANSI output has been written and processed.  Common causes:

- **Large ANSI output.**  A 120×40 fully styled grid generates ~50–100 KB
  of ANSI escape sequences per frame.  Writing this to stdout takes
  measurable time, during which the terminal may render partial output.
- **Slow terminal emulators.**  Windows `cmd.exe` and legacy `conhost`
  have slow ANSI parsing.  Even moderate grids can flicker.
- **SSH connections.**  Each frame's ANSI output must traverse the
  network.  At 100 ms round-trip, 30 FPS is physically impossible
  regardless of grid size.
- **Terminal multiplexers.**  `tmux` and `screen` add an extra
  rendering layer (they re-render wyby's output into their own virtual
  screen), roughly doubling latency.
- **System load.**  GC pauses, CPU contention, and I/O pressure all
  contribute to frame-time jitter.

## Render Cost Categories

The `render_warnings` module defines four cost categories based on
effective styled cell count:

| Category   | Cell Count     | Expected FPS        | Flicker Risk |
|------------|----------------|---------------------|--------------|
| LIGHT      | < 2,000        | 30+ on all terminals| Negligible   |
| MODERATE   | 2,000 – 4,800  | 30 on fast terminals| Low          |
| HEAVY      | 4,800 – 12,000 | 15–30 on fast       | Moderate     |
| EXTREME    | > 12,000       | Single-digit likely | High         |

These assume worst-case per-cell styling.  Grids with mostly uniform
styling are cheaper because Rich batches same-style character runs.

## Mitigation Strategies

### 1. Keep Grid Dimensions Reasonable

80×24 (1,920 cells) is safe everywhere.  120×40 (4,800 cells) is the
practical upper bound for flicker-free 30 FPS on fast terminals.

### 2. Minimize Per-Cell Styling

Default cells (space, no colour, no bold/dim) skip `Style` allocation
entirely.  A 200×60 grid that is 90% blank is much cheaper than a
200×60 grid where every cell is individually coloured.

### 3. Use `estimate_render_cost()` at Startup

```python
from wyby.render_warnings import estimate_render_cost, RenderCost

cost = estimate_render_cost(width, height)
if cost >= RenderCost.HEAVY:
    # Warn the user or fall back to a smaller grid
    ...
```

### 4. Profile with `FPSCounter` and `RenderTimer`

Estimates are no substitute for measurement.  Enable the FPS counter
and check actual throughput in the target environment:

```python
engine = Engine(width=120, height=40, show_fps=True)
# ... after running for a few seconds:
if engine.fps_counter:
    print(f"Actual FPS: {engine.fps_counter.fps:.1f}")
```

For finer granularity, the `Renderer` exposes a `RenderTimer` that
tracks per-`present()` call duration:

```python
renderer = Renderer(console)
with renderer:
    renderer.present(buffer)
    timer = renderer.render_timer
    print(f"Last render: {timer.last_render_ms:.2f} ms")
    print(f"Avg render:  {timer.avg_render_ms:.2f} ms")
    print(f"Min render:  {timer.min_render_ms:.2f} ms")
    print(f"Max render:  {timer.max_render_ms:.2f} ms")
```

**Caveat:** `RenderTimer` measures Python-side wall-clock time only
(Rich serialisation + `stdout.write()`).  Terminal-side processing
(ANSI parsing, glyph rasterisation, GPU compositing) happens after
the write returns and is not captured.  Actual visible-frame latency
is always higher than the reported render time.

### 5. Reduce TPS for Large Grids

If 30 tps causes the game loop to fall behind, lower the tick rate.
A puzzle game or roguelike at 15 tps (66 ms per frame) is perfectly
playable and gives the terminal twice as long to render each frame.

### 6. Account for SSH and Multiplexers

If the game may be played over SSH or inside `tmux`, test in those
environments.  SSH compression (`ssh -C`) helps for large frames
but adds CPU overhead.  Consider offering a "low-bandwidth mode"
that uses a smaller grid or sparser styling.

### 7. Call `present()` Exactly Once Per Tick

Calling `present()` multiple times per tick wastes bandwidth — only
the last frame is visible.  The game loop should call `present()`
once after all rendering logic is complete.

## What wyby Cannot Control

These factors are outside the framework's influence:

- **Terminal emulator rendering speed.**  Kitty, WezTerm, and Alacritty
  are GPU-accelerated and fast.  Legacy terminals are not.
- **VSync.**  Most terminals sync to the display refresh rate (typically
  60 Hz / ~16 ms).  wyby cannot bypass VSync.
- **Network latency.**  SSH adds round-trip time to every frame.
- **OS scheduling.**  Python's GIL, GC pauses, and OS thread scheduling
  cause frame-time jitter that wyby cannot eliminate.
- **Font rendering.**  Complex Unicode glyphs (emoji, CJK, combining
  characters) are slower to rasterise than ASCII.

## Summary

Terminal rendering is inherently constrained.  wyby makes no FPS
guarantees — 15–30 FPS is realistic on modern terminals with
moderate grid sizes.  Use the `render_warnings` module and
`FPSCounter` to understand your game's rendering budget, and design
grid dimensions and styling density accordingly.
