# topmark:header:start
#
#   project      : TopMark
#   file         : collectors.py
#   file_relpath : src/topmark/api/collectors.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Internal collectors for public API stream events.

The collectors in this module consume the stable public event DTOs emitted by
`stream_check()`, `stream_strip()`, and `stream_probe()` and rebuild durable
batch-style API results. They are intentionally internal for now: the public
compatibility boundary remains the event DTOs and stream entry points exported
from `topmark.api`.

The current public file-result events do not carry per-file diagnostics. Callers
that already own diagnostic mappings may pass them into the collector finalizer
so existing batch API behavior can be preserved without changing the public event
contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from typing import Literal

from topmark.api.types import FileResultEvent
from topmark.api.types import ProbeFileResultEvent
from topmark.api.types import ProbeRunResult
from topmark.api.types import RunCompletedEvent
from topmark.api.types import RunResult
from topmark.api.types import RunStartedEvent

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

    from typing_extensions import Self

    from topmark.api.types import ContentStreamEvent
    from topmark.api.types import DiagnosticEntry
    from topmark.api.types import FileResult
    from topmark.api.types import ProbeFileResult
    from topmark.api.types import ProbeStreamEvent


@dataclass(frozen=True, kw_only=True, slots=True)
class CollectedContentRun:
    """Collected content stream result and selected path metadata.

    Attributes:
        result: Rebuilt public batch result.
        selected_paths: Ordered selected paths from the run-start event.
    """

    result: RunResult
    selected_paths: tuple[Path, ...]


@dataclass(frozen=True, kw_only=True, slots=True)
class CollectedProbeRun:
    """Collected probe stream result and selected path metadata.

    Attributes:
        result: Rebuilt public probe batch result.
        selected_paths: Ordered selected paths from the run-start event.
    """

    result: ProbeRunResult
    selected_paths: tuple[Path, ...]


def _require_content_event(event: object) -> ContentStreamEvent:
    """Return a supported content event or reject an untyped runtime value."""
    if not isinstance(event, RunStartedEvent | FileResultEvent | RunCompletedEvent):
        raise TypeError(f"Unsupported content stream event: {type(event).__name__}.")
    return event


def _require_probe_event(event: object) -> ProbeStreamEvent:
    """Return a supported probe event or reject an untyped runtime value."""
    if not isinstance(event, RunStartedEvent | ProbeFileResultEvent | RunCompletedEvent):
        raise TypeError(f"Unsupported probe stream event: {type(event).__name__}.")
    return event


class ContentRunCollector:
    """Accumulate `check` or `strip` stream events into a `RunResult`.

    Args:
        command: Expected content command for every consumed event.
    """

    def __init__(
        self,
        command: Literal["check", "strip"],
    ) -> None:
        self._command: Literal["check", "strip"] = command
        self._started: RunStartedEvent | None = None
        self._files: list[FileResult] = []
        self._completed: RunCompletedEvent | None = None

    def consume(
        self,
        event: ContentStreamEvent,
    ) -> Self:
        """Consume one content stream event.

        Args:
            event: Public stream event to add to this collector.

        Returns:
            This collector for fluent use.

        Raises:
            TypeError: If the event is not a supported content event DTO.
            ValueError: If the event violates the expected stream order or
                command identity.
        """  # noqa: DOC503 - documents TypeError propagated by event validation
        event = _require_content_event(event)
        if isinstance(event, RunStartedEvent):
            expected_kind = "run_started"
        elif isinstance(event, FileResultEvent):
            expected_kind = "file_result"
        else:
            expected_kind = "run_completed"
        if event.kind != expected_kind:
            raise ValueError(
                f"{type(event).__name__} kind must be {expected_kind!r}, got {event.kind!r}."
            )
        if event.command != self._command:
            raise ValueError(f"Expected {self._command!r} stream event, got {event.command!r}.")
        if isinstance(event, RunStartedEvent):
            if self._started is not None:
                raise ValueError("Stream contains more than one run-start event.")
            self._started = event
        elif isinstance(event, FileResultEvent):
            if self._started is None:
                raise ValueError("File-result event appeared before run-start event.")
            if self._completed is not None:
                raise ValueError("File-result event appeared after run-completed event.")
            expected_index: int = len(self._files)
            if event.index != expected_index:
                raise ValueError(f"Expected file-result index {expected_index}, got {event.index}.")
            self._files.append(event.result)
        else:  # RunCompletedEvent
            if self._started is None:
                raise ValueError("Run-completed event appeared before run-start event.")
            if self._completed is not None:
                raise ValueError("Stream contains more than one run-completed event.")
            self._completed = event
        return self

    def finish(
        self,
        *,
        diagnostics: dict[str, list[DiagnosticEntry]] | None = None,
        bucket_summary: dict[str, int] | None = None,
    ) -> CollectedContentRun:
        """Return the collected content run.

        Args:
            diagnostics: Optional per-file diagnostics owned by the producer.
            bucket_summary: Optional precomputed bucket summary owned by the
                producer. When omitted, the collector derives it from file events.

        Returns:
            Collected content run with batch-compatible result metadata.

        Raises:
            ValueError: If the consumed stream is incomplete.
        """
        if self._started is None:
            raise ValueError("Cannot finish a stream without a run-start event.")
        if self._completed is None:
            raise ValueError("Cannot finish a stream without a run-completed event.")

        summary: dict[str, int] = {}
        derived_bucket_summary: dict[str, int] = {}
        for file_result in self._files:
            outcome_key: str = file_result.outcome.value
            summary[outcome_key] = summary.get(outcome_key, 0) + 1
            derived_bucket_summary[file_result.bucket_key] = (
                derived_bucket_summary.get(file_result.bucket_key, 0) + 1
            )

        completed: RunCompletedEvent = self._completed
        if dict(completed.summary) != summary:
            raise ValueError("Run-completed summary does not match file-result events.")

        result = RunResult(
            files=tuple(self._files),
            summary=completed.summary,
            had_errors=completed.had_errors,
            skipped=completed.skipped,
            written=completed.written,
            failed=completed.failed,
            bucket_summary=(
                bucket_summary if bucket_summary is not None else derived_bucket_summary
            ),
            diagnostics=diagnostics,
            diagnostic_totals=completed.diagnostic_totals,
            diagnostic_totals_all=completed.diagnostic_totals_all,
        )
        return CollectedContentRun(
            result=result,
            selected_paths=tuple(self._started.paths),
        )


class ProbeRunCollector:
    """Accumulate `probe` stream events into a `ProbeRunResult`."""

    def __init__(self) -> None:
        self._started: RunStartedEvent | None = None
        self._files: list[ProbeFileResult] = []
        self._completed: RunCompletedEvent | None = None

    def consume(
        self,
        event: ProbeStreamEvent,
    ) -> Self:
        """Consume one probe stream event.

        Args:
            event: Public probe stream event to add to this collector.

        Returns:
            This collector for fluent use.

        Raises:
            TypeError: If the event is not a supported probe event DTO.
            ValueError: If the event violates the expected stream order or
                command identity.
        """  # noqa: DOC503 - documents TypeError propagated by event validation
        event = _require_probe_event(event)
        if isinstance(event, RunStartedEvent):
            expected_kind = "run_started"
        elif isinstance(event, ProbeFileResultEvent):
            expected_kind = "file_result"
        else:
            expected_kind = "run_completed"
        if event.kind != expected_kind:
            raise ValueError(
                f"{type(event).__name__} kind must be {expected_kind!r}, got {event.kind!r}."
            )
        if event.command != "probe":
            raise ValueError(f"Expected 'probe' stream event, got {event.command!r}.")
        if isinstance(event, RunStartedEvent):
            if self._started is not None:
                raise ValueError("Stream contains more than one run-start event.")
            self._started = event
        elif isinstance(event, ProbeFileResultEvent):
            if self._started is None:
                raise ValueError("File-result event appeared before run-start event.")
            if self._completed is not None:
                raise ValueError("File-result event appeared after run-completed event.")
            expected_index: int = len(self._files)
            if event.index != expected_index:
                raise ValueError(f"Expected file-result index {expected_index}, got {event.index}.")
            self._files.append(event.result)
        else:  # RunCompletedEvent
            if self._started is None:
                raise ValueError("Run-completed event appeared before run-start event.")
            if self._completed is not None:
                raise ValueError("Stream contains more than one run-completed event.")
            self._completed = event
        return self

    def finish(
        self,
        *,
        diagnostics: dict[str, list[DiagnosticEntry]] | None = None,
    ) -> CollectedProbeRun:
        """Return the collected probe run.

        Args:
            diagnostics: Optional per-file diagnostics owned by the producer.

        Returns:
            Collected probe run with batch-compatible result metadata.

        Raises:
            ValueError: If the consumed stream is incomplete.
        """
        if self._started is None:
            raise ValueError("Cannot finish a stream without a run-start event.")
        if self._completed is None:
            raise ValueError("Cannot finish a stream without a run-completed event.")

        summary: dict[str, int] = {}
        for file_result in self._files:
            summary[file_result.status] = summary.get(file_result.status, 0) + 1

        completed: RunCompletedEvent = self._completed
        if dict(completed.summary) != summary:
            raise ValueError("Run-completed summary does not match file-result events.")

        result = ProbeRunResult(
            files=tuple(self._files),
            summary=completed.summary,
            had_errors=completed.had_errors,
            diagnostics=diagnostics,
            diagnostic_totals=completed.diagnostic_totals,
        )
        return CollectedProbeRun(
            result=result,
            selected_paths=tuple(self._started.paths),
        )


def collect_content_stream(
    events: Iterable[ContentStreamEvent],
    *,
    command: Literal["check", "strip"],
    diagnostics: dict[str, list[DiagnosticEntry]] | None = None,
    bucket_summary: dict[str, int] | None = None,
) -> CollectedContentRun:
    """Collect content events into a batch-compatible internal run object.

    Args:
        events: Public content stream events in producer order.
        command: Expected command identity for all events.
        diagnostics: Optional per-file diagnostics owned by the event producer.
        bucket_summary: Optional bucket summary owned by the event producer.

    Returns:
        Collected content run.
    """
    collector = ContentRunCollector(command)
    for event in events:
        collector.consume(event)
    return collector.finish(
        diagnostics=diagnostics,
        bucket_summary=bucket_summary,
    )


def collect_probe_stream(
    events: Iterable[ProbeStreamEvent],
    *,
    diagnostics: dict[str, list[DiagnosticEntry]] | None = None,
) -> CollectedProbeRun:
    """Collect probe events into a batch-compatible internal run object.

    Args:
        events: Public probe stream events in producer order.
        diagnostics: Optional per-file diagnostics owned by the event producer.

    Returns:
        Collected probe run.
    """
    collector = ProbeRunCollector()
    for event in events:
        collector.consume(event)
    return collector.finish(diagnostics=diagnostics)
