"""Tests for wyby.renderer — Rich Console and Live display integration."""

from __future__ import annotations

import io

import pytest
from rich.console import Console
from rich.text import Text

from wyby.renderer import LiveDisplay, Renderer, create_console


# ---------------------------------------------------------------------------
# create_console
# ---------------------------------------------------------------------------


class TestCreateConsole:
    """Tests for the create_console() factory function."""

    def test_returns_console_instance(self) -> None:
        console = create_console(file=io.StringIO(), force_terminal=True)
        assert isinstance(console, Console)

    def test_default_creates_without_error(self) -> None:
        # Use force_terminal=False to avoid TTY issues in CI.
        console = create_console(force_terminal=False)
        assert isinstance(console, Console)

    def test_custom_width(self) -> None:
        console = create_console(
            file=io.StringIO(), force_terminal=True, width=120
        )
        assert console.width == 120

    def test_custom_height(self) -> None:
        console = create_console(
            file=io.StringIO(), force_terminal=True, height=40
        )
        assert console.height == 40

    def test_custom_width_and_height(self) -> None:
        console = create_console(
            file=io.StringIO(), force_terminal=True, width=60, height=20
        )
        assert console.width == 60
        assert console.height == 20

    def test_force_terminal_true(self) -> None:
        console = create_console(file=io.StringIO(), force_terminal=True)
        assert console.is_terminal is True

    def test_force_terminal_false(self) -> None:
        console = create_console(file=io.StringIO(), force_terminal=False)
        assert console.is_terminal is False

    def test_color_system_none_disables_color(self) -> None:
        console = create_console(
            file=io.StringIO(), force_terminal=True, color_system=None
        )
        assert console.color_system is None

    def test_color_system_truecolor(self) -> None:
        console = create_console(
            file=io.StringIO(), force_terminal=True, color_system="truecolor"
        )
        assert console.color_system == "truecolor"

    def test_highlight_disabled(self) -> None:
        """Integers should not get syntax-highlighted escape codes."""
        buf = io.StringIO()
        console = create_console(
            file=buf, force_terminal=True, color_system="truecolor"
        )
        console.print(42)
        output = buf.getvalue().strip()
        # If highlighting were enabled, "42" would be wrapped in
        # ANSI bold/color codes (containing \033).  With highlighting
        # disabled, the output is just "42".
        assert output == "42"

    def test_markup_disabled(self) -> None:
        """Console should not interpret Rich markup in game text."""
        buf = io.StringIO()
        console = create_console(
            file=buf, force_terminal=True, color_system=None
        )
        console.print("[red]hello[/red]")
        output = buf.getvalue()
        # With markup=False and no color, brackets are literal text.
        assert "[red]" in output

    def test_custom_file(self) -> None:
        buf = io.StringIO()
        console = create_console(file=buf, force_terminal=True)
        console.print("test output", highlight=False)
        assert "test output" in buf.getvalue()


# ---------------------------------------------------------------------------
# LiveDisplay — construction
# ---------------------------------------------------------------------------


class TestLiveDisplayInit:
    """Tests for LiveDisplay construction."""

    def test_default_console_created(self) -> None:
        """When no console is provided, one is created automatically."""
        display = LiveDisplay()
        assert isinstance(display.console, Console)

    def test_custom_console(self) -> None:
        console = Console(file=io.StringIO(), force_terminal=True)
        display = LiveDisplay(console=console)
        assert display.console is console

    def test_not_started_initially(self) -> None:
        display = LiveDisplay(
            console=Console(file=io.StringIO(), force_terminal=True)
        )
        assert display.is_started is False

    def test_rejects_non_console_string(self) -> None:
        with pytest.raises(TypeError, match="rich.console.Console"):
            LiveDisplay(console="not a console")  # type: ignore[arg-type]

    def test_rejects_non_console_int(self) -> None:
        with pytest.raises(TypeError, match="rich.console.Console"):
            LiveDisplay(console=42)  # type: ignore[arg-type]

    def test_accepts_none_explicitly(self) -> None:
        display = LiveDisplay(console=None)
        assert isinstance(display.console, Console)


# ---------------------------------------------------------------------------
# LiveDisplay — lifecycle
# ---------------------------------------------------------------------------


class TestLiveDisplayLifecycle:
    """Tests for LiveDisplay start/stop lifecycle."""

    @staticmethod
    def _make_display() -> LiveDisplay:
        """Create a LiveDisplay with a StringIO console for testing."""
        console = Console(file=io.StringIO(), force_terminal=True)
        return LiveDisplay(console=console)

    def test_start_sets_is_started(self) -> None:
        display = self._make_display()
        display.start()
        try:
            assert display.is_started is True
        finally:
            display.stop()

    def test_stop_clears_is_started(self) -> None:
        display = self._make_display()
        display.start()
        display.stop()
        assert display.is_started is False

    def test_double_start_is_noop(self) -> None:
        """Calling start() twice should not raise or create a second Live."""
        display = self._make_display()
        display.start()
        try:
            display.start()  # Should be a no-op
            assert display.is_started is True
        finally:
            display.stop()

    def test_stop_without_start_is_noop(self) -> None:
        display = self._make_display()
        display.stop()  # Should not raise
        assert display.is_started is False

    def test_double_stop_is_noop(self) -> None:
        display = self._make_display()
        display.start()
        display.stop()
        display.stop()  # Should not raise
        assert display.is_started is False

    def test_restart_after_stop(self) -> None:
        """A stopped display can be started again."""
        display = self._make_display()
        display.start()
        display.stop()
        display.start()
        try:
            assert display.is_started is True
        finally:
            display.stop()


# ---------------------------------------------------------------------------
# LiveDisplay — context manager
# ---------------------------------------------------------------------------


class TestLiveDisplayContextManager:
    """Tests for LiveDisplay as a context manager."""

    @staticmethod
    def _make_display() -> LiveDisplay:
        console = Console(file=io.StringIO(), force_terminal=True)
        return LiveDisplay(console=console)

    def test_starts_on_enter(self) -> None:
        display = self._make_display()
        with display:
            assert display.is_started is True

    def test_stops_on_exit(self) -> None:
        display = self._make_display()
        with display:
            pass
        assert display.is_started is False

    def test_stops_on_exception(self) -> None:
        display = self._make_display()
        with pytest.raises(ValueError, match="test"):
            with display:
                assert display.is_started is True
                raise ValueError("test")
        assert display.is_started is False

    def test_returns_self(self) -> None:
        display = self._make_display()
        with display as ctx:
            assert ctx is display


# ---------------------------------------------------------------------------
# LiveDisplay — update
# ---------------------------------------------------------------------------


class TestLiveDisplayUpdate:
    """Tests for LiveDisplay.update()."""

    @staticmethod
    def _make_display() -> LiveDisplay:
        console = Console(file=io.StringIO(), force_terminal=True)
        return LiveDisplay(console=console)

    def test_update_with_text(self) -> None:
        display = self._make_display()
        with display:
            display.update(Text("hello world"))

    def test_update_with_string(self) -> None:
        display = self._make_display()
        with display:
            display.update("hello world")

    def test_update_when_not_started_is_noop(self) -> None:
        """update() before start() should silently do nothing."""
        display = self._make_display()
        display.update(Text("hello"))  # Should not raise

    def test_update_after_stop_is_noop(self) -> None:
        display = self._make_display()
        display.start()
        display.stop()
        display.update(Text("hello"))  # Should not raise

    def test_multiple_updates(self) -> None:
        """Successive updates should replace the displayed content."""
        display = self._make_display()
        with display:
            for i in range(10):
                display.update(Text(f"Frame {i}"))


# ---------------------------------------------------------------------------
# LiveDisplay — repr
# ---------------------------------------------------------------------------


class TestLiveDisplayRepr:
    """Tests for LiveDisplay.__repr__."""

    def test_repr_when_not_started(self) -> None:
        console = Console(file=io.StringIO(), force_terminal=True)
        display = LiveDisplay(console=console)
        r = repr(display)
        assert "started=False" in r
        assert "LiveDisplay" in r

    def test_repr_when_started(self) -> None:
        console = Console(file=io.StringIO(), force_terminal=True)
        display = LiveDisplay(console=console)
        display.start()
        try:
            r = repr(display)
            assert "started=True" in r
        finally:
            display.stop()


# ---------------------------------------------------------------------------
# Engine integration
# ---------------------------------------------------------------------------


class TestEngineConsoleIntegration:
    """Tests for Engine's Console and LiveDisplay integration."""

    def test_engine_has_console_property(self) -> None:
        from wyby.app import Engine

        engine = Engine()
        assert isinstance(engine.console, Console)

    def test_engine_has_live_display_property(self) -> None:
        from wyby.app import Engine

        engine = Engine()
        assert isinstance(engine.live_display, LiveDisplay)

    def test_engine_custom_console(self) -> None:
        from wyby.app import Engine

        console = Console(file=io.StringIO(), force_terminal=True)
        engine = Engine(console=console)
        assert engine.console is console
        assert engine.live_display.console is console

    def test_engine_live_display_not_started_before_run(self) -> None:
        from wyby.app import Engine

        engine = Engine()
        assert engine.live_display.is_started is False

    def test_shutdown_stops_live_display(self) -> None:
        """Engine._shutdown() should stop the LiveDisplay if it was started."""
        from wyby.app import Engine

        console = Console(file=io.StringIO(), force_terminal=True)
        engine = Engine(console=console)
        engine.live_display.start()
        assert engine.live_display.is_started is True
        engine._shutdown()
        assert engine.live_display.is_started is False

    def test_shutdown_safe_when_display_not_started(self) -> None:
        """Engine._shutdown() should not raise if display was never started."""
        from wyby.app import Engine

        console = Console(file=io.StringIO(), force_terminal=True)
        engine = Engine(console=console)
        engine._shutdown()  # Should not raise

    def test_engine_rejects_non_console(self) -> None:
        """Passing a non-Console object should raise TypeError."""
        from wyby.app import Engine

        with pytest.raises(TypeError, match="rich.console.Console"):
            Engine(console="bad")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Renderer — construction
# ---------------------------------------------------------------------------


class TestRendererInit:
    """Tests for Renderer construction."""

    def test_default_console_created(self) -> None:
        """When no console is provided, one is created automatically."""
        renderer = Renderer()
        assert isinstance(renderer.console, Console)

    def test_custom_console(self) -> None:
        console = Console(file=io.StringIO(), force_terminal=True)
        renderer = Renderer(console=console)
        assert renderer.console is console

    def test_not_started_initially(self) -> None:
        renderer = Renderer(
            console=Console(file=io.StringIO(), force_terminal=True)
        )
        assert renderer.is_started is False

    def test_frame_count_zero_initially(self) -> None:
        renderer = Renderer(
            console=Console(file=io.StringIO(), force_terminal=True)
        )
        assert renderer.frame_count == 0

    def test_rejects_non_console_string(self) -> None:
        with pytest.raises(TypeError, match="rich.console.Console"):
            Renderer(console="not a console")  # type: ignore[arg-type]

    def test_rejects_non_console_int(self) -> None:
        with pytest.raises(TypeError, match="rich.console.Console"):
            Renderer(console=42)  # type: ignore[arg-type]

    def test_accepts_none_explicitly(self) -> None:
        renderer = Renderer(console=None)
        assert isinstance(renderer.console, Console)

    def test_has_live_display(self) -> None:
        renderer = Renderer(
            console=Console(file=io.StringIO(), force_terminal=True)
        )
        assert isinstance(renderer.live_display, LiveDisplay)

    def test_live_display_shares_console(self) -> None:
        console = Console(file=io.StringIO(), force_terminal=True)
        renderer = Renderer(console=console)
        assert renderer.live_display.console is console


# ---------------------------------------------------------------------------
# Renderer — lifecycle
# ---------------------------------------------------------------------------


class TestRendererLifecycle:
    """Tests for Renderer start/stop lifecycle."""

    @staticmethod
    def _make_renderer() -> Renderer:
        console = Console(file=io.StringIO(), force_terminal=True)
        return Renderer(console=console)

    def test_start_sets_is_started(self) -> None:
        renderer = self._make_renderer()
        renderer.start()
        try:
            assert renderer.is_started is True
        finally:
            renderer.stop()

    def test_stop_clears_is_started(self) -> None:
        renderer = self._make_renderer()
        renderer.start()
        renderer.stop()
        assert renderer.is_started is False

    def test_double_start_is_noop(self) -> None:
        """Calling start() twice should not raise or reset frame count."""
        renderer = self._make_renderer()
        renderer.start()
        try:
            renderer.present(Text("frame"))
            assert renderer.frame_count == 1
            renderer.start()  # Should be a no-op
            assert renderer.is_started is True
            # Frame count should NOT be reset by a redundant start().
            assert renderer.frame_count == 1
        finally:
            renderer.stop()

    def test_stop_without_start_is_noop(self) -> None:
        renderer = self._make_renderer()
        renderer.stop()  # Should not raise
        assert renderer.is_started is False

    def test_double_stop_is_noop(self) -> None:
        renderer = self._make_renderer()
        renderer.start()
        renderer.stop()
        renderer.stop()  # Should not raise
        assert renderer.is_started is False

    def test_restart_after_stop(self) -> None:
        """A stopped renderer can be started again."""
        renderer = self._make_renderer()
        renderer.start()
        renderer.stop()
        renderer.start()
        try:
            assert renderer.is_started is True
        finally:
            renderer.stop()

    def test_start_resets_frame_count(self) -> None:
        """Starting a fresh cycle resets the frame counter."""
        renderer = self._make_renderer()
        renderer.start()
        renderer.present(Text("frame 1"))
        renderer.present(Text("frame 2"))
        assert renderer.frame_count == 2
        renderer.stop()
        renderer.start()
        try:
            assert renderer.frame_count == 0
        finally:
            renderer.stop()


# ---------------------------------------------------------------------------
# Renderer — context manager
# ---------------------------------------------------------------------------


class TestRendererContextManager:
    """Tests for Renderer as a context manager."""

    @staticmethod
    def _make_renderer() -> Renderer:
        console = Console(file=io.StringIO(), force_terminal=True)
        return Renderer(console=console)

    def test_starts_on_enter(self) -> None:
        renderer = self._make_renderer()
        with renderer:
            assert renderer.is_started is True

    def test_stops_on_exit(self) -> None:
        renderer = self._make_renderer()
        with renderer:
            pass
        assert renderer.is_started is False

    def test_stops_on_exception(self) -> None:
        renderer = self._make_renderer()
        with pytest.raises(ValueError, match="test"):
            with renderer:
                assert renderer.is_started is True
                raise ValueError("test")
        assert renderer.is_started is False

    def test_returns_self(self) -> None:
        renderer = self._make_renderer()
        with renderer as ctx:
            assert ctx is renderer


# ---------------------------------------------------------------------------
# Renderer — present
# ---------------------------------------------------------------------------


class TestRendererPresent:
    """Tests for Renderer.present()."""

    @staticmethod
    def _make_renderer() -> Renderer:
        console = Console(file=io.StringIO(), force_terminal=True)
        return Renderer(console=console)

    def test_present_with_text(self) -> None:
        renderer = self._make_renderer()
        with renderer:
            renderer.present(Text("hello world"))

    def test_present_with_string(self) -> None:
        renderer = self._make_renderer()
        with renderer:
            renderer.present("hello world")

    def test_present_increments_frame_count(self) -> None:
        renderer = self._make_renderer()
        with renderer:
            assert renderer.frame_count == 0
            renderer.present(Text("frame 1"))
            assert renderer.frame_count == 1
            renderer.present(Text("frame 2"))
            assert renderer.frame_count == 2

    def test_present_when_not_started_is_noop(self) -> None:
        """present() before start() should silently do nothing."""
        renderer = self._make_renderer()
        renderer.present(Text("hello"))  # Should not raise
        assert renderer.frame_count == 0

    def test_present_after_stop_is_noop(self) -> None:
        renderer = self._make_renderer()
        renderer.start()
        renderer.stop()
        renderer.present(Text("hello"))  # Should not raise
        assert renderer.frame_count == 0

    def test_present_does_not_increment_when_stopped(self) -> None:
        """Frame count should not increase for no-op presents."""
        renderer = self._make_renderer()
        renderer.present(Text("a"))
        renderer.present(Text("b"))
        assert renderer.frame_count == 0

    def test_multiple_presents(self) -> None:
        """Successive presents should replace the displayed content."""
        renderer = self._make_renderer()
        with renderer:
            for i in range(10):
                renderer.present(Text(f"Frame {i}"))
            assert renderer.frame_count == 10


# ---------------------------------------------------------------------------
# Renderer — repr
# ---------------------------------------------------------------------------


class TestRendererRepr:
    """Tests for Renderer.__repr__."""

    def test_repr_when_not_started(self) -> None:
        console = Console(file=io.StringIO(), force_terminal=True)
        renderer = Renderer(console=console)
        r = repr(renderer)
        assert "started=False" in r
        assert "Renderer" in r
        assert "frame_count=0" in r

    def test_repr_when_started(self) -> None:
        console = Console(file=io.StringIO(), force_terminal=True)
        renderer = Renderer(console=console)
        renderer.start()
        try:
            r = repr(renderer)
            assert "started=True" in r
        finally:
            renderer.stop()

    def test_repr_shows_frame_count(self) -> None:
        console = Console(file=io.StringIO(), force_terminal=True)
        renderer = Renderer(console=console)
        renderer.start()
        try:
            renderer.present(Text("frame"))
            r = repr(renderer)
            assert "frame_count=1" in r
        finally:
            renderer.stop()


# ---------------------------------------------------------------------------
# Renderer — package export
# ---------------------------------------------------------------------------


class TestRendererExport:
    """Tests for Renderer availability in the public API."""

    def test_importable_from_wyby(self) -> None:
        from wyby import Renderer as R  # noqa: N811

        assert R is Renderer

    def test_in_all(self) -> None:
        import wyby

        assert "Renderer" in wyby.__all__
