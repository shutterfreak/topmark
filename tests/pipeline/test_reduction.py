# topmark:header:start
#
#   project      : TopMark
#   file         : test_reduction.py
#   file_relpath : tests/pipeline/test_reduction.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Tests for the batch processing-context reduction boundary."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.helpers.pipeline import make_context_from_text
from topmark.config.io.deserializers import mutable_config_from_defaults
from topmark.core.exit_codes import ExitCode
from topmark.pipeline.engine import exit_code_from_pipeline_results
from topmark.pipeline.outcomes import OutcomeReasonCount
from topmark.pipeline.outcomes import collect_outcome_reason_counts
from topmark.pipeline.outcomes import collect_outcome_reason_counts_for_apply
from topmark.pipeline.reduction import ProcessingReduction
from topmark.pipeline.reduction import reduce_processing_contexts
from topmark.pipeline.status import ComparisonStatus
from topmark.pipeline.status import ContentStatus
from topmark.pipeline.status import FsStatus
from topmark.pipeline.status import HeaderStatus
from topmark.pipeline.status import WriteStatus

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.config.model import FrozenConfig
    from topmark.pipeline.context.model import ProcessingContext


def _make_reduction_context(
    tmp_path: Path,
    filename: str,
) -> ProcessingContext:
    """Create a small processing context for reduction-boundary tests."""
    cfg: FrozenConfig = mutable_config_from_defaults().freeze()
    return make_context_from_text(
        "print('hello')\n",
        cfg=cfg,
        path=tmp_path / filename,
    )


def test_reduce_processing_contexts_returns_batch_handover(
    tmp_path: Path,
) -> None:
    """Batch reduction should preserve contexts and produce ordered results."""
    first: ProcessingContext = _make_reduction_context(tmp_path, "first.py")
    second: ProcessingContext = _make_reduction_context(tmp_path, "second.py")
    first.status.header = HeaderStatus.MISSING
    second.status.header = HeaderStatus.DETECTED

    reduction: ProcessingReduction = reduce_processing_contexts([first, second])

    assert reduction.contexts == (first, second)
    assert [result.path.name for result in reduction.results] == ["first.py", "second.py"]
    assert reduction.results[0].status.header is HeaderStatus.MISSING
    assert reduction.results[1].status.header is HeaderStatus.DETECTED


def test_reduce_processing_contexts_snapshots_status_without_releasing_contexts(
    tmp_path: Path,
) -> None:
    """Batch reduction should detach result state while retaining source contexts."""
    ctx: ProcessingContext = _make_reduction_context(tmp_path, "sample.py")
    ctx.status.header = HeaderStatus.MISSING

    reduction: ProcessingReduction = reduce_processing_contexts([ctx])
    ctx.status.header = HeaderStatus.DETECTED

    assert reduction.contexts[0] is ctx
    assert reduction.contexts[0].status.header is HeaderStatus.DETECTED
    assert reduction.results[0].status.header is HeaderStatus.MISSING


def test_reduced_results_match_context_summary_counts(
    tmp_path: Path,
) -> None:
    """Reduced results should preserve context-based outcome summary rows."""
    first_insert: ProcessingContext = _make_reduction_context(tmp_path, "first.py")
    first_insert.status.header = HeaderStatus.MISSING
    first_insert.status.comparison = ComparisonStatus.CHANGED

    second_insert: ProcessingContext = _make_reduction_context(tmp_path, "second.py")
    second_insert.status.header = HeaderStatus.MISSING
    second_insert.status.comparison = ComparisonStatus.CHANGED

    unchanged: ProcessingContext = _make_reduction_context(tmp_path, "unchanged.py")
    unchanged.status.header = HeaderStatus.DETECTED
    unchanged.status.comparison = ComparisonStatus.UNCHANGED

    contexts: list[ProcessingContext] = [first_insert, second_insert, unchanged]
    reduction: ProcessingReduction = reduce_processing_contexts(contexts)

    context_rows: list[OutcomeReasonCount] = collect_outcome_reason_counts(contexts)
    result_rows: list[OutcomeReasonCount] = collect_outcome_reason_counts_for_apply(
        reduction.results,
        apply=False,
    )

    assert result_rows == context_rows


def test_exit_code_selection_accepts_reduced_results(
    tmp_path: Path,
) -> None:
    """Exit-code selection should work across contexts and reduced results."""
    not_found: ProcessingContext = _make_reduction_context(tmp_path, "missing.py")
    not_found.status.fs = FsStatus.NOT_FOUND

    write_failed: ProcessingContext = _make_reduction_context(tmp_path, "failed.py")
    write_failed.status.write = WriteStatus.FAILED

    contexts: list[ProcessingContext] = [write_failed, not_found]
    reduction: ProcessingReduction = reduce_processing_contexts(contexts)

    assert exit_code_from_pipeline_results(contexts) is ExitCode.FILE_NOT_FOUND
    assert exit_code_from_pipeline_results(reduction.results) is ExitCode.FILE_NOT_FOUND


def test_exit_code_selection_preserves_result_priority(
    tmp_path: Path,
) -> None:
    """Result-based exit-code selection should preserve existing priority order."""
    unreadable: ProcessingContext = _make_reduction_context(tmp_path, "unreadable.py")
    unreadable.status.content = ContentStatus.UNREADABLE

    no_write_permission: ProcessingContext = _make_reduction_context(tmp_path, "blocked.py")
    no_write_permission.status.fs = FsStatus.NO_WRITE_PERMISSION

    reduction: ProcessingReduction = reduce_processing_contexts(
        [unreadable, no_write_permission],
    )

    assert exit_code_from_pipeline_results(reduction.results) is ExitCode.PERMISSION_DENIED
