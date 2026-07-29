# topmark:header:start
#
#   project      : TopMark
#   file         : types.py
#   file_relpath : src/topmark/processors/types.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Type definitions for the pipeline processing layer.

This module provides structured type definitions, such as dataclass objects,
used to pass data between the pipeline's distinct phases. These types improve
the clarity and type safety of complex return values compared to using
bare tuples or dictionaries.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from enum import Enum
from typing import Literal
from typing import TypeAlias

HeaderFieldValidationTargetLiteral: TypeAlias = Literal[
    "name",
    "value",
]
"""Header-field component targeted by a validation issue."""


@dataclass(frozen=True, kw_only=True, slots=True)
class HeaderFieldValidationIssue:
    """One deterministic violation of the header-field serialization contract.

    Attributes:
        field_index: Zero-based position in the configured field sequence.
        field_name: Original field name. Diagnostic rendering must not echo this
            value unless it has independently been established as safe.
        target: Whether the violation applies to the field name or value.
        rule: Stable machine-friendly rule identifier.
    """

    field_index: int
    field_name: str
    target: HeaderFieldValidationTargetLiteral
    rule: str


@dataclass(frozen=True, kw_only=True, slots=True)
class HeaderFieldValidationResult:
    """Typed aggregate returned by processor field validation."""

    issues: tuple[HeaderFieldValidationIssue, ...] = ()

    @property
    def is_valid(self) -> bool:
        """Return whether every selected field satisfied the contract."""
        return not self.issues


@dataclass(kw_only=True, slots=True)
class HeaderParseResult:
    """Result of parsing key-value fields from a header block.

    This dataclass provides a structured and type-safe alternative to
    a bare return tuple, ensuring that consuming code can access the
    parsed data and metrics by name. The initializer requires all arguments
    to be passed by keyword.

    Attributes:
        fields: Mapping of all successfully parsed header fields (key → value). Defaults to an
            empty dictionary.
        success_count: The number of logical fields successfully parsed and added to the
            ``fields`` dictionary. Multiline continuation records count once. Defaults to 0.
        error_count: The number of malformed logical fields or orphan records. A malformed
            multiline scalar counts once. Defaults to 0.
    """

    fields: dict[str, str] = field(default_factory=lambda: {})
    success_count: int = 0
    error_count: int = 0


class BoundsKind(Enum):
    """Discriminant for header-bound detection results.

    Members:
        SPAN: A valid header span was found.
        MALFORMED: Header markers exist, but their shape is invalid (e.g., only `end`,
            only `start`, multiple starts/ends, or `end` before `start`).
        NONE: No header markers were detected.
    """

    SPAN = "span"
    MALFORMED = "malformed"
    NONE = "none"


@dataclass(frozen=True, kw_only=True, slots=True)
class HeaderBounds:
    """Structured result for header-bound detection.

    This is a discriminated union controlled by ``kind``:

    * When ``kind is BoundsKind.SPAN``:
        - ``start`` and ``end`` are **required** (0-based line indexes).
        - ``start`` is **inclusive**, ``end`` is **exclusive** (slice-friendly).
        - ``reason`` is unused (``None``).
    * When ``kind is BoundsKind.MALFORMED``:
        - ``start``/``end`` MAY be provided to pinpoint the offending region
          (best-effort; if unknown, they can be ``None``).
        - ``reason`` SHOULD explain the malformed shape (e.g., ``"end without start"``).
    * When ``kind is BoundsKind.NONE``:
        - No markers were detected; ``start``/``end``/``reason`` are ``None``.

    Attributes:
        kind: Discriminant of the result.
        start: Start line index (inclusive) when a span is available.
        end: End line index (exclusive) when a span is available.
        reason: Human-readable reason when ``kind`` is ``MALFORMED``.
    """

    kind: BoundsKind
    start: int | None = None  # inclusive
    end: int | None = None  # exclusive
    reason: str | None = None  # e.g., "end without start", "start without end"


class StripDiagKind(Enum):
    """Outcome classification for header stripping operations.

    Members:
        REMOVED: A header was found and removed successfully.
        NOT_FOUND: No header was detected; no changes made.
        MALFORMED_REFUSED: Malformed header markers detected; removal refused by policy.
        MALFORMED_REMOVED: Malformed markers detected but removal performed (if policy allows).
        NOOP_EMPTY: File effectively empty; nothing to remove.
        ERROR: Unexpected error encountered; no changes made.
    """

    REMOVED = "removed"
    NOT_FOUND = "not_found"
    MALFORMED_REFUSED = "malformed_refused"
    MALFORMED_REMOVED = "malformed_removed"
    NOOP_EMPTY = "noop_empty"
    ERROR = "error"


@dataclass(frozen=True, kw_only=True, slots=True)
class StripDiagnostic:
    """Diagnostic payload describing a strip attempt.

    Attributes:
        kind: High-level outcome classification.
        reason: Optional human-readable explanation (e.g., policy gate or malformed reason).
        removed_span: Inclusive (start, end) span of the removed header in the original input;
            present only when a header was actually removed.
        notes: Additional details for logging or user-facing hints.
    """

    kind: StripDiagKind
    reason: str | None = None
    removed_span: tuple[int, int] | None = None  # inclusive span
    notes: list[str] = field(default_factory=list[str])


@dataclass(frozen=True, kw_only=True, slots=True)
class StripHeaderResult:
    """Result of attempting to remove a TopMark header from file lines.

    Attributes:
        lines: Updated file lines. This is the original line list when no header
            was removed or when removal was refused.
        removed_span: Inclusive `(start, end)` line span of the removed header in
            the original input, or `None` when no header was removed.
        diagnostic: Diagnostic payload describing the strip attempt outcome.
    """

    lines: list[str]
    removed_span: tuple[int, int] | None
    diagnostic: StripDiagnostic
