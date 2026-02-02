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

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

from yachalk import chalk

from topmark.api.public_types import PublicDiagnostic
from topmark.config.logging import get_logger
from topmark.core.diagnostics import DiagnosticLevel, DiagnosticStats
from topmark.core.enum_mixins import enum_from_name
from topmark.pipeline.context.policy import (
    can_change,
    check_permitted_by_policy,
    effective_would_add_or_update,
    effective_would_strip,
)
from topmark.pipeline.hints import Cluster, Hint
from topmark.pipeline.status import (
    ComparisonStatus,
    ContentStatus,
    FsStatus,
    GenerationStatus,
    HeaderStatus,
    PlanStatus,
    ResolveStatus,
    StripStatus,
    WriteStatus,
)

from .types import DiagnosticTotals, FileResult, Outcome, RunResult

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from topmark.config.logging import TopmarkLogger
    from topmark.core.exit_codes import ExitCode
    from topmark.pipeline.context.model import ProcessingContext
    from topmark.pipeline.views import DiffView
    from topmark.rendering.colored_enum import Colorizer

    from .public_types import PublicDiagnostic

logger: TopmarkLogger = get_logger(__name__)

__all__: list[str] = [
    "apply_view_filter",
    "classify_outcome",
    "collect_diagnostic_totals",
    "collect_diagnostics",
    "count_writes",
    "finalize_run_result",
    "summarize",
    "to_file_result",
]


def classify_outcome(r: ProcessingContext, *, apply: bool) -> Outcome:
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
    return map_bucket(r, apply=apply).outcome


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


class Intent(Enum):
    STRIP = "strip"
    INSERT = "insert"
    UPDATE = "update"
    NONE = "none"  # no clear action (compare skipped, etc.)


def determine_intent(r: ProcessingContext) -> Intent:
    """Derive the high-level intent for bucketing from the current context.

    Intent is inferred from statuses that indicate what the pipeline is trying
    to do for this file:

    - STRIP: the strip axis is non-pending (strip pipeline ran).
    - INSERT: header axis indicates a missing header.
    - UPDATE: header axis is decided (not PENDING) and not missing.
    - NONE: insufficient information to infer an action (early termination).

    Args:
        r (ProcessingContext): The processing context.

    Returns:
        Intent: The inferred bucketing intent.
    """
    if r.status.strip != StripStatus.PENDING:
        return Intent.STRIP
    if r.status.header == HeaderStatus.MISSING:
        return Intent.INSERT
    if r.status.header != HeaderStatus.PENDING:
        return Intent.UPDATE
    return Intent.NONE


NO_REASON_PROVIDED: str = "(no reason provided)"

FormatCallable = Callable[[str], str]


_OUTCOME_COLOR: dict[Outcome, FormatCallable] = {
    Outcome.PENDING: chalk.gray,
    Outcome.SKIPPED: chalk.yellow,
    Outcome.WOULD_CHANGE: chalk.red_bright,
    Outcome.CHANGED: chalk.yellow_bright,
    Outcome.UNCHANGED: chalk.green,
    Outcome.WOULD_INSERT: chalk.yellow,
    Outcome.WOULD_UPDATE: chalk.yellow,
    Outcome.WOULD_STRIP: chalk.yellow,
    Outcome.INSERTED: chalk.yellow_bright,
    Outcome.UPDATED: chalk.yellow_bright,
    Outcome.STRIPPED: chalk.yellow_bright,
    Outcome.ERROR: chalk.red_bright,
}


def outcome_color(o: Outcome) -> FormatCallable:
    """Return the formatter used to colorize a given outcome."""
    return _OUTCOME_COLOR[o]


@dataclass
class ResultBucket:
    """Outcome + human label used for CLI/API bucketing.

    The bucket is a small value object that couples a public `Outcome` with an
    optional human-facing label used in summaries.

    Args:
        outcome (Outcome | None): The classified outcome to set. If ``None``,
            the default value is preserved.
        reason (str | None): Human-facing bucket label (summary text). If
            ``None``, the default value is preserved.

    Attributes:
        outcome (Outcome): The classified outcome.
        reason (str | None): Human-facing bucket label (summary text). This is
            intentionally independent of internal debug tracing.
    """

    outcome: Outcome = Outcome.PENDING
    reason: str | None = None

    def __init__(self, *, outcome: Outcome | None, reason: str | None) -> None:
        if outcome is not None:
            self.outcome = outcome
        if reason is not None:
            self.reason = reason

        logger.debug("ResultBucket: '%s'", self.__repr__())

    def __repr__(self) -> str:
        return f"{self.outcome.value}: {self.reason or NO_REASON_PROVIDED}"


def map_bucket(r: ProcessingContext, *, apply: bool) -> ResultBucket:
    """Map a file context to a public bucket (Outcome + label).

    This function is precedence-ordered: the first matching rule wins. The ordering
    matters because some axes may remain PENDING depending on the chosen pipeline
    (for example, strip pipelines may omit comparison).

    Precedence (high → low):
        1) Hard skips/errors (resolve/fs/content fatal states).
        2) Content-level soft skips (mixed newlines / BOM-before-shebang / reflow).
        3) Empty-file default compliance: empty files are UNCHANGED unless policy allows
           inserting headers into empty files.
        4) Strip intent mapping based on the strip axis (READY/NOT_NEEDED/FAILED). This
           must not depend on comparison.
        5) Malformed headers that TopMark cannot safely interpret.
        6) Policy veto (add-only / update-only).
        7) Comparison/write outcomes (UNCHANGED/CHANGED and write WRITTEN/FAILED).
        8) Dry-run previews and remaining fallbacks (NO_FIELDS, plan skipped).
        9) Pending (no rule matched).

    Args:
        r (ProcessingContext): The per-file pipeline context.
        apply (bool): Whether the run is in apply mode.

    Returns:
        ResultBucket: Bucket containing public Outcome and a human label.
    """
    intent: Intent = determine_intent(r)
    logger.trace("intent: %s; apply: %s; status: %s", intent.value, apply, r.status)

    def ret(tag: str, *, outcome: Outcome, reason: str | None) -> ResultBucket:
        """Return a bucket while emitting a structured debug trace.

        The `tag` is debug-only and is intended to make it easy to locate the
        matching precedence branch in logs.

        Args:
            tag (str): Stable debug tag for the matching branch.
            outcome (Outcome): Public outcome for CLI/API.
            reason (str | None): Human-facing bucket label.

        Returns:
            ResultBucket: Constructed bucket.
        """
        logger.debug(
            "bucket[%s] intent='%s' apply='%s' outcome='%s' reason='%s'",
            tag,
            intent.value,
            apply,
            outcome.value,
            reason or NO_REASON_PROVIDED,
        )
        return ResultBucket(outcome=outcome, reason=reason)

    # --- 1) Hard skips/errors (resolve/fs/content fatal states) ---
    if r.status.resolve != ResolveStatus.RESOLVED:
        return ret(
            "skip:resolve",
            outcome=Outcome.SKIPPED,
            reason=r.status.resolve.value,
        )
    if r.status.fs in {FsStatus.NOT_FOUND, FsStatus.NO_READ_PERMISSION, FsStatus.UNREADABLE}:
        return ret(
            "error:fs-read",
            outcome=Outcome.ERROR,
            reason=r.status.fs.value,
        )
    if apply and r.status.fs == FsStatus.NO_WRITE_PERMISSION:
        return ret(
            "error:fs-write",
            outcome=Outcome.ERROR,
            reason=r.status.fs.value,
        )
    if r.status.content in {
        ContentStatus.PENDING,
        ContentStatus.UNSUPPORTED,
        ContentStatus.UNREADABLE,
    }:
        return ret(
            "skip:content",
            outcome=Outcome.SKIPPED,
            reason=r.status.content.value,
        )

    # --- 2) Content-level soft skips (may be policy-overridable) ---
    if r.status.content in {
        ContentStatus.SKIPPED_MIXED_LINE_ENDINGS,
        ContentStatus.SKIPPED_POLICY_BOM_BEFORE_SHEBANG,
        ContentStatus.SKIPPED_REFLOW,
    }:
        return ret(
            "skip:content-soft",
            outcome=Outcome.SKIPPED,
            reason=r.status.content.value,
        )

    # --- 3) Empty-file default compliance ---
    # Empty files are compliant by default (not a non-compliance). If policy allows inserting
    # into empties, `can_change(r)` will be True and we fall through to normal change bucketing.
    if r.status.fs == FsStatus.EMPTY and not can_change(r):
        return ret(
            "unchanged:empty-default",
            outcome=Outcome.UNCHANGED,
            reason="empty_file",
        )

    # --- 4) Strip mapping (strip pipelines may omit comparer; do not depend on comparison) ---
    if intent == Intent.STRIP:
        if r.status.strip == StripStatus.READY:
            return ret(
                "strip:ready",
                outcome=Outcome.STRIPPED if apply else Outcome.WOULD_STRIP,
                reason=r.status.strip.value,
            )
        if r.status.strip == StripStatus.NOT_NEEDED:
            return ret(
                "strip:not-needed",
                outcome=Outcome.UNCHANGED,
                reason=r.status.strip.value,
            )
        if r.status.strip == StripStatus.FAILED:
            return ret(
                "strip:failed",
                outcome=Outcome.ERROR,
                reason=r.status.strip.value,
            )

    # --- 5) Malformed header that TopMark cannot safely interpret ---
    if r.status.header == HeaderStatus.MALFORMED:
        return ret(
            "error:header-malformed",
            outcome=Outcome.ERROR,
            reason=r.status.header.value,
        )

    # --- 6) Policy veto (add-only / update-only) ---
    # Policy veto is tri-state: False means forbidden; True/None both mean “not vetoed”.
    permitted_by_policy: bool | None = check_permitted_by_policy(r)
    if permitted_by_policy is False:
        return ret(
            "skip:policy",
            outcome=Outcome.SKIPPED,
            reason="skipped by policy",
        )

    logger.debug("map_bucket: permitted_by_policy=%s", permitted_by_policy)

    header_lbl: str = r.status.header.value
    comparison_lbl: str = r.status.comparison.value
    strip_lbl: str = r.status.strip.value

    # --- 7) Comparison/write outcomes ---
    if r.status.comparison == ComparisonStatus.UNCHANGED:
        return ret(
            "unchanged:up-to-date",
            outcome=Outcome.UNCHANGED,
            reason="up-to-date",
        )

    # Compute the Outcome value for a change (only meaningful when change is intended/detected).
    outcome_if_changed: Outcome
    if apply:
        if intent == Intent.STRIP:
            outcome_if_changed = Outcome.STRIPPED
        elif intent == Intent.INSERT:
            outcome_if_changed = Outcome.INSERTED
        elif intent == Intent.UPDATE:
            outcome_if_changed = Outcome.UPDATED
        else:
            outcome_if_changed = Outcome.CHANGED
    else:
        if intent == Intent.STRIP:
            outcome_if_changed = Outcome.WOULD_STRIP
        elif intent == Intent.INSERT:
            outcome_if_changed = Outcome.WOULD_INSERT
        elif intent == Intent.UPDATE:
            outcome_if_changed = Outcome.WOULD_UPDATE
        else:
            outcome_if_changed = Outcome.WOULD_CHANGE

    reason_if_changed: str = f"{header_lbl}, {comparison_lbl}"
    logger.debug(
        "Outcome if changed: '%s', reason if changed: '%s'",
        outcome_if_changed.value,
        reason_if_changed,
    )

    # Apply path: the writer has the final word.
    if r.status.write == WriteStatus.WRITTEN:
        return ret(
            "changed:written",
            outcome=outcome_if_changed,
            reason=reason_if_changed,
        )
    if r.status.write == WriteStatus.FAILED:
        return ret(
            "error:write",
            outcome=Outcome.ERROR,
            reason=r.status.write.value,
        )

    # Changed comparison: map to the appropriate change outcome.
    if r.status.comparison == ComparisonStatus.CHANGED:
        if intent == Intent.STRIP:
            return ret(
                "changed:strip",
                outcome=outcome_if_changed,
                reason=f"{header_lbl}, {strip_lbl}",
            )
        elif intent in (Intent.INSERT, Intent.UPDATE):
            return ret(
                "changed:header",
                outcome=outcome_if_changed,
                reason=reason_if_changed,
            )
        else:
            return ret(
                "changed:generic",
                outcome=outcome_if_changed,
                reason=reason_if_changed,
            )

    # --- 8) Dry-run previews and remaining fallbacks ---
    if not apply:
        if intent in (Intent.INSERT, Intent.UPDATE):
            if effective_would_add_or_update(r):
                return ret(
                    "would-change:header",
                    outcome=outcome_if_changed,
                    reason=header_lbl,
                )
            return ret(
                "would-change:header-fallthrough",
                outcome=outcome_if_changed,
                reason=header_lbl,
            )
        if intent == Intent.STRIP:
            if effective_would_strip(r):
                # Prefer the strip axis label for summaries.
                return ret(
                    "would-strip",
                    outcome=outcome_if_changed,
                    reason=StripStatus.READY.value,
                )
            if r.status.strip == StripStatus.NOT_NEEDED:
                return ret(
                    "unchanged:strip-not-needed",
                    outcome=Outcome.UNCHANGED,
                    reason=r.status.strip.value,
                )
        if r.status.plan == PlanStatus.PREVIEWED:
            return ret(
                "preview:plan",
                outcome=outcome_if_changed,
                reason=reason_if_changed,
            )

    if r.status.generation == GenerationStatus.NO_FIELDS:
        return ret(
            "unchanged:no-fields",
            outcome=Outcome.UNCHANGED,
            reason=r.status.generation.value,
        )

    if r.status.plan in (
        PlanStatus.SKIPPED,
        PlanStatus.FAILED,
    ):
        return ret(
            "skip:plan",
            outcome=Outcome.SKIPPED,
            reason=r.status.plan.value,  # or other e.g. reason_if_changed?
        )

    # --- 9) Pending (optional) ---
    # If you prefer to collapse this to UNCHANGED, return that here instead.
    return ret("pending", outcome=Outcome.PENDING, reason=NO_REASON_PROVIDED)


def collect_outcome_counts(
    results: list[ProcessingContext],
) -> dict[str, tuple[int, str, Callable[[str], str]]]:
    """Count results by classification key.

    Keeps the first-seen label and color for each key.

    Args:
        results (list[ProcessingContext]): Processing contexts to classify and count.

    Returns:
        dict[str, tuple[int, str, Callable[[str], str]]]: Mapping from classification
            key to ``(count, label, color_fn)``.
    """
    counts: dict[str, tuple[int, str, Callable[[str], str]]] = {}

    for r in results:
        apply: bool = r.config.apply_changes is True
        bucket: ResultBucket = map_bucket(r, apply=apply)
        color: FormatCallable = outcome_color(bucket.outcome)
        key: str = bucket.outcome.value
        label: str = bucket.reason or NO_REASON_PROVIDED
        n: int
        n, _, _ = counts.get(key, (0, label, color))
        counts[key] = (n + 1, label, color)
    return counts


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
    # Local import to avoid import cycles at module import time

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
