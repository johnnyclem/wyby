"""Logging configuration for RuneTUI.

Provides a setup_logging() function that configures logging for the library.
By default, logs go to a file (runetui.log) to avoid interfering with
terminal rendering. In debug mode, log level is set to DEBUG.

Caveat: Writing logs to stderr while Rich Live is active will corrupt
the terminal display. Always use file-based logging during gameplay.
"""

from __future__ import annotations

import logging
import os


def setup_logging(
    level: int | None = None,
    log_file: str = "runetui.log",
    debug: bool = False,
) -> None:
    """Configure logging for RuneTUI.

    Args:
        level: Explicit log level. If None, uses DEBUG when debug=True, else INFO.
        log_file: Path to the log file. Set to empty string to disable file logging.
        debug: Enable debug-level logging.
    """
    resolved_level = level or (logging.DEBUG if debug else logging.INFO)

    # Override from environment
    env_level = os.environ.get("RUNETUI_LOG_LEVEL", "").upper()
    if env_level in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
        resolved_level = getattr(logging, env_level)

    root_logger = logging.getLogger("runetui")
    root_logger.setLevel(resolved_level)

    # Clear existing handlers
    root_logger.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    if log_file:
        file_handler = logging.FileHandler(log_file, mode="a")
        file_handler.setLevel(resolved_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    else:
        # Fallback to NullHandler (library convention)
        root_logger.addHandler(logging.NullHandler())
