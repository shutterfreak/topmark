# topmark:header:start
#
#   project      : TopMark
#   file         : test_reporting.py
#   file_relpath : tests/pipeline/test_reporting.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Unit tests for pipeline reporting helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.helpers.pipeline import run_insert
from topmark.pipeline.context.policy import effective_would_add_or_update
from topmark.pipeline.reduction import reduce_processing_contexts
from topmark.pipeline.reporting import ReportFilterResult
from topmark.pipeline.reporting import ReportScope
from topmark.pipeline.reporting import filter_results_for_report
from topmark.pipeline.reporting import would_change_result

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.config.model import FrozenConfig
    from topmark.pipeline.context.model import ProcessingContext
    from topmark.pipeline.result import ProcessingResult


def _result_paths(results: list[ProcessingContext] | list[ProcessingResult]) -> list[Path]:
    """Return paths from filtered context or result lists."""
    return [result.path for result in results]


@pytest.mark.parametrize(
    "report_scope",
    [ReportScope.ACTIONABLE, ReportScope.NONCOMPLIANT, ReportScope.ALL],
)
def test_filter_results_for_report_accepts_reduced_results(
    tmp_path: Path,
    default_frozen_config: FrozenConfig,
    report_scope: ReportScope,
) -> None:
    """Report filtering should preserve behavior after context reduction."""
    path: Path = tmp_path / "sample.py"
    path.write_text("print('hello')\n", encoding="utf-8")
    ctx: ProcessingContext = run_insert(path=path, cfg=default_frozen_config)

    context_filter: ReportFilterResult[ProcessingContext] = filter_results_for_report(
        [ctx],
        report_scope=report_scope,
        would_change=effective_would_add_or_update,
    )
    result_filter: ReportFilterResult[ProcessingResult] = filter_results_for_report(
        reduce_processing_contexts([ctx]).results,
        report_scope=report_scope,
        would_change=would_change_result,
    )

    assert _result_paths(result_filter.view_results) == _result_paths(context_filter.view_results)
    assert result_filter.skipped_count == context_filter.skipped_count
    assert result_filter.unsupported_count_all == context_filter.unsupported_count_all


def test_would_change_result_uses_durable_outcome_snapshot(
    tmp_path: Path,
    default_frozen_config: FrozenConfig,
) -> None:
    """The result predicate should read the durable outcome snapshot."""
    path: Path = tmp_path / "sample.py"
    path.write_text("print('hello')\n", encoding="utf-8")
    ctx: ProcessingContext = run_insert(path=path, cfg=default_frozen_config)
    result: ProcessingResult = reduce_processing_contexts([ctx]).results[0]

    assert would_change_result(result) is (result.outcome.would_change is True)
