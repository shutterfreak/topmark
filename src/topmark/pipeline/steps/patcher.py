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

This step compares the original file image (``ctx.image``) with the pipeline's
updated image (``ctx.views.updated``) and produces a unified diff suitable for CLI/CI
consumption. It mutates only the processing context and performs no I/O.

Inputs:
  * ``ctx.views.image`` - [`FileImageView`][topmark.pipeline.views.FileImageView] carrying the
    original file image view.
  * ``ctx.views.updated`` - [`UpdatedView`][topmark.pipeline.views.UpdatedView] carrinyng the
    updated file image (or ``None``)).

Outputs:
  * ``ctx.views.diff`` - [`DiffView`][topmark.pipeline.views.DiffView] carrying the
    unified diff text (or ``None``). Diff file labels are human-facing display labels,
    not machine-readable path serialization fields.
"""

from __future__ import annotations

import difflib
import logging
from typing import TYPE_CHECKING

from topmark.core.logging import get_logger
from topmark.pipeline.hints import Axis
from topmark.pipeline.hints import Cluster
from topmark.pipeline.hints import KnownCode
from topmark.pipeline.status import ComparisonStatus
from topmark.pipeline.status import PatchStatus
from topmark.pipeline.steps.base import BaseStep
from topmark.pipeline.structured_diff import render_structured_unified_diff
from topmark.pipeline.views import DiffView
from topmark.pipeline.views import EditView
from topmark.pipeline.views import UpdatedView
from topmark.pipeline.views import ViewSlot
from topmark.presentation.formatters.unified_diff import format_patch_plain
from topmark.presentation.shared.paths import get_display_path
from topmark.utils.timestamp import format_gnu_diff_timestamp

if TYPE_CHECKING:
    from topmark.core.logging import TopmarkLogger
    from topmark.pipeline.context.model import ProcessingContext


logger: TopmarkLogger = get_logger(__name__)


class PatcherStep(BaseStep):
    """Produce a unified diff between original and updated file images.

    Generates a unified diff (CLI/CI friendly) when comparison indicates a
    change and an updated image is present. Normalizes `ComparisonStatus` to
    `UNCHANGED` if computed diff is empty.

    This step does not print; the CLI or API decides how to display diffs.

    Axes written:
      - comparison  (normalization only; no new comparisons are computed here)

    Sets/normalizes:
      - PatchStatus: {PENDING, GENERATED, SKIPPED, FAILED}
      - PATCH_* hint codes for patch/patcher semantics:
          PATCH_GENERATED: patch generated and available
          PATCH_SKIPPED: no patch needed (unchanged)
          PATCH_FAILED: change detected but patch generation failed
      - ComparisonStatus: {PENDING, CHANGED, UNCHANGED, SKIPPED, CANNOT_COMPARE}
    """

    def __init__(self) -> None:
        super().__init__(
            name=self.__class__.__name__,
            primary_axis=Axis.PATCH,
            axes_written=(
                Axis.COMPARISON,  # For one edge case
                Axis.PATCH,
            ),
            consumes_views=frozenset(
                {
                    ViewSlot.IMAGE,
                    ViewSlot.UPDATED,
                    ViewSlot.EDIT,
                }
            ),
        )

    def may_proceed(self, ctx: ProcessingContext) -> bool:
        """Determine if processing can proceed to the patcher step.

        Processing can proceed if:
        - The comparison step was performed (ctx.status.comparison is CHANGED or UNCHANGED)

        Args:
            ctx: The processing context for the current file.

        Returns:
            True if processing can proceed to the patcher step, False otherwise.
        """
        if ctx.is_halted:
            return False

        return ctx.status.comparison in {
            ComparisonStatus.CHANGED,
            ComparisonStatus.UNCHANGED,
        }

    def run(self, ctx: ProcessingContext) -> None:
        """Generate and attach a unified diff to the processing context (view-based).

        The step runs only after comparison. If the comparison status is
        ``UNCHANGED`` or if no updated image is present, the diff is omitted.

        Unified diff file labels use the shared human-facing display path policy,
        including the logical ``--stdin-filename`` in STDIN content mode.

        Args:
            ctx: The processing context holding original/updated images
                and statuses.

        Mutations:
            ProcessingContext: The same context with ``ctx.views.diff`` set when a change is
                detected, and with comparison status normalized when applicable.

        Raises:
            RuntimeError: During the GitHub issue #167 shadow-validation phase,
                when the structured single-edit diff renderer produces output
                that differs from the current `difflib.unified_diff()` result.
                This temporary assertion protects the existing diff-output
                contract while validating parity before any future backend
                switch.
        """
        logger.debug(
            "File '%s' : header status %s, header comparison status: %s",
            ctx.path,
            ctx.status.header.value,
            ctx.status.comparison.value,
        )

        # If nothing changed, ensure no diff is attached
        if ctx.status.comparison == ComparisonStatus.UNCHANGED:
            ctx.status.patch = PatchStatus.SKIPPED
            ctx.views.diff = DiffView(text=None)
            return

        # ctx.status.comparison == ComparisonStatus.CHANGED:

        # Materialize lines from views once for diffing
        current_lines: list[str] = ctx.materialize_image_lines()
        updated_lines: list[str] | None = None
        updated_view: UpdatedView | None = ctx.views.updated
        if updated_view and updated_view.lines is not None:
            updated_lines = ctx.materialize_updated_lines()

        # We only generate a diff when we have an updated image; otherwise skip.
        if updated_lines is None:
            logger.debug(
                "Patch skipped for %s: comparison=%s but no updated image present",
                ctx.path,
                ctx.status.comparison.value,
            )
            ctx.views.diff = DiffView(text=None)
            ctx.status.patch = PatchStatus.SKIPPED
            return

        display_path: str = get_display_path(ctx)

        fromfile: str = f"{display_path} (current)"
        tofile: str = f"{display_path} (updated)"
        fromfiledate: str = format_gnu_diff_timestamp(dt=ctx.timestamp)
        tofiledate: str = format_gnu_diff_timestamp(dt=ctx.run_options.started_at)

        patch_lines: list[str] = list(
            difflib.unified_diff(
                current_lines,
                updated_lines,
                fromfile=fromfile,
                tofile=tofile,
                fromfiledate=fromfiledate,
                n=3,
                lineterm=ctx.newline_style,
                tofiledate=tofiledate,
            )
        )

        # Transitional shadow-diff validation for GitHub issue #167.
        #
        # `difflib.unified_diff()` remains the production source of truth in this
        # PR so the public diff contract stays unchanged. When the planner or
        # stripper records exactly one structured edit, we also render the new
        # structured diff and compare it with the difflib result. This intentionally
        # duplicates diff work for now: the goal is to prove parity across the full
        # test suite before a later PR can make the structured renderer the primary
        # backend for single-splice edits.
        #
        # A mismatch is treated as a hard failure during this transitional phase.
        # Silent fallback would hide cases where EditView metadata or structured
        # rendering diverges from the existing output contract.
        edit_view: EditView | None = ctx.views.edit
        if edit_view is not None and len(edit_view.edits) == 1:
            structured_patch_lines: list[str] | None = render_structured_unified_diff(
                original_lines=current_lines,
                edit=edit_view.edits[0],
                fromfile=fromfile,
                tofile=tofile,
                fromfiledate=fromfiledate,
                tofiledate=tofiledate,
                lineterm=ctx.newline_style,
                context=3,
            )
            if structured_patch_lines is not None and structured_patch_lines != patch_lines:
                logger.debug(
                    "structured diff shadow mismatch for %s: structured=%r difflib=%r",
                    ctx.path,
                    structured_patch_lines,
                    patch_lines,
                )
                # Keep this as a temporary assertion until the structured renderer
                # becomes the primary single-edit backend or this validation phase is
                # explicitly retired.
                raise RuntimeError(
                    f"structured diff shadow mismatch for {ctx.path}: "
                    f"structured={structured_patch_lines!r} difflib={patch_lines!r}"
                )
        if len(patch_lines) == 0:
            ctx.status.comparison = ComparisonStatus.UNCHANGED
            ctx.status.patch = PatchStatus.SKIPPED
            ctx.views.diff = DiffView(text=None)
            logger.debug("File header unchanged: %s", ctx.path)
            return

        if logger.isEnabledFor(logging.INFO):
            logger.info(
                "Patch (rendered):\n%s",
                format_patch_plain(
                    patch=patch_lines,
                ),
            )

        # Join exactly as produced by difflib. Do not introduce CRLF conversions.
        ctx.views.diff = DiffView(text="".join(patch_lines))
        if not ctx.views.diff or not ctx.views.diff.text:
            logger.error("ComparisonStatus == CHANGED but no diff generated: PatchStatus == FAILED")
            ctx.status.patch = PatchStatus.FAILED
        else:
            ctx.status.patch = PatchStatus.GENERATED

        return

    def hint(self, ctx: ProcessingContext) -> None:
        """Attach diff hints (non-binding).

        Args:
            ctx: The processing context.
        """
        apply: bool = ctx.run_options.apply_changes is True
        st: PatchStatus = ctx.status.patch

        # May proceed to next step (always):
        if st == PatchStatus.GENERATED:
            ctx.hint(
                axis=Axis.PATCH,
                code=KnownCode.PATCH_GENERATED,
                cluster=Cluster.CHANGED if apply else Cluster.WOULD_CHANGE,
                message="patch generated",
            )
        elif st == PatchStatus.SKIPPED:
            ctx.hint(
                axis=Axis.PATCH,
                code=KnownCode.PATCH_SKIPPED,
                cluster=Cluster.UNCHANGED,
                message="no patch needed (unchanged)",
            )
        # Stop processing:
        elif st == PatchStatus.FAILED:
            ctx.hint(
                axis=Axis.PATCH,
                code=KnownCode.PATCH_FAILED,
                cluster=Cluster.ERROR,
                message="change detected but patch generation failed",
                terminal=True,
            )
        elif st == PatchStatus.PENDING:
            # patcher did not complete
            ctx.request_halt(reason=f"{self.__class__.__name__} did not set state.", at_step=self)
