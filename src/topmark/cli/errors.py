# topmark:header:start
#
#   file         : errors.py
#   file_relpath : src/topmark/cli/errors.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Exceptions for TopMark CLI.

Usage:
    Raise these exceptions in CLI commands or processing to signal errors
    with standardized messages and exit codes.

Styling:
    These exceptions use Click's styling (``click.style``) so that color
    honoring matches the user's ``--color``/``--no-color`` settings and TTY
    detection. If your own logger uses ``chalk`` elsewhere, that's fine—stick to
    Click styling for exceptions printed by Click.
"""

from __future__ import annotations

import click

from topmark.cli_shared.exit_codes import ExitCode


class TopmarkError(click.ClickException):
    """Base class for all TopMark CLI errors."""

    exit_code = ExitCode.FAILURE

    def format_message(self) -> str:  # pragma: no cover - trivial
        """Return a bright‑red styled message for Click's error output.

        Click's ``ClickException.show()`` prints ``"Error: " + format_message()``.
        We colorize only the message text here so the ``Error:`` prefix remains
        Click's default style (which may be themed by Click itself in future
        versions).
        """
        # ``self.message`` is set by ClickException; ensure it's a string.
        msg = str(getattr(self, "message", ""))
        return click.style(msg, fg="bright_red")


class TopmarkUsageError(TopmarkError):
    """Error for command-line invocation errors (invalid flags/args)."""

    exit_code = ExitCode.USAGE_ERROR


class TopmarkConfigError(TopmarkError):
    """Error for configuration errors (missing/invalid/malformed config)."""

    exit_code = ExitCode.CONFIG_ERROR


class TopmarkFileNotFoundError(TopmarkError):
    """Error when input path does not exist."""

    exit_code = ExitCode.FILE_NOT_FOUND


class TopmarkPermissionDeniedError(TopmarkError):
    """Error for insufficient permissions (read/write)."""

    exit_code = ExitCode.PERMISSION_DENIED


class TopmarkIOError(TopmarkError):
    """Error for I/O errors reading/writing files."""

    exit_code = ExitCode.IO_ERROR


class TopmarkEncodingError(TopmarkError):
    """Error for text decoding/encoding errors (e.g., UnicodeDecodeError)."""

    exit_code = ExitCode.ENCODING_ERROR


class TopmarkUnsupportedFileTypeError(TopmarkError):
    """Error for known/unsupported file types (skipped as per policy)."""

    exit_code = ExitCode.UNSUPPORTED_FILE_TYPE


class TopmarkPipelineError(TopmarkError):
    """Error for internal pipeline failures (processor/step contract violation)."""

    exit_code = ExitCode.PIPELINE_ERROR


class TopmarkUnexpectedError(TopmarkError):
    """Error for unhandled/unknown errors (last-resort)."""

    exit_code = ExitCode.UNEXPECTED_ERROR
