"""Application entry point and game loop.

This module will provide the main ``Engine`` class that drives the
fixed-timestep game loop: drain input → update active scene → render frame.

Caveats:
    - **Not yet implemented.** This module is a placeholder establishing
      the package structure. See SCOPE.md for the intended design.
    - The game loop targets ~30 ticks per second by default, but actual
      frame rate depends on terminal emulator, grid size, and style
      complexity. Do not assume 60 FPS — that is not a meaningful target
      for terminal output.
    - Rich's ``Live`` display re-renders the full renderable each frame.
      CPU cost scales with frame complexity, and flicker is possible on
      slow terminals (especially Windows ``cmd.exe``).
    - The engine does not provide networking, audio, or GPU acceleration.
      These are explicitly out of scope for wyby v0.1.
"""
