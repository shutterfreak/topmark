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
from typing import TYPE_CHECKING, Mapping, Sequence

from topmark.api.public_types import PublicDiagnostic
from topmark.cli.cmd_common import filter_view_results
from topmark.config.logging import TopmarkLogger, get_logger
from topmark.pipeline.context import (
    ComparisonStatus,
    ProcessingContext,
    ResolveStatus,
    WriteStatus,
)

from .types import DiagnosticTotals, FileResult, Outcome, RunResult

if TYPE_CHECKING:
    from topmark.cli_shared.exit_codes import ExitCode

    from .public_types import PublicDiagnostic

logger: TopmarkLogger = get_logger(__name__)

__all__: list[str] = [
    "map_outcome",
    "to_file_result",
    "apply_view_filter",
    "summarize",
    "collect_diagnostics",
    "collect_diagnostic_totals",
    "count_writes",
    "finalize_run_result",
]


def map_outcome(r: ProcessingContext, *, apply: bool) -> Outcome:
    """Translate a `ProcessingContext` status into a public `Outcome`.

    Args:
        r (ProcessingContext): The processing context to classify.
        apply (bool): Whether the run is in apply mode; influences CHANGED/Would-change.

    Returns:
        Outcome: The public outcome classification.

    Notes:
        - Non-resolved *skipped* statuses (e.g., unsupported or known-no-headers)
          are treated as `UNCHANGED` in the API layer.
        - When `apply=False`, changed files are reported as `WOULD_CHANGE`.
        - When `apply=True`, changed files are reported as `CHANGED`.
    """
    if r.status.resolve != ResolveStatus.RESOLVED:
        # Treat unsupported/matched-but-unhandled types as non-errors for API consumers.
        unsupported: set[ResolveStatus] = {
            ResolveStatus.UNSUPPORTED,
            ResolveStatus.TYPE_RESOLVED_HEADERS_UNSUPPORTED,
        }
        if r.status.resolve in unsupported:
            return Outcome.UNCHANGED
        return Outcome.ERROR
    if r.status.comparison == ComparisonStatus.UNCHANGED:
        return Outcome.UNCHANGED
    # At this point the file either would change or did change.
    if apply:
        # In apply mode, run_steps_for_files computes updates; caller may write them.
        return Outcome.CHANGED
    # Dry-run: would change
    return Outcome.WOULD_CHANGE


def to_file_result(r: ProcessingContext, *, apply: bool) -> FileResult:
    """Convert a `ProcessingContext` into a public `FileResult`.

    Args:
        r (ProcessingContext): The source processing context.
        apply (bool): Whether the run is in apply mode (affects outcome mapping).

    Returns:
        FileResult: Public, JSON-friendly per-file result.
    """
    # Prefer a unified diff when available; otherwise None (human views may omit diffs).
    diff: str | None = r.diff.text if r.diff else None
    message: str | None = r.summary or None
    return FileResult(
        path=Path(str(r.path)), outcome=map_outcome(r, apply=apply), diff=diff, message=message
    )


def apply_view_filter(
    results: list[ProcessingContext],
    *,
    skip_compliant: bool,
    skip_unsupported: bool,
) -> tuple[list[ProcessingContext], int]:
    """Apply view filtering and return `(filtered_results, skipped_count)`.

    Args:
        results (list[ProcessingContext]): Raw pipeline results.
        skip_compliant (bool): If `True`, hide compliant files.
        skip_unsupported (bool): If `True`, hide unsupported files.

    Returns:
        tuple[list[ProcessingContext], int]: The filtered results and the number of
            results excluded by view-level filtering.
    """
    view_results: list[ProcessingContext] = filter_view_results(
        results, skip_compliant=skip_compliant, skip_unsupported=skip_unsupported
    )
    skipped: int = len(results) - len(view_results)
    return view_results, skipped


def summarize(files: Sequence[FileResult]) -> Mapping[str, int]:
    """Count occurrences of each `Outcome` value.

    Args:
        files (Sequence[FileResult]): File results to aggregate.

    Returns:
        Mapping[str, int]: Outcome label to count mapping.
    """
    counts: dict[str, int] = {}
    for fr in files:
        counts[fr.outcome.value] = counts.get(fr.outcome.value, 0) + 1
    return counts


def count_writes(
    results: Sequence[ProcessingContext],
    *,
    apply: bool,
    eligible: set[WriteStatus],
) -> tuple[int, int]:
    """Return `(written, failed)` counts for the given results.

    Args:
        results (Sequence[ProcessingContext]): Pipeline results.
        apply (bool): Whether the run was in apply mode (counts are zero when False).
        eligible (set[WriteStatus]): Which `WriteStatus` values count as "written".

    Returns:
        tuple[int, int]: The `(written, failed)` counts.
    """
    if not apply:
        return 0, 0
    written: int = sum(1 for r in results if r.status.write in eligible)
    failed: int = sum(1 for r in results if r.status.write == WriteStatus.FAILED)
    return written, failed


def collect_diagnostics(
    results: list[ProcessingContext],
) -> dict[str, list[PublicDiagnostic]]:
    """Collect per-file diagnostics as `{path: [diagnostic, ...]}`.

    Diagnostics are returned in the *public* JSON-friendly shape and do not
    expose internal classes or enums.

    Args:
        results (list[ProcessingContext]): Pipeline results (typically the filtered view).

    Returns:
        dict[str, list[PublicDiagnostic]]: Mapping from file path to diagnostic entries.
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
        results (list[ProcessingContext]): Pipeline results (typically the filtered view).

    Returns:
        DiagnosticTotals: Aggregate counts (info/warning/error/total).
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
    write_statuses: set[WriteStatus],
    encountered_error_code: "ExitCode | None",
) -> RunResult:
    """Assemble a `RunResult` from pipeline results with consistent view filtering.

    This helper centralizes common post-run logic used by `check()` and `strip()`
    to avoid duplication and drift (filtering, summarization, diagnostics, and
    write/failed counts).

    Args:
        results (list[ProcessingContext]): Raw pipeline results (unfiltered).
        file_list (list[Path]): Resolved input files for the run.
        apply (bool): Whether the run was in apply mode (affects counting).
        skip_compliant (bool): If `True`, hide compliant files in the returned view.
        skip_unsupported (bool): If `True`, hide unsupported files in the view.
        write_statuses (set[WriteStatus]): Which `WriteStatus` values count as "written".
        encountered_error_code (ExitCode | None): Fatal exit code if any was encountered.

    Returns:
        RunResult: Public, JSON-friendly bundle with per-file results and aggregates.
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

    had_errors: bool = any(map_outcome(r, apply=apply) == Outcome.ERROR for r in results) or (
        encountered_error_code is not None
    )

    diagnostics: dict[str, list[PublicDiagnostic]] = collect_diagnostics(view_results)
    diagnostic_totals: DiagnosticTotals = collect_diagnostic_totals(view_results)
    diagnostic_totals_all: DiagnosticTotals = collect_diagnostic_totals(results)

    written: int
    failed: int
    written, failed = count_writes(results, apply=apply, eligible=write_statuses)

    return RunResult(
        files=files,
        summary=summary,
        had_errors=had_errors,
        skipped=skipped,
        written=written,
        failed=failed,
        diagnostics=diagnostics,
        diagnostic_totals=diagnostic_totals,
        diagnostic_totals_all=diagnostic_totals_all,
    )
