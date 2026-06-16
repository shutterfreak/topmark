# topmark:header:start
#
#   project      : TopMark
#   file         : runner.py
#   file_relpath : src/topmark/pipeline/runner.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Run the TopMark V2 header processing pipeline for a single file.

This module defines the HeaderProcessor protocol interface, a registry system for
associating file extensions with processor implementations, and helper functions
for processor lookup and registration. It enables extensible, comment-style-based
header processing for different file types.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.core.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Sequence

    from topmark.core.logging import TopmarkLogger
    from topmark.pipeline.context.model import ProcessingContext
    from topmark.pipeline.protocols import Step
    from topmark.pipeline.views import ViewSlot

logger: TopmarkLogger = get_logger(__name__)


def run(
    ctx: ProcessingContext,
    steps: Sequence[Step[ProcessingContext]],
    *,
    prune_views: bool = True,
    keep_diff_view: bool = False,
) -> ProcessingContext:
    """Execute the pipeline sequentially.

    Args:
        ctx: Mutable processing context.
        steps: Ordered sequence of pipeline steps. Each step takes and returns a context.
        prune_views: Release consumed view payloads between steps once no remaining
            step declares them as consumed (default: `True`).
        keep_diff_view: Whether to preserve the diff view during between-step pruning
            (required when the pipeline generates a unified diff in
            [`PatcherStep`][topmark.pipeline.steps.patcher.PatcherStep]).

    Returns:
        The final processing context after all steps have run.
    """
    step_count: int = len(steps)
    for index, step in enumerate(steps):
        ctx = step(ctx)
        if prune_views is True:
            remaining_view_consumers: set[ViewSlot] = set()
            for remaining_step in steps[index + 1 : step_count]:
                remaining_view_consumers.update(remaining_step.consumes_views)
            ctx.views.release_consumed(
                remaining_view_consumers=remaining_view_consumers,
                keep_diff_view=keep_diff_view,
            )

    return ctx
