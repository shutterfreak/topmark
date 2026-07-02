# topmark:header:start
#
#   project      : TopMark
#   file         : pipeline.py
#   file_relpath : src/topmark/presentation/shared/pipeline.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Shared pipeline presentation models and utilities (Click-free).

This module defines the presentation payload shared by human-facing pipeline
renderers for `topmark check` and `topmark strip`.

Scope:
    - Provide immutable report models consumed by TEXT and Markdown renderers.
    - Centralize small display helpers that must remain consistent across human
      formats.
    - Avoid Click, console, and I/O dependencies; callers are responsible for
      building reports, rendering strings, and printing output.

TEXT renderers may use `verbosity_level` and `styled` for console-oriented
progressive disclosure. Markdown renderers treat Markdown as document-oriented
output and ignore TEXT-only verbosity and styling controls.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from topmark.pipeline.outcomes import map_bucket
from topmark.pipeline.status import FsStatus

if TYPE_CHECKING:
    from collections.abc import Sequence

    from topmark.pipeline.context.model import ProcessingContext
    from topmark.pipeline.kinds import PipelineKindLiteral
    from topmark.pipeline.outcomes import ResultBucket
    from topmark.pipeline.reporting import ReportScope
    from topmark.pipeline.result import ProcessingResult


@dataclass(frozen=True, kw_only=True, slots=True)
class ProbeCommandHumanReport:
    """Prepared payload for human-facing pipeline probe command renderers.

    The report is shared by human-facing renderers for `topmark probe`. It
    contains only presentation-ready data and policy flags; it does not perform
    rendering, Click interaction, or console output.

    Attributes:
        verbosity_level: Effective TEXT verbosity; Markdown renderers ignore it.
        styled: Whether TEXT renderers should apply styling; Markdown renderers ignore it.
        pipeline_kind: Pipeline kind used to select command-specific guidance.
        file_list_total: Total number of candidate files before view filtering.
        view_results: Durable probe results selected for the current human-output view.
    """

    verbosity_level: int
    styled: bool
    pipeline_kind: PipelineKindLiteral
    file_list_total: int
    view_results: Sequence[ProcessingResult]


@dataclass(frozen=True, kw_only=True, slots=True)
class PipelineHumanPresentationOptions:
    """Configuration for human-facing pipeline command presentation.

    The options are shared by TEXT and Markdown presentation paths for
    `topmark check` and `topmark strip`. They describe how stream-derived
    processing results should be rendered, but intentionally do not carry
    realized result state such as file totals, filtered views, or unsupported
    counts.

    Attributes:
        verbosity_level: Effective TEXT verbosity; Markdown renderers ignore it.
        styled: Whether TEXT renderers should apply styling; Markdown renderers ignore it.
        pipeline_kind: Pipeline kind used to select command-specific guidance.
        report_scope: Active report scope for the current view.
        summary_mode: Whether to render grouped outcome counts instead of per-file sections.
        show_diffs: Whether to render unified diffs as separate payload output.
        apply_changes: Whether the command runs in apply mode.
    """

    verbosity_level: int
    styled: bool
    pipeline_kind: PipelineKindLiteral
    report_scope: ReportScope
    summary_mode: bool
    show_diffs: bool
    apply_changes: bool


@dataclass(frozen=True, kw_only=True, slots=True)
class PipelineCommandHumanReport:
    """Prepared payload for human-facing pipeline command renderers.

    The report is shared by TEXT and Markdown renderers for `topmark check` and
    `topmark strip`. It contains realized presentation state derived from a
    completed stream plus policy flags; it does not perform rendering, Click
    interaction, or console output.

    Attributes:
        verbosity_level: Effective TEXT verbosity; Markdown renderers ignore it.
        styled: Whether TEXT renderers should apply styling; Markdown renderers ignore it.
        pipeline_kind: Pipeline kind used to select command-specific guidance.
        file_list_total: Total number of user-requested results before view filtering,
            including selected pipeline files and synthetic resolver-level outcomes.
        view_results: Durable processing results selected for the current human-output view.
        report_scope: Active report scope for the current view.
        unsupported_count: Number of unsupported files omitted from actionable listings.
        summary_mode: Whether to render grouped outcome counts instead of per-file sections.
        show_diffs: Whether to render unified diffs as separate payload output.
        apply_changes: Whether the command runs in apply mode.
    """

    verbosity_level: int
    styled: bool
    pipeline_kind: PipelineKindLiteral
    file_list_total: int
    view_results: Sequence[ProcessingResult]
    report_scope: ReportScope
    unsupported_count: int
    summary_mode: bool
    show_diffs: bool
    apply_changes: bool


@dataclass(frozen=True, kw_only=True, slots=True)
class PipelineFileSummary:
    """Format-neutral one-line pipeline summary data.

    The summary captures the common semantic fields used by TEXT and Markdown
    per-file renderers. Format-specific renderers remain responsible for path
    decoration, Markdown escaping, terminal styling, and verbosity-specific
    nudges.

    Attributes:
        file_type_label: Human-facing file-type label, or `None` when omitted.
        bucket: Public result bucket for the result execution mode.
        key: Bucket outcome value for compact human display.
        label: Bucket reason for compact human display.
        secondary_parts: Additional compact suffix entries, in priority order.
        diagnostic_total: Number of diagnostics attached to the result.
    """

    file_type_label: str | None
    bucket: ResultBucket
    key: str
    label: str
    secondary_parts: tuple[str, ...]
    diagnostic_total: int


@dataclass(frozen=True, kw_only=True, slots=True)
class PipelineCommandHumanOutput:
    """Rendered human pipeline command output split by output stream.

    The split keeps payload output and report output separate without coupling
    presentation renderers to Click, Rich console objects, or concrete stream
    handles. Commands remain responsible for writing `stdout` and `stderr` to
    the appropriate streams.

    Attributes:
        stdout: Payload-oriented output intended for standard output.
        stderr: Human report, guidance, summary, or diagnostic output intended
            for standard error when standard output is reserved for a payload.
    """

    stdout: str
    stderr: str


def get_file_type_label(
    ctx: ProcessingContext | ProcessingResult,
) -> str | None:
    """Return the human-facing file-type label for a pipeline result.

    Resolved files use their local file-type key. Unresolved files usually render
    as ``<unknown>`` so users can see that type resolution did not complete.
    Synthetic missing-file contexts are the exception: they are created by file
    resolution before type resolution can run, so they omit the file-type segment
    entirely.

    This keeps missing-file output concise:

    ```text
    fubar: error: not_found
    ```

    while still preserving useful context if a file was resolved before a later
    filesystem failure.

    Args:
        ctx: Processing context or durable result to inspect.

    Returns:
        File-type label for human output, or `None` when the file-type segment
        should be omitted.
    """
    if ctx.file_type is not None:
        return ctx.file_type.local_key
    if ctx.status.fs == FsStatus.NOT_FOUND:
        return None
    return "<unknown>"


def summarize_pipeline_file(
    result: ProcessingResult,
) -> PipelineFileSummary:
    """Build format-neutral compact summary data for one pipeline result.

    TEXT and Markdown per-file renderers intentionally differ in styling,
    escaping, and progressive disclosure. This helper centralizes the shared
    semantic selection so both renderers describe write status, diffs, and
    diagnostics consistently without sharing terminal or Markdown concerns.

    Args:
        result: Durable processing result to summarize.

    Returns:
        Presentation-ready summary data for human renderers.
    """
    apply_changes: bool = result.execution_mode.apply_changes is True
    bucket: ResultBucket = map_bucket(result, apply=apply_changes)

    secondary_parts: list[str] = []
    if result.status.has_write_outcome():
        secondary_parts.append(result.status.write.value)
    elif result.detail.diff_text:
        secondary_parts.append("diff")

    diagnostic_total: int = 0
    if result.diagnostics:
        diagnostic_total = result.diagnostics.stats().total
        triage_summary: str = result.diagnostics.stats().triage_summary()
        # Triage summary is nonempty if there are diagnostics:
        secondary_parts.append(triage_summary)

    return PipelineFileSummary(
        file_type_label=get_file_type_label(result),
        bucket=bucket,
        key=bucket.outcome.value,
        label=bucket.reason or "(no reason provided)",
        secondary_parts=tuple(secondary_parts),
        diagnostic_total=diagnostic_total,
    )
