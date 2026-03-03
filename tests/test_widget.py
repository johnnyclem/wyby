"""Tests for wyby.widget — Widget base class for terminal UI overlays."""

from __future__ import annotations

import pytest

from wyby.event import Event
from wyby.grid import CellBuffer
from wyby.widget import Widget


# ---------------------------------------------------------------------------
# Helpers — concrete subclasses for testing
# ---------------------------------------------------------------------------


class DummyWidget(Widget):
    """Minimal concrete widget for testing the base class."""

    def __init__(
        self,
        x: int = 0,
        y: int = 0,
        width: int = 5,
        height: int = 3,
    ) -> None:
        super().__init__(x=x, y=y, width=width, height=height)
        self.draw_count = 0

    def draw(self, buffer: CellBuffer) -> None:
        self.draw_count += 1


class LabelWidget(Widget):
    """A simple label widget that draws text."""

    def __init__(self, text: str, x: int = 0, y: int = 0) -> None:
        super().__init__(x=x, y=y, width=len(text), height=1)
        self.text = text

    def draw(self, buffer: CellBuffer) -> None:
        if not self.visible:
            return
        buffer.put_text(self.x, self.y, self.text)


class FocusTracker(Widget):
    """Widget that records focus/blur events."""

    def __init__(self, **kwargs: int) -> None:
        super().__init__(**kwargs)
        self.focus_count = 0
        self.blur_count = 0

    def draw(self, buffer: CellBuffer) -> None:
        pass

    def on_focus(self) -> None:
        self.focus_count += 1

    def on_blur(self) -> None:
        self.blur_count += 1


class EventConsumer(Widget):
    """Widget that consumes specific events."""

    def __init__(self, consume: bool = True, **kwargs: int) -> None:
        super().__init__(**kwargs)
        self._consume = consume
        self.events_received: list[Event] = []

    def draw(self, buffer: CellBuffer) -> None:
        pass

    def handle_event(self, event: Event) -> bool:
        self.events_received.append(event)
        return self._consume


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestWidgetConstruction:
    """Widget creation and default state."""

    def test_default_position(self) -> None:
        w = DummyWidget()
        assert w.x == 0
        assert w.y == 0

    def test_custom_position(self) -> None:
        w = DummyWidget(x=10, y=20)
        assert w.x == 10
        assert w.y == 20

    def test_default_size(self) -> None:
        w = DummyWidget()
        assert w.width == 5
        assert w.height == 3

    def test_custom_size(self) -> None:
        w = DummyWidget(x=0, y=0, width=40, height=20)
        assert w.width == 40
        assert w.height == 20

    def test_default_visible(self) -> None:
        w = DummyWidget()
        assert w.visible is True

    def test_default_not_focused(self) -> None:
        w = DummyWidget()
        assert w.focused is False

    def test_default_no_parent(self) -> None:
        w = DummyWidget()
        assert w.parent is None

    def test_default_no_children(self) -> None:
        w = DummyWidget()
        assert w.children == []

    def test_negative_position_allowed(self) -> None:
        w = DummyWidget(x=-5, y=-10)
        assert w.x == -5
        assert w.y == -10

    def test_width_clamped_to_minimum(self) -> None:
        w = DummyWidget(x=0, y=0, width=0, height=1)
        assert w.width == 1

    def test_height_clamped_to_minimum(self) -> None:
        w = DummyWidget(x=0, y=0, width=1, height=0)
        assert w.height == 1

    def test_width_clamped_to_maximum(self) -> None:
        w = DummyWidget(x=0, y=0, width=9999, height=1)
        assert w.width == 1000

    def test_height_clamped_to_maximum(self) -> None:
        w = DummyWidget(x=0, y=0, width=1, height=9999)
        assert w.height == 1000

    def test_negative_width_clamped(self) -> None:
        w = DummyWidget(x=0, y=0, width=-5, height=1)
        assert w.width == 1

    def test_negative_height_clamped(self) -> None:
        w = DummyWidget(x=0, y=0, width=1, height=-5)
        assert w.height == 1


# ---------------------------------------------------------------------------
# Type validation
# ---------------------------------------------------------------------------


class TestWidgetTypeValidation:
    """Type checking on constructor arguments."""

    def test_x_rejects_float(self) -> None:
        with pytest.raises(TypeError, match="x must be an int"):
            DummyWidget(x=1.5)  # type: ignore[arg-type]

    def test_y_rejects_float(self) -> None:
        with pytest.raises(TypeError, match="y must be an int"):
            DummyWidget(y=1.5)  # type: ignore[arg-type]

    def test_width_rejects_float(self) -> None:
        with pytest.raises(TypeError, match="width must be an int"):
            DummyWidget(width=1.5)  # type: ignore[arg-type]

    def test_height_rejects_float(self) -> None:
        with pytest.raises(TypeError, match="height must be an int"):
            DummyWidget(height=1.5)  # type: ignore[arg-type]

    def test_x_rejects_bool(self) -> None:
        with pytest.raises(TypeError, match="x must be an int"):
            DummyWidget(x=True)  # type: ignore[arg-type]

    def test_y_rejects_bool(self) -> None:
        with pytest.raises(TypeError, match="y must be an int"):
            DummyWidget(y=False)  # type: ignore[arg-type]

    def test_width_rejects_string(self) -> None:
        with pytest.raises(TypeError, match="width must be an int"):
            DummyWidget(width="5")  # type: ignore[arg-type]

    def test_height_rejects_none(self) -> None:
        with pytest.raises(TypeError, match="height must be an int"):
            DummyWidget(height=None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Position setters
# ---------------------------------------------------------------------------


class TestWidgetPosition:
    """Position property setters."""

    def test_set_x(self) -> None:
        w = DummyWidget()
        w.x = 42
        assert w.x == 42

    def test_set_y(self) -> None:
        w = DummyWidget()
        w.y = 42
        assert w.y == 42

    def test_set_negative_x(self) -> None:
        w = DummyWidget()
        w.x = -10
        assert w.x == -10

    def test_set_x_rejects_float(self) -> None:
        w = DummyWidget()
        with pytest.raises(TypeError, match="x must be an int"):
            w.x = 1.5  # type: ignore[assignment]

    def test_set_y_rejects_bool(self) -> None:
        w = DummyWidget()
        with pytest.raises(TypeError, match="y must be an int"):
            w.y = True  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Size setters
# ---------------------------------------------------------------------------


class TestWidgetSize:
    """Size property setters with clamping."""

    def test_set_width(self) -> None:
        w = DummyWidget()
        w.width = 20
        assert w.width == 20

    def test_set_height(self) -> None:
        w = DummyWidget()
        w.height = 15
        assert w.height == 15

    def test_set_width_clamps_to_min(self) -> None:
        w = DummyWidget()
        w.width = 0
        assert w.width == 1

    def test_set_height_clamps_to_min(self) -> None:
        w = DummyWidget()
        w.height = -3
        assert w.height == 1

    def test_set_width_clamps_to_max(self) -> None:
        w = DummyWidget()
        w.width = 5000
        assert w.width == 1000

    def test_set_width_rejects_float(self) -> None:
        w = DummyWidget()
        with pytest.raises(TypeError, match="width must be an int"):
            w.width = 10.0  # type: ignore[assignment]

    def test_set_height_rejects_string(self) -> None:
        w = DummyWidget()
        with pytest.raises(TypeError, match="height must be an int"):
            w.height = "10"  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Visibility
# ---------------------------------------------------------------------------


class TestWidgetVisibility:
    """Visibility toggling."""

    def test_set_visible_false(self) -> None:
        w = DummyWidget()
        w.visible = False
        assert w.visible is False

    def test_set_visible_true(self) -> None:
        w = DummyWidget()
        w.visible = False
        w.visible = True
        assert w.visible is True

    def test_visible_coerces_to_bool(self) -> None:
        w = DummyWidget()
        w.visible = 0  # type: ignore[assignment]
        assert w.visible is False
        w.visible = 1  # type: ignore[assignment]
        assert w.visible is True

    def test_label_skips_draw_when_invisible(self) -> None:
        buf = CellBuffer(20, 5)
        label = LabelWidget("Hello", x=0, y=0)
        label.visible = False
        label.draw(buf)
        # Buffer should remain blank — label didn't draw
        cell = buf.get(0, 0)
        assert cell is not None
        assert cell.char == " "


# ---------------------------------------------------------------------------
# Focus
# ---------------------------------------------------------------------------


class TestWidgetFocus:
    """Focus state and lifecycle hooks."""

    def test_set_focused_triggers_on_focus(self) -> None:
        w = FocusTracker()
        w.focused = True
        assert w.focus_count == 1
        assert w.blur_count == 0

    def test_set_unfocused_triggers_on_blur(self) -> None:
        w = FocusTracker()
        w.focused = True
        w.focused = False
        assert w.focus_count == 1
        assert w.blur_count == 1

    def test_setting_focused_true_twice_no_duplicate(self) -> None:
        """on_focus is not called when already focused."""
        w = FocusTracker()
        w.focused = True
        w.focused = True
        assert w.focus_count == 1

    def test_setting_focused_false_twice_no_duplicate(self) -> None:
        """on_blur is not called when already unfocused."""
        w = FocusTracker()
        w.focused = False  # Already False
        assert w.blur_count == 0

    def test_default_on_focus_does_nothing(self) -> None:
        """Base Widget.on_focus is a no-op."""
        w = DummyWidget()
        w.focused = True  # Should not raise

    def test_default_on_blur_does_nothing(self) -> None:
        """Base Widget.on_blur is a no-op."""
        w = DummyWidget()
        w.focused = True
        w.focused = False  # Should not raise


# ---------------------------------------------------------------------------
# Event handling
# ---------------------------------------------------------------------------


class TestWidgetEvents:
    """Event handling via handle_event."""

    def test_default_returns_false(self) -> None:
        w = DummyWidget()
        e = Event()
        assert w.handle_event(e) is False

    def test_consumer_returns_true(self) -> None:
        w = EventConsumer(consume=True)
        e = Event()
        assert w.handle_event(e) is True

    def test_non_consumer_returns_false(self) -> None:
        w = EventConsumer(consume=False)
        e = Event()
        assert w.handle_event(e) is False

    def test_event_is_recorded(self) -> None:
        w = EventConsumer()
        e = Event()
        w.handle_event(e)
        assert w.events_received == [e]

    def test_multiple_events(self) -> None:
        w = EventConsumer()
        e1 = Event()
        e2 = Event()
        w.handle_event(e1)
        w.handle_event(e2)
        assert len(w.events_received) == 2


# ---------------------------------------------------------------------------
# Drawing
# ---------------------------------------------------------------------------


class TestWidgetDraw:
    """Drawing into a CellBuffer."""

    def test_draw_is_called(self) -> None:
        buf = CellBuffer(10, 5)
        w = DummyWidget()
        w.draw(buf)
        assert w.draw_count == 1

    def test_label_draws_text(self) -> None:
        buf = CellBuffer(20, 5)
        label = LabelWidget("Hi", x=3, y=1)
        label.draw(buf)
        cell_h = buf.get(3, 1)
        cell_i = buf.get(4, 1)
        assert cell_h is not None and cell_h.char == "H"
        assert cell_i is not None and cell_i.char == "i"

    def test_draw_clips_silently(self) -> None:
        """Drawing outside buffer bounds does not raise."""
        buf = CellBuffer(5, 5)
        label = LabelWidget("Hello World", x=0, y=0)
        label.draw(buf)  # "World" extends beyond buffer — should not raise

    def test_draw_at_negative_position(self) -> None:
        """Drawing at negative position clips silently."""
        buf = CellBuffer(10, 5)
        label = LabelWidget("Hello", x=-3, y=0)
        label.draw(buf)  # First 3 chars clipped, "lo" visible
        cell = buf.get(0, 0)
        assert cell is not None
        assert cell.char == "l"


# ---------------------------------------------------------------------------
# Parent/child hierarchy
# ---------------------------------------------------------------------------


class TestWidgetHierarchy:
    """Parent/child widget relationships."""

    def test_add_child_sets_parent(self) -> None:
        parent = DummyWidget()
        child = DummyWidget()
        parent.add_child(child)
        assert child.parent is parent

    def test_add_child_appears_in_children(self) -> None:
        parent = DummyWidget()
        child = DummyWidget()
        parent.add_child(child)
        assert child in parent.children

    def test_remove_child_clears_parent(self) -> None:
        parent = DummyWidget()
        child = DummyWidget()
        parent.add_child(child)
        parent.remove_child(child)
        assert child.parent is None

    def test_remove_child_removes_from_list(self) -> None:
        parent = DummyWidget()
        child = DummyWidget()
        parent.add_child(child)
        parent.remove_child(child)
        assert child not in parent.children

    def test_remove_unknown_child_raises(self) -> None:
        parent = DummyWidget()
        child = DummyWidget()
        with pytest.raises(ValueError, match="is not a child"):
            parent.remove_child(child)

    def test_add_child_reparents(self) -> None:
        """Adding a child that already has a parent re-parents it."""
        parent1 = DummyWidget()
        parent2 = DummyWidget()
        child = DummyWidget()
        parent1.add_child(child)
        parent2.add_child(child)
        assert child.parent is parent2
        assert child not in parent1.children
        assert child in parent2.children

    def test_add_self_as_child_raises(self) -> None:
        w = DummyWidget()
        with pytest.raises(ValueError, match="cannot be its own child"):
            w.add_child(w)

    def test_add_non_widget_raises(self) -> None:
        w = DummyWidget()
        with pytest.raises(TypeError, match="child must be a Widget"):
            w.add_child("not a widget")  # type: ignore[arg-type]

    def test_multiple_children(self) -> None:
        parent = DummyWidget()
        c1 = DummyWidget()
        c2 = DummyWidget()
        c3 = DummyWidget()
        parent.add_child(c1)
        parent.add_child(c2)
        parent.add_child(c3)
        assert len(parent.children) == 3

    def test_children_returns_copy(self) -> None:
        """Modifying the returned list does not affect internal state."""
        parent = DummyWidget()
        child = DummyWidget()
        parent.add_child(child)
        children_copy = parent.children
        children_copy.clear()
        assert len(parent.children) == 1


# ---------------------------------------------------------------------------
# Bounds checking
# ---------------------------------------------------------------------------


class TestWidgetBounds:
    """Point-in-widget bounds checking."""

    def test_point_inside(self) -> None:
        w = DummyWidget(x=10, y=20, width=5, height=3)
        assert w.contains_point(12, 21) is True

    def test_point_at_top_left_corner(self) -> None:
        w = DummyWidget(x=10, y=20, width=5, height=3)
        assert w.contains_point(10, 20) is True

    def test_point_at_bottom_right_edge_exclusive(self) -> None:
        """Bottom-right corner is exclusive (standard half-open interval)."""
        w = DummyWidget(x=10, y=20, width=5, height=3)
        assert w.contains_point(15, 23) is False

    def test_point_just_inside_bottom_right(self) -> None:
        w = DummyWidget(x=10, y=20, width=5, height=3)
        assert w.contains_point(14, 22) is True

    def test_point_outside_left(self) -> None:
        w = DummyWidget(x=10, y=20, width=5, height=3)
        assert w.contains_point(9, 21) is False

    def test_point_outside_above(self) -> None:
        w = DummyWidget(x=10, y=20, width=5, height=3)
        assert w.contains_point(12, 19) is False

    def test_point_outside_right(self) -> None:
        w = DummyWidget(x=10, y=20, width=5, height=3)
        assert w.contains_point(15, 21) is False

    def test_point_outside_below(self) -> None:
        w = DummyWidget(x=10, y=20, width=5, height=3)
        assert w.contains_point(12, 23) is False


# ---------------------------------------------------------------------------
# Repr
# ---------------------------------------------------------------------------


class TestWidgetRepr:
    """String representation."""

    def test_repr_basic(self) -> None:
        w = DummyWidget(x=1, y=2, width=10, height=5)
        assert repr(w) == "DummyWidget(x=1, y=2, w=10, h=5)"

    def test_repr_invisible(self) -> None:
        w = DummyWidget(x=0, y=0, width=5, height=3)
        w.visible = False
        assert "visible=False" in repr(w)

    def test_repr_focused(self) -> None:
        w = DummyWidget(x=0, y=0, width=5, height=3)
        w.focused = True
        assert "focused" in repr(w)

    def test_repr_subclass_name(self) -> None:
        w = LabelWidget("test")
        assert repr(w).startswith("LabelWidget(")


# ---------------------------------------------------------------------------
# Abstract class enforcement
# ---------------------------------------------------------------------------


class TestWidgetAbstract:
    """Widget cannot be instantiated directly."""

    def test_cannot_instantiate_base(self) -> None:
        with pytest.raises(TypeError):
            Widget()  # type: ignore[abstract]

    def test_must_implement_draw(self) -> None:
        """Subclass without draw() cannot be instantiated."""

        class Incomplete(Widget):
            pass

        with pytest.raises(TypeError):
            Incomplete()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# Slots
# ---------------------------------------------------------------------------


class TestWidgetSlots:
    """Widget uses __slots__ for memory efficiency."""

    def test_base_widget_uses_slots(self) -> None:
        assert "__slots__" in Widget.__dict__

    def test_slots_include_expected_attrs(self) -> None:
        expected = {"_x", "_y", "_width", "_height",
                    "_visible", "_focused", "_parent", "_children",
                    "_z_index"}
        assert expected == set(Widget.__slots__)

    def test_subclass_can_add_dict(self) -> None:
        """Subclasses without __slots__ get a __dict__."""
        w = DummyWidget()
        assert hasattr(w, "__dict__")


# ---------------------------------------------------------------------------
# Import from package root
# ---------------------------------------------------------------------------


class TestWidgetImport:
    """Widget is accessible from the wyby package root."""

    def test_import_from_wyby(self) -> None:
        from wyby import Widget as W
        assert W is Widget
