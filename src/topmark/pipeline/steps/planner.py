# topmark:header:start
#
#   project      : TopMark
#   file         : planner.py
#   file_relpath : src/topmark/pipeline/steps/planner.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Plan step for inserting, replacing, or removing the TopMark header (view-based).

This step consumes views produced by earlier phases and emits an updated
file image via ``ctx.views.updated``. It respects comparer outcomes and strip
fast‑paths and never performs I/O.

Inputs:
  * ``ctx.views.header`` ([`HeaderView`][topmark.pipeline.views.HeaderView]) –
    existing header (range/lines/block).
  * ``ctx.views.build`` ([`BuilderView`][topmark.pipeline.views.BuilderView]) –
    field dictionaries (not used directly).
  * ``ctx.views.render`` ([`RenderView`][topmark.pipeline.views.RenderView]) –
    expected header text to write.
  * ``ctx.views.image`` ([`FileImageView`][topmark.pipeline.views.FileImageView]) –
    original file image.

Outputs:
  * ``ctx.views.updated`` ([`UpdatedView`][topmark.pipeline.views.UpdatedView]) –
    updated file image (sequence/iterable).
  * ``ctx.status.write`` – write outcome (SKIPPED/REPLACED/INSERTED/REMOVED/PREVIEWED/FAILED).

Behavior:
  * **Strip fast‑path**: if ``status.strip == READY``, keep the precomputed image in
    ``ctx.views.updated``, reattach BOM if needed, mark write=REMOVED (or PREVIEWED).
  * **Already up‑to‑date**: if ``status.comparison == UNCHANGED``, set write=SKIPPED and
    mirror the original image into ``ctx.views.updated``.
  * **Replace**: if a header range is known, splice rendered header lines over that range.
  * **Insert (text‑based)**: prefer character‑offset insertion when supported.
  * **Insert (line‑based)**: fallback using ``compute_insertion_anchor`` plus
    optional whitespace fixes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.config.logging import get_logger
from topmark.filetypes.base import InsertCapability
from topmark.pipeline.adapters import PreInsertViewAdapter
from topmark.pipeline.context.policy import (
    allow_content_reflow_by_policy,
    allow_empty_by_policy,
)
from topmark.pipeline.hints import Axis, Cluster, KnownCode
from topmark.pipeline.processors.base import NO_LINE_ANCHOR
from topmark.pipeline.status import (
    ComparisonStatus,
    ContentStatus,
    HeaderStatus,
    PlanStatus,
    RenderStatus,
    StripStatus,
)
from topmark.pipeline.steps.base import BaseStep
from topmark.pipeline.views import HeaderView, RenderView, UpdatedView

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from topmark.config.logging import TopmarkLogger
    from topmark.filetypes.base import FileType, InsertChecker, InsertCheckResult
    from topmark.pipeline.context.model import ProcessingContext

logger: TopmarkLogger = get_logger(__name__)


def _drop_trailing_blank_if_header_at_eof(
    lines: list[str],
    insert_index: int,
    header_len: int,
) -> list[str]:
    """If the header occupies the tail of the file and the last line is blank, drop it.

    This avoids creating an extra blank *after* the header when there is no
    following body content. It preserves the policy of ensuring a blank line
    before body text, while keeping insert→strip→insert idempotent for empty bodies.

    Args:
        lines (list[str]): The file content as a list of lines (each with its own newline).
        insert_index (int): The line index where the header was inserted.
        header_len (int): The number of lines in the inserted header.

    Returns:
        list[str]: The (possibly) modified list of lines. Never ``None``.
    """
    if not lines:
        return lines
    tail_start: int = insert_index + header_len
    if tail_start >= len(lines):
        # Header runs to EOF: drop any number of trailing blank lines.
        i: int = len(lines) - 1
        while i >= 0 and lines[i].strip() == "":
            i -= 1
        return lines[: i + 1]
    return lines


def _prepend_bom_to_lines_if_needed(
    lines: list[str],
    ctx: ProcessingContext,
) -> list[str]:
    """Re-prepend a UTF-8 BOM to the first line when appropriate.

    The reader strips a leading BOM ("\ufeff") from the in-memory image and records
    that fact in ``ctx.leading_bom``. Before returning an updated image, the updater
    re-attaches the BOM **unless** doing so would break a POSIX shebang.

    Behavior:
        * If ``ctx.leading_bom`` is False, return ``lines`` unchanged.
        * If a shebang is present (``ctx.has_shebang`` is True), do **not** prepend a BOM;
          append a diagnostic explaining why and return ``lines`` unchanged.
        * Otherwise, prepend a BOM to the first line if it is not already present.

    Args:
        lines (list[str]): The updated file content as a list of lines (each with its own newline).
        ctx (ProcessingContext): The pipeline processing context
            (provides ``leading_bom`` and ``has_shebang``).

    Returns:
        list[str]: The (possibly) modified list of lines. Never ``None``.
    """
    if not lines:
        return lines
    if not ctx.leading_bom:
        # Return unmodified lines (no BOM to insert)
        return lines

    # leading_bom is True
    if ctx.has_shebang:
        # Do not re-add the BOM which was stripped in reader.read(); a valid shebang
        # must start at byte 0 on POSIX systems.
        ctx.error(
            "UTF-8 BOM appears before the shebang; POSIX requires '#!' at byte 0. "
            "TopMark will not modify this file by default. Consider removing the BOM "
            "or using a future '--fix-bom' option to resolve this conflict."
        )
        return lines

    # Re-attach the stripped BOM
    first: str = lines[0]
    if not first.startswith("\ufeff"):
        lines = lines[:]  # shallow copy to avoid mutating caller’s list
        lines[0] = "\ufeff" + first
    return lines


class PlannerStep(BaseStep):
    """Synthesize an updated image from compare/strip results (no I/O).

    Consumes either a prepared strip image (fast path) or the rendered header
    text to construct a new file image in memory. This step **does not** perform
    any writes; it only sets the intended update/write statuses and populates
    ``ctx.views.updated`` for downstream patch/apply steps.

    Sets:
        PlanStatus: {PENDING, PREVIEWED, INSERTED, REPLACED, REMOVED, SKIPPED, FAILED}

    Notes:
        The writer performs the actual I/O. Policies (e.g., add-only/update-only)
        are respected here when deciding the intended action.
    """

    def __init__(self) -> None:
        super().__init__(
            name=self.__class__.__name__,
            primary_axis=Axis.PLAN,
            axes_written=(Axis.PLAN,),
        )

    def may_proceed(self, ctx: ProcessingContext) -> bool:
        """Return True if the planner can compute an updated image.

        Conditions:
            * Resolve succeeded (``resolve == RESOLVED``); and
            * Either:
                - **Strip fast-path**: ``status.strip == READY``; or
                - **Normal path**: content is OK **or** empty+policy is allowed,
                  and we have something to apply (``comparison == CHANGED`` **or** a
                  rendered header is present via ``RenderView.lines``).

        Args:
            ctx (ProcessingContext): The processing context.

        Returns:
            bool: ``True`` if the updater can proceed; otherwise ``False``.
        """
        if ctx.is_halted:
            outcome: bool = False
        else:
            outcome = (
                # Strip fast-path
                ctx.status.strip == StripStatus.READY
                # Normal update: content OK or empty+policy allowed
                or ctx.status.render == RenderStatus.RENDERED
                or ctx.status.comparison == ComparisonStatus.CHANGED
            )
        logger.info("may_proceed: %s", outcome)
        return outcome

    def run(self, ctx: ProcessingContext) -> None:
        """Plan insert/replace/remove of the TopMark header for the current file (view-based).

        Behavior by case:
        * **Strip fast-path**: When ``status.strip == READY``, keep the precomputed
            ``ctx.views.updated.lines``, reattach a BOM if the reader saw one, and mark
            ``write=REMOVED`` (or ``PREVIEWED`` when not applying).
        * **Already up-to-date**: When ``status.comparison == UNCHANGED``, do nothing,
            set ``write=SKIPPED``, and mirror the original image into ``ctx.views.updated``.
        * **Replace**: If a header range is known (``ctx.views.header.range``), splice
            the rendered header lines (``ctx.views.render.lines``) over that range; reattach BOM
            if needed; if the result equals the original, set ``write=SKIPPED``; otherwise
            ``write=REPLACED`` (or ``PREVIEWED``).
        * **Insert (text-based)**: If the processor provides a character offset, insert
            the rendered header text there (after optional ``prepare_header_for_insertion_text``),
            reattach BOM if needed; if identical to original, ``SKIPPED``; else ``INSERTED``.
        * **Insert (line-based fallback)**: Use ``compute_insertion_anchor`` (line index),
            optionally adjust whitespace via ``prepare_header_for_insertion``, reattach BOM
            if needed; set ``INSERTED`` unless the result is identical, in which case ``SKIPPED``.

        Notes:
        This function performs no I/O; it only populates ``ctx.views.updated`` and
        ``ctx.status.write`` for downstream patch/apply steps.
        """
        logger.debug("ctx: %s", ctx)
        logger.debug("ctx.config.apply_changes = %s", ctx.config.apply_changes)

        apply: bool = False if ctx.config.apply_changes is None else ctx.config.apply_changes

        # Materialize original image once (list[str]) for splice operations.
        original_lines: list[str] = list(ctx.iter_image_lines())

        if ctx.status.content != ContentStatus.OK and not allow_empty_by_policy(ctx):
            logger.debug("planner: skipping (content status=%s)", ctx.status.content.value)
            ctx.status.plan = PlanStatus.SKIPPED
            reason: str = f"Could not update file (status: {ctx.status.content.value})."
            ctx.info(reason)
            ctx.request_halt(reason=reason, at_step=self)
            return

        # TODO: enable updating based on future allow_XXX_by_policy() policy:
        if ctx.status.header in {
            HeaderStatus.MALFORMED_ALL_FIELDS,
            HeaderStatus.MALFORMED_SOME_FIELDS,
        }:
            ctx.status.plan = PlanStatus.SKIPPED
            ctx.views.updated = UpdatedView(lines=original_lines)
            reason = "Existing header has malformed fields; TopMark will not update it."
            ctx.warn(reason)
            ctx.request_halt(reason=reason, at_step=self)
            return

        logger.debug("ctx: %s", ctx.to_dict())

        # --- strip fast-path (must run before any add/replace logic) ---
        if ctx.status.strip == StripStatus.READY:
            # Previous step computed updated_file_lines for a removal.
            updated_view: UpdatedView | None = ctx.views.updated
            if not updated_view or updated_view.lines is None:
                # TODO: check whether this can be the case when the file to be stripped
                # would become empty after stripping!
                logger.error(
                    "Stripper might have omitted to set ctx.views.updated, "
                    "or the resulting updated file might become empty after stripping. "
                    "ctx.views.updated is %s, ctx.views.updated.file_lines is %s",
                    "defined" if updated_view else "not set",
                    "defined" if updated_view and updated_view.lines else "not set",
                )
                ctx.status.plan = PlanStatus.FAILED  # TODO FIXME
                reason = "No updated file lines available for stripping."
                ctx.request_halt(reason=reason, at_step=self)
                return

            # ✅ Preserve empty list as a valid updated image
            seq: Sequence[str] | Iterable[str] = updated_view.lines
            stripped_lines: list[str] = seq if isinstance(seq, list) else list(seq)

            # Re-attach BOM only if needed (no-op for empty)
            stripped_lines = _prepend_bom_to_lines_if_needed(stripped_lines, ctx)

            ctx.views.updated = UpdatedView(lines=stripped_lines)
            ctx.status.plan = PlanStatus.REMOVED if apply else PlanStatus.PREVIEWED
            return

        # If the comparer determined the file is already compliant, do nothing.
        if ctx.status.comparison == ComparisonStatus.UNCHANGED:
            ctx.status.plan = PlanStatus.SKIPPED
            # Preserve the original image as the "updated" content for downstream steps.
            ctx.views.updated = UpdatedView(lines=original_lines)
            logger.trace("Updater: no-op (comparison=UNCHANGED) for %s", ctx.path)
            return

        # Non-strip processing
        render_view: RenderView | None = ctx.views.render
        if render_view is None or render_view.lines is None:
            ctx.status.plan = PlanStatus.FAILED
            reason = "Cannot update header: no rendered header available"
            ctx.error(reason)
            ctx.request_halt(reason=reason, at_step=self)
            return

        rendered_expected_header_lines: list[str] = list(render_view.lines)

        if ctx.header_processor is None:
            ctx.status.plan = PlanStatus.FAILED
            reason = "Cannot update header: no header processor assigned"
            ctx.error(reason)
            ctx.request_halt(reason=reason, at_step=self)
            return

        ft: FileType | None = ctx.file_type
        checker: InsertChecker | None = ft.pre_insert_checker if ft else None

        # --- Pre-insert capability check (authoritative) --------------------------
        # Only evaluate here if the advisory checker did not run (UNEVALUATED).
        if checker is not None:
            if ctx.pre_insert_capability == InsertCapability.UNEVALUATED:
                try:
                    view = PreInsertViewAdapter(ctx)
                    result: InsertCheckResult = checker(view) or {}
                except Exception as exc:
                    logger.exception(
                        "pre-insert checker failed for %s: %s", getattr(ft, "name", ft), exc
                    )
                    from topmark.cli_shared.utils import format_callable_pretty

                    result = {
                        "capability": InsertCapability.SKIP_OTHER,
                        "reason": f"checker error: {format_callable_pretty(checker)}, {exc}",
                        "origin": __name__,
                    }

                # Persist the authoritative view for downstream bucketing/rendering
                cap: InsertCapability = result.get("capability", InsertCapability.OK)
                ctx.pre_insert_capability = cap
                ctx.pre_insert_reason = result.get("reason", ctx.pre_insert_reason)
                ctx.pre_insert_origin = result.get("origin", __name__)

                if cap != InsertCapability.OK:
                    pre_insert_reason = ctx.pre_insert_reason or "pre-insert checker skipped update"
                    origin = ctx.pre_insert_origin or __name__
                    logger.debug(
                        "pre-insert: %s – %s", getattr(cap, "value", cap), pre_insert_reason
                    )
                    # Preserve original image; mark as skipped
                    ctx.views.updated = UpdatedView(lines=original_lines)
                    ctx.status.plan = PlanStatus.SKIPPED
                    reason = f"{pre_insert_reason} (origin: {origin})"
                    ctx.warn(reason)
                    ctx.request_halt(reason=reason, at_step=self)
                    return

            if ctx.pre_insert_capability == InsertCapability.SKIP_IDEMPOTENCE_RISK:
                # TODO - align with reader.ReaderStep.run()
                if ctx.status.content == ContentStatus.OK and allow_content_reflow_by_policy(ctx):
                    pass
                else:
                    # Advisory-only pre-insert probe already ran in reader step.
                    # Here we enforce the gate: if the advisory is not OK, skip updating.
                    pre_insert_reason: str = (
                        ctx.pre_insert_reason or "pre-insert check refused insertion"
                    )
                    origin: str = ctx.pre_insert_origin or __name__
                    logger.debug(
                        "pre-insert (advisory): %s – %s",
                        getattr(ctx.pre_insert_capability, "value", ctx.pre_insert_capability),
                        pre_insert_reason,
                    )
                    ctx.views.updated = UpdatedView(lines=original_lines)
                    ctx.status.plan = PlanStatus.SKIPPED
                    reason = f"{pre_insert_reason} (origin: {origin})"
                    ctx.warn(reason)
                    ctx.request_halt(reason=reason, at_step=self)
                    return

            # --- Pre-insert capability gate (authoritative) ---------------------------
            elif ctx.pre_insert_capability != InsertCapability.OK:
                # Advisory-only pre-insert probe already ran in reader step.
                # Here we enforce the gate: if the advisory is not OK, skip updating.
                pre_insert_reason: str = (
                    ctx.pre_insert_reason or "pre-insert check refused insertion"
                )
                origin: str = ctx.pre_insert_origin or __name__
                logger.debug(
                    "pre-insert (advisory): %s – %s",
                    getattr(ctx.pre_insert_capability, "value", ctx.pre_insert_capability),
                    pre_insert_reason,
                )
                ctx.views.updated = UpdatedView(lines=original_lines)
                ctx.status.plan = PlanStatus.SKIPPED
                reason = f"{pre_insert_reason} (origin: {origin})"
                ctx.warn(reason)
                ctx.request_halt(reason=reason, at_step=self)
                return

        # --- Replace path (view-based) ---
        header_view: HeaderView | None = ctx.views.header
        existing_range: tuple[int, int] | None = header_view.range if header_view else None
        if existing_range is not None:
            # Replace existing header: remove old header lines and insert new header in place
            start: int
            end: int
            start, end = existing_range
            new_lines: list[str] = (
                original_lines[:start] + rendered_expected_header_lines + original_lines[end + 1 :]
            )
            # Prepend BOM if needed
            new_lines = _prepend_bom_to_lines_if_needed(new_lines, ctx)
            # If replacement is identical to the original, treat as a no-op.
            if new_lines == original_lines:
                ctx.status.plan = PlanStatus.SKIPPED
                ctx.views.updated = UpdatedView(lines=original_lines)
                logger.trace("Updater: replacement yields no changes for %s", ctx.path)
                return
            ctx.status.plan = PlanStatus.REPLACED if apply else PlanStatus.PREVIEWED
            ctx.views.updated = UpdatedView(lines=new_lines)
            logger.trace("Updated file (replace):\n%s", "".join(new_lines))
            return

        # --- Insert: text-based first ---
        try:
            logger.debug("upd.path: try=text; file=%s", ctx.path)
            original_text: str = "".join(original_lines)
            char_offset: int | None = None
            if hasattr(ctx.header_processor, "get_header_insertion_char_offset"):
                char_offset = ctx.header_processor.get_header_insertion_char_offset(original_text)
            logger.debug("upd.text: offset=%s; head[:40]=%r", char_offset, original_text[:40])

            if char_offset is not None:
                header_text: str = "".join(rendered_expected_header_lines)
                if hasattr(ctx.header_processor, "prepare_header_for_insertion_text"):
                    try:
                        header_text = ctx.header_processor.prepare_header_for_insertion_text(
                            original_text=original_text,
                            insert_offset=char_offset,
                            rendered_header_text=header_text,
                            newline_style=ctx.newline_style or "\n",
                        )
                    except Exception as e:
                        logger.warning(
                            "prepare_header_for_insertion_text failed for %s: %s", ctx.path, e
                        )
                logger.debug(
                    "upd.text.pad: insert_offset=%d; header_head[:40]=%r",
                    char_offset,
                    header_text[:40],
                )
                logger.debug(
                    "upd.text.splice: pre_tail[:10]=%r post_head[:10]=%r",
                    original_text[max(0, char_offset - 10) : char_offset],
                    original_text[char_offset : char_offset + 10],
                )
                new_text: str = (
                    original_text[:char_offset] + header_text + original_text[char_offset:]
                )
                # If header text ends at EOF with trailing blank lines, drop them all.
                # The blank-after-header policy should only apply when body text follows.
                while new_text.endswith("\r\n\r\n"):
                    new_text = new_text[:-2]  # drop one CRLF pair
                while new_text.endswith("\n\n") or new_text.endswith("\r\r"):
                    new_text = new_text[:-1]  # drop one LF or CR
                logger.trace("Updater (text): trimmed EOF blanks; len=%d", len(new_text))

                # Prepend BOM if needed
                if getattr(ctx, "leading_bom", False) and not new_text.startswith("\ufeff"):
                    new_text = "\ufeff" + new_text
                if new_text == original_text:
                    ctx.views.updated = UpdatedView(lines=original_lines)
                    # ctx.status.write = WriteStatus.SKIPPED
                    ctx.status.plan = PlanStatus.SKIPPED
                    logger.trace("Updater: text-based insertion yields no changes for %s", ctx.path)
                    return
                ctx.views.updated = UpdatedView(lines=new_text.splitlines(keepends=True))
                ctx.status.plan = PlanStatus.INSERTED if apply else PlanStatus.PREVIEWED
                return
        except Exception as e:
            logger.warning("text-based insertion failed for %s: %s", ctx.path, e)

        # --- Insert: line-based fallback ---
        insert_index: int = ctx.header_processor.compute_insertion_anchor(original_lines)
        if insert_index == NO_LINE_ANCHOR:
            ctx.status.plan = PlanStatus.FAILED
            reason = f"No line-based insertion anchor for file: {ctx.path}"
            ctx.error(reason)
            ctx.request_halt(reason=reason, at_step=self)
            return

        # defensive clamp
        if insert_index < 0:
            insert_index = 0
        elif insert_index > len(original_lines):
            insert_index = len(original_lines)

        # optional whitespace adjustments
        try:
            header_lines: list[str] = ctx.header_processor.prepare_header_for_insertion(
                original_lines=original_lines,
                insert_index=insert_index,
                rendered_header_lines=rendered_expected_header_lines,
                newline_style=ctx.newline_style or "\n",
            )
        except Exception as e:
            logger.warning("prepare_header_for_insertion failed for %s: %s", ctx.path, e)
            header_lines = rendered_expected_header_lines

        # Splice header; if inserting at BOF and the first original line is a BOM-only blank,
        # consume it so we don't leave a dangling BOM+blank after the header.
        body_start: int = insert_index
        if insert_index == 0 and original_lines:
            first: str = original_lines[0]
            # Consume only a BOM-bearing blank at BOF (e.g., "\ufeff" or "\ufeff\n"),
            # but preserve a user-authored plain blank line.
            is_bom_blank: bool = (
                first.startswith("\ufeff") and first.replace("\ufeff", "").strip() == ""
            )
            if is_bom_blank:
                body_start = 1
                logger.trace(
                    "Updater (line): consuming BOM-only/blank line at BOF after header insertion"
                )

        new_lines = original_lines[:insert_index] + header_lines + original_lines[body_start:]

        # If header occupies the tail and last line is blank, drop all trailing blanks.
        new_lines = _drop_trailing_blank_if_header_at_eof(
            new_lines, insert_index, len(header_lines)
        )
        # Prepend BOM if needed
        new_lines = _prepend_bom_to_lines_if_needed(new_lines, ctx)
        if new_lines == original_lines:
            ctx.views.updated = UpdatedView(lines=original_lines)
            ctx.status.plan = PlanStatus.SKIPPED
            logger.trace("Updater: line-based insertion yields no changes for %s", ctx.path)
            return
        ctx.views.updated = UpdatedView(lines=new_lines)
        ctx.status.plan = PlanStatus.INSERTED if apply else PlanStatus.PREVIEWED
        logger.trace("Updated file (line-based):\n%s", "".join(new_lines))
        return

    def hint(self, ctx: ProcessingContext) -> None:
        """Attach update hints (non-binding).

        Args:
            ctx (ProcessingContext): The processing context.
        """
        apply: bool = ctx.config.apply_changes is True
        ft: FileType | None = ctx.file_type
        checker: InsertChecker | None = ft.pre_insert_checker if ft else None
        st: PlanStatus = ctx.status.plan

        # May proceed to next step (always):
        if st == PlanStatus.INSERTED:
            ctx.hint(
                axis=Axis.PLAN,
                code=KnownCode.PLAN_INSERT,
                cluster=Cluster.CHANGED if apply else Cluster.WOULD_CHANGE,
                message="header will be inserted" if apply else "header would be inserted",
            )
        elif st == PlanStatus.REPLACED:
            ctx.hint(
                axis=Axis.PLAN,
                code=KnownCode.PLAN_UPDATE,
                cluster=Cluster.CHANGED if apply else Cluster.WOULD_CHANGE,
                message="header will be replaced" if apply else "header would be replaced",
            )
        elif st == PlanStatus.REMOVED:
            ctx.hint(
                axis=Axis.PLAN,
                code=KnownCode.PLAN_REMOVE,
                cluster=Cluster.CHANGED if apply else Cluster.WOULD_CHANGE,
                message="header will be removed" if apply else "header would be removed",
            )
        elif st == PlanStatus.SKIPPED:
            if ctx.status.content != ContentStatus.OK and not allow_empty_by_policy(ctx):
                msg: str = f"Could not update file (status: {ctx.status.content.value})."
            elif ctx.status.header in {
                HeaderStatus.MALFORMED_ALL_FIELDS,
                HeaderStatus.MALFORMED_SOME_FIELDS,
            }:
                # TODO: enable updating based on future policy:
                msg = "Existing header has malformed fields; TopMark will not update it."
            elif checker is not None and ctx.pre_insert_capability != InsertCapability.OK:
                pre_insert_reason: str = (
                    ctx.pre_insert_reason or "pre-insert check refused insertion"
                )
                origin: str = ctx.pre_insert_origin or __name__
                msg = f"{pre_insert_reason} (origin: {origin})"
            else:
                msg = "no update needed"
            ctx.hint(
                axis=Axis.PLAN,
                code=KnownCode.PLAN_SKIP,
                cluster=Cluster.SKIPPED,
                message=msg,
                terminal=True,
            )
        # Stop processing:
        elif st == PlanStatus.PREVIEWED:
            # TODO: stop processing of proceed to next step?
            ctx.hint(
                axis=Axis.PLAN,
                code="previewed",
                # code=KnownCode.,
                # cluster=Cluster,
                message="previewed changes",
                terminal=True,
            )
        elif st == PlanStatus.FAILED:
            ctx.hint(
                axis=Axis.PLAN,
                code=KnownCode.PLAN_FAILED,
                cluster=Cluster.SKIPPED,
                message="failed to compute update",
                terminal=True,
            )
        elif st == PlanStatus.PENDING:
            # updater did not complete
            ctx.request_halt(reason=f"{self.__class__.__name__} did not set state.", at_step=self)
