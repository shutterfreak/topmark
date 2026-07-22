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

This step uses the original file image (``ctx.views.image``) plus either one
structured edit or the pipeline's updated image (``ctx.views.updated``) to produce
a unified diff suitable for CLI/CI consumption. It mutates only the processing
context and performs no I/O.

Inputs:
  * ``ctx.views.image`` - [`FileImageView`][topmark.pipeline.views.FileImageView] carrying the
    original file image view.
  * ``ctx.views.updated`` - optional [`UpdatedView`][topmark.pipeline.views.UpdatedView]
    carrying the updated file image.
  * ``ctx.views.edit`` - optional [`EditView`][topmark.pipeline.views.EditView]
    carrying structured edit metadata.

Outputs:
  * ``ctx.views.diff`` - [`DiffView`][topmark.pipeline.views.DiffView] carrying the
    unified diff text (or ``None``). Diff file labels are human-facing display labels,
    not machine-readable path serialization fields.
"""

from __future__ import annotations

import difflib
import logging
from collections.abc import Sequence
from typing import TYPE_CHECKING

from topmark.core.logging import get_logger
from topmark.pipeline.context.policy import source_lines_with_remediated_bom
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
    from topmark.pipeline.views import PlannedEdit


logger: TopmarkLogger = get_logger(__name__)


def _apply_single_edit(
    *,
    original_lines: Sequence[str],
    edit: PlannedEdit,
) -> list[str] | None:
    """Apply one planned edit to original lines for optional validation.

    Args:
        original_lines: Original file image lines.
        edit: Planned edit to apply.

    Returns:
        list[str] | None: Updated lines when the edit span is valid, otherwise
        ``None``.
    """
    if edit.old_start < 0 or edit.old_end < edit.old_start or edit.old_end > len(original_lines):
        return None

    return [
        *original_lines[: edit.old_start],
        *edit.new_lines,
        *original_lines[edit.old_end :],
    ]


def _render_difflib_unified_diff(
    *,
    current_lines: Sequence[str],
    updated_lines: Sequence[str],
    fromfile: str,
    tofile: str,
    fromfiledate: str,
    tofiledate: str,
    lineterm: str,
) -> list[str]:
    """Render the generic difflib unified diff fallback.

    Args:
        current_lines: Original file image lines.
        updated_lines: Updated file image lines.
        fromfile: Diff label for the original file.
        tofile: Diff label for the updated file.
        fromfiledate: Timestamp label for the original file.
        tofiledate: Timestamp label for the updated file.
        lineterm: Diff control-line terminator.

    Returns:
        list[str]: Unified diff lines.
    """
    return list(
        difflib.unified_diff(
            current_lines,
            updated_lines,
            fromfile=fromfile,
            tofile=tofile,
            fromfiledate=fromfiledate,
            tofiledate=tofiledate,
            n=3,
            lineterm=lineterm,
        )
    )


def _render_structured_patch_lines(
    *,
    current_lines: Sequence[str],
    edit_view: EditView | None,
    expected_updated_lines: Sequence[str] | None,
    fromfile: str,
    tofile: str,
    fromfiledate: str,
    tofiledate: str,
    lineterm: str,
) -> list[str] | None:
    """Render patch lines directly from valid single-edit metadata.

    Args:
        current_lines: Original file image lines.
        edit_view: Structured planned edits, when available.
        expected_updated_lines: Optional materialized updated image to validate
            caller-provided metadata without additional materialization.
        fromfile: Diff label for the original file.
        tofile: Diff label for the updated file.
        fromfiledate: Timestamp label for the original file.
        tofiledate: Timestamp label for the updated file.
        lineterm: Diff control-line terminator.

    Returns:
        list[str] | None: Structured unified diff lines, or ``None`` when the
        metadata is absent, invalid, or unsupported by the structured renderer.
    """
    if edit_view is None or len(edit_view.edits) != 1:
        return None

    edit: PlannedEdit = edit_view.edits[0]
    applied_lines: list[str] | None = _apply_single_edit(
        original_lines=current_lines,
        edit=edit,
    )
    if applied_lines is None:
        return None

    if expected_updated_lines is not None and applied_lines != list(expected_updated_lines):
        logger.debug("structured diff metadata did not match updated image; falling back")
        return None

    return render_structured_unified_diff(
        original_lines=current_lines,
        edit=edit,
        fromfile=fromfile,
        tofile=tofile,
        fromfiledate=fromfiledate,
        tofiledate=tofiledate,
        lineterm=lineterm,
        context=3,
    )


class PatcherStep(BaseStep):
    """Produce a unified diff between the original image and planned content.

    Generates a unified diff (CLI/CI friendly) when comparison indicates a
    change and either one usable structured edit or an updated image is present.
    Normalizes `ComparisonStatus` to `UNCHANGED` if the computed diff is empty.

    This step does not print; the CLI or API decides how to display diffs.

    Axes written:
      - comparison  (normalization only; no new comparisons are computed here)
      - patch

    Sets/normalizes:
      - PatchStatus: {PENDING, GENERATED, SKIPPED, FAILED}
      - PATCH_* hint codes for patch/patcher semantics:
          PATCH_GENERATED: patch generated and available
          PATCH_SKIPPED: no patch needed (unchanged)
          PATCH_FAILED: change detected but patch generation failed
      - ComparisonStatus: {CHANGED, UNCHANGED}
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

    def may_proceed(
        self,
        ctx: ProcessingContext,
    ) -> bool:
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

    def run(
        self,
        ctx: ProcessingContext,
    ) -> None:
        """Generate and attach a unified diff to the processing context (view-based).

        The step runs only after comparison. If the comparison status is
        ``UNCHANGED``, the diff is omitted. A changed comparison requires either
        one usable structured edit or an updated image; otherwise patch generation
        fails.

        Unified diff file labels use the shared human-facing display path policy,
        including the logical ``--stdin-filename`` in STDIN content mode.

        Args:
            ctx: The processing context holding original/updated images
                and statuses.

        Mutations:
            ProcessingContext: The same context with ``ctx.views.diff`` set when a change is
                detected, and with comparison status normalized when applicable.

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

        # Materialize original file lines from views once for diffing
        current_lines: list[str] = source_lines_with_remediated_bom(
            ctx.materialize_image_lines(),
            ctx,
        )

        display_path: str = get_display_path(ctx)

        fromfile: str = f"{display_path} (current)"
        tofile: str = f"{display_path} (updated)"
        fromfiledate: str = format_gnu_diff_timestamp(dt=ctx.timestamp)
        tofiledate: str = format_gnu_diff_timestamp(dt=ctx.run_options.started_at)

        updated_view: UpdatedView | None = ctx.views.updated
        expected_updated_lines: Sequence[str] | None = None
        if (
            updated_view is not None
            and updated_view.lines is not None
            and isinstance(updated_view.lines, Sequence)
        ):
            expected_updated_lines = updated_view.lines

        patch_lines: list[str] | None = _render_structured_patch_lines(
            current_lines=current_lines,
            edit_view=ctx.views.edit,
            expected_updated_lines=expected_updated_lines,
            fromfile=fromfile,
            tofile=tofile,
            fromfiledate=fromfiledate,
            tofiledate=tofiledate,
            lineterm=ctx.newline_style,
        )

        if patch_lines is None:
            updated_lines: list[str] | None = None
            if updated_view and updated_view.lines is not None:
                updated_lines = ctx.materialize_updated_lines()

            # We only generate a fallback diff when we have an updated image.
            if updated_lines is None:
                reason: str = (
                    "Cannot generate patch: comparison detected changes but no updated image "
                    "or usable structured edit is available."
                )
                ctx.views.diff = DiffView(text=None)
                ctx.status.patch = PatchStatus.FAILED
                ctx.diagnostics.add_error(reason)
                return

            #  Render the generic difflib unified diff fallback.
            patch_lines = _render_difflib_unified_diff(
                current_lines=current_lines,
                updated_lines=updated_lines,
                fromfile=fromfile,
                tofile=tofile,
                fromfiledate=fromfiledate,
                tofiledate=tofiledate,
                lineterm=ctx.newline_style,
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

        # Join exactly as produced by the selected backend. Do not introduce CRLF conversions.
        patch_text: str = "".join(patch_lines)
        if not patch_text:
            ctx.views.diff = DiffView(text=None)
            ctx.status.patch = PatchStatus.FAILED
            ctx.diagnostics.add_error(
                "Patch generation produced empty diff text for changed content."
            )
        else:
            ctx.views.diff = DiffView(text=patch_text)
            ctx.status.patch = PatchStatus.GENERATED

        return

    def hint(
        self,
        ctx: ProcessingContext,
    ) -> None:
        """Attach diff hints (non-binding).

        Args:
            ctx: The processing context.

        Raises:
            RuntimeError: If the context contains an unexpected patcher status value.
        """
        apply: bool = ctx.run_options.apply_changes is True
        st: PatchStatus = ctx.status.patch

        match st:
            # May proceed to next step (always):
            case PatchStatus.GENERATED:
                ctx.hint(
                    axis=Axis.PATCH,
                    code=KnownCode.PATCH_GENERATED,
                    cluster=Cluster.CHANGED if apply else Cluster.WOULD_CHANGE,
                    message="patch generated",
                )
            case PatchStatus.SKIPPED:
                ctx.hint(
                    axis=Axis.PATCH,
                    code=KnownCode.PATCH_SKIPPED,
                    cluster=Cluster.UNCHANGED,
                    message="no patch needed (unchanged)",
                )

            # Stop processing:
            case PatchStatus.FAILED:
                ctx.hint(
                    axis=Axis.PATCH,
                    code=KnownCode.PATCH_FAILED,
                    cluster=Cluster.ERROR,
                    message="change detected but patch generation failed",
                    terminal=True,
                )

            # States owned outside this step:
            case PatchStatus.PENDING:  # pragma: no cover - BaseStep owns pending-state handling.
                # BaseStep.__call__() handles PENDING state (step did not complete)
                pass

            case _:  # pragma: no cover - exhaustive enum guard for untyped callers.
                raise RuntimeError(f"Unexpected PatchStatus found: {st!r}")
