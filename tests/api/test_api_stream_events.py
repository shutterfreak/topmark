# topmark:header:start
#
#   project      : TopMark
#   file         : test_api_stream_events.py
#   file_relpath : tests/api/test_api_stream_events.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Tests for public streaming API event contracts."""

from __future__ import annotations

from pathlib import Path

from topmark import api
from topmark.core.outcomes import Outcome


def test_content_stream_event_contract_uses_public_file_result() -> None:
    """Content stream events carry public DTOs and stable discriminators."""
    file_result = api.FileResult(
        path=Path("src/example.py"),
        outcome=Outcome.WOULD_UPDATE,
        diff="--- old\n+++ new\n",
        bucket_key=Outcome.WOULD_UPDATE.value,
        bucket_label="would update",
    )

    started = api.RunStartedEvent(
        kind="run_started",
        command="check",
        selected_count=1,
        paths=(Path("src/example.py"),),
    )
    file_event = api.FileResultEvent(
        kind="file_result",
        command="check",
        index=0,
        result=file_result,
    )
    completed = api.RunCompletedEvent(
        kind="run_completed",
        command="check",
        summary={Outcome.WOULD_UPDATE.value: 1},
        had_errors=False,
        skipped=0,
        written=0,
        failed=0,
    )

    stream: tuple[api.ContentStreamEvent, ...] = (
        started,
        file_event,
        completed,
    )  # Equivalent to `api.ContentStreamEvent`

    assert [event.kind for event in stream] == [
        "run_started",
        "file_result",
        "run_completed",
    ]
    assert file_event.result is file_result
    assert completed.summary == {"would update": 1}


def test_probe_stream_event_contract_uses_public_probe_result() -> None:
    """Probe stream events use the probe-specific public file-result DTO."""
    probe_result = api.ProbeFileResult(
        path=Path("README.md"),
        status="resolved",
        reason="resolved",
        selected_file_type="markdown",
        selected_processor="markdown",
        candidates=(),
    )

    started = api.RunStartedEvent(
        kind="run_started",
        command="probe",
        selected_count=1,
        paths=(Path("README.md"),),
    )
    file_event = api.ProbeFileResultEvent(
        kind="file_result",
        command="probe",
        index=0,
        result=probe_result,
    )
    completed = api.RunCompletedEvent(
        kind="run_completed",
        command="probe",
        summary={"resolved": 1},
        had_errors=False,
    )

    stream: tuple[api.ProbeStreamEvent, ...] = (
        started,
        file_event,
        completed,
    )  # Equivalent to `api.ProbeStreamEvent`

    assert [event.command for event in stream] == ["probe", "probe", "probe"]
    assert file_event.result is probe_result
    assert completed.skipped == 0


def test_stream_check_matches_batch_result_and_order(
    repo_py_with_and_without_header: Path,
) -> None:
    """stream_check() emits batch-compatible events in deterministic order."""
    path: Path = repo_py_with_and_without_header / "src" / "without_header.py"

    batch: api.RunResult = api.check(
        [path],
        config=None,
        include_file_types=["python"],
        report="all",
        prune_views=True,
    )
    events: tuple[api.ContentStreamEvent, ...] = tuple(
        api.stream_check(
            [path],
            config=None,
            include_file_types=["python"],
            report="all",
            prune_views=True,
        )
    )

    assert [event.kind for event in events] == [
        "run_started",
        "file_result",
        "run_completed",
    ]
    started = events[0]
    assert isinstance(started, api.RunStartedEvent)
    assert started.command == "check"
    assert started.selected_count == 1
    assert started.paths == (path,)

    file_event = events[1]
    assert isinstance(file_event, api.FileResultEvent)
    assert file_event.command == "check"
    assert file_event.index == 0
    assert file_event.result == batch.files[0]

    completed = events[2]
    assert isinstance(completed, api.RunCompletedEvent)
    assert completed.command == "check"
    assert completed.summary == batch.summary
    assert completed.had_errors == batch.had_errors
    assert completed.skipped == batch.skipped
    assert completed.written == batch.written
    assert completed.failed == batch.failed
    assert completed.diagnostic_totals == batch.diagnostic_totals
    assert completed.diagnostic_totals_all == batch.diagnostic_totals_all


def test_stream_strip_matches_batch_result_and_order(
    repo_py_with_and_without_header: Path,
) -> None:
    """stream_strip() emits batch-compatible events in deterministic order."""
    path: Path = repo_py_with_and_without_header / "src" / "with_header.py"

    batch: api.RunResult = api.strip(
        [path],
        config=None,
        include_file_types=["python"],
        report="all",
        prune_views=True,
    )
    events: tuple[api.ContentStreamEvent, ...] = tuple(
        api.stream_strip(
            [path],
            config=None,
            include_file_types=["python"],
            report="all",
            prune_views=True,
        )
    )

    assert [event.kind for event in events] == [
        "run_started",
        "file_result",
        "run_completed",
    ]
    file_event = events[1]
    assert isinstance(file_event, api.FileResultEvent)
    assert file_event.command == "strip"
    assert file_event.result == batch.files[0]

    completed = events[2]
    assert isinstance(completed, api.RunCompletedEvent)
    assert completed.command == "strip"
    assert completed.summary == batch.summary
    assert completed.had_errors == batch.had_errors


def test_stream_probe_matches_batch_result_and_includes_synthetic_missing(
    tmp_path: Path,
) -> None:
    """stream_probe() preserves probe batch ordering including synthetic results."""
    existing: Path = tmp_path / "example.py"
    missing: Path = tmp_path / "missing.py"
    existing.write_text("print('hello')\n", encoding="utf-8")

    batch: api.ProbeRunResult = api.probe(
        [existing, missing],
        config=None,
        include_file_types=["python"],
        prune_views=True,
    )
    events: tuple[api.ProbeStreamEvent, ...] = tuple(
        api.stream_probe(
            [existing, missing],
            config=None,
            include_file_types=["python"],
            prune_views=True,
        )
    )

    assert [event.kind for event in events] == [
        "run_started",
        "file_result",
        "file_result",
        "run_completed",
    ]
    started = events[0]
    assert isinstance(started, api.RunStartedEvent)
    assert started.command == "probe"
    assert started.selected_count == 1
    assert started.paths == (existing,)

    file_events = events[1:3]
    assert all(isinstance(event, api.ProbeFileResultEvent) for event in file_events)
    probe_file_events = [
        event for event in file_events if isinstance(event, api.ProbeFileResultEvent)
    ]
    assert [event.index for event in probe_file_events] == [0, 1]
    assert [event.result for event in probe_file_events] == list(batch.files)

    completed = events[3]
    assert isinstance(completed, api.RunCompletedEvent)
    assert completed.command == "probe"
    assert completed.summary == batch.summary
    assert completed.had_errors == batch.had_errors
    assert completed.diagnostic_totals == batch.diagnostic_totals
