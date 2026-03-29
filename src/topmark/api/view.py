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

These helpers convert internal `ProcessingContext` objects into stable, JSON-friendly public
shapes, apply view-level filtering, and assemble a `RunResult`.

Why this exists:
- `check()` and `strip()` share post-run behavior (filtering, summaries, diagnostics, counts).
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

    from topmark.api.types import DiagnosticEntry
    from topmark.core.exit_codes import ExitCode
    from topmark.core.logging import TopmarkLogger
    from topmark.pipeline.context.model import ProcessingContext
    from topmark.pipeline.views import DiffView

logger: TopmarkLogger = get_logger(__name__)


def to_file_result(ctx: ProcessingContext, *, apply: bool) -> FileResult:
    """Convert a `ProcessingContext` into a public `FileResult`.

    Args:
        ctx: The source processing context.
        apply: Whether the run is in apply mode (affects outcome mapping).

    Returns:
        Public, JSON-friendly per-file result.
    """
    # Prefer a unified diff when available; otherwise None (human views may omit diffs).
    diff_view: DiffView | None = ctx.views.diff
    diff: str | None = diff_view.text if diff_view else None

    # Bucket: CLI-style key + human label (label may change between versions).
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


def summarize(files: Sequence[FileResult]) -> Mapping[str, int]:
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
                {"level": d.level.value, "message": d.message} for d in r.diagnostics
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
            lv: str = d.level.value
            if lv == "info":
                total_info += 1
            elif lv == "warning":
                total_warn += 1
            elif lv == "error":
                total_error += 1
    total: int = total_info + total_warn + total_error
    return {"info": total_info, "warning": total_warn, "error": total_error, "total": total}


def finalize_run_result(
    *,
    results: list[ProcessingContext],
    file_list: list[Path],
    apply: bool,
    report: ReportScope,
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
        report: Public report-scope selection for the returned view.
        would_change: Predicate describing whether a result represents a file
            TopMark would change (or did change, depending on caller context).
        update_statuses: Which `PlanStatus` values count as written/updated.
        encountered_error_code: Fatal exit code if any was encountered.

    Returns:
        Public, JSON-friendly bundle with per-file results and aggregates.
    """
    if not file_list:
        return RunResult(files=(), summary={}, had_errors=False)

    filtered: ReportFilterResult = filter_results_for_report(
        results,
        report=report,
        would_change=would_change,
    )
    view_results: list[ProcessingContext] = filtered.view_results
    files: tuple[FileResult, ...] = tuple(to_file_result(r, apply=apply) for r in view_results)
    summary: Mapping[str, int] = summarize(files)

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
