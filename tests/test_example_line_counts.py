"""Tests for the example_line_counts module."""

from __future__ import annotations

import os
import pytest

from wyby.example_line_counts import (
    LineCounts,
    count_example_lines,
    count_lines,
    format_line_counts,
)


# ---------------------------------------------------------------------------
# LineCounts dataclass-like behaviour
# ---------------------------------------------------------------------------


class TestLineCounts:
    """LineCounts construction, properties, and equality."""

    def test_attributes(self) -> None:
        lc = LineCounts(path="/a/b.py", total=10, code=7, blank=2, comment=1)
        assert lc.path == "/a/b.py"
        assert lc.total == 10
        assert lc.code == 7
        assert lc.blank == 2
        assert lc.comment == 1

    def test_filename_property(self) -> None:
        lc = LineCounts(path="/a/b/hello.py", total=1, code=1, blank=0, comment=0)
        assert lc.filename == "hello.py"

    def test_repr(self) -> None:
        lc = LineCounts(path="/x/demo.py", total=5, code=3, blank=1, comment=1)
        r = repr(lc)
        assert "demo.py" in r
        assert "total=5" in r
        assert "code=3" in r

    def test_equality(self) -> None:
        a = LineCounts(path="/a.py", total=10, code=7, blank=2, comment=1)
        b = LineCounts(path="/a.py", total=10, code=7, blank=2, comment=1)
        assert a == b

    def test_inequality_different_total(self) -> None:
        a = LineCounts(path="/a.py", total=10, code=7, blank=2, comment=1)
        b = LineCounts(path="/a.py", total=11, code=7, blank=2, comment=2)
        assert a != b

    def test_inequality_different_type(self) -> None:
        lc = LineCounts(path="/a.py", total=1, code=1, blank=0, comment=0)
        assert lc != "not a LineCounts"


# ---------------------------------------------------------------------------
# count_lines — single file counting
# ---------------------------------------------------------------------------


class TestCountLines:
    """count_lines() on individual files."""

    def test_empty_file(self, tmp_path: object) -> None:
        f = tmp_path / "empty.py"  # type: ignore[operator]
        f.write_text("", encoding="utf-8")
        lc = count_lines(f)
        assert lc.total == 0
        assert lc.code == 0
        assert lc.blank == 0
        assert lc.comment == 0

    def test_code_only(self, tmp_path: object) -> None:
        f = tmp_path / "code.py"  # type: ignore[operator]
        f.write_text("x = 1\ny = 2\n", encoding="utf-8")
        lc = count_lines(f)
        assert lc.total == 2
        assert lc.code == 2
        assert lc.blank == 0
        assert lc.comment == 0

    def test_blank_lines(self, tmp_path: object) -> None:
        f = tmp_path / "blanks.py"  # type: ignore[operator]
        f.write_text("x = 1\n\n\ny = 2\n", encoding="utf-8")
        lc = count_lines(f)
        assert lc.total == 4
        assert lc.code == 2
        assert lc.blank == 2
        assert lc.comment == 0

    def test_comment_lines(self, tmp_path: object) -> None:
        f = tmp_path / "comments.py"  # type: ignore[operator]
        f.write_text("# a comment\nx = 1\n  # indented comment\n", encoding="utf-8")
        lc = count_lines(f)
        assert lc.total == 3
        assert lc.code == 1
        assert lc.blank == 0
        assert lc.comment == 2

    def test_inline_comment_counts_as_code(self, tmp_path: object) -> None:
        """Lines with code + trailing comment are classified as code."""
        f = tmp_path / "inline.py"  # type: ignore[operator]
        f.write_text("x = 1  # set x\n", encoding="utf-8")
        lc = count_lines(f)
        assert lc.code == 1
        assert lc.comment == 0

    def test_invariant_total_equals_sum(self, tmp_path: object) -> None:
        f = tmp_path / "mixed.py"  # type: ignore[operator]
        f.write_text("# header\n\nx = 1\ny = 2\n\n# end\n", encoding="utf-8")
        lc = count_lines(f)
        assert lc.total == lc.code + lc.blank + lc.comment

    def test_whitespace_only_line_is_blank(self, tmp_path: object) -> None:
        f = tmp_path / "ws.py"  # type: ignore[operator]
        f.write_text("x = 1\n   \n\t\n", encoding="utf-8")
        lc = count_lines(f)
        assert lc.blank == 2

    def test_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError):
            count_lines("/nonexistent/path/foo.py")

    def test_directory_raises(self, tmp_path: object) -> None:
        with pytest.raises(IsADirectoryError):
            count_lines(tmp_path)  # type: ignore[arg-type]

    def test_non_utf8_raises(self, tmp_path: object) -> None:
        f = tmp_path / "binary.py"  # type: ignore[operator]
        f.write_bytes(b"\x80\x81\x82\xff")
        with pytest.raises(UnicodeDecodeError):
            count_lines(f)

    def test_path_is_resolved(self, tmp_path: object) -> None:
        f = tmp_path / "resolved.py"  # type: ignore[operator]
        f.write_text("a = 1\n", encoding="utf-8")
        lc = count_lines(f)
        assert os.path.isabs(lc.path)

    def test_no_trailing_newline(self, tmp_path: object) -> None:
        """File without trailing newline should count correctly."""
        f = tmp_path / "no_nl.py"  # type: ignore[operator]
        f.write_text("x = 1\ny = 2", encoding="utf-8")
        lc = count_lines(f)
        assert lc.total == 2
        assert lc.code == 2


# ---------------------------------------------------------------------------
# count_example_lines — directory scanning
# ---------------------------------------------------------------------------


class TestCountExampleLines:
    """count_example_lines() discovers and counts *.py files."""

    def test_empty_directory(self, tmp_path: object) -> None:
        result = count_example_lines(tmp_path)  # type: ignore[arg-type]
        assert result == []

    def test_nonexistent_directory(self, tmp_path: object) -> None:
        missing = tmp_path / "nope"  # type: ignore[operator]
        result = count_example_lines(missing)
        assert result == []

    def test_discovers_py_files(self, tmp_path: object) -> None:
        (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")  # type: ignore[operator]
        (tmp_path / "b.py").write_text("y = 2\nz = 3\n", encoding="utf-8")  # type: ignore[operator]
        result = count_example_lines(tmp_path)  # type: ignore[arg-type]
        assert len(result) == 2
        filenames = [r.filename for r in result]
        assert "a.py" in filenames
        assert "b.py" in filenames

    def test_ignores_non_py_files(self, tmp_path: object) -> None:
        (tmp_path / "readme.md").write_text("# hi\n", encoding="utf-8")  # type: ignore[operator]
        (tmp_path / "script.py").write_text("pass\n", encoding="utf-8")  # type: ignore[operator]
        result = count_example_lines(tmp_path)  # type: ignore[arg-type]
        assert len(result) == 1
        assert result[0].filename == "script.py"

    def test_ignores_subdirectories(self, tmp_path: object) -> None:
        sub = tmp_path / "subdir"  # type: ignore[operator]
        sub.mkdir()
        (sub / "hidden.py").write_text("pass\n", encoding="utf-8")
        (tmp_path / "top.py").write_text("pass\n", encoding="utf-8")  # type: ignore[operator]
        result = count_example_lines(tmp_path)  # type: ignore[arg-type]
        assert len(result) == 1
        assert result[0].filename == "top.py"

    def test_sorted_by_filename(self, tmp_path: object) -> None:
        (tmp_path / "z.py").write_text("pass\n", encoding="utf-8")  # type: ignore[operator]
        (tmp_path / "a.py").write_text("pass\n", encoding="utf-8")  # type: ignore[operator]
        (tmp_path / "m.py").write_text("pass\n", encoding="utf-8")  # type: ignore[operator]
        result = count_example_lines(tmp_path)  # type: ignore[arg-type]
        filenames = [r.filename for r in result]
        assert filenames == ["a.py", "m.py", "z.py"]

    def test_skips_non_utf8_files(self, tmp_path: object) -> None:
        (tmp_path / "good.py").write_text("x = 1\n", encoding="utf-8")  # type: ignore[operator]
        (tmp_path / "bad.py").write_bytes(b"\x80\x81\x82\xff")  # type: ignore[operator]
        result = count_example_lines(tmp_path)  # type: ignore[arg-type]
        assert len(result) == 1
        assert result[0].filename == "good.py"

    def test_default_examples_dir(self) -> None:
        """Default directory should find the bundled examples."""
        result = count_example_lines()
        # The repo has at least the hello_world.py example.
        filenames = [r.filename for r in result]
        assert "hello_world.py" in filenames

    def test_counts_are_positive(self) -> None:
        """All bundled examples should have positive total line counts."""
        result = count_example_lines()
        for lc in result:
            assert lc.total > 0, f"{lc.filename} has zero lines"

    def test_invariant_holds_for_all_examples(self) -> None:
        """total == code + blank + comment for every example."""
        result = count_example_lines()
        for lc in result:
            assert lc.total == lc.code + lc.blank + lc.comment, (
                f"{lc.filename}: {lc.total} != {lc.code} + {lc.blank} + {lc.comment}"
            )


# ---------------------------------------------------------------------------
# format_line_counts — text table formatting
# ---------------------------------------------------------------------------


class TestFormatLineCounts:
    """format_line_counts() produces a human-readable table."""

    def test_empty_list(self) -> None:
        assert format_line_counts([]) == "No examples found."

    def test_single_entry(self) -> None:
        counts = [LineCounts(path="/a/demo.py", total=10, code=7, blank=2, comment=1)]
        text = format_line_counts(counts)
        assert "demo.py" in text
        assert "10" in text
        assert "TOTAL" in text

    def test_multiple_entries_have_totals(self) -> None:
        counts = [
            LineCounts(path="/a.py", total=10, code=7, blank=2, comment=1),
            LineCounts(path="/b.py", total=20, code=15, blank=3, comment=2),
        ]
        text = format_line_counts(counts)
        lines = text.split("\n")
        # Should have header, separator, 2 data rows, separator, total row.
        assert len(lines) == 6
        # Total row should sum correctly.
        assert "30" in lines[-1]  # total_total = 10 + 20

    def test_header_present(self) -> None:
        counts = [LineCounts(path="/x.py", total=5, code=3, blank=1, comment=1)]
        text = format_line_counts(counts)
        assert "File" in text
        assert "Total" in text
        assert "Code" in text
        assert "Blank" in text
        assert "Comment" in text
