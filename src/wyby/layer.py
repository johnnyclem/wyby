"""Layer ordering for compositing game visuals.

This module provides :class:`Layer` and :class:`LayerStack` — the
compositing system that manages separate rendering layers with a
defined draw order.  Game code writes into individual layers (background,
entities, UI), and the stack flattens them into a single
:class:`~wyby.grid.CellBuffer` for presentation.

The three built-in layers, drawn bottom-to-top:

1. **BACKGROUND** — terrain, floor tiles, static scenery.
2. **ENTITIES** — player characters, NPCs, items, projectiles.
3. **UI** — HUD elements, menus, health bars, text overlays.

Each layer is a full-size :class:`~wyby.grid.CellBuffer`.  During
:meth:`LayerStack.flatten`, layers are composited in ascending order
(BACKGROUND first, then ENTITIES, then UI).  **Transparent** cells —
default blank cells with ``char=" "`` and no styling — let lower layers
show through.  Any cell that is not a default blank (different character,
any foreground/background colour, or bold/dim set) is **opaque** and
overwrites whatever is below it.

Typical per-frame usage::

    layers = LayerStack(80, 24)

    # Each frame:
    layers.clear()
    layers[Layer.BACKGROUND].fill(Cell(char="."))
    layers[Layer.ENTITIES].put(5, 3, Cell(char="@", fg="green"))
    layers[Layer.UI].put_text(0, 0, "HP: 100", fg="red")

    # Composite and present:
    frame = layers.flatten()
    renderer.present(frame)  # or convert to Rich renderable first

Caveats
-------
- **Memory cost.**  ``LayerStack`` allocates one :class:`CellBuffer` per
  layer (currently 3).  For an 80x24 grid that's 3 x 1920 = 5760
  :class:`~wyby.grid.Cell` objects.  For a 200x60 grid it's 36 000.
  This is modest on modern hardware but worth noting — it's 3x the
  memory of a single buffer.
- **flatten() allocates a new CellBuffer every call.**  It does not
  reuse a buffer across frames.  This means the garbage collector
  reclaims the previous frame's output buffer each tick.  For typical
  game sizes (80x24 to 200x60) this is fast, but it could become
  measurable at very large sizes or high frame rates.  A future
  optimisation could reuse a destination buffer.
- **Transparency is all-or-nothing.**  A cell is either fully
  transparent (default blank) or fully opaque.  There is no alpha
  blending, partial transparency, or colour mixing between layers.
  Terminal cells don't support alpha, so this matches the medium.
- **No per-cell z-ordering within a layer.**  All cells in the ENTITIES
  layer have the same z-order.  If two entities overlap, the last
  ``put()`` call wins.  For fine-grained z-control within a layer,
  sort draw calls in your game logic before writing to the buffer.
- **Layer set is fixed at construction.**  You cannot add or remove
  layers at runtime.  The three-layer model (background, entities, UI)
  covers most 2D game needs.  If you need more layers, use multiple
  ``LayerStack`` instances or composite ``CellBuffer`` objects manually.
- **Background colour compositing.**  A cell on ENTITIES with a
  non-default ``bg`` colour will cover the BACKGROUND cell's ``bg``
  entirely — there is no colour blending.  If you want the background
  colour to "shine through" entity cells, set the entity cell's ``bg``
  to ``None`` and let the background layer provide the colour.  However,
  ``flatten()`` copies the full cell, so the entity cell with
  ``bg=None`` will overwrite the background cell's ``bg`` with ``None``.
  To preserve background colours behind entities, leave entity cells
  as default blanks (transparent) wherever you don't want to draw.
"""

from __future__ import annotations

import enum

from wyby.grid import Cell, CellBuffer, _DEFAULT_CHAR


class Layer(enum.IntEnum):
    """Render layer identifiers, ordered from back to front.

    Layers are composited in ascending numeric order: BACKGROUND (0)
    is drawn first, then ENTITIES (1), then UI (2).  Higher-numbered
    layers overwrite lower ones wherever they have opaque cells.

    Using :class:`~enum.IntEnum` makes layer ordering explicit and
    allows iteration with ``sorted()`` or ``for layer in Layer:``.
    """

    BACKGROUND = 0
    ENTITIES = 1
    UI = 2


def _is_transparent(cell: Cell) -> bool:
    """Return True if *cell* is a default blank (fully transparent).

    A cell is transparent when it matches the default :class:`Cell`
    state: space character, no colours, no bold/dim.  Any deviation
    (different character, any colour set, bold or dim enabled) makes
    the cell opaque.
    """
    return (
        cell.char == _DEFAULT_CHAR
        and cell.fg is None
        and cell.bg is None
        and cell.bold is False
        and cell.dim is False
    )


class LayerStack:
    """Manages ordered rendering layers for compositing.

    Holds one :class:`~wyby.grid.CellBuffer` per :class:`Layer` and
    composites them into a single output buffer via :meth:`flatten`.

    Parameters
    ----------
    width:
        Number of columns.  Passed through to each layer's
        :class:`CellBuffer` (clamped to valid range).
    height:
        Number of rows.  Passed through to each layer's
        :class:`CellBuffer` (clamped to valid range).

    Raises
    ------
    TypeError:
        If *width* or *height* is not an ``int``.

    Caveats
    -------
    - Dimensions are validated by :class:`CellBuffer`, which clamps
      them to ``[1, 1000]``.  ``LayerStack`` does not add its own
      dimension constraints.
    - All layers share the same dimensions.  There is no support for
      layers of different sizes (e.g., a small UI panel over a large
      background).  The workaround is to write into a sub-region of
      the full-size layer buffer.
    """

    __slots__ = ("_width", "_height", "_layers")

    def __init__(self, width: int, height: int) -> None:
        # Let CellBuffer validate types and clamp dimensions.
        # We create one buffer to capture the clamped values, then
        # use those for all layers.
        probe = CellBuffer(width, height)
        self._width = probe.width
        self._height = probe.height

        self._layers: dict[Layer, CellBuffer] = {
            layer: CellBuffer(self._width, self._height)
            for layer in Layer
        }

    @property
    def width(self) -> int:
        """Number of columns in each layer buffer."""
        return self._width

    @property
    def height(self) -> int:
        """Number of rows in each layer buffer."""
        return self._height

    def __getitem__(self, layer: Layer) -> CellBuffer:
        """Return the :class:`CellBuffer` for *layer*.

        Raises
        ------
        KeyError:
            If *layer* is not a valid :class:`Layer` member.
        """
        return self._layers[layer]

    def clear(self) -> None:
        """Clear all layers to default blank cells.

        Call this once at the start of each frame before drawing.
        """
        for buf in self._layers.values():
            buf.clear()

    def clear_layer(self, layer: Layer) -> None:
        """Clear a single layer to default blank cells.

        Raises
        ------
        KeyError:
            If *layer* is not a valid :class:`Layer` member.
        """
        self._layers[layer].clear()

    def flatten(self) -> CellBuffer:
        """Composite all layers into a single :class:`CellBuffer`.

        Layers are drawn in ascending order (BACKGROUND, ENTITIES, UI).
        For each cell position, the topmost opaque cell wins.  A cell
        is opaque if it differs from the default blank (``Cell()``).

        Returns a **new** :class:`CellBuffer` — the layer buffers are
        not modified.

        Caveats
        -------
        - Allocates a new ``CellBuffer`` on every call.  For large
          buffers at high frame rates, this allocation is the main
          cost.  The actual cell copying is a tight Python loop over
          ``width * height * len(Layer)`` cells.
        - Transparent cells (default blanks) on upper layers let the
          lower layer cell show through.  But a cell with ``bg=None``
          and a non-default ``char`` is still **opaque** — it will
          overwrite the lower cell entirely, including its ``bg``.
        """
        result = CellBuffer(self._width, self._height)

        # Iterate layers bottom-to-top.  For each cell, if the layer
        # has an opaque cell, copy it to the result (overwriting any
        # value placed by a lower layer).
        for layer in sorted(Layer):
            buf = self._layers[layer]
            for y in range(self._height):
                src_row = buf.row(y)
                dst_row = result.row(y)
                if src_row is None or dst_row is None:
                    continue  # Defensive; should not happen.
                for x in range(self._width):
                    cell = src_row[x]
                    if not _is_transparent(cell):
                        dst_row[x] = cell

        return result

    def __repr__(self) -> str:
        return (
            f"LayerStack(width={self._width}, height={self._height}, "
            f"layers={list(Layer.__members__.keys())})"
        )
