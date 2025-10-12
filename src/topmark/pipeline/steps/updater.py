# topmark:header:start
#
#   project      : TopMark
#   file         : updater.py
#   file_relpath : src/topmark/pipeline/steps/updater.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Update step for inserting or replacing the TopMark header (view‑based).

This step consumes views produced by earlier phases and emits an updated
file image via ``ctx.updated``. It respects comparer outcomes and strip
fast‑paths and never performs I/O.

Inputs:
  * ``ctx.header`` (:class:`HeaderView`) – existing header (range/lines/block).
  * ``ctx.build`` (:class:`BuilderView`) – field dictionaries (not used directly).
  * ``ctx.render`` (:class:`RenderView`) – expected header text to write.
  * ``ctx.image`` (:class:`FileImageView`) – original file image.

Outputs:
  * ``ctx.updated`` (:class:`UpdatedView`) – updated file image (sequence/iterable).
  * ``ctx.status.write`` – write outcome (SKIPPED/REPLACED/INSERTED/REMOVED/PREVIEWED/FAILED).

Behavior:
  * **Strip fast‑path**: if ``status.strip == READY``, keep the precomputed image in
    ``ctx.updated``, reattach BOM if needed, mark write=REMOVED (or PREVIEWED).
  * **Already up‑to‑date**: if ``status.comparison == UNCHANGED``, set write=SKIPPED and
    mirror the original image into ``ctx.updated``.
  * **Replace**: if a header range is known, splice rendered header lines over that range.
  * **Insert (text‑based)**: prefer character‑offset insertion when supported.
  * **Insert (line‑based)**: fallback using ``compute_insertion_anchor`` plus
    optional whitespace fixes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterable, Sequence

from topmark.config.logging import TopmarkLogger, get_logger
from topmark.pipeline.adapters import PreInsertViewAdapter
from topmark.pipeline.context import (
    ComparisonStatus,
    ContentStatus,
    HeaderStatus,
    ProcessingContext,
    StripStatus,
    WriteStatus,
    allow_empty_by_policy,
    may_proceed_to_updater,
)
from topmark.pipeline.processors.base import NO_LINE_ANCHOR
from topmark.pipeline.views import UpdatedView

if TYPE_CHECKING:
    from topmark.filetypes.base import FileType, InsertCapability, InsertChecker, InsertCheckResult
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
        ctx.add_error(
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


def update(ctx: ProcessingContext) -> ProcessingContext:
    """Insert or replace the TopMark header for the current file (view-based).

    Behavior by case:
      * **Strip fast-path**: When ``status.strip == READY``, keep the precomputed
        ``ctx.updated.lines``, reattach a BOM if the reader saw one, and mark
        ``write=REMOVED`` (or ``PREVIEWED`` when not applying).
      * **Already up-to-date**: When ``status.comparison == UNCHANGED``, do nothing,
        set ``write=SKIPPED``, and mirror the original image into ``ctx.updated``.
      * **Replace**: If a header range is known (``ctx.header.range``), splice
        the rendered header lines (``ctx.render.lines``) over that range; reattach BOM
        if needed; if the result equals the original, set ``write=SKIPPED``; otherwise
        ``write=REPLACED`` (or ``PREVIEWED``).
      * **Insert (text-based)**: If the processor provides a character offset, insert
        the rendered header text there (after optional ``prepare_header_for_insertion_text``),
        reattach BOM if needed; if identical to original, ``SKIPPED``; else ``INSERTED``.
      * **Insert (line-based fallback)**: Use ``compute_insertion_anchor`` (line index),
        optionally adjust whitespace via ``prepare_header_for_insertion``, reattach BOM if needed;
        set ``INSERTED`` unless the result is identical, in which case ``SKIPPED``.

    Notes:
      This function performs no I/O; it only populates ``ctx.updated`` and
      ``ctx.status.write`` for downstream patch/apply steps.
    """
    logger.debug("ctx: %s", ctx)
    logger.debug("ctx.config.apply_changes = %s", ctx.config.apply_changes)

    apply: bool = False if ctx.config.apply_changes is None else ctx.config.apply_changes

    if not may_proceed_to_updater(ctx):
        logger.info("Updater skipped by may_proceed_to_updater()")
        # Be explicit on refusal: mark as SKIPPED and mirror the current image.
        # (Don't materialize before we need to; if you prefer, move this below after
        # the 'original_lines' materialization and reuse it.)
        try:
            current: list[str] = list(ctx.iter_file_lines())
        except Exception:
            current = []
        ctx.updated = UpdatedView(lines=current)
        ctx.status.write = WriteStatus.SKIPPED
        ctx.add_info("Updater gated: conditions not satisfied for update()")
        return ctx

    # Materialize original image once (list[str]) for splice operations.
    original_lines: list[str] = list(ctx.iter_file_lines())

    if ctx.status.content != ContentStatus.OK and not allow_empty_by_policy(ctx):
        ctx.status.write = WriteStatus.SKIPPED
        ctx.add_info(f"Could not update file (status: {ctx.status.content.value}).")
        logger.debug("Updater: skipping (content status=%s)", ctx.status.content.value)
        return ctx

    if ctx.status.header in {
        HeaderStatus.MALFORMED,
        HeaderStatus.MALFORMED_ALL_FIELDS,
        HeaderStatus.MALFORMED_SOME_FIELDS,
    }:
        ctx.status.write = WriteStatus.SKIPPED
        ctx.updated = UpdatedView(lines=original_lines)
        ctx.add_warning("Existing header is malformed; TopMark will not update it.")
        return ctx

    logger.debug("ctx: %s", ctx.to_dict())

    # --- strip fast-path (must run before any add/replace logic) ---
    if ctx.status.strip == StripStatus.READY:
        # Previous step computed updated_file_lines for a removal.
        if not ctx.updated or ctx.updated.lines is None:
            logger.error(
                "Stripper might have omitted to set ctx.updated, ctx.updated: %s",
                "defined" if ctx.updated else "not set",
            )
            ctx.status.write = WriteStatus.FAILED  # TODO FIXME
            return ctx

        # ✅ Preserve empty list as a valid updated image
        seq: Sequence[str] | Iterable[str] = ctx.updated.lines
        stripped_lines: list[str] = seq if isinstance(seq, list) else list(seq)

        # Re-attach BOM only if needed (no-op for empty)
        stripped_lines = _prepend_bom_to_lines_if_needed(stripped_lines, ctx)

        ctx.updated = UpdatedView(lines=stripped_lines)
        ctx.status.write = WriteStatus.REMOVED if apply else WriteStatus.PREVIEWED
        return ctx

    # If the comparer determined the file is already compliant, do nothing.
    if ctx.status.comparison == ComparisonStatus.UNCHANGED:
        ctx.status.write = WriteStatus.SKIPPED
        # Preserve the original image as the "updated" content for downstream steps.
        ctx.updated = UpdatedView(lines=original_lines)
        logger.trace("Updater: no-op (comparison=UNCHANGED) for %s", ctx.path)
        return ctx

    # Non-strip processing
    if ctx.render is None or ctx.render.lines is None:
        ctx.add_error("Cannot update header: no rendered header available")
        ctx.status.write = WriteStatus.SKIPPED
        return ctx

    rendered_expected_header_lines: list[str] = list(ctx.render.lines)

    if ctx.header_processor is None:
        ctx.add_error("Cannot update header: no header processor assigned")
        ctx.status.write = WriteStatus.SKIPPED
        return ctx

    from topmark.filetypes.base import InsertCapability  # local to avoid cycles

    ft: FileType | None = ctx.file_type
    checker: InsertChecker | None = ft.pre_insert_checker if ft else None

    # --- Pre-insert capability gate (authoritative) ---------------------------
    if checker is not None and ctx.pre_insert_capability != InsertCapability.OK:
        # Advisory-only pre-insert probe already ran in reader step.
        # Here we enforce the gate: if the advisory is not OK, skip updating.
        reason: str = ctx.pre_insert_reason or "pre-insert check refused insertion"
        origin: str = ctx.pre_insert_origin or __name__
        logger.debug(
            "pre-insert (advisory): %s – %s",
            getattr(ctx.pre_insert_capability, "value", ctx.pre_insert_capability),
            reason,
        )
        ctx.updated = UpdatedView(lines=original_lines)
        ctx.status.write = WriteStatus.SKIPPED
        ctx.add_warning(f"{reason} (origin: {origin})")
        return ctx

    # --- Pre-insert capability check (authoritative) --------------------------
    # Only evaluate here if the advisory checker did not run (UNEVALUATED).
    if checker is not None and ctx.pre_insert_capability == InsertCapability.UNEVALUATED:
        try:
            view = PreInsertViewAdapter(ctx)
            result: "InsertCheckResult" = checker(view) or {}
        except Exception as exc:
            logger.exception("pre-insert checker failed for %s: %s", getattr(ft, "name", ft), exc)
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
            reason = ctx.pre_insert_reason or "pre-insert checker skipped update"
            origin = ctx.pre_insert_origin or __name__
            logger.debug("pre-insert: %s – %s", getattr(cap, "value", cap), reason)
            # Preserve original image; mark as skipped
            ctx.updated = UpdatedView(lines=original_lines)
            ctx.status.write = WriteStatus.SKIPPED
            ctx.add_warning(f"{reason} (origin: {origin})")
            return ctx

    # --- Replace path (view-based) ---
    existing_range: tuple[int, int] | None = ctx.header.range if ctx.header else None
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
            ctx.status.write = WriteStatus.SKIPPED
            ctx.updated = UpdatedView(lines=original_lines)
            logger.trace("Updater: replacement yields no changes for %s", ctx.path)
            return ctx
        ctx.status.write = WriteStatus.REPLACED if apply else WriteStatus.PREVIEWED
        ctx.updated = UpdatedView(lines=new_lines)
        logger.trace("Updated file (replace):\n%s", "".join(new_lines))
        return ctx

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
            new_text: str = original_text[:char_offset] + header_text + original_text[char_offset:]
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
                ctx.updated = UpdatedView(lines=original_lines)
                ctx.status.write = WriteStatus.SKIPPED
                logger.trace("Updater: text-based insertion yields no changes for %s", ctx.path)
                return ctx
            ctx.updated = UpdatedView(lines=new_text.splitlines(keepends=True))
            ctx.status.write = WriteStatus.INSERTED if apply else WriteStatus.PREVIEWED
            return ctx
    except Exception as e:
        logger.warning("text-based insertion failed for %s: %s", ctx.path, e)

    # --- Insert: line-based fallback ---
    insert_index: int = ctx.header_processor.compute_insertion_anchor(original_lines)
    if insert_index == NO_LINE_ANCHOR:
        ctx.status.write = WriteStatus.FAILED
        ctx.add_error(f"No line-based insertion anchor for file: {ctx.path}")
        return ctx

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
    new_lines = _drop_trailing_blank_if_header_at_eof(new_lines, insert_index, len(header_lines))
    # Prepend BOM if needed
    new_lines = _prepend_bom_to_lines_if_needed(new_lines, ctx)
    if new_lines == original_lines:
        ctx.updated = UpdatedView(lines=original_lines)
        ctx.status.write = WriteStatus.SKIPPED
        logger.trace("Updater: line-based insertion yields no changes for %s", ctx.path)
        return ctx
    ctx.updated = UpdatedView(lines=new_lines)
    ctx.status.write = WriteStatus.INSERTED if apply else WriteStatus.PREVIEWED
    logger.trace("Updated file (line-based):\n%s", "".join(new_lines))
    return ctx
