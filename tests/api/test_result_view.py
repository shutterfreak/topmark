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

from dataclasses import replace
from typing import TYPE_CHECKING

from tests.helpers.pipeline import run_insert_diff
from topmark import api
from topmark.api.view import finalize_probe_result
from topmark.api.view import finalize_run_result
from topmark.api.view import to_probe_file_result
from topmark.core.exit_codes import ExitCode
from topmark.diagnostic.model import Diagnostic
from topmark.diagnostic.model import DiagnosticLevel
from topmark.diagnostic.model import FrozenDiagnosticLog
from topmark.pipeline.reduction import ProcessingReduction
from topmark.pipeline.reduction import reduce_processing_contexts
from topmark.pipeline.reporting import ReportScope
from topmark.pipeline.reporting import would_add_or_update_result
from topmark.pipeline.result import ProbeCandidateSnapshot
from topmark.pipeline.result import ProbeMatchSnapshot
from topmark.pipeline.result import ProbeSelectionSnapshot
from topmark.pipeline.result import ProbeSnapshot
from topmark.pipeline.result import ProcessingResult
from topmark.pipeline.status import PlanStatus
from topmark.pipeline.status import ResolveStatus
from topmark.pipeline.status import WriteStatus

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.api.types import RunResult
    from topmark.config.model import FrozenConfig
    from topmark.pipeline.context.model import ProcessingContext
    from topmark.pipeline.context.status import StatusSnapshot
    from topmark.pipeline.result import ProcessingResult


def _durable_result(
    *,
    path: Path,
    default_frozen_config: FrozenConfig,
) -> ProcessingResult:
    path.write_text("print('hello')\n", encoding="utf-8")
    ctx: ProcessingContext = run_insert_diff(path=path, cfg=default_frozen_config)
    return reduce_processing_contexts([ctx]).results[0]


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
        would_change=would_add_or_update_result,
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


def test_probe_candidate_conversion_uses_stable_ordered_match_tokens(
    tmp_path: Path,
    default_frozen_config: FrozenConfig,
) -> None:
    """Probe conversion preserves candidate fields without leaking raw errors."""
    path: Path = tmp_path / "signals.py"
    base: ProcessingResult = _durable_result(
        path=path,
        default_frozen_config=default_frozen_config,
    )
    selected = ProbeSelectionSnapshot(
        qualified_key="pytest:signals",
        namespace="pytest",
        local_key="signals",
        score=42,
    )
    probe = ProbeSnapshot(
        path=path,
        status="resolved",
        reason="selected_highest_score",
        candidates=(
            ProbeCandidateSnapshot(
                qualified_key="pytest:signals",
                namespace="pytest",
                local_key="signals",
                score=42,
                selected=True,
                tie_break_rank=1,
                match=ProbeMatchSnapshot(
                    extension=True,
                    filename=True,
                    pattern=True,
                    content_probe_allowed=True,
                    content_match=True,
                ),
            ),
            ProbeCandidateSnapshot(
                qualified_key="pytest:error",
                namespace="pytest",
                local_key="error",
                score=7,
                selected=False,
                tie_break_rank=2,
                match=ProbeMatchSnapshot(
                    extension=False,
                    filename=False,
                    pattern=False,
                    content_probe_allowed=True,
                    content_match=False,
                    content_error="UnicodeDecodeError: private detail",
                ),
            ),
        ),
        selected_file_type=selected,
        selected_processor=ProbeSelectionSnapshot(
            qualified_key="pytest:processor",
            namespace="pytest",
            local_key="processor",
        ),
    )

    public: api.ProbeFileResult = to_probe_file_result(replace(base, probe=probe))

    assert public.selected_file_type == "signals"
    assert public.selected_processor == "processor"
    assert [candidate.qualified_key for candidate in public.candidates] == [
        "pytest:signals",
        "pytest:error",
    ]
    assert public.candidates[0] == api.ProbeCandidateInfo(
        file_type="signals",
        qualified_key="pytest:signals",
        score=42,
        selected=True,
        rank=1,
        matched_by=(
            "extension",
            "filename",
            "pattern",
            "content",
        ),
    )
    assert public.candidates[1].matched_by == ("content_error",)
    assert "private detail" not in repr(public)


def test_probe_conversion_without_snapshot_uses_existing_outcome_vocabulary(
    tmp_path: Path,
    default_frozen_config: FrozenConfig,
) -> None:
    """A missing probe snapshot falls back without exposing internal objects."""
    path: Path = tmp_path / "fallback.py"
    base: ProcessingResult = _durable_result(
        path=path,
        default_frozen_config=default_frozen_config,
    )

    public: api.ProbeFileResult = to_probe_file_result(replace(base, probe=None))

    assert public.path == path
    assert isinstance(public.status, str)
    assert isinstance(public.reason, str)
    assert public.selected_file_type is None
    assert public.selected_processor is None
    assert public.candidates == ()
    assert "ProcessingResult" not in repr(public)


def test_finalize_run_result_preserves_diagnostics_and_full_run_aggregates(
    tmp_path: Path,
    default_frozen_config: FrozenConfig,
) -> None:
    """Filtered views retain full-run errors, writes, failures, and diagnostic totals."""
    first_path: Path = tmp_path / "first.py"
    second_path: Path = tmp_path / "second.py"
    base: ProcessingResult = _durable_result(
        path=first_path,
        default_frozen_config=default_frozen_config,
    )
    diagnostics = FrozenDiagnosticLog(
        items=(
            Diagnostic(
                level=DiagnosticLevel.INFO,
                message="first info",
            ),
            Diagnostic(
                level=DiagnosticLevel.WARNING,
                message="then warning",
            ),
            Diagnostic(
                level=DiagnosticLevel.ERROR,
                message="finally error",
            ),
        )
    )
    hidden_status: StatusSnapshot = replace(
        base.status,
        resolve=ResolveStatus.UNSUPPORTED,
        plan=PlanStatus.INSERTED,
        write=WriteStatus.WRITTEN,
    )
    written: ProcessingResult = replace(
        base,
        diagnostics=diagnostics,
        diagnostic_counts=diagnostics.to_dict(),
        status=hidden_status,
    )
    failed: ProcessingResult = replace(
        base,
        path=second_path,
        display_path=str(second_path),
        diagnostics=FrozenDiagnosticLog(items=()),
        diagnostic_counts={
            "info": 0,
            "warning": 0,
            "error": 0,
        },
        status=replace(hidden_status, write=WriteStatus.FAILED),
    )

    result: RunResult = finalize_run_result(
        results=(written, failed),
        file_list=[first_path, second_path],
        apply=True,
        report_scope=ReportScope.ACTIONABLE,
        update_statuses=frozenset({PlanStatus.INSERTED}),
        encountered_exit_code=None,
    )

    assert result.files == ()
    assert result.skipped == 2
    assert result.diagnostics == {}
    assert result.diagnostic_totals == {
        "info": 0,
        "warning": 0,
        "error": 0,
        "total": 0,
    }
    assert result.diagnostic_totals_all == {
        "info": 1,
        "warning": 1,
        "error": 1,
        "total": 3,
    }
    assert result.had_errors is True
    assert result.written == 1
    assert result.failed == 1


def test_finalize_probe_result_preserves_diagnostic_order_and_fatal_errors(
    tmp_path: Path,
    default_frozen_config: FrozenConfig,
) -> None:
    """Probe finalization exposes ordered diagnostics and honors fatal exit state."""
    path: Path = tmp_path / "probe.py"
    base: ProcessingResult = _durable_result(
        path=path,
        default_frozen_config=default_frozen_config,
    )
    diagnostics = FrozenDiagnosticLog(
        items=(
            Diagnostic(
                level=DiagnosticLevel.INFO,
                message="first",
            ),
            Diagnostic(
                level=DiagnosticLevel.WARNING,
                message="second",
            ),
        )
    )
    public: api.ProbeRunResult = finalize_probe_result(
        results=(
            replace(
                base,
                diagnostics=diagnostics,
                diagnostic_counts=diagnostics.to_dict(),
            ),
        ),
        file_list=[path],
        encountered_exit_code=ExitCode.PIPELINE_ERROR,
    )

    assert public.diagnostics == {
        str(path): [
            {
                "level": "info",
                "message": "first",
            },
            {
                "level": "warning",
                "message": "second",
            },
        ]
    }
    assert public.diagnostic_totals == {
        "info": 1,
        "warning": 1,
        "error": 0,
        "total": 2,
    }
    assert public.had_errors is True


def test_finalize_probe_result_counts_error_before_later_diagnostic(
    tmp_path: Path,
    default_frozen_config: FrozenConfig,
) -> None:
    """Diagnostic aggregation continues after an error and preserves order."""
    path: Path = tmp_path / "diagnostic-order.py"
    base: ProcessingResult = _durable_result(
        path=path,
        default_frozen_config=default_frozen_config,
    )
    diagnostics = FrozenDiagnosticLog(
        items=(
            Diagnostic(level=DiagnosticLevel.ERROR, message="first error"),
            Diagnostic(level=DiagnosticLevel.INFO, message="later info"),
        )
    )

    public: api.ProbeRunResult = finalize_probe_result(
        results=(
            replace(
                base,
                diagnostics=diagnostics,
                diagnostic_counts=diagnostics.to_dict(),
            ),
        ),
        file_list=[path],
        encountered_exit_code=None,
    )

    assert public.diagnostics == {
        str(path): [
            {"level": "error", "message": "first error"},
            {"level": "info", "message": "later info"},
        ]
    }
    assert public.diagnostic_totals == {
        "info": 1,
        "warning": 0,
        "error": 1,
        "total": 2,
    }
    assert public.had_errors is True
