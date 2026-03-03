"""Tests for Renderer overlay draw support."""

from __future__ import annotations

import io

import pytest
from rich.console import Console
from rich.text import Text

from wyby.grid import CellBuffer
from wyby.renderer import Renderer
from wyby.widget import Widget


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class StubOverlay(Widget):
    """Minimal overlay that records draw calls and writes a marker cell."""

    def __init__(
        self,
        x: int = 0,
        y: int = 0,
        width: int = 1,
        height: int = 1,
        marker: str = "X",
    ) -> None:
        super().__init__(x=x, y=y, width=width, height=height)
        self.marker = marker
        self.draw_count = 0

    def draw(self, buffer: CellBuffer) -> None:
        if not self.visible:
            return
        self.draw_count += 1
        buffer.put_text(self.x, self.y, self.marker)


def _make_renderer() -> Renderer:
    console = Console(file=io.StringIO(), force_terminal=True)
    return Renderer(console=console)


# ---------------------------------------------------------------------------
# add_overlay
# ---------------------------------------------------------------------------


class TestAddOverlay:
    """Tests for Renderer.add_overlay()."""

    def test_adds_widget(self) -> None:
        renderer = _make_renderer()
        overlay = StubOverlay()
        renderer.add_overlay(overlay)
        assert overlay in renderer.overlays

    def test_overlay_count_increments(self) -> None:
        renderer = _make_renderer()
        assert renderer.overlay_count == 0
        renderer.add_overlay(StubOverlay())
        assert renderer.overlay_count == 1
        renderer.add_overlay(StubOverlay())
        assert renderer.overlay_count == 2

    def test_duplicate_add_is_noop(self) -> None:
        renderer = _make_renderer()
        overlay = StubOverlay()
        renderer.add_overlay(overlay)
        renderer.add_overlay(overlay)
        assert renderer.overlay_count == 1

    def test_rejects_non_widget_string(self) -> None:
        renderer = _make_renderer()
        with pytest.raises(TypeError, match="Widget"):
            renderer.add_overlay("not a widget")  # type: ignore[arg-type]

    def test_rejects_non_widget_int(self) -> None:
        renderer = _make_renderer()
        with pytest.raises(TypeError, match="Widget"):
            renderer.add_overlay(42)  # type: ignore[arg-type]

    def test_rejects_none(self) -> None:
        renderer = _make_renderer()
        with pytest.raises(TypeError, match="Widget"):
            renderer.add_overlay(None)  # type: ignore[arg-type]

    def test_preserves_registration_order(self) -> None:
        renderer = _make_renderer()
        a = StubOverlay(marker="A")
        b = StubOverlay(marker="B")
        c = StubOverlay(marker="C")
        renderer.add_overlay(a)
        renderer.add_overlay(b)
        renderer.add_overlay(c)
        assert renderer.overlays == [a, b, c]


# ---------------------------------------------------------------------------
# remove_overlay
# ---------------------------------------------------------------------------


class TestRemoveOverlay:
    """Tests for Renderer.remove_overlay()."""

    def test_removes_widget(self) -> None:
        renderer = _make_renderer()
        overlay = StubOverlay()
        renderer.add_overlay(overlay)
        renderer.remove_overlay(overlay)
        assert overlay not in renderer.overlays
        assert renderer.overlay_count == 0

    def test_raises_on_unknown_widget(self) -> None:
        renderer = _make_renderer()
        overlay = StubOverlay()
        with pytest.raises(ValueError, match="not a registered overlay"):
            renderer.remove_overlay(overlay)

    def test_removes_correct_widget_from_multiple(self) -> None:
        renderer = _make_renderer()
        a = StubOverlay(marker="A")
        b = StubOverlay(marker="B")
        renderer.add_overlay(a)
        renderer.add_overlay(b)
        renderer.remove_overlay(a)
        assert renderer.overlays == [b]


# ---------------------------------------------------------------------------
# clear_overlays
# ---------------------------------------------------------------------------


class TestClearOverlays:
    """Tests for Renderer.clear_overlays()."""

    def test_clears_all(self) -> None:
        renderer = _make_renderer()
        renderer.add_overlay(StubOverlay())
        renderer.add_overlay(StubOverlay())
        renderer.clear_overlays()
        assert renderer.overlay_count == 0

    def test_clear_when_empty_is_noop(self) -> None:
        renderer = _make_renderer()
        renderer.clear_overlays()  # Should not raise.
        assert renderer.overlay_count == 0


# ---------------------------------------------------------------------------
# overlays property
# ---------------------------------------------------------------------------


class TestOverlaysProperty:
    """Tests for Renderer.overlays property."""

    def test_returns_copy(self) -> None:
        """Mutating the returned list should not affect the renderer."""
        renderer = _make_renderer()
        overlay = StubOverlay()
        renderer.add_overlay(overlay)
        copy = renderer.overlays
        copy.clear()
        assert renderer.overlay_count == 1

    def test_empty_by_default(self) -> None:
        renderer = _make_renderer()
        assert renderer.overlays == []


# ---------------------------------------------------------------------------
# present() — overlay compositing
# ---------------------------------------------------------------------------


class TestPresentWithOverlays:
    """Tests for overlay drawing during Renderer.present()."""

    def test_overlay_drawn_on_cellbuffer(self) -> None:
        """Overlay.draw() should be called when present() receives a CellBuffer."""
        renderer = _make_renderer()
        overlay = StubOverlay(x=0, y=0, marker="@")
        renderer.add_overlay(overlay)
        buf = CellBuffer(10, 5)
        with renderer:
            renderer.present(buf)
        assert overlay.draw_count == 1

    def test_overlay_writes_into_buffer(self) -> None:
        """Overlay content should appear in the CellBuffer after present()."""
        renderer = _make_renderer()
        overlay = StubOverlay(x=2, y=1, marker="H")
        renderer.add_overlay(overlay)
        buf = CellBuffer(10, 5)
        with renderer:
            renderer.present(buf)
        cell = buf.get(2, 1)
        assert cell is not None
        assert cell.char == "H"

    def test_multiple_overlays_draw_in_order(self) -> None:
        """Later overlays overwrite earlier ones at the same position."""
        renderer = _make_renderer()
        first = StubOverlay(x=0, y=0, marker="A")
        second = StubOverlay(x=0, y=0, marker="B")
        renderer.add_overlay(first)
        renderer.add_overlay(second)
        buf = CellBuffer(10, 5)
        with renderer:
            renderer.present(buf)
        # "B" was drawn last, so it should be visible at (0, 0).
        cell = buf.get(0, 0)
        assert cell is not None
        assert cell.char == "B"
        assert first.draw_count == 1
        assert second.draw_count == 1

    def test_hidden_overlay_not_drawn(self) -> None:
        """Overlays with visible=False should be skipped."""
        renderer = _make_renderer()
        overlay = StubOverlay(x=0, y=0, marker="X")
        overlay.visible = False
        renderer.add_overlay(overlay)
        buf = CellBuffer(10, 5)
        with renderer:
            renderer.present(buf)
        assert overlay.draw_count == 0
        # Buffer cell at (0, 0) should still be the default blank.
        cell = buf.get(0, 0)
        assert cell is not None
        assert cell.char == " "

    def test_overlay_skipped_for_non_cellbuffer(self) -> None:
        """Overlays should not interfere with non-CellBuffer renderables."""
        renderer = _make_renderer()
        overlay = StubOverlay(x=0, y=0, marker="X")
        renderer.add_overlay(overlay)
        with renderer:
            renderer.present(Text("plain text"))
            renderer.present("just a string")
        # Overlay draw() should not have been called since neither
        # renderable is a CellBuffer.
        assert overlay.draw_count == 0
        assert renderer.frame_count == 2

    def test_no_overlays_no_side_effects(self) -> None:
        """present() with no overlays should not modify the buffer."""
        renderer = _make_renderer()
        buf = CellBuffer(5, 3)
        buf.put_text(0, 0, "Hi")
        with renderer:
            renderer.present(buf)
        cell = buf.get(0, 0)
        assert cell is not None
        assert cell.char == "H"

    def test_overlay_drawn_each_frame(self) -> None:
        """Overlays should be drawn on every present() call."""
        renderer = _make_renderer()
        overlay = StubOverlay(x=0, y=0, marker="F")
        renderer.add_overlay(overlay)
        buf = CellBuffer(10, 5)
        with renderer:
            for _ in range(5):
                buf.clear()
                renderer.present(buf)
        assert overlay.draw_count == 5

    def test_present_still_increments_frame_count(self) -> None:
        """frame_count should increment normally with overlays."""
        renderer = _make_renderer()
        renderer.add_overlay(StubOverlay())
        buf = CellBuffer(10, 5)
        with renderer:
            renderer.present(buf)
            renderer.present(buf)
        assert renderer.frame_count == 2

    def test_overlay_not_drawn_when_renderer_stopped(self) -> None:
        """present() is a no-op when not started, even with overlays."""
        renderer = _make_renderer()
        overlay = StubOverlay()
        renderer.add_overlay(overlay)
        renderer.present(CellBuffer(5, 3))
        assert overlay.draw_count == 0


# ---------------------------------------------------------------------------
# Overlay persistence across start/stop
# ---------------------------------------------------------------------------


class TestOverlayPersistence:
    """Overlays persist across start/stop cycles."""

    def test_overlays_survive_stop(self) -> None:
        renderer = _make_renderer()
        overlay = StubOverlay()
        renderer.add_overlay(overlay)
        renderer.start()
        renderer.stop()
        assert renderer.overlay_count == 1

    def test_overlays_survive_restart(self) -> None:
        renderer = _make_renderer()
        overlay = StubOverlay(x=0, y=0, marker="P")
        renderer.add_overlay(overlay)
        buf = CellBuffer(10, 5)

        renderer.start()
        renderer.present(buf)
        renderer.stop()

        buf.clear()
        renderer.start()
        try:
            renderer.present(buf)
        finally:
            renderer.stop()

        assert overlay.draw_count == 2


# ---------------------------------------------------------------------------
# repr
# ---------------------------------------------------------------------------


class TestRendererOverlayRepr:
    """Renderer repr should include overlay count."""

    def test_repr_shows_overlay_count(self) -> None:
        renderer = _make_renderer()
        renderer.add_overlay(StubOverlay())
        renderer.add_overlay(StubOverlay())
        r = repr(renderer)
        assert "overlays=2" in r

    def test_repr_zero_overlays(self) -> None:
        renderer = _make_renderer()
        r = repr(renderer)
        assert "overlays=0" in r
