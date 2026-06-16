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

It does not introduce per-file streaming consolidation or incremental summary
updates. It does provide explicit knobs for whether the handover retains source
contexts and whether volatile context-owned view payloads are released after
durable snapshots have been created.
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
        contexts: Immutable tuple of retained source mutable processing
            contexts. This is empty when the caller requested a reduced-only
            handover.
        results: Immutable tuple of durable processing-result snapshots reduced
            from source contexts in the same order.
    """

    contexts: tuple[ProcessingContext, ...]
    results: tuple[ProcessingResult, ...]


def reduce_processing_contexts(
    contexts: Iterable[ProcessingContext],
    *,
    retain_contexts: bool = True,
    release_views: bool = False,
) -> ProcessingReduction:
    """Reduce completed processing contexts to durable results as a batch.

    This helper marks the current post-run handover boundary. By default it
    preserves source contexts for compatibility with remaining context-based
    consumers. Callers that have migrated to durable results can request a
    reduced-only handover and release volatile view payloads after snapshotting.

    Args:
        contexts: Completed or partially completed processing contexts to reduce.
        retain_contexts: Whether to keep source contexts in the returned
            reduction object. Use ``False`` once all downstream consumers for
            the current command operate on durable results.
        release_views: Whether to release context-owned view payloads after
            durable snapshots have been created. This never runs before
            `ProcessingResult.from_context()` has copied result-owned detail
            fields such as `diff_text`.

    Returns:
        Batch reduction containing durable results and, when requested, the
        retained source contexts in matching order.
    """
    source_contexts: tuple[ProcessingContext, ...] = tuple(contexts)
    results: tuple[ProcessingResult, ...] = tuple(
        ProcessingResult.from_context(ctx) for ctx in source_contexts
    )

    if release_views is True:
        for ctx in source_contexts:
            ctx.views.release_all()

    return ProcessingReduction(
        contexts=source_contexts if retain_contexts is True else (),
        results=results,
    )
