# topmark:header:start
#
#   project      : TopMark
#   file         : types.py
#   file_relpath : src/topmark/api/types.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Stable public value types for the TopMark API.

This module centralizes the public, non-protocol type surface used by
`topmark.api`. It contains:

- public config-input mapping aliases
- literal token types used in public function signatures
- JSON-friendly TypedDict shapes for diagnostics and registry metadata
- frozen dataclasses returned by public API helpers

These shapes follow the project's semver policy. Internal domain objects may be
richer and are allowed to evolve independently (for example, internal
pipeline-only diagnostics, views, and runtime context objects).

Use this module for stable public value shapes. Structural plugin contracts
belong in [`topmark.api.protocols`][topmark.api.protocols].
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING
from typing import Final
from typing import Literal
from typing import TypeAlias
from typing import TypedDict

from topmark.core.logging import TopmarkLogger
from topmark.core.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path


logger: TopmarkLogger = get_logger(__name__)


# ---- Public config input and token literals ----

ConfigMapping: TypeAlias = Mapping[str, object]
"""TOML-tool-table-shaped mapping accepted by the public API.

This is the public config-input shape for API entrypoints. It represents the
resolved `[tool.topmark]` table (or equivalent mapping), not the full
`pyproject.toml` document.

Values are typed as `object` intentionally so the public boundary does not leak
`Any`. Validation and narrowing happen explicitly inside the config-loading
layer.
"""

DiagnosticLevelLiteral = Literal["info", "warning", "error"]
"""Allowed public diagnostic severity tokens."""

PipelineKindLiteral = Literal["check", "strip"]
"""Allowed public pipeline-family tokens."""


# ---- Public diagnostics and run-result shapes ----


class DiagnosticEntry(TypedDict):
    """JSON-friendly diagnostic entry for API consumers.

    Notes:
        - Uses string literal levels for stability and easy serialization.
        - Mirrors internal pipeline diagnostics but does not expose internal enums/classes.
    """

    level: DiagnosticLevelLiteral
    message: str


class DiagnosticTotals(TypedDict):
    """Aggregate diagnostic counts across the returned *view*.

    Attributes:
        info: Number of info diagnostics.
        warning: Number of warning diagnostics.
        error: Number of error diagnostics.
        total: Sum of all diagnostics.
    """

    info: int
    warning: int
    error: int
    total: int


class Outcome(str, Enum):
    """Stable per-file outcome bucket used by the public API.

    Values mirror the high-level outcome categories exposed by the CLI and API.
    Consumers should prefer `Outcome` (and `Outcome.value`) for programmatic
    decisions rather than relying on human-facing labels.
    """

    PENDING = "pending"
    ERROR = "error"
    # File skipped (not processed)
    SKIPPED = "skipped"
    # File already complies
    UNCHANGED = "unchanged"
    # A change was detected but not applied
    WOULD_CHANGE = "would change"
    WOULD_INSERT = "would insert"
    WOULD_UPDATE = "would update"
    WOULD_STRIP = "would strip"
    # Changes have been applied
    CHANGED = "changed"
    INSERTED = "inserted"
    UPDATED = "updated"
    STRIPPED = "stripped"


# Stable presentation/aggregation order for public outcomes.
OUTCOME_ORDER: Final[tuple[Outcome, ...]] = (
    Outcome.PENDING,
    Outcome.SKIPPED,
    Outcome.UNCHANGED,
    Outcome.WOULD_CHANGE,
    Outcome.WOULD_INSERT,
    Outcome.WOULD_UPDATE,
    Outcome.WOULD_STRIP,
    Outcome.CHANGED,
    Outcome.INSERTED,
    Outcome.UPDATED,
    Outcome.STRIPPED,
    Outcome.ERROR,
)


@dataclass(frozen=True)
class FileResult:
    """Result for a single file after pipeline execution and view filtering.

    This object is a **pure data carrier** intended for machine consumption
    (JSON, NDJSON, API callers). It deliberately contains no pre-rendered
    human-facing messages or ANSI formatting.

    Attributes:
        path: Absolute or workspace-relative path to the file.
        outcome: Stable, high-level outcome bucket describing the
            file's final state (e.g. ``UNCHANGED``, ``WOULD_UPDATE``, ``ERROR``).
        diff: Unified diff as a string when available.
            ``None`` if diffs were not requested or are not applicable.
        bucket_key: Public bucket identifier corresponding to the
            outcome classification (typically ``outcome.value``). This key is
            stable and suitable for aggregation and machine processing.
        bucket_label: Human-oriented explanation for the bucket,
            derived from the first-seen classification reason. Intended for
            display purposes only.

    Notes:
        - ``outcome`` is the **authoritative semantic signal** and is stable
          across versions.
        - ``bucket_key`` mirrors the public outcome value and exists to support
          uniform bucketing and summaries.
        - ``bucket_label`` is best-effort, may change between versions, and
          should not be relied upon for programmatic decisions.
        - Any human-readable or colorized summaries must be generated by
          presentation helpers (e.g. in ``topmark.presentation``), not by the API.
    """

    path: Path
    outcome: Outcome
    diff: str | None
    bucket_key: str | None = None
    bucket_label: str | None = None


@dataclass(frozen=True)
class RunResult:
    """Aggregate result of a TopMark run after view-level filtering.

    This structure summarizes per-file results, outcome counts, and diagnostics
    in a JSON-friendly form suitable for API consumers and machine-readable
    output formats.

    Attributes:
        files: Ordered sequence of per-file results **after report-scope filtering**.
        summary: Mapping from public outcome values
            (``Outcome.value``) to counts for the returned ``files``.
        had_errors: ``True`` if any file encountered an error during
            processing, computed from the **unfiltered** result set so that
            real errors are not hidden by report filtering.
        skipped: Number of results excluded by report-scope filtering.
        written: Number of files successfully written
            (only meaningful when ``apply=True``; otherwise ``0``).
        failed: Number of files that failed to write
            (only meaningful when ``apply=True``; otherwise ``0``).
        bucket_summary: Optional summary aggregated
            by bucket key rather than by outcome alone. When present, this is
            primarily intended to support CLI-style reporting.
        diagnostics: Optional mapping
            from file path to public diagnostic entries for the **returned view**.
        diagnostic_totals: Aggregate diagnostic counts
            across the returned (filtered) view.
        diagnostic_totals_all: Aggregate diagnostic
            counts across the entire run (pre report filtering).

    Notes:
        - ``summary`` is strictly derived from ``files`` and reflects only the
          filtered view.
        - ``bucket_summary`` is optional and more presentation-oriented than
          ``summary``; consumers should not assume it is always present.
        - No fields in this object contain formatted or colorized output.
          Presentation is the responsibility of higher layers (CLI or UI).
    """

    files: Sequence[FileResult]
    summary: Mapping[str, int]
    had_errors: bool
    skipped: int = 0
    written: int = 0
    failed: int = 0
    bucket_summary: Mapping[str, int] | None = None
    diagnostics: dict[str, list[DiagnosticEntry]] | None = None
    diagnostic_totals: DiagnosticTotals | None = None
    diagnostic_totals_all: DiagnosticTotals | None = None


# ---- Public registry / metadata shapes ----


class FileTypePolicyInfo(TypedDict, total=True):
    r"""Stable metadata describing header placement policy for a file type.

    This typed dict is the public, JSON-friendly representation of a
    [`topmark.filetypes.policy.FileTypeHeaderPolicy`][topmark.filetypes.policy.FileTypeHeaderPolicy]
    instance.

    Attributes:
        supports_shebang: Whether this file type commonly starts with a POSIX
            shebang (for example, ``#!/usr/bin/env bash``). When `True`,
            processors may skip a leading shebang during placement.
        encoding_line_regex: Optional regex string that matches an encoding
            declaration line immediately after a shebang (for example, Python
            PEP 263). When provided and a shebang was skipped, a matching line
            is also skipped for placement.
        pre_header_blank_after_block: Number of blank lines to place between a
            preamble block (shebang/encoding or similar) and the header.
        ensure_blank_after_header: Whether exactly one blank line should follow
            the header when body content follows.
        blank_collapse_mode: How blank lines around the header are identified
            and collapsed during insert/strip repairs. See
            [`BlankCollapseMode`][topmark.filetypes.policy.BlankCollapseMode]
            for semantics.
        blank_collapse_extra: Additional characters to treat as blank in
            addition to those covered by `blank_collapse_mode`.
    """

    supports_shebang: bool
    encoding_line_regex: str | None

    pre_header_blank_after_block: int
    ensure_blank_after_header: bool

    # How to identify and collapse “blank” lines around the header during insert/strip repairs.
    blank_collapse_mode: str
    blank_collapse_extra: str


class FileTypeInfo(TypedDict, total=True):
    """Stable metadata about a registered file type.

    This is the JSON-friendly public view returned by registry-facing API
    helpers. It describes discovery metadata, binding state, and the effective
    placement policy for the file type.

    Attributes:
        local_key: File type local key (compatibility identifier).
        namespace: Namespace that owns the file type.
        qualified_key: Canonical file type key.
        description: Human description.
        bound: Whether the file type currently has an effective processor
            binding.
        extensions: Known filename extensions (without dots).
        filenames: Exact filenames matched (for example, ``"Makefile"``).
        patterns: Full-match regular-expression patterns.
        skip_processing: Whether the type is discoverable but not processed.
        has_content_matcher: Whether a content matcher exists.
        has_insert_checker: Whether a header insert checker exists.
        policy: Policy/strategy for header placement.
    """

    local_key: str
    namespace: str
    qualified_key: str

    description: str

    bound: bool

    extensions: Sequence[str]
    filenames: Sequence[str]
    patterns: Sequence[str]
    skip_processing: bool
    has_content_matcher: bool
    has_insert_checker: bool
    policy: FileTypePolicyInfo


class ProcessorInfo(TypedDict, total=True):
    """Stable metadata about a registered header processor.

    This is the JSON-friendly public view returned by registry-facing API
    helpers. It describes the processor's identity, binding state, and comment
    delimiter metadata.

    Attributes:
        local_key: Processor local key (compatibility identifier).
        namespace: Namespace that owns the processor.
        qualified_key: Canonical processor key.
        description: Human description.
        bound: Whether the processor currently participates in at least one
            effective file-type binding.
        line_indent: Line comment indent (if applicable).
        line_prefix: Line comment prefix (if applicable).
        line_suffix: Line comment suffix (if applicable).
        block_prefix: Block comment prefix (if applicable).
        block_suffix: Block comment suffix (if applicable).
    """

    local_key: str
    namespace: str
    qualified_key: str

    description: str

    bound: bool

    line_indent: str
    line_prefix: str
    line_suffix: str
    block_prefix: str
    block_suffix: str


class BindingInfo(TypedDict, total=True):
    """Stable metadata about an effective file-type-to-processor binding.

    This is the JSON-friendly public view returned by registry-facing API
    helpers for effective bindings.

    Attributes:
        file_type_key: Canonical file type key.
        file_type_local_key: File type local key.
        file_type_namespace: Namespace that owns the file type.
        processor_key: Canonical processor key.
        processor_local_key: Processor local key.
        processor_namespace: Namespace that owns the processor.
        file_type_description: Human description of the file type.
        processor_description: Human description of the processor.
    """

    file_type_key: str
    file_type_local_key: str
    file_type_namespace: str

    processor_key: str
    processor_local_key: str
    processor_namespace: str

    file_type_description: str
    processor_description: str


# ---- Public policy / reporting tokens ----


PublicEmptyInsertModeLiteral = Literal[
    "bytes_empty",
    "logical_empty",
    "whitespace_empty",
]
"""Public token type for configuring how TopMark classifies “empty” files.

These values intentionally mirror the internal `EmptyInsertMode.value` strings
without exposing the internal enum class as part of the public API.
"""

PublicHeaderMutationModeLiteral = Literal[
    "all",
    "add_only",
    "update_only",
]
"""Public token type for configuring which header mutations are allowed.

These values intentionally mirror the internal `HeaderMutationMode.value`
strings without exposing the internal enum class as part of the public API.
"""

PublicReportScopeLiteral = Literal[
    "actionable",
    "noncompliant",
    "all",
]
"""Public token type for selecting the returned run-result scope.

These values intentionally mirror the internal `ReportScope.value` strings
without exposing the internal enum class as part of the public API.
"""


# ---- Public policy shapes ----


class PublicPolicy(TypedDict, total=False):
    """Public, JSON-friendly policy overlay.

    This structure mirrors the stable, public subset of TopMark's internal
    policy model and can be passed to public API helpers to refine runtime
    behavior. All keys are optional; unspecified options inherit from the
    resolved config/defaults.

    Keys:
        header_mutation_mode: Defines how headers may be mutated: process all
            files (`"all"`, default), only add headers when no header is
            present (`"add_only"`), or only update existing headers
            (`"update_only"`).
        allow_header_in_empty_files: Allow inserting headers into files that are
            classified as empty under the effective `empty_insert_mode`.
        empty_insert_mode: Public token controlling which files are considered
            empty for insertion.
        render_empty_header_when_no_fields: Allow inserting an empty header when
            no fields are defined.
        allow_reflow: If `True`, allow reflowing file content when inserting a
            header. This can break check/strip idempotence.
        allow_content_probe: Whether the resolver may consult file contents
            during file-type detection.

    Notes:
        This is a stable public contract. Public APIs use JSON/TOML-friendly
        primitive values, so enum-backed internal policy values are exposed as
        string tokens rather than internal enum classes.
    """

    header_mutation_mode: PublicHeaderMutationModeLiteral
    allow_header_in_empty_files: bool
    empty_insert_mode: PublicEmptyInsertModeLiteral
    render_empty_header_when_no_fields: bool
    allow_reflow: bool
    allow_content_probe: bool


class PublicPolicyByType(TypedDict, total=False):
    """Per-file-type public policy overlays.

    This mapping applies a `PublicPolicy` overlay to a specific file type key.

    Example mapping:
        {"python": {"allow_header_in_empty_files": True}}

    Notes:
        Keys must match registered file type identifiers. Values use the same
        stable `PublicPolicy` structure as the global overlay.
    """

    __extra_items__: PublicPolicy
