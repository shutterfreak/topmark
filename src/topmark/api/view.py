# topmark:header:start
#
#   project      : TopMark
#   file         : view.py
#   file_relpath : src/topmark/api/view.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""View and packaging helpers for the public API.

These helpers convert internal `ProcessingContext` objects into stable,
JSON-friendly public shapes, apply view-level filtering where appropriate, and
assemble public run-result DTOs.

Why this exists:
- `check()` and `strip()` share post-run behavior: filtering, summaries, diagnostics, and counts.
- `probe()` has a different result contract but shares diagnostics and DTO packaging conventions.
- Keeping this logic in one place avoids drift between API functions and keeps the façade small.

This module performs no I/O and produces no formatted/ANSI output; presentation belongs to
CLI/UI layers.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from topmark.api.types import DiagnosticEntry
from topmark.api.types import DiagnosticTotals
from topmark.api.types import FileResult
from topmark.api.types import ProbeCandidateInfo
from topmark.api.types import ProbeFileResult
from topmark.api.types import ProbeRunResult
from topmark.api.types import RunResult
from topmark.core.logging import get_logger
from topmark.pipeline.outcomes import NO_REASON_PROVIDED
from topmark.pipeline.outcomes import ResultBucket
from topmark.pipeline.outcomes import classify_outcome
from topmark.pipeline.outcomes import map_bucket
from topmark.pipeline.reporting import ReportFilterResult
from topmark.pipeline.reporting import ReportScope
from topmark.pipeline.reporting import filter_results_for_report
from topmark.pipeline.status import PlanStatus
from topmark.pipeline.status import WriteStatus

if TYPE_CHECKING:
    from collections.abc import Callable
    from collections.abc import Mapping
    from collections.abc import Sequence

    from topmark.core.exit_codes import ExitCode
    from topmark.core.logging import TopmarkLogger
    from topmark.pipeline.context.model import ProcessingContext
    from topmark.pipeline.views import DiffView
    from topmark.resolution.probe import ResolutionProbeMatchSignals
    from topmark.resolution.probe import ResolutionProbeResult

logger: TopmarkLogger = get_logger(__name__)


def to_file_result(ctx: ProcessingContext, *, apply: bool) -> FileResult:
    """Convert a content-processing context into a public `FileResult`.

    Args:
        ctx: The source processing context.
        apply: Whether the run is in apply mode (affects outcome mapping).

    Returns:
        Public, JSON-friendly per-file result.
    """
    # Prefer a unified diff when available; otherwise None (human views may omit diffs).
    diff_view: DiffView | None = ctx.views.diff
    diff: str | None = diff_view.text if diff_view else None

    # Bucket: stable key plus display-oriented label. The key is stable; the
    # label may change between versions.
    bucket: ResultBucket = map_bucket(ctx, apply=apply)
    key: str = bucket.outcome.value
    label: str = bucket.reason or NO_REASON_PROVIDED

    return FileResult(
        path=Path(str(ctx.path)),
        outcome=classify_outcome(ctx, apply=apply),
        diff=diff,
        bucket_key=key,
        bucket_label=label,
    )


def _probe_match_tokens(match: ResolutionProbeMatchSignals) -> tuple[str, ...]:
    """Return stable public match-signal tokens for a probe candidate.

    Args:
        match: Internal probe match-signal object.

    Returns:
        Ordered public tokens describing resolver signals that contributed to the
        candidate match.
    """
    tokens: list[str] = []
    if match.extension:
        tokens.append("extension")
    if match.filename:
        tokens.append("filename")
    if match.pattern:
        tokens.append("pattern")
    if match.content_match:
        tokens.append("content")
    # Expose content-read failures as a signal token, not as the raw internal
    # error payload.
    if match.content_error is not None:
        tokens.append("content_error")
    return tuple(tokens)


def _probe_candidate_infos(probe: ResolutionProbeResult) -> tuple[ProbeCandidateInfo, ...]:
    """Return normalized public candidate DTOs for an internal probe result.

    Args:
        probe: Internal resolution probe result.

    Returns:
        Candidate information in deterministic resolver order.
    """
    # Preserve resolver order. Public consumers get rank/selected/matched_by but
    # not matcher objects, registry entries, or raw content diagnostics.
    return tuple(
        ProbeCandidateInfo(
            file_type=candidate.local_key,
            qualified_key=candidate.qualified_key,
            score=candidate.score,
            selected=candidate.selected,
            rank=candidate.tie_break_rank,
            matched_by=_probe_match_tokens(candidate.match),
        )
        for candidate in probe.candidates
    )


def to_probe_file_result(ctx: ProcessingContext) -> ProbeFileResult:
    """Convert a `ProcessingContext` into a public `ProbeFileResult`.

    Args:
        ctx: The source processing context from the probe pipeline, including
            real and synthetic contexts.

    Returns:
        Public, JSON-friendly probe result for one path.
    """
    probe: ResolutionProbeResult | None = ctx.resolution_probe
    if probe is None:
        # This should not happen for the probe pipeline. Keep the public API
        # robust if a future internal step halts before attaching a probe result.
        bucket: ResultBucket = map_bucket(ctx, apply=False)
        return ProbeFileResult(
            path=Path(str(ctx.path)),
            status=bucket.outcome.value,
            reason=bucket.reason or NO_REASON_PROVIDED,
            selected_file_type=None,
            selected_processor=None,
            candidates=(),
        )

    return ProbeFileResult(
        path=Path(str(probe.path)),
        status=probe.status.value,
        reason=probe.reason.value,
        selected_file_type=(
            probe.selected_file_type.local_key if probe.selected_file_type is not None else None
        ),
        selected_processor=(
            probe.selected_processor.local_key if probe.selected_processor is not None else None
        ),
        candidates=_probe_candidate_infos(probe),
    )


def summarize_file_results(files: Sequence[FileResult]) -> Mapping[str, int]:
    """Count occurrences of each `Outcome` value.

    Args:
        files: File results to aggregate.

    Returns:
        Outcome label to count mapping.
    """
    counts: dict[str, int] = {}
    for fr in files:
        counts[fr.outcome.value] = counts.get(fr.outcome.value, 0) + 1
    return counts


def summarize_probe_file_results(files: Sequence[ProbeFileResult]) -> Mapping[str, int]:
    """Count occurrences of each public probe status.

    Args:
        files: Probe file results to aggregate.

    Returns:
        Mapping from public probe status string to count.
    """
    counts: dict[str, int] = {}
    for fr in files:
        counts[fr.status] = counts.get(fr.status, 0) + 1
    return counts


def count_writes(
    results: Sequence[ProcessingContext],
    *,
    apply: bool,
    eligible: set[PlanStatus],
) -> tuple[int, int]:
    """Return `(written, failed)` counts for the given results.

    Args:
        results: Pipeline results.
        apply: Whether the run was in apply mode (counts are zero when False).
        eligible: Which `WriteStatus` values count as "written".

    Returns:
        The `(written, failed)` counts.
    """
    if not apply:
        return 0, 0
    written: int = sum(
        1 for r in results if r.status.plan in eligible and r.status.write == WriteStatus.WRITTEN
    )
    failed: int = sum(1 for r in results if r.status.write == WriteStatus.FAILED)
    return written, failed


def collect_diagnostics(
    results: list[ProcessingContext],
) -> dict[str, list[DiagnosticEntry]]:
    """Collect per-file diagnostics as `{path: [diagnostic, ...]}`.

    Diagnostics are returned in the *public* JSON-friendly shape and do not
    expose internal classes or enums.

    Args:
        results: Pipeline results (typically the filtered view).

    Returns:
        Mapping from file path to diagnostic entries.
    """
    diags: dict[str, list[DiagnosticEntry]] = {}
    for r in results:
        if r.diagnostics:
            diags[str(r.path)] = [
                DiagnosticEntry(
                    level=d.level.value,
                    message=d.message,
                )
                for d in r.diagnostics
            ]
    return diags


def collect_diagnostic_totals(results: list[ProcessingContext]) -> DiagnosticTotals:
    """Return aggregate counts of diagnostics across the given results.

    Args:
        results: Pipeline results (typically the filtered view).

    Returns:
        Aggregate counts (info/warning/error/total).
    """
    total_info: int = 0
    total_warn: int = 0
    total_error: int = 0
    for r in results:
        if not r.diagnostics:
            continue
        for d in r.diagnostics:
            match d.level.value:
                case "info":
                    total_info += 1
                case "warning":
                    total_warn += 1
                case "error":
                    total_error += 1
    total: int = total_info + total_warn + total_error
    return DiagnosticTotals(
        info=total_info,
        warning=total_warn,
        error=total_error,
        total=total,
    )


def finalize_run_result(
    *,
    results: list[ProcessingContext],
    file_list: list[Path],
    apply: bool,
    report_scope: ReportScope,
    would_change: Callable[[ProcessingContext], bool],
    update_statuses: set[PlanStatus],
    encountered_error_code: ExitCode | None,
) -> RunResult:
    """Assemble a `RunResult` from pipeline results with consistent report filtering.

    This helper centralizes common post-run logic used by `check()` and `strip()`
    to avoid duplication and drift (report filtering, summarization, diagnostics,
    and write/failed counts).

    Args:
        results: Raw pipeline results (unfiltered).
        file_list: Resolved input files for the run.
        apply: Whether the run was in apply mode (affects counting).
        report_scope: Active report scope for the current view.
        would_change: Predicate describing whether a result represents a file
            TopMark would change (or did change, depending on caller context).
        update_statuses: Which `PlanStatus` values count as written/updated.
        encountered_error_code: Fatal exit code if any was encountered.

    Returns:
        Public, JSON-friendly bundle with per-file results and aggregates.
    """
    if not file_list:
        return RunResult(
            files=(),
            summary={},
            had_errors=False,
        )

    filtered: ReportFilterResult = filter_results_for_report(
        results,
        report_scope=report_scope,
        would_change=would_change,
    )
    view_results: list[ProcessingContext] = filtered.view_results
    files: tuple[FileResult, ...] = tuple(
        to_file_result(
            r,
            apply=apply,
        )
        for r in view_results
    )
    summary: Mapping[str, int] = summarize_file_results(files)

    diagnostics: dict[str, list[DiagnosticEntry]] = collect_diagnostics(view_results)
    diagnostic_totals: DiagnosticTotals = collect_diagnostic_totals(view_results)
    diagnostic_totals_all: DiagnosticTotals = collect_diagnostic_totals(results)
    had_errors: bool = (diagnostic_totals_all["error"] > 0) or (encountered_error_code is not None)

    written: int
    failed: int
    written, failed = count_writes(results, apply=apply, eligible=update_statuses)

    bucket_summary: dict[str, int] = {}
    for fr in files:
        # Each FileResult already carries bucket_key. If absent, recompute from ctx.
        if fr.bucket_key:
            b_key: str = fr.bucket_key
        else:
            # If you already track the surviving contexts in this scope as `view_ctxs`,
            # you can recompute with map_result_bucket(ctx). Otherwise, keep it simple:
            b_key = fr.outcome.value  # harmless fallback (shouldn't happen)
        bucket_summary[b_key] = bucket_summary.get(b_key, 0) + 1

    return RunResult(
        files=files,
        summary=summary,
        had_errors=had_errors,
        skipped=filtered.skipped_count,
        written=written,
        failed=failed,
        bucket_summary=bucket_summary,
        diagnostics=diagnostics,
        diagnostic_totals=diagnostic_totals,
        diagnostic_totals_all=diagnostic_totals_all,
    )


def finalize_probe_result(
    *,
    results: list[ProcessingContext],
    file_list: list[Path],
    encountered_error_code: ExitCode | None,
) -> ProbeRunResult:
    """Assemble a `ProbeRunResult` from probe pipeline results.

    Probe results are intentionally not routed through `finalize_run_result()`:
    probing explains file-type resolution rather than header compliance or file
    mutation. This helper maps each internal `ResolutionProbeResult` into stable
    public DTOs and summarizes by public probe status.

    Args:
        results: Raw probe pipeline results, including synthetic contexts for
            discovery-filtered explicit inputs when supplied by the caller.
        file_list: Resolved input files for the run. Used only to preserve the
            empty-run behavior shared with other API entry points.
        encountered_error_code: Fatal exit code if any was encountered.

    Returns:
        Public, JSON-friendly probe result bundle.
    """
    if not file_list and not results:
        return ProbeRunResult(
            files=(),
            summary={},
            had_errors=False,
        )

    files: tuple[ProbeFileResult, ...] = tuple(to_probe_file_result(r) for r in results)
    summary: Mapping[str, int] = summarize_probe_file_results(files)

    diagnostics: dict[str, list[DiagnosticEntry]] = collect_diagnostics(results)
    diagnostic_totals: DiagnosticTotals = collect_diagnostic_totals(results)
    had_errors: bool = (diagnostic_totals["error"] > 0) or (encountered_error_code is not None)

    return ProbeRunResult(
        files=files,
        summary=summary,
        had_errors=had_errors,
        diagnostics=diagnostics,
        diagnostic_totals=diagnostic_totals,
    )
