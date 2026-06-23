# topmark:header:start
#
#   project      : TopMark
#   file         : reporting.py
#   file_relpath : src/topmark/pipeline/reporting.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Pipeline reporting scope helpers.

This module defines small helpers that decide which per-file pipeline results should be included
in the human-facing per-file listing.

Notes:
    - `--summary` remains "summary only" and bypasses per-file listing.
    - Verbosity controls detail density; report scope controls inclusion.
    - Machine-readable output remains schema-driven and should typically use the full
      unfiltered results list.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING
from typing import Generic
from typing import Protocol
from typing import TypeVar

from topmark.pipeline.status import ContentStatus
from topmark.pipeline.status import FsStatus
from topmark.pipeline.status import ResolveStatus

if TYPE_CHECKING:
    from collections.abc import Callable
    from collections.abc import Iterable
    from collections.abc import Sequence

    from topmark.diagnostic.model import Diagnostic
    from topmark.pipeline.outcomes import SupportsOutcomeClassification


class ReportScope(str, Enum):
    """Controls which per-file entries are rendered for human output.

    `ReportScope` affects only the **human per-file listing** used by the TEXT
    and MARKDOWN emitters. It does **not** change the underlying pipeline result
    set, and it should not affect machine-readable output or summary-only mode.

    Values:
        ACTIONABLE: Entries that require user attention in the normal day-to-day
            workflow. This includes files that TopMark would change and other
            problem states that deserve visibility, but it intentionally hides
            unsupported entries from the per-file list.
        NONCOMPLIANT: Actionable entries plus unsupported entries. This is the
            broader "show everything that is not already okay" view.
        ALL: Every result, including unchanged/compliant entries.

    Inclusion overview:

    | scope          | includes unsupported? | includes unchanged? | includes would-change? |
    | -------------- | :-------------------: | :-----------------: | :--------------------: |
    | `actionable`   |          no           |         no          |         **yes**        |
    | `noncompliant` |       **yes**         |         no          |         **yes**        |
    | `all`          |       **yes**         |       **yes**       |         **yes**        |

    Notes:
        - Verbosity controls **how much detail** is shown for included entries;
          report scope controls **which entries** appear in the human per-file
          listing.
        - Summary mode remains summary-only and bypasses per-file filtering.
        - Machine-readable formats should continue to use the full unfiltered
          result set.
    """

    ACTIONABLE = "actionable"
    NONCOMPLIANT = "noncompliant"
    ALL = "all"


class SupportsReportStatus(Protocol):
    """Minimum status surface required by report-scope filtering."""

    @property
    def resolve(self) -> ResolveStatus:
        """Resolution status used to detect unsupported entries."""
        ...

    @property
    def fs(self) -> FsStatus:
        """Filesystem status used to detect problem entries."""
        ...

    @property
    def content(self) -> ContentStatus:
        """Content status used to detect problem entries."""
        ...


class SupportsReportFiltering(Protocol):
    """Minimum result surface required by report-scope filtering.

    The protocol is intentionally satisfied by both mutable
    `ProcessingContext` instances and durable `ProcessingResult` snapshots.
    This lets reporting helpers move to the result side of the reduction
    boundary without changing human detail rendering yet.
    """

    @property
    def status(self) -> SupportsReportStatus:
        """Per-axis status values used by report filtering."""
        ...

    @property
    def diagnostics(self) -> Iterable[Diagnostic]:
        """Diagnostics used to decide whether a result needs attention."""
        ...


TReportResult = TypeVar("TReportResult", bound=SupportsReportFiltering)


@dataclass(frozen=True, kw_only=True, slots=True)
class ReportFilterResult(Generic[TReportResult]):
    """Result of applying a report scope to pipeline results.

    Attributes:
        view_results: Filtered result list for the selected human report scope.
        skipped_count: Number of entries hidden by report filtering.
        unsupported_count_all: Unsupported entries counted across the full input.
    """

    view_results: list[TReportResult]
    skipped_count: int
    unsupported_count_all: int


_UNSUPPORTED_RESOLVE: frozenset[ResolveStatus] = frozenset(
    {
        ResolveStatus.UNSUPPORTED,
        ResolveStatus.TYPE_RESOLVED_HEADERS_UNSUPPORTED,
        ResolveStatus.TYPE_RESOLVED_NO_PROCESSOR_REGISTERED,
    }
)


def _is_unsupported(r: SupportsReportFiltering) -> bool:
    return r.status.resolve in _UNSUPPORTED_RESOLVE


def _has_problem_diagnostics(r: SupportsReportFiltering) -> bool:
    # Treat warnings and errors as "problems"; info is intentionally ignored.
    return any(d.level.value in {"warning", "error"} for d in r.diagnostics)


def _needs_attention(r: SupportsReportFiltering) -> bool:
    """Return True when a result deserves human attention in per-file output.

    This is intentionally broader than "would change". In addition to
    user-actionable changes, it includes problem states such as unsupported
    files, warnings/errors, and unreadable / failed pipeline states.

    Args:
        r: Processing result to classify.

    Returns:
        True if the result should be considered noncompliant or noteworthy.
    """
    if _is_unsupported(r):
        return True
    if _has_problem_diagnostics(r):
        return True
    if r.status.fs not in {FsStatus.OK, FsStatus.EMPTY}:
        return True
    return r.status.content not in {
        ContentStatus.OK,
        ContentStatus.SKIPPED_MIXED_LINE_ENDINGS,
    }


def would_change_result(result: SupportsOutcomeClassification) -> bool:
    """Return the generic change flag stored on a reduced result.

    This predicate is useful for command-agnostic reporting. Prefer
    `would_add_or_update_result` for `check` and `would_strip_result` for
    `strip`, where report-scope filtering must follow command-specific mutation
    intent.

    Args:
        result: Mutable context or durable result carrying outcome flags.

    Returns:
        True when the result represents a generic pending or completed change.
    """
    return result.outcome.would_change is True


def would_add_or_update_result(result: SupportsOutcomeClassification) -> bool:
    """Return whether a result is actionable for `check` report filtering.

    Args:
        result: Mutable context or durable result carrying outcome flags.

    Returns:
        True when `check` would add or update a header for this result.
    """
    return result.outcome.effective_would_add_or_update is True


def would_strip_result(result: SupportsOutcomeClassification) -> bool:
    """Return whether a result is actionable for `strip` report filtering.

    Args:
        result: Mutable context or durable result carrying outcome flags.

    Returns:
        True when `strip` would remove a header for this result.
    """
    return result.outcome.effective_would_strip is True


def filter_results_for_report(
    results: Sequence[TReportResult],
    *,
    report_scope: ReportScope,
    would_change: Callable[[TReportResult], bool],
) -> ReportFilterResult[TReportResult]:
    """Filter raw pipeline results for human per-file rendering.

    This helper is intentionally scoped to **human per-file output**. Callers
    should keep the original `results` sequence for summary mode and for
    machine-readable output.

    Semantics:
        - `ReportScope.ALL`: keep every result.
        - `ReportScope.NONCOMPLIANT`: keep everything that is not already okay,
          including unsupported entries.
        - `ReportScope.ACTIONABLE`: keep entries that need attention, but hide
          unsupported entries from the per-file list and summarize them
          separately.

    Args:
        results: Raw pipeline results or durable result snapshots.
        report_scope: Active report scope for the current view.
        would_change: Predicate describing whether a result represents a file
            TopMark would change (or did change, depending on caller context).

    Returns:
        Filter result where:
        - `view_results` is the filtered per-file list for human output.
        - `unsupported_count_all` is counted across the full raw result set so
            it can still be summarized even when hidden from the per-file list.
    """
    unsupported_count: int = sum(1 for r in results if _is_unsupported(r))
    count: int = len(results)
    skipped_count: int

    if report_scope == ReportScope.ALL:
        skipped_count = 0
        return ReportFilterResult(
            view_results=list(results),
            skipped_count=skipped_count,
            unsupported_count_all=unsupported_count,
        )

    def is_noncompliant(r: TReportResult) -> bool:
        return would_change(r) or _needs_attention(r)

    if report_scope == ReportScope.NONCOMPLIANT:
        view: list[TReportResult] = [r for r in results if is_noncompliant(r)]
        skipped_count = count - len(view)
        return ReportFilterResult(
            view_results=view,
            skipped_count=skipped_count,
            unsupported_count_all=unsupported_count,
        )

    # ACTIONABLE (default): only entries that require user action (would change) plus problems,
    # but keep unsupported out of the per-file list (summarize instead).
    view = [r for r in results if is_noncompliant(r) and not _is_unsupported(r)]
    skipped_count = count - len(view)
    return ReportFilterResult(
        view_results=view,
        skipped_count=skipped_count,
        unsupported_count_all=unsupported_count,
    )
