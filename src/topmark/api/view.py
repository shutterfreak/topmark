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
JSON-friendly public shapes, apply user-visible filters, and assemble
`RunResult` summaries. Keeping them separate from `api.__init__` avoids
duplication between `check()` and `strip()` and keeps the public surface tidy.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from topmark.api.public_types import PublicDiagnostic
from topmark.config.logging import get_logger
from topmark.pipeline.outcomes import (
    NO_REASON_PROVIDED,
    ResultBucket,
    classify_outcome,
    map_bucket,
)
from topmark.pipeline.status import (
    ComparisonStatus,
    ContentStatus,
    GenerationStatus,
    PlanStatus,
    ResolveStatus,
    StripStatus,
    WriteStatus,
)

from .types import DiagnosticTotals, FileResult, RunResult

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from topmark.api.public_types import PublicDiagnostic
    from topmark.config.logging import TopmarkLogger
    from topmark.core.exit_codes import ExitCode
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

    # Compute CLI bucket for API visibility (key + human label)
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


# --- View filtering helpers ---------------------------------------------------


def filter_view_results(
    results: list[ProcessingContext],
    *,
    skip_compliant: bool,
    skip_unsupported: bool,
) -> list[ProcessingContext]:
    """Apply --skip-compliant and --skip-unsupported filters to a results list.

    Args:
        results: Full list of ProcessingContext results.
        skip_compliant: If True, filter out files that are compliant/unchanged.
        skip_unsupported: If True, filter out files that were skipped as unsupported.

    Returns:
        Filtered list of ProcessingContext results.
    """
    view: list[ProcessingContext] = results
    if skip_compliant:
        view = [
            r
            for r in view
            if not (
                r.status.resolve == ResolveStatus.RESOLVED
                and r.status.content == ContentStatus.OK
                and (
                    # “check/update” style: rendered or no-fields and unchanged
                    (
                        r.status.comparison == ComparisonStatus.UNCHANGED
                        and r.status.generation
                        in {
                            GenerationStatus.GENERATED,
                            GenerationStatus.NO_FIELDS,
                        }
                    )
                    # “strip” style: nothing to strip (image unchanged is implied)
                    or r.status.strip == StripStatus.NOT_NEEDED
                )
            )
        ]

    if skip_unsupported:
        view = [
            r
            for r in view
            if r.status.resolve
            not in {
                ResolveStatus.UNSUPPORTED,
                ResolveStatus.TYPE_RESOLVED_HEADERS_UNSUPPORTED,
                ResolveStatus.TYPE_RESOLVED_NO_PROCESSOR_REGISTERED,
            }
        ]

    return view


def apply_view_filter(
    results: list[ProcessingContext],
    *,
    skip_compliant: bool,
    skip_unsupported: bool,
) -> tuple[list[ProcessingContext], int]:
    """Apply view filtering and return `(filtered_results, skipped_count)`.

    Args:
        results: Raw pipeline results.
        skip_compliant: If `True`, hide compliant files.
        skip_unsupported: If `True`, hide unsupported files.

    Returns:
        The filtered results and the number of results excluded by view-level filtering.
    """
    view_results: list[ProcessingContext] = filter_view_results(
        results, skip_compliant=skip_compliant, skip_unsupported=skip_unsupported
    )
    skipped: int = len(results) - len(view_results)
    return view_results, skipped


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
) -> dict[str, list[PublicDiagnostic]]:
    """Collect per-file diagnostics as `{path: [diagnostic, ...]}`.

    Diagnostics are returned in the *public* JSON-friendly shape and do not
    expose internal classes or enums.

    Args:
        results: Pipeline results (typically the filtered view).

    Returns:
        Mapping from file path to diagnostic entries.
    """
    diags: dict[str, list[PublicDiagnostic]] = {}
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
    skip_compliant: bool,
    skip_unsupported: bool,
    update_statuses: set[PlanStatus],
    encountered_error_code: ExitCode | None,
) -> RunResult:
    """Assemble a `RunResult` from pipeline results with consistent view filtering.

    This helper centralizes common post-run logic used by `check()` and `strip()`
    to avoid duplication and drift (filtering, summarization, diagnostics, and
    write/failed counts).

    Args:
        results: Raw pipeline results (unfiltered).
        file_list: Resolved input files for the run.
        apply: Whether the run was in apply mode (affects counting).
        skip_compliant: If `True`, hide compliant files in the returned view.
        skip_unsupported: If `True`, hide unsupported files in the view.
        update_statuses: Which `UpdateStatus` values count as "updated".
        encountered_error_code: Fatal exit code if any was encountered.

    Returns:
        Public, JSON-friendly bundle with per-file results and aggregates.
    """
    if not file_list:
        return RunResult(files=(), summary={}, had_errors=False)

    view_results: list[ProcessingContext]
    skipped: int
    view_results, skipped = apply_view_filter(
        results, skip_compliant=skip_compliant, skip_unsupported=skip_unsupported
    )
    files: tuple[FileResult, ...] = tuple(to_file_result(r, apply=apply) for r in view_results)
    summary: Mapping[str, int] = summarize(files)

    diagnostics: dict[str, list[PublicDiagnostic]] = collect_diagnostics(view_results)
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
        bucket_summary=bucket_summary,
        had_errors=had_errors,
        skipped=skipped,
        written=written,
        failed=failed,
        diagnostics=diagnostics,
        diagnostic_totals=diagnostic_totals,
        diagnostic_totals_all=diagnostic_totals_all,
    )


__all__: list[str] = [
    "apply_view_filter",
    "collect_diagnostic_totals",
    "collect_diagnostics",
    "count_writes",
    "finalize_run_result",
    "summarize",
    "to_file_result",
]
