"""Tests for the screenshot_placeholders module."""

from __future__ import annotations

import textwrap

import pytest

from wyby.screenshot_placeholders import (
    ScreenshotPlaceholder,
    format_all_placeholders,
    format_placeholder,
    generate_all_placeholders,
    generate_placeholder,
)


# ---------------------------------------------------------------------------
# ScreenshotPlaceholder construction, properties, and equality
# ---------------------------------------------------------------------------


class TestScreenshotPlaceholder:
    """ScreenshotPlaceholder construction, repr, and equality."""

    def test_attributes(self) -> None:
        sp = ScreenshotPlaceholder(
            path="/a/b/hello.py",
            title="Hello World",
            description="A greeting demo",
            width=40,
            height=12,
            elements=["Centred text"],
        )
        assert sp.path == "/a/b/hello.py"
        assert sp.title == "Hello World"
        assert sp.description == "A greeting demo"
        assert sp.width == 40
        assert sp.height == 12
        assert sp.elements == ["Centred text"]

    def test_defaults(self) -> None:
        sp = ScreenshotPlaceholder(path="/a.py")
        assert sp.title == ""
        assert sp.description == ""
        assert sp.width == 80
        assert sp.height == 24
        assert sp.elements == []

    def test_filename_property(self) -> None:
        sp = ScreenshotPlaceholder(path="/a/b/hello_world.py")
        assert sp.filename == "hello_world.py"

    def test_repr(self) -> None:
        sp = ScreenshotPlaceholder(
            path="/a/demo.py",
            title="Demo",
            width=60,
            height=20,
            elements=["Score display"],
        )
        r = repr(sp)
        assert "demo.py" in r
        assert "Demo" in r
        assert "60x20" in r
        assert "elements=1" in r

    def test_equality(self) -> None:
        a = ScreenshotPlaceholder(
            path="/a.py", title="X", width=40, height=12,
        )
        b = ScreenshotPlaceholder(
            path="/a.py", title="X", width=40, height=12,
        )
        assert a == b

    def test_inequality_different_title(self) -> None:
        a = ScreenshotPlaceholder(path="/a.py", title="X")
        b = ScreenshotPlaceholder(path="/a.py", title="Y")
        assert a != b

    def test_inequality_different_dimensions(self) -> None:
        a = ScreenshotPlaceholder(path="/a.py", width=40, height=12)
        b = ScreenshotPlaceholder(path="/a.py", width=80, height=24)
        assert a != b

    def test_inequality_different_type(self) -> None:
        sp = ScreenshotPlaceholder(path="/a.py")
        assert sp != "not a placeholder"


# ---------------------------------------------------------------------------
# generate_placeholder — single file
# ---------------------------------------------------------------------------


class TestGeneratePlaceholder:
    """generate_placeholder() on individual example files."""

    def test_basic_example(self, tmp_path: object) -> None:
        """Generates a placeholder from a simple example file."""
        f = tmp_path / "hello_world.py"  # type: ignore[operator]
        f.write_text(textwrap.dedent('''\
            """Example: A minimal hello-world scene."""

            from wyby.grid import CellBuffer

            class HelloScene:
                def __init__(self):
                    self.buffer = CellBuffer(40, 12)

                def render(self):
                    self.buffer.put_text(10, 6, "Hello, World!")
        '''), encoding="utf-8")

        sp = generate_placeholder(f)
        assert sp.title == "Hello World"
        assert sp.description == "A minimal hello-world scene."
        assert sp.width == 40
        assert sp.height == 12
        assert any("Hello, World!" in e for e in sp.elements)

    def test_engine_dimensions(self, tmp_path: object) -> None:
        """Extracts dimensions from Engine constructor kwargs."""
        f = tmp_path / "game_demo.py"  # type: ignore[operator]
        f.write_text(textwrap.dedent('''\
            """A game demo."""

            engine = Engine(title="demo", width=60, height=20, tps=30)
        '''), encoding="utf-8")

        sp = generate_placeholder(f)
        assert sp.width == 60
        assert sp.height == 20

    def test_default_dimensions_when_not_found(self, tmp_path: object) -> None:
        """Falls back to default dimensions when not detected."""
        f = tmp_path / "minimal.py"  # type: ignore[operator]
        f.write_text('"""A minimal script."""\nx = 1\n', encoding="utf-8")

        sp = generate_placeholder(f)
        assert sp.width == ScreenshotPlaceholder.DEFAULT_WIDTH
        assert sp.height == ScreenshotPlaceholder.DEFAULT_HEIGHT

    def test_no_docstring(self, tmp_path: object) -> None:
        """Returns empty description when no module docstring."""
        f = tmp_path / "no_doc.py"  # type: ignore[operator]
        f.write_text("x = 1\n", encoding="utf-8")

        sp = generate_placeholder(f)
        assert sp.description == ""

    def test_file_not_found(self) -> None:
        """Raises FileNotFoundError for missing files."""
        with pytest.raises(FileNotFoundError):
            generate_placeholder("/nonexistent/path.py")

    def test_score_element_detected(self, tmp_path: object) -> None:
        """Detects score display elements."""
        f = tmp_path / "game.py"  # type: ignore[operator]
        f.write_text(textwrap.dedent('''\
            """A game with score."""

            class Game:
                score = 0
                def render(self):
                    buf = CellBuffer(40, 12)
                    buf.put_text(0, 0, f"Score: {self.score}")
        '''), encoding="utf-8")

        sp = generate_placeholder(f)
        assert "Score display" in sp.elements

    def test_game_over_element_detected(self, tmp_path: object) -> None:
        """Detects game-over screen elements."""
        f = tmp_path / "game.py"  # type: ignore[operator]
        f.write_text(textwrap.dedent('''\
            """A game."""

            class Game:
                game_over = False
                def render(self):
                    buf = CellBuffer(40, 12)
        '''), encoding="utf-8")

        sp = generate_placeholder(f)
        assert "Game-over screen" in sp.elements

    def test_menu_element_detected(self, tmp_path: object) -> None:
        """Detects menu interface elements."""
        f = tmp_path / "menu_game.py"  # type: ignore[operator]
        f.write_text(textwrap.dedent('''\
            """A menu example."""

            class MenuScene:
                menu_items = ["Start", "Quit"]
        '''), encoding="utf-8")

        sp = generate_placeholder(f)
        assert "Menu interface" in sp.elements

    def test_health_element_detected(self, tmp_path: object) -> None:
        """Detects health indicator elements."""
        f = tmp_path / "health.py"  # type: ignore[operator]
        f.write_text(textwrap.dedent('''\
            """Health demo."""

            class Demo:
                health = 100
                def render(self):
                    buf = CellBuffer(50, 15)
        '''), encoding="utf-8")

        sp = generate_placeholder(f)
        assert "Health indicator" in sp.elements

    def test_paddle_and_ball_detected(self, tmp_path: object) -> None:
        """Detects paddle and ball elements (pong-like games)."""
        f = tmp_path / "pong.py"  # type: ignore[operator]
        f.write_text(textwrap.dedent('''\
            """Pong game."""

            class Pong:
                paddle_y = 5
                ball_x = 20
                ball_y = 10
        '''), encoding="utf-8")

        sp = generate_placeholder(f)
        assert "Paddle elements" in sp.elements
        assert "Ball element" in sp.elements

    def test_box_drawing_border_detected(self, tmp_path: object) -> None:
        """Detects box-drawing border characters."""
        f = tmp_path / "borders.py"  # type: ignore[operator]
        f.write_text(textwrap.dedent('''\
            """Border demo."""

            border_char = "─"
        '''), encoding="utf-8")

        sp = generate_placeholder(f)
        assert "Box-drawing border" in sp.elements

    def test_collectible_detected(self, tmp_path: object) -> None:
        """Detects food/collectible markers."""
        f = tmp_path / "snake.py"  # type: ignore[operator]
        f.write_text(textwrap.dedent('''\
            """Snake game."""

            class Snake:
                food = (10, 5)
        '''), encoding="utf-8")

        sp = generate_placeholder(f)
        assert "Collectible markers" in sp.elements


# ---------------------------------------------------------------------------
# generate_all_placeholders — directory scanning
# ---------------------------------------------------------------------------


class TestGenerateAllPlaceholders:
    """generate_all_placeholders() directory scanning."""

    def test_empty_directory(self, tmp_path: object) -> None:
        results = generate_all_placeholders(tmp_path)  # type: ignore[arg-type]
        assert results == []

    def test_nonexistent_directory(self, tmp_path: object) -> None:
        results = generate_all_placeholders(
            tmp_path / "nonexistent",  # type: ignore[operator]
        )
        assert results == []

    def test_discovers_py_files(self, tmp_path: object) -> None:
        (tmp_path / "alpha.py").write_text(  # type: ignore[operator]
            '"""Alpha example."""\n', encoding="utf-8",
        )
        (tmp_path / "beta.py").write_text(  # type: ignore[operator]
            '"""Beta example."""\n', encoding="utf-8",
        )
        # Non-Python file should be ignored.
        (tmp_path / "readme.md").write_text(  # type: ignore[operator]
            "# README\n", encoding="utf-8",
        )

        results = generate_all_placeholders(tmp_path)  # type: ignore[arg-type]
        assert len(results) == 2
        filenames = [p.filename for p in results]
        assert "alpha.py" in filenames
        assert "beta.py" in filenames

    def test_sorted_by_filename(self, tmp_path: object) -> None:
        (tmp_path / "zebra.py").write_text(  # type: ignore[operator]
            '"""Zebra."""\n', encoding="utf-8",
        )
        (tmp_path / "alpha.py").write_text(  # type: ignore[operator]
            '"""Alpha."""\n', encoding="utf-8",
        )

        results = generate_all_placeholders(tmp_path)  # type: ignore[arg-type]
        assert results[0].filename == "alpha.py"
        assert results[1].filename == "zebra.py"

    def test_skips_failing_files(self, tmp_path: object) -> None:
        """A file that fails to process does not block others."""
        (tmp_path / "good.py").write_text(  # type: ignore[operator]
            '"""Good example."""\n', encoding="utf-8",
        )
        # Create a subdirectory with .py suffix (unusual but possible).
        bad = tmp_path / "bad.py"  # type: ignore[operator]
        bad.mkdir()

        results = generate_all_placeholders(tmp_path)  # type: ignore[arg-type]
        assert len(results) == 1
        assert results[0].filename == "good.py"


# ---------------------------------------------------------------------------
# format_placeholder — single placeholder formatting
# ---------------------------------------------------------------------------


class TestFormatPlaceholder:
    """format_placeholder() output structure."""

    def test_contains_title_heading(self) -> None:
        sp = ScreenshotPlaceholder(
            path="/a/hello.py", title="Hello World",
        )
        output = format_placeholder(sp)
        assert "### Hello World" in output

    def test_contains_description(self) -> None:
        sp = ScreenshotPlaceholder(
            path="/a/hello.py",
            title="Hello World",
            description="A greeting demo.",
        )
        output = format_placeholder(sp)
        assert "A greeting demo." in output

    def test_contains_screenshot_label(self) -> None:
        sp = ScreenshotPlaceholder(
            path="/a/hello.py", title="Hello World",
        )
        output = format_placeholder(sp)
        assert "[Screenshot: Hello World]" in output

    def test_contains_dimensions(self) -> None:
        sp = ScreenshotPlaceholder(
            path="/a/hello.py",
            title="Hello World",
            width=40,
            height=12,
        )
        output = format_placeholder(sp)
        assert "40x12 character grid" in output

    def test_contains_elements(self) -> None:
        sp = ScreenshotPlaceholder(
            path="/a/hello.py",
            title="Hello World",
            elements=["Score display", "Health indicator"],
        )
        output = format_placeholder(sp)
        assert "Score display" in output
        assert "Health indicator" in output

    def test_fenced_code_block(self) -> None:
        sp = ScreenshotPlaceholder(path="/a/hello.py", title="Test")
        output = format_placeholder(sp)
        assert output.count("```") == 2

    def test_box_borders(self) -> None:
        sp = ScreenshotPlaceholder(path="/a/hello.py", title="Test")
        output = format_placeholder(sp)
        assert "┌" in output
        assert "┐" in output
        assert "└" in output
        assert "┘" in output
        assert "│" in output

    def test_minimum_box_width(self) -> None:
        """Box width is at least 40 even for narrow buffers."""
        sp = ScreenshotPlaceholder(
            path="/a/tiny.py", title="Tiny", width=10, height=5,
        )
        output = format_placeholder(sp)
        # Find the top border line and check its length.
        for line in output.splitlines():
            if line.startswith("┌"):
                assert len(line) >= 40
                break

    def test_maximum_box_width(self) -> None:
        """Box width is capped at 78 for very wide buffers."""
        sp = ScreenshotPlaceholder(
            path="/a/wide.py", title="Wide", width=200, height=50,
        )
        output = format_placeholder(sp)
        for line in output.splitlines():
            if line.startswith("┌"):
                assert len(line) <= 78
                break

    def test_no_elements_still_valid(self) -> None:
        """Placeholder without elements is still a valid box."""
        sp = ScreenshotPlaceholder(
            path="/a/simple.py", title="Simple",
        )
        output = format_placeholder(sp)
        assert "[Screenshot: Simple]" in output
        # Should have box borders.
        assert "┌" in output
        assert "┘" in output


# ---------------------------------------------------------------------------
# format_all_placeholders — document formatting
# ---------------------------------------------------------------------------


class TestFormatAllPlaceholders:
    """format_all_placeholders() document output."""

    def test_empty_list(self) -> None:
        assert format_all_placeholders([]) == "No examples found."

    def test_header(self) -> None:
        placeholders = [
            ScreenshotPlaceholder(path="/a.py", title="Alpha"),
        ]
        output = format_all_placeholders(placeholders)
        assert "## Screenshot Placeholders" in output

    def test_contains_all_placeholders(self) -> None:
        placeholders = [
            ScreenshotPlaceholder(path="/a.py", title="Alpha"),
            ScreenshotPlaceholder(path="/b.py", title="Beta"),
        ]
        output = format_all_placeholders(placeholders)
        assert "[Screenshot: Alpha]" in output
        assert "[Screenshot: Beta]" in output

    def test_contains_replacement_note(self) -> None:
        placeholders = [
            ScreenshotPlaceholder(path="/a.py", title="Alpha"),
        ]
        output = format_all_placeholders(placeholders)
        assert "Replace these with actual terminal screenshots" in output
