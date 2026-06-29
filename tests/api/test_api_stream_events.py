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
