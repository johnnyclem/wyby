"""Cell buffer rendering and Rich renderable generation.

This module will provide the renderer that walks a scene's entities
(in z-order), writes them into a cell buffer, then converts the buffer
to a Rich renderable for display via ``Rich.Live``.

Caveats:
    - **Not yet implemented.** This module is a placeholder establishing
      the package structure. See SCOPE.md for the intended design.
    - Rich's ``Live`` display is **not** a double-buffered graphics
      surface. It re-renders the full renderable on each refresh.
      Flicker is possible, especially on terminals with slow rendering.
    - CPU cost scales with frame complexity. A 120x40 grid of
      individually styled cells is measurably more expensive than a
      plain text block.
    - The renderer does not modify game state. It only reads entity
      positions and appearances to produce the display.
    - Z-ordering is determined by entity z-index, resolved by the
      renderer. There is no separate z-ordering system to synchronise.
    - The cell buffer is the single source of truth for what appears
      on screen. Game logic should not call Rich directly.
"""
