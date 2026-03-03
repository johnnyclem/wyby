"""Tests for wyby.grid.DoubleBuffer — simulated double-buffering."""

from __future__ import annotations

import pytest

from wyby.grid import (
    Cell,
    CellBuffer,
    DoubleBuffer,
    _DEFAULT_CHAR,
    _MAX_DIMENSION,
    _MIN_DIMENSION,
)


# ---------------------------------------------------------------------------
# DoubleBuffer — Initialisation
# ---------------------------------------------------------------------------


class TestDoubleBufferInit:
    """DoubleBuffer initialisation and dimension properties."""

    def test_width_and_height(self) -> None:
        db = DoubleBuffer(80, 24)
        assert db.width == 80
        assert db.height == 24

    def test_small_buffer(self) -> None:
        db = DoubleBuffer(1, 1)
        assert db.width == 1
        assert db.height == 1

    def test_dimensions_clamped_to_min(self) -> None:
        db = DoubleBuffer(0, -5)
        assert db.width == _MIN_DIMENSION
        assert db.height == _MIN_DIMENSION

    def test_dimensions_clamped_to_max(self) -> None:
        db = DoubleBuffer(9999, 9999)
        assert db.width == _MAX_DIMENSION
        assert db.height == _MAX_DIMENSION

    def test_front_and_back_are_cellbuffers(self) -> None:
        db = DoubleBuffer(10, 5)
        assert isinstance(db.front, CellBuffer)
        assert isinstance(db.back, CellBuffer)

    def test_front_and_back_are_different_objects(self) -> None:
        db = DoubleBuffer(10, 5)
        assert db.front is not db.back

    def test_front_and_back_have_same_dimensions(self) -> None:
        db = DoubleBuffer(10, 5)
        assert db.front.width == db.back.width == 10
        assert db.front.height == db.back.height == 5

    def test_both_buffers_start_blank(self) -> None:
        db = DoubleBuffer(3, 2)
        for buf in (db.front, db.back):
            for y in range(2):
                for x in range(3):
                    cell = buf.get(x, y)
                    assert cell is not None
                    assert cell.char == _DEFAULT_CHAR

    def test_swap_count_starts_at_zero(self) -> None:
        db = DoubleBuffer(5, 5)
        assert db.swap_count == 0

    def test_rejects_non_int_width(self) -> None:
        with pytest.raises(TypeError, match="width must be an int"):
            DoubleBuffer("80", 24)  # type: ignore[arg-type]

    def test_rejects_non_int_height(self) -> None:
        with pytest.raises(TypeError, match="height must be an int"):
            DoubleBuffer(80, 24.0)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# DoubleBuffer.swap
# ---------------------------------------------------------------------------


class TestDoubleBufferSwap:
    """Tests for the swap() operation."""

    def test_swap_exchanges_buffers(self) -> None:
        """After swap, front should contain what was drawn on back."""
        db = DoubleBuffer(10, 1)
        db.back.put_text(0, 0, "Hello")
        db.swap()
        cell = db.front.get(0, 0)
        assert cell is not None
        assert cell.char == "H"

    def test_swap_clears_new_back(self) -> None:
        """After swap, the new back buffer should be blank."""
        db = DoubleBuffer(10, 1)
        db.back.put_text(0, 0, "Hello")
        db.swap()
        # The new back buffer (was the old front) should be cleared.
        for x in range(10):
            cell = db.back.get(x, 0)
            assert cell is not None
            assert cell.char == _DEFAULT_CHAR

    def test_front_preserves_drawn_content(self) -> None:
        """Front should retain all content drawn on the old back buffer."""
        db = DoubleBuffer(10, 1)
        db.back.put(3, 0, Cell(char="@", fg="green", bold=True))
        db.swap()
        cell = db.front.get(3, 0)
        assert cell is not None
        assert cell.char == "@"
        assert cell.fg == "green"
        assert cell.bold is True

    def test_swap_count_increments(self) -> None:
        db = DoubleBuffer(5, 5)
        assert db.swap_count == 0
        db.swap()
        assert db.swap_count == 1
        db.swap()
        assert db.swap_count == 2

    def test_double_swap_returns_to_original(self) -> None:
        """Two swaps should cycle the buffers back to the originals."""
        db = DoubleBuffer(10, 1)
        original_front = db.front
        original_back = db.back
        db.swap()
        db.swap()
        # After two swaps, the original front is front again and the
        # original back is back again (though both have been cleared).
        assert db.front is original_front
        assert db.back is original_back

    def test_typical_frame_cycle(self) -> None:
        """Simulate a typical game loop: draw to back, swap, read front."""
        db = DoubleBuffer(20, 5)

        # Frame 1: draw a player on the back buffer.
        db.back.put(5, 2, Cell(char="@", fg="green"))
        db.swap()

        # Front now has the player; back is clear for frame 2.
        assert db.front.get(5, 2) is not None
        assert db.front.get(5, 2).char == "@"  # type: ignore[union-attr]
        assert db.back.get(5, 2) is not None
        assert db.back.get(5, 2).char == _DEFAULT_CHAR  # type: ignore[union-attr]

        # Frame 2: draw player at new position.
        db.back.put(6, 2, Cell(char="@", fg="green"))
        db.swap()

        # Front now shows the new position; old position is gone.
        assert db.front.get(6, 2) is not None
        assert db.front.get(6, 2).char == "@"  # type: ignore[union-attr]
        assert db.front.get(5, 2) is not None
        assert db.front.get(5, 2).char == _DEFAULT_CHAR  # type: ignore[union-attr]

    def test_swap_with_styled_content(self) -> None:
        """Styled cells should survive the swap intact."""
        db = DoubleBuffer(5, 1)
        db.back.put(0, 0, Cell(char="X", fg="red", bg="blue", bold=True, dim=True))
        db.swap()
        cell = db.front.get(0, 0)
        assert cell is not None
        assert cell.char == "X"
        assert cell.fg == "red"
        assert cell.bg == "blue"
        assert cell.bold is True
        assert cell.dim is True


# ---------------------------------------------------------------------------
# DoubleBuffer.clear
# ---------------------------------------------------------------------------


class TestDoubleBufferClear:
    """Tests for clear() — resets both buffers."""

    def test_clear_resets_both_buffers(self) -> None:
        db = DoubleBuffer(5, 5)
        db.back.put(0, 0, Cell(char="@"))
        db.swap()
        db.back.put(1, 1, Cell(char="#"))
        # Both buffers now have content.
        db.clear()
        for buf in (db.front, db.back):
            for y in range(5):
                for x in range(5):
                    cell = buf.get(x, y)
                    assert cell is not None
                    assert cell.char == _DEFAULT_CHAR

    def test_clear_preserves_dimensions(self) -> None:
        db = DoubleBuffer(10, 8)
        db.clear()
        assert db.width == 10
        assert db.height == 8
        assert db.front.width == 10
        assert db.back.height == 8

    def test_clear_does_not_reset_swap_count(self) -> None:
        db = DoubleBuffer(5, 5)
        db.swap()
        db.swap()
        db.clear()
        assert db.swap_count == 2


# ---------------------------------------------------------------------------
# DoubleBuffer — repr
# ---------------------------------------------------------------------------


class TestDoubleBufferRepr:
    """Tests for DoubleBuffer.__repr__."""

    def test_repr_contains_class_name(self) -> None:
        db = DoubleBuffer(10, 5)
        assert "DoubleBuffer" in repr(db)

    def test_repr_contains_dimensions(self) -> None:
        db = DoubleBuffer(10, 5)
        r = repr(db)
        assert "width=10" in r
        assert "height=5" in r

    def test_repr_contains_swap_count(self) -> None:
        db = DoubleBuffer(10, 5)
        assert "swap_count=0" in repr(db)
        db.swap()
        assert "swap_count=1" in repr(db)


# ---------------------------------------------------------------------------
# DoubleBuffer — Rich renderable integration
# ---------------------------------------------------------------------------


class TestDoubleBufferRichIntegration:
    """Front buffer should work as a Rich renderable."""

    def test_front_is_rich_renderable(self) -> None:
        """The front buffer should be accepted by Rich Console."""
        import io
        from rich.console import Console

        db = DoubleBuffer(10, 2)
        db.back.put_text(0, 0, "Hello")
        db.swap()

        sio = io.StringIO()
        console = Console(
            file=sio, force_terminal=True, color_system=None, width=10,
        )
        # Should not raise — CellBuffer is a valid Rich renderable.
        console.print(db.front, end="")
        assert "Hello" in sio.getvalue()

    def test_front_works_with_renderer(self) -> None:
        """The front buffer should be accepted by Renderer.present()."""
        import io
        from rich.console import Console

        from wyby.renderer import Renderer

        sio = io.StringIO()
        console = Console(file=sio, force_terminal=True, width=20)
        renderer = Renderer(console=console)
        db = DoubleBuffer(10, 2)
        db.back.put_text(0, 0, "Frame1")
        db.swap()
        with renderer:
            renderer.present(db.front)
            assert renderer.frame_count == 1


# ---------------------------------------------------------------------------
# DoubleBuffer — package export
# ---------------------------------------------------------------------------


class TestDoubleBufferExport:
    """Tests for DoubleBuffer availability in the public API."""

    def test_importable_from_wyby(self) -> None:
        from wyby import DoubleBuffer as DB  # noqa: N811

        assert DB is DoubleBuffer

    def test_in_all(self) -> None:
        import wyby

        assert "DoubleBuffer" in wyby.__all__
