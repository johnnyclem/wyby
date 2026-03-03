"""Tests for the example_readme module."""

from __future__ import annotations

import os
import textwrap

import pytest

from wyby.example_readme import (
    ExampleReadme,
    format_all_readmes,
    format_readme,
    generate_all_readmes,
    generate_example_readme,
)


# ---------------------------------------------------------------------------
# ExampleReadme construction and properties
# ---------------------------------------------------------------------------


class TestExampleReadme:
    """ExampleReadme construction, properties, and equality."""

    def test_attributes(self) -> None:
        r = ExampleReadme(
            path="/a/hello_world.py",
            title="Hello World",
            description="Minimal scene",
            detail="Extended description.",
            run_command="python examples/hello_world.py",
            controls=[("q", "quit")],
            caveats=["Requires TTY"],
        )
        assert r.path == "/a/hello_world.py"
        assert r.title == "Hello World"
        assert r.description == "Minimal scene"
        assert r.detail == "Extended description."
        assert r.run_command == "python examples/hello_world.py"
        assert r.controls == [("q", "quit")]
        assert r.caveats == ["Requires TTY"]

    def test_filename_property(self) -> None:
        r = ExampleReadme(path="/a/b/demo.py")
        assert r.filename == "demo.py"

    def test_default_controls_empty(self) -> None:
        r = ExampleReadme(path="/a.py")
        assert r.controls == []

    def test_default_caveats_empty(self) -> None:
        r = ExampleReadme(path="/a.py")
        assert r.caveats == []

    def test_repr(self) -> None:
        r = ExampleReadme(
            path="/demo.py",
            title="Demo",
            controls=[("q", "quit")],
            caveats=["needs TTY"],
        )
        text = repr(r)
        assert "demo.py" in text
        assert "Demo" in text
        assert "controls=1" in text
        assert "caveats=1" in text

    def test_equality(self) -> None:
        a = ExampleReadme(path="/a.py", title="A", description="desc")
        b = ExampleReadme(path="/a.py", title="A", description="desc")
        assert a == b

    def test_inequality(self) -> None:
        a = ExampleReadme(path="/a.py", title="A")
        b = ExampleReadme(path="/a.py", title="B")
        assert a != b

    def test_inequality_different_type(self) -> None:
        r = ExampleReadme(path="/a.py")
        assert r != "not a readme"


# ---------------------------------------------------------------------------
# generate_example_readme — single file
# ---------------------------------------------------------------------------


class TestGenerateExampleReadme:
    """generate_example_readme() on individual example files."""

    def test_basic_example(self, tmp_path: object) -> None:
        """A well-formed example should produce a complete README."""
        f = tmp_path / "hello_world.py"  # type: ignore[operator]
        f.write_text(
            textwrap.dedent('''\
            """Example: Minimal hello-world scene.

            The simplest possible wyby scene.

            Run this example::

                python examples/hello_world.py

            Caveats:
                - Requires a real terminal (TTY).
                - Terminal cells are ~1:2 aspect ratio.
            """

            from wyby.scene import Scene
            from wyby.grid import CellBuffer
            from wyby.input import KeyEvent
            from wyby.app import QuitSignal

            class HelloScene(Scene):
                def __init__(self):
                    super().__init__()
                    self.buffer = CellBuffer(10, 10)
                def handle_events(self, events):
                    for event in events:
                        if isinstance(event, KeyEvent) and event.key in ("q", "escape"):
                            raise QuitSignal
                def update(self, dt): pass
                def render(self):
                    self.buffer.clear()
                    hint = " Q:quit "
                    self.buffer.put_text(0, 0, hint)
            '''),
            encoding="utf-8",
        )
        readme = generate_example_readme(f)
        assert readme.title == "Hello World"
        assert "Minimal hello-world scene" in readme.description
        assert "simplest" in readme.detail.lower()
        assert "python examples/hello_world.py" in readme.run_command
        assert len(readme.caveats) == 2
        assert any("TTY" in c for c in readme.caveats)
        assert os.path.isabs(readme.path)

    def test_title_from_filename(self, tmp_path: object) -> None:
        """Title should be derived from the filename."""
        f = tmp_path / "snake_game.py"  # type: ignore[operator]
        f.write_text('"""A snake game."""\nx = 1\n', encoding="utf-8")
        readme = generate_example_readme(f)
        assert readme.title == "Snake Game"

    def test_no_docstring(self, tmp_path: object) -> None:
        """A file with no docstring should still produce a README."""
        f = tmp_path / "no_docs.py"  # type: ignore[operator]
        f.write_text("x = 1\n", encoding="utf-8")
        readme = generate_example_readme(f)
        assert readme.title == "No Docs"
        assert readme.description == ""
        assert readme.caveats == []
        # Should have a fallback run command.
        assert "no_docs.py" in readme.run_command

    def test_file_not_found(self) -> None:
        """Missing files should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            generate_example_readme("/nonexistent/path.py")

    def test_controls_extracted(self, tmp_path: object) -> None:
        """Controls should be extracted from hint strings."""
        f = tmp_path / "game.py"  # type: ignore[operator]
        f.write_text(
            textwrap.dedent('''\
            """A game."""
            hint = " Arrows:move Q:quit "
            '''),
            encoding="utf-8",
        )
        readme = generate_example_readme(f)
        keys = [k for k, _ in readme.controls]
        assert "Arrows" in keys
        assert "Q" in keys

    def test_caveats_multiline(self, tmp_path: object) -> None:
        """Multi-line caveats should be joined."""
        f = tmp_path / "multi.py"  # type: ignore[operator]
        f.write_text(
            textwrap.dedent('''\
            """Example: Multi-line caveats.

            Run this example::

                python examples/multi.py

            Caveats:
                - This is a long caveat that spans
                  multiple lines in the docstring.
                - Short caveat.
            """
            x = 1
            '''),
            encoding="utf-8",
        )
        readme = generate_example_readme(f)
        assert len(readme.caveats) == 2
        assert "spans multiple lines" in readme.caveats[0]

    def test_path_is_resolved(self, tmp_path: object) -> None:
        """The result path should be absolute."""
        f = tmp_path / "resolved.py"  # type: ignore[operator]
        f.write_text('"""A test."""\n', encoding="utf-8")
        readme = generate_example_readme(f)
        assert os.path.isabs(readme.path)


# ---------------------------------------------------------------------------
# generate_all_readmes — directory scanning
# ---------------------------------------------------------------------------


class TestGenerateAllReadmes:
    """generate_all_readmes() discovers and processes *.py files."""

    def test_empty_directory(self, tmp_path: object) -> None:
        result = generate_all_readmes(tmp_path)  # type: ignore[arg-type]
        assert result == []

    def test_nonexistent_directory(self, tmp_path: object) -> None:
        missing = tmp_path / "nope"  # type: ignore[operator]
        result = generate_all_readmes(missing)
        assert result == []

    def test_discovers_py_files(self, tmp_path: object) -> None:
        for name in ("a.py", "b.py"):
            (tmp_path / name).write_text(  # type: ignore[operator]
                f'"""Example {name}."""\nx = 1\n',
                encoding="utf-8",
            )
        result = generate_all_readmes(tmp_path)  # type: ignore[arg-type]
        assert len(result) == 2

    def test_ignores_non_py_files(self, tmp_path: object) -> None:
        (tmp_path / "readme.md").write_text("# hi\n", encoding="utf-8")  # type: ignore[operator]
        (tmp_path / "script.py").write_text('"""A script."""\n', encoding="utf-8")  # type: ignore[operator]
        result = generate_all_readmes(tmp_path)  # type: ignore[arg-type]
        assert len(result) == 1
        assert result[0].filename == "script.py"

    def test_ignores_subdirectories(self, tmp_path: object) -> None:
        sub = tmp_path / "subdir"  # type: ignore[operator]
        sub.mkdir()
        (sub / "hidden.py").write_text('"""Hidden."""\n', encoding="utf-8")
        (tmp_path / "top.py").write_text('"""Top."""\n', encoding="utf-8")  # type: ignore[operator]
        result = generate_all_readmes(tmp_path)  # type: ignore[arg-type]
        assert len(result) == 1
        assert result[0].filename == "top.py"

    def test_sorted_by_filename(self, tmp_path: object) -> None:
        for name in ("z.py", "a.py", "m.py"):
            (tmp_path / name).write_text(  # type: ignore[operator]
                f'"""Doc for {name}."""\n',
                encoding="utf-8",
            )
        result = generate_all_readmes(tmp_path)  # type: ignore[arg-type]
        filenames = [r.filename for r in result]
        assert filenames == ["a.py", "m.py", "z.py"]

    def test_default_examples_dir(self) -> None:
        """Default directory should find the bundled examples."""
        result = generate_all_readmes()
        filenames = [r.filename for r in result]
        assert "hello_world.py" in filenames

    def test_bundled_examples_have_descriptions(self) -> None:
        """All bundled examples should have non-empty descriptions."""
        results = generate_all_readmes()
        for r in results:
            assert r.description, f"{r.filename} has no description"

    def test_bundled_examples_have_caveats(self) -> None:
        """All bundled examples should have at least one caveat."""
        results = generate_all_readmes()
        for r in results:
            assert len(r.caveats) > 0, f"{r.filename} has no caveats"

    def test_bundled_examples_have_run_commands(self) -> None:
        """All bundled examples should have run commands."""
        results = generate_all_readmes()
        for r in results:
            assert r.run_command, f"{r.filename} has no run command"
            assert "python" in r.run_command


# ---------------------------------------------------------------------------
# format_readme — Markdown formatting
# ---------------------------------------------------------------------------


class TestFormatReadme:
    """format_readme() produces Markdown text."""

    def test_includes_title(self) -> None:
        readme = ExampleReadme(path="/demo.py", title="Demo Game")
        text = format_readme(readme)
        assert "# Demo Game" in text

    def test_includes_description(self) -> None:
        readme = ExampleReadme(
            path="/demo.py",
            title="Demo",
            description="A demo game.",
        )
        text = format_readme(readme)
        assert "A demo game." in text

    def test_includes_run_command(self) -> None:
        readme = ExampleReadme(
            path="/demo.py",
            title="Demo",
            run_command="python examples/demo.py",
        )
        text = format_readme(readme)
        assert "## How to Run" in text
        assert "python examples/demo.py" in text
        assert "```bash" in text

    def test_includes_controls_table(self) -> None:
        readme = ExampleReadme(
            path="/demo.py",
            title="Demo",
            controls=[("q", "quit"), ("Arrows", "move")],
        )
        text = format_readme(readme)
        assert "## Controls" in text
        assert "| Key | Action |" in text
        assert "| `q` | quit |" in text
        assert "| `Arrows` | move |" in text

    def test_no_controls_section_when_empty(self) -> None:
        readme = ExampleReadme(path="/demo.py", title="Demo", controls=[])
        text = format_readme(readme)
        assert "## Controls" not in text

    def test_includes_caveats(self) -> None:
        readme = ExampleReadme(
            path="/demo.py",
            title="Demo",
            caveats=["Requires TTY", "No resize support"],
        )
        text = format_readme(readme)
        assert "## Caveats" in text
        assert "- Requires TTY" in text
        assert "- No resize support" in text

    def test_no_caveats_section_when_empty(self) -> None:
        readme = ExampleReadme(path="/demo.py", title="Demo", caveats=[])
        text = format_readme(readme)
        assert "## Caveats" not in text

    def test_full_format(self) -> None:
        readme = ExampleReadme(
            path="/snake_game.py",
            title="Snake Game",
            description="A classic Snake game.",
            detail="Move the snake to eat food.",
            run_command="python examples/snake_game.py",
            controls=[("Arrows", "move"), ("Q", "quit")],
            caveats=["Requires TTY"],
        )
        text = format_readme(readme)
        assert "# Snake Game" in text
        assert "A classic Snake game." in text
        assert "Move the snake to eat food." in text
        assert "python examples/snake_game.py" in text
        assert "| `Arrows` | move |" in text
        assert "- Requires TTY" in text


# ---------------------------------------------------------------------------
# format_all_readmes — combined document
# ---------------------------------------------------------------------------


class TestFormatAllReadmes:
    """format_all_readmes() produces a combined Markdown document."""

    def test_empty_list(self) -> None:
        assert format_all_readmes([]) == "No examples found."

    def test_single_readme(self) -> None:
        readmes = [
            ExampleReadme(
                path="/demo.py",
                title="Demo",
                description="A demo.",
            ),
        ]
        text = format_all_readmes(readmes)
        assert "# Demo" in text
        assert "---" not in text

    def test_multiple_readmes_separated(self) -> None:
        readmes = [
            ExampleReadme(path="/a.py", title="A", description="First."),
            ExampleReadme(path="/b.py", title="B", description="Second."),
        ]
        text = format_all_readmes(readmes)
        assert "# A" in text
        assert "# B" in text
        assert "---" in text

    def test_bundled_examples_format(self) -> None:
        """Formatting all bundled example READMEs should not raise."""
        readmes = generate_all_readmes()
        text = format_all_readmes(readmes)
        assert len(text) > 0
        # Should contain at least one title.
        assert "# " in text
