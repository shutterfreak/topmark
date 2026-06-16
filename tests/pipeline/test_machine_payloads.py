# topmark:header:start
#
#   project      : TopMark
#   file         : test_machine_payloads.py
#   file_relpath : tests/pipeline/test_machine_payloads.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Unit tests for pipeline machine payload builders."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.helpers.pipeline import make_pipeline_context
from topmark.config.io.deserializers import mutable_config_from_defaults
from topmark.pipeline.machine.payloads import build_processing_results_summary_rows_payload
from topmark.pipeline.machine.payloads import iter_processing_results_summary_entries
from topmark.pipeline.result import ProcessingResult
from topmark.pipeline.status import ComparisonStatus
from topmark.pipeline.status import ContentStatus
from topmark.pipeline.status import FsStatus
from topmark.pipeline.status import HeaderStatus
from topmark.pipeline.status import ResolveStatus
from topmark.pipeline.status import WriteStatus
from topmark.runtime.model import RunOptions

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.config.model import MutableConfig
    from topmark.pipeline.context.model import ProcessingContext
    from topmark.pipeline.machine.schemas import OutcomeSummaryRow


def _make_inserted_context(tmp_path: Path) -> ProcessingContext:
    """Create a context classified as an inserted file in apply mode."""
    mutable: MutableConfig = mutable_config_from_defaults()
    ctx: ProcessingContext = make_pipeline_context(tmp_path / "case.py", mutable.freeze())
    ctx.run_options = RunOptions(apply_changes=True)
    ctx.status.resolve = ResolveStatus.RESOLVED
    ctx.status.fs = FsStatus.OK
    ctx.status.content = ContentStatus.OK
    ctx.status.header = HeaderStatus.MISSING
    ctx.status.comparison = ComparisonStatus.CHANGED
    ctx.status.write = WriteStatus.WRITTEN
    return ctx


def test_processing_summary_rows_payload_uses_result_execution_mode(
    tmp_path: Path,
) -> None:
    """JSON summary rows should summarize durable result snapshots directly."""
    ctx: ProcessingContext = _make_inserted_context(tmp_path)
    result: ProcessingResult = ProcessingResult.from_context(ctx)

    rows: list[OutcomeSummaryRow] = build_processing_results_summary_rows_payload(
        [result],
    )

    assert rows == [
        {
            "outcome": "changed",
            "reason": "written",
            "count": 1,
        }
    ]


def test_processing_summary_entries_use_result_execution_mode(
    tmp_path: Path,
) -> None:
    """NDJSON summary entries should summarize durable result snapshots directly."""
    ctx: ProcessingContext = _make_inserted_context(tmp_path)
    result: ProcessingResult = ProcessingResult.from_context(ctx)

    rows: list[OutcomeSummaryRow] = list(
        iter_processing_results_summary_entries(
            [result],
        ),
    )

    assert rows == [
        {
            "outcome": "changed",
            "reason": "written",
            "count": 1,
        }
    ]
