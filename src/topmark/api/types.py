# topmark:header:start
#
#   file         : types.py
#   file_relpath : src/topmark/api/types.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Stable public types for the TopMark API.

This module defines enums, dataclasses, and TypedDicts that appear in the
public function signatures and return values of :mod:`topmark.api`. These
shapes follow the project's semver policy.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Mapping, Sequence, TypedDict

if TYPE_CHECKING:
    from pathlib import Path


class Outcome(str, Enum):
    """Per-file outcome bucket.

    Values mirror CLI semantics:
      - ``UNCHANGED``: Header is present and compliant; no changes needed.
      - ``WOULD_CHANGE``: Dry-run detected changes would be made (apply=False).
      - ``CHANGED``: A write occurred (apply=True) or formatting-only drift fixed.
      - ``ERROR``: File failed to process.
    """

    UNCHANGED = "unchanged"
    WOULD_CHANGE = "would_change"
    CHANGED = "changed"
    ERROR = "error"


@dataclass(frozen=True)
class FileResult:
    """Result for a single file.

    Attributes:
        path: Absolute or workspace-relative path to the file.
        outcome: High-level outcome bucket.
        diff: Unified diff as a string when available (``None`` if not requested
            or not applicable).
        message: Optional human‑readable note (``None`` if not applicable).
    """

    path: "Path"
    outcome: Outcome
    diff: str | None
    message: str | None


@dataclass(frozen=True)
class RunResult:
    """Aggregate result of a run.

    Attributes:
        files: Ordered sequence of :class:`FileResult` entries **after view filtering**
            (e.g., respecting `skip_compliant` / `skip_unsupported`).
        summary: Mapping of :class:`Outcome` names to counts for the filtered `files`.
        had_errors: True if any file encountered an error during processing (computed
            from the **unfiltered** result set so real errors aren’t hidden by filters).
        skipped: Number of items removed by view filters (e.g., `skip_compliant`).
        written: Number of files successfully written (only in apply mode; otherwise 0).
        failed: Number of files that failed to write (only in apply mode; otherwise 0).
        diagnostics: Optional mapping from file path (string) to a list of pipeline
            diagnostic messages; present only if any were produced.
    """

    files: Sequence[FileResult]
    summary: Mapping[str, int]
    had_errors: bool
    skipped: int = 0
    written: int = 0
    failed: int = 0
    diagnostics: dict[str, list[str]] | None = None


# Tiny intent object used by check()/strip() to gate writes
@dataclass(frozen=True)
class WritePolicy:
    """Policy controlling which files to write when `apply=True`.

    Attributes:
        allow_insert: Permit inserting a new header (add-only).
        allow_replace: Permit replacing/updating an existing header (update-only).
        allow_remove: Permit removing a header (strip).
    """

    allow_insert: bool = False  # add missing headers
    allow_replace: bool = False  # update existing non-compliant headers
    allow_remove: bool = False  # strip headers


class FileTypeInfo(TypedDict, total=False):
    """Metadata about a registered file type.

    Keys:
        name: Identifier of the file type (e.g., ``"python"``).
        description: Human description.
        supported: File type is supported by a header processor
        processor_name: Name of the header processor registered to the file type or None
        extensions: Known filename extensions (without dots).
        filenames: Exact filenames matched (e.g., ``"Makefile"``).
        patterns: Glob-like patterns.
        skip_processing: Whether the type is discoverable but not processed.
        content_matcher: Whether a content matcher is configured.
        header_policy: Policy/strategy name for header placement.
    """

    name: str
    description: str
    supported: bool
    processor_name: str | None
    extensions: Sequence[str]
    filenames: Sequence[str]
    patterns: Sequence[str]
    skip_processing: bool
    content_matcher: bool
    header_policy: str


class ProcessorInfo(TypedDict, total=False):
    """Metadata about a registered header processor.

    Keys:
        name: Processor identifier (e.g., ``"pound"``, ``"slash"``, ``"xml"``).
        description: Human description.
        line_prefix: Line comment prefix (if applicable).
        line_suffix: Line comment suffix (if applicable).
        block_prefix: Block comment prefix (if applicable).
        block_suffix: Block comment suffix (if applicable).
    """

    name: str
    description: str
    line_prefix: str
    line_suffix: str
    block_prefix: str
    block_suffix: str
