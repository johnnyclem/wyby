"""Grid and cell types, coordinate helpers.

This module will provide the ``Cell`` data type (character + foreground
colour + background colour + style) and the ``CellBuffer`` class that
represents a 2D grid of cells.

Caveats:
    - **Not yet implemented.** This module is a placeholder establishing
      the package structure. See SCOPE.md for the intended design.
    - Terminal character cells are not square pixels. They are typically
      ~1:2 aspect ratio (roughly twice as tall as wide). A "square"
      game tile in cell coordinates will appear as a tall rectangle.
      Coordinate helpers will account for this, but the distortion is
      inherent and cannot be fully eliminated.
    - Unicode width is not simple. CJK characters occupy 2 cells.
      Emoji width varies by terminal — some render as 1 cell, some as 2.
      ``wcwidth`` (or equivalent) will be used for width calculation.
    - The safe default for game tiles is ASCII or simple Unicode
      (box-drawing characters, block elements). Complex emoji and ZWJ
      sequences are terminal-dependent.
"""
