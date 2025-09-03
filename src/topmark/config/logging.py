# topmark:header:start
#
#   file         : logging.py
#   file_relpath : src/topmark/config/logging.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Custom TopMark logging with TRACE logging.

This module extends the standard logging module with TopMark-specific features,
including a custom TRACE level, a specialized logger class, and colored output formatting.
"""

import logging
import sys
from collections.abc import Mapping
from typing import Final, cast

from yachalk import chalk

# Define TRACE_LEVEL as a module-level constant
TRACE_LEVEL: Final[int] = logging.DEBUG - 5


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


if not hasattr(logging, "TRACE"):
    logging.addLevelName(TRACE_LEVEL, "TRACE")
    # Expose TRACE_LEVEL as logging.TRACE
    logging.TRACE = TRACE_LEVEL  # type: ignore

logging.setLoggerClass(TopmarkLogger)

# You can import TopmarkLogger via:
# from topmark.logging_config import TopmarkLogger


LOG_FORMAT = "[%(levelname)s] %(message)s"
DEBUG_LOG_FORMAT = "[%(levelname)s] [%(filename)s:%(lineno)d] [%(funcName)s] %(message)s"


class ChalkFormatter(logging.Formatter):
    """Formatter that outputs log records with chalk-colored formatting based on severity level."""

    def format(self, record: logging.LogRecord) -> str:
        """Format the specified record with colors based on log level.

        Args:
            record: The LogRecord to be formatted.

        Returns:
            The colorized formatted log message as a string.
        """
        level = record.levelno
        message = super().format(record)

        result: str = ""

        # Apply color styles to the message depending on the log severity
        if level >= logging.CRITICAL:
            result = chalk.red_bright(message)
        elif level >= logging.ERROR:
            result = chalk.red(message)
        elif level >= logging.WARNING:
            result = chalk.yellow(message)
        elif level >= logging.INFO:
            result = chalk.green(message)
        elif level >= logging.DEBUG:
            result = chalk.gray(message)
        elif level >= TRACE_LEVEL:  # Handle TRACE level specifically
            result = chalk.blue(message)
        else:
            # Fallback color for unknown or lower-than-TRACE levels
            result = chalk.dim.red(message)

        return result


def setup_logging(level: int = logging.INFO) -> None:
    """Configure the root logger with a specified log level and colored output.

    This function sets the root logger's level, clears existing handlers to avoid duplicate logs,
    adds a StreamHandler with colored formatting, and disables propagation to parent loggers.

    Args:
        level: The logging level to set for the root logger (default is logging.INFO).
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove all existing handlers to prevent duplicate log messages
    if root_logger.handlers:
        for handler in root_logger.handlers[
            :
        ]:  # Iterate over a copy since we're modifying the list
            root_logger.removeHandler(handler)

    # Create and add a StreamHandler explicitly outputting to sys.stdout
    handler = logging.StreamHandler(sys.stdout)
    # Use detailed logging format for info and above levels, simpler otherwise
    formatter = ChalkFormatter(LOG_FORMAT if level >= logging.INFO else DEBUG_LOG_FORMAT)
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
    logger = logging.getLogger(name)
    return cast("TopmarkLogger", logger)
