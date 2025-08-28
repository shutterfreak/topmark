# topmark:header:start
#
#   file         : patcher.py
#   file_relpath : src/topmark/pipeline/steps/patcher.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Patch (diff) generation step for the TopMark pipeline.

This step compares the original file content with the pipeline's updated content
and produces a unified diff (header patch). It also formats a colorized preview
for logging and CLI display.
"""

import difflib

from yachalk import chalk

from topmark.config.logging import get_logger
from topmark.pipeline.context import ComparisonStatus, ProcessingContext
from topmark.utils.diff import render_patch

logger = get_logger(__name__)


def patch(ctx: ProcessingContext) -> ProcessingContext:
    """Generate and attach a unified diff to the processing context.

    The step runs only when the comparison status is either ``CHANGED`` or
    ``UNCHANGED``. For unchanged inputs, the diff is empty and the status is
    normalized to ``UNCHANGED``.

    Args:
        ctx: The processing context holding original/updated lines and statuses.

    Returns:
        ProcessingContext: The same context with ``header_diff`` set when a
        change is detected, and with comparison status updated.
    """
    # Safeguard: Only run when comparison was performed
    if ctx.status.comparison not in [
        ComparisonStatus.CHANGED,
        ComparisonStatus.UNCHANGED,
    ]:
        return ctx

    # If nothing changed, ensure no diff is attached
    if ctx.status.comparison is ComparisonStatus.UNCHANGED:
        ctx.header_diff = None
        return ctx

    logger.debug(
        "File '%s' : header status %s, header comparison status: %s",
        ctx.path,
        ctx.status.header.value,
        ctx.status.comparison.value,
    )

    # Generate unified diff using the actual lines from the file for the existing header
    logger.trace("Current file lines: %d: %r", len(ctx.file_lines or []), ctx.file_lines)
    logger.trace(
        "Updated file lines: %d: %r",
        len(ctx.updated_file_lines or []),
        ctx.updated_file_lines,
    )

    # We only generate a diff when we have an updated image; otherwise skip.
    if ctx.updated_file_lines is None:
        logger.debug(
            "Patch skipped for %s: comparison=%s but no updated_file_lines present",
            ctx.path,
            ctx.status.comparison.value,
        )
        ctx.header_diff = None
        return ctx

    patch_lines = list(
        difflib.unified_diff(
            ctx.file_lines or [],
            ctx.updated_file_lines or [],
            fromfile=f"{ctx.path} (current)",
            tofile=f"{ctx.path} (updated)",
            n=3,
            lineterm=ctx.newline_style,
        )
    )

    if len(patch_lines) == 0:
        ctx.status.comparison = ComparisonStatus.UNCHANGED
        ctx.header_diff = None
        logger.debug("File header unchanged: %s", ctx.path)
        return ctx

    logger.info("Patch (rendered):\n%s", render_patch(patch_lines))

    # Join exactly as produced by difflib. Do not introduce CRLF conversions.
    ctx.header_diff = "".join(patch_lines)

    # write_patch(context.header_diff, context.path.as_posix() + ".diff")

    logger.debug(
        "\n===DIFF START ===\n%s=== DIFF END ===",
        chalk.yellow_bright.bg_blue(ctx.header_diff),
    )

    # Note: this step does not print; the CLI decides how to display diffs.

    return ctx
