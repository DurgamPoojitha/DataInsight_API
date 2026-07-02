"""
DataInsight API — Structured Logger
=====================================
Provides a pre-configured logging setup for the entire application.

Design decisions:
  - Uses Python's built-in `logging` module (no third-party dep).
  - Applies a structured, single-line format for log aggregator ingestion.
  - Reads the log level from the LOG_LEVEL environment variable.
  - Module-level `get_logger()` factory returns a StructuredLogger wrapper.

Python 3.14 Compatibility:
  `logging.makeRecord()` in Python 3.14 raises KeyError when extra={} keys
  shadow any built-in LogRecord attribute ('filename', 'lineno', 'module',
  'name', 'pathname', etc.).  This module works around the issue by using a
  thin StructuredLogger wrapper that appends structured fields directly to
  the message string — avoiding `extra={}` entirely.

Usage:
    from app.utils.logger import get_logger
    logger = get_logger(__name__)
    logger.info("File uploaded", file_name="data.csv", rows=1024)
"""

import logging
import os
import sys


# ---------------------------------------------------------------------------
# Log-level configuration (reads from environment, defaults to INFO)
# ---------------------------------------------------------------------------

_LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
_VALID_LEVELS: set[str] = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}

if _LOG_LEVEL not in _VALID_LEVELS:
    _LOG_LEVEL = "INFO"


# ---------------------------------------------------------------------------
# Formatter
# ---------------------------------------------------------------------------

class _StructuredFormatter(logging.Formatter):
    """
    Single-line structured log formatter.

    Example output:
        [2024-01-15 10:23:45,123] INFO     datainsight.services.dataset | File uploaded
    """

    FMT: str = "[%(asctime)s] %(levelname)-8s %(name)s | %(message)s"

    def format(self, record: logging.LogRecord) -> str:  # noqa: A003
        self._style._fmt = self.FMT
        return super().format(record)


# ---------------------------------------------------------------------------
# Root logger setup (called once at import time)
# ---------------------------------------------------------------------------

def _configure_root_logger() -> None:
    """
    Configure the root 'datainsight' logger with a StreamHandler that writes
    to stdout. No-op if the handler has already been added.
    """
    root_logger = logging.getLogger("datainsight")

    if root_logger.handlers:
        return

    root_logger.setLevel(getattr(logging, _LOG_LEVEL, logging.INFO))

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(getattr(logging, _LOG_LEVEL, logging.INFO))
    handler.setFormatter(_StructuredFormatter())

    root_logger.addHandler(handler)
    root_logger.propagate = False


_configure_root_logger()


# ---------------------------------------------------------------------------
# StructuredLogger wrapper
# ---------------------------------------------------------------------------

class StructuredLogger:
    """
    A thin wrapper around a standard Logger that appends keyword-argument
    fields to the message string as 'key=value' pairs.

    This avoids the Python 3.14 `logging.makeRecord` KeyError that occurs
    when `extra={}` keys collide with built-in LogRecord attributes.

    Usage:
        logger = get_logger(__name__)
        logger.info("File uploaded", file_name="data.csv", rows=1024)
        # → [2024-01-15 10:23:45] INFO datainsight.app | File uploaded | file_name=data.csv rows=1024
    """

    def __init__(self, name: str) -> None:
        qualified_name = (
            name if name.startswith("datainsight") else f"datainsight.{name}"
        )
        self._logger = logging.getLogger(qualified_name)

    # ------------------------------------------------------------------
    # Internal helper
    # ------------------------------------------------------------------

    def _build_msg(self, msg: str, fields: dict) -> str:
        """Append key=value pairs to the log message."""
        if not fields:
            return msg
        pairs = " ".join(f"{k}={v}" for k, v in fields.items())
        return f"{msg} | {pairs}"

    # ------------------------------------------------------------------
    # Public logging methods (mirror logging.Logger API)
    # ------------------------------------------------------------------

    def debug(self, msg: str, **fields) -> None:
        """Log a DEBUG-level message with optional structured fields."""
        if self._logger.isEnabledFor(logging.DEBUG):
            self._logger.debug(self._build_msg(msg, fields))

    def info(self, msg: str, **fields) -> None:
        """Log an INFO-level message with optional structured fields."""
        if self._logger.isEnabledFor(logging.INFO):
            self._logger.info(self._build_msg(msg, fields))

    def warning(self, msg: str, **fields) -> None:
        """Log a WARNING-level message with optional structured fields."""
        if self._logger.isEnabledFor(logging.WARNING):
            self._logger.warning(self._build_msg(msg, fields))

    def error(self, msg: str, **fields) -> None:
        """Log an ERROR-level message with optional structured fields."""
        if self._logger.isEnabledFor(logging.ERROR):
            self._logger.error(self._build_msg(msg, fields))

    def exception(self, msg: str, exc_info: BaseException | None = None, **fields) -> None:
        """Log an ERROR with exception traceback."""
        self._logger.exception(self._build_msg(msg, fields), exc_info=exc_info)

    def critical(self, msg: str, **fields) -> None:
        """Log a CRITICAL-level message with optional structured fields."""
        if self._logger.isEnabledFor(logging.CRITICAL):
            self._logger.critical(self._build_msg(msg, fields))


# ---------------------------------------------------------------------------
# Public factory function
# ---------------------------------------------------------------------------

def get_logger(name: str) -> StructuredLogger:
    """
    Return a StructuredLogger for the given module name.

    Args:
        name: Typically `__name__` of the calling module.

    Returns:
        A StructuredLogger instance that appends kwargs as key=value fields.

    Example:
        logger = get_logger(__name__)
        logger.info("Dataset saved", dataset_id="abc", rows=500)
    """
    return StructuredLogger(name)
