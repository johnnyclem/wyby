# wyby — Scope Definition

## What wyby Is

wyby is a proposed Python framework for building terminal-rendered 2D games and
interactive applications. It targets developers who want to prototype grid-based
games, roguelikes, puzzle games, or small interactive demos using only a terminal
emulator — no GPU, no browser, no game engine install required.

**Status: Pre-release. No code has been published. Nothing is available on PyPI.**
All descriptions below define the intended scope, not shipped features.

## The Pitch (Honest Version)

Terminals are everywhere. Every developer already has one open. wyby asks: what
if you could build a playable 2D game that runs right there?

The goal is a Python library that lets you:

- Define a grid of styled cells and update it in a loop
- Handle keyboard input with a consistent, cross-platform abstraction
- Organize game objects, scenes, and state without inventing your own framework
- See something on screen in minutes, not hours

wyby is **not** trying to replace Pygame, Godot, or Unity. It is a constrained
creative medium — more like making pixel art on graph paper than painting on a
canvas. The constraints are the point.

### Who This Is For

- Developers learning game programming concepts (game loops, state machines,
  entity management) who want fast iteration without asset pipelines
- Roguelike and ASCII-game hobbyists
- People who want to build interactive terminal tools that go beyond menus
- Jam participants who want a minimal-dependency starting point

### Who This Is Not For

- Anyone who needs real-time physics, audio, or network multiplayer out of the box
- Projects that require consistent visual fidelity across all possible terminals
- Production games targeting end users who don't use terminals

---

## Technical Overview

### Core Runtime

wyby provides a game loop that repeatedly:

1. Reads input
2. Updates game state
3. Renders a frame to the terminal

Rendering uses [Rich](https://github.com/Textualize/rich) to produce styled,
colored text output. The display is a grid of character cells — each cell holds a
character (or short string) with foreground color, background color, and style
attributes.

#### What Rich Gives Us

- Truecolor (24-bit) output on supported terminals, with automatic fallback to
  256-color or basic palettes
- Text styling (bold, dim, italic, etc.)
- Layout primitives (tables, panels) that can compose UI elements
- `Live` display for updating the terminal in place without full-screen curses

#### What Rich Does Not Give Us

Rich's `Live` display is **not** a double-buffered graphics surface. It
re-renders the full Rich renderable on each refresh. This means:

- **Flicker is possible**, especially on terminals with slow rendering, on
  Windows `cmd.exe`, or when the renderable is large and complex.
- **CPU cost scales with frame complexity.** Rich performs layout, style
  resolution, and ANSI escape generation on every frame. A 120x40 grid of
  individually styled cells is measurably more expensive than a plain text block.
- **Frame rate is not guaranteed.** Achievable refresh rate depends on terminal
  emulator, OS, grid size, and style complexity. On a modern terminal (kitty,
  WezTerm, iTerm2) with a modest grid, 15-30 updates per second is realistic.
  On Windows Console or over SSH, it may be significantly lower. We will not
  claim "60 FPS" because that is not a meaningful or reliable target for
  terminal output.

The framework should include a simple FPS counter/diagnostic so developers can
measure actual performance in their environment.

### Why Not curses?

wyby chooses Rich + ANSI escape sequences over the `curses` module. This is a
tradeoff, not an upgrade:

**Advantages of the Rich approach:**
- Works on Windows without requiring `windows-curses` or WSL
- Produces Rich renderables that can be mixed with other Rich output (tables,
  markdown, progress bars) for UI overlays, menus, and debug panels
- No C extension dependency; pip-installable pure Python
- Color and style management through Rich's existing API

**What you give up compared to curses/blessed/urwid/Textual:**
- No true double-buffered screen; no differential updates (curses only redraws
  changed cells, which is fundamentally more efficient for large grids)
- No built-in character-level input with timeout (curses `getch` with
  `nodelay`/`halfdelay` is purpose-built for this)
- No `SIGWINCH` handling for terminal resize without additional plumbing
- Less battle-tested for full-screen interactive applications
- Textual provides an actual widget/event system with mouse support, focus
  management, and CSS-like styling — wyby does not aim to replicate that

If your project is a full-screen interactive application with complex widget
layouts, Textual is likely a better choice. If you want a roguelike with custom
rendering and minimal abstraction, wyby is the intended fit.

### Input Handling

Terminal input is genuinely difficult to do well. wyby's scope:

**Keyboard (core, required):**
- Read stdin in non-blocking or polled mode
- Parse ANSI escape sequences into a normalized key event enum
- Handle arrow keys, enter, escape, common modifier combos (Ctrl+C, etc.)

**Platform realities:**
- On Unix: `sys.stdin` with `termios` raw mode, or `select`-based polling.
  This is well-understood but requires terminal cooked-mode restoration on exit
  (signal handlers for cleanup).
- On Windows: `msvcrt.kbhit()`/`msvcrt.getwch()` for basic input, which
  behaves differently from Unix in key representation and timing.
- The `keyboard` library is **explicitly out of scope** for wyby. It installs
  system-wide hooks, requires root/admin on Linux, captures input from all
  applications, and raises legitimate security concerns. wyby will only read
  from its own terminal's stdin.

**Mouse (optional, limited, not in v0.1):**
- Some terminals support mouse reporting via escape sequences (xterm mouse
  protocol). This can provide click and scroll events.
- Hover and drag are technically reportable but inconsistently supported. Many
  terminals don't report hover. Some report drag only while a button is held.
- Mouse support, if added, will be an opt-in feature with terminal capability
  detection and a clear fallback (keyboard-only mode).
- wyby will **not** promise universal mouse support. The documentation will
  state which terminals are tested and what works.

### Terminal Rendering Constraints

Terminals are not pixel grids. wyby's documentation and API should make these
constraints visible, not hide them:

**Character cells are not square pixels.**
Terminal cells are typically ~1:2 aspect ratio (roughly twice as tall as wide).
A "square" game tile in cell coordinates will appear as a tall rectangle. wyby
should provide a coordinate helper that accounts for this, but the distortion
is inherent and cannot be fully eliminated.

**Unicode width is not simple.**
- CJK characters occupy 2 cells. Emoji width varies by terminal — some render
  as 1 cell, some as 2, and variation selectors/ZWJ sequences are handled
  inconsistently.
- wyby will use `wcwidth` (or equivalent) for width calculation and document
  that emoji/complex grapheme rendering is terminal-dependent.
- The safe default is ASCII or simple Unicode (box-drawing characters, block
  elements) for game tiles.

**Half-block "pixels" (using `U+2580 ▀` / `U+2584 ▄`):**
- This technique gives 2x vertical resolution by coloring the foreground and
  background of a block character differently, effectively making each cell
  two "pixels."
- It works well on terminals that support truecolor. On 256-color terminals,
  color banding is visible. On terminals without Unicode support, it fails.
- wyby may provide a half-block renderer as an optional mode, with clear
  documentation that it requires a capable terminal.

**Truecolor is not universal.**
- Most modern terminal emulators (kitty, iTerm2, WezTerm, Windows Terminal,
  GNOME Terminal) support truecolor.
- Some do not (older xterm configs, `linux` virtual console, some SSH
  configurations). Rich handles fallback, but the visual result will differ.
- wyby should detect `$COLORTERM` and report capability at startup.

### Sprites and Image Conversion

Converting raster images (PNG, JPEG) to terminal cell grids is possible but
involves significant quality loss and complexity:

- **Color quantization**: The image must be downsampled to the terminal's grid
  resolution. A 200x200 pixel image mapped to a 40x20 cell grid loses ~99% of
  its pixels.
- **Aspect ratio distortion**: Terminal cells are not square. Naive mapping
  produces stretched/squished results. Compensating requires non-uniform
  scaling.
- **Dithering**: Optional, but needed for gradients. Adds visual noise and is
  style-dependent. Floyd-Steinberg works but may look chaotic at low resolution.
- **Performance**: Converting an image to a styled cell grid on every frame
  would be expensive. Sprites should be pre-converted and cached as cell data.

wyby may include a utility to convert a PIL Image to a cell grid (with
documented quality caveats), but this is a convenience tool, not a core feature.
It will not look like the original image. It will look like terminal art.

**SVG support** is explicitly out of initial scope. Pillow does not load SVG
natively. Conversion requires `cairosvg` or similar, which depends on system
libraries (`libcairo`). If SVG support is added later, it will be via an
optional dependency with clear install instructions.

### Architecture

wyby's internal architecture has these layers, in update order:

```
Input  -->  Game Logic  -->  Scene/Entity State  -->  Renderer  -->  Terminal
```

**1. Input Layer**
Polls or reads keyboard events from stdin. Produces a queue of `KeyEvent`
values. No global hooks, no system-wide capture.

**2. Game Loop**
A fixed-timestep loop (target delta configurable, default ~33ms / ~30 tps).
Each tick: drain input queue, call the active scene's `update()`, call
`render()`. The loop measures actual tick duration for diagnostics.

**3. Scene Stack**
Scenes are the primary organizational unit. A stack of scenes allows pushing
a pause menu over gameplay, or a dialog over a map. Only the top scene
receives input. Scenes below it may or may not render (configurable).

- Scenes own their entities and state.
- Scene transitions are explicit (push, pop, replace).
- There is no implicit global state shared between scenes.

**4. Entity Model**
wyby provides a simple entity container — not a full ECS (Entity Component
System). Entities are Python objects with position, appearance (character +
style), and optional tags/groups for querying. This is deliberately minimal:

- No archetype storage, no bitset component masks, no system scheduling.
- If your game outgrows this, you can bring in `esper` or another ECS library
  and use wyby only for rendering.
- The entity model's job is to answer: "what is at position (x, y)?" and
  "give me all entities tagged 'enemy'."

**5. Renderer**
The renderer walks the scene's entities (in z-order), writes them into a cell
buffer, then converts the buffer to a Rich renderable and pushes it to
`Live`. The cell buffer is the single source of truth for what appears on
screen.

**Responsibility boundaries:**
- Input layer does not know about scenes or entities.
- Game logic does not call Rich directly.
- The renderer does not modify game state.
- Z-ordering is determined by entity z-index, resolved by the renderer. There
  is no separate z-ordering system to synchronize.

### Save / Load

Serializing arbitrary Python objects (via `pickle`) is unsafe and fragile.
wyby's approach to save/load:

- Games define a save schema: a dictionary (or dataclass) describing the state
  to persist. This is the game's responsibility, not the framework's.
- wyby provides helpers to serialize this schema to JSON (or optionally
  MessagePack) and write/read it to disk.
- **wyby does not serialize scene objects, entity instances, or runtime state
  automatically.** The game must implement `to_save_data()` and
  `from_save_data()` methods that produce and consume plain data.
- This is intentionally explicit. Implicit serialization of object graphs leads
  to versioning nightmares, security issues (`pickle` deserialization is code
  execution), and opaque bugs.

### Networking

Multiplayer / networking is **out of scope for the initial version.** This is
not a "simple stub" deferral — it's a recognition that networking is a major
subsystem:

- Synchronization (lockstep vs. client-server vs. rollback) is a design
  decision that shapes the entire game architecture.
- Latency compensation, clock drift, and determinism are hard problems that
  cannot be meaningfully stubbed.
- Protocol design (TCP vs. UDP, message framing, authentication) requires
  careful security consideration.
- Adding networking later is possible but will likely require changes to the
  game loop and state management.

If someone wants to build a networked terminal game, wyby can handle the
rendering, but the networking layer is their responsibility.

---

## Proposed Package Structure

```
wyby/
  __init__.py
  app.py          # Application entry point, game loop
  input.py        # Keyboard input abstraction
  scene.py        # Scene base class, scene stack
  entity.py       # Entity container, spatial queries
  renderer.py     # Cell buffer, Rich renderable generation
  grid.py         # Grid/cell types, coordinate helpers
  color.py        # Color utilities, palette management
  save.py         # Schema-based save/load helpers
  diagnostics.py  # FPS counter, tick timing, capability reporting
  _platform.py    # Platform-specific input backends (Unix/Windows)
```

No CLI scaffolding tool is included in the initial version. There is no
`wyby new` command. You create a Python file, import `wyby`, and run it.

---

## What "Done" Looks Like for v0.1

A successful v0.1 means:

1. A developer can `pip install wyby` (once published) and write a ~50-line
   Python script that shows a character moving around a grid with arrow keys.
2. The framework handles the game loop, input polling, and rendering without
   the developer writing ANSI escape codes or managing terminal state.
3. It works on macOS Terminal, iTerm2, Windows Terminal, and common Linux
   terminal emulators (GNOME Terminal, kitty, Alacritty). Other terminals may
   work but are not tested.
4. The documentation is honest about what works, what doesn't, and what
   terminals are supported.
5. There is at least one example game (a simple roguelike or Snake) that
   demonstrates the API.

### What v0.1 Does Not Include

- Mouse support
- Image/sprite conversion
- SVG loading
- Networking
- Audio
- A CLI scaffolding tool
- Half-block pixel rendering (may be added as experimental)
- Any guarantee of specific frame rates

---

## Dependencies

**Required:**
- Python >= 3.10
- `rich` — terminal rendering and styling

**Optional (future):**
- `pillow` — image-to-cell-grid conversion
- `cairosvg` — SVG rasterization (requires system `libcairo`)
- `msgpack` — binary save format alternative to JSON

**Explicitly not used:**
- `keyboard` — system-wide input hooks (security and permission issues)
- `curses` — replaced by Rich-based rendering (tradeoffs documented above)
- `pickle` — unsafe for save/load

---

## Open Questions

These are decisions that should be made during implementation, not pre-decided
in a scope document:

1. **Fixed vs. variable timestep?** Fixed is simpler and more deterministic,
   but some developers expect `dt`-based updates. Leaning toward fixed with
   configurable tick rate.

2. **How to handle terminal resize mid-game?** Options: ignore (clip), detect
   and re-layout, or pause and prompt. Needs experimentation.

3. **Should the renderer support layers (background, entities, UI) as separate
   buffers?** Simpler to start with one buffer and z-ordering. Layers add
   complexity but enable effects like transparent UI overlays.

4. **What's the right abstraction for "a cell's appearance"?** A named tuple?
   A dataclass? A Rich `Style` directly? This affects the entire API surface.

5. **Testing strategy for terminal output.** Snapshot tests of the cell buffer
   (not the ANSI output) are likely the right approach, but need to decide on
   tooling.

---

## License

GNU General Public License v3.0. See [LICENSE](./LICENSE).
