# topmark:header:start
#
#   project      : TopMark
#   file         : streaming.py
#   file_relpath : src/topmark/pipeline/machine/streaming.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Internal streaming adapters for pipeline NDJSON machine output.

This module bridges durable pipeline results to the NDJSON serializer without
changing the public streaming event DTOs. The public `FileResultEvent` and
`ProbeFileResultEvent` values intentionally expose a reduced API view; existing
NDJSON contracts still require the richer durable `ProcessingResult` payload
shape. These internal events therefore keep a public-style stream lifecycle while
carrying the durable result needed to preserve the current schema exactly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from typing import Literal
from typing import TypeAlias

if TYPE_CHECKING:
    from collections.abc import Iterable
    from collections.abc import Iterator
    from pathlib import Path

    from topmark.pipeline.kinds import PipelineKindLiteral
    from topmark.pipeline.result import ProcessingResult


@dataclass(frozen=True, kw_only=True, slots=True)
class MachineRunStartedEvent:
    """Internal run-start event for pipeline machine-output streams.

    Attributes:
        kind: Stable internal event kind.
        command: Command family represented by this stream.
        selected_count: Number of selected file paths.
        paths: Ordered selected paths associated with the run.
    """

    kind: Literal["run_started"]
    command: PipelineKindLiteral
    selected_count: int
    paths: tuple[Path, ...]


@dataclass(frozen=True, kw_only=True, slots=True)
class MachineProcessingResultEvent:
    """Internal per-file event carrying a durable processing result.

    Attributes:
        kind: Stable internal event kind.
        command: Command family represented by this stream.
        index: Zero-based result index in deterministic processing order.
        result: Durable processing result used for existing machine payloads.
    """

    kind: Literal["file_result"]
    command: PipelineKindLiteral
    index: int
    result: ProcessingResult


@dataclass(frozen=True, kw_only=True, slots=True)
class MachineRunCompletedEvent:
    """Internal run-completed event for pipeline machine-output streams.

    Attributes:
        kind: Stable internal event kind.
        command: Command family represented by this stream.
    """

    kind: Literal["run_completed"]
    command: PipelineKindLiteral


MachineProcessingStreamEvent: TypeAlias = (
    MachineRunStartedEvent | MachineProcessingResultEvent | MachineRunCompletedEvent
)
"""Internal pipeline machine stream event union."""


def iter_machine_processing_stream(
    results: Iterable[ProcessingResult],
    *,
    command: PipelineKindLiteral,
) -> Iterator[MachineProcessingStreamEvent]:
    """Yield internal machine stream events for durable processing results.

    Args:
        results: Durable processing or probe results in command order.
        command: Command family represented by the stream.

    Yields:
        One run-start event, one per-file result event per durable result, and
        one run-completed event in deterministic order.
    """
    result_tuple: tuple[ProcessingResult, ...] = tuple(results)
    yield MachineRunStartedEvent(
        kind="run_started",
        command=command,
        selected_count=len(result_tuple),
        paths=tuple(result.path for result in result_tuple),
    )
    for index, result in enumerate(result_tuple):
        yield MachineProcessingResultEvent(
            kind="file_result",
            command=command,
            index=index,
            result=result,
        )
    yield MachineRunCompletedEvent(
        kind="run_completed",
        command=command,
    )
