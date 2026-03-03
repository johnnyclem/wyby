"""Tests for the example_platforms module.

Validates cross-platform compatibility checking of wyby examples,
including platform caveat detection, source-code pattern scanning,
and result formatting.

Caveats:
    - These tests run on the current host OS only.  Platform-specific
      behaviour is tested via synthetic example files, not by actually
      running on multiple OSes.
    - Pattern detection tests use minimal source snippets.  Real
      examples may match more patterns due to richer source code.
"""

from __future__ import annotations

import os
import textwrap

import pytest

from wyby.example_platforms import (
    PLATFORMS,
    ExamplePlatformResult,
    PlatformCaveat,
    check_all_example_platforms,
    check_example_platform,
    format_platform_check_results,
)


# ---------------------------------------------------------------------------
# PlatformCaveat construction and equality
# ---------------------------------------------------------------------------


class TestPlatformCaveat:
    """PlatformCaveat construction, repr, and equality."""

    def test_attributes(self) -> None:
        c = PlatformCaveat(
            platform="linux",
            category="input",
            description="Uses termios raw mode.",
        )
        assert c.platform == "linux"
        assert c.category == "input"
        assert c.description == "Uses termios raw mode."

    def test_repr(self) -> None:
        c = PlatformCaveat(
            platform="windows",
            category="timing",
            description="Sleep granularity.",
        )
        text = repr(c)
        assert "windows" in text
        assert "timing" in text

    def test_equality(self) -> None:
        a = PlatformCaveat(platform="linux", category="input", description="x")
        b = PlatformCaveat(platform="linux", category="input", description="x")
        assert a == b

    def test_inequality_different_platform(self) -> None:
        a = PlatformCaveat(platform="linux", category="input", description="x")
        b = PlatformCaveat(platform="macos", category="input", description="x")
        assert a != b

    def test_inequality_different_description(self) -> None:
        a = PlatformCaveat(platform="linux", category="input", description="x")
        b = PlatformCaveat(platform="linux", category="input", description="y")
        assert a != b

    def test_inequality_different_type(self) -> None:
        c = PlatformCaveat(platform="linux", category="input", description="x")
        assert c != "not a caveat"


# ---------------------------------------------------------------------------
# PLATFORMS constant
# ---------------------------------------------------------------------------


class TestPlatforms:
    """The PLATFORMS tuple."""

    def test_is_tuple(self) -> None:
        assert isinstance(PLATFORMS, tuple)

    def test_contains_linux(self) -> None:
        assert "linux" in PLATFORMS

    def test_contains_macos(self) -> None:
        assert "macos" in PLATFORMS

    def test_contains_windows(self) -> None:
        assert "windows" in PLATFORMS

    def test_length(self) -> None:
        assert len(PLATFORMS) == 3


# ---------------------------------------------------------------------------
# ExamplePlatformResult construction and properties
# ---------------------------------------------------------------------------


class TestExamplePlatformResult:
    """ExamplePlatformResult construction, properties, and equality."""

    def test_attributes(self) -> None:
        r = ExamplePlatformResult(path="/a/demo.py")
        assert r.path == "/a/demo.py"
        assert r.error is None
        assert r.detected_features == []

    def test_filename_property(self) -> None:
        r = ExamplePlatformResult(path="/a/b/game.py")
        assert r.filename == "game.py"

    def test_ok_when_no_error(self) -> None:
        r = ExamplePlatformResult(path="/a.py")
        assert r.ok is True

    def test_not_ok_when_error(self) -> None:
        r = ExamplePlatformResult(path="/a.py", error="file not found")
        assert r.ok is False

    def test_default_platforms(self) -> None:
        """Default platforms dict should have all three platforms."""
        r = ExamplePlatformResult(path="/a.py")
        assert set(r.platforms.keys()) == set(PLATFORMS)

    def test_caveats_for(self) -> None:
        caveat = PlatformCaveat(
            platform="linux", category="input", description="test"
        )
        r = ExamplePlatformResult(
            path="/a.py",
            platforms={"linux": [caveat], "macos": [], "windows": []},
        )
        assert r.caveats_for("linux") == [caveat]
        assert r.caveats_for("macos") == []

    def test_caveats_for_unknown_platform(self) -> None:
        r = ExamplePlatformResult(path="/a.py")
        with pytest.raises(KeyError):
            r.caveats_for("freebsd")

    def test_total_caveats(self) -> None:
        c1 = PlatformCaveat(platform="linux", category="x", description="a")
        c2 = PlatformCaveat(platform="windows", category="y", description="b")
        r = ExamplePlatformResult(
            path="/a.py",
            platforms={"linux": [c1], "macos": [], "windows": [c2]},
        )
        assert r.total_caveats == 2

    def test_repr(self) -> None:
        r = ExamplePlatformResult(path="/demo.py")
        text = repr(r)
        assert "demo.py" in text
        assert "OK" in text

    def test_repr_fail(self) -> None:
        r = ExamplePlatformResult(path="/fail.py", error="oops")
        text = repr(r)
        assert "FAIL" in text

    def test_equality(self) -> None:
        a = ExamplePlatformResult(path="/a.py")
        b = ExamplePlatformResult(path="/a.py")
        assert a == b

    def test_inequality(self) -> None:
        a = ExamplePlatformResult(path="/a.py")
        b = ExamplePlatformResult(path="/b.py")
        assert a != b

    def test_inequality_different_type(self) -> None:
        r = ExamplePlatformResult(path="/a.py")
        assert r != "not a result"


# ---------------------------------------------------------------------------
# check_example_platform — single file analysis
# ---------------------------------------------------------------------------


class TestCheckExamplePlatform:
    """check_example_platform() on individual files."""

    def test_basic_example(self, tmp_path: object) -> None:
        """A simple example should get base caveats for all platforms."""
        f = tmp_path / "simple.py"  # type: ignore[operator]
        f.write_text(
            textwrap.dedent("""\
            from wyby.scene import Scene

            class SimpleScene(Scene):
                def __init__(self):
                    super().__init__()
                def handle_events(self, events): pass
                def update(self, dt): pass
                def render(self): pass
            """),
            encoding="utf-8",
        )
        result = check_example_platform(f)
        assert result.ok is True
        # Should have base caveats for each platform.
        for platform in PLATFORMS:
            assert len(result.caveats_for(platform)) > 0

    def test_file_not_found(self, tmp_path: object) -> None:
        """Missing file should produce an error result."""
        missing = tmp_path / "nonexistent.py"  # type: ignore[operator]
        result = check_example_platform(missing)
        assert result.ok is False
        assert "not found" in result.error

    def test_encoding_error(self, tmp_path: object) -> None:
        """Non-UTF-8 file should produce an error result."""
        f = tmp_path / "binary.py"  # type: ignore[operator]
        f.write_bytes(b"\x80\x81\x82\xff")
        result = check_example_platform(f)
        assert result.ok is False
        assert "encoding" in result.error.lower()

    def test_path_is_resolved(self, tmp_path: object) -> None:
        """Result path should be absolute."""
        f = tmp_path / "resolved.py"  # type: ignore[operator]
        f.write_text("x = 1\n", encoding="utf-8")
        result = check_example_platform(f)
        assert os.path.isabs(result.path)

    def test_timer_pattern_detected(self, tmp_path: object) -> None:
        """Source with move_timer should trigger timing caveats."""
        f = tmp_path / "timer_game.py"  # type: ignore[operator]
        f.write_text(
            textwrap.dedent("""\
            class Game:
                def __init__(self):
                    self.move_timer = 0.0
                    self.move_interval = 0.12

                def update(self, dt):
                    self.move_timer += dt
                    if self.move_timer >= self.move_interval:
                        self.move_timer = 0.0
            """),
            encoding="utf-8",
        )
        result = check_example_platform(f)
        assert result.ok is True
        assert len(result.detected_features) > 0
        # Windows should have an extra timing caveat.
        windows_caveats = result.caveats_for("windows")
        timing_caveats = [c for c in windows_caveats if c.category == "timing"]
        # Base timing caveat + detected timing caveat.
        assert len(timing_caveats) >= 2

    def test_paddle_pattern_detected(self, tmp_path: object) -> None:
        """Source mentioning 'paddle' should trigger key-repeat caveats."""
        f = tmp_path / "paddle_game.py"  # type: ignore[operator]
        f.write_text(
            textwrap.dedent("""\
            class PongScene:
                def __init__(self):
                    self.paddle_y = 10
                def handle_events(self, events):
                    for e in events:
                        if e.key == "up":
                            self.paddle_y -= 1
            """),
            encoding="utf-8",
        )
        result = check_example_platform(f)
        assert result.ok is True
        # All platforms should have key-repeat caveats.
        for platform in PLATFORMS:
            input_caveats = [
                c for c in result.caveats_for(platform) if c.category == "input"
            ]
            assert len(input_caveats) >= 1

    def test_random_pattern_detected(self, tmp_path: object) -> None:
        """Source using random.randint should trigger RNG caveat."""
        f = tmp_path / "random_game.py"  # type: ignore[operator]
        f.write_text(
            textwrap.dedent("""\
            import random
            x = random.randint(0, 10)
            """),
            encoding="utf-8",
        )
        result = check_example_platform(f)
        assert result.ok is True
        assert len(result.detected_features) > 0

    def test_unicode_pattern_detected(self, tmp_path: object) -> None:
        """Source with box-drawing characters should trigger unicode caveats."""
        f = tmp_path / "box_game.py"  # type: ignore[operator]
        f.write_text(
            'border = "┌──────┐"\n',
            encoding="utf-8",
        )
        result = check_example_platform(f)
        assert result.ok is True
        windows_caveats = result.caveats_for("windows")
        unicode_caveats = [c for c in windows_caveats if c.category == "unicode"]
        assert len(unicode_caveats) >= 1

    def test_no_extra_caveats_for_plain_code(self, tmp_path: object) -> None:
        """Source with no platform-sensitive features should only have base caveats."""
        f = tmp_path / "plain.py"  # type: ignore[operator]
        f.write_text("x = 1\ny = 2\n", encoding="utf-8")
        result = check_example_platform(f)
        assert result.ok is True
        assert result.detected_features == []


# ---------------------------------------------------------------------------
# check_all_example_platforms — directory scanning
# ---------------------------------------------------------------------------


class TestCheckAllExamplePlatforms:
    """check_all_example_platforms() discovers and analyses *.py files."""

    def test_empty_directory(self, tmp_path: object) -> None:
        result = check_all_example_platforms(tmp_path)  # type: ignore[arg-type]
        assert result == []

    def test_nonexistent_directory(self, tmp_path: object) -> None:
        missing = tmp_path / "nope"  # type: ignore[operator]
        result = check_all_example_platforms(missing)
        assert result == []

    def test_discovers_py_files(self, tmp_path: object) -> None:
        for name in ("a.py", "b.py"):
            (tmp_path / name).write_text("x = 1\n", encoding="utf-8")  # type: ignore[operator]
        result = check_all_example_platforms(tmp_path)  # type: ignore[arg-type]
        assert len(result) == 2

    def test_ignores_non_py_files(self, tmp_path: object) -> None:
        (tmp_path / "readme.md").write_text("# hi\n", encoding="utf-8")  # type: ignore[operator]
        (tmp_path / "script.py").write_text("x = 1\n", encoding="utf-8")  # type: ignore[operator]
        result = check_all_example_platforms(tmp_path)  # type: ignore[arg-type]
        assert len(result) == 1
        assert result[0].filename == "script.py"

    def test_ignores_subdirectories(self, tmp_path: object) -> None:
        sub = tmp_path / "subdir"  # type: ignore[operator]
        sub.mkdir()
        (sub / "hidden.py").write_text("pass\n", encoding="utf-8")
        (tmp_path / "top.py").write_text("pass\n", encoding="utf-8")  # type: ignore[operator]
        result = check_all_example_platforms(tmp_path)  # type: ignore[arg-type]
        assert len(result) == 1
        assert result[0].filename == "top.py"

    def test_sorted_by_filename(self, tmp_path: object) -> None:
        for name in ("z.py", "a.py", "m.py"):
            (tmp_path / name).write_text("x = 1\n", encoding="utf-8")  # type: ignore[operator]
        result = check_all_example_platforms(tmp_path)  # type: ignore[arg-type]
        filenames = [r.filename for r in result]
        assert filenames == ["a.py", "m.py", "z.py"]

    def test_default_examples_dir(self) -> None:
        """Default directory should find the bundled examples."""
        result = check_all_example_platforms()
        filenames = [r.filename for r in result]
        assert "hello_world.py" in filenames

    def test_bundled_examples_all_ok(self) -> None:
        """All bundled examples should analyse without error."""
        results = check_all_example_platforms()
        for r in results:
            assert r.ok, f"{r.filename} failed: {r.error}"

    def test_bundled_examples_have_caveats(self) -> None:
        """All bundled examples should have caveats for every platform."""
        results = check_all_example_platforms()
        for r in results:
            for platform in PLATFORMS:
                assert len(r.caveats_for(platform)) > 0, (
                    f"{r.filename} has no caveats for {platform}"
                )

    def test_bundled_examples_windows_has_most_caveats(self) -> None:
        """Windows typically has the most caveats due to platform differences.

        Caveat: this is a heuristic assertion — Windows has more base
        caveats (input, timing, signals, terminal) than Linux or macOS.
        """
        results = check_all_example_platforms()
        for r in results:
            windows_count = len(r.caveats_for("windows"))
            linux_count = len(r.caveats_for("linux"))
            assert windows_count >= linux_count, (
                f"{r.filename}: expected Windows >= Linux caveats, "
                f"got {windows_count} vs {linux_count}"
            )


# ---------------------------------------------------------------------------
# format_platform_check_results — text formatting
# ---------------------------------------------------------------------------


class TestFormatPlatformCheckResults:
    """format_platform_check_results() produces a human-readable report."""

    def test_empty_list(self) -> None:
        assert format_platform_check_results([]) == "No examples found."

    def test_single_result(self) -> None:
        results = [ExamplePlatformResult(path="/demo.py")]
        text = format_platform_check_results(results)
        assert "demo.py" in text
        assert "OK" in text

    def test_header_present(self) -> None:
        results = [ExamplePlatformResult(path="/x.py")]
        text = format_platform_check_results(results)
        assert "Example" in text
        assert "Linux" in text
        assert "macOS" in text
        assert "Windows" in text
        assert "Status" in text

    def test_error_result_shown(self) -> None:
        results = [
            ExamplePlatformResult(path="/bad.py", error="file not found"),
        ]
        text = format_platform_check_results(results)
        assert "FAIL" in text
        assert "ERROR" in text

    def test_caveats_section_present(self) -> None:
        results = [ExamplePlatformResult(path="/x.py")]
        text = format_platform_check_results(results)
        assert "Platform caveats by example:" in text

    def test_cross_platform_notes_present(self) -> None:
        results = [ExamplePlatformResult(path="/x.py")]
        text = format_platform_check_results(results)
        assert "Cross-platform notes:" in text
        assert "TTY" in text
        assert "Windows Terminal" in text

    def test_multiple_results(self) -> None:
        results = [
            ExamplePlatformResult(path="/a.py"),
            ExamplePlatformResult(path="/b.py"),
        ]
        text = format_platform_check_results(results)
        assert "a.py" in text
        assert "b.py" in text

    def test_platform_labels_in_caveat_details(self) -> None:
        """Caveat details should show platform labels."""
        caveat = PlatformCaveat(
            platform="linux", category="input", description="test caveat"
        )
        results = [
            ExamplePlatformResult(
                path="/x.py",
                platforms={
                    "linux": [caveat],
                    "macos": [],
                    "windows": [],
                },
            ),
        ]
        text = format_platform_check_results(results)
        assert "[linux]" in text
        assert "[input]" in text
        assert "test caveat" in text

    def test_bundled_examples_format(self) -> None:
        """Formatting all bundled example results should not raise."""
        results = check_all_example_platforms()
        text = format_platform_check_results(results)
        assert len(text) > 0
        assert "hello_world.py" in text


# ---------------------------------------------------------------------------
# Package-level exports
# ---------------------------------------------------------------------------


class TestExamplePlatformsExports:
    """New types should be importable from the top-level package."""

    def test_platform_caveat_importable(self) -> None:
        from wyby import PlatformCaveat as PC

        assert PC is PlatformCaveat

    def test_example_platform_result_importable(self) -> None:
        from wyby import ExamplePlatformResult as EPR

        assert EPR is ExamplePlatformResult

    def test_platforms_importable(self) -> None:
        from wyby import EXAMPLE_PLATFORMS

        assert EXAMPLE_PLATFORMS is PLATFORMS

    def test_check_example_platform_importable(self) -> None:
        from wyby import check_example_platform as cep

        assert cep is check_example_platform

    def test_check_all_example_platforms_importable(self) -> None:
        from wyby import check_all_example_platforms as caep

        assert caep is check_all_example_platforms

    def test_format_platform_check_results_importable(self) -> None:
        from wyby import format_platform_check_results as fpcr

        assert fpcr is format_platform_check_results

    def test_in_all(self) -> None:
        import wyby

        assert "PlatformCaveat" in wyby.__all__
        assert "ExamplePlatformResult" in wyby.__all__
        assert "EXAMPLE_PLATFORMS" in wyby.__all__
        assert "check_example_platform" in wyby.__all__
        assert "check_all_example_platforms" in wyby.__all__
        assert "format_platform_check_results" in wyby.__all__
