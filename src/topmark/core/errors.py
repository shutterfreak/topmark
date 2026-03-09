# topmark:header:start
#
#   project      : TopMark
#   file         : errors.py
#   file_relpath : src/topmark/core/errors.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Core TopMark exceptions.

This module defines Click-free exception types that may be raised from any
layer of TopMark, including registry construction, file-type resolution, I/O,
and higher-level orchestration code.

Each exception carries structured [`ErrorContext`][topmark.core.errors.ErrorContext]
metadata so callers can inspect machine-useful details such as the affected
path, file type, encoding, or additional diagnostic information.

CLI commands should catch these core exceptions and translate them into
user-facing CLI errors with appropriate exit codes.

Design goals:
    - No Click dependency.
    - Structured context via `ErrorContext`.
    - Clear distinction between internal invariant failures and plausibly
      recoverable runtime errors.
    - Preserve the underlying cause via exception chaining (`raise ... from exc`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from typing import Final

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True, slots=True)
class ErrorContext:
    """Structured context attached to a core TopMark error.

    Attributes:
        message: Human-readable error message, without CLI styling.
        path: Optional filesystem path associated with the failure.
        file_type: Optional file type name associated with the failure.
        encoding: Optional encoding name relevant to the failure.
        details: Optional tuple of additional diagnostic details.
    """

    message: str
    path: Path | None = None
    file_type: str | None = None
    encoding: str | None = None
    details: tuple[str, ...] = ()


class TopmarkError(Exception):
    """Base class for Click-free TopMark exceptions.

    Args:
        context: Structured context describing the failure.
    """

    def __init__(self, context: ErrorContext) -> None:
        super().__init__(context.message)
        self.context: Final[ErrorContext] = context

    def __str__(self) -> str:
        """Return the human-readable message for display purposes."""
        return self.context.message


class UnknownFileTypeError(TopmarkError):
    """Raised when a file type name cannot be resolved from a registry.

    This error is typically raised by public registry helpers when a caller
    references a file type name that is not present in the effective file type
    view.
    """

    def __init__(self, *, file_type: str, path: Path | None = None) -> None:
        msg: str = (
            f"Unknown file type: {file_type}"
            if path is None
            else f"Unknown file type for {path}: {file_type}"
        )
        super().__init__(ErrorContext(message=msg, path=path, file_type=file_type))
        self.file_type: Final[str] = file_type


class ProcessorBindingError(TopmarkError):
    """Raised when explicit processor bindings are invalid or inconsistent.

    This signals an internal registry-construction invariant failure, such as an
    unknown bound file type name or duplicate binding declaration. Callers would
    normally treat this as a programming or packaging error rather than attempt
    recovery.
    """

    def __init__(self, *, message: str, file_type: str | None = None) -> None:
        super().__init__(ErrorContext(message=message, file_type=file_type))
        self.file_type: Final[str | None] = file_type


class ProcessorRegistrationError(TopmarkError):
    """Base class for processor-registration failures.

    Args:
        message: Human-readable error message.
        file_type: File type name associated with the failed registration.
    """

    def __init__(self, *, message: str, file_type: str) -> None:
        super().__init__(ErrorContext(message=message, file_type=file_type))
        self.file_type: Final[str] = file_type


class DuplicateProcessorRegistrationError(ProcessorRegistrationError):
    """Raised when a processor is already registered for a given file type.

    This condition may be recoverable depending on caller policy, for example by
    unregistering or replacing the existing overlay entry before retrying.
    """

    def __init__(self, *, file_type: str) -> None:
        super().__init__(
            message=f"File type '{file_type}' already has a registered processor.",
            file_type=file_type,
        )


class UnsupportedFileTypeError(TopmarkError):
    """Raised when a file type is recognized but currently unsupported.

    This distinguishes “unknown file type” from “known file type with no usable
    processor”, which can be useful for diagnostics, reporting, and fallback
    handling.
    """

    def __init__(self, *, file_type: str, path: Path | None = None) -> None:
        msg: str = (
            f"Unsupported file type: {file_type}"
            if path is None
            else f"Unsupported file type for {path}: {file_type}"
        )
        super().__init__(ErrorContext(message=msg, path=path, file_type=file_type))
        self.file_type: Final[str] = file_type
