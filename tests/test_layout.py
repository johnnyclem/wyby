"""Tests for wyby.layout — HBox and VBox layout containers."""

from __future__ import annotations

import pytest

from wyby.button import Button
from wyby.grid import CellBuffer
from wyby.input import MouseEvent
from wyby.layout import Alignment, HBox, VBox
from wyby.widget import Widget


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class DummyWidget(Widget):
    """Minimal concrete widget for testing layout."""

    def draw(self, buffer: CellBuffer) -> None:
        if not self.visible:
            return
        buffer.put_text(self.x, self.y, "X" * self.width)


# ---------------------------------------------------------------------------
# HBox — Construction
# ---------------------------------------------------------------------------


class TestHBoxConstruction:
    """HBox creation and default state."""

    def test_default_values(self) -> None:
        box = HBox()
        assert box.x == 0
        assert box.y == 0
        assert box.width == 1
        assert box.height == 1
        assert box.spacing == 0
        assert box.padding == 0
        assert box.align == Alignment.START
        assert box.auto_layout is True

    def test_custom_values(self) -> None:
        box = HBox(x=5, y=10, width=40, height=3, spacing=2, padding=1,
                    align=Alignment.CENTER)
        assert box.x == 5
        assert box.y == 10
        assert box.width == 40
        assert box.height == 3
        assert box.spacing == 2
        assert box.padding == 1
        assert box.align == Alignment.CENTER

    def test_z_index(self) -> None:
        box = HBox(z_index=5)
        assert box.z_index == 5

    def test_is_widget(self) -> None:
        box = HBox()
        assert isinstance(box, Widget)


# ---------------------------------------------------------------------------
# HBox — Type validation
# ---------------------------------------------------------------------------


class TestHBoxTypeValidation:
    """Type checking on HBox constructor arguments."""

    def test_spacing_rejects_float(self) -> None:
        with pytest.raises(TypeError, match="spacing must be an int"):
            HBox(spacing=1.5)  # type: ignore[arg-type]

    def test_spacing_rejects_bool(self) -> None:
        with pytest.raises(TypeError, match="spacing must be an int"):
            HBox(spacing=True)  # type: ignore[arg-type]

    def test_padding_rejects_float(self) -> None:
        with pytest.raises(TypeError, match="padding must be an int"):
            HBox(padding=1.5)  # type: ignore[arg-type]

    def test_padding_rejects_bool(self) -> None:
        with pytest.raises(TypeError, match="padding must be an int"):
            HBox(padding=True)  # type: ignore[arg-type]

    def test_align_rejects_string(self) -> None:
        with pytest.raises(TypeError, match="align must be an Alignment"):
            HBox(align="center")  # type: ignore[arg-type]

    def test_negative_spacing_rejected(self) -> None:
        with pytest.raises(ValueError, match="spacing must be >= 0"):
            HBox(spacing=-1)

    def test_negative_padding_rejected(self) -> None:
        with pytest.raises(ValueError, match="padding must be >= 0"):
            HBox(padding=-1)


# ---------------------------------------------------------------------------
# HBox — Property setters
# ---------------------------------------------------------------------------


class TestHBoxProperties:
    """HBox property setters with validation."""

    def test_set_spacing(self) -> None:
        box = HBox()
        box.spacing = 3
        assert box.spacing == 3

    def test_set_spacing_rejects_float(self) -> None:
        box = HBox()
        with pytest.raises(TypeError, match="spacing must be an int"):
            box.spacing = 1.5  # type: ignore[assignment]

    def test_set_spacing_rejects_negative(self) -> None:
        box = HBox()
        with pytest.raises(ValueError, match="spacing must be >= 0"):
            box.spacing = -1

    def test_set_padding(self) -> None:
        box = HBox()
        box.padding = 2
        assert box.padding == 2

    def test_set_padding_rejects_float(self) -> None:
        box = HBox()
        with pytest.raises(TypeError, match="padding must be an int"):
            box.padding = 1.5  # type: ignore[assignment]

    def test_set_padding_rejects_negative(self) -> None:
        box = HBox()
        with pytest.raises(ValueError, match="padding must be >= 0"):
            box.padding = -1

    def test_set_align(self) -> None:
        box = HBox()
        box.align = Alignment.END
        assert box.align == Alignment.END

    def test_set_align_rejects_string(self) -> None:
        box = HBox()
        with pytest.raises(TypeError, match="align must be an Alignment"):
            box.align = "end"  # type: ignore[assignment]

    def test_set_auto_layout(self) -> None:
        box = HBox()
        box.auto_layout = False
        assert box.auto_layout is False


# ---------------------------------------------------------------------------
# HBox — Layout positioning
# ---------------------------------------------------------------------------


class TestHBoxLayout:
    """HBox child positioning."""

    def test_single_child_at_origin(self) -> None:
        box = HBox(x=0, y=0, width=40, height=3)
        child = DummyWidget(width=5, height=1)
        box.add_child(child)
        box.apply_layout()
        assert child.x == 0
        assert child.y == 0

    def test_two_children_packed(self) -> None:
        box = HBox(x=0, y=0, width=40, height=3)
        c1 = DummyWidget(width=5, height=1)
        c2 = DummyWidget(width=8, height=1)
        box.add_child(c1)
        box.add_child(c2)
        box.apply_layout()
        assert c1.x == 0
        assert c2.x == 5  # right after c1

    def test_two_children_with_spacing(self) -> None:
        box = HBox(x=0, y=0, width=40, height=3, spacing=2)
        c1 = DummyWidget(width=5, height=1)
        c2 = DummyWidget(width=8, height=1)
        box.add_child(c1)
        box.add_child(c2)
        box.apply_layout()
        assert c1.x == 0
        assert c2.x == 7  # 5 (c1 width) + 2 (spacing)

    def test_three_children_with_spacing(self) -> None:
        box = HBox(x=0, y=0, width=60, height=3, spacing=1)
        c1 = DummyWidget(width=3, height=1)
        c2 = DummyWidget(width=4, height=1)
        c3 = DummyWidget(width=5, height=1)
        box.add_child(c1)
        box.add_child(c2)
        box.add_child(c3)
        box.apply_layout()
        assert c1.x == 0
        assert c2.x == 4   # 3 + 1
        assert c3.x == 9   # 4 + 4 + 1

    def test_padding_offsets_start(self) -> None:
        box = HBox(x=0, y=0, width=40, height=5, padding=2)
        child = DummyWidget(width=5, height=1)
        box.add_child(child)
        box.apply_layout()
        assert child.x == 2  # padding
        assert child.y == 2  # padding (START alignment)

    def test_container_offset(self) -> None:
        """Container's own position offsets children."""
        box = HBox(x=10, y=5, width=40, height=3)
        child = DummyWidget(width=5, height=1)
        box.add_child(child)
        box.apply_layout()
        assert child.x == 10
        assert child.y == 5

    def test_container_offset_with_padding(self) -> None:
        box = HBox(x=10, y=5, width=40, height=5, padding=1)
        child = DummyWidget(width=5, height=1)
        box.add_child(child)
        box.apply_layout()
        assert child.x == 11  # 10 + 1
        assert child.y == 6   # 5 + 1

    def test_align_start(self) -> None:
        """START alignment places children at the top."""
        box = HBox(x=0, y=0, width=40, height=10, align=Alignment.START)
        child = DummyWidget(width=5, height=2)
        box.add_child(child)
        box.apply_layout()
        assert child.y == 0

    def test_align_center(self) -> None:
        """CENTER alignment vertically centres children."""
        box = HBox(x=0, y=0, width=40, height=10, align=Alignment.CENTER)
        child = DummyWidget(width=5, height=2)
        box.add_child(child)
        box.apply_layout()
        # inner_height = 10, child height = 2, offset = (10 - 2) // 2 = 4
        assert child.y == 4

    def test_align_end(self) -> None:
        """END alignment places children at the bottom."""
        box = HBox(x=0, y=0, width=40, height=10, align=Alignment.END)
        child = DummyWidget(width=5, height=2)
        box.add_child(child)
        box.apply_layout()
        # inner_height = 10, child height = 2, y = 0 + 10 - 2 = 8
        assert child.y == 8

    def test_align_center_with_padding(self) -> None:
        box = HBox(x=0, y=0, width=40, height=12, padding=1,
                    align=Alignment.CENTER)
        child = DummyWidget(width=5, height=2)
        box.add_child(child)
        box.apply_layout()
        # inner_height = 12 - 2*1 = 10, offset = (10 - 2) // 2 = 4
        # child.y = 0 + 1 + 4 = 5
        assert child.y == 5

    def test_invisible_children_skipped(self) -> None:
        """Invisible children don't consume layout space."""
        box = HBox(x=0, y=0, width=40, height=3, spacing=1)
        c1 = DummyWidget(width=5, height=1)
        c2 = DummyWidget(width=5, height=1)
        c2.visible = False
        c3 = DummyWidget(width=5, height=1)
        box.add_child(c1)
        box.add_child(c2)
        box.add_child(c3)
        box.apply_layout()
        assert c1.x == 0
        # c2 is skipped, so c3 is right after c1
        assert c3.x == 6  # 5 + 1

    def test_no_children(self) -> None:
        """Empty layout does nothing."""
        box = HBox(x=0, y=0, width=40, height=3)
        box.apply_layout()  # should not raise


# ---------------------------------------------------------------------------
# HBox — Drawing
# ---------------------------------------------------------------------------


class TestHBoxDraw:
    """HBox drawing into CellBuffer."""

    def test_draws_children(self) -> None:
        buf = CellBuffer(20, 5)
        box = HBox(x=0, y=0, width=20, height=5)
        c1 = DummyWidget(width=3, height=1)
        c2 = DummyWidget(width=3, height=1)
        box.add_child(c1)
        box.add_child(c2)
        box.draw(buf)
        # c1 at x=0, c2 at x=3
        assert buf.get(0, 0).char == "X"
        assert buf.get(2, 0).char == "X"
        assert buf.get(3, 0).char == "X"
        assert buf.get(5, 0).char == "X"

    def test_skips_draw_when_invisible(self) -> None:
        buf = CellBuffer(20, 5)
        box = HBox(x=0, y=0, width=20, height=5)
        child = DummyWidget(width=3, height=1)
        box.add_child(child)
        box.visible = False
        box.draw(buf)
        assert buf.get(0, 0).char == " "

    def test_auto_layout_on_draw(self) -> None:
        """Layout is applied automatically before drawing."""
        buf = CellBuffer(20, 5)
        box = HBox(x=0, y=0, width=20, height=5, spacing=2)
        c1 = DummyWidget(width=3, height=1)
        c2 = DummyWidget(width=3, height=1)
        box.add_child(c1)
        box.add_child(c2)
        # Don't call apply_layout manually — draw should do it
        box.draw(buf)
        assert c1.x == 0
        assert c2.x == 5  # 3 + 2

    def test_no_auto_layout(self) -> None:
        """With auto_layout=False, draw does not reposition children."""
        box = HBox(x=0, y=0, width=20, height=5, auto_layout=False)
        child = DummyWidget(x=99, y=99, width=3, height=1)
        box.add_child(child)
        buf = CellBuffer(20, 5)
        box.draw(buf)
        # Position should remain as manually set
        assert child.x == 99
        assert child.y == 99

    def test_draws_with_buttons(self) -> None:
        """Integration: HBox positions real Button widgets."""
        buf = CellBuffer(40, 5)
        box = HBox(x=0, y=0, width=40, height=3, spacing=1)
        btn1 = Button("OK")
        btn2 = Button("Cancel")
        box.add_child(btn1)
        box.add_child(btn2)
        box.draw(buf)
        # btn1 at x=0: "[ OK ]" (width 6)
        assert buf.get(0, 0).char == "["
        # btn2 at x=7: "[ Cancel ]"
        assert buf.get(7, 0).char == "["


# ---------------------------------------------------------------------------
# HBox — Event handling
# ---------------------------------------------------------------------------


class TestHBoxEventHandling:
    """HBox event routing to children."""

    def test_routes_event_to_children(self) -> None:
        box = HBox(x=0, y=0, width=40, height=3)
        calls: list[str] = []
        btn = Button("OK", on_click=lambda: calls.append("clicked"))
        box.add_child(btn)
        box.apply_layout()
        event = MouseEvent(x=2, y=0, button="left", action="press")
        result = box.handle_event(event)
        assert result is True
        assert calls == ["clicked"]

    def test_event_not_consumed_when_missed(self) -> None:
        box = HBox(x=0, y=0, width=40, height=3)
        btn = Button("OK", on_click=lambda: None)
        box.add_child(btn)
        box.apply_layout()
        event = MouseEvent(x=30, y=0, button="left", action="press")
        result = box.handle_event(event)
        assert result is False

    def test_reverse_order_routing(self) -> None:
        """Last child gets first chance at the event."""
        box = HBox(x=0, y=0, width=40, height=3)
        calls: list[str] = []
        # Two overlapping buttons at the same position
        btn1 = Button("A", x=0, y=0, on_click=lambda: calls.append("A"))
        btn2 = Button("B", x=0, y=0, on_click=lambda: calls.append("B"))
        box.add_child(btn1)
        box.add_child(btn2)
        # Don't apply_layout — manually set overlapping positions
        box.auto_layout = False
        event = MouseEvent(x=1, y=0, button="left", action="press")
        box.handle_event(event)
        # btn2 (last added) should handle first
        assert calls == ["B"]

    def test_skips_invisible_children(self) -> None:
        box = HBox(x=0, y=0, width=40, height=3)
        calls: list[str] = []
        btn = Button("OK", x=0, y=0, on_click=lambda: calls.append("clicked"))
        btn.visible = False
        box.add_child(btn)
        event = MouseEvent(x=2, y=0, button="left", action="press")
        result = box.handle_event(event)
        assert result is False
        assert calls == []


# ---------------------------------------------------------------------------
# HBox — Repr
# ---------------------------------------------------------------------------


class TestHBoxRepr:
    """HBox string representation."""

    def test_repr(self) -> None:
        box = HBox(x=1, y=2, width=40, height=3, spacing=2, padding=1)
        r = repr(box)
        assert "HBox(" in r
        assert "x=1" in r
        assert "y=2" in r
        assert "spacing=2" in r
        assert "padding=1" in r
        assert "children=0" in r

    def test_repr_with_children(self) -> None:
        box = HBox(x=0, y=0, width=40, height=3)
        box.add_child(DummyWidget(width=5, height=1))
        box.add_child(DummyWidget(width=5, height=1))
        assert "children=2" in repr(box)


# ---------------------------------------------------------------------------
# VBox — Construction
# ---------------------------------------------------------------------------


class TestVBoxConstruction:
    """VBox creation and default state."""

    def test_default_values(self) -> None:
        box = VBox()
        assert box.x == 0
        assert box.y == 0
        assert box.width == 1
        assert box.height == 1
        assert box.spacing == 0
        assert box.padding == 0
        assert box.align == Alignment.START
        assert box.auto_layout is True

    def test_custom_values(self) -> None:
        box = VBox(x=5, y=10, width=40, height=20, spacing=1, padding=2,
                    align=Alignment.END)
        assert box.x == 5
        assert box.y == 10
        assert box.width == 40
        assert box.height == 20
        assert box.spacing == 1
        assert box.padding == 2
        assert box.align == Alignment.END

    def test_z_index(self) -> None:
        box = VBox(z_index=3)
        assert box.z_index == 3

    def test_is_widget(self) -> None:
        box = VBox()
        assert isinstance(box, Widget)


# ---------------------------------------------------------------------------
# VBox — Type validation
# ---------------------------------------------------------------------------


class TestVBoxTypeValidation:
    """Type checking on VBox constructor arguments."""

    def test_spacing_rejects_float(self) -> None:
        with pytest.raises(TypeError, match="spacing must be an int"):
            VBox(spacing=1.5)  # type: ignore[arg-type]

    def test_spacing_rejects_bool(self) -> None:
        with pytest.raises(TypeError, match="spacing must be an int"):
            VBox(spacing=True)  # type: ignore[arg-type]

    def test_padding_rejects_float(self) -> None:
        with pytest.raises(TypeError, match="padding must be an int"):
            VBox(padding=1.5)  # type: ignore[arg-type]

    def test_padding_rejects_bool(self) -> None:
        with pytest.raises(TypeError, match="padding must be an int"):
            VBox(padding=True)  # type: ignore[arg-type]

    def test_align_rejects_string(self) -> None:
        with pytest.raises(TypeError, match="align must be an Alignment"):
            VBox(align="center")  # type: ignore[arg-type]

    def test_negative_spacing_rejected(self) -> None:
        with pytest.raises(ValueError, match="spacing must be >= 0"):
            VBox(spacing=-1)

    def test_negative_padding_rejected(self) -> None:
        with pytest.raises(ValueError, match="padding must be >= 0"):
            VBox(padding=-1)


# ---------------------------------------------------------------------------
# VBox — Property setters
# ---------------------------------------------------------------------------


class TestVBoxProperties:
    """VBox property setters with validation."""

    def test_set_spacing(self) -> None:
        box = VBox()
        box.spacing = 3
        assert box.spacing == 3

    def test_set_spacing_rejects_float(self) -> None:
        box = VBox()
        with pytest.raises(TypeError, match="spacing must be an int"):
            box.spacing = 1.5  # type: ignore[assignment]

    def test_set_spacing_rejects_negative(self) -> None:
        box = VBox()
        with pytest.raises(ValueError, match="spacing must be >= 0"):
            box.spacing = -1

    def test_set_padding(self) -> None:
        box = VBox()
        box.padding = 2
        assert box.padding == 2

    def test_set_padding_rejects_float(self) -> None:
        box = VBox()
        with pytest.raises(TypeError, match="padding must be an int"):
            box.padding = 1.5  # type: ignore[assignment]

    def test_set_padding_rejects_negative(self) -> None:
        box = VBox()
        with pytest.raises(ValueError, match="padding must be >= 0"):
            box.padding = -1

    def test_set_align(self) -> None:
        box = VBox()
        box.align = Alignment.CENTER
        assert box.align == Alignment.CENTER

    def test_set_align_rejects_string(self) -> None:
        box = VBox()
        with pytest.raises(TypeError, match="align must be an Alignment"):
            box.align = "center"  # type: ignore[assignment]

    def test_set_auto_layout(self) -> None:
        box = VBox()
        box.auto_layout = False
        assert box.auto_layout is False


# ---------------------------------------------------------------------------
# VBox — Layout positioning
# ---------------------------------------------------------------------------


class TestVBoxLayout:
    """VBox child positioning."""

    def test_single_child_at_origin(self) -> None:
        box = VBox(x=0, y=0, width=40, height=20)
        child = DummyWidget(width=5, height=1)
        box.add_child(child)
        box.apply_layout()
        assert child.x == 0
        assert child.y == 0

    def test_two_children_packed(self) -> None:
        box = VBox(x=0, y=0, width=40, height=20)
        c1 = DummyWidget(width=5, height=2)
        c2 = DummyWidget(width=5, height=3)
        box.add_child(c1)
        box.add_child(c2)
        box.apply_layout()
        assert c1.y == 0
        assert c2.y == 2  # right below c1

    def test_two_children_with_spacing(self) -> None:
        box = VBox(x=0, y=0, width=40, height=20, spacing=1)
        c1 = DummyWidget(width=5, height=2)
        c2 = DummyWidget(width=5, height=3)
        box.add_child(c1)
        box.add_child(c2)
        box.apply_layout()
        assert c1.y == 0
        assert c2.y == 3  # 2 (c1 height) + 1 (spacing)

    def test_three_children_with_spacing(self) -> None:
        box = VBox(x=0, y=0, width=40, height=30, spacing=2)
        c1 = DummyWidget(width=5, height=1)
        c2 = DummyWidget(width=5, height=3)
        c3 = DummyWidget(width=5, height=2)
        box.add_child(c1)
        box.add_child(c2)
        box.add_child(c3)
        box.apply_layout()
        assert c1.y == 0
        assert c2.y == 3   # 1 + 2
        assert c3.y == 8   # 3 + 3 + 2

    def test_padding_offsets_start(self) -> None:
        box = VBox(x=0, y=0, width=40, height=20, padding=3)
        child = DummyWidget(width=5, height=1)
        box.add_child(child)
        box.apply_layout()
        assert child.x == 3  # padding (START alignment)
        assert child.y == 3  # padding

    def test_container_offset(self) -> None:
        box = VBox(x=10, y=5, width=40, height=20)
        child = DummyWidget(width=5, height=1)
        box.add_child(child)
        box.apply_layout()
        assert child.x == 10
        assert child.y == 5

    def test_container_offset_with_padding(self) -> None:
        box = VBox(x=10, y=5, width=40, height=20, padding=2)
        child = DummyWidget(width=5, height=1)
        box.add_child(child)
        box.apply_layout()
        assert child.x == 12  # 10 + 2
        assert child.y == 7   # 5 + 2

    def test_align_start(self) -> None:
        """START alignment places children at the left."""
        box = VBox(x=0, y=0, width=20, height=20, align=Alignment.START)
        child = DummyWidget(width=5, height=1)
        box.add_child(child)
        box.apply_layout()
        assert child.x == 0

    def test_align_center(self) -> None:
        """CENTER alignment horizontally centres children."""
        box = VBox(x=0, y=0, width=20, height=20, align=Alignment.CENTER)
        child = DummyWidget(width=6, height=1)
        box.add_child(child)
        box.apply_layout()
        # inner_width = 20, child width = 6, offset = (20 - 6) // 2 = 7
        assert child.x == 7

    def test_align_end(self) -> None:
        """END alignment places children at the right."""
        box = VBox(x=0, y=0, width=20, height=20, align=Alignment.END)
        child = DummyWidget(width=6, height=1)
        box.add_child(child)
        box.apply_layout()
        # inner_width = 20, child width = 6, x = 0 + 20 - 6 = 14
        assert child.x == 14

    def test_align_center_with_padding(self) -> None:
        box = VBox(x=0, y=0, width=22, height=20, padding=1,
                    align=Alignment.CENTER)
        child = DummyWidget(width=6, height=1)
        box.add_child(child)
        box.apply_layout()
        # inner_width = 22 - 2*1 = 20, offset = (20 - 6) // 2 = 7
        # child.x = 0 + 1 + 7 = 8
        assert child.x == 8

    def test_invisible_children_skipped(self) -> None:
        box = VBox(x=0, y=0, width=40, height=20, spacing=1)
        c1 = DummyWidget(width=5, height=2)
        c2 = DummyWidget(width=5, height=2)
        c2.visible = False
        c3 = DummyWidget(width=5, height=2)
        box.add_child(c1)
        box.add_child(c2)
        box.add_child(c3)
        box.apply_layout()
        assert c1.y == 0
        # c2 skipped, so c3 is right after c1
        assert c3.y == 3  # 2 + 1

    def test_no_children(self) -> None:
        box = VBox(x=0, y=0, width=40, height=20)
        box.apply_layout()  # should not raise


# ---------------------------------------------------------------------------
# VBox — Drawing
# ---------------------------------------------------------------------------


class TestVBoxDraw:
    """VBox drawing into CellBuffer."""

    def test_draws_children(self) -> None:
        buf = CellBuffer(20, 10)
        box = VBox(x=0, y=0, width=20, height=10)
        c1 = DummyWidget(width=3, height=1)
        c2 = DummyWidget(width=3, height=1)
        box.add_child(c1)
        box.add_child(c2)
        box.draw(buf)
        # c1 at y=0
        assert buf.get(0, 0).char == "X"
        # c2 at y=1
        assert buf.get(0, 1).char == "X"

    def test_skips_draw_when_invisible(self) -> None:
        buf = CellBuffer(20, 10)
        box = VBox(x=0, y=0, width=20, height=10)
        child = DummyWidget(width=3, height=1)
        box.add_child(child)
        box.visible = False
        box.draw(buf)
        assert buf.get(0, 0).char == " "

    def test_auto_layout_on_draw(self) -> None:
        buf = CellBuffer(20, 10)
        box = VBox(x=0, y=0, width=20, height=10, spacing=2)
        c1 = DummyWidget(width=3, height=1)
        c2 = DummyWidget(width=3, height=1)
        box.add_child(c1)
        box.add_child(c2)
        box.draw(buf)
        assert c1.y == 0
        assert c2.y == 3  # 1 + 2

    def test_no_auto_layout(self) -> None:
        box = VBox(x=0, y=0, width=20, height=10, auto_layout=False)
        child = DummyWidget(x=99, y=99, width=3, height=1)
        box.add_child(child)
        buf = CellBuffer(20, 10)
        box.draw(buf)
        assert child.x == 99
        assert child.y == 99

    def test_draws_with_buttons(self) -> None:
        """Integration: VBox positions real Button widgets."""
        buf = CellBuffer(40, 10)
        box = VBox(x=0, y=0, width=40, height=10, spacing=1)
        btn1 = Button("OK")
        btn2 = Button("Cancel")
        box.add_child(btn1)
        box.add_child(btn2)
        box.draw(buf)
        # btn1 at y=0
        assert buf.get(0, 0).char == "["
        # btn2 at y=2 (1 height + 1 spacing)
        assert buf.get(0, 2).char == "["


# ---------------------------------------------------------------------------
# VBox — Event handling
# ---------------------------------------------------------------------------


class TestVBoxEventHandling:
    """VBox event routing to children."""

    def test_routes_event_to_children(self) -> None:
        box = VBox(x=0, y=0, width=40, height=20)
        calls: list[str] = []
        btn = Button("OK", on_click=lambda: calls.append("clicked"))
        box.add_child(btn)
        box.apply_layout()
        event = MouseEvent(x=2, y=0, button="left", action="press")
        result = box.handle_event(event)
        assert result is True
        assert calls == ["clicked"]

    def test_event_not_consumed_when_missed(self) -> None:
        box = VBox(x=0, y=0, width=40, height=20)
        btn = Button("OK", on_click=lambda: None)
        box.add_child(btn)
        box.apply_layout()
        event = MouseEvent(x=30, y=15, button="left", action="press")
        result = box.handle_event(event)
        assert result is False

    def test_skips_invisible_children(self) -> None:
        box = VBox(x=0, y=0, width=40, height=20)
        calls: list[str] = []
        btn = Button("OK", x=0, y=0, on_click=lambda: calls.append("clicked"))
        btn.visible = False
        box.add_child(btn)
        event = MouseEvent(x=2, y=0, button="left", action="press")
        result = box.handle_event(event)
        assert result is False


# ---------------------------------------------------------------------------
# VBox — Repr
# ---------------------------------------------------------------------------


class TestVBoxRepr:
    """VBox string representation."""

    def test_repr(self) -> None:
        box = VBox(x=1, y=2, width=40, height=20, spacing=1, padding=2)
        r = repr(box)
        assert "VBox(" in r
        assert "x=1" in r
        assert "y=2" in r
        assert "spacing=1" in r
        assert "padding=2" in r
        assert "children=0" in r

    def test_repr_with_children(self) -> None:
        box = VBox(x=0, y=0, width=40, height=20)
        box.add_child(DummyWidget(width=5, height=1))
        assert "children=1" in repr(box)


# ---------------------------------------------------------------------------
# Nested layouts
# ---------------------------------------------------------------------------


class TestNestedLayouts:
    """Composing layout containers."""

    def test_vbox_containing_hbox(self) -> None:
        """VBox with an HBox child positions the HBox, then HBox
        positions its own children."""
        outer = VBox(x=0, y=0, width=40, height=20, spacing=1)
        row = HBox(x=0, y=0, width=40, height=1, spacing=2)
        c1 = DummyWidget(width=5, height=1)
        c2 = DummyWidget(width=5, height=1)
        row.add_child(c1)
        row.add_child(c2)
        outer.add_child(row)

        buf = CellBuffer(40, 20)
        outer.draw(buf)

        # VBox places the HBox at y=0
        assert row.y == 0
        # HBox places c1 at x=0, c2 at x=7 (5 + 2)
        assert c1.x == 0
        assert c2.x == 7

    def test_hbox_containing_vbox(self) -> None:
        outer = HBox(x=0, y=0, width=40, height=10)
        col = VBox(x=0, y=0, width=10, height=10, spacing=1)
        c1 = DummyWidget(width=5, height=2)
        c2 = DummyWidget(width=5, height=2)
        col.add_child(c1)
        col.add_child(c2)
        outer.add_child(col)

        buf = CellBuffer(40, 10)
        outer.draw(buf)

        # HBox places VBox at x=0
        assert col.x == 0
        # VBox places c1 at y=0, c2 at y=3 (2 + 1)
        assert c1.y == 0
        assert c2.y == 3


# ---------------------------------------------------------------------------
# Alignment enum
# ---------------------------------------------------------------------------


class TestAlignment:
    """Alignment enum values."""

    def test_values(self) -> None:
        assert Alignment.START.value == "start"
        assert Alignment.CENTER.value == "center"
        assert Alignment.END.value == "end"

    def test_members(self) -> None:
        assert len(Alignment) == 3


# ---------------------------------------------------------------------------
# Import from package root
# ---------------------------------------------------------------------------


class TestLayoutImport:
    """Layout classes are accessible from the wyby package root."""

    def test_import_hbox(self) -> None:
        from wyby import HBox as H
        assert H is HBox

    def test_import_vbox(self) -> None:
        from wyby import VBox as V
        assert V is VBox

    def test_import_alignment(self) -> None:
        from wyby import Alignment as A
        assert A is Alignment
