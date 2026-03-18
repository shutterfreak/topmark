# topmark:header:start
#
#   project      : TopMark
#   file         : status.py
#   file_relpath : src/topmark/pipeline/status.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Status enums for each axis in the TopMark pipeline.

This module defines the *authoritative* set of statuses for every pipeline axis.
Each enum captures a phase (e.g., resolve, fs, content, header, generation,
render, strip, comparison, update, write). Steps **must only** write to the
axes listed in their ``axes_written`` contract.

Conventions:
  * All enums inherit from
    [`EnumIntrospectionMixin`][topmark.core.enum_mixins.EnumIntrospectionMixin]
    (from [`topmark.core.enum_mixins`][topmark.core.enum_mixins]).
    and
    [`StyledStrEnum`][topmark.core.presentation.StyledStrEnum]
    (from [`topmark.core.presentation`][topmark.core.presentation])
    for shared utilities and semantic style roles.
  * Values are human‑readable strings used in CLI/diagnostics; do not rely on
    identity (`is`) checks—prefer equality (`==`).
  * Only the view/API layer synthesizes public outcomes; steps should not
    attempt to classify coarse buckets.
"""

from __future__ import annotations

from topmark.core.enum_mixins import EnumIntrospectionMixin
from topmark.core.presentation import StyledStrEnum
from topmark.core.presentation import StyleRole


class BaseStatus(EnumIntrospectionMixin, StyledStrEnum):
    """Represents the base status class of file system checks in the pipeline.

    Each member should define a ``str` value and a semantic `StyleRole`.
    """

    pass


class FsStatus(BaseStatus):
    """Represents the status of file system checks in the pipeline."""

    PENDING = (
        "pending",
        StyleRole.PENDING,
    )
    OK = (
        "ok",
        StyleRole.OK,
    )
    EMPTY = (
        "empty file",
        StyleRole.WARNING,
    )
    NOT_FOUND = (
        "not found",
        StyleRole.ERROR,
    )
    NO_READ_PERMISSION = (
        "no read permission",
        StyleRole.ERROR,
    )
    UNREADABLE = (
        "read error",
        StyleRole.ERROR,
    )
    NO_WRITE_PERMISSION = (
        "no write permission",
        StyleRole.ERROR,
    )
    BINARY = (
        "binary file",
        StyleRole.ERROR,
    )
    BOM_BEFORE_SHEBANG = (
        "UTF BOM before shebang",
        StyleRole.WARNING,
    )
    UNICODE_DECODE_ERROR = (
        "Unicode decode error",
        StyleRole.WARNING,
    )
    MIXED_LINE_ENDINGS = (
        "file contains mixed line endings",
        StyleRole.WARNING,
    )


class ResolveStatus(BaseStatus):
    """Represents the status of file type resolution in the pipeline.

    Used to indicate whether the file type was successfully resolved or not.
    """

    PENDING = (
        "resolve pending",
        StyleRole.PENDING,
    )
    RESOLVED = (
        "resolved",
        StyleRole.OK,
    )
    TYPE_RESOLVED_HEADERS_UNSUPPORTED = (
        "known file type, headers not supported",
        StyleRole.UNSUPPORTED,
    )
    TYPE_RESOLVED_NO_PROCESSOR_REGISTERED = (
        "known file type, no header processor",
        StyleRole.ERROR,
    )
    UNSUPPORTED = (
        "unsupported file type",
        StyleRole.UNSUPPORTED,
    )


class ContentStatus(BaseStatus):
    """Represents the status of file content checks in the pipeline.

    `SKIPPED_*` states are policy-aware potential non-terminal states.
    """

    PENDING = (
        "file content pending",
        StyleRole.PENDING,
    )
    OK = (
        "ok",
        StyleRole.OK,
    )
    UNSUPPORTED = (
        "unsupported",
        StyleRole.UNSUPPORTED,
    )
    SKIPPED_MIXED_LINE_ENDINGS = (
        "mixed line endings",
        StyleRole.ERROR,
    )
    SKIPPED_POLICY_BOM_BEFORE_SHEBANG = (
        "BOM before shebang",
        StyleRole.ERROR,
    )
    SKIPPED_REFLOW = (
        "Would reflow content (breaks check/strip idempotence)",
        StyleRole.ERROR,
    )
    UNREADABLE = (
        "unreadable",
        StyleRole.ERROR,
    )


class HeaderStatus(BaseStatus):
    """Represents the status of header processing for a file in the pipeline.

    Used to indicate detection, parsing, and validation results for the file header.
    """

    PENDING = (
        "header detection pending",
        StyleRole.PENDING,
    )
    MISSING = (
        "header missing",
        StyleRole.EMPHASIS,
    )
    DETECTED = (
        "header detected",
        StyleRole.OK,
    )
    MALFORMED = (
        "header malformed",
        StyleRole.ERROR,
    )
    MALFORMED_ALL_FIELDS = (
        "header malformed (all fields invalid)",
        StyleRole.ERROR,
    )
    MALFORMED_SOME_FIELDS = (
        "header malformed (some fields invalid)",
        StyleRole.ERROR,
    )
    EMPTY = (
        "header empty",
        StyleRole.WARNING,
    )


class GenerationStatus(BaseStatus):
    """Represents the status of header generation in the pipeline.

    Used to indicate whether a new header was generated, rendered,
    or if required fields are missing.
    """

    PENDING = (
        "header field generation pending",
        StyleRole.PENDING,
    )
    GENERATED = (
        "header fields generated",
        StyleRole.OK,
    )
    NO_FIELDS = (
        "no header fields",
        StyleRole.WARNING,
    )
    SKIPPED = (
        "header field generation skipped",
        StyleRole.SKIPPED,
    )


class RenderStatus(BaseStatus):
    """Rendering status for expected header text.

    Indicates whether the renderer produced an in-memory textual representation of
    the expected header. This status does not imply that a change is necessary —
    it only tracks whether rendering completed.

    States:
        PENDING: Rendering has not been executed or did not complete.
        RENDERED: The expected header text was successfully rendered.
    """

    PENDING = (
        "header field rendering pending",
        StyleRole.PENDING,
    )
    RENDERED = (
        "header fields rendered",
        StyleRole.EMPHASIS,
    )
    SKIPPED = (
        "header rendering skipped",
        StyleRole.SKIPPED,
    )


class ComparisonStatus(BaseStatus):
    """Represents the status of comparing the current and expected header in the pipeline.

    Used to indicate if the header has changed, is unchanged, or cannot be compared.
    """

    PENDING = (
        "comparison pending",
        StyleRole.PENDING,
    )
    CHANGED = (
        "changes found",
        StyleRole.CHANGED,
    )
    UNCHANGED = (
        "no changes found",
        StyleRole.UNCHANGED,
    )
    SKIPPED = (
        "comparison skipped",
        StyleRole.SKIPPED,
    )


class StripStatus(BaseStatus):
    """Represents the status of header stripping in the pipeline.

    This axis is orthogonal to scanner detection and write outcomes:
      - Scanner (HeaderStatus) tells us whether a header exists in the original file.
      - StripStatus tells us whether we prepared/performed a removal.
      - WriteStatus records the final write outcome (e.g., REMOVED on apply).
    """

    PENDING = (
        "stripping pending",
        StyleRole.PENDING,
    )
    NOT_NEEDED = (
        "stripping not needed",
        StyleRole.UNCHANGED,
    )  # no header present to remove
    READY = (
        "ready for stripping",
        StyleRole.OK,
    )  # removal prepared (updated_file_lines computed,)
    FAILED = (
        "stripping failed",
        StyleRole.ERROR,
    )


class PlanStatus(BaseStatus):
    """Represents the status of the plan (pre-write) phase.

    Indicates the intended change (insert/replace/remove/skip) and whether a
    preview was produced.
    """

    PENDING = (
        "update pending",
        StyleRole.PENDING,
    )
    PREVIEWED = (
        "update previewed",
        StyleRole.EMPHASIS,
    )
    REPLACED = (
        "header replaced",
        StyleRole.CHANGED,
    )
    INSERTED = (
        "header inserted",
        StyleRole.CHANGED,
    )
    REMOVED = (
        "header removed",
        StyleRole.CHANGED,
    )
    SKIPPED = (
        "update skipped",
        StyleRole.SKIPPED,
    )
    FAILED = (
        "update failed",
        StyleRole.ERROR,
    )


class PatchStatus(BaseStatus):
    """Represents the status of patch (diff) generation in the pipeline.

    Indicates whether a unified diff was generated, skipped because content
    is unchanged or an updated image was unavailable, or failed to generate.
    """

    PENDING = (
        "patch pending",
        StyleRole.PENDING,
    )
    GENERATED = (
        "patch generated",
        StyleRole.OK,
    )
    SKIPPED = (
        "patch skipped",
        StyleRole.SKIPPED,
    )
    FAILED = (
        "patch failed",
        StyleRole.ERROR,
    )


class WriteStatus(BaseStatus):
    """Represents the status of the header write operation in the pipeline.

    Used to indicate whether the header was written, previewed, skipped, or failed.
    """

    PENDING = (
        "write pending",
        StyleRole.PENDING,
    )
    WRITTEN = (
        "changes written to file",
        StyleRole.OK,
    )
    SKIPPED = (
        "write was skipped",
        StyleRole.SKIPPED,
    )
    FAILED = (
        "write failed",
        StyleRole.ERROR,
    )
