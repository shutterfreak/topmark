# topmark:header:start
#
#   project      : TopMark
#   file         : logging.py
#   file_relpath : src/topmark/core/logging.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Custom TopMark logging with TRACE logging.

This module extends Python's standard logging with TopMark-specific features, including a custom
`TRACE` level (below `DEBUG`) and a specialized logger class.

Logging output is intentionally plain text (no ANSI styling). Presentation and color concerns belong
in the CLI layer.
"""

from __future__ import annotations

import logging
import os
import sys
from typing import TYPE_CHECKING
from typing import Final
from typing import cast

if TYPE_CHECKING:
    from collections.abc import Mapping

# Define TRACE_LEVEL as a module-level constant
TRACE_LEVEL: Final[int] = logging.DEBUG - 5
if not hasattr(logging, "TRACE"):
    logging.addLevelName(TRACE_LEVEL, "TRACE")
    logging.TRACE = TRACE_LEVEL  # type: ignore[attr-defined]


class TopmarkLogger(logging.Logger):
    """Custom logger class for TopMark with support for a TRACE log level below DEBUG."""

    def trace(
        self,
        msg: object,
        *args: object,
        extra: Mapping[str, object] | None = None,
    ) -> None:
        """Log 'msg % args' with severity 'TRACE'.

        This method logs a message with the custom TRACE level, which is lower than DEBUG.

        Args:
            msg: The message to be logged.
            *args: Variable length argument list for the message.
            extra: Optional dictionary of extra information to pass to the logger.
        """
        if self.isEnabledFor(TRACE_LEVEL):
            self._log(
                TRACE_LEVEL,
                msg=msg,
                args=args,
                extra=extra,
                stacklevel=2,
            )


logging.setLoggerClass(TopmarkLogger)


_LOG_FORMAT = "[%(levelname)s] %(message)s"
_DEBUG_LOG_FORMAT = "[%(levelname)s] [%(filename)s:%(lineno)d] [%(funcName)s] %(message)s"


class TopmarkFormatter(logging.Formatter):
    """Plain-text formatter for TopMark logs."""


def resolve_env_log_level() -> int | None:
    """Return a logging level from environment or None if unset.

    Honors TOPMARK_LOG_LEVEL (e.g., "TRACE", "DEBUG", "INFO", numeric "10").
    """
    val: str | None = os.environ.get("TOPMARK_LOG_LEVEL")
    if val:
        v: str = val.strip().upper()
        if v.isdigit():
            try:
                return int(v)
            except ValueError:
                return None
        name_to_level: dict[str, int] = {
            "TRACE": TRACE_LEVEL,
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "WARN": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL,
            "FATAL": logging.CRITICAL,
            "NOTSET": logging.NOTSET,
        }
        return name_to_level.get(v)
    return None


def setup_logging(level: int | None = None) -> None:
    """Configure the root logger with a specified log level (and plain-text output).

    If ``level`` is None, environment variables are consulted via
    [`resolve_env_log_level`][topmark.core.logging.resolve_env_log_level].
    Default is CRITICAL when unspecified.
    """
    if level is None:
        level = resolve_env_log_level() or logging.CRITICAL

    root_logger: logging.Logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove all existing handlers to prevent duplicate log messages
    handler: logging.Handler
    if root_logger.handlers:
        for handler in root_logger.handlers[
            :
        ]:  # Iterate over a copy since we're modifying the list
            root_logger.removeHandler(handler)

    # Create and add a StreamHandler explicitly outputting to sys.stdout
    handler = logging.StreamHandler(sys.stdout)
    # Use detailed logging format for info and above levels, simpler otherwise
    formatter = TopmarkFormatter(_LOG_FORMAT if level >= logging.INFO else _DEBUG_LOG_FORMAT)
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    # Disable propagation to avoid duplicate logs in parent loggers
    root_logger.propagate = False


def get_logger(name: str) -> TopmarkLogger:
    """Retrieve a TopmarkLogger instance with the specified name.

    Args:
        name: The name of the logger.

    Returns:
        A TopmarkLogger instance.
    """
    logger: logging.Logger = logging.getLogger(name)
    return cast("TopmarkLogger", logger)
