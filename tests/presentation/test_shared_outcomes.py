# topmark:header:start
#
#   project      : TopMark
#   file         : test_shared_outcomes.py
#   file_relpath : tests/presentation/test_shared_outcomes.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Unit tests for shared presentation outcome helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.helpers.pipeline import make_pipeline_context
from topmark.config.io.deserializers import mutable_config_from_defaults
from topmark.pipeline.result import ProcessingResult
from topmark.pipeline.status import ComparisonStatus
from topmark.pipeline.status import ContentStatus
from topmark.pipeline.status import FsStatus
from topmark.pipeline.status import HeaderStatus
from topmark.pipeline.status import ResolveStatus
from topmark.pipeline.status import WriteStatus
from topmark.presentation.shared.outcomes import collect_outcome_counts_styled
from topmark.presentation.shared.outcomes import collect_outcome_counts_styled_for_apply
from topmark.runtime.model import RunOptions

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.cli.presentation import TextStyler
    from topmark.config.model import MutableConfig
    from topmark.pipeline.context.model import ProcessingContext
    from topmark.pipeline.kinds import PipelineKindLiteral
    from topmark.pipeline.outcomes import OutcomeReasonCount


def _make_inserted_context(
    tmp_path: Path,
    *,
    pipeline_kind: PipelineKindLiteral = "check",
) -> ProcessingContext:
    """Create a context classified as an inserted file in apply mode."""
    mutable: MutableConfig = mutable_config_from_defaults()
    ctx: ProcessingContext = make_pipeline_context(tmp_path / "case.py", mutable.freeze())
    ctx.run_options = RunOptions(
        pipeline_kind=pipeline_kind,
        apply_changes=True,
    )

    ctx.status.resolve = ResolveStatus.RESOLVED
    ctx.status.fs = FsStatus.OK
    ctx.status.content = ContentStatus.OK
    ctx.status.header = HeaderStatus.MISSING
    ctx.status.comparison = ComparisonStatus.CHANGED
    ctx.status.write = WriteStatus.WRITTEN
    return ctx


def test_collect_outcome_counts_styled_for_apply_supports_processing_results(
    tmp_path: Path,
) -> None:
    """Apply-explicit styled summaries should support durable results."""
    ctx: ProcessingContext = _make_inserted_context(
        tmp_path,
    )
    result: ProcessingResult = ProcessingResult.from_context(ctx)

    context_rows: list[tuple[OutcomeReasonCount, TextStyler]] = [
        (row, styler) for row, styler in collect_outcome_counts_styled([ctx])
    ]
    result_rows: list[tuple[OutcomeReasonCount, TextStyler]] = [
        (row, styler)
        for row, styler in collect_outcome_counts_styled_for_apply([result], apply=True)
    ]

    assert [row for row, _styler in result_rows] == [row for row, _styler in context_rows]
    assert [styler("x") for _row, styler in result_rows] == [
        styler("x") for _row, styler in context_rows
    ]
