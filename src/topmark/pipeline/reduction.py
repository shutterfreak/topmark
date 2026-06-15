# topmark:header:start
#
#   project      : TopMark
#   file         : reduction.py
#   file_relpath : src/topmark/pipeline/reduction.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Batch handover helpers for durable pipeline result reduction.

This module defines the explicit boundary between mutable pipeline execution
state and durable result state. The current helper is intentionally a *batch*
reducer: it consumes already-produced
[`ProcessingContext`][topmark.pipeline.context.model.ProcessingContext]
instances and returns matching
[`ProcessingResult`][topmark.pipeline.result.ProcessingResult] snapshots.

It does not introduce per-file streaming consolidation, incremental summary
updates, or early release of context-owned views. Its purpose is to make the
handover seam typed and testable so later work can decide whether this boundary
can move earlier in the processing loop.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from topmark.pipeline.result import ProcessingResult

if TYPE_CHECKING:
    from collections.abc import Iterable

    from topmark.pipeline.context.model import ProcessingContext


@dataclass(frozen=True, kw_only=True, slots=True)
class ProcessingReduction:
    """Batch reduction result for processed pipeline contexts.

    Attributes:
        contexts: Immutable tuple of the source mutable processing contexts.
            These are retained intentionally for current CLI, API, human-output,
            probe-output, and machine-detail consumers.
        results: Immutable tuple of durable processing-result snapshots reduced
            from `contexts` in the same order.
    """

    contexts: tuple[ProcessingContext, ...]
    results: tuple[ProcessingResult, ...]


def reduce_processing_contexts(
    contexts: Iterable[ProcessingContext],
) -> ProcessingReduction:
    """Reduce completed processing contexts to durable results as a batch.

    This helper marks the current post-run handover boundary. It preserves the
    source contexts while creating detached durable result snapshots, which lets
    existing context-based consumers keep working while summary and exit-code
    logic gains a result-compatible seam.

    Args:
        contexts: Completed or partially completed processing contexts to reduce.

    Returns:
        Batch reduction containing the source contexts and corresponding
        durable results in matching order.
    """
    source_contexts: tuple[ProcessingContext, ...] = tuple(contexts)
    return ProcessingReduction(
        contexts=source_contexts,
        results=tuple(ProcessingResult.from_context(ctx) for ctx in source_contexts),
    )
