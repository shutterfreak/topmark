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
layer of TopMark, including registry construction, file-type resolution, TOML/template
document handling, and higher-level orchestration code.

Each exception carries structured [`ErrorContext`][topmark.core.errors.ErrorContext]
metadata so callers can inspect machine-useful details such as the affected
path, qualified key, encoding, or additional diagnostic information.

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
        qualified_key: Optional qualified key associated with the failure.
        encoding: Optional encoding name relevant to the failure.
        details: Optional tuple of additional diagnostic details.
    """

    message: str
    path: Path | None = None
    qualified_key: str | None = None
    encoding: str | None = None
    details: tuple[str, ...] = ()


class TopmarkError(Exception):
    """Base class for Click-free TopMark exceptions.

    Args:
        context: Structured context describing the failure.
    """

    def __init__(
        self,
        context: ErrorContext,
    ) -> None:
        super().__init__(context.message)
        self.context: Final[ErrorContext] = context

    def __str__(self) -> str:
        """Return the human-readable message for display purposes.

        Returns:
            The message stored in the attached `ErrorContext`.
        """
        return self.context.message


# ---- Common registry lookup errors ----


class ReservedNamespaceError(TopmarkError):
    """Raised when a reserved namespace is used by an ineligible registry entry.

    This is intended for registry composition and registration APIs where the
    ``topmark`` namespace is reserved for built-in entities and must not be
    claimed by external overlays, plugins, or test fixtures unless they are
    defined from within the TopMark package.

    Args:
        namespace: Reserved namespace that was used.
        owner: Human-readable owner label for the offending entry.
        entities: Registry entity category involved in the violation.
        owner_module: Optional module path where the offending entry is defined.
    """

    def __init__(
        self,
        *,
        namespace: str,
        owner: str,
        entities: str,
        owner_module: str | None = None,
    ) -> None:
        details: list[str] = [
            f"namespace={namespace}",
            f"owner={owner}",
            f"entities={entities}",
        ]
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


# ---- File-type / registry lookup errors ----


class UnsupportedFileTypeError(TopmarkError):
    """Raised when a file type is recognized but currently unsupported.

    This distinguishes "unknown file type" from "known file type with no usable
    processor", which can be useful for diagnostics, reporting, and fallback
    handling.

    Args:
        file_type: Recognized file type identifier that is currently unsupported.
        path: Optional filesystem path associated with the lookup.
    """

    def __init__(
        self,
        *,
        file_type: str,
        path: Path | None = None,
    ) -> None:
        msg: str = (
            f"Unsupported file type: {file_type}"
            if path is None
            else f"Unsupported file type for {path}: {file_type}"
        )
        super().__init__(
            ErrorContext(
                message=msg,
                path=path,
                qualified_key=file_type,
            )
        )
        self.file_type: Final[str] = file_type


class UnknownFileTypeError(TopmarkError):
    """Raised when a file type identifier cannot be resolved from a registry.

    This error is typically raised by public registry helpers when a caller
    references a file type identifier that is not present in the effective file
    type view.

    Args:
        file_type: File type identifier that could not be resolved.
        path: Optional filesystem path associated with the lookup.
    """

    def __init__(
        self,
        *,
        file_type: str,
        path: Path | None = None,
    ) -> None:
        msg: str = (
            f"Unknown file type identifier: {file_type}"
            if path is None
            else f"Unknown file type identifier for {path}: {file_type}"
        )
        super().__init__(
            ErrorContext(
                message=msg,
                path=path,
                qualified_key=file_type,
            )
        )
        self.file_type: Final[str] = file_type


class AmbiguousFileTypeIdentifierError(TopmarkError):
    """Raised when an unqualified file type identifier resolves ambiguously.

    This error is intended for lookup helpers that accept either unqualified or
    qualified file type identifiers. Callers can recover by retrying with an
    explicit qualified identifier of the form ``"<namespace>:<name>"``.

    Args:
        file_type: Unqualified file type identifier supplied by the caller.
        candidates: Candidate qualified keys that matched the identifier.
    """

    def __init__(
        self,
        *,
        file_type: str,
        candidates: tuple[str, ...],
    ) -> None:
        message: str = (
            f"Ambiguous file type identifier: {file_type} (candidates: {', '.join(candidates)})"
        )
        super().__init__(
            ErrorContext(
                message=message,
                qualified_key=file_type,
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
                qualified_key=identifier or local_key,
                details=tuple(details),
            )
        )
        self.identifier: Final[str | None] = identifier
        self.namespace: Final[str | None] = namespace
        self.local_key: Final[str | None] = local_key


# ---- Processor registration / binding errors ----


class ProcessorBindingError(TopmarkError):
    """Raised when explicit processor bindings are invalid or inconsistent.

    This signals a registry-construction or registry-mutation invariant
    failure, such as an unknown bound file type identifier, an unknown
    processor qualified key, or a duplicate binding declaration.

    Args:
        message: Human-readable error message.
        file_type: Optional file type qualified key associated with the failed
            binding operation.
    """

    def __init__(
        self,
        *,
        message: str,
        file_type: str | None = None,
    ) -> None:
        super().__init__(
            ErrorContext(
                message=message,
                qualified_key=file_type,
            )
        )
        self.file_type: Final[str | None] = file_type


class ProcessorRegistrationError(TopmarkError):
    """Base class for processor-registration failures.

    Args:
        message: Human-readable error message.
        qualified_key: Processor qualified key associated with the failed registration.
    """

    def __init__(
        self,
        *,
        message: str,
        qualified_key: str,
    ) -> None:
        super().__init__(
            ErrorContext(
                message=message,
                qualified_key=qualified_key,
            )
        )
        self.qualified_key: Final[str] = qualified_key


class DuplicateProcessorRegistrationError(ProcessorRegistrationError):
    """Raised when a processor qualified key is already registered.

    This condition may be recoverable depending on caller policy, for example by
    unregistering or replacing the existing entry before retrying.

    Args:
        qualified_key: Processor qualified key that is already present in the
            effective registry.
    """

    def __init__(
        self,
        *,
        qualified_key: str,
    ) -> None:
        super().__init__(
            message=f"Processor '{qualified_key}' is already registered.",
            qualified_key=qualified_key,
        )


class DuplicateProcessorKeyError(TopmarkError):
    """Raised when multiple processor classes claim the same qualified key.

    This signals an internal or overlay-composition invariant failure: the same
    qualified processor identity must not resolve to different processor classes
    in the effective processor registry.

    Args:
        qualified_key: Conflicting processor qualified key.
        existing_class: Human-readable label for the already-associated class.
        new_class: Human-readable label for the newly encountered class.
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
                qualified_key=qualified_key,
                details=(
                    f"existing_class={existing_class}",
                    f"new_class={new_class}",
                ),
            )
        )
        self.qualified_key: Final[str] = qualified_key
        self.existing_class: Final[str] = existing_class
        self.new_class: Final[str] = new_class


# ---- Policy / reporting boundary errors ----


class InvalidPolicyError(TopmarkError):
    """Raised when a supplied policy value is invalid or malformed.

    This is intended for API-facing policy overlays and other policy parsing
    boundaries where invalid scalar values should be rejected explicitly.

    Args:
        message: Human-readable error message.
        policy_key: Optional policy key associated with the invalid value.
    """

    def __init__(
        self,
        *,
        message: str,
        policy_key: str | None = None,
    ) -> None:
        super().__init__(
            ErrorContext(
                message=message,
                qualified_key=policy_key,
            )
        )
        self.policy_key: Final[str | None] = policy_key


class InvalidReportScopeError(TopmarkError):
    """Raised when a supplied report-scope value is invalid or malformed.

    This is intended for API-facing reporting/view boundaries where invalid
    scalar values should be rejected explicitly.

    Args:
        message: Human-readable error message.
        report_value: Optional invalid public report-scope token.
    """

    def __init__(
        self,
        *,
        message: str,
        report_value: str | None = None,
    ) -> None:
        super().__init__(
            ErrorContext(
                message=message,
                qualified_key=report_value,
            )
        )
        self.report_value: Final[str | None] = report_value


# ---- TOML document errors ----


class TomlDocumentError(TopmarkError):
    """Base class for TOML document parsing, rendering, and surgery errors.

    This groups TOML-specific failures that arise while parsing, rendering, or
    structurally rewriting TOML documents.

    Args:
        message: Human-readable error message.
        details: Optional structured diagnostic details.
    """

    def __init__(
        self,
        *,
        message: str,
        details: tuple[str, ...] = (),
    ) -> None:
        super().__init__(
            ErrorContext(
                message=message,
                details=details,
            )
        )


class TomlRenderError(TomlDocumentError):
    """Raised when TOML rendering fails due to invalid inputs or invariants."""


class TomlParseError(TomlDocumentError):
    """Raised when a TOML document cannot be parsed."""


class TomlSurgeryError(TomlDocumentError):
    """Raised when structural TOML editing fails or required TOML shape invariants are violated."""


# ---- Template-specific document errors ----


class TemplateError(TomlDocumentError):
    """Base class for annotated config-template editing and validation errors.

    Template errors are narrower than generic TOML document errors: they refer
    specifically to the annotated configuration template and the presentation-
    preserving helpers that edit or validate it.
    """


class TemplateEditError(TemplateError):
    """Raised when annotated config-template editing fails."""


class TemplateValidationError(TemplateError):
    """Raised when an annotated config-template result fails validation."""
