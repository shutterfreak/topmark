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

from topmark.config.logging import TopmarkLogger, get_logger
from topmark.constants import VALUE_NOT_SET

if TYPE_CHECKING:
    from collections.abc import Sequence

    from .context import ProcessingContext
    from .contracts import Step

logger: TopmarkLogger = get_logger(__name__)


def run(ctx: ProcessingContext, steps: Sequence[Step]) -> ProcessingContext:
    """Execute the pipeline sequentially.

    Args:
        ctx (ProcessingContext): Mutable processing context.
        steps (Sequence[Step]): Ordered sequence of pipeline steps.
            Each step takes and returns a context.

    Returns:
        ProcessingContext: The final processing context after all steps have run.
    """
    logger.info(
        "header_format: %s",
        ctx.config.header_format.value if ctx.config.header_format else VALUE_NOT_SET,
    )
    for step in steps:
        ctx = step(ctx)
    return ctx
