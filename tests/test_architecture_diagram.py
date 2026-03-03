"""Tests for the architecture_diagram module."""

from __future__ import annotations

import pytest

from wyby.architecture_diagram import (
    DIAGRAM_CAVEATS,
    LAYERS,
    ArchitectureDiagram,
    DiagramCaveat,
    Layer,
    format_diagram,
    format_diagram_markdown,
    generate_diagram,
)


# ---------------------------------------------------------------------------
# Layer construction and equality
# ---------------------------------------------------------------------------


class TestLayer:
    """Layer construction, repr, and equality."""

    def test_attributes(self) -> None:
        layer = Layer(
            name="Input",
            module="input",
            description="Polls stdin for events.",
            data_flow_out="KeyEvent queue",
            responsibility="No system-wide hooks.",
        )
        assert layer.name == "Input"
        assert layer.module == "input"
        assert layer.description == "Polls stdin for events."
        assert layer.data_flow_out == "KeyEvent queue"
        assert layer.responsibility == "No system-wide hooks."

    def test_default_responsibility(self) -> None:
        layer = Layer(
            name="X", module="x", description="X.", data_flow_out="X",
        )
        assert layer.responsibility == ""

    def test_repr(self) -> None:
        layer = Layer(
            name="Input", module="input", description="D.",
            data_flow_out="out",
        )
        r = repr(layer)
        assert "Input" in r
        assert "input" in r

    def test_equality(self) -> None:
        a = Layer(
            name="X", module="x", description="D.",
            data_flow_out="out",
        )
        b = Layer(
            name="X", module="x", description="D.",
            data_flow_out="out",
        )
        assert a == b

    def test_inequality_different_name(self) -> None:
        a = Layer(
            name="X", module="x", description="D.",
            data_flow_out="out",
        )
        b = Layer(
            name="Y", module="x", description="D.",
            data_flow_out="out",
        )
        assert a != b

    def test_inequality_different_type(self) -> None:
        layer = Layer(
            name="X", module="x", description="D.",
            data_flow_out="out",
        )
        assert layer != "not a layer"


# ---------------------------------------------------------------------------
# DiagramCaveat construction and equality
# ---------------------------------------------------------------------------


class TestDiagramCaveat:
    """DiagramCaveat construction, repr, and equality."""

    def test_attributes(self) -> None:
        c = DiagramCaveat(topic="No ECS", description="Simple container.")
        assert c.topic == "No ECS"
        assert c.description == "Simple container."

    def test_repr(self) -> None:
        c = DiagramCaveat(topic="No ECS", description="Simple container.")
        r = repr(c)
        assert "No ECS" in r

    def test_equality(self) -> None:
        a = DiagramCaveat(topic="X", description="Y")
        b = DiagramCaveat(topic="X", description="Y")
        assert a == b

    def test_inequality_different_topic(self) -> None:
        a = DiagramCaveat(topic="X", description="Y")
        b = DiagramCaveat(topic="Z", description="Y")
        assert a != b

    def test_inequality_different_type(self) -> None:
        c = DiagramCaveat(topic="X", description="Y")
        assert c != "not a caveat"


# ---------------------------------------------------------------------------
# ArchitectureDiagram construction and validation
# ---------------------------------------------------------------------------


class TestArchitectureDiagram:
    """ArchitectureDiagram construction, validation, and equality."""

    def test_default_construction(self) -> None:
        d = ArchitectureDiagram()
        assert d.width == 72
        assert d.title == "wyby Runtime Architecture"
        assert len(d.layers) == len(LAYERS)
        assert len(d.caveats) == len(DIAGRAM_CAVEATS)

    def test_custom_width(self) -> None:
        d = ArchitectureDiagram(width=60)
        assert d.width == 60

    def test_custom_title(self) -> None:
        d = ArchitectureDiagram(title="Custom Title")
        assert d.title == "Custom Title"

    def test_empty_layers(self) -> None:
        d = ArchitectureDiagram(layers=[])
        assert d.layers == []

    def test_empty_caveats(self) -> None:
        d = ArchitectureDiagram(caveats=[])
        assert d.caveats == []

    def test_width_too_small(self) -> None:
        with pytest.raises(ValueError, match=">="):
            ArchitectureDiagram(width=20)

    def test_width_too_large(self) -> None:
        with pytest.raises(ValueError, match="<="):
            ArchitectureDiagram(width=200)

    def test_width_not_int(self) -> None:
        with pytest.raises(TypeError, match="int"):
            ArchitectureDiagram(width="72")  # type: ignore[arg-type]

    def test_width_bool_rejected(self) -> None:
        with pytest.raises(TypeError, match="int"):
            ArchitectureDiagram(width=True)  # type: ignore[arg-type]

    def test_repr(self) -> None:
        d = ArchitectureDiagram()
        r = repr(d)
        assert "wyby Runtime Architecture" in r
        assert str(len(LAYERS)) in r
        assert "72" in r

    def test_equality(self) -> None:
        a = ArchitectureDiagram(width=60, title="T", layers=[], caveats=[])
        b = ArchitectureDiagram(width=60, title="T", layers=[], caveats=[])
        assert a == b

    def test_inequality_different_width(self) -> None:
        a = ArchitectureDiagram(width=60)
        b = ArchitectureDiagram(width=72)
        assert a != b

    def test_inequality_different_type(self) -> None:
        d = ArchitectureDiagram()
        assert d != "not a diagram"

    def test_min_width_boundary(self) -> None:
        d = ArchitectureDiagram(width=ArchitectureDiagram.MIN_WIDTH)
        assert d.width == ArchitectureDiagram.MIN_WIDTH

    def test_max_width_boundary(self) -> None:
        d = ArchitectureDiagram(width=ArchitectureDiagram.MAX_WIDTH)
        assert d.width == ArchitectureDiagram.MAX_WIDTH


# ---------------------------------------------------------------------------
# LAYERS catalog
# ---------------------------------------------------------------------------


class TestLayersCatalog:
    """Verify the LAYERS catalog structure."""

    def test_layers_not_empty(self) -> None:
        assert len(LAYERS) > 0

    def test_all_layers_have_names(self) -> None:
        for layer in LAYERS:
            assert layer.name, f"Layer with module {layer.module!r} has no name"

    def test_all_layers_have_modules(self) -> None:
        for layer in LAYERS:
            assert layer.module, f"Layer {layer.name!r} has no module"

    def test_all_layers_have_descriptions(self) -> None:
        for layer in LAYERS:
            assert layer.description, f"Layer {layer.name!r} has no description"

    def test_all_layers_have_data_flow(self) -> None:
        for layer in LAYERS:
            assert layer.data_flow_out, (
                f"Layer {layer.name!r} has no data_flow_out"
            )

    def test_expected_layer_names(self) -> None:
        """Verify the five expected architecture layers are present."""
        names = [layer.name for layer in LAYERS]
        assert "Input" in names
        assert "Game Loop" in names
        assert "Scene Stack" in names
        assert "Entity Model" in names
        assert "Renderer" in names

    def test_layer_order(self) -> None:
        """Layers are in pipeline order: Input first, Renderer last."""
        assert LAYERS[0].name == "Input"
        assert LAYERS[-1].name == "Renderer"

    def test_unique_layer_names(self) -> None:
        names = [layer.name for layer in LAYERS]
        assert len(names) == len(set(names))


# ---------------------------------------------------------------------------
# DIAGRAM_CAVEATS catalog
# ---------------------------------------------------------------------------


class TestDiagramCaveatsCatalog:
    """Verify the DIAGRAM_CAVEATS catalog structure."""

    def test_caveats_not_empty(self) -> None:
        assert len(DIAGRAM_CAVEATS) > 0

    def test_all_caveats_have_topics(self) -> None:
        for caveat in DIAGRAM_CAVEATS:
            assert caveat.topic, "Caveat has no topic"

    def test_all_caveats_have_descriptions(self) -> None:
        for caveat in DIAGRAM_CAVEATS:
            assert caveat.description, (
                f"Caveat {caveat.topic!r} has no description"
            )

    def test_unique_topics(self) -> None:
        topics = [c.topic for c in DIAGRAM_CAVEATS]
        assert len(topics) == len(set(topics))


# ---------------------------------------------------------------------------
# generate_diagram
# ---------------------------------------------------------------------------


class TestGenerateDiagram:
    """generate_diagram() function."""

    def test_default_diagram(self) -> None:
        d = generate_diagram()
        assert len(d.layers) == len(LAYERS)
        assert len(d.caveats) == len(DIAGRAM_CAVEATS)
        assert d.width == 72

    def test_custom_width(self) -> None:
        d = generate_diagram(width=60)
        assert d.width == 60

    def test_custom_title(self) -> None:
        d = generate_diagram(title="My Diagram")
        assert d.title == "My Diagram"

    def test_without_caveats(self) -> None:
        d = generate_diagram(include_caveats=False)
        assert d.caveats == []
        assert len(d.layers) == len(LAYERS)

    def test_invalid_width_type(self) -> None:
        with pytest.raises(TypeError):
            generate_diagram(width=3.14)  # type: ignore[arg-type]

    def test_invalid_width_value(self) -> None:
        with pytest.raises(ValueError):
            generate_diagram(width=10)


# ---------------------------------------------------------------------------
# format_diagram — plain text output
# ---------------------------------------------------------------------------


class TestFormatDiagram:
    """format_diagram() plain text output."""

    def test_contains_title(self) -> None:
        d = generate_diagram()
        output = format_diagram(d)
        assert "wyby Runtime Architecture" in output

    def test_contains_flow_summary(self) -> None:
        d = generate_diagram()
        output = format_diagram(d)
        assert "Input" in output
        assert "-->" in output
        assert "Renderer" in output

    def test_contains_all_layer_names(self) -> None:
        d = generate_diagram()
        output = format_diagram(d)
        for layer in LAYERS:
            assert f"[ {layer.name} ]" in output

    def test_contains_module_references(self) -> None:
        d = generate_diagram()
        output = format_diagram(d)
        for layer in LAYERS:
            assert f"wyby.{layer.module}" in output

    def test_contains_box_drawing(self) -> None:
        d = generate_diagram()
        output = format_diagram(d)
        assert "┌" in output
        assert "┐" in output
        assert "└" in output
        assert "┘" in output
        assert "│" in output

    def test_contains_arrows(self) -> None:
        d = generate_diagram()
        output = format_diagram(d)
        assert "▼" in output

    def test_contains_data_flow_labels(self) -> None:
        d = generate_diagram()
        output = format_diagram(d)
        # At least the first layer's data flow label should appear
        # (last layer has no arrow).
        assert LAYERS[0].data_flow_out in output

    def test_empty_layers(self) -> None:
        d = ArchitectureDiagram(layers=[], caveats=[])
        output = format_diagram(d)
        assert d.title in output
        # No boxes or arrows.
        assert "┌" not in output
        assert "▼" not in output

    def test_single_layer_no_arrow(self) -> None:
        """A diagram with one layer should have a box but no arrow."""
        single = Layer(
            name="Only", module="only", description="The only layer.",
            data_flow_out="nothing",
        )
        d = ArchitectureDiagram(layers=[single], caveats=[])
        output = format_diagram(d)
        assert "[ Only ]" in output
        assert "▼" not in output

    def test_custom_width_affects_output(self) -> None:
        d1 = generate_diagram(width=50)
        d2 = generate_diagram(width=90)
        out1 = format_diagram(d1)
        out2 = format_diagram(d2)
        # The wider diagram should have wider box borders.
        border1 = [ln for ln in out1.splitlines() if ln.startswith("┌")]
        border2 = [ln for ln in out2.splitlines() if ln.startswith("┌")]
        if border1 and border2:
            assert len(border2[0]) > len(border1[0])

    def test_description_word_wrapping(self) -> None:
        """Long descriptions should be wrapped, not overflow."""
        long_layer = Layer(
            name="Test",
            module="test",
            description="A " + "very " * 50 + "long description.",
            data_flow_out="output",
        )
        d = ArchitectureDiagram(
            layers=[long_layer], caveats=[], width=50,
        )
        output = format_diagram(d)
        for line in output.splitlines():
            # Lines within boxes should not wildly exceed the width.
            # Allow some slack for edge cases.
            assert len(line) <= d.width + 2


# ---------------------------------------------------------------------------
# format_diagram_markdown — Markdown output
# ---------------------------------------------------------------------------


class TestFormatDiagramMarkdown:
    """format_diagram_markdown() Markdown output."""

    def test_contains_heading(self) -> None:
        d = generate_diagram()
        output = format_diagram_markdown(d)
        assert "## wyby Runtime Architecture" in output

    def test_contains_fenced_code_block(self) -> None:
        d = generate_diagram()
        output = format_diagram_markdown(d)
        assert output.count("```") == 2

    def test_contains_introduction(self) -> None:
        d = generate_diagram()
        output = format_diagram_markdown(d)
        assert "data-flow pipeline" in output

    def test_contains_responsibility_section(self) -> None:
        d = generate_diagram()
        output = format_diagram_markdown(d)
        assert "### Responsibility Boundaries" in output

    def test_contains_responsibility_entries(self) -> None:
        d = generate_diagram()
        output = format_diagram_markdown(d)
        for layer in LAYERS:
            if layer.responsibility:
                assert f"**{layer.name}**" in output

    def test_contains_caveats_section(self) -> None:
        d = generate_diagram()
        output = format_diagram_markdown(d)
        assert "### Architecture Caveats" in output

    def test_contains_caveat_entries(self) -> None:
        d = generate_diagram()
        output = format_diagram_markdown(d)
        for caveat in DIAGRAM_CAVEATS:
            assert caveat.topic in output

    def test_no_caveats_section_when_empty(self) -> None:
        d = generate_diagram(include_caveats=False)
        output = format_diagram_markdown(d)
        assert "### Architecture Caveats" not in output

    def test_diagram_is_inside_code_block(self) -> None:
        d = generate_diagram()
        output = format_diagram_markdown(d)
        # Find content between the ``` markers.
        parts = output.split("```")
        assert len(parts) >= 3
        diagram_content = parts[1]
        # The diagram content should contain box characters.
        assert "┌" in diagram_content
        assert "│" in diagram_content
