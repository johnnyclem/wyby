"""Colour utilities and palette management.

This module will provide helpers for working with colours in the terminal,
including named palettes, colour conversion, and terminal capability
detection.

Caveats:
    - **Not yet implemented.** This module is a placeholder establishing
      the package structure. See SCOPE.md for the intended design.
    - Truecolor (24-bit) support is not universal. Most modern terminal
      emulators support it (kitty, iTerm2, WezTerm, Windows Terminal,
      GNOME Terminal), but some do not (older xterm configs, the Linux
      virtual console, some SSH configurations). Rich handles fallback
      to 256-colour or basic palettes, but the visual result will differ.
    - ``$COLORTERM`` should be checked to detect terminal colour
      capability. wyby will report this at startup via diagnostics.
    - Colour perception varies by display and ambient lighting.
      Palette design should consider contrast and accessibility.
"""
