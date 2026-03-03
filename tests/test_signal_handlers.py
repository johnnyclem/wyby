"""Tests for wyby.signal_handlers — process-level SIGINT/SIGTERM handling.

These tests verify that the SignalHandler class correctly installs and
uninstalls signal handlers, converts signals to KeyboardInterrupt, and
supports double-interrupt for force-quit during shutdown.
"""

from __future__ import annotations

import logging
import os
import signal

import pytest

from wyby.signal_handlers import SignalHandler, _HAS_SIGTERM


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_main_thread() -> bool:
    """Check if the current thread is the main thread."""
    import threading
    return threading.current_thread() is threading.main_thread()


# ---------------------------------------------------------------------------
# SignalHandler basics
# ---------------------------------------------------------------------------


class TestSignalHandlerInit:
    """SignalHandler should initialise with clean state."""

    def test_not_installed_on_init(self) -> None:
        handler = SignalHandler()
        assert handler._installed is False

    def test_not_interrupted_on_init(self) -> None:
        handler = SignalHandler()
        assert handler.interrupted is False

    def test_repr_not_installed(self) -> None:
        handler = SignalHandler()
        assert "not installed" in repr(handler)


# ---------------------------------------------------------------------------
# Install / uninstall
# ---------------------------------------------------------------------------


class TestInstallUninstall:
    """Signal handlers should be installed and restored correctly."""

    def test_install_sets_installed(self) -> None:
        handler = SignalHandler()
        handler.install()
        try:
            assert handler._installed is True
        finally:
            handler.uninstall()

    def test_uninstall_clears_installed(self) -> None:
        handler = SignalHandler()
        handler.install()
        handler.uninstall()
        assert handler._installed is False

    def test_install_is_idempotent(self) -> None:
        handler = SignalHandler()
        handler.install()
        try:
            handler.install()  # Should not raise or change state.
            assert handler._installed is True
        finally:
            handler.uninstall()

    def test_uninstall_is_idempotent(self) -> None:
        handler = SignalHandler()
        handler.uninstall()  # Not installed — should be a no-op.
        assert handler._installed is False

    def test_restores_original_sigint_handler(self) -> None:
        original = signal.getsignal(signal.SIGINT)
        handler = SignalHandler()
        handler.install()
        handler.uninstall()
        assert signal.getsignal(signal.SIGINT) is original

    @pytest.mark.skipif(
        not _HAS_SIGTERM,
        reason="SIGTERM not supported on this platform",
    )
    def test_restores_original_sigterm_handler(self) -> None:
        original = signal.getsignal(signal.SIGTERM)
        handler = SignalHandler()
        handler.install()
        handler.uninstall()
        assert signal.getsignal(signal.SIGTERM) is original

    def test_repr_installed(self) -> None:
        handler = SignalHandler()
        handler.install()
        try:
            assert "installed" in repr(handler)
            assert "not installed" not in repr(handler)
        finally:
            handler.uninstall()


# ---------------------------------------------------------------------------
# Context manager
# ---------------------------------------------------------------------------


class TestContextManager:
    """SignalHandler should work as a context manager."""

    def test_install_on_enter(self) -> None:
        handler = SignalHandler()
        with handler:
            assert handler._installed is True

    def test_uninstall_on_exit(self) -> None:
        handler = SignalHandler()
        with handler:
            pass
        assert handler._installed is False

    def test_restores_on_exception(self) -> None:
        original = signal.getsignal(signal.SIGINT)
        handler = SignalHandler()
        with pytest.raises(RuntimeError):
            with handler:
                raise RuntimeError("test")
        assert signal.getsignal(signal.SIGINT) is original

    def test_enter_returns_self(self) -> None:
        handler = SignalHandler()
        with handler as ctx:
            assert ctx is handler


# ---------------------------------------------------------------------------
# Signal handling behaviour
# ---------------------------------------------------------------------------


class TestSignalHandling:
    """Signals should raise KeyboardInterrupt and set the interrupted flag."""

    def test_sigint_raises_keyboard_interrupt(self) -> None:
        handler = SignalHandler()
        handler.install()
        try:
            with pytest.raises(KeyboardInterrupt):
                os.kill(os.getpid(), signal.SIGINT)
        finally:
            handler.uninstall()

    def test_sigint_sets_interrupted_flag(self) -> None:
        handler = SignalHandler()
        handler.install()
        try:
            try:
                os.kill(os.getpid(), signal.SIGINT)
            except KeyboardInterrupt:
                pass
            assert handler.interrupted is True
        finally:
            handler.uninstall()

    @pytest.mark.skipif(
        not _HAS_SIGTERM,
        reason="SIGTERM not supported on this platform",
    )
    def test_sigterm_raises_keyboard_interrupt(self) -> None:
        handler = SignalHandler()
        handler.install()
        try:
            with pytest.raises(KeyboardInterrupt):
                os.kill(os.getpid(), signal.SIGTERM)
        finally:
            handler.uninstall()

    @pytest.mark.skipif(
        not _HAS_SIGTERM,
        reason="SIGTERM not supported on this platform",
    )
    def test_sigterm_sets_interrupted_flag(self) -> None:
        handler = SignalHandler()
        handler.install()
        try:
            try:
                os.kill(os.getpid(), signal.SIGTERM)
            except KeyboardInterrupt:
                pass
            assert handler.interrupted is True
        finally:
            handler.uninstall()

    def test_second_sigint_still_raises(self) -> None:
        """A second SIGINT should also raise KeyboardInterrupt."""
        handler = SignalHandler()
        handler.install()
        try:
            # First signal.
            try:
                os.kill(os.getpid(), signal.SIGINT)
            except KeyboardInterrupt:
                pass

            # Second signal — should still raise.
            with pytest.raises(KeyboardInterrupt):
                os.kill(os.getpid(), signal.SIGINT)
        finally:
            handler.uninstall()

    def test_repr_after_interrupt(self) -> None:
        handler = SignalHandler()
        handler.install()
        try:
            try:
                os.kill(os.getpid(), signal.SIGINT)
            except KeyboardInterrupt:
                pass
            assert "interrupted" in repr(handler)
        finally:
            handler.uninstall()


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------


class TestSignalHandlerLogging:
    """Signal handlers should log install/uninstall and signal receipt."""

    def test_install_logs_debug(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        handler = SignalHandler()
        with caplog.at_level(
            logging.DEBUG, logger="wyby.signal_handlers"
        ):
            handler.install()
            handler.uninstall()
        messages = [r.message for r in caplog.records]
        assert any("installed" in m.lower() for m in messages)

    def test_uninstall_logs_debug(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        handler = SignalHandler()
        with caplog.at_level(
            logging.DEBUG, logger="wyby.signal_handlers"
        ):
            handler.install()
            handler.uninstall()
        messages = [r.message for r in caplog.records]
        assert any("restored" in m.lower() for m in messages)

    def test_sigint_logs_message(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        handler = SignalHandler()
        handler.install()
        try:
            with caplog.at_level(
                logging.DEBUG, logger="wyby.signal_handlers"
            ):
                try:
                    os.kill(os.getpid(), signal.SIGINT)
                except KeyboardInterrupt:
                    pass
            messages = [r.message for r in caplog.records]
            assert any("SIGINT" in m for m in messages)
        finally:
            handler.uninstall()


# ---------------------------------------------------------------------------
# Integration with Engine
# ---------------------------------------------------------------------------


class TestEngineSignalIntegration:
    """Engine.run() should install/uninstall signal handlers."""

    def test_signal_handler_installed_during_run(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from wyby.app import Engine

        installed_during_tick = False

        def check_installed(self_: Engine) -> None:
            nonlocal installed_during_tick
            installed_during_tick = self_._signal_handler._installed
            self_.stop()

        monkeypatch.setattr(Engine, "_tick", check_installed)
        engine = Engine()
        engine.run(loop=True)
        assert installed_during_tick is True

    def test_signal_handler_uninstalled_after_run(self) -> None:
        from wyby.app import Engine

        engine = Engine()
        engine.run(loop=False)
        assert engine._signal_handler._installed is False

    def test_signal_handler_uninstalled_after_keyboard_interrupt(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from wyby.app import Engine

        def raise_interrupt(self_: Engine) -> None:
            raise KeyboardInterrupt

        monkeypatch.setattr(Engine, "_tick", raise_interrupt)
        engine = Engine()
        engine.run(loop=True)
        assert engine._signal_handler._installed is False

    def test_signal_handler_uninstalled_after_exception(self) -> None:
        from wyby.app import Engine
        from wyby.scene import Scene

        class CrashScene(Scene):
            def update(self, dt: float) -> None:
                raise ValueError("boom")
            def render(self) -> None:
                pass

        engine = Engine()
        engine.scenes.push(CrashScene())
        with pytest.raises(ValueError):
            engine.run(loop=False)
        assert engine._signal_handler._installed is False


# ---------------------------------------------------------------------------
# Engine shutdown resilience
# ---------------------------------------------------------------------------


class TestShutdownResilience:
    """Engine._shutdown() should survive a second KeyboardInterrupt."""

    def test_shutdown_completes_despite_interrupt_during_exit_hook(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """If Ctrl+C arrives during scene teardown, terminal cleanup
        should still run."""
        from wyby.app import Engine
        from wyby.scene import Scene

        input_manager_stopped = False

        class SlowExitScene(Scene):
            def update(self, dt: float) -> None:
                pass
            def render(self) -> None:
                pass
            def on_exit(self) -> None:
                raise KeyboardInterrupt

        class FakeInputManager:
            """Minimal mock that tracks stop() calls."""
            is_started = True
            def start(self) -> None:
                pass
            def stop(self) -> None:
                nonlocal input_manager_stopped
                input_manager_stopped = True

        engine = Engine()
        engine.scenes.push(SlowExitScene())
        # Inject the mock directly.
        engine._input_manager = FakeInputManager()  # type: ignore[assignment]

        def stop_immediately(self_: Engine) -> None:
            self_.stop()

        monkeypatch.setattr(Engine, "_tick", stop_immediately)
        engine.run(loop=True)

        # Terminal restoration should have run despite the interrupt.
        assert input_manager_stopped is True
        assert engine.scenes.is_empty

    def test_shutdown_clears_remaining_scenes_on_interrupt(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Second Ctrl+C should clear remaining scenes without hanging."""
        from wyby.app import Engine
        from wyby.scene import Scene

        class InterruptOnExitScene(Scene):
            def update(self, dt: float) -> None:
                pass
            def render(self) -> None:
                pass
            def on_exit(self) -> None:
                raise KeyboardInterrupt

        class NormalScene(Scene):
            def __init__(self) -> None:
                super().__init__()
                self.exit_called = False
            def update(self, dt: float) -> None:
                pass
            def render(self) -> None:
                pass
            def on_exit(self) -> None:
                self.exit_called = True

        engine = Engine()
        bottom = NormalScene()
        engine.scenes.push(bottom)
        engine.scenes.push(InterruptOnExitScene())  # top — interrupts

        def stop_immediately(self_: Engine) -> None:
            self_.stop()

        monkeypatch.setattr(Engine, "_tick", stop_immediately)
        engine.run(loop=True)

        assert engine.scenes.is_empty
        # Bottom scene's exit hook was NOT called because the interrupt
        # during the top scene's exit caused remaining hooks to be skipped.
        assert bottom.exit_called is False


# ---------------------------------------------------------------------------
# SIGTERM integration (Unix only)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not _HAS_SIGTERM,
    reason="SIGTERM not supported on this platform",
)
class TestSIGTERMIntegration:
    """SIGTERM should trigger graceful engine shutdown."""

    def test_sigterm_stops_engine(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from wyby.app import Engine
        from wyby.scene import Scene

        class TrackingScene(Scene):
            def __init__(self) -> None:
                super().__init__()
                self.exited = False
            def update(self, dt: float) -> None:
                pass
            def render(self) -> None:
                pass
            def on_exit(self) -> None:
                self.exited = True

        engine = Engine()
        scene = TrackingScene()
        engine.scenes.push(scene)

        tick_count = 0

        def tick_then_sigterm(self_: Engine) -> None:
            nonlocal tick_count
            tick_count += 1
            if tick_count >= 2:
                os.kill(os.getpid(), signal.SIGTERM)

        monkeypatch.setattr(Engine, "_tick", tick_then_sigterm)
        engine.run(loop=True)

        assert engine.running is False
        assert scene.exited is True


# ---------------------------------------------------------------------------
# Import and public API
# ---------------------------------------------------------------------------


class TestSignalHandlerImport:
    """SignalHandler should be importable from the top-level package."""

    def test_importable_from_wyby(self) -> None:
        from wyby import SignalHandler as SHFromInit
        assert SHFromInit is SignalHandler

    def test_in_all(self) -> None:
        import wyby
        assert "SignalHandler" in wyby.__all__
