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

from yachalk import chalk

from topmark.api.public_types import PublicDiagnostic
from topmark.config.logging import get_logger
from topmark.core.diagnostics import DiagnosticLevel, DiagnosticStats
from topmark.core.enum_mixins import enum_from_name
from topmark.pipeline.hints import Cluster, Hint
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

    from topmark.config.logging import TopmarkLogger
    from topmark.core.exit_codes import ExitCode
    from topmark.pipeline.context.model import ProcessingContext
    from topmark.pipeline.views import DiffView
    from topmark.rendering.colored_enum import Colorizer

    from .public_types import PublicDiagnostic

logger: TopmarkLogger = get_logger(__name__)


def to_file_result(r: ProcessingContext, *, apply: bool) -> FileResult:
    """Convert a `ProcessingContext` into a public `FileResult`.

    Args:
        r (ProcessingContext): The source processing context.
        apply (bool): Whether the run is in apply mode (affects outcome mapping).

    Returns:
        FileResult: Public, JSON-friendly per-file result.
    """
    # Prefer a unified diff when available; otherwise None (human views may omit diffs).
    diff_view: DiffView | None = r.views.diff
    diff: str | None = diff_view.text if diff_view else None
    message: str | None = format_summary(r) or None

    # Compute CLI bucket for API visibility (key + human label)
    bucket: ResultBucket = map_bucket(r, apply=apply)
    key: str = bucket.outcome.value
    label: str = bucket.reason or NO_REASON_PROVIDED

    return FileResult(
        path=Path(str(r.path)),
        outcome=classify_outcome(r, apply=apply),
        diff=diff,
        message=message,
        bucket_key=key,
        bucket_label=label,
    )


# --- CLI presentation helpers -------------------------------------------------


def filter_view_results(
    results: list[ProcessingContext],
    *,
    skip_compliant: bool,
    skip_unsupported: bool,
) -> list[ProcessingContext]:
    """Apply --skip-compliant and --skip-unsupported filters to a results list.

    Args:
        results (list[ProcessingContext]): Full list of ProcessingContext results.
        skip_compliant (bool): If True, filter out files that are compliant/unchanged.
        skip_unsupported (bool): If True, filter out files that were skipped as unsupported.

    Returns:
        list[ProcessingContext]: Filtered list of ProcessingContext results.
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
    eligible: set[PlanStatus],
) -> tuple[int, int]:
    """Return `(written, failed)` counts for the given results.

    Args:
        results (Sequence[ProcessingContext]): Pipeline results.
        apply (bool): Whether the run was in apply mode (counts are zero when False).
        eligible (set[PlanStatus]): Which `WriteStatus` values count as "written".

    Returns:
        tuple[int, int]: The `(written, failed)` counts.
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
    update_statuses: set[PlanStatus],
    encountered_error_code: ExitCode | None,
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
        update_statuses (set[PlanStatus]): Which `UpdateStatus` values count as "updated".
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


def format_summary(ctx: ProcessingContext) -> str:
    """Return a concise, human‑readable one‑liner for this file.

    The summary is aligned with TopMark's pipeline phases and mirrors what
    comparable tools (e.g., *ruff*, *black*, *prettier*) surface: a clear
    primary outcome plus a few terse hints.

    Rendering rules:
        1. Primary bucket comes from the view-layer classification helper
            `map_bucket()` in `topmark.api.view`. This ensures stable wording
            across commands and pipelines.
        2. If a write outcome is known (e.g., PREVIEWED/WRITTEN/INSERTED/REMOVED),
            append it as a trailing hint.
        3. If there is a diff but no write outcome (e.g., check/summary with
            `--diff`), append a "diff" hint.
        4. If diagnostics exist, append the diagnostic count as a hint.

    Verbose per‑line diagnostics are emitted only when Config.verbosity_level >= 1
    (treats None as 0).

    Examples (colors omitted here):
        path/to/file.py: python – would insert header - previewed
        path/to/file.py: python – up-to-date
        path/to/file.py: python – would strip header - diff - 2 issues

    Args:
        ctx (ProcessingContext): Processing context containing status and
            configuration.

    Returns:
        str: Human-readable one-line summary, possibly followed by
        additional lines for verbose diagnostics depending on the
        configuration verbosity level.
    """
    verbosity_level: int = ctx.config.verbosity_level or 0

    parts: list[str] = [f"{ctx.path}:"]

    # File type (dim), or <unknown> if resolution failed
    if ctx.file_type is not None:
        parts.append(chalk.dim(ctx.file_type.name))
    else:
        parts.append(chalk.dim("<unknown>"))

    head: Hint | None = None
    if not ctx.diagnostic_hints:
        key: str = "no_hint"
        label: str = "No diagnostic hints"
    else:
        head = ctx.diagnostic_hints.headline()
        if head is None:
            key = "no_hint"
            label = "No diagnostic hints"
        else:
            key = head.code
            label = f"{head.axis.value.title()}: {head.message}"
            logger.debug("Key: '%s', label: '%s'", key, label)

    # Color choice can still be simple or based on cluster:
    cluster: str | None = head.cluster if head else None
    # head.cluster now carries the cluster value (e.g. "changed") but
    # enum_from_name(Cluster, cluster) looks up by enum name (e.g. "CHANGED").
    # Hence we use case insensitive lookup:
    cluster_elem: Cluster | None = enum_from_name(
        Cluster,
        cluster,
        case_insensitive=True,
    )
    color_fn: Colorizer = cluster_elem.color if cluster_elem else chalk.red.italic

    parts.append("-")
    parts.append(color_fn(f"{key}: {label}"))

    # Secondary hints: write status > diff marker > diagnostics

    if ctx.status.has_write_outcome():
        parts.append("-")
        parts.append(ctx.status.write.color(ctx.status.write.value))
    elif ctx.views.diff and ctx.views.diff.text:
        parts.append("-")
        parts.append(chalk.yellow("diff"))

    diag_show_hint: str = ""
    if ctx.diagnostics:
        stats: DiagnosticStats = ctx.diagnostics.stats()
        n_info: int = stats.n_info
        n_warn: int = stats.n_warning
        n_err: int = stats.n_error
        parts.append("-")
        # Compose a compact triage summary like "1 error, 2 warnings"
        triage: list[str] = []
        if verbosity_level <= 0:
            diag_show_hint = chalk.dim.italic(" (use '-v' to view)")
        if n_err:
            triage.append(chalk.red_bright(f"{n_err} error" + ("s" if n_err != 1 else "")))
        if n_warn:
            triage.append(chalk.yellow(f"{n_warn} warning" + ("s" if n_warn != 1 else "")))
        if n_info and not (n_err or n_warn):
            # Only show infos when there are no higher severities
            triage.append(chalk.blue(f"{n_info} info" + ("s" if n_info != 1 else "")))
        parts.append(", ".join(triage) if triage else chalk.blue("info"))

    result: str = " ".join(parts) + diag_show_hint

    # Optional verbose diagnostic listing (gated by verbosity level)
    if ctx.diagnostics and verbosity_level > 0:
        details: list[str] = []
        for d in ctx.diagnostics:
            prefix: str = {
                DiagnosticLevel.ERROR: chalk.red_bright("error"),
                DiagnosticLevel.WARNING: chalk.yellow("warning"),
                DiagnosticLevel.INFO: chalk.blue("info"),
            }[d.level]
            details.append(f"  [{prefix}] {d.message}")
        result += "\n" + "\n".join(details)

    return result


__all__: list[str] = [
    "apply_view_filter",
    "collect_diagnostic_totals",
    "collect_diagnostics",
    "count_writes",
    "finalize_run_result",
    "summarize",
    "to_file_result",
]
