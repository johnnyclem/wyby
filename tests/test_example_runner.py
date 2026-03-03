"""Tests for the example_runner module."""

from __future__ import annotations

import os
import textwrap

from wyby.example_runner import (
    ExampleCheckResult,
    check_all_examples,
    check_example,
    format_check_results,
)


# ---------------------------------------------------------------------------
# ExampleCheckResult construction and properties
# ---------------------------------------------------------------------------


class TestExampleCheckResult:
    """ExampleCheckResult construction, properties, and equality."""

    def test_attributes(self) -> None:
        r = ExampleCheckResult(
            path="/a/hello.py",
            importable=True,
            scene_classes=["HelloScene"],
            scenes_constructed=1,
            lifecycle_ok=True,
        )
        assert r.path == "/a/hello.py"
        assert r.importable is True
        assert r.scene_classes == ["HelloScene"]
        assert r.scenes_constructed == 1
        assert r.lifecycle_ok is True
        assert r.error is None

    def test_filename_property(self) -> None:
        r = ExampleCheckResult(path="/a/b/demo.py")
        assert r.filename == "demo.py"

    def test_ok_when_all_pass(self) -> None:
        r = ExampleCheckResult(
            path="/a.py",
            importable=True,
            lifecycle_ok=True,
        )
        assert r.ok is True

    def test_not_ok_when_import_fails(self) -> None:
        r = ExampleCheckResult(
            path="/a.py",
            importable=False,
            error="ImportError",
        )
        assert r.ok is False

    def test_not_ok_when_lifecycle_fails(self) -> None:
        r = ExampleCheckResult(
            path="/a.py",
            importable=True,
            lifecycle_ok=False,
            error="render raised",
        )
        assert r.ok is False

    def test_not_ok_when_error_present(self) -> None:
        r = ExampleCheckResult(
            path="/a.py",
            importable=True,
            lifecycle_ok=True,
            error="some issue",
        )
        assert r.ok is False

    def test_repr(self) -> None:
        r = ExampleCheckResult(
            path="/demo.py",
            importable=True,
            scene_classes=["MyScene"],
            lifecycle_ok=True,
        )
        text = repr(r)
        assert "demo.py" in text
        assert "OK" in text
        assert "MyScene" in text

    def test_repr_fail(self) -> None:
        r = ExampleCheckResult(path="/fail.py", error="oops")
        text = repr(r)
        assert "FAIL" in text

    def test_equality(self) -> None:
        a = ExampleCheckResult(path="/a.py", importable=True, lifecycle_ok=True)
        b = ExampleCheckResult(path="/a.py", importable=True, lifecycle_ok=True)
        assert a == b

    def test_inequality(self) -> None:
        a = ExampleCheckResult(path="/a.py", importable=True)
        b = ExampleCheckResult(path="/a.py", importable=False)
        assert a != b

    def test_inequality_different_type(self) -> None:
        r = ExampleCheckResult(path="/a.py")
        assert r != "not a result"

    def test_default_caveats(self) -> None:
        r = ExampleCheckResult(path="/a.py")
        assert r.caveats == []

    def test_custom_caveats(self) -> None:
        r = ExampleCheckResult(path="/a.py", caveats=["needs TTY"])
        assert r.caveats == ["needs TTY"]


# ---------------------------------------------------------------------------
# check_example — single file validation
# ---------------------------------------------------------------------------


class TestCheckExample:
    """check_example() on individual example files."""

    def test_valid_example(self, tmp_path: object) -> None:
        """A well-formed example with a Scene subclass should pass."""
        f = tmp_path / "good_example.py"  # type: ignore[operator]
        f.write_text(
            textwrap.dedent("""\
            from wyby.scene import Scene
            from wyby.grid import CellBuffer

            class GoodScene(Scene):
                def __init__(self):
                    super().__init__()
                    self.buffer = CellBuffer(10, 10)

                def handle_events(self, events):
                    pass

                def update(self, dt):
                    pass

                def render(self):
                    self.buffer.clear()

            def main():
                pass

            if __name__ == "__main__":
                main()
            """),
            encoding="utf-8",
        )
        result = check_example(f)
        assert result.importable is True
        assert result.scene_classes == ["GoodScene"]
        assert result.scenes_constructed == 1
        assert result.lifecycle_ok is True
        assert result.ok is True
        assert result.error is None

    def test_nonexistent_file(self, tmp_path: object) -> None:
        """A missing file should fail at import."""
        missing = tmp_path / "nonexistent.py"  # type: ignore[operator]
        result = check_example(missing)
        assert result.importable is False
        assert result.ok is False
        assert result.error is not None

    def test_syntax_error(self, tmp_path: object) -> None:
        """A file with a syntax error should fail at import."""
        f = tmp_path / "bad_syntax.py"  # type: ignore[operator]
        f.write_text("def broken(\n", encoding="utf-8")
        result = check_example(f)
        assert result.importable is False
        assert result.ok is False
        assert "Import failed" in result.error

    def test_no_scene_subclass(self, tmp_path: object) -> None:
        """A file with no Scene subclass should fail gracefully."""
        f = tmp_path / "no_scene.py"  # type: ignore[operator]
        f.write_text(
            textwrap.dedent("""\
            x = 42

            def main():
                pass
            """),
            encoding="utf-8",
        )
        result = check_example(f)
        assert result.importable is True
        assert result.scene_classes == []
        assert result.lifecycle_ok is False
        assert result.ok is False
        assert "No Scene subclasses" in result.error

    def test_scene_construction_failure(self, tmp_path: object) -> None:
        """A scene that raises in __init__ should be reported."""
        f = tmp_path / "bad_init.py"  # type: ignore[operator]
        f.write_text(
            textwrap.dedent("""\
            from wyby.scene import Scene

            class BadScene(Scene):
                def __init__(self):
                    raise RuntimeError("boom")

                def handle_events(self, events):
                    pass

                def update(self, dt):
                    pass

                def render(self):
                    pass
            """),
            encoding="utf-8",
        )
        result = check_example(f)
        assert result.importable is True
        assert result.scene_classes == ["BadScene"]
        assert result.scenes_constructed == 0
        assert result.lifecycle_ok is False
        assert "construction failed" in result.error

    def test_lifecycle_failure(self, tmp_path: object) -> None:
        """A scene that raises in render() should be reported."""
        f = tmp_path / "bad_render.py"  # type: ignore[operator]
        f.write_text(
            textwrap.dedent("""\
            from wyby.scene import Scene

            class CrashScene(Scene):
                def __init__(self):
                    super().__init__()

                def handle_events(self, events):
                    pass

                def update(self, dt):
                    pass

                def render(self):
                    raise ValueError("render failed")
            """),
            encoding="utf-8",
        )
        result = check_example(f)
        assert result.importable is True
        assert result.scenes_constructed == 1
        assert result.lifecycle_ok is False
        assert "lifecycle error" in result.error

    def test_multiple_scene_classes(self, tmp_path: object) -> None:
        """A file with multiple Scene subclasses should check all."""
        f = tmp_path / "multi_scene.py"  # type: ignore[operator]
        f.write_text(
            textwrap.dedent("""\
            from wyby.scene import Scene
            from wyby.grid import CellBuffer

            class SceneA(Scene):
                def __init__(self):
                    super().__init__()
                    self.buffer = CellBuffer(10, 10)
                def handle_events(self, events): pass
                def update(self, dt): pass
                def render(self): self.buffer.clear()

            class SceneB(Scene):
                def __init__(self):
                    super().__init__()
                    self.buffer = CellBuffer(10, 10)
                def handle_events(self, events): pass
                def update(self, dt): pass
                def render(self): self.buffer.clear()
            """),
            encoding="utf-8",
        )
        result = check_example(f)
        assert result.importable is True
        assert len(result.scene_classes) == 2
        assert result.scenes_constructed == 2
        assert result.lifecycle_ok is True

    def test_caveats_populated(self, tmp_path: object) -> None:
        """Results should include common caveats."""
        f = tmp_path / "any_example.py"  # type: ignore[operator]
        f.write_text(
            textwrap.dedent("""\
            from wyby.scene import Scene
            from wyby.grid import CellBuffer

            class SimpleScene(Scene):
                def __init__(self):
                    super().__init__()
                    self.buffer = CellBuffer(10, 10)
                def handle_events(self, events): pass
                def update(self, dt): pass
                def render(self): self.buffer.clear()
            """),
            encoding="utf-8",
        )
        result = check_example(f)
        assert len(result.caveats) > 0
        assert any("TTY" in c for c in result.caveats)

    def test_path_is_resolved(self, tmp_path: object) -> None:
        """The result path should be absolute."""
        f = tmp_path / "resolved.py"  # type: ignore[operator]
        f.write_text("x = 1\n", encoding="utf-8")
        result = check_example(f)
        assert os.path.isabs(result.path)


# ---------------------------------------------------------------------------
# check_all_examples — directory scanning
# ---------------------------------------------------------------------------


class TestCheckAllExamples:
    """check_all_examples() discovers and validates *.py files."""

    def test_empty_directory(self, tmp_path: object) -> None:
        result = check_all_examples(tmp_path)  # type: ignore[arg-type]
        assert result == []

    def test_nonexistent_directory(self, tmp_path: object) -> None:
        missing = tmp_path / "nope"  # type: ignore[operator]
        result = check_all_examples(missing)
        assert result == []

    def test_discovers_py_files(self, tmp_path: object) -> None:
        for name in ("a.py", "b.py"):
            (tmp_path / name).write_text(  # type: ignore[operator]
                textwrap.dedent("""\
                from wyby.scene import Scene
                from wyby.grid import CellBuffer

                class TestScene(Scene):
                    def __init__(self):
                        super().__init__()
                        self.buffer = CellBuffer(10, 10)
                    def handle_events(self, events): pass
                    def update(self, dt): pass
                    def render(self): self.buffer.clear()
                """),
                encoding="utf-8",
            )
        result = check_all_examples(tmp_path)  # type: ignore[arg-type]
        assert len(result) == 2

    def test_ignores_non_py_files(self, tmp_path: object) -> None:
        (tmp_path / "readme.md").write_text("# hi\n", encoding="utf-8")  # type: ignore[operator]
        (tmp_path / "script.py").write_text(  # type: ignore[operator]
            textwrap.dedent("""\
            from wyby.scene import Scene
            from wyby.grid import CellBuffer

            class S(Scene):
                def __init__(self):
                    super().__init__()
                    self.buffer = CellBuffer(10, 10)
                def handle_events(self, events): pass
                def update(self, dt): pass
                def render(self): self.buffer.clear()
            """),
            encoding="utf-8",
        )
        result = check_all_examples(tmp_path)  # type: ignore[arg-type]
        assert len(result) == 1
        assert result[0].filename == "script.py"

    def test_ignores_subdirectories(self, tmp_path: object) -> None:
        sub = tmp_path / "subdir"  # type: ignore[operator]
        sub.mkdir()
        (sub / "hidden.py").write_text("pass\n", encoding="utf-8")
        (tmp_path / "top.py").write_text("pass\n", encoding="utf-8")  # type: ignore[operator]
        result = check_all_examples(tmp_path)  # type: ignore[arg-type]
        assert len(result) == 1
        assert result[0].filename == "top.py"

    def test_sorted_by_filename(self, tmp_path: object) -> None:
        for name in ("z.py", "a.py", "m.py"):
            (tmp_path / name).write_text("x = 1\n", encoding="utf-8")  # type: ignore[operator]
        result = check_all_examples(tmp_path)  # type: ignore[arg-type]
        filenames = [r.filename for r in result]
        assert filenames == ["a.py", "m.py", "z.py"]

    def test_default_examples_dir(self) -> None:
        """Default directory should find the bundled examples."""
        result = check_all_examples()
        filenames = [r.filename for r in result]
        assert "hello_world.py" in filenames

    def test_bundled_examples_all_importable(self) -> None:
        """All bundled examples should be importable."""
        results = check_all_examples()
        for r in results:
            assert r.importable, f"{r.filename} failed to import: {r.error}"

    def test_bundled_examples_all_pass(self) -> None:
        """All bundled examples should pass validation."""
        results = check_all_examples()
        for r in results:
            assert r.ok, f"{r.filename} failed: {r.error}"

    def test_bundled_examples_have_scene_classes(self) -> None:
        """All bundled examples should have at least one Scene subclass."""
        results = check_all_examples()
        for r in results:
            assert len(r.scene_classes) > 0, (
                f"{r.filename} has no Scene subclasses"
            )

    def test_each_result_has_caveats(self) -> None:
        """Each result should include common caveats."""
        results = check_all_examples()
        for r in results:
            assert len(r.caveats) > 0, f"{r.filename} has no caveats"


# ---------------------------------------------------------------------------
# format_check_results — text table formatting
# ---------------------------------------------------------------------------


class TestFormatCheckResults:
    """format_check_results() produces a human-readable table."""

    def test_empty_list(self) -> None:
        assert format_check_results([]) == "No examples found."

    def test_single_passing_result(self) -> None:
        results = [
            ExampleCheckResult(
                path="/demo.py",
                importable=True,
                scene_classes=["DemoScene"],
                scenes_constructed=1,
                lifecycle_ok=True,
            ),
        ]
        text = format_check_results(results)
        assert "demo.py" in text
        assert "OK" in text
        assert "1/1" in text

    def test_single_failing_result(self) -> None:
        results = [
            ExampleCheckResult(
                path="/bad.py",
                importable=False,
                error="ImportError",
            ),
        ]
        text = format_check_results(results)
        assert "bad.py" in text
        assert "FAIL" in text
        assert "0/1" in text

    def test_mixed_results(self) -> None:
        results = [
            ExampleCheckResult(
                path="/good.py",
                importable=True,
                scene_classes=["GoodScene"],
                scenes_constructed=1,
                lifecycle_ok=True,
            ),
            ExampleCheckResult(
                path="/bad.py",
                importable=False,
                error="nope",
            ),
        ]
        text = format_check_results(results)
        assert "1/2" in text

    def test_header_present(self) -> None:
        results = [
            ExampleCheckResult(
                path="/x.py",
                importable=True,
                scene_classes=["X"],
                lifecycle_ok=True,
            ),
        ]
        text = format_check_results(results)
        assert "Example" in text
        assert "Import" in text
        assert "Scenes" in text
        assert "Lifecycle" in text
        assert "Status" in text

    def test_caveats_in_footer(self) -> None:
        results = [
            ExampleCheckResult(
                path="/x.py",
                importable=True,
                lifecycle_ok=True,
            ),
        ]
        text = format_check_results(results)
        assert "Caveats:" in text
        assert "TTY" in text
