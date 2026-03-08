# wyby

A Python framework for building terminal-rendered 2D games.

> **Pre-release (v0.1.0dev0).** The API is unstable and subject to breaking
> changes. Not published on PyPI. Do not use in production.

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

## Quick Start

### Hello World

The simplest wyby program — a styled message on screen:

```python
from wyby.app import Engine, QuitSignal
from wyby.grid import CellBuffer
from wyby.input import InputManager, KeyEvent
from wyby.scene import Scene

class HelloScene(Scene):
    def __init__(self):
        super().__init__()
        self.buffer = CellBuffer(40, 12)

    def handle_events(self, events):
        for event in events:
            if isinstance(event, KeyEvent) and event.key in ("q", "escape"):
                raise QuitSignal

    def update(self, dt):
        pass

    def render(self):
        self.buffer.clear()
        self.buffer.put_text(13, 5, "Hello, World!", fg="bright_green", bold=True)
        self.buffer.put_text(8, 7, "Press q or Esc to quit", fg="bright_black")

engine = Engine(title="hello", width=40, height=12, tps=30,
                input_manager=InputManager())
engine.push_scene(HelloScene())
engine.run()
```

What it looks like in the terminal:

```





             Hello, World!

        Press q or Esc to quit




```

### Movable Character

A character you can walk around with arrow keys — the core of any
roguelike or grid-based game:

```python
from wyby.app import Engine, QuitSignal
from wyby.grid import CellBuffer
from wyby.input import InputManager, KeyEvent
from wyby.scene import Scene

class WalkScene(Scene):
    def __init__(self, width=30, height=16):
        super().__init__()
        self.w, self.h = width, height
        self.buffer = CellBuffer(width, height)
        self.px, self.py = width // 2, height // 2  # player position

    def handle_events(self, events):
        for event in events:
            if not isinstance(event, KeyEvent):
                continue
            if event.key in ("q", "escape"):
                raise QuitSignal
            dx, dy = 0, 0
            if event.key == "up":    dy = -1
            elif event.key == "down":  dy = 1
            elif event.key == "left":  dx = -1
            elif event.key == "right": dx = 1
            # Clamp to interior of border
            self.px = max(1, min(self.w - 2, self.px + dx))
            self.py = max(1, min(self.h - 2, self.py + dy))

    def update(self, dt):
        pass

    def render(self):
        self.buffer.clear()
        # Draw border
        for x in range(self.w):
            self.buffer.put_text(x, 0, "─", fg="bright_black")
            self.buffer.put_text(x, self.h - 1, "─", fg="bright_black")
        for y in range(self.h):
            self.buffer.put_text(0, y, "│", fg="bright_black")
            self.buffer.put_text(self.w - 1, y, "│", fg="bright_black")
        self.buffer.put_text(0, 0, "┌", fg="bright_black")
        self.buffer.put_text(self.w - 1, 0, "┐", fg="bright_black")
        self.buffer.put_text(0, self.h - 1, "└", fg="bright_black")
        self.buffer.put_text(self.w - 1, self.h - 1, "┘", fg="bright_black")
        # Draw player
        self.buffer.put_text(self.px, self.py, "@", fg="bright_yellow", bold=True)
        # HUD
        self.buffer.put_text(2, 0, f" ({self.px},{self.py}) ", fg="white")

engine = Engine(title="walk", width=30, height=16, tps=30,
                input_manager=InputManager())
engine.push_scene(WalkScene())
engine.run()
```

What it looks like:

```
┌ (15,8) ─────────────────────┐
│                              │
│                              │
│                              │
│                              │
│                              │
│                              │
│                              │
│              @               │
│                              │
│                              │
│                              │
│                              │
│                              │
│                              │
└──────────────────────────────┘
```

## Example Games

wyby ships with complete example games in the `examples/` directory:

### Snake

Classic snake — arrow keys to steer, eat food (`*`) to grow, avoid walls
and yourself.

```
python examples/snake_game.py
```

```
┌ Score: 3 ───────────────────┐
│                              │
│                              │
│                              │
│                              │
│       ooo                    │
│          o        *          │
│          o                   │
│          o                   │
│          @                   │
│                              │
│                              │
│                              │
│                              │
│                              │
│                              │
│                              │
│                              │
│ Arrows:move Q:quit ─────────┘
```

### Pong

Two-player pong — Player 1 uses `w`/`s`, Player 2 uses arrow keys.

```
python examples/pong_game.py
```

```
┌──────────────────────────────────────┐
│         2         │        3         │
│                   │                  │
│                   │                  │
│                   │                  │
│  █                │                  │
│  █                │              █   │
│  █           o    │              █   │
│  █                │              █   │
│                   │              █   │
│                   │                  │
│                   │                  │
│                   │                  │
│                   │                  │
│ W/S:P1  ↑/↓:P2  Q:quit ────────────┘
```

### Flappy Bird

Single-player — press `Space` or `Up` to flap, dodge the pipes.

```
python examples/flappy_bird_game.py
```

```
┌──────────────────────────────────────┐
│                        ██            │
│                        ██            │
│                        ██            │
│    >                   ██            │
│                        ██            │
│                                      │
│                        ██            │
│                        ██            │
│                        ██            │
│                        ██            │
│                        ██            │
│ Score: 4  ──────── Space:flap Q:quit │
└──────────────────────────────────────┘
```

## Architecture

```
Input  →  Game Logic  →  Scene/Entity State  →  Renderer  →  Terminal
```

**Scene stack** — scenes are the primary organizational unit. Push a pause
menu over gameplay, a dialog over a map. Only the top scene receives input.

**Entity model** — simple containers with position, appearance, and tags.
Not a full ECS. If you outgrow it, bring in `esper` or similar and use
wyby for rendering only.

**CellBuffer** — a 2D grid of styled character cells. The renderer converts
this to a Rich renderable and pushes it via `Live` display.

See [SCOPE.md](./SCOPE.md) for the full technical overview, design rationale,
and constraint documentation.

## Important Caveats

- **No frame rate guarantees.** Rendering performance depends on your terminal
  emulator, OS, grid size, and style complexity. 15-30 updates/second is
  realistic on modern terminals (kitty, WezTerm, iTerm2). Less on Windows
  Console or over SSH.

- **Rich is not a game engine.** Rich's `Live` display re-renders the full
  renderable each frame. No double-buffered surface or differential updates.
  Flicker is possible on slow terminals or with large grids.

- **Terminal cells are not square pixels.** Cells have roughly a 1:2
  aspect ratio (taller than wide). Vertical movement appears ~2x faster
  visually than horizontal movement.

- **Unicode/emoji rendering varies.** CJK characters take 2 cells; emoji
  width is terminal-dependent. Stick to ASCII or box-drawing characters
  for reliable results.

- **No system-wide input hooks.** wyby reads only from its own stdin.
  The `keyboard` library is excluded (requires elevated permissions,
  captures system-wide input).

- **No networking in v0.1.** Multiplayer is a major subsystem, not a stub.

## Requirements

- Python >= 3.10
- `rich` >= 13.0

## Installation

wyby is not published on PyPI. Install from source:

```bash
git clone <repo-url>
cd wyby
pip install -e ".[dev]"
```

## Running Examples

```bash
python examples/hello_world.py
python examples/snake_game.py
python examples/pong_game.py
python examples/flappy_bird_game.py
```

All examples require a real terminal (TTY). They will not work with piped
stdin or in CI environments without a TTY.

## License

[GPL-3.0-only](./LICENSE)
