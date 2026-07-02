# topmark:header:start
#
#   project      : TopMark
#   file         : streaming.py
#   file_relpath : src/topmark/cli/streaming.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI stream-emission helpers.

This module contains small command-layer helpers for payload streams whose
ownership must remain explicit. It intentionally sits above the low-level
console abstraction: helpers here describe CLI output intent, while
`topmark.cli.console` describes concrete console behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import click

from topmark.core.exit_codes import ExitCode
from topmark.pipeline.engine import exit_code_from_pipeline_results
from topmark.pipeline.machine.streaming import MachineProcessingResultEvent
from topmark.pipeline.machine.streaming import MachineProcessingStreamEvent
from topmark.pipeline.machine.streaming import MachineRunCompletedEvent
from topmark.pipeline.machine.streaming import MachineRunStartedEvent
from topmark.pipeline.reduction import iter_processing_results
from topmark.pipeline.status import WriteStatus

if TYPE_CHECKING:
    from collections.abc import Callable
    from collections.abc import Iterable
    from collections.abc import Iterator
    from pathlib import Path

    from topmark.pipeline.context.model import ProcessingContext
    from topmark.pipeline.kinds import PipelineKindLiteral
    from topmark.pipeline.result import ProcessingResult


_EXIT_CODE_PRIORITY: dict[ExitCode, int] = {
    ExitCode.FILE_NOT_FOUND: 5,
    ExitCode.PERMISSION_DENIED: 4,
    ExitCode.ENCODING_ERROR: 3,
    ExitCode.IO_ERROR: 2,
    ExitCode.PIPELINE_ERROR: 1,
}


@dataclass(kw_only=True, slots=True)
class ProcessingStreamStats:
    """Mutable CLI statistics observed while consuming processing stream events.

    Attributes:
        exit_code: Highest-priority process exit code implied by observed durable
            per-file results, or `None` when no result implies an error.
        written: Number of files whose writer status is `WRITTEN`.
        failed: Number of files whose writer status is `FAILED`.
        would_change: Whether any observed result matches the command's dry-run
            would-change predicate.
    """

    exit_code: ExitCode | None = None
    written: int = 0
    failed: int = 0
    would_change: bool = False

    def observe(self, result: ProcessingResult, *, would_change: bool) -> None:
        """Update stream statistics from one durable processing result.

        Args:
            result: Durable result observed from the stream.
            would_change: Whether this result would change command output in a
                dry-run run.
        """
        result_exit_code: ExitCode | None = exit_code_from_pipeline_results([result])
        if result_exit_code is not None:
            self.exit_code = select_exit_code(self.exit_code, result_exit_code)

        if result.status.write == WriteStatus.WRITTEN:
            self.written += 1
        elif result.status.write == WriteStatus.FAILED:
            self.failed += 1

        if would_change:
            self.would_change = True


@dataclass(kw_only=True, slots=True)
class ProbeStreamStats:
    """Mutable CLI statistics observed while consuming probe stream events.

    Attributes:
        exit_code: Highest-priority hard-error exit code implied by observed
            durable probe results, or `None` when no result implies a hard error.
        missing_probe: Whether any observed durable result did not carry a probe
            snapshot. This indicates an internal probe pipeline error after hard
            errors have been handled.
        unresolved_probe: Whether any observed probe snapshot has a non-resolved
            status. Filtered explicit inputs are represented this way and map to
            `UNSUPPORTED_FILE_TYPE`.
    """

    exit_code: ExitCode | None = None
    missing_probe: bool = False
    unresolved_probe: bool = False

    def observe(self, result: ProcessingResult) -> None:
        """Update stream statistics from one durable probe result.

        Args:
            result: Durable probe result observed from the stream.
        """
        result_exit_code: ExitCode | None = exit_code_from_pipeline_results([result])
        if result_exit_code is not None:
            self.exit_code = select_exit_code(self.exit_code, result_exit_code)

        if result.probe is None:
            self.missing_probe = True
        elif result.probe.status != "resolved":
            self.unresolved_probe = True


def observe_probe_stream(
    events: Iterable[MachineProcessingStreamEvent],
    *,
    stats: ProbeStreamStats,
) -> Iterator[MachineProcessingStreamEvent]:
    """Yield probe stream events while recording CLI exit-status statistics.

    Args:
        events: Internal machine processing stream events.
        stats: Mutable probe statistics updated for each file-result event.

    Yields:
        The original events, preserving order and object identity.
    """
    for event in events:
        if isinstance(event, MachineProcessingResultEvent):
            stats.observe(event.result)
        yield event


def select_exit_code(current: ExitCode | None, candidate: ExitCode) -> ExitCode:
    """Return the higher-priority pipeline exit code.

    Args:
        current: Current selected exit code, if any.
        candidate: Newly observed candidate exit code.

    Returns:
        The exit code with the highest pipeline-error priority.
    """
    if current is None:
        return candidate

    current_priority: int = _EXIT_CODE_PRIORITY.get(current, 0)
    candidate_priority: int = _EXIT_CODE_PRIORITY.get(candidate, 0)
    if candidate_priority > current_priority:
        return candidate
    return current


def emit_stdout_payload(payload: str, *, nl: bool = True) -> None:
    """Emit a command payload that intentionally owns STDOUT.

    Use this for payload text that must be written to STDOUT independently of
    the human report console, such as unified diff output. Do not use it for
    diagnostics, warnings, status messages, or machine-output emitters that
    already receive an explicit console.

    Args:
        payload: Payload text to emit. Empty strings are ignored.
        nl: Whether Click should append a trailing newline.
    """
    if payload:
        click.echo(payload, nl=nl)


def iter_cli_processing_stream(
    contexts: Iterable[ProcessingContext],
    *,
    command: PipelineKindLiteral,
    paths: Iterable[Path],
    release_views: bool,
) -> Iterator[MachineProcessingStreamEvent]:
    """Yield internal machine events from pipeline contexts without batch reduction.

    Args:
        contexts: Completed processing contexts in deterministic command order.
        command: Command family represented by the stream.
        paths: Ordered paths represented by the run, including synthetic missing
            inputs appended after selected paths.
        release_views: Whether to release context-owned transient views after each
            durable result snapshot is created.

    Yields:
        Internal machine stream events suitable for presentation or NDJSON output.
    """
    path_tuple: tuple[Path, ...] = tuple(paths)
    yield MachineRunStartedEvent(
        command=command,
        selected_count=len(path_tuple),
        paths=path_tuple,
    )
    for index, result in enumerate(
        iter_processing_results(contexts, release_views=release_views),
    ):
        yield MachineProcessingResultEvent(
            command=command,
            index=index,
            result=result,
        )
    yield MachineRunCompletedEvent(
        command=command,
    )


def observe_processing_stream(
    events: Iterable[MachineProcessingStreamEvent],
    *,
    stats: ProcessingStreamStats,
    would_change: Callable[[ProcessingResult], bool],
) -> Iterator[MachineProcessingStreamEvent]:
    """Yield processing stream events while recording CLI summary statistics.

    Args:
        events: Internal machine processing stream events.
        stats: Mutable statistics object updated for each file-result event.
        would_change: Command-specific dry-run would-change predicate.

    Yields:
        The original events, preserving order and object identity.
    """
    for event in events:
        if isinstance(event, MachineProcessingResultEvent):
            stats.observe(
                event.result,
                would_change=would_change(event.result),
            )
        yield event
