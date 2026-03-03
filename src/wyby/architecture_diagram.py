"""Generate text-based architecture diagrams for wyby documentation.

This module produces ASCII-art architecture diagrams that visualize the
runtime layer structure of a wyby game.  The diagrams are intended for
inclusion in README files, documentation, and terminal display where
graphical diagrams are not practical.

The primary entry points are:

- :data:`LAYERS` — catalog of all architecture layers with descriptions
  and data-flow annotations.
- :data:`DIAGRAM_CAVEATS` — caveats about the architecture and what the
  diagram does and does not represent.
- :func:`generate_diagram` — produce an :class:`ArchitectureDiagram`
  with the full layer stack and data-flow arrows.
- :func:`format_diagram` — format a diagram as plain text suitable for
  a fenced code block.
- :func:`format_diagram_markdown` — format a diagram as a complete
  Markdown section with heading, description, and caveats.

Caveats:
    - The diagram is a **static, simplified representation** of the
      runtime architecture.  It shows the intended data-flow direction
      between layers but does not capture every internal interaction
      (e.g., scene stack push/pop, entity component queries).
    - Layer descriptions are maintained manually alongside the actual
      module implementations.  If the architecture changes, this module
      must be updated to match.
    - The text rendering uses box-drawing characters (``─``, ``│``,
      ``┌``, etc.) which require a terminal or font that supports
      Unicode box-drawing.  On terminals limited to ASCII, the diagram
      may render incorrectly.
    - Diagram width is configurable but defaults to 72 columns.  Very
      narrow widths (below 40) may truncate layer names or descriptions.
"""

from __future__ import annotations

import logging

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Layer catalog
# ---------------------------------------------------------------------------


class Layer:
    """A single layer in the wyby runtime architecture.

    Attributes:
        name: Short identifier for the layer (e.g., ``"Input"``).
        module: Primary module implementing this layer (e.g., ``"input"``).
        description: One-line explanation of what this layer does.
        data_flow_out: What this layer produces (e.g., ``"KeyEvent queue"``).
        responsibility: Clarifying note about what this layer does *not* do.

    Caveats:
        - ``module`` refers to the primary module only.  Some layers
          span multiple modules (e.g., rendering involves ``renderer``,
          ``grid``, ``color``, and ``layer``).
        - ``data_flow_out`` describes the *intended* output, not every
          possible side-effect or callback.
    """

    __slots__ = ("name", "module", "description", "data_flow_out", "responsibility")

    def __init__(
        self,
        *,
        name: str,
        module: str,
        description: str,
        data_flow_out: str,
        responsibility: str = "",
    ) -> None:
        self.name = name
        self.module = module
        self.description = description
        self.data_flow_out = data_flow_out
        self.responsibility = responsibility

    def __repr__(self) -> str:
        return (
            f"Layer(name={self.name!r}, module={self.module!r})"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Layer):
            return NotImplemented
        return (
            self.name == other.name
            and self.module == other.module
            and self.description == other.description
            and self.data_flow_out == other.data_flow_out
            and self.responsibility == other.responsibility
        )


# The runtime layers in update order (top = first in the pipeline).
#
# Caveat: this catalog is maintained manually and reflects the intended
# architecture from SCOPE.md.  If modules are restructured, the layers
# and their descriptions must be updated to match.
LAYERS: tuple[Layer, ...] = (
    Layer(
        name="Input",
        module="input",
        description=(
            "Polls stdin for keyboard/mouse events and produces "
            "a queue of KeyEvent values."
        ),
        data_flow_out="KeyEvent queue",
        responsibility=(
            "Does not know about scenes or entities.  No system-wide "
            "hooks — reads only from the process's own stdin."
        ),
    ),
    Layer(
        name="Game Loop",
        module="app",
        description=(
            "Fixed-timestep loop (default ~30 tps) using an accumulator "
            "pattern.  Drains input, calls update(), calls render()."
        ),
        data_flow_out="Tick delta (dt)",
        responsibility=(
            "Measures actual tick duration for diagnostics.  Does not "
            "own game state — delegates to the active scene."
        ),
    ),
    Layer(
        name="Scene Stack",
        module="scene",
        description=(
            "Stack of scenes with push/pop/replace transitions.  Only "
            "the top scene receives input."
        ),
        data_flow_out="Active scene reference",
        responsibility=(
            "Scenes own their entities and state.  No implicit global "
            "state is shared between scenes."
        ),
    ),
    Layer(
        name="Entity Model",
        module="entity",
        description=(
            "Simple entity containers with position, tags, and "
            "component composition.  Not a full ECS."
        ),
        data_flow_out="Entity state (position, components, tags)",
        responsibility=(
            "No archetype storage, no bitset masks, no system "
            "scheduling.  Game logic lives in Scene.update()."
        ),
    ),
    Layer(
        name="Renderer",
        module="renderer",
        description=(
            "Walks scene entities by z-order, writes them into a "
            "CellBuffer, converts to a Rich renderable for Live display."
        ),
        data_flow_out="Terminal output (via Rich Live)",
        responsibility=(
            "Does not modify game state.  The CellBuffer is the single "
            "source of truth for what appears on screen."
        ),
    ),
)


# ---------------------------------------------------------------------------
# Diagram caveats
# ---------------------------------------------------------------------------


class DiagramCaveat:
    """A caveat about the architecture diagram or the architecture itself.

    Attributes:
        topic: Short label (e.g., ``"Not a full ECS"``).
        description: Full explanation.

    Caveats:
        - These are documentation-only objects with no runtime effect.
    """

    __slots__ = ("topic", "description")

    def __init__(self, *, topic: str, description: str) -> None:
        self.topic = topic
        self.description = description

    def __repr__(self) -> str:
        return f"DiagramCaveat(topic={self.topic!r})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DiagramCaveat):
            return NotImplemented
        return (
            self.topic == other.topic
            and self.description == other.description
        )


# Architecture caveats — things the diagram simplifies or omits.
#
# Caveat: maintained manually.  Update when architectural decisions
# change or new subsystems are added.
DIAGRAM_CAVEATS: tuple[DiagramCaveat, ...] = (
    DiagramCaveat(
        topic="Simplified data flow",
        description=(
            "The diagram shows a linear pipeline from Input to Terminal.  "
            "In practice, scenes can push/pop other scenes, entities "
            "query each other via tags, and the event queue allows "
            "decoupled communication.  These interactions are not shown."
        ),
    ),
    DiagramCaveat(
        topic="Rich re-renders every frame",
        description=(
            "The Renderer layer uses Rich's Live display, which "
            "re-renders the full renderable on each frame.  There is "
            "no differential update or double-buffered surface.  "
            "Flicker is possible on slow terminals or large grids."
        ),
    ),
    DiagramCaveat(
        topic="Not a full ECS",
        description=(
            "The Entity Model layer is a simple container, not an "
            "Entity Component System.  There are no systems, no "
            "archetype storage, and no automatic component scheduling.  "
            "If your game outgrows this, use a dedicated ECS library "
            "(e.g., esper) and wyby only for rendering."
        ),
    ),
    DiagramCaveat(
        topic="No networking layer",
        description=(
            "Multiplayer networking is out of scope for v0.1.  The "
            "diagram does not include a network layer.  Adding "
            "networking later will likely require changes to the game "
            "loop and state management."
        ),
    ),
    DiagramCaveat(
        topic="No audio layer",
        description=(
            "Audio is out of scope.  Terminal games typically do not "
            "have audio, and adding it would require platform-specific "
            "dependencies outside wyby's design goals."
        ),
    ),
    DiagramCaveat(
        topic="Terminal cells are not square pixels",
        description=(
            "The Renderer outputs to a character cell grid, not a "
            "pixel grid.  Cells have roughly a 1:2 aspect ratio "
            "(taller than wide).  A 'square' game tile in cell "
            "coordinates will appear as a tall rectangle."
        ),
    ),
    DiagramCaveat(
        topic="Frame rate is terminal-dependent",
        description=(
            "Achievable frame rate depends on the terminal emulator, "
            "OS, grid size, and style complexity.  15-30 updates/second "
            "is realistic on modern terminals.  The diagram does not "
            "convey performance characteristics."
        ),
    ),
)


# ---------------------------------------------------------------------------
# Diagram data structure
# ---------------------------------------------------------------------------


class ArchitectureDiagram:
    """A text-based architecture diagram.

    Attributes:
        layers: The ordered list of architecture layers.
        caveats: Caveats about the diagram and architecture.
        width: Target width in columns for the rendered diagram.
        title: Diagram title.

    Caveats:
        - ``width`` is a target, not a guarantee.  Some content may
          extend slightly beyond the target width if layer names or
          descriptions are very long.
        - ``layers`` are in pipeline order (first = earliest in the
          update loop).  This is the intended reading order.
    """

    __slots__ = ("layers", "caveats", "width", "title")

    # Minimum and maximum supported widths.
    MIN_WIDTH = 40
    MAX_WIDTH = 120

    def __init__(
        self,
        *,
        layers: list[Layer] | None = None,
        caveats: list[DiagramCaveat] | None = None,
        width: int = 72,
        title: str = "wyby Runtime Architecture",
    ) -> None:
        if isinstance(width, bool) or not isinstance(width, int):
            raise TypeError(
                f"width must be an int, got {type(width).__name__}"
            )
        if width < self.MIN_WIDTH:
            raise ValueError(
                f"width must be >= {self.MIN_WIDTH}, got {width}"
            )
        if width > self.MAX_WIDTH:
            raise ValueError(
                f"width must be <= {self.MAX_WIDTH}, got {width}"
            )
        self.layers = layers if layers is not None else list(LAYERS)
        self.caveats = caveats if caveats is not None else list(DIAGRAM_CAVEATS)
        self.width = width
        self.title = title

    def __repr__(self) -> str:
        return (
            f"ArchitectureDiagram(title={self.title!r}, "
            f"layers={len(self.layers)}, width={self.width})"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ArchitectureDiagram):
            return NotImplemented
        return (
            self.layers == other.layers
            and self.caveats == other.caveats
            and self.width == other.width
            and self.title == other.title
        )


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------


def generate_diagram(
    *,
    width: int = 72,
    title: str = "wyby Runtime Architecture",
    include_caveats: bool = True,
) -> ArchitectureDiagram:
    """Generate an architecture diagram with the default layer stack.

    Args:
        width: Target diagram width in columns.  Clamped to
            [:attr:`ArchitectureDiagram.MIN_WIDTH`,
            :attr:`ArchitectureDiagram.MAX_WIDTH`].
        title: Title text for the diagram.
        include_caveats: Whether to include architecture caveats.

    Returns:
        An :class:`ArchitectureDiagram` populated with :data:`LAYERS`
        and optionally :data:`DIAGRAM_CAVEATS`.

    Raises:
        TypeError: If *width* is not an int.
        ValueError: If *width* is out of the allowed range.

    Caveats:
        - The diagram always uses the full :data:`LAYERS` catalog.
          There is no mechanism to generate a partial diagram (e.g.,
          only rendering layers).  Filter the ``layers`` attribute
          after generation if needed.
    """
    caveats = list(DIAGRAM_CAVEATS) if include_caveats else []

    diagram = ArchitectureDiagram(
        layers=list(LAYERS),
        caveats=caveats,
        width=width,
        title=title,
    )

    _logger.debug(
        "Generated architecture diagram: %d layers, width=%d, caveats=%d",
        len(diagram.layers),
        diagram.width,
        len(diagram.caveats),
    )

    return diagram


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------


def _centre_text(text: str, width: int) -> str:
    """Centre text within a given width, padding with spaces."""
    if len(text) >= width:
        return text[:width]
    padding = width - len(text)
    left = padding // 2
    right = padding - left
    return " " * left + text + " " * right


def _render_layer_box(layer: Layer, inner_width: int) -> list[str]:
    """Render a single layer as a bordered box.

    Returns a list of lines (without trailing newlines).

    Caveats:
        - Long descriptions are wrapped at word boundaries to fit
          within the box.  Very long words may still overflow.
    """
    lines: list[str] = []

    # Top border.
    lines.append("┌" + "─" * inner_width + "┐")

    # Layer name, centred and bold-marked.
    name_text = f"[ {layer.name} ]"
    lines.append("│" + _centre_text(name_text, inner_width) + "│")

    # Module reference.
    mod_text = f"wyby.{layer.module}"
    lines.append("│" + _centre_text(mod_text, inner_width) + "│")

    # Separator.
    lines.append("│" + "─" * inner_width + "│")

    # Description — word-wrap to fit.
    desc_width = inner_width - 2  # 1 space padding each side.
    words = layer.description.split()
    desc_lines: list[str] = []
    current_line = ""
    for word in words:
        if current_line and len(current_line) + 1 + len(word) > desc_width:
            desc_lines.append(current_line)
            current_line = word
        else:
            current_line = current_line + " " + word if current_line else word
    if current_line:
        desc_lines.append(current_line)

    for desc_line in desc_lines:
        padded = " " + desc_line.ljust(desc_width) + " "
        lines.append("│" + padded + "│")

    # Responsibility note (if present).
    if layer.responsibility:
        lines.append("│" + " " * inner_width + "│")
        resp_words = layer.responsibility.split()
        resp_lines: list[str] = []
        current_line = ""
        for word in resp_words:
            if current_line and len(current_line) + 1 + len(word) > desc_width:
                resp_lines.append(current_line)
                current_line = word
            else:
                current_line = current_line + " " + word if current_line else word
        if current_line:
            resp_lines.append(current_line)

        for resp_line in resp_lines:
            padded = " " + resp_line.ljust(desc_width) + " "
            lines.append("│" + padded + "│")

    # Bottom border.
    lines.append("└" + "─" * inner_width + "┘")

    return lines


def _render_arrow(inner_width: int, label: str) -> list[str]:
    """Render a data-flow arrow between layers.

    Returns a list of lines showing a downward arrow with a label.

    Caveats:
        - The arrow is centred within the given width.  Long labels
          are truncated.
    """
    lines: list[str] = []
    centre = inner_width // 2

    # Arrow shaft.
    shaft_line = " " * centre + "│" + " " * (inner_width - centre - 1)
    lines.append(" " + shaft_line + " ")

    # Label beside the arrow.
    label_text = f"  {label}"
    max_label = inner_width - centre - 1
    if len(label_text) > max_label:
        label_text = label_text[:max_label - 3] + "..."
    label_line = " " * centre + "│" + label_text
    label_line = label_line.ljust(inner_width + 2)
    lines.append(label_line)

    # Arrow head.
    head_line = " " * centre + "▼" + " " * (inner_width - centre - 1)
    lines.append(" " + head_line + " ")

    return lines


def format_diagram(diagram: ArchitectureDiagram) -> str:
    """Format an :class:`ArchitectureDiagram` as plain text.

    Produces a text rendering with:

    1. A centred title.
    2. A linear flow overview line.
    3. Detailed layer boxes connected by data-flow arrows.

    Args:
        diagram: The diagram to format.

    Returns:
        A multi-line plain-text string.

    Caveats:
        - The output uses Unicode box-drawing characters.  Terminals
          or fonts without box-drawing support will render incorrectly.
        - Layer descriptions are word-wrapped to fit the diagram width.
          Very long single words may overflow the box boundary.
    """
    # Inner width for box content (subtract the two border characters).
    inner_width = diagram.width - 2
    lines: list[str] = []

    # Title.
    lines.append(_centre_text(diagram.title, diagram.width))
    lines.append(_centre_text("=" * len(diagram.title), diagram.width))
    lines.append("")

    # Linear flow summary.
    if diagram.layers:
        flow_parts = [layer.name for layer in diagram.layers]
        flow_line = "  -->  ".join(flow_parts)
        lines.append(flow_line)
        lines.append("")

    # Detailed layer boxes with arrows.
    for i, layer in enumerate(diagram.layers):
        box_lines = _render_layer_box(layer, inner_width)
        lines.extend(box_lines)

        # Arrow between layers (not after the last one).
        if i < len(diagram.layers) - 1:
            arrow_lines = _render_arrow(inner_width, layer.data_flow_out)
            lines.extend(arrow_lines)

    return "\n".join(lines)


def format_diagram_markdown(diagram: ArchitectureDiagram) -> str:
    """Format an :class:`ArchitectureDiagram` as a Markdown section.

    Produces a complete Markdown section with:

    1. A heading and introduction.
    2. The diagram in a fenced code block.
    3. A responsibility boundaries summary.
    4. A caveats section (if caveats are present).

    Args:
        diagram: The diagram to format.

    Returns:
        A multi-line Markdown string.

    Caveats:
        - The output is plain Markdown, not a Rich renderable.
        - The fenced code block preserves exact spacing.  Markdown
          renderers that apply proportional fonts will break alignment.
    """
    lines: list[str] = []

    # Heading.
    lines.append(f"## {diagram.title}")
    lines.append("")
    lines.append(
        "The diagram below shows the runtime data-flow pipeline of a "
        "wyby game.  Each layer processes data and passes results "
        "downward to the next layer."
    )
    lines.append("")

    # Diagram in a fenced code block.
    lines.append("```")
    lines.append(format_diagram(diagram))
    lines.append("```")
    lines.append("")

    # Responsibility boundaries.
    lines.append("### Responsibility Boundaries")
    lines.append("")
    for layer in diagram.layers:
        if layer.responsibility:
            lines.append(f"- **{layer.name}**: {layer.responsibility}")
    lines.append("")

    # Caveats.
    if diagram.caveats:
        lines.append("### Architecture Caveats")
        lines.append("")
        for caveat in diagram.caveats:
            lines.append(f"- **{caveat.topic}**: {caveat.description}")
        lines.append("")

    return "\n".join(lines)
