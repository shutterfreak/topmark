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
- JSON-friendly TypedDict shapes for diagnostics, policy, and registry metadata
- frozen dataclasses returned by public API helpers, including probe and run DTOs
- public streaming event DTOs that define the compatibility contract for
  future incremental API entry points

These shapes follow the project's semver policy. Internal domain objects may be
richer and are allowed to evolve independently (for example, internal
pipeline-only diagnostics, views, and runtime context objects).

Outcome semantics are defined in
[`topmark.core.outcomes`][topmark.core.outcomes] so lower-level pipeline code can
classify results without importing the API package. API result DTOs reference
that shared enum while keeping the rest of the public value surface here.

Use this module for stable public value shapes. Structural plugin contracts
belong in [`topmark.api.protocols`][topmark.api.protocols].
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING
from typing import Literal
from typing import TypeAlias
from typing import TypedDict

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from topmark.config.model import FrozenConfig
    from topmark.core.exit_codes import ExitCode
    from topmark.core.outcomes import Outcome
    from topmark.pipeline.context.model import ProcessingContext
    from topmark.pipeline.kinds import PipelineKindLiteral


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

DiagnosticLevelLiteral: TypeAlias = Literal[
    "info",
    "warning",
    "error",
]
"""Allowed public diagnostic severity tokens."""


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


@dataclass(frozen=True, kw_only=True, slots=True)
class ProbeCandidateInfo:
    """Stable public view of one file-type resolution candidate.

    Attributes:
        file_type: Public file type identifier for the candidate.
        qualified_key: Canonical namespaced file type key.
        score: Resolver score used only for explanatory ordering within this
            probe result. The exact scoring algorithm is internal and may evolve.
        selected: Whether this candidate was selected as the effective file type.
        rank: One-based rank after resolver tie-breaking.
        matched_by: Stable string tokens describing which resolver signals matched,
            such as extension, filename, pattern, content, or content_error.

    Notes:
        This object deliberately omits internal registry objects, matcher instances,
        and raw scoring details. Consumers should treat `selected`, `rank`, and
        `matched_by` as the stable decision signals; `score` is explanatory only.
    """

    file_type: str
    qualified_key: str
    score: int
    selected: bool
    rank: int
    matched_by: tuple[str, ...]


@dataclass(frozen=True, kw_only=True, slots=True)
class ProbeFileResult:
    """Probe result for a single path.

    Attributes:
        path: Path that was probed, reported as missing, or reported as filtered
            during explicit-input discovery.
        status: Stable string status for the probe result, derived from the
            internal resolver status without exposing internal enum classes.
        reason: Stable string reason describing why the path reached that status.
        selected_file_type: Public local identifier of the selected file type, if
            one resolved successfully.
        selected_processor: Public local identifier of the selected processor, if
            one is bound for the selected file type.
        candidates: Ordered, normalized candidate list considered during file-type
            resolution. Empty for missing or discovery-filtered paths.

    Notes:
        `status` and `reason` are plain strings to keep the public API JSON-friendly
        and independent from internal resolver enum classes. Candidate internals are
        reduced to `ProbeCandidateInfo` records.
    """

    path: Path
    status: str
    reason: str
    selected_file_type: str | None
    selected_processor: str | None
    candidates: Sequence[ProbeCandidateInfo]


@dataclass(frozen=True, kw_only=True, slots=True)
class ProbeRunResult:
    """Aggregate result of a TopMark probe run.

    Attributes:
        files: Ordered sequence of per-path probe results.
        summary: Mapping from public probe status strings to counts for `files`.
        had_errors: `True` when any unfiltered result represents a hard error.
        diagnostics: Optional mapping from file path to public diagnostic entries
            for the probe result set.
        diagnostic_totals: Aggregate diagnostic counts across the probe result set.

    Notes:
        This is the public API shape for `topmark.api.probe()`. It intentionally
        exposes resolution as stable primitive values and DTOs instead of returning
        `ProcessingContext`, `ResolutionProbeResult`, or other internal structures.
    """

    files: Sequence[ProbeFileResult]
    summary: Mapping[str, int]
    had_errors: bool
    diagnostics: dict[str, list[DiagnosticEntry]] | None = None
    diagnostic_totals: DiagnosticTotals | None = None


# Stable presentation/aggregation order for public outcomes.
@dataclass(frozen=True, kw_only=True, slots=True)
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
    bucket_key: str
    bucket_label: str


@dataclass(frozen=True, kw_only=True, slots=True)
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


@dataclass(frozen=True, kw_only=True, slots=True)
class ApiPipelineRun:
    """Resolved runtime state and pipeline results for one API execution.

    This value object is the low-level orchestration result returned by the
    internal API runtime helpers. It exposes the fully resolved runtime config,
    the selected file list, the produced processing contexts, and any fatal
    pipeline-level exit code.

    Attributes:
        effective_cfg: Final runtime config after layered discovery, runtime
            overlays, and execution-scoped adjustments.
        file_list: Files selected for pipeline execution after discovery and
            filtering.
        contexts: Processing contexts produced by pipeline execution. For probe
            runs, this may also include synthetic contexts representing missing
            or filtered explicit inputs.
        exit_code: Fatal pipeline-level exit code, if one was encountered.

    Notes:
        This object intentionally exposes internal processing contexts rather
        than stable public DTOs. Higher-level public API helpers are expected
        to normalize these contexts into stable machine-facing result objects
        such as [`RunResult`][topmark.api.types.RunResult] and
        [`ProbeRunResult`][topmark.api.types.ProbeRunResult].
    """

    effective_cfg: FrozenConfig
    file_list: list[Path]
    contexts: list[ProcessingContext]
    exit_code: ExitCode | None


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

    # How to identify and collapse "blank" lines around the header during insert/strip repairs.
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


PublicEmptyInsertModeLiteral: TypeAlias = Literal[
    "bytes_empty",
    "logical_empty",
    "whitespace_empty",
]
"""Public token type for configuring how TopMark classifies "empty" files.

These values intentionally mirror the internal `EmptyInsertMode.value` strings
without exposing the internal enum class as part of the public API.
"""

PublicHeaderMutationModeLiteral: TypeAlias = Literal[
    "all",
    "add_only",
    "update_only",
]
"""Public token type for configuring which header mutations are allowed.

These values intentionally mirror the internal `HeaderMutationMode.value`
strings without exposing the internal enum class as part of the public API.
"""

PublicReportScopeLiteral: TypeAlias = Literal[
    "actionable",
    "noncompliant",
    "all",
]
"""Public token type for selecting the returned run-result scope.

These values intentionally mirror the internal `ReportScope.value` strings
without exposing the internal enum class as part of the public API.
"""


PublicStreamEventKindLiteral: TypeAlias = Literal[
    "run_started",
    "file_result",
    "run_completed",
]
"""Discriminator values for public streaming API events."""


@dataclass(frozen=True, kw_only=True, slots=True)
class RunStartedEvent:
    """Public event emitted before processing selected files.

    Attributes:
        kind: Stable event discriminator. Always `"run_started"`.
        command: Public pipeline command that produced the event.
        selected_count: Number of selected real files known at run start. Probe
            streams may later emit synthetic file-result events for missing or
            explicitly filtered inputs.
        paths: Ordered selected file paths when the producer can expose them
            without materializing additional state.

    Notes:
        This event is intentionally small. It establishes the ordered stream and
        command identity without exposing internal runtime configuration or
        mutable pipeline contexts.
    """

    kind: Literal["run_started"]
    command: PipelineKindLiteral
    selected_count: int
    paths: Sequence[Path] = ()


@dataclass(frozen=True, kw_only=True, slots=True)
class FileResultEvent:
    """Public event carrying one content-processing file result.

    Attributes:
        kind: Stable event discriminator. Always `"file_result"`.
        command: Public command that produced the event. For this event shape,
            the command is `"check"` or `"strip"`.
        index: Zero-based event order among emitted file-result events.
        result: Stable public file-result DTO.

    Notes:
        The event carries a public [`FileResult`][topmark.api.types.FileResult]
        rather than internal [`ProcessingResult`][topmark.pipeline.result.ProcessingResult]
        state. This keeps future streaming APIs aligned with the existing stable
        public API surface.
    """

    kind: Literal["file_result"]
    command: Literal["check", "strip"]
    index: int
    result: FileResult


@dataclass(frozen=True, kw_only=True, slots=True)
class ProbeFileResultEvent:
    """Public event carrying one probe file result.

    Attributes:
        kind: Stable event discriminator. Always `"file_result"`.
        command: Public command that produced the event. Always `"probe"`.
        index: Zero-based event order among emitted probe-result events.
        result: Stable public probe-file-result DTO.

    Notes:
        Probe uses a dedicated event type because probe results describe
        file-type resolution rather than header compliance or write outcomes.
    """

    kind: Literal["file_result"]
    command: Literal["probe"]
    index: int
    result: ProbeFileResult


@dataclass(frozen=True, kw_only=True, slots=True)
class RunCompletedEvent:
    """Public event emitted after all file-result events have been produced.

    Attributes:
        kind: Stable event discriminator. Always `"run_completed"`.
        command: Public pipeline command that produced the event.
        summary: Public summary mapping for the emitted result view. For
            `check` and `strip`, keys are public outcome values. For `probe`,
            keys are public probe status strings.
        had_errors: Whether the full run encountered errors, including errors
            hidden from the emitted view by report filtering when applicable.
        skipped: Number of results excluded by report-scope filtering. Probe
            streams currently report `0`.
        written: Number of files successfully written for apply-mode content
            processing streams. Probe streams report `0`.
        failed: Number of files that failed to write for apply-mode content
            processing streams. Probe streams report `0`.
        diagnostic_totals: Aggregate diagnostics for the emitted view.
        diagnostic_totals_all: Aggregate diagnostics for the full run before
            report-scope filtering when available.

    Notes:
        End-of-run aggregation stays explicit so callers that consume file
        events incrementally can still make final decisions using the same
        summary and error semantics as the batch API.
    """

    kind: Literal["run_completed"]
    command: PipelineKindLiteral
    summary: Mapping[str, int]
    had_errors: bool
    skipped: int = 0
    written: int = 0
    failed: int = 0
    diagnostic_totals: DiagnosticTotals | None = None
    diagnostic_totals_all: DiagnosticTotals | None = None


ContentStreamEvent: TypeAlias = RunStartedEvent | FileResultEvent | RunCompletedEvent
"""Event union for future `check` and `strip` streaming APIs."""

ProbeStreamEvent: TypeAlias = RunStartedEvent | ProbeFileResultEvent | RunCompletedEvent
"""Event union for future `probe` streaming APIs."""

PublicStreamEvent: TypeAlias = ContentStreamEvent | ProbeStreamEvent
"""Union of all public streaming API event shapes."""


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
