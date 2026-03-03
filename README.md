# wyby

A Python framework for building terminal-rendered 2D games.

> **Disclaimer:** wyby is in early pre-release development (v0.1.0dev0).
> The API is unstable and subject to breaking changes without notice.
> Nothing is published on PyPI. Do not use this in production.

## What It Is

wyby provides building blocks for creating interactive 2D games that run
entirely in a terminal emulator — roguelikes, puzzle games, ASCII art demos,
and similar. It uses [Rich](https://github.com/Textualize/rich) for styled
character-grid rendering and targets developers who want fast iteration
without asset pipelines or engine installs.

## What It Is Not

wyby is **not** a replacement for Pygame, Godot, or Unity. It is a constrained
creative medium. If you need real-time physics, audio, network multiplayer, or
consistent visual fidelity across all terminals, this is not the right tool.

## Important Caveats

- **No frame rate guarantees.** Rendering performance depends on your terminal
  emulator, OS, grid size, and style complexity. On modern terminals (kitty,
  WezTerm, iTerm2) with modest grids, 15-30 updates/second is realistic. On
  Windows Console or over SSH it may be significantly lower.

- **Rich is not a game engine.** Rich's `Live` display re-renders the full
  renderable each frame. There is no double-buffered surface or differential
  update. Flicker is possible, especially on slow terminals or with large grids.

- **Terminal cells are not square pixels.** Cells have roughly a 1:2
  aspect ratio (taller than wide). A "square" tile in cell coordinates
  appears as a tall rectangle. This distortion is inherent to terminals.

- **Unicode/emoji rendering varies.** CJK characters take 2 cells; emoji width
  is terminal-dependent. Stick to ASCII or simple Unicode (box-drawing, block
  elements) for reliable results.

- **No system-wide input hooks.** wyby only reads from its own process's stdin.
  The `keyboard` library is explicitly excluded due to its requirement for
  elevated permissions and system-wide capture.

- **No pickle for save/load.** Games must implement explicit serialization via
  `to_save_data()`/`from_save_data()` with JSON or msgpack. Pickle
  deserialization is code execution and is not safe for game saves.

- **No networking in v0.1.** Multiplayer requires synchronization, latency
  compensation, and protocol design — none of which can be meaningfully stubbed.

## Requirements

- Python >= 3.10
- `rich` >= 13.0

## Installation

```bash
# Clone and install in development mode
git clone <repo-url>
cd wyby
pip install -e ".[dev]"
```

## License

[GPL-3.0-only](./LICENSE)
