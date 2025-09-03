# topmark:header:start
#
#   file         : comparer.py
#   file_relpath : src/topmark/pipeline/steps/comparer.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Header comparer step for the TopMark pipeline.

This step assigns a `ComparisonStatus` by comparing the *existing* header with the
*expected* header produced by the render step. The comparer prefers a
**semantic (dict‑wise) comparison** of header fields and falls back to a
**formatting comparison** when content is equal but layout differs. In `strip`
pipelines (or any path that precomputes `updated_file_lines`), it performs a
full‑file image comparison.

Summary of behavior:
  • If `ctx.updated_file_lines` is provided (e.g., `strip` step), compare the entire
    file image (`file_lines` vs `updated_file_lines`).
  • If `generation` is `PENDING` (pipelines that don’t render), set `UNCHANGED`.
  • Else, compare `existing_header_dict` vs `expected_header_dict`:
      – If dicts differ → `CHANGED`.
      – If dicts are equal but the *rendered block text* differs from the existing
        block (ordering/spacing/affixes/newlines), treat this as a **formatting
        change** → `CHANGED`.
  • Otherwise → `UNCHANGED`.

This contract keeps CLI summaries consistent: content changes and pure formatting
drifts both show up as "would update header", whereas true matches land in
"up‑to‑date".
"""

from topmark.config.logging import get_logger
from topmark.pipeline.context import (
    ComparisonStatus,
    GenerationStatus,
    ProcessingContext,
)

logger = get_logger(__name__)


def compare(ctx: ProcessingContext) -> ProcessingContext:
    """Compare existing vs expected header and set `ctx.status.comparison`.

    The step runs only when header generation has completed or when there are no
    header fields to generate. In other cases it returns the context unchanged.

    Decision tree:
      1) **Precomputed image**: If `ctx.updated_file_lines` exists (e.g., `strip`), set
         `UNCHANGED` iff `file_lines == updated_file_lines`; else `CHANGED`.
      2) **No generation**: If `generation == PENDING`, set `UNCHANGED`.
      3) **Dict‑wise content**: Compare `existing_header_dict` vs `expected_header_dict`.
         – Different → `CHANGED`.
         – Equal → proceed to (4).
      4) **Formatting fallback**: If we have both `existing_header_block` and
         `expected_header_lines`, compare exact block text. If blocks differ (order,
         alignment, spacing, affixes, newline style), set `CHANGED`; otherwise `UNCHANGED`.

    Args:
        ctx: The processing context carrying file state, statuses, and dictionaries.

    Returns:
        ProcessingContext: The same context, with `status.comparison` updated to
        ``CHANGED`` or ``UNCHANGED`` when applicable.
    """
    # If we have a precomputed full file updated content, use direct comparison
    # (relevant for the strip pipeline)
    if ctx.updated_file_lines is not None:
        # Full file image comparison (strip step or similar)
        if ctx.file_lines == ctx.updated_file_lines:
            ctx.status.comparison = ComparisonStatus.UNCHANGED
        else:
            ctx.status.comparison = ComparisonStatus.CHANGED
        logger.debug(
            "comparer: precomputed full-file comparison for %s -> %s",
            ctx.path,
            ctx.status.comparison.value,
        )
        return ctx

    # If generation status is PENDING, mark as UNCHANGED for pipelines that don't render
    # (e.g., 'strip')
    if ctx.status.generation == GenerationStatus.PENDING:
        ctx.status.comparison = ComparisonStatus.UNCHANGED
        logger.debug(
            "comparer: no generation and no precomputed output for %s -> UNCHANGED",
            ctx.path,
        )
        return ctx

    # Prefer dictionary comparison when we have rendered/parsed data
    logger.trace("Existing header dict: %s", ctx.existing_header_dict)
    logger.trace("Expected header dict: %s", ctx.expected_header_dict)
    ctx.status.comparison = (
        ComparisonStatus.UNCHANGED
        if ctx.existing_header_dict == ctx.expected_header_dict
        else ComparisonStatus.CHANGED
    )

    # If field content is equal but formatting/order/spacing differs, optionally
    # mark as CHANGED so the CLI can propose a formatting update. This relies on
    # comparing the exact rendered block to the existing block captured by the
    # scanner. Only applies when we actually detected a header and have a render.
    if (
        ctx.status.comparison is ComparisonStatus.UNCHANGED
        and ctx.existing_header_block is not None
        and ctx.expected_header_lines is not None
    ):
        existing_block = ctx.existing_header_block
        expected_block = "".join(ctx.expected_header_lines)
        if existing_block != expected_block:
            logger.debug(
                "Header dicts equal but block text differs for %s → formatting change",
                ctx.path,
            )
            ctx.status.comparison = ComparisonStatus.CHANGED

    logger.debug(
        "File '%s' : header status %s, header dict-wise comparison: %s",
        ctx.path,
        ctx.status.header.value,
        ctx.status.comparison.value,
    )

    return ctx
