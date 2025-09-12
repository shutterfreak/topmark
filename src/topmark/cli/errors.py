# topmark:header:start
#
#   project      : TopMark
#   file         : errors.py
#   file_relpath : src/topmark/cli/errors.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Exceptions for TopMark CLI.

Usage:
    Raise these exceptions in CLI commands or processing to signal errors
    with standardized messages and exit codes.

Styling:
    Exceptions prefer the project console if available (see `show()`); if no console
    is present in the Click context, they fall back to Click's default styling.
"""

from __future__ import annotations

from typing import IO, Any

import click

from topmark.cli_shared.exit_codes import ExitCode


class TopmarkError(click.ClickException):
    """Base class for all TopMark CLI errors."""

    exit_code = ExitCode.FAILURE

    def format_message(self) -> str:  # pragma: no cover - trivial
        """Return the plain error message text.

        Notes:
            - Unlike Click’s default, this method does not add color.
            - Colorization is applied in `show()` when a project console is present.
        """
        # ``self.message`` is set by ClickException; ensure it's a string.
        msg = str(getattr(self, "message", ""))
        return msg

    def show(self, file: IO[Any] | None = None) -> None:  # pragma: no cover - Click prints errors
        """Display the error using the project console if available.

        Falls back to Click’s default error display when no console is present.
        """
        try:
            ctx = click.get_current_context(silent=True)
            if ctx is not None and isinstance(getattr(ctx, "obj", None), dict):
                console = ctx.obj.get("console")
                if console is not None:
                    # Use console for user-facing error output with bright red style
                    console.error(console.styled(self.format_message(), fg="bright_red"))
                    return
        except Exception:
            pass
        # Fallback to Click's default behavior (includes its own styling)
        super().show(file)


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
