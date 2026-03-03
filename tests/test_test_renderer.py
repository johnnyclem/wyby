"""Tests for wyby.test_renderer — headless renderer for testing."""

from __future__ import annotations

import pytest

from wyby.grid import Cell, CellBuffer
from wyby.test_renderer import TestRendererBuffer


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestTestRendererBufferInit:
    """Tests for TestRendererBuffer construction."""

    def test_default_dimensions(self) -> None:
        renderer = TestRendererBuffer()
        assert renderer.width == 80
        assert renderer.height == 24

    def test_custom_dimensions(self) -> None:
        renderer = TestRendererBuffer(width=40, height=20)
        assert renderer.width == 40
        assert renderer.height == 20

    def test_not_started_initially(self) -> None:
        renderer = TestRendererBuffer()
        assert renderer.is_started is False

    def test_frame_count_zero_initially(self) -> None:
        renderer = TestRendererBuffer()
        assert renderer.frame_count == 0

    def test_last_frame_none_initially(self) -> None:
        renderer = TestRendererBuffer()
        assert renderer.last_frame is None

    def test_frame_history_empty_initially(self) -> None:
        renderer = TestRendererBuffer()
        assert renderer.frame_history == []

    def test_no_overlays_initially(self) -> None:
        renderer = TestRendererBuffer()
        assert renderer.overlays == []
        assert renderer.overlay_count == 0

    def test_rejects_zero_width(self) -> None:
        with pytest.raises(ValueError, match="width"):
            TestRendererBuffer(width=0)

    def test_rejects_negative_width(self) -> None:
        with pytest.raises(ValueError, match="width"):
            TestRendererBuffer(width=-1)

    def test_rejects_zero_height(self) -> None:
        with pytest.raises(ValueError, match="height"):
            TestRendererBuffer(height=0)

    def test_rejects_negative_height(self) -> None:
        with pytest.raises(ValueError, match="height"):
            TestRendererBuffer(height=-1)

    def test_rejects_non_int_width(self) -> None:
        with pytest.raises(ValueError, match="width"):
            TestRendererBuffer(width=3.5)  # type: ignore[arg-type]

    def test_rejects_non_int_height(self) -> None:
        with pytest.raises(ValueError, match="height"):
            TestRendererBuffer(height="10")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


class TestTestRendererBufferLifecycle:
    """Tests for start/stop lifecycle."""

    def test_start_sets_is_started(self) -> None:
        renderer = TestRendererBuffer()
        renderer.start()
        assert renderer.is_started is True
        renderer.stop()

    def test_stop_clears_is_started(self) -> None:
        renderer = TestRendererBuffer()
        renderer.start()
        renderer.stop()
        assert renderer.is_started is False

    def test_double_start_is_noop(self) -> None:
        renderer = TestRendererBuffer()
        renderer.start()
        renderer.present(CellBuffer(10, 5))
        assert renderer.frame_count == 1
        renderer.start()  # Should be a no-op
        assert renderer.is_started is True
        # Frame count should NOT be reset by a redundant start().
        assert renderer.frame_count == 1
        renderer.stop()

    def test_stop_without_start_is_noop(self) -> None:
        renderer = TestRendererBuffer()
        renderer.stop()  # Should not raise
        assert renderer.is_started is False

    def test_double_stop_is_noop(self) -> None:
        renderer = TestRendererBuffer()
        renderer.start()
        renderer.stop()
        renderer.stop()  # Should not raise
        assert renderer.is_started is False

    def test_restart_after_stop(self) -> None:
        renderer = TestRendererBuffer()
        renderer.start()
        renderer.stop()
        renderer.start()
        assert renderer.is_started is True
        renderer.stop()

    def test_start_resets_frame_count(self) -> None:
        renderer = TestRendererBuffer()
        renderer.start()
        renderer.present(CellBuffer(5, 3))
        renderer.present(CellBuffer(5, 3))
        assert renderer.frame_count == 2
        renderer.stop()
        renderer.start()
        assert renderer.frame_count == 0
        renderer.stop()

    def test_start_resets_frame_history(self) -> None:
        renderer = TestRendererBuffer()
        renderer.start()
        renderer.present(CellBuffer(5, 3))
        assert len(renderer.frame_history) == 1
        renderer.stop()
        renderer.start()
        assert len(renderer.frame_history) == 0
        renderer.stop()

    def test_start_resets_last_frame(self) -> None:
        renderer = TestRendererBuffer()
        renderer.start()
        renderer.present(CellBuffer(5, 3))
        assert renderer.last_frame is not None
        renderer.stop()
        renderer.start()
        assert renderer.last_frame is None
        renderer.stop()

    def test_frame_history_survives_stop(self) -> None:
        """Frame history remains accessible after stop for assertions."""
        renderer = TestRendererBuffer()
        renderer.start()
        renderer.present(CellBuffer(5, 3))
        renderer.stop()
        assert len(renderer.frame_history) == 1
        assert renderer.last_frame is not None


# ---------------------------------------------------------------------------
# Context manager
# ---------------------------------------------------------------------------


class TestTestRendererBufferContextManager:
    """Tests for context manager protocol."""

    def test_starts_on_enter(self) -> None:
        renderer = TestRendererBuffer()
        with renderer:
            assert renderer.is_started is True

    def test_stops_on_exit(self) -> None:
        renderer = TestRendererBuffer()
        with renderer:
            pass
        assert renderer.is_started is False

    def test_stops_on_exception(self) -> None:
        renderer = TestRendererBuffer()
        with pytest.raises(ValueError, match="boom"):
            with renderer:
                assert renderer.is_started is True
                raise ValueError("boom")
        assert renderer.is_started is False

    def test_returns_self(self) -> None:
        renderer = TestRendererBuffer()
        with renderer as ctx:
            assert ctx is renderer


# ---------------------------------------------------------------------------
# present() — CellBuffer frames
# ---------------------------------------------------------------------------


class TestTestRendererBufferPresent:
    """Tests for present() with CellBuffer renderables."""

    def test_present_increments_frame_count(self) -> None:
        renderer = TestRendererBuffer()
        with renderer:
            assert renderer.frame_count == 0
            renderer.present(CellBuffer(5, 3))
            assert renderer.frame_count == 1
            renderer.present(CellBuffer(5, 3))
            assert renderer.frame_count == 2

    def test_present_captures_last_frame(self) -> None:
        renderer = TestRendererBuffer()
        with renderer:
            buf = CellBuffer(10, 5)
            buf.put_text(0, 0, "Hello")
            renderer.present(buf)
            assert renderer.last_frame is not None
            assert renderer.last_frame.width == 10
            assert renderer.last_frame.height == 5

    def test_present_captures_cell_content(self) -> None:
        renderer = TestRendererBuffer()
        with renderer:
            buf = CellBuffer(10, 5)
            buf.put_text(0, 0, "Hello")
            renderer.present(buf)
            cell = renderer.last_frame.get(0, 0)
            assert cell is not None
            assert cell.char == "H"

    def test_present_captures_cell_style(self) -> None:
        renderer = TestRendererBuffer()
        with renderer:
            buf = CellBuffer(10, 5)
            buf.put(2, 1, Cell(char="@", fg="green", bg="black", bold=True))
            renderer.present(buf)
            cell = renderer.last_frame.get(2, 1)
            assert cell is not None
            assert cell.char == "@"
            assert cell.fg == "green"
            assert cell.bg == "black"
            assert cell.bold is True

    def test_present_deep_copies_buffer(self) -> None:
        """Mutating the original buffer after present() should not affect the snapshot."""
        renderer = TestRendererBuffer()
        with renderer:
            buf = CellBuffer(10, 5)
            buf.put_text(0, 0, "Before")
            renderer.present(buf)

            # Mutate the original buffer.
            buf.put_text(0, 0, "After!")

            # Snapshot should still have the original content.
            cell = renderer.last_frame.get(0, 0)
            assert cell.char == "B"

    def test_frame_history_accumulates(self) -> None:
        renderer = TestRendererBuffer()
        with renderer:
            for i in range(5):
                buf = CellBuffer(10, 1)
                buf.put_text(0, 0, str(i))
                renderer.present(buf)
            assert len(renderer.frame_history) == 5
            # Each frame should be independent.
            assert renderer.frame_history[0].get(0, 0).char == "0"
            assert renderer.frame_history[4].get(0, 0).char == "4"

    def test_present_when_not_started_is_noop(self) -> None:
        renderer = TestRendererBuffer()
        renderer.present(CellBuffer(5, 3))
        assert renderer.frame_count == 0
        assert renderer.last_frame is None

    def test_present_after_stop_is_noop(self) -> None:
        renderer = TestRendererBuffer()
        renderer.start()
        renderer.stop()
        renderer.present(CellBuffer(5, 3))
        assert renderer.frame_count == 0

    def test_present_does_not_increment_when_stopped(self) -> None:
        renderer = TestRendererBuffer()
        renderer.present(CellBuffer(5, 3))
        renderer.present(CellBuffer(5, 3))
        assert renderer.frame_count == 0

    def test_present_various_buffer_sizes(self) -> None:
        """TestRendererBuffer accepts any size CellBuffer."""
        renderer = TestRendererBuffer(width=80, height=24)
        with renderer:
            # Smaller than default.
            renderer.present(CellBuffer(5, 3))
            assert renderer.last_frame.width == 5
            assert renderer.last_frame.height == 3

            # Larger than default.
            renderer.present(CellBuffer(200, 60))
            assert renderer.last_frame.width == 200
            assert renderer.last_frame.height == 60


# ---------------------------------------------------------------------------
# present() — non-CellBuffer renderables
# ---------------------------------------------------------------------------


class TestTestRendererBufferNonBuffer:
    """Tests for present() with non-CellBuffer renderables."""

    def test_string_renderable_increments_frame_count(self) -> None:
        renderer = TestRendererBuffer()
        with renderer:
            renderer.present("hello")
            assert renderer.frame_count == 1

    def test_string_renderable_does_not_set_last_frame(self) -> None:
        renderer = TestRendererBuffer()
        with renderer:
            renderer.present("hello")
            # last_frame is None because strings don't produce cell snapshots.
            assert renderer.last_frame is None

    def test_string_renderable_stored_in_non_buffer_frames(self) -> None:
        renderer = TestRendererBuffer()
        with renderer:
            renderer.present("hello")
            assert len(renderer.non_buffer_frames) == 1
            assert renderer.non_buffer_frames[0] == "hello"

    def test_mixed_renderables(self) -> None:
        """Mixing CellBuffer and string frames works correctly."""
        renderer = TestRendererBuffer()
        with renderer:
            buf = CellBuffer(10, 1)
            buf.put_text(0, 0, "Frame")
            renderer.present(buf)
            renderer.present("string frame")
            renderer.present(buf)

            assert renderer.frame_count == 3
            assert len(renderer.frame_history) == 2  # Only CellBuffers
            assert len(renderer.non_buffer_frames) == 1


# ---------------------------------------------------------------------------
# clear_buffer
# ---------------------------------------------------------------------------


class TestTestRendererBufferClearBuffer:
    """Tests for clear_buffer()."""

    def test_clear_buffer_when_started(self) -> None:
        renderer = TestRendererBuffer()
        with renderer:
            renderer.clear_buffer()  # Should not raise

    def test_clear_buffer_does_not_affect_frame_count(self) -> None:
        renderer = TestRendererBuffer()
        with renderer:
            renderer.present(CellBuffer(5, 3))
            assert renderer.frame_count == 1
            renderer.clear_buffer()
            assert renderer.frame_count == 1

    def test_clear_buffer_when_not_started_is_noop(self) -> None:
        renderer = TestRendererBuffer()
        renderer.clear_buffer()  # Should not raise

    def test_clear_buffer_does_not_affect_history(self) -> None:
        renderer = TestRendererBuffer()
        with renderer:
            renderer.present(CellBuffer(5, 3))
            renderer.clear_buffer()
            assert len(renderer.frame_history) == 1
            assert renderer.last_frame is not None


# ---------------------------------------------------------------------------
# clear_history
# ---------------------------------------------------------------------------


class TestTestRendererBufferClearHistory:
    """Tests for clear_history()."""

    def test_clear_history_resets_frame_history(self) -> None:
        renderer = TestRendererBuffer()
        with renderer:
            renderer.present(CellBuffer(5, 3))
            renderer.present(CellBuffer(5, 3))
            assert len(renderer.frame_history) == 2
            renderer.clear_history()
            assert len(renderer.frame_history) == 0

    def test_clear_history_resets_last_frame(self) -> None:
        renderer = TestRendererBuffer()
        with renderer:
            renderer.present(CellBuffer(5, 3))
            assert renderer.last_frame is not None
            renderer.clear_history()
            assert renderer.last_frame is None

    def test_clear_history_resets_non_buffer_frames(self) -> None:
        renderer = TestRendererBuffer()
        with renderer:
            renderer.present("hello")
            assert len(renderer.non_buffer_frames) == 1
            renderer.clear_history()
            assert len(renderer.non_buffer_frames) == 0

    def test_clear_history_does_not_affect_frame_count(self) -> None:
        renderer = TestRendererBuffer()
        with renderer:
            renderer.present(CellBuffer(5, 3))
            renderer.present(CellBuffer(5, 3))
            assert renderer.frame_count == 2
            renderer.clear_history()
            assert renderer.frame_count == 2


# ---------------------------------------------------------------------------
# Convenience: get_cell / get_text
# ---------------------------------------------------------------------------


class TestTestRendererBufferConvenience:
    """Tests for get_cell() and get_text() convenience methods."""

    def test_get_cell_returns_cell(self) -> None:
        renderer = TestRendererBuffer()
        with renderer:
            buf = CellBuffer(10, 5)
            buf.put(3, 2, Cell(char="X", fg="red"))
            renderer.present(buf)
            cell = renderer.get_cell(3, 2)
            assert cell is not None
            assert cell.char == "X"
            assert cell.fg == "red"

    def test_get_cell_returns_none_without_frame(self) -> None:
        renderer = TestRendererBuffer()
        assert renderer.get_cell(0, 0) is None

    def test_get_cell_returns_none_out_of_bounds(self) -> None:
        renderer = TestRendererBuffer()
        with renderer:
            renderer.present(CellBuffer(5, 3))
            assert renderer.get_cell(100, 100) is None

    def test_get_text_extracts_string(self) -> None:
        renderer = TestRendererBuffer()
        with renderer:
            buf = CellBuffer(20, 5)
            buf.put_text(0, 0, "Score: 42")
            renderer.present(buf)
            text = renderer.get_text(0, 0, 9)
            assert text == "Score: 42"

    def test_get_text_returns_empty_without_frame(self) -> None:
        renderer = TestRendererBuffer()
        assert renderer.get_text(0, 0, 5) == ""

    def test_get_text_partial_read(self) -> None:
        renderer = TestRendererBuffer()
        with renderer:
            buf = CellBuffer(20, 5)
            buf.put_text(0, 0, "Hello World")
            renderer.present(buf)
            text = renderer.get_text(6, 0, 5)
            assert text == "World"

    def test_get_text_stops_at_buffer_edge(self) -> None:
        renderer = TestRendererBuffer()
        with renderer:
            buf = CellBuffer(5, 1)
            buf.put_text(0, 0, "ABCDE")
            renderer.present(buf)
            # Requesting more chars than available — should stop at edge.
            text = renderer.get_text(3, 0, 10)
            assert text == "DE"


# ---------------------------------------------------------------------------
# Overlay support
# ---------------------------------------------------------------------------


class TestTestRendererBufferOverlays:
    """Tests for overlay management and compositing."""

    @staticmethod
    def _make_label_widget(
        text: str, x: int, y: int, z_index: int = 0
    ) -> object:
        """Create a minimal Widget subclass for testing overlays."""
        from wyby.widget import Widget

        class _TestLabel(Widget):
            def __init__(
                self, label: str, wx: int, wy: int, wz: int
            ) -> None:
                super().__init__(
                    x=wx, y=wy, width=len(label), height=1, z_index=wz
                )
                self._label = label

            def draw(self, buffer: CellBuffer) -> None:
                if not self.visible:
                    return
                buffer.put_text(self.x, self.y, self._label)

        return _TestLabel(text, x, y, z_index)

    def test_add_overlay(self) -> None:
        renderer = TestRendererBuffer()
        widget = self._make_label_widget("HP", 0, 0)
        renderer.add_overlay(widget)
        assert renderer.overlay_count == 1

    def test_add_overlay_duplicate_is_noop(self) -> None:
        renderer = TestRendererBuffer()
        widget = self._make_label_widget("HP", 0, 0)
        renderer.add_overlay(widget)
        renderer.add_overlay(widget)
        assert renderer.overlay_count == 1

    def test_add_overlay_rejects_non_widget(self) -> None:
        renderer = TestRendererBuffer()
        with pytest.raises(TypeError, match="Widget"):
            renderer.add_overlay("not a widget")  # type: ignore[arg-type]

    def test_remove_overlay(self) -> None:
        renderer = TestRendererBuffer()
        widget = self._make_label_widget("HP", 0, 0)
        renderer.add_overlay(widget)
        renderer.remove_overlay(widget)
        assert renderer.overlay_count == 0

    def test_remove_overlay_not_registered(self) -> None:
        renderer = TestRendererBuffer()
        widget = self._make_label_widget("HP", 0, 0)
        with pytest.raises(ValueError, match="not a registered overlay"):
            renderer.remove_overlay(widget)

    def test_clear_overlays(self) -> None:
        renderer = TestRendererBuffer()
        renderer.add_overlay(self._make_label_widget("A", 0, 0))
        renderer.add_overlay(self._make_label_widget("B", 5, 0))
        renderer.clear_overlays()
        assert renderer.overlay_count == 0

    def test_overlay_drawn_into_buffer(self) -> None:
        """Overlays should be composited into the CellBuffer before capture."""
        renderer = TestRendererBuffer()
        widget = self._make_label_widget("HUD", 0, 0)
        renderer.add_overlay(widget)
        with renderer:
            buf = CellBuffer(20, 5)
            renderer.present(buf)
            # The captured frame should contain the overlay text.
            text = renderer.get_text(0, 0, 3)
            assert text == "HUD"

    def test_overlay_z_order(self) -> None:
        """Higher z_index overlays draw on top of lower ones."""
        renderer = TestRendererBuffer()
        # Both overlays write to the same position.
        bg_widget = self._make_label_widget("B", 0, 0, z_index=0)
        fg_widget = self._make_label_widget("F", 0, 0, z_index=10)
        renderer.add_overlay(bg_widget)
        renderer.add_overlay(fg_widget)
        with renderer:
            buf = CellBuffer(10, 1)
            renderer.present(buf)
            cell = renderer.get_cell(0, 0)
            assert cell.char == "F"  # Higher z_index wins

    def test_hidden_overlay_not_drawn(self) -> None:
        """Overlays with visible=False should not be drawn."""
        renderer = TestRendererBuffer()
        widget = self._make_label_widget("Hidden", 0, 0)
        widget.visible = False
        renderer.add_overlay(widget)
        with renderer:
            buf = CellBuffer(10, 1)
            renderer.present(buf)
            cell = renderer.get_cell(0, 0)
            assert cell.char == " "  # Default blank cell

    def test_overlay_mutates_caller_buffer(self) -> None:
        """Overlays should mutate the caller's buffer (matches production)."""
        renderer = TestRendererBuffer()
        widget = self._make_label_widget("OVR", 0, 0)
        renderer.add_overlay(widget)
        with renderer:
            buf = CellBuffer(10, 1)
            renderer.present(buf)
            # The original buffer should have been mutated by the overlay.
            cell = buf.get(0, 0)
            assert cell.char == "O"

    def test_overlays_persist_across_start_stop(self) -> None:
        """Overlays should persist across start/stop cycles."""
        renderer = TestRendererBuffer()
        widget = self._make_label_widget("Persist", 0, 0)
        renderer.add_overlay(widget)
        renderer.start()
        renderer.stop()
        renderer.start()
        assert renderer.overlay_count == 1
        renderer.stop()


# ---------------------------------------------------------------------------
# repr
# ---------------------------------------------------------------------------


class TestTestRendererBufferRepr:
    """Tests for __repr__."""

    def test_repr_when_not_started(self) -> None:
        renderer = TestRendererBuffer(width=40, height=20)
        r = repr(renderer)
        assert "TestRendererBuffer" in r
        assert "started=False" in r
        assert "40x20" in r

    def test_repr_when_started(self) -> None:
        renderer = TestRendererBuffer()
        renderer.start()
        r = repr(renderer)
        assert "started=True" in r
        renderer.stop()

    def test_repr_shows_frame_count(self) -> None:
        renderer = TestRendererBuffer()
        with renderer:
            renderer.present(CellBuffer(5, 3))
            r = repr(renderer)
            assert "frame_count=1" in r


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestTestRendererBufferErrorHandling:
    """Tests for error handling and edge cases."""

    def test_present_with_empty_buffer(self) -> None:
        """A 1x1 buffer (minimum size) should be capturable."""
        renderer = TestRendererBuffer()
        with renderer:
            buf = CellBuffer(1, 1)
            renderer.present(buf)
            assert renderer.last_frame is not None
            assert renderer.last_frame.width == 1
            assert renderer.last_frame.height == 1

    def test_present_preserves_dim_attribute(self) -> None:
        renderer = TestRendererBuffer()
        with renderer:
            buf = CellBuffer(10, 5)
            buf.put(0, 0, Cell(char="d", dim=True))
            renderer.present(buf)
            cell = renderer.get_cell(0, 0)
            assert cell.dim is True

    def test_present_preserves_default_cells(self) -> None:
        """Default (blank) cells should be captured correctly."""
        renderer = TestRendererBuffer()
        with renderer:
            buf = CellBuffer(5, 3)
            renderer.present(buf)
            cell = renderer.get_cell(0, 0)
            assert cell.char == " "
            assert cell.fg is None
            assert cell.bg is None
            assert cell.bold is False
            assert cell.dim is False


# ---------------------------------------------------------------------------
# Package export
# ---------------------------------------------------------------------------


class TestTestRendererBufferExport:
    """Tests for TestRendererBuffer availability in the public API."""

    def test_importable_from_wyby(self) -> None:
        from wyby import TestRendererBuffer as TRB

        assert TRB is TestRendererBuffer

    def test_in_all(self) -> None:
        import wyby

        assert "TestRendererBuffer" in wyby.__all__
