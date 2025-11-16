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
  * All enums inherit from `EnumIntrospectionMixin` (from `topmark.core.enum_mixins`)
    and `ColoredStrEnum` (from `topmark.rendering.colored_enum`) for shared utilities
    and colors.
  * Values are human‑readable strings used in CLI/diagnostics; do not rely on
    identity (`is`) checks—prefer equality (`==`).
  * Only the view/API layer synthesizes public outcomes; steps should not
    attempt to classify coarse buckets.
"""

from __future__ import annotations

from yachalk import chalk

from topmark.core.enum_mixins import EnumIntrospectionMixin
from topmark.rendering.colored_enum import ColoredStrEnum


class FsStatus(EnumIntrospectionMixin, ColoredStrEnum):
    """Represents the status of file system checks in the pipeline."""

    # Value format: (description: str, color_renderer: ChalkBuilder)
    PENDING = ("pending", chalk.gray)
    OK = ("ok", chalk.green)
    EMPTY = ("empty file", chalk.yellow)
    NOT_FOUND = ("not found", chalk.red)
    NO_READ_PERMISSION = ("no read permission", chalk.red_bright)
    UNREADABLE = ("read error", chalk.red_bright)
    NO_WRITE_PERMISSION = ("no write permission", chalk.red_bright)
    BINARY = ("binary file", chalk.red)
    BOM_BEFORE_SHEBANG = ("UTF BOM before shebang", chalk.yellow)
    UNICODE_DECODE_ERROR = ("Unicode decode error", chalk.yellow)
    MIXED_LINE_ENDINGS = ("file contains mixed line endings", chalk.yellow)


class ResolveStatus(EnumIntrospectionMixin, ColoredStrEnum):
    """Represents the status of file type resolution in the pipeline.

    Used to indicate whether the file type was successfully resolved or not.
    """

    PENDING = ("resolve pending", chalk.gray)
    RESOLVED = ("resolved", chalk.green)
    TYPE_RESOLVED_HEADERS_UNSUPPORTED = ("known file type, headers not supported", chalk.yellow)
    TYPE_RESOLVED_NO_PROCESSOR_REGISTERED = ("known file type, no header processor", chalk.red)
    UNSUPPORTED = ("unsupported file type", chalk.yellow)


class ContentStatus(EnumIntrospectionMixin, ColoredStrEnum):
    """Represents the status of file content checks in the pipeline.

    `SKIPPED_*` states are policy-aware potential non-terminal states.
    """

    PENDING = ("file content pending", chalk.gray)
    OK = ("ok", chalk.green)
    UNSUPPORTED = ("unsupported", chalk.yellow)
    SKIPPED_MIXED_LINE_ENDINGS = ("mixed line endings", chalk.red)
    SKIPPED_POLICY_BOM_BEFORE_SHEBANG = ("BOM before shebang", chalk.red)
    SKIPPED_REFLOW = ("Would reflow content (breaks check/strip idempotence)", chalk.red)
    UNREADABLE = ("unreadable", chalk.red_bright)


class HeaderStatus(EnumIntrospectionMixin, ColoredStrEnum):
    """Represents the status of header processing for a file in the pipeline.

    Used to indicate detection, parsing, and validation results for the file header.
    """

    PENDING = ("header detection pending", chalk.gray)
    MISSING = ("header missing", chalk.blue)
    DETECTED = ("header detected", chalk.green)
    MALFORMED = ("header malformed", chalk.red_bright)
    MALFORMED_ALL_FIELDS = ("header malformed (all fields invalid)", chalk.red_bright)
    MALFORMED_SOME_FIELDS = ("header malformed (some fields invalid)", chalk.red_bright)
    EMPTY = ("header empty", chalk.yellow_bright)


class GenerationStatus(EnumIntrospectionMixin, ColoredStrEnum):
    """Represents the status of header generation in the pipeline.

    Used to indicate whether a new header was generated, rendered,
    or if required fields are missing.
    """

    PENDING = ("header field generation pending", chalk.gray)
    GENERATED = ("header fields generated", chalk.green)
    NO_FIELDS = ("no header fields", chalk.yellow_bright)
    SKIPPED = ("header field generation skipped", chalk.red)
    # RENDERED = "header fields rendered", chalk.blue


class RenderStatus(EnumIntrospectionMixin, ColoredStrEnum):
    """Rendering status for expected header text.

    Indicates whether the renderer produced an in-memory textual representation of
    the expected header. This status does not imply that a change is necessary —
    it only tracks whether rendering completed.

    States:
        PENDING: Rendering has not been executed or did not complete.
        RENDERED: The expected header text was successfully rendered.
    """

    PENDING = ("header field rednering pending", chalk.gray)
    RENDERED = ("header fields rendered", chalk.blue)
    SKIPPED = ("header rendering skipped", chalk.yellow)


class ComparisonStatus(EnumIntrospectionMixin, ColoredStrEnum):
    """Represents the status of comparing the current and expected header in the pipeline.

    Used to indicate if the header has changed, is unchanged, or cannot be compared.
    """

    PENDING = ("comparison pending", chalk.gray)
    CHANGED = ("changes found", chalk.red)
    UNCHANGED = ("no changes found", chalk.green)
    SKIPPED = ("comparison skipped", chalk.yellow)


class StripStatus(EnumIntrospectionMixin, ColoredStrEnum):
    """Represents the status of header stripping in the pipeline.

    This axis is orthogonal to scanner detection and write outcomes:
      - Scanner (HeaderStatus) tells us whether a header exists in the original file.
      - StripStatus tells us whether we prepared/performed a removal.
      - WriteStatus records the final write outcome (e.g., REMOVED on apply).
    """

    PENDING = ("stripping pending", chalk.gray)
    NOT_NEEDED = ("stripping not needed", chalk.blue)  # no header present to remove
    READY = ("ready for stripping", chalk.green)  # removal prepared (updated_file_lines computed)
    FAILED = ("stripping failed", chalk.red_bright)


class PlanStatus(EnumIntrospectionMixin, ColoredStrEnum):
    """Represents the status of the plan (pre-write) phase.

    Indicates the intended change (insert/replace/remove/skip) and whether a
    preview was produced.
    """

    PENDING = ("update pending", chalk.gray)
    PREVIEWED = ("update previewed", chalk.blue)
    REPLACED = ("header replaced", chalk.green)
    INSERTED = ("header inserted", chalk.green_bright)
    REMOVED = ("header removed", chalk.yellow_bright)
    SKIPPED = ("update skipped", chalk.yellow)
    FAILED = ("update failed", chalk.red_bright)


class PatchStatus(EnumIntrospectionMixin, ColoredStrEnum):
    """Represents the status of patch (diff) generation in the pipeline.

    Indicates whether a unified diff was generated, skipped because content
    is unchanged or an updated image was unavailable, or failed to generate.
    """

    PENDING = ("patch pending", chalk.gray)
    GENERATED = ("patch generated", chalk.green)
    SKIPPED = ("patch skipped", chalk.yellow)
    FAILED = ("patch failed", chalk.red_bright)


class WriteStatus(EnumIntrospectionMixin, ColoredStrEnum):
    """Represents the status of the header write operation in the pipeline.

    Used to indicate whether the header was written, previewed, skipped, or failed.
    """

    PENDING = ("write pending", chalk.gray)
    WRITTEN = ("changes written to file", chalk.green)
    SKIPPED = ("write was skipped", chalk.yellow)
    FAILED = ("write failed", chalk.red_bright)
