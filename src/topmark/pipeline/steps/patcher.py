# topmark:header:start
#
#   project      : TopMark
#   file         : patcher.py
#   file_relpath : src/topmark/pipeline/steps/patcher.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Patch (diff) generation step for the TopMark pipeline (view-based).

This step compares the original file image (``ctx.image``) with the pipeline’s
updated image (``ctx.updated``) and produces a unified diff suitable for CLI/CI
consumption. It mutates only the processing context and performs no I/O.

Inputs:
  * ``ctx.image`` – original file image view.
  * ``ctx.updated`` – updated file image view (populated by ``updater``).

Outputs:
  * ``ctx.diff`` – :class:`DiffView` carrying the unified diff text (or ``None``).
"""

from __future__ import annotations

import difflib
from typing import Iterable, Sequence

from yachalk import chalk

from topmark.config.logging import TopmarkLogger, get_logger
from topmark.pipeline.context import ComparisonStatus, ProcessingContext, may_proceed_to_patcher
from topmark.pipeline.views import DiffView
from topmark.utils.diff import render_patch

logger: TopmarkLogger = get_logger(__name__)


def patch(ctx: ProcessingContext) -> ProcessingContext:
    """Generate and attach a unified diff to the processing context (view-based).

    The step runs only after comparison. If the comparison status is
    ``UNCHANGED`` or if no updated image is present, the diff is omitted.

    Args:
        ctx (ProcessingContext): The processing context holding original/updated images
            and statuses.

    Returns:
        ProcessingContext: The same context with ``ctx.diff`` set when a change is
            detected, and with comparison status normalized when applicable.
    """
    logger.debug("ctx: %s", ctx)

    # Safeguard: Only run when comparison was performed
    if not may_proceed_to_patcher(ctx):
        logger.info("Patcher skipped by may_proceed_to_patcher()")
        return ctx

    # If nothing changed, ensure no diff is attached
    if ctx.status.comparison == ComparisonStatus.UNCHANGED:
        ctx.diff = DiffView(text=None)
        return ctx

    logger.debug(
        "File '%s' : header status %s, header comparison status: %s",
        ctx.path,
        ctx.status.header.value,
        ctx.status.comparison.value,
    )

    # Materialize lines from views once for diffing
    current_lines: list[str] = list(ctx.iter_file_lines())
    updated_lines: list[str] | None = None
    if ctx.updated and ctx.updated.lines is not None:
        updated_seq: Sequence[str] | Iterable[str] = ctx.updated.lines
        updated_lines = updated_seq if isinstance(updated_seq, list) else list(updated_seq)

    logger.trace("Current file lines: %d", len(current_lines))
    logger.trace(
        "Updated file lines: %s", "None" if updated_lines is None else str(len(updated_lines))
    )

    # We only generate a diff when we have an updated image; otherwise skip.
    if updated_lines is None:
        logger.debug(
            "Patch skipped for %s: comparison=%s but no updated image present",
            ctx.path,
            ctx.status.comparison.value,
        )
        ctx.diff = DiffView(text=None)
        return ctx

    patch_lines: list[str] = list(
        difflib.unified_diff(
            current_lines,
            updated_lines,
            fromfile=f"{ctx.path} (current)",
            tofile=f"{ctx.path} (updated)",
            n=3,
            lineterm=ctx.newline_style,
        )
    )

    if len(patch_lines) == 0:
        ctx.status.comparison = ComparisonStatus.UNCHANGED
        ctx.diff = DiffView(text=None)
        logger.debug("File header unchanged: %s", ctx.path)
        return ctx

    logger.info("Patch (rendered):\n%s", render_patch(patch_lines))

    # Join exactly as produced by difflib. Do not introduce CRLF conversions.
    ctx.diff = DiffView(text="".join(patch_lines))

    # write_patch(context.header_diff, context.path.as_posix() + ".diff")

    logger.debug(
        "\n===DIFF START ===\n%s=== DIFF END ===",
        chalk.yellow_bright.bg_blue(ctx.diff.text or ""),
    )

    # Note: this step does not print; the CLI decides how to display diffs.

    return ctx
