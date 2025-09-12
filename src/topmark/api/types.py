# topmark:header:start
#
#   project      : TopMark
#   file         : types.py
#   file_relpath : src/topmark/api/types.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Stable public types for the TopMark API.

This module defines enums, dataclasses, and TypedDicts that appear in the
public function signatures and return values of [`topmark.api`][topmark.api]. These
shapes follow the project's semver policy.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Mapping, Sequence, TypedDict

if TYPE_CHECKING:
    from pathlib import Path

    from .public_types import PublicDiagnostic


class DiagnosticTotals(TypedDict):
    """Aggregate diagnostic counts across the returned *view*.

    Attributes:
        info (int): Number of info diagnostics.
        warning (int): Number of warning diagnostics.
        error (int): Number of error diagnostics.
        total (int): Sum of all diagnostics.
    """

    info: int
    warning: int
    error: int
    total: int


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
        path (Path): Absolute or workspace-relative path to the file.
        outcome (Outcome): High-level outcome bucket.
        diff (str | None): Unified diff as a string when available (``None`` if not requested
            or not applicable).
        message (str | None): Optional human‑readable note (``None`` if not applicable).
    """

    path: Path
    outcome: Outcome
    diff: str | None
    message: str | None


@dataclass(frozen=True)
class RunResult:
    """Aggregate result of a run.

    Attributes:
        files (Sequence[FileResult]): Ordered sequence of
            [`FileResult`][topmark.api.types.FileResult] entries **after view filtering**
            (e.g., respecting `skip_compliant` / `skip_unsupported`).
        summary (Mapping[str, int]): Mapping of [`Outcome`][topmark.api.types.Outcome] names
            to counts for the filtered `files`.
        had_errors (bool): `True` if any file encountered an error during processing (computed
            from the **unfiltered** result set so real errors aren’t hidden by filters).
        skipped (int): Number of items removed by view filters (e.g., `skip_compliant`).
        written (int): Number of files successfully written (only in apply mode; otherwise 0).
        failed (int): Number of files that failed to write (only in apply mode; otherwise 0).
        diagnostics (dict[str, list[PublicDiagnostic]] | None): Optional mapping from file path
            to a list of public diagnostics.
        diagnostic_totals (DiagnosticTotals | None): Optional aggregate counts across the
            **returned view** (not the entire run).
        diagnostic_totals_all (DiagnosticTotals | None): Optional aggregate counts across the
            **entire run** (pre view filtering).
    """

    files: Sequence[FileResult]
    summary: Mapping[str, int]
    had_errors: bool
    skipped: int = 0
    written: int = 0
    failed: int = 0
    diagnostics: dict[str, list[PublicDiagnostic]] | None = None
    diagnostic_totals: DiagnosticTotals | None = None
    diagnostic_totals_all: DiagnosticTotals | None = None


# Tiny intent object used by check()/strip() to gate writes
@dataclass(frozen=True)
class WritePolicy:
    """Policy controlling which files to write when `apply=True`.

    Attributes:
        allow_insert (bool): Permit inserting a new header (add-only).
        allow_replace (bool): Permit replacing/updating an existing header (update-only).
        allow_remove (bool): Permit removing a header (strip).
    """

    allow_insert: bool = False  # add missing headers
    allow_replace: bool = False  # update existing non-compliant headers
    allow_remove: bool = False  # strip headers


class FileTypeInfo(TypedDict, total=False):
    """Metadata about a registered file type.

    Attributes:
        name (str): Identifier of the file type (e.g., ``"python"``).
        description (str): Human description.
        supported (bool): File type is supported by a header processor
        processor_name (str | None): Name of the header processor registered to the file type
            or `None`
        extensions (Sequence[str]): Known filename extensions (without dots).
        filenames (Sequence[str]): Exact filenames matched (e.g., ``"Makefile"``).
        patterns (Sequence[str]): Glob-like patterns.
        skip_processing (bool): Whether the type is discoverable but not processed.
        content_matcher (bool): Whether a content matcher is configured.
        header_policy (str): Policy/strategy name for header placement.
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

    Attributes:
        name (str): Processor identifier (e.g., ``"pound"``, ``"slash"``, ``"xml"``).
        description (str): Human description.
        line_prefix (str): Line comment prefix (if applicable).
        line_suffix (str): Line comment suffix (if applicable).
        block_prefix (str): Block comment prefix (if applicable).
        block_suffix (str): Block comment suffix (if applicable).
    """

    name: str
    description: str
    line_prefix: str
    line_suffix: str
    block_prefix: str
    block_suffix: str
