# topmark:header:start
#
#   project      : TopMark
#   file         : test_api_stream_collectors.py
#   file_relpath : tests/api/test_api_stream_collectors.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Tests for internal stream-to-result collectors."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from topmark import api
from topmark.api.collectors import ContentRunCollector
from topmark.api.collectors import ProbeRunCollector
from topmark.api.collectors import collect_content_stream
from topmark.api.collectors import collect_probe_stream
from topmark.api.types import DiagnosticTotals
from topmark.core.outcomes import Outcome

if TYPE_CHECKING:
    from topmark.api.collectors import CollectedContentRun
    from topmark.api.collectors import CollectedProbeRun
    from topmark.api.types import ContentStreamEvent
    from topmark.api.types import DiagnosticEntry
    from topmark.api.types import ProbeStreamEvent
    from topmark.pipeline.kinds import PipelineKindLiteral


def _content_file_result() -> api.FileResult:
    return api.FileResult(
        path=Path("src/example.py"),
        outcome=Outcome.WOULD_UPDATE,
        diff=None,
        bucket_key=Outcome.WOULD_UPDATE.value,
        bucket_label="would update",
    )


def _probe_file_result() -> api.ProbeFileResult:
    return api.ProbeFileResult(
        path=Path("README.md"),
        status="resolved",
        reason="resolved",
        selected_file_type="markdown",
        selected_processor="markdown",
        candidates=(),
    )


def _content_run_started() -> api.RunStartedEvent:
    return api.RunStartedEvent(
        kind="run_started",
        command="check",
        selected_count=1,
        paths=(Path("src/example.py"),),
    )


def _probe_run_started() -> api.RunStartedEvent:
    return api.RunStartedEvent(
        kind="run_started",
        command="probe",
        selected_count=1,
        paths=(Path("README.md"),),
    )


def _content_file_event(index: int = 0) -> api.FileResultEvent:
    return api.FileResultEvent(
        kind="file_result",
        command="check",
        index=index,
        result=_content_file_result(),
    )


def _probe_file_event(index: int = 0) -> api.ProbeFileResultEvent:
    return api.ProbeFileResultEvent(
        kind="file_result",
        command="probe",
        index=index,
        result=_probe_file_result(),
    )


def _content_run_completed(
    *,
    summary: dict[str, int] | None = None,
    command: PipelineKindLiteral = "check",
) -> api.RunCompletedEvent:
    return api.RunCompletedEvent(
        kind="run_completed",
        command=command,
        summary=(summary if summary is not None else {Outcome.WOULD_UPDATE.value: 1}),
        had_errors=False,
    )


def _probe_run_completed(
    *,
    summary: dict[str, int] | None = None,
    command: PipelineKindLiteral = "probe",
) -> api.RunCompletedEvent:
    return api.RunCompletedEvent(
        kind="run_completed",
        command=command,
        summary=(
            summary
            if summary is not None
            else {
                "resolved": 1,
            }
        ),
        had_errors=False,
    )


def test_content_collector_rebuilds_run_result_from_events() -> None:
    """Content collectors aggregate summaries, buckets, flags, and diagnostics."""
    file_result: api.FileResult = _content_file_result()
    diagnostic_totals = DiagnosticTotals(
        info=0,
        warning=1,
        error=0,
        total=1,
    )
    diagnostics: dict[str, list[DiagnosticEntry]] = {
        "src/example.py": [
            api.DiagnosticEntry(
                level="warning",
                message="example",
            ),
        ],
    }

    collected: CollectedContentRun = collect_content_stream(
        (
            _content_run_started(),
            api.FileResultEvent(
                kind="file_result",
                command="check",
                index=0,
                result=file_result,
            ),
            api.RunCompletedEvent(
                kind="run_completed",
                command="check",
                summary={
                    Outcome.WOULD_UPDATE.value: 1,
                },
                had_errors=False,
                skipped=2,
                written=0,
                failed=0,
                diagnostic_totals=diagnostic_totals,
                diagnostic_totals_all=diagnostic_totals,
            ),
        ),
        command="check",
        diagnostics=diagnostics,
    )

    assert collected.selected_paths == (Path("src/example.py"),)
    assert collected.result.files == (file_result,)
    assert collected.result.summary == {
        Outcome.WOULD_UPDATE.value: 1,
    }
    assert collected.result.bucket_summary == {
        Outcome.WOULD_UPDATE.value: 1,
    }
    assert collected.result.skipped == 2
    assert collected.result.diagnostics == diagnostics
    assert collected.result.diagnostic_totals == diagnostic_totals
    assert collected.result.diagnostic_totals_all == diagnostic_totals


def test_content_collector_rejects_out_of_order_file_events() -> None:
    """Collectors reject non-deterministic or malformed event indexes."""
    file_result: api.FileResult = _content_file_result()

    with pytest.raises(ValueError, match="Expected file-result index 0"):
        collect_content_stream(
            (
                _content_run_started(),
                api.FileResultEvent(
                    kind="file_result",
                    command="check",
                    index=1,
                    result=file_result,
                ),
                api.RunCompletedEvent(
                    kind="run_completed",
                    command="check",
                    summary={
                        Outcome.WOULD_UPDATE.value: 1,
                    },
                    had_errors=False,
                ),
            ),
            command="check",
        )


def test_probe_collector_rebuilds_probe_result_from_events() -> None:
    """Probe collectors aggregate status summaries and diagnostic totals."""
    probe_result = _probe_file_result()
    diagnostic_totals = DiagnosticTotals(info=0, warning=0, error=0, total=0)

    collected: CollectedProbeRun = collect_probe_stream(
        (
            _probe_run_started(),
            api.ProbeFileResultEvent(
                kind="file_result",
                command="probe",
                index=0,
                result=probe_result,
            ),
            api.RunCompletedEvent(
                kind="run_completed",
                command="probe",
                summary={
                    "resolved": 1,
                },
                had_errors=False,
                diagnostic_totals=diagnostic_totals,
            ),
        )
    )

    assert collected.selected_paths == (Path("README.md"),)
    assert collected.result.files == (probe_result,)
    assert collected.result.summary == {
        "resolved": 1,
    }
    assert collected.result.diagnostic_totals == diagnostic_totals


@pytest.mark.parametrize(
    ("events", "expected_message"),
    [
        (
            (_content_run_started(), _content_run_started()),
            "Stream contains more than one run-start event",
        ),
        (
            (_content_file_event(),),
            "File-result event appeared before run-start event",
        ),
        (
            (_content_run_completed(),),
            "Run-completed event appeared before run-start event",
        ),
        (
            (_content_run_started(), _content_run_completed(), _content_file_event()),
            "File-result event appeared after run-completed event",
        ),
        (
            (_content_run_started(), _content_run_completed(), _content_run_completed()),
            "Stream contains more than one run-completed event",
        ),
        (
            (
                _content_run_started(),
                _content_file_event(),
                _content_run_completed(
                    summary={
                        Outcome.SKIPPED.value: 1,
                    }
                ),
            ),
            "Run-completed summary does not match file-result events",
        ),
    ],
)
def test_content_collector_rejects_malformed_streams(
    events: tuple[ContentStreamEvent, ...],
    expected_message: str,
) -> None:
    """Content collectors reject malformed stream ordering and summaries."""
    with pytest.raises(
        ValueError,
        match=expected_message,
    ):
        collect_content_stream(events, command="check")


@pytest.mark.parametrize(
    ("events", "expected_message"),
    [
        (
            (_probe_run_started(), _probe_run_started()),
            "Stream contains more than one run-start event",
        ),
        (
            (_probe_file_event(),),
            "File-result event appeared before run-start event",
        ),
        (
            (_probe_run_completed(),),
            "Run-completed event appeared before run-start event",
        ),
        (
            (_probe_run_started(), _probe_run_completed(), _probe_file_event()),
            "File-result event appeared after run-completed event",
        ),
        (
            (_probe_run_started(), _probe_run_completed(), _probe_run_completed()),
            "Stream contains more than one run-completed event",
        ),
        (
            (
                _probe_run_started(),
                _probe_file_event(),
                _probe_run_completed(
                    summary={
                        "unsupported": 1,
                    }
                ),
            ),
            "Run-completed summary does not match file-result events",
        ),
    ],
)
def test_probe_collector_rejects_malformed_streams(
    events: tuple[ProbeStreamEvent, ...],
    expected_message: str,
) -> None:
    """Probe collectors reject malformed stream ordering and summaries."""
    with pytest.raises(
        ValueError,
        match=expected_message,
    ):
        collect_probe_stream(events)


@pytest.mark.parametrize(
    ("event", "expected_message"),
    [
        (
            api.RunStartedEvent(
                kind="run_started",
                command="strip",
                selected_count=1,
                paths=(Path("src/example.py"),),
            ),
            "Expected 'check' stream event, got 'strip'",
        ),
        (
            _content_run_completed(command="strip"),
            "Expected 'check' stream event, got 'strip'",
        ),
    ],
)
def test_content_collector_rejects_mismatched_command(
    event: ContentStreamEvent,
    expected_message: str,
) -> None:
    """Content collectors enforce the configured command identity."""
    collector = ContentRunCollector("check")

    with pytest.raises(
        ValueError,
        match=expected_message,
    ):
        collector.consume(event)


def test_probe_collector_rejects_mismatched_command() -> None:
    """Probe collectors enforce probe command identity."""
    collector = ProbeRunCollector()
    event = api.RunStartedEvent(
        kind="run_started",
        command="check",
        selected_count=1,
        paths=(Path("src/example.py"),),
    )

    with pytest.raises(
        ValueError,
        match="Expected 'probe' stream event, got 'check'",
    ):
        collector.consume(event)


@pytest.mark.parametrize(
    ("collector", "expected_message"),
    [
        (
            ContentRunCollector("check"),
            "Cannot finish a stream without a run-start event",
        ),
        (
            ProbeRunCollector(),
            "Cannot finish a stream without a run-start event",
        ),
    ],
)
def test_collectors_reject_finish_without_start(
    collector: ContentRunCollector | ProbeRunCollector,
    expected_message: str,
) -> None:
    """Collectors require a run-start event before finalization."""
    with pytest.raises(
        ValueError,
        match=expected_message,
    ):
        collector.finish()


def test_content_collector_rejects_finish_without_completion() -> None:
    """Content collectors require a run-completed event before finalization."""
    collector = ContentRunCollector("check")
    collector.consume(_content_run_started())

    with pytest.raises(
        ValueError,
        match="Cannot finish a stream without a run-completed event",
    ):
        collector.finish()


def test_probe_collector_rejects_finish_without_completion() -> None:
    """Probe collectors require a run-completed event before finalization."""
    collector = ProbeRunCollector()
    collector.consume(_probe_run_started())

    with pytest.raises(
        ValueError,
        match="Cannot finish a stream without a run-completed event",
    ):
        collector.finish()
