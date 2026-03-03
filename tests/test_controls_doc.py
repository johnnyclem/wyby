"""Tests for the controls_doc module."""

from __future__ import annotations

import textwrap

import pytest

from wyby.controls_doc import (
    CONTROL_CAVEATS,
    SUPPORTED_KEYS,
    ControlCaveat,
    ControlsDoc,
    SupportedKey,
    caveats_by_category,
    controls_for_all_examples,
    controls_for_example,
    format_all_controls_docs,
    format_controls_doc,
    format_controls_reference,
    keys_by_category,
)


# ---------------------------------------------------------------------------
# SupportedKey
# ---------------------------------------------------------------------------


class TestSupportedKey:
    """SupportedKey construction, repr, and equality."""

    def test_attributes(self) -> None:
        key = SupportedKey(
            name="up", label="Up Arrow", category="arrow",
        )
        assert key.name == "up"
        assert key.label == "Up Arrow"
        assert key.category == "arrow"
        assert key.caveat is None

    def test_with_caveat(self) -> None:
        key = SupportedKey(
            name="enter",
            label="Enter",
            category="special",
            caveat="Ambiguous with Ctrl+M",
        )
        assert key.caveat == "Ambiguous with Ctrl+M"

    def test_repr(self) -> None:
        key = SupportedKey(name="up", label="Up Arrow", category="arrow")
        text = repr(key)
        assert "up" in text
        assert "Up Arrow" in text
        assert "arrow" in text

    def test_equality(self) -> None:
        a = SupportedKey(name="up", label="Up Arrow", category="arrow")
        b = SupportedKey(name="up", label="Up Arrow", category="arrow")
        assert a == b

    def test_inequality(self) -> None:
        a = SupportedKey(name="up", label="Up Arrow", category="arrow")
        b = SupportedKey(name="down", label="Down Arrow", category="arrow")
        assert a != b

    def test_inequality_different_type(self) -> None:
        key = SupportedKey(name="up", label="Up Arrow", category="arrow")
        assert key != "not a key"


# ---------------------------------------------------------------------------
# SUPPORTED_KEYS catalog
# ---------------------------------------------------------------------------


class TestSupportedKeysCatalog:
    """SUPPORTED_KEYS catalog completeness and structure."""

    def test_not_empty(self) -> None:
        assert len(SUPPORTED_KEYS) > 0

    def test_all_are_supported_key(self) -> None:
        for key in SUPPORTED_KEYS:
            assert isinstance(key, SupportedKey)

    def test_arrow_keys_present(self) -> None:
        arrow_names = {k.name for k in SUPPORTED_KEYS if k.category == "arrow"}
        assert "up" in arrow_names
        assert "down" in arrow_names
        assert "left" in arrow_names
        assert "right" in arrow_names

    def test_special_keys_present(self) -> None:
        special_names = {k.name for k in SUPPORTED_KEYS if k.category == "special"}
        assert "enter" in special_names
        assert "escape" in special_names
        assert "tab" in special_names
        assert "backspace" in special_names
        assert "space" in special_names

    def test_navigation_keys_present(self) -> None:
        nav_names = {k.name for k in SUPPORTED_KEYS if k.category == "navigation"}
        assert "home" in nav_names
        assert "end" in nav_names
        assert "pageup" in nav_names
        assert "pagedown" in nav_names

    def test_all_have_labels(self) -> None:
        for key in SUPPORTED_KEYS:
            assert key.label, f"Key {key.name!r} has no label"

    def test_all_have_categories(self) -> None:
        for key in SUPPORTED_KEYS:
            assert key.category, f"Key {key.name!r} has no category"


# ---------------------------------------------------------------------------
# keys_by_category
# ---------------------------------------------------------------------------


class TestKeysByCategory:
    """keys_by_category() grouping."""

    def test_returns_dict(self) -> None:
        result = keys_by_category()
        assert isinstance(result, dict)

    def test_has_expected_categories(self) -> None:
        result = keys_by_category()
        assert "arrow" in result
        assert "navigation" in result
        assert "special" in result
        assert "printable" in result

    def test_arrow_category_has_four_keys(self) -> None:
        result = keys_by_category()
        assert len(result["arrow"]) == 4

    def test_all_keys_accounted_for(self) -> None:
        result = keys_by_category()
        total = sum(len(v) for v in result.values())
        assert total == len(SUPPORTED_KEYS)


# ---------------------------------------------------------------------------
# ControlCaveat
# ---------------------------------------------------------------------------


class TestControlCaveat:
    """ControlCaveat construction, repr, and equality."""

    def test_attributes(self) -> None:
        caveat = ControlCaveat(
            topic="Ctrl+M vs Enter",
            description="They produce the same byte.",
            category="modifier",
        )
        assert caveat.topic == "Ctrl+M vs Enter"
        assert caveat.description == "They produce the same byte."
        assert caveat.category == "modifier"

    def test_repr(self) -> None:
        caveat = ControlCaveat(
            topic="XON/XOFF", description="...", category="terminal",
        )
        text = repr(caveat)
        assert "XON/XOFF" in text
        assert "terminal" in text

    def test_equality(self) -> None:
        a = ControlCaveat(topic="A", description="desc", category="modifier")
        b = ControlCaveat(topic="A", description="desc", category="modifier")
        assert a == b

    def test_inequality(self) -> None:
        a = ControlCaveat(topic="A", description="desc", category="modifier")
        b = ControlCaveat(topic="B", description="desc", category="modifier")
        assert a != b

    def test_inequality_different_type(self) -> None:
        caveat = ControlCaveat(
            topic="A", description="desc", category="modifier",
        )
        assert caveat != "not a caveat"


# ---------------------------------------------------------------------------
# CONTROL_CAVEATS catalog
# ---------------------------------------------------------------------------


class TestControlCaveatsCatalog:
    """CONTROL_CAVEATS catalog completeness and structure."""

    def test_not_empty(self) -> None:
        assert len(CONTROL_CAVEATS) > 0

    def test_all_are_control_caveat(self) -> None:
        for caveat in CONTROL_CAVEATS:
            assert isinstance(caveat, ControlCaveat)

    def test_has_modifier_caveats(self) -> None:
        cats = {c.category for c in CONTROL_CAVEATS}
        assert "modifier" in cats

    def test_has_terminal_caveats(self) -> None:
        cats = {c.category for c in CONTROL_CAVEATS}
        assert "terminal" in cats

    def test_has_platform_caveats(self) -> None:
        cats = {c.category for c in CONTROL_CAVEATS}
        assert "platform" in cats

    def test_has_mouse_caveats(self) -> None:
        cats = {c.category for c in CONTROL_CAVEATS}
        assert "mouse" in cats

    def test_all_have_topics(self) -> None:
        for caveat in CONTROL_CAVEATS:
            assert caveat.topic, f"Caveat has no topic: {caveat!r}"

    def test_all_have_descriptions(self) -> None:
        for caveat in CONTROL_CAVEATS:
            assert caveat.description, f"Caveat has no description: {caveat!r}"

    def test_ctrl_m_vs_enter_documented(self) -> None:
        topics = {c.topic for c in CONTROL_CAVEATS}
        assert "Ctrl+M vs Enter" in topics

    def test_shift_modifier_documented(self) -> None:
        topics = {c.topic for c in CONTROL_CAVEATS}
        assert "Shift modifier" in topics

    def test_alt_meta_documented(self) -> None:
        topics = {c.topic for c in CONTROL_CAVEATS}
        assert "Alt/Meta modifier" in topics


# ---------------------------------------------------------------------------
# caveats_by_category
# ---------------------------------------------------------------------------


class TestCaveatsByCategory:
    """caveats_by_category() grouping."""

    def test_returns_dict(self) -> None:
        result = caveats_by_category()
        assert isinstance(result, dict)

    def test_has_expected_categories(self) -> None:
        result = caveats_by_category()
        assert "modifier" in result
        assert "terminal" in result
        assert "platform" in result
        assert "mouse" in result

    def test_all_caveats_accounted_for(self) -> None:
        result = caveats_by_category()
        total = sum(len(v) for v in result.values())
        assert total == len(CONTROL_CAVEATS)


# ---------------------------------------------------------------------------
# ControlsDoc
# ---------------------------------------------------------------------------


class TestControlsDoc:
    """ControlsDoc construction, repr, and equality."""

    def test_attributes(self) -> None:
        doc = ControlsDoc(
            example_name="Snake Game",
            filename="snake_game.py",
            controls=[("Arrows", "move"), ("Q", "quit")],
            caveats=[
                ControlCaveat(
                    topic="A", description="desc", category="modifier",
                ),
            ],
            example_caveats=["Requires TTY"],
        )
        assert doc.example_name == "Snake Game"
        assert doc.filename == "snake_game.py"
        assert len(doc.controls) == 2
        assert len(doc.caveats) == 1
        assert len(doc.example_caveats) == 1

    def test_defaults(self) -> None:
        doc = ControlsDoc(
            example_name="Test", filename="test.py",
        )
        assert doc.controls == []
        assert doc.caveats == []
        assert doc.example_caveats == []

    def test_repr(self) -> None:
        doc = ControlsDoc(
            example_name="Demo",
            filename="demo.py",
            controls=[("q", "quit")],
        )
        text = repr(doc)
        assert "Demo" in text
        assert "controls=1" in text

    def test_equality(self) -> None:
        a = ControlsDoc(example_name="A", filename="a.py")
        b = ControlsDoc(example_name="A", filename="a.py")
        assert a == b

    def test_inequality(self) -> None:
        a = ControlsDoc(example_name="A", filename="a.py")
        b = ControlsDoc(example_name="B", filename="b.py")
        assert a != b

    def test_inequality_different_type(self) -> None:
        doc = ControlsDoc(example_name="A", filename="a.py")
        assert doc != "not a doc"


# ---------------------------------------------------------------------------
# controls_for_example — single file
# ---------------------------------------------------------------------------


class TestControlsForExample:
    """controls_for_example() on individual example files."""

    def test_basic_example(self, tmp_path: object) -> None:
        f = tmp_path / "snake_game.py"  # type: ignore[operator]
        f.write_text(
            textwrap.dedent('''\
            """Example: Classic Snake game.

            A snake game.

            Run this example::

                python examples/snake_game.py

            Caveats:
                - Requires a real terminal (TTY).
            """

            from wyby.input import KeyEvent

            class SnakeScene:
                def handle_events(self, events):
                    for event in events:
                        if isinstance(event, KeyEvent):
                            if event.key == "up":
                                pass
                            elif event.key == "q":
                                pass
                def render(self):
                    hint = " Arrows:move Q:quit "
            '''),
            encoding="utf-8",
        )
        doc = controls_for_example(f)
        assert doc.example_name == "Snake Game"
        assert doc.filename == "snake_game.py"
        assert len(doc.controls) > 0
        assert len(doc.caveats) > 0
        assert len(doc.example_caveats) > 0

    def test_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError):
            controls_for_example("/nonexistent/path.py")

    def test_no_controls(self, tmp_path: object) -> None:
        f = tmp_path / "empty.py"  # type: ignore[operator]
        f.write_text('"""An empty example."""\nx = 1\n', encoding="utf-8")
        doc = controls_for_example(f)
        assert doc.controls == []
        # Should still have framework caveats.
        assert len(doc.caveats) > 0

    def test_caveats_include_modifier_info(self, tmp_path: object) -> None:
        f = tmp_path / "game.py"  # type: ignore[operator]
        f.write_text(
            textwrap.dedent('''\
            """Example: A game."""
            hint = " Q:quit "
            '''),
            encoding="utf-8",
        )
        doc = controls_for_example(f)
        caveat_categories = {c.category for c in doc.caveats}
        # Modifier caveats are always included (they document what's
        # NOT detectable).
        assert "modifier" in caveat_categories


# ---------------------------------------------------------------------------
# controls_for_all_examples — directory scanning
# ---------------------------------------------------------------------------


class TestControlsForAllExamples:
    """controls_for_all_examples() discovers and processes *.py files."""

    def test_empty_directory(self, tmp_path: object) -> None:
        result = controls_for_all_examples(tmp_path)  # type: ignore[arg-type]
        assert result == []

    def test_nonexistent_directory(self, tmp_path: object) -> None:
        missing = tmp_path / "nope"  # type: ignore[operator]
        result = controls_for_all_examples(missing)
        assert result == []

    def test_discovers_py_files(self, tmp_path: object) -> None:
        for name in ("a.py", "b.py"):
            (tmp_path / name).write_text(  # type: ignore[operator]
                f'"""Example {name}."""\nx = 1\n',
                encoding="utf-8",
            )
        result = controls_for_all_examples(tmp_path)  # type: ignore[arg-type]
        assert len(result) == 2

    def test_ignores_non_py_files(self, tmp_path: object) -> None:
        (tmp_path / "readme.md").write_text("# hi\n", encoding="utf-8")  # type: ignore[operator]
        (tmp_path / "script.py").write_text(  # type: ignore[operator]
            '"""A script."""\n', encoding="utf-8",
        )
        result = controls_for_all_examples(tmp_path)  # type: ignore[arg-type]
        assert len(result) == 1

    def test_sorted_by_filename(self, tmp_path: object) -> None:
        for name in ("z.py", "a.py", "m.py"):
            (tmp_path / name).write_text(  # type: ignore[operator]
                f'"""Doc for {name}."""\n',
                encoding="utf-8",
            )
        result = controls_for_all_examples(tmp_path)  # type: ignore[arg-type]
        filenames = [d.filename for d in result]
        assert filenames == ["a.py", "m.py", "z.py"]

    def test_default_examples_dir(self) -> None:
        result = controls_for_all_examples()
        filenames = [d.filename for d in result]
        assert "hello_world.py" in filenames

    def test_bundled_examples_have_controls(self) -> None:
        """Most bundled examples should have at least one control."""
        results = controls_for_all_examples()
        examples_with_controls = [d for d in results if d.controls]
        # At least some examples should have detected controls.
        assert len(examples_with_controls) > 0

    def test_bundled_examples_have_caveats(self) -> None:
        """All bundled examples should have framework caveats."""
        results = controls_for_all_examples()
        for doc in results:
            assert len(doc.caveats) > 0, (
                f"{doc.filename} has no framework caveats"
            )


# ---------------------------------------------------------------------------
# format_controls_doc — Markdown formatting
# ---------------------------------------------------------------------------


class TestFormatControlsDoc:
    """format_controls_doc() produces Markdown text."""

    def test_includes_example_name(self) -> None:
        doc = ControlsDoc(
            example_name="Snake Game", filename="snake_game.py",
        )
        text = format_controls_doc(doc)
        assert "## Snake Game" in text

    def test_includes_controls_table(self) -> None:
        doc = ControlsDoc(
            example_name="Demo",
            filename="demo.py",
            controls=[("q", "quit"), ("Arrows", "move")],
        )
        text = format_controls_doc(doc)
        assert "### Controls" in text
        assert "| Key | Action |" in text
        assert "| `q` | quit |" in text
        assert "| `Arrows` | move |" in text

    def test_no_controls_message(self) -> None:
        doc = ControlsDoc(
            example_name="Demo", filename="demo.py", controls=[],
        )
        text = format_controls_doc(doc)
        assert "No controls detected" in text

    def test_includes_example_caveats(self) -> None:
        doc = ControlsDoc(
            example_name="Demo",
            filename="demo.py",
            example_caveats=["Requires TTY"],
        )
        text = format_controls_doc(doc)
        assert "### Example Caveats" in text
        assert "- Requires TTY" in text

    def test_includes_framework_caveats(self) -> None:
        doc = ControlsDoc(
            example_name="Demo",
            filename="demo.py",
            caveats=[
                ControlCaveat(
                    topic="Ctrl modifier",
                    description="Ctrl+A through Ctrl+Z.",
                    category="modifier",
                ),
            ],
        )
        text = format_controls_doc(doc)
        assert "### Input Caveats" in text
        assert "**Ctrl modifier**" in text

    def test_empty_doc_still_has_header(self) -> None:
        doc = ControlsDoc(
            example_name="Empty", filename="empty.py",
        )
        text = format_controls_doc(doc)
        assert "## Empty" in text


# ---------------------------------------------------------------------------
# format_controls_reference — full reference document
# ---------------------------------------------------------------------------


class TestFormatControlsReference:
    """format_controls_reference() produces a reference document."""

    def test_has_title(self) -> None:
        text = format_controls_reference()
        assert "# Controls Reference" in text

    def test_has_supported_keys_section(self) -> None:
        text = format_controls_reference()
        assert "## Supported Keys" in text

    def test_has_arrow_keys_section(self) -> None:
        text = format_controls_reference()
        assert "### Arrow Keys" in text

    def test_has_special_keys_section(self) -> None:
        text = format_controls_reference()
        assert "### Special Keys" in text

    def test_has_input_caveats_section(self) -> None:
        text = format_controls_reference()
        assert "## Input Caveats" in text

    def test_has_modifier_keys_section(self) -> None:
        text = format_controls_reference()
        assert "### Modifier Keys" in text

    def test_includes_key_names(self) -> None:
        text = format_controls_reference()
        assert "`up`" in text
        assert "`enter`" in text
        assert "`escape`" in text

    def test_includes_caveat_topics(self) -> None:
        text = format_controls_reference()
        assert "Ctrl+M vs Enter" in text
        assert "XON/XOFF" in text


# ---------------------------------------------------------------------------
# format_all_controls_docs — combined document
# ---------------------------------------------------------------------------


class TestFormatAllControlsDocs:
    """format_all_controls_docs() produces a combined document."""

    def test_empty_list(self) -> None:
        assert format_all_controls_docs([]) == "No examples found."

    def test_single_doc(self) -> None:
        docs = [
            ControlsDoc(
                example_name="Demo",
                filename="demo.py",
                controls=[("q", "quit")],
            ),
        ]
        text = format_all_controls_docs(docs)
        assert "## Demo" in text
        assert "| `q` | quit |" in text

    def test_multiple_docs_separated(self) -> None:
        docs = [
            ControlsDoc(example_name="A", filename="a.py"),
            ControlsDoc(example_name="B", filename="b.py"),
        ]
        text = format_all_controls_docs(docs)
        assert "## A" in text
        assert "## B" in text
        assert "---" in text

    def test_has_header(self) -> None:
        docs = [ControlsDoc(example_name="A", filename="a.py")]
        text = format_all_controls_docs(docs)
        assert "# Example Controls Documentation" in text

    def test_bundled_examples_format(self) -> None:
        """Formatting all bundled examples should not raise."""
        docs = controls_for_all_examples()
        text = format_all_controls_docs(docs)
        assert len(text) > 0
