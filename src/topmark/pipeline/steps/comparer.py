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
  • If `ctx.views.updated` carries an updated image, compare full file images.
  • If `generation` is `PENDING` (pipelines that don’t render), set `UNCHANGED`.
  • Else, compare dicts: `ctx.views.header.mapping` vs `ctx.views.build.selected`:
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

from typing import TYPE_CHECKING

from topmark.config.logging import get_logger
from topmark.pipeline.hints import Axis, Cluster, KnownCode
from topmark.pipeline.status import (
    ComparisonStatus,
    GenerationStatus,
    HeaderStatus,
    RenderStatus,
)
from topmark.pipeline.steps.base import BaseStep

if TYPE_CHECKING:
    from topmark.config.logging import TopmarkLogger
    from topmark.pipeline.context.model import ProcessingContext
    from topmark.pipeline.views import BuilderView, HeaderView, RenderView, UpdatedView

logger: TopmarkLogger = get_logger(__name__)


class ComparerStep(BaseStep):
    """Compare existing vs expected header content/format.

    Prefers semantic (field-mapping) comparison and falls back to formatting
    comparison when dictionaries match but layout differs. In strip-mode or when
    an updated image exists, can compare full file images.

    Axes written:
      - comparison

    Sets:
      - ComparisonStatus: {PENDING, CHANGED, UNCHANGED, SKIPPED, CANNOT_COMPARE}
    """

    def __init__(self) -> None:
        super().__init__(
            name=self.__class__.__name__,
            primary_axis=Axis.COMPARISON,
            axes_written=(Axis.COMPARISON,),
        )

    def may_proceed(self, ctx: ProcessingContext) -> bool:
        """Return True if comparison can run.

        Conditions:
          * Resolve succeeded, file type and header processor exist; and
          * One of:
            - Generation is `GENERATED` or `NO_FIELDS`; or
            - Policy allows empty-file processing; or
            - An updated image is already present (strip/update fast path).

        Args:
            ctx (ProcessingContext): The processing context for the current file.

        Returns:
            bool: True if processing can proceed to the build step, False otherwise.
        """
        if ctx.is_halted:
            outcome: bool = False
        else:
            # Check pipelines:
            rendered_ready: bool = ctx.status.render == RenderStatus.RENDERED
            # Strip pipelines:
            # strip_ready   = ctx.status.strip == StripStatus.READY
            # Check and strip pipelines:
            updated_ready: bool = (
                ctx.views.updated is not None and ctx.views.updated.lines is not None
            )
            outcome = (
                rendered_ready
                # or strip_ready
                or updated_ready
            )
        logger.debug("%s may_proceed is %s", self.__class__.__name__, outcome)
        return outcome

    def run(self, ctx: ProcessingContext) -> None:
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

        Mutations:
            ProcessingContext: The same context, with `status.comparison` updated to
                ``CHANGED`` or ``UNCHANGED`` when applicable.
        """
        logger.debug("ctx: %s", ctx)

        logger.debug("ctx.config.apply_changes = %s", ctx.config.apply_changes)

        # Skip comparison if malformed header fields
        # TODO: enable comparing based on future policy:
        if ctx.status.header in {
            HeaderStatus.MALFORMED_ALL_FIELDS,
            HeaderStatus.MALFORMED_SOME_FIELDS,
        }:
            ctx.status.comparison = ComparisonStatus.SKIPPED
            reason = f"Skipped: {ctx.status.header.value}"
            ctx.warn(reason)
            ctx.request_halt(reason=reason, at_step=self)
            return

        logger.debug("OK to proceed, header Status: %s", ctx.status.header.value)

        # If we have a precomputed full file updated content, use direct comparison
        # (relevant for the strip pipeline)
        updated_view: UpdatedView | None = ctx.views.updated
        if updated_view and updated_view.lines is not None:
            # 1) Full file image comparison (strip step or similar)
            current_lines: list[str] = ctx.materialize_image_lines()
            updated_lines: list[str] = ctx.materialize_updated_lines()
            if current_lines == updated_lines:
                ctx.status.comparison = ComparisonStatus.UNCHANGED
            else:
                ctx.status.comparison = ComparisonStatus.CHANGED
            logger.debug(
                "comparer: full-image comparison for %s -> %s",
                ctx.path,
                ctx.status.comparison.value,
            )
            return

        # 2) If generation status is PENDING, mark as UNCHANGED for pipelines that don't render
        # (e.g., 'strip')
        if ctx.status.generation == GenerationStatus.PENDING:
            logger.debug(
                "comparer: generation=%s; no generation and no precomputed output "
                "for %s -> UNCHANGED",
                ctx.status.generation.value,
                ctx.path,
            )
            ctx.status.comparison = ComparisonStatus.UNCHANGED
            return

        # 3) Dict-wise comparison using views
        header_view: HeaderView | None = ctx.views.header
        builder_view: BuilderView | None = ctx.views.build
        existing_dict: dict[str, str] = (
            header_view.mapping if (header_view and header_view.mapping) else {}
        )
        expected_dict: dict[str, str] = (
            builder_view.selected if (builder_view and builder_view.selected) else {}
        )
        ctx.status.comparison = (
            ComparisonStatus.UNCHANGED
            if existing_dict == expected_dict
            else ComparisonStatus.CHANGED
        )
        logger.trace("Existing header dict: %s", existing_dict)
        logger.trace("Expected header dict: %s", expected_dict)

        # 4) Formatting fallback: compare rendered vs existing block text
        # If field content is equal but formatting/order/spacing differs, optionally
        # mark as CHANGED so the CLI can propose a formatting update. This relies on
        # comparing the exact rendered block to the existing block captured by the
        # scanner. Only applies when we actually detected a header and have a render.
        render_view: RenderView | None = ctx.views.render
        if (
            ctx.status.comparison is ComparisonStatus.UNCHANGED
            and header_view
            and header_view.block is not None
            and render_view
            and render_view.block is not None
        ) and header_view.block != render_view.block:
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

        return

    def hint(self, ctx: ProcessingContext) -> None:
        """Attach comparison hints (non-binding).

        Args:
            ctx (ProcessingContext): The processing context.
        """
        st: ComparisonStatus = ctx.status.comparison

        # May proceed to next step (always):
        if st == ComparisonStatus.CHANGED:
            ctx.hint(
                axis=Axis.COMPARISON,
                code=KnownCode.COMPARE_CHANGED,
                cluster=Cluster.CHANGED,
                message="differences detected",
            )
        elif st == ComparisonStatus.UNCHANGED:
            ctx.hint(
                axis=Axis.COMPARISON,
                code=KnownCode.COMPARE_UNCHANGED,
                cluster=Cluster.UNCHANGED,
                message="no differences detected",
            )
        # Stop processing:
        elif st == ComparisonStatus.SKIPPED:
            ctx.hint(
                axis=Axis.COMPARISON,
                code=KnownCode.COMPARE_SKIPPED,
                cluster=Cluster.SKIPPED,
                message="comparison skipped",
                terminal=True,
            )
        elif st == ComparisonStatus.PENDING:
            # comparer did not complete
            ctx.request_halt(reason=f"{self.__class__.__name__} did not set state.", at_step=self)
