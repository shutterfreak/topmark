# topmark:header:start
#
#   project      : TopMark
#   file         : comparer.py
#   file_relpath : src/topmark/pipeline/steps/comparer.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Header comparer step for the TopMark pipeline (view-based).

This step assigns a `ComparisonStatus` by comparing the *existing* header (from `HeaderView`)
with the *expected* header produced by the renderer (from RenderView). The comparer prefers a
**semantic (dict‑wise) comparison** of header fields and falls back to a
**formatting comparison** when content is equal but layout differs. In `strip`
pipelines (or when an update has already produced a full image), it can perform a
full-file comparison.

Summary of behavior:
  • If `ctx.updated` carries an updated image, compare full file images.
  • If `generation` is `PENDING` (pipelines that don’t render), set `UNCHANGED`.
  • Else, compare dicts: `ctx.header.mapping` vs `ctx.build.selected`:
      – If dicts differ → `CHANGED`.
      – If dicts equal but *rendered block* differs from existing block
        (ordering/spacing/affixes/newlines), treat this as a **formatting
        change** → `CHANGED`.
  • Otherwise → `UNCHANGED`.

This contract keeps CLI summaries consistent: content changes and pure formatting
drifts both show up as "would update header", whereas true matches land in
"up‑to‑date".
"""

from __future__ import annotations

from typing import Iterable, Sequence

from topmark.config.logging import TopmarkLogger, get_logger
from topmark.pipeline.context import (
    ComparisonStatus,
    GenerationStatus,
    HeaderStatus,
    ProcessingContext,
    may_proceed_to_comparer,
)

logger: TopmarkLogger = get_logger(__name__)


def compare(ctx: ProcessingContext) -> ProcessingContext:
    """Compare existing vs expected header and set `ctx.status.comparison`.

    The step runs only when header generation has completed or when there are no
    header fields to generate. In other cases it returns the context unchanged.

    Decision tree:
      1. **Precomputed image**: If `ctx.updated_file_lines` exists (e.g., `strip`), set
         `UNCHANGED` iff `file_lines == updated_file_lines`; else `CHANGED`.
      2. **No generation**: If `generation == PENDING`, set `UNCHANGED`.
      3. **Dict‑wise content**: Compare `existing_header_dict` vs `expected_header_dict`.
         – Different → `CHANGED`.
         – Equal → proceed to (4).
      4. **Formatting fallback**: If we have both `existing_header_block` and
         `expected_header_lines`, compare exact block text. If blocks differ (order,
         alignment, spacing, affixes, newline style), set `CHANGED`; otherwise `UNCHANGED`.

    Args:
        ctx (ProcessingContext): The processing context carrying file state, statuses,
            and dictionaries.

    Returns:
        ProcessingContext: The same context, with `status.comparison` updated to
            ``CHANGED`` or ``UNCHANGED`` when applicable.
    """
    logger.debug("ctx: %s", ctx)

    logger.debug("ctx.config.apply_changes = %s", ctx.config.apply_changes)

    if not may_proceed_to_comparer(ctx):
        logger.info("Comparer skipped by may_proceed_to_comparer()")
        return ctx

    # Skip comparison if malformed headers
    if ctx.status.header in {
        HeaderStatus.MALFORMED,
        HeaderStatus.MALFORMED_ALL_FIELDS,
        HeaderStatus.MALFORMED_SOME_FIELDS,
    }:
        ctx.status.comparison = ComparisonStatus.SKIPPED
        return ctx
    logger.debug("OK to proceed, header Status: %s", ctx.status.header.value)

    # If we have a precomputed full file updated content, use direct comparison
    # (relevant for the strip pipeline)
    if ctx.updated and ctx.updated.lines is not None:
        # 1) Full file image comparison (strip step or similar)
        current_lines: list[str] = list(ctx.iter_file_lines())
        updated_seq: Sequence[str] | Iterable[str] = ctx.updated.lines
        updated_lines: list[str] = (
            updated_seq if isinstance(updated_seq, list) else list(updated_seq)
        )
        if current_lines == updated_lines:
            ctx.status.comparison = ComparisonStatus.UNCHANGED
        else:
            ctx.status.comparison = ComparisonStatus.CHANGED
        logger.debug(
            "comparer: full-image comparison for %s -> %s",
            ctx.path,
            ctx.status.comparison.value,
        )
        return ctx

    # 2) If generation status is PENDING, mark as UNCHANGED for pipelines that don't render
    # (e.g., 'strip')
    if ctx.status.generation == GenerationStatus.PENDING:
        ctx.status.comparison = ComparisonStatus.UNCHANGED
        logger.debug(
            "comparer: generation=%s; no generation and no precomputed output for %s -> UNCHANGED",
            ctx.status.generation.value,
            ctx.path,
        )
        return ctx

    # 3) Dict-wise comparison using views
    existing_dict: dict[str, str] = (
        ctx.header.mapping if (ctx.header and ctx.header.mapping) else {}
    )
    expected_dict: dict[str, str] = ctx.build.selected if (ctx.build and ctx.build.selected) else {}
    ctx.status.comparison = (
        ComparisonStatus.UNCHANGED if existing_dict == expected_dict else ComparisonStatus.CHANGED
    )
    logger.trace("Existing header dict: %s", existing_dict)
    logger.trace("Expected header dict: %s", expected_dict)

    # 4) Formatting fallback: compare rendered vs existing block text
    # If field content is equal but formatting/order/spacing differs, optionally
    # mark as CHANGED so the CLI can propose a formatting update. This relies on
    # comparing the exact rendered block to the existing block captured by the
    # scanner. Only applies when we actually detected a header and have a render.
    if (
        ctx.status.comparison is ComparisonStatus.UNCHANGED
        and ctx.header
        and ctx.header.block is not None
        and ctx.render
        and ctx.render.block is not None
    ):
        if ctx.header.block != ctx.render.block:
            logger.debug(
                "Header dicts equal but block text differs for %s → formatting change",
                ctx.path,
            )
            ctx.status.comparison = ComparisonStatus.CHANGED

    logger.debug(
        "Comparer: %s – header status=%s, comparison=%s",
        ctx.path,
        ctx.status.header.value,
        ctx.status.comparison.value,
    )

    return ctx
