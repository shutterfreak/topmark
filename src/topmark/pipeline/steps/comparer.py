# topmark:header:start
#
#   file         : comparer.py
#   file_relpath : src/topmark/pipeline/steps/comparer.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Header dictionary comparer step for the TopMark pipeline.

This step compares the **existing** header field dictionary extracted from a
file with the **expected** header field dictionary computed by earlier steps.
Its output is a comparison status flag indicating whether content changed.
"""

from topmark.config.logging import get_logger
from topmark.pipeline.context import (
    ComparisonStatus,
    GenerationStatus,
    ProcessingContext,
)

logger = get_logger(__name__)


def compare(ctx: ProcessingContext) -> ProcessingContext:
    """Compare existing and expected header dictionaries and set comparison status.

    The step runs only when header generation has completed or when there are no
    header fields to generate. In other cases it returns the context unchanged.

    Args:
        ctx: The processing context carrying file state, statuses, and dictionaries.

    Returns:
        ProcessingContext: The same context, with `status.comparison` updated to
        ``CHANGED`` or ``UNCHANGED`` when applicable.
    """
    # Fast path: some pipelines (e.g., 'strip') precompute the new file image
    # in `updated_file_lines` without running builder/renderer. In that case,
    # we compare the full file content directly and set `ComparisonStatus`.
    if ctx.updated_file_lines is not None:
        before = ctx.file_lines or []
        after = ctx.updated_file_lines
        ctx.status.comparison = (
            ComparisonStatus.CHANGED if before != after else ComparisonStatus.UNCHANGED
        )
        logger.debug(
            "comparer: precomputed full-file comparison for %s -> %s",
            ctx.path,
            ctx.status.comparison.value,
        )
        return ctx

    # In pipelines where we never render/generate (e.g., 'strip') and no precomputed
    # output exists, there is nothing to change; treat as UNCHANGED.
    if ctx.status.generation is GenerationStatus.PENDING:
        ctx.status.comparison = ComparisonStatus.UNCHANGED
        logger.debug(
            "comparer: no generation and no precomputed output for %s -> UNCHANGED",
            ctx.path,
        )

    # Safeguard: Only compare when generation completed or no fields were requested
    logger.trace(
        "Status: file: %s, header: %s, generation: %s",
        ctx.status.file.value,
        ctx.status.header.value,
        ctx.status.generation.value,
    )
    if ctx.status.generation not in (
        GenerationStatus.GENERATED,
        GenerationStatus.NO_FIELDS,
    ):
        return ctx

    # Use empty dicts if either side is missing to simplify comparison
    existing = ctx.existing_header_dict or {}
    expected = ctx.expected_header_dict or {}

    logger.trace("Existing header dict: %s", existing)
    logger.trace("Expected header dict: %s", expected)
    # Update comparison status based on content equality
    # if existing == expected:
    #     ctx.status.comparison = ComparisonStatus.UNCHANGED
    # else:
    #     ctx.status.comparison = ComparisonStatus.CHANGED

    # Normal comparison logic for pipelines that generate a header
    before = ctx.file_lines or []
    after = ctx.updated_file_lines or []
    ctx.status.comparison = (
        ComparisonStatus.CHANGED if before != after else ComparisonStatus.UNCHANGED
    )

    logger.debug(
        "File '%s' : header status %s, header content-wise comparison: %s",
        ctx.path,
        ctx.status.header.value,
        ctx.status.comparison.value,
    )

    return ctx
