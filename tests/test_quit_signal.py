"""Tests for wyby.app.QuitSignal — clean quit signal mechanism."""

from __future__ import annotations

import logging

import pytest

from wyby.app import Engine, QuitSignal


# ---------------------------------------------------------------------------
# QuitSignal basics
# ---------------------------------------------------------------------------


class TestQuitSignalIsException:
    """QuitSignal should be a standard Exception subclass."""

    def test_is_exception_subclass(self) -> None:
        assert issubclass(QuitSignal, Exception)

    def test_is_not_base_exception_direct(self) -> None:
        """QuitSignal inherits via Exception, not directly from BaseException."""
        assert QuitSignal.__bases__ == (Exception,)

    def test_can_be_raised_and_caught(self) -> None:
        with pytest.raises(QuitSignal):
            raise QuitSignal()

    def test_accepts_message(self) -> None:
        exc = QuitSignal("player quit")
        assert str(exc) == "player quit"

    def test_accepts_no_message(self) -> None:
        exc = QuitSignal()
        assert str(exc) == ""


# ---------------------------------------------------------------------------
# QuitSignal import
# ---------------------------------------------------------------------------


class TestQuitSignalImport:
    """QuitSignal should be importable from the top-level wyby package."""

    def test_importable_from_wyby(self) -> None:
        from wyby import QuitSignal as QSFromInit

        assert QSFromInit is QuitSignal

    def test_in_all(self) -> None:
        import wyby

        assert "QuitSignal" in wyby.__all__


# ---------------------------------------------------------------------------
# Engine catches QuitSignal (loop=True)
# ---------------------------------------------------------------------------


class TestEngineQuitSignalLoop:
    """QuitSignal raised during a tick should cleanly stop the loop."""

    def test_quit_signal_stops_loop(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        engine = Engine()
        call_count = 0

        def raise_on_second(self_: Engine) -> None:
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                raise QuitSignal("done")

        monkeypatch.setattr(Engine, "_tick", raise_on_second)
        # Should not raise — QuitSignal is caught internally.
        engine.run(loop=True)
        assert engine.running is False
        assert call_count == 2

    def test_quit_signal_logs_message(
        self,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        engine = Engine()

        def raise_quit(self_: Engine) -> None:
            raise QuitSignal()

        monkeypatch.setattr(Engine, "_tick", raise_quit)
        with caplog.at_level(logging.DEBUG, logger="wyby.app"):
            engine.run(loop=True)
        messages = [r.message for r in caplog.records]
        assert any("QuitSignal" in m for m in messages)

    def test_quit_signal_sets_running_false(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        engine = Engine()

        def raise_quit(self_: Engine) -> None:
            raise QuitSignal()

        monkeypatch.setattr(Engine, "_tick", raise_quit)
        engine.run(loop=True)
        assert engine.running is False


# ---------------------------------------------------------------------------
# Engine catches QuitSignal (loop=False, single tick)
# ---------------------------------------------------------------------------


class TestEngineQuitSignalSingleTick:
    """QuitSignal in single-tick mode should also be caught cleanly."""

    def test_quit_signal_in_single_tick(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        engine = Engine()

        def raise_quit(self_: Engine) -> None:
            raise QuitSignal("quit from single tick")

        monkeypatch.setattr(Engine, "_tick", raise_quit)
        # Should not raise.
        engine.run(loop=False)
        assert engine.running is False


# ---------------------------------------------------------------------------
# QuitSignal with message preserved
# ---------------------------------------------------------------------------


class TestQuitSignalMessage:
    """The engine should handle QuitSignal regardless of message content."""

    def test_quit_with_empty_message(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        engine = Engine()

        def raise_quit(self_: Engine) -> None:
            raise QuitSignal()

        monkeypatch.setattr(Engine, "_tick", raise_quit)
        engine.run(loop=False)
        assert engine.running is False

    def test_quit_with_custom_message(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        engine = Engine()

        def raise_quit(self_: Engine) -> None:
            raise QuitSignal("player pressed escape")

        monkeypatch.setattr(Engine, "_tick", raise_quit)
        engine.run(loop=True)
        assert engine.running is False


# ---------------------------------------------------------------------------
# QuitSignal does not interfere with KeyboardInterrupt
# ---------------------------------------------------------------------------


class TestQuitSignalAndKeyboardInterrupt:
    """QuitSignal and KeyboardInterrupt should both work independently."""

    def test_keyboard_interrupt_still_works(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """KeyboardInterrupt should still be caught after QuitSignal exists."""
        engine = Engine()

        def raise_interrupt(self_: Engine) -> None:
            raise KeyboardInterrupt

        monkeypatch.setattr(Engine, "_tick", raise_interrupt)
        engine.run(loop=True)
        assert engine.running is False

    def test_quit_signal_not_caught_by_broad_except(self) -> None:
        """QuitSignal should be catchable with 'except Exception'."""
        caught = False
        try:
            raise QuitSignal("test")
        except Exception:
            caught = True
        assert caught
