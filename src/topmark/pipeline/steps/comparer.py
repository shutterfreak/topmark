# topmark:header:start
#
#   project      : TopMark
#   file         : comparer.py
#   file_relpath : src/topmark/pipeline/steps/comparer.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Classify differences between the current and expected file/header views.

The comparer rejects malformed headers first. It then prefers one valid structured
edit as proof of change, falls back to full-image comparison when an updated image
is available, and finally compares semantic header mappings followed by exact block
content when the current content is known.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.core.logging import get_logger
from topmark.pipeline.hints import Axis
from topmark.pipeline.hints import Cluster
from topmark.pipeline.hints import KnownCode
from topmark.pipeline.status import ComparisonStatus
from topmark.pipeline.status import HeaderStatus
from topmark.pipeline.status import RenderStatus
from topmark.pipeline.steps.base import BaseStep
from topmark.pipeline.views import ViewSlot

if TYPE_CHECKING:
    from collections.abc import Mapping

    from topmark.core.logging import TopmarkLogger
    from topmark.pipeline.context.model import ProcessingContext
    from topmark.pipeline.views import BuilderView
    from topmark.pipeline.views import EditView
    from topmark.pipeline.views import HeaderView
    from topmark.pipeline.views import PlannedEdit
    from topmark.pipeline.views import RenderView
    from topmark.pipeline.views import UpdatedView

logger: TopmarkLogger = get_logger(__name__)


class ComparerStep(BaseStep):
    """Classify current versus expected content on the comparison axis.

    The step consumes current, header, build, render, structured-edit, and updated
    views. It writes only `ComparisonStatus` and may add comparer diagnostics,
    hints, or a malformed-header halt.

    Axes written:
      - comparison

    Sets:
      - ComparisonStatus: {CHANGED, UNCHANGED, SKIPPED}
    """

    def __init__(self) -> None:
        super().__init__(
            name=self.__class__.__name__,
            primary_axis=Axis.COMPARISON,
            axes_written=(Axis.COMPARISON,),
            consumes_views=frozenset(
                {
                    ViewSlot.IMAGE,
                    ViewSlot.HEADER,
                    ViewSlot.BUILD,
                    ViewSlot.RENDER,
                    ViewSlot.UPDATED,
                    ViewSlot.EDIT,
                }
            ),
        )

    def may_proceed(
        self,
        ctx: ProcessingContext,
    ) -> bool:
        """Return whether a non-halted context has comparison-ready output.

        A rendered result is ready. An updated view is ready when its ``lines``
        payload is present, including an empty sequence. Resolution, generation,
        and empty-file policy are owned by earlier steps and are not re-evaluated
        here.

        Args:
            ctx: The processing context for the current file.

        Returns:
            True if comparison can run, False otherwise.
        """
        if ctx.is_halted:
            return False

        # Rendering workflows:
        rendered_ready: bool = ctx.status.render == RenderStatus.RENDERED
        # Workflows with a precomputed updated image, including strip:
        updated_ready: bool = ctx.views.updated is not None and ctx.views.updated.lines is not None
        return rendered_ready or updated_ready

    def run(
        self,
        ctx: ProcessingContext,
    ) -> None:
        """Set comparison status using the ordered view-based decision tree.

        `may_proceed()` admits a rendered result or an updated-lines payload. Once
        admitted, malformed headers are skipped first. A single in-bounds structured
        edit then proves a change without materializing full images. Otherwise an
        available updated image is compared with the current image. If neither path
        applies, rendered flows compare header/build mappings and exact header/render
        text when the existing content is known. A missing header is known empty text,
        so a non-empty rendered block is classified as an insertion change.

        Args:
            ctx: The processing context carrying statuses and comparison views.

        Mutations:
            ProcessingContext: `status.comparison`, diagnostics, and halt state as
                required by the selected branch.
        """
        logger.debug("ctx: %s", ctx)

        logger.debug("ctx.run_options.apply_changes = %s", ctx.run_options.apply_changes)

        # Skip comparison if malformed header fields
        # TODO: enable comparing based on future policy:
        if ctx.status.header in {
            HeaderStatus.MALFORMED_ALL_FIELDS,
            HeaderStatus.MALFORMED_SOME_FIELDS,
        }:
            ctx.status.comparison = ComparisonStatus.SKIPPED
            reason: str = f"Skipped: {ctx.status.header.value}"
            ctx.diagnostics.add_warning(reason)
            ctx.request_halt(reason=reason, at_step=self)
            return

        logger.debug("OK to proceed, header Status: %s", ctx.status.header.value)

        # If a prior step produced structured edit metadata, use it as the
        # comparison source of truth. Planner/stripper own this metadata and
        # emit edits only after constructing an updated image, so a valid
        # non-empty edit means the file image would change without needing to
        # materialize both complete images just to prove inequality.
        edit_view: EditView | None = ctx.views.edit
        if edit_view is not None and len(edit_view.edits) == 1:
            edit: PlannedEdit = edit_view.edits[0]
            if (
                edit.old_start >= 0
                and edit.old_end >= edit.old_start
                and edit.old_end <= ctx.image_line_count()
            ):
                ctx.status.comparison = ComparisonStatus.CHANGED
                logger.debug(
                    "comparer: single-edit comparison for %s -> %s",
                    ctx.path,
                    ctx.status.comparison.value,
                )
                return

        # If we have a precomputed full file updated content but no usable edit
        # metadata, fall back to direct full-image comparison.
        updated_view: UpdatedView | None = ctx.views.updated
        if updated_view and updated_view.lines is not None:
            # Full file image comparison (strip step or similar)
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

        # Dict-wise comparison using views.
        header_view: HeaderView | None = ctx.views.header
        builder_view: BuilderView | None = ctx.views.build
        existing_dict: Mapping[str, str] = (
            header_view.mapping if (header_view and header_view.mapping) else {}
        )
        expected_dict: Mapping[str, str] = (
            builder_view.selected if (builder_view and builder_view.selected) else {}
        )
        ctx.status.comparison = (
            ComparisonStatus.UNCHANGED
            if existing_dict == expected_dict
            else ComparisonStatus.CHANGED
        )
        logger.trace("Existing header dict: %s", existing_dict)
        logger.trace("Expected header dict: %s", expected_dict)

        # Block fallback: compare rendered vs known existing block text.
        # If field content is equal but formatting/order/spacing differs, optionally
        # mark as CHANGED so the CLI can propose a formatting update. A missing header
        # has known empty content, allowing a rendered markers-only block to be compared
        # without treating absent views in other states as empty.
        render_view: RenderView | None = ctx.views.render
        existing_block: str | None = (
            ""
            if ctx.status.header == HeaderStatus.MISSING
            else header_view.block
            if header_view
            else None
        )
        if (
            ctx.status.comparison == ComparisonStatus.UNCHANGED
            and existing_block is not None
            and render_view
            and render_view.block is not None
        ) and existing_block != render_view.block:
            if header_view and header_view.block is not None:
                ctx.diagnostics.add_info(
                    "Header fields unchanged, rendered header block text differs "
                    "→ formatting change",
                )
            ctx.status.comparison = ComparisonStatus.CHANGED

        logger.debug(
            "Comparer: %s - header status=%s, comparison=%s",
            ctx.path,
            ctx.status.header.value,
            ctx.status.comparison.value,
        )

        return

    def hint(
        self,
        ctx: ProcessingContext,
    ) -> None:
        """Attach comparison hints (non-binding).

        Args:
            ctx: The processing context.

        Raises:
            RuntimeError: If the context contains an unexpected comparison status value.
        """
        st: ComparisonStatus = ctx.status.comparison

        match st:
            # May proceed to next step (always):
            case ComparisonStatus.CHANGED:
                if ctx.run_options.apply_changes is True:
                    ctx.hint(
                        axis=Axis.COMPARISON,
                        code=KnownCode.COMPARE_CHANGED,
                        cluster=Cluster.CHANGED,
                        message="differences detected",
                    )
                else:
                    ctx.hint(
                        axis=Axis.COMPARISON,
                        code=KnownCode.COMPARE_WOULD_CHANGE,
                        cluster=Cluster.WOULD_CHANGE,
                        message="differences detected",
                    )
            case ComparisonStatus.UNCHANGED:
                ctx.hint(
                    axis=Axis.COMPARISON,
                    code=KnownCode.COMPARE_UNCHANGED,
                    cluster=Cluster.UNCHANGED,
                    message="no differences detected",
                )

            # Stop processing:
            case ComparisonStatus.SKIPPED:
                ctx.hint(
                    axis=Axis.COMPARISON,
                    code=KnownCode.COMPARE_SKIPPED,
                    cluster=Cluster.SKIPPED,
                    message="comparison skipped",
                    terminal=True,
                )

            # States owned outside this step:
            case (
                ComparisonStatus.PENDING
            ):  # pragma: no cover - BaseStep owns pending-state handling.
                # BaseStep.__call__() handles PENDING state (step did not complete)
                pass

            case _:  # pragma: no cover - exhaustive enum guard for untyped callers.
                raise RuntimeError(f"Unexpected ComparisonStatus found: {st!r}")
