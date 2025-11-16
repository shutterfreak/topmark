# topmark:header:start
#
#   project      : TopMark
#   file         : types.py
#   file_relpath : src/topmark/pipeline/processors/types.py
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

from dataclasses import dataclass, field
from enum import Enum


@dataclass(kw_only=True)
class HeaderParseResult:
    """Result of parsing key-value fields from a header block.

    This dataclass provides a structured and type-safe alternative to
    a bare return tuple, ensuring that consuming code can access the
    parsed data and metrics by name. The initializer requires all arguments
    to be passed by keyword.

    Attributes:
        fields (dict[str, str]): Mapping of all successfully parsed header fields
            (key → value). Defaults to an empty dictionary.
        success_count (int): The number of header lines that were successfully
            parsed and added to the ``fields`` dictionary. Defaults to 0.
        error_count (int): The number of header lines that were malformed (e.g.,
            missing a colon, or having an empty field name). Defaults to 0.
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


@dataclass(frozen=True)
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
        kind (BoundsKind): Discriminant of the result.
        start (int | None): Start line index (inclusive) when a span is available.
        end (int | None): End line index (exclusive) when a span is available.
        reason (str | None): Human-readable reason when ``kind`` is ``MALFORMED``.
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


@dataclass(frozen=True)
class StripDiagnostic:
    """Diagnostic payload describing a strip attempt.

    Attributes:
        kind (StripDiagKind): High-level outcome classification.
        reason (str | None): Optional human-readable explanation (e.g., policy gate or
            malformed reason).
        removed_span (tuple[int, int] | None): Inclusive (start, end) span of the removed header
            in the original input; present only when a header was actually removed.
        notes (list[str]): Additional details for logging or user-facing hints.
    """

    kind: StripDiagKind
    reason: str | None = None
    removed_span: tuple[int, int] | None = None  # inclusive span
    notes: list[str] = field(default_factory=list[str])
