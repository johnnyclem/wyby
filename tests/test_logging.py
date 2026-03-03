"""Tests for wyby._logging — NullHandler setup and configure_logging()."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from wyby._logging import (
    _DEFAULT_FORMAT,
    _LIBRARY_LOGGER_NAME,
    configure_logging,
    setup_null_handler,
)


@pytest.fixture(autouse=True)
def _restore_wyby_logger():
    """Save and restore the wyby logger's handlers and level around every test.

    configure_logging() mutates the shared wyby logger. Without cleanup,
    state leaks between tests and into other test modules (e.g. the
    project_init tests that rely on the logger having no explicit level).
    """
    logger = logging.getLogger(_LIBRARY_LOGGER_NAME)
    original_handlers = logger.handlers[:]
    original_level = logger.level
    yield
    logger.handlers[:] = original_handlers
    logger.setLevel(original_level)


# ---------------------------------------------------------------------------
# setup_null_handler
# ---------------------------------------------------------------------------


class TestSetupNullHandler:
    """Tests for setup_null_handler()."""

    def test_adds_null_handler_to_wyby_logger(self) -> None:
        logger = logging.getLogger(_LIBRARY_LOGGER_NAME)
        logger.handlers.clear()
        setup_null_handler()
        null_handlers = [
            h for h in logger.handlers if isinstance(h, logging.NullHandler)
        ]
        assert len(null_handlers) >= 1

    def test_null_handler_present_after_import(self) -> None:
        """Importing wyby should attach a NullHandler automatically."""
        logger = logging.getLogger(_LIBRARY_LOGGER_NAME)
        null_handlers = [
            h for h in logger.handlers if isinstance(h, logging.NullHandler)
        ]
        assert len(null_handlers) >= 1


# ---------------------------------------------------------------------------
# configure_logging — stderr (default)
# ---------------------------------------------------------------------------


class TestConfigureLoggingStderr:
    """Tests for configure_logging() with default stderr output."""

    def test_returns_wyby_logger(self) -> None:
        logger = logging.getLogger(_LIBRARY_LOGGER_NAME)
        result = configure_logging()
        assert result is logger

    def test_sets_level_with_int(self) -> None:
        logger = logging.getLogger(_LIBRARY_LOGGER_NAME)
        configure_logging(level=logging.DEBUG)
        assert logger.level == logging.DEBUG

    def test_sets_level_with_string(self) -> None:
        logger = logging.getLogger(_LIBRARY_LOGGER_NAME)
        configure_logging(level="INFO")
        assert logger.level == logging.INFO

    def test_string_level_is_case_insensitive(self) -> None:
        logger = logging.getLogger(_LIBRARY_LOGGER_NAME)
        configure_logging(level="debug")
        assert logger.level == logging.DEBUG

    def test_default_level_is_warning(self) -> None:
        logger = logging.getLogger(_LIBRARY_LOGGER_NAME)
        configure_logging()
        assert logger.level == logging.WARNING

    def test_adds_stream_handler_to_stderr(self) -> None:
        logger = logging.getLogger(_LIBRARY_LOGGER_NAME)
        configure_logging()
        stream_handlers = [
            h
            for h in logger.handlers
            if isinstance(h, logging.StreamHandler)
            and not isinstance(h, logging.FileHandler)
            and not isinstance(h, logging.NullHandler)
        ]
        assert len(stream_handlers) >= 1
        import sys

        assert stream_handlers[-1].stream is sys.stderr

    def test_handler_uses_provided_format(self) -> None:
        logger = logging.getLogger(_LIBRARY_LOGGER_NAME)
        custom_fmt = "%(levelname)s: %(message)s"
        configure_logging(fmt=custom_fmt)
        last_handler = logger.handlers[-1]
        assert last_handler.formatter._fmt == custom_fmt

    def test_default_format_string(self) -> None:
        assert "%(asctime)s" in _DEFAULT_FORMAT
        assert "%(name)s" in _DEFAULT_FORMAT
        assert "%(levelname)s" in _DEFAULT_FORMAT
        assert "%(message)s" in _DEFAULT_FORMAT

    def test_emits_messages_at_configured_level(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """After configure_logging(DEBUG), debug messages should appear."""
        logger = logging.getLogger(_LIBRARY_LOGGER_NAME)
        configure_logging(level=logging.DEBUG)
        with caplog.at_level(logging.DEBUG, logger=_LIBRARY_LOGGER_NAME):
            logger.debug("test debug message")
        assert any("test debug message" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# configure_logging — file output
# ---------------------------------------------------------------------------


class TestConfigureLoggingFile:
    """Tests for configure_logging() with file output."""

    def test_creates_file_handler(self, tmp_path: Path) -> None:
        log_file = tmp_path / "game.log"
        logger = logging.getLogger(_LIBRARY_LOGGER_NAME)
        configure_logging(level=logging.DEBUG, filename=log_file)
        file_handlers = [
            h for h in logger.handlers if isinstance(h, logging.FileHandler)
        ]
        assert len(file_handlers) >= 1

    def test_writes_to_file(self, tmp_path: Path) -> None:
        log_file = tmp_path / "game.log"
        logger = logging.getLogger(_LIBRARY_LOGGER_NAME)
        configure_logging(level=logging.INFO, filename=log_file)
        logger.info("hello from test")
        for h in logger.handlers:
            h.flush()
        content = log_file.read_text(encoding="utf-8")
        assert "hello from test" in content

    def test_appends_by_default(self, tmp_path: Path) -> None:
        log_file = tmp_path / "game.log"
        log_file.write_text("existing line\n", encoding="utf-8")
        logger = logging.getLogger(_LIBRARY_LOGGER_NAME)
        configure_logging(level=logging.INFO, filename=log_file)
        logger.info("new line")
        for h in logger.handlers:
            h.flush()
        content = log_file.read_text(encoding="utf-8")
        assert "existing line" in content
        assert "new line" in content

    def test_overwrite_mode(self, tmp_path: Path) -> None:
        log_file = tmp_path / "game.log"
        log_file.write_text("old content\n", encoding="utf-8")
        logger = logging.getLogger(_LIBRARY_LOGGER_NAME)
        configure_logging(
            level=logging.INFO, filename=log_file, filemode="w"
        )
        logger.info("fresh start")
        for h in logger.handlers:
            h.flush()
        content = log_file.read_text(encoding="utf-8")
        assert "old content" not in content
        assert "fresh start" in content

    def test_accepts_path_object(self, tmp_path: Path) -> None:
        log_file = tmp_path / "game.log"
        logger = logging.getLogger(_LIBRARY_LOGGER_NAME)
        configure_logging(level=logging.INFO, filename=Path(log_file))
        logger.info("path object works")
        for h in logger.handlers:
            h.flush()
        content = log_file.read_text(encoding="utf-8")
        assert "path object works" in content


# ---------------------------------------------------------------------------
# configure_logging — child logger propagation
# ---------------------------------------------------------------------------


class TestChildLoggerPropagation:
    """Verify that child loggers (e.g. wyby.project_init) propagate correctly."""

    def test_child_logger_messages_propagate(self, tmp_path: Path) -> None:
        log_file = tmp_path / "game.log"
        parent = logging.getLogger(_LIBRARY_LOGGER_NAME)
        configure_logging(level=logging.DEBUG, filename=log_file)
        child = logging.getLogger(f"{_LIBRARY_LOGGER_NAME}.some_module")
        child.debug("child says hello")
        for h in parent.handlers:
            h.flush()
        content = log_file.read_text(encoding="utf-8")
        assert "child says hello" in content
