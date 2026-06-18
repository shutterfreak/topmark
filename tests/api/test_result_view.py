# topmark:header:start
#
#   project      : TopMark
#   file         : test_result_view.py
#   file_relpath : tests/api/test_result_view.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Tests for public API view assembly from durable processing results."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.helpers.pipeline import run_insert_diff
from topmark.api.view import finalize_run_result
from topmark.pipeline.reduction import ProcessingReduction
from topmark.pipeline.reduction import reduce_processing_contexts
from topmark.pipeline.reporting import ReportScope
from topmark.pipeline.status import PlanStatus

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.api.types import RunResult
    from topmark.config.model import FrozenConfig
    from topmark.pipeline.context.model import ProcessingContext


def test_finalize_run_result_consumes_durable_processing_results(
    tmp_path: Path,
    default_frozen_config: FrozenConfig,
) -> None:
    """Public API check/strip DTO assembly should not require live context views."""
    path: Path = tmp_path / "sample.py"
    path.write_text("print('hello')\n", encoding="utf-8")
    ctx: ProcessingContext = run_insert_diff(path=path, cfg=default_frozen_config)

    reduction: ProcessingReduction = reduce_processing_contexts([ctx])
    if ctx.views.diff is not None:
        ctx.views.diff.release()

    result: RunResult = finalize_run_result(
        results=reduction.results,
        file_list=[path],
        apply=False,
        report_scope=ReportScope.ALL,
        update_statuses=frozenset(
            {
                PlanStatus.INSERTED,
                PlanStatus.REPLACED,
                PlanStatus.REMOVED,
            }
        ),
        encountered_exit_code=None,
    )

    assert len(result.files) == 1
    assert result.files[0].path == path
    assert result.files[0].diff == reduction.results[0].detail.diff_text
    assert result.files[0].diff is not None
    assert result.had_errors is False
