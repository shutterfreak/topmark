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
    """Raised when a file type identifier cannot be resolved from a registry.

    This error is typically raised by public registry helpers when a caller
    references a file type identifier that is not present in the effective file
    type view.
    """

    def __init__(self, *, file_type: str, path: Path | None = None) -> None:
        msg: str = (
            f"Unknown file type identifier: {file_type}"
            if path is None
            else f"Unknown file type identifier for {path}: {file_type}"
        )
        super().__init__(ErrorContext(message=msg, path=path, file_type=file_type))
        self.file_type: Final[str] = file_type


class AmbiguousFileTypeIdentifierError(TopmarkError):
    """Raised when an unqualified file type identifier resolves ambiguously.

    This error is intended for lookup helpers that accept either unqualified or
    qualified file type identifiers. Callers can recover by retrying with an
    explicit qualified identifier of the form ``"<namespace>:<name>"``.
    """

    def __init__(self, *, file_type: str, candidates: tuple[str, ...]) -> None:
        message: str = (
            f"Ambiguous file type identifier: {file_type} (candidates: {', '.join(candidates)})"
        )
        super().__init__(
            ErrorContext(
                message=message,
                file_type=file_type,
                details=tuple(f"candidate={candidate}" for candidate in candidates),
            )
        )
        self.file_type: Final[str] = file_type
        self.candidates: Final[tuple[str, ...]] = candidates


class InvalidRegistryIdentityError(TopmarkError):
    """Raised when a registry identifier or identity pair is malformed.

    This error is intended for public registry APIs that accept identifiers such
    as ``"<local_key>"`` or ``"<namespace>:<local_key>"`` and need to reject
    malformed input explicitly rather than treating it as merely unknown.

    Args:
        message: Human-readable error message, without CLI styling.
        identifier: Optional raw identifier string supplied by the caller.
        namespace: Optional namespace component when available.
        local_key: Optional namespace-local identifier when available.
    """

    def __init__(
        self,
        *,
        message: str,
        identifier: str | None = None,
        namespace: str | None = None,
        local_key: str | None = None,
    ) -> None:
        details: list[str] = []
        if identifier is not None:
            details.append(f"identifier={identifier}")
        if namespace is not None:
            details.append(f"namespace={namespace}")
        if local_key is not None:
            details.append(f"local_key={local_key}")

        super().__init__(
            ErrorContext(
                message=message,
                file_type=identifier or local_key,
                details=tuple(details),
            )
        )
        self.identifier: Final[str | None] = identifier
        self.namespace: Final[str | None] = namespace
        self.local_key: Final[str | None] = local_key


class ReservedNamespaceError(TopmarkError):
    """Raised when a reserved namespace is used by an ineligible registry entry.

    This is intended for registry composition / registration APIs where the
    `topmark` namespace is reserved for built-in entities and must not be
    claimed by external overlays, plugins, or test fixtures unless they are
    defined from within the TopMark package.
    """

    def __init__(
        self,
        *,
        namespace: str,
        owner: str,
        entities: str,
        owner_module: str | None = None,
    ) -> None:
        details: list[str] = [f"namespace={namespace}", f"owner={owner}", f"entities={entities}"]
        if owner_module is not None:
            details.append(f"owner_module={owner_module}")

        message: str = (
            f"Reserved namespace violation: '{namespace}' is reserved for built-in "
            f"TopMark {entities} (owner: {owner})"
        )
        super().__init__(
            ErrorContext(
                message=message,
                details=tuple(details),
            )
        )
        self.namespace: Final[str] = namespace
        self.owner: Final[str] = owner
        self.entities: Final[str] = entities
        self.owner_module: Final[str | None] = owner_module


class ProcessorBindingError(TopmarkError):
    """Raised when explicit processor bindings are invalid or inconsistent.

    This signals an internal registry-construction invariant failure, such as an
    unknown bound file type identifier or duplicate binding declaration. Callers would
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


class DuplicateProcessorKeyError(TopmarkError):
    """Raised when multiple processor classes claim the same qualified key.

    This signals an internal or overlay-composition invariant failure: the same
    qualified processor identity must not resolve to different processor classes
    in the effective processor registry.
    """

    def __init__(
        self,
        *,
        qualified_key: str,
        existing_class: str,
        new_class: str,
    ) -> None:
        message: str = (
            "Duplicate processor key detected: "
            f"{qualified_key} (classes: {existing_class} vs {new_class})"
        )
        super().__init__(
            ErrorContext(
                message=message,
                details=(
                    f"qualified_key={qualified_key}",
                    f"existing_class={existing_class}",
                    f"new_class={new_class}",
                ),
            )
        )
        self.qualified_key: Final[str] = qualified_key
        self.existing_class: Final[str] = existing_class
        self.new_class: Final[str] = new_class


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
