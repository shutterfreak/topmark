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
    - Machine output remains schema-driven and should typically use the full
      unfiltered results list.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from topmark.pipeline.status import ContentStatus
from topmark.pipeline.status import FsStatus
from topmark.pipeline.status import ResolveStatus

if TYPE_CHECKING:
    from collections.abc import Callable

    from topmark.pipeline.context.model import ProcessingContext


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
            broader “show everything that is not already okay” view.
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


@dataclass(frozen=True)
class ReportFilterResult:
    """Result of applying a report scope to pipeline contexts."""

    view_results: list[ProcessingContext]
    skipped_count: int
    unsupported_count_all: int


_UNSUPPORTED_RESOLVE: frozenset[ResolveStatus] = frozenset(
    {
        ResolveStatus.UNSUPPORTED,
        ResolveStatus.TYPE_RESOLVED_HEADERS_UNSUPPORTED,
        ResolveStatus.TYPE_RESOLVED_NO_PROCESSOR_REGISTERED,
    }
)


def _is_unsupported(r: ProcessingContext) -> bool:
    return r.status.resolve in _UNSUPPORTED_RESOLVE


def _has_problem_diagnostics(r: ProcessingContext) -> bool:
    # Treat warnings and errors as "problems"; info is intentionally ignored.
    if not r.diagnostics:
        return False
    return any(d.level.value in {"warning", "error"} for d in r.diagnostics)


def _needs_attention(r: ProcessingContext) -> bool:
    """Return True when a result deserves human attention in per-file output.

    This is intentionally broader than “would change”. In addition to
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
    return r.status.content not in {ContentStatus.OK, ContentStatus.SKIPPED_MIXED_LINE_ENDINGS}


def filter_results_for_report(
    results: list[ProcessingContext],
    *,
    report: ReportScope,
    would_change: Callable[[ProcessingContext], bool],
) -> ReportFilterResult:
    """Filter raw pipeline results for human per-file rendering.

    This helper is intentionally scoped to **human per-file output**. Callers
    should keep the original `results` list for summary mode and for
    machine-readable output.

    Semantics:
        - `ReportScope.ALL`: keep every result.
        - `ReportScope.NONCOMPLIANT`: keep everything that is not already okay,
          including unsupported entries.
        - `ReportScope.ACTIONABLE`: keep entries that need attention, but hide
          unsupported entries from the per-file list and summarize them
          separately.

    Args:
        results: Raw pipeline results.
        report: Which entries to include in the human per-file listing.
        would_change: Predicate describing whether a result represents a file
            TopMark would change (or did change, depending on caller context).

    Returns:
        `(view_results, unsupported_count_all)` where:
        - `view_results` is the filtered per-file list for human output.
        - `unsupported_count_all` is counted across the full raw result set so
            it can still be summarized even when hidden from the per-file list.
    """
    unsupported_count: int = sum(1 for r in results if _is_unsupported(r))
    count: int = len(results)
    skipped_count: int

    if report == ReportScope.ALL:
        skipped_count = 0
        return ReportFilterResult(
            view_results=results,
            skipped_count=skipped_count,
            unsupported_count_all=unsupported_count,
        )

    def is_noncompliant(r: ProcessingContext) -> bool:
        return would_change(r) or _needs_attention(r)

    if report == ReportScope.NONCOMPLIANT:
        view: list[ProcessingContext] = [r for r in results if is_noncompliant(r)]
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
