# topmark:header:start
#
#   project      : TopMark
#   file         : reduction.py
#   file_relpath : src/topmark/pipeline/reduction.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Reduction helpers for durable pipeline result snapshots.

This module defines the explicit boundary between mutable pipeline execution
state and durable result state. The iterator helper reduces completed
[`ProcessingContext`][topmark.pipeline.context.model.ProcessingContext]
instances one at a time, allowing callers to release volatile context-owned
view payloads immediately after each durable
[`ProcessingResult`][topmark.pipeline.result.ProcessingResult] snapshot is
created.

The batch helper remains available for callers that need stable, ordered
materialization for summaries, machine-output envelopes, public API DTOs, or
other full-run reporting contracts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from topmark.pipeline.result import ProcessingResult

if TYPE_CHECKING:
    from collections.abc import Iterable
    from collections.abc import Iterator

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


def iter_processing_results(
    contexts: Iterable[ProcessingContext],
    *,
    release_views: bool = False,
) -> Iterator[ProcessingResult]:
    """Yield durable processing results from completed contexts.

    This helper is the streaming-capable reduction boundary. It snapshots each
    mutable context into a durable result before advancing to the next context.
    When requested, volatile view payloads owned by that context are released
    immediately after the snapshot is created.

    Args:
        contexts: Completed or partially completed processing contexts to reduce.
        release_views: Whether to release context-owned view payloads after each
            durable snapshot has been created. This never runs before
            `ProcessingResult.from_context()` has copied result-owned detail
            fields such as `diff_text`.

    Yields:
        Durable processing-result snapshots in the same order as the input
        contexts.
    """
    for ctx in contexts:
        result: ProcessingResult = ProcessingResult.from_context(ctx)
        if release_views is True:
            ctx.views.release_all()
        yield result


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
    if retain_contexts is True:
        source_contexts: tuple[ProcessingContext, ...] = tuple(contexts)
        results: tuple[ProcessingResult, ...] = tuple(
            iter_processing_results(source_contexts, release_views=release_views),
        )
        return ProcessingReduction(contexts=source_contexts, results=results)

    return ProcessingReduction(
        contexts=(),
        results=tuple(iter_processing_results(contexts, release_views=release_views)),
    )
