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
from topmark.pipeline.reduction import ProcessingReduction
from topmark.pipeline.reduction import iter_processing_results
from topmark.pipeline.reduction import reduce_processing_contexts
from topmark.pipeline.status import ContentStatus
from topmark.pipeline.status import FsStatus
from topmark.pipeline.status import HeaderStatus
from topmark.pipeline.status import WriteStatus
from topmark.pipeline.views import DiffView

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from topmark.config.model import FrozenConfig
    from topmark.pipeline.context.model import ProcessingContext
    from topmark.pipeline.result import ProcessingResult


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


def test_reduce_processing_contexts_can_release_views_without_retaining_contexts(
    tmp_path: Path,
) -> None:
    """Reduced-only handover should snapshot detail before releasing view payloads."""
    ctx: ProcessingContext = _make_reduction_context(tmp_path, "sample.py")
    ctx.views.diff = DiffView(text="--- current\n+++ updated\n")

    reduction: ProcessingReduction = reduce_processing_contexts(
        [ctx],
        retain_contexts=False,
        release_views=True,
    )

    assert reduction.contexts == ()
    assert reduction.results[0].detail.diff_text == "--- current\n+++ updated\n"
    assert ctx.views.diff is not None
    assert ctx.views.diff.text is None


def test_iter_processing_results_reduces_and_releases_one_context_at_a_time(
    tmp_path: Path,
) -> None:
    """Iterator reduction should release each context before consuming the next one."""
    first: ProcessingContext = _make_reduction_context(tmp_path, "first.py")
    second: ProcessingContext = _make_reduction_context(tmp_path, "second.py")
    first.views.diff = DiffView(text="--- first\n+++ first\n")
    second.views.diff = DiffView(text="--- second\n+++ second\n")

    consumed_second: bool = False

    def contexts() -> Iterator[ProcessingContext]:
        nonlocal consumed_second
        yield first
        consumed_second = True
        yield second

    result_iter: Iterator[ProcessingResult] = iter_processing_results(
        contexts(),
        release_views=True,
    )

    first_result: ProcessingResult = next(result_iter)

    assert first_result.detail.diff_text == "--- first\n+++ first\n"
    assert first.views.diff is not None
    assert first.views.diff.text is None
    assert consumed_second is False
    assert second.views.diff is not None
    assert second.views.diff.text == "--- second\n+++ second\n"

    second_result: ProcessingResult = next(result_iter)

    assert second_result.detail.diff_text == "--- second\n+++ second\n"
    assert second.views.diff is not None
    assert second.views.diff.text is None
