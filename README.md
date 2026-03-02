# RuneTUI

A Python library for developing terminal-based (TUI) games using modern terminal capabilities.

> **Disclaimer:** RuneTUI is experimental (v0.1.0). Terminal game development has inherent
> limitations. Frame rates, input responsiveness, and visual fidelity depend on the terminal
> emulator, OS, hardware, and scene complexity. Rich Live rendering introduces overhead that
> may cause flicker or latency under heavy use. This library provides building blocks, not
> guarantees.

## Installation

```bash
pip install -e .
```

For image sprite support:
```bash
pip install -e ".[images]"
```

For SVG sprite support:
```bash
pip install -e ".[svg]"
```

For development:
```bash
pip install -e ".[dev]"
```

## Quick Start

```python
from runetui import Engine, EngineConfig, Scene
from runetui.renderer import Renderer
from runetui.events import Event, KeyEvent

class HelloScene(Scene):
    def handle_event(self, event: Event) -> None:
        pass

    def update(self, dt: float) -> None:
        pass

    def render(self, renderer: Renderer) -> None:
        renderer.draw_text(10, 5, "Hello, RuneTUI!")

engine = Engine(EngineConfig(title="Hello", width=40, height=12))
engine.push_scene(HelloScene())
engine.run()
```

## Architecture

```
Engine (game loop, scene stack, timing)
  ├── Renderer (Rich Console + Live, virtual buffer)
  ├── InputManager (keyboard polling, event queue)
  └── Scene Stack
       └── Scene (handle_event, update, render)
            ├── Entities (Position, Velocity, components)
            ├── Sprites (text, image, SVG)
            └── Widgets (Button, HealthBar)
```

The game loop follows the **input-update-render** pattern:
1. **Input**: Poll keyboard/mouse events, push to event queue
2. **Update**: Fixed-timestep game logic (scene.update)
3. **Render**: Draw to virtual buffer, present via Rich Live

## Known Limitations and Caveats

### Rendering
- Rich Live refresh can introduce **flicker and latency**, especially with complex styling
- True double-buffering is not possible in a terminal
- Emoji and wide Unicode characters may render inconsistently across terminals
- Terminal cell aspect ratio is roughly 2:1 (taller than wide)

### Input
- On **Linux**, the `keyboard` library requires root/sudo for global key hooks
- Default input uses `sys.stdin` in cbreak mode (no sudo needed, but limited)
- Mouse support varies by terminal — hover and drag may not work reliably
- Some key combinations are intercepted by the terminal or OS

### Performance
- No frame rate guarantees — `time.sleep()` precision is platform-dependent (1-15ms)
- Image-to-text sprite conversion is CPU-intensive; do it at load time, not per-frame
- Large buffers (>100x50) with rich styling will be slower

### Platform
- SIGWINCH (terminal resize) is Unix-only
- Windows terminal support depends on Windows Terminal or similar modern emulators
- macOS Terminal.app has limited truecolor support; iTerm2 recommended

## API Reference

### Engine & EngineConfig
- `Engine(config)` — Create the game engine
- `engine.push_scene(scene)` — Push a scene onto the stack
- `engine.pop_scene()` — Pop the top scene
- `engine.replace_scene(scene)` — Replace the top scene
- `engine.run()` — Start the game loop
- `engine.stop()` — Signal the engine to stop

### Scene (abstract)
- `handle_event(event)` — Process input events
- `update(dt)` — Update game logic (fixed timestep)
- `render(renderer)` — Draw to the renderer buffer
- `on_enter()` / `on_exit()` — Lifecycle hooks
- `on_resize(width, height)` — Terminal resize callback

### Renderer
- `draw_text(x, y, text, style, layer)` — Write text to buffer
- `draw_rect(x, y, w, h, char, style, layer)` — Fill a rectangle
- `clear_buffer()` — Reset the buffer
- `present()` — Push buffer to terminal

### Entity & Components
- `Entity(x, y)` — Create with position
- `entity.add_component(component)` — Attach a component
- `entity.get_component(Type)` — Retrieve a component
- `entity.update(dt)` — Apply velocity to position

### Sprite
- `Sprite.from_text(text, style)` — Create from string
- `Sprite.from_image(path, width)` — Create from image (requires Pillow)
- `sprite.draw(renderer, x, y)` — Draw to buffer

### Widgets
- `Button(x, y, label, on_click)` — Clickable button
- `HealthBar(x, y, width, current, maximum)` — Progress bar

### Collision
- `check_aabb_collision(entity_a, entity_b)` — AABB overlap check
- `apply_velocity(entity, dt, gravity, friction)` — Physics helper

## License

MIT — see [LICENSE](LICENSE).
