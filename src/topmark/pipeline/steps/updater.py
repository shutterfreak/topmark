# topmark:header:start
#
#   project      : TopMark
#   file         : updater.py
#   file_relpath : src/topmark/pipeline/steps/updater.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Provides a pipeline step for inserting or replacing the TopMark header in a file.

This module defines a function that updates the ProcessingContext by inserting or replacing
the TopMark header in the file's contents. It updates the context's `updated_file_lines`
and `status.write` accordingly to reflect the changes made.

This step is covered by unit tests across processors (pound, slash, xml) and supports both
line-based and text-based insertion as well as replacement and the strip fast-path.

The updater respects comparer outcomes and file fidelity:
  * If `status.strip == READY`, it emits the strip image (`updated_file_lines`) and
    sets `write=REMOVED` (BOM reattached when present).
  * If `status.comparison == UNCHANGED`, it **short‑circuits** and sets `write=SKIPPED`,
    preserving the original image and producing no diff.
  * For replace/insert operations, it reattaches a leading UTF‑8 BOM when the reader
    detected one, and it avoids touch‑writes by checking if the resulting image equals
    the original.
  * **Insert (line‑based fallback)**: Use `compute_insertion_anchor`, optionally adjust
    whitespace via `prepare_header_for_insertion`, reattach BOM if needed; set `INSERTED`
    unless the result is identical, in which case `SKIPPED`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.config.logging import TopmarkLogger, get_logger
from topmark.pipeline.context import ComparisonStatus, ProcessingContext, StripStatus, WriteStatus
from topmark.pipeline.processors.base import NO_LINE_ANCHOR

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
    """Insert or replace the TopMark header for the current file.

    Behavior by case:
      • **Strip fast‑path**: When `status.strip == READY`, keep the precomputed
        `updated_file_lines`, reattach a BOM if the reader saw one, and mark
        `write=REMOVED`.
      • **Already up‑to‑date**: When `status.comparison == UNCHANGED`, do nothing,
        set `write=SKIPPED`, and keep the original image. No diff is produced.
      • **Replace**: If an `existing_header_range` is known, splice
        `expected_header_lines` over that range; reattach BOM if needed; if the
        result equals the original, set `write=SKIPPED`; otherwise `write=REPLACED`.
      • **Insert (text‑based)**: If the processor provides a character offset, insert
        the rendered header text there (after optional `prepare_header_for_insertion_text`),
        reattach BOM if needed; if identical to original, `SKIPPED`; else `INSERTED`.
      • **Insert (line‑based fallback)**: Use `get_header_insertion_index`, optionally
        adjust whitespace via `prepare_header_for_insertion`, reattach BOM if needed;
        set `INSERTED` unless the result is identical, in which case `SKIPPED`.

    The updater never mutates the file on disk; it only prepares `updated_file_lines` and
    `status.write` for later patch/apply steps.
    """
    logger.debug("ctx.config.apply_changes = %s", ctx.config.apply_changes)
    apply: bool = False if ctx.config.apply_changes is None else ctx.config.apply_changes

    if ctx.status.strip == StripStatus.READY:
        # Previous step computed updated_file_lines for a removal.
        # Ensure BOM policy is respected on the final output.
        ctx.updated_file_lines = _prepend_bom_to_lines_if_needed(ctx.updated_file_lines or [], ctx)
        ctx.status.write = WriteStatus.REMOVED if apply else WriteStatus.PREVIEWED
        return ctx

    # If the comparer determined the file is already compliant, do nothing.
    if ctx.status.comparison is ComparisonStatus.UNCHANGED:
        ctx.status.write = WriteStatus.SKIPPED
        # Preserve the original image as the "updated" content for downstream steps.
        ctx.updated_file_lines = ctx.file_lines or []
        logger.trace("Updater: no-op (comparison=UNCHANGED) for %s", ctx.path)
        return ctx

    # Non-strip processing
    if ctx.expected_header_lines is None:
        ctx.add_error("Cannot update header: no rendered header available")
        ctx.status.write = WriteStatus.SKIPPED
        return ctx

    if ctx.header_processor is None:
        ctx.add_error("Cannot update header: no header processor assigned")
        ctx.status.write = WriteStatus.SKIPPED
        return ctx

    # --- Pre-insert capability check (authoritative) --------------------------
    try:
        ft: FileType | None = getattr(ctx, "file_type", None)
        checker: InsertChecker | None = getattr(ft, "pre_insert_checker", None) if ft else None
        if checker is not None:
            # Local import to avoid potential import cycles
            from topmark.filetypes.base import InsertCapability

            try:
                result: InsertCheckResult = checker(ctx) or {}
            except Exception as exc:
                logger.exception(
                    "pre-insert checker failed for %s: %s", getattr(ft, "name", ft), exc
                )
                result = {"capability": InsertCapability.SKIP_OTHER, "reason": "checker error"}

            cap: InsertCapability = result.get("capability", InsertCapability.OK)
            if cap is not InsertCapability.OK:
                reason: str = result.get("reason", "pre-insert checker skipped update")
                logger.debug("pre-insert: %s – %s", getattr(cap, "value", cap), reason)
                # Preserve original image; mark as skipped
                original_lines: list[str] = ctx.file_lines or []
                ctx.updated_file_lines = original_lines
                ctx.status.write = WriteStatus.SKIPPED
                # Surface hint for UX/debugging (non-fatal)
                try:
                    ctx.add_warning(reason)
                except Exception:
                    pass
                return ctx
    except Exception:
        # Never let the gate crash the updater; continue with normal flow
        logger.debug("pre-insert gate: ignored due to unexpected error", exc_info=True)

    original_lines = ctx.file_lines or []
    rendered_expected_header_lines: list[str] = ctx.expected_header_lines

    if ctx.existing_header_range is not None:
        # Replace existing header: remove old header lines and insert new header in place
        start: int
        end: int
        start, end = ctx.existing_header_range
        new_lines: list[str] = (
            original_lines[:start] + rendered_expected_header_lines + original_lines[end + 1 :]
        )
        # Prepend BOM if needed
        new_lines = _prepend_bom_to_lines_if_needed(new_lines, ctx)
        # If replacement is identical to the original, treat as a no-op.
        if new_lines == original_lines:
            ctx.status.write = WriteStatus.SKIPPED
            ctx.updated_file_lines = original_lines
            logger.trace("Updater: replacement yields no changes for %s", ctx.path)
            return ctx
        ctx.status.write = WriteStatus.REPLACED if apply else WriteStatus.PREVIEWED
        ctx.updated_file_lines = new_lines
        logger.trace("Updated file (replace):\n%s", "".join(ctx.updated_file_lines or []))
        return ctx
    else:
        # 1) text-based first
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
                    ctx.updated_file_lines = original_lines
                    ctx.status.write = WriteStatus.SKIPPED
                    logger.trace("Updater: text-based insertion yields no changes for %s", ctx.path)
                    return ctx
                ctx.updated_file_lines = new_text.splitlines(keepends=True)
                ctx.status.write = WriteStatus.INSERTED if apply else WriteStatus.PREVIEWED
                return ctx
        except Exception as e:
            logger.warning("text-based insertion failed for %s: %s", ctx.path, e)

        # 2) fallback: line-based
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
        new_lines = _drop_trailing_blank_if_header_at_eof(
            new_lines, insert_index, len(header_lines)
        )
        # Prepend BOM if needed
        new_lines = _prepend_bom_to_lines_if_needed(new_lines, ctx)
        if new_lines == original_lines:
            ctx.updated_file_lines = original_lines
            ctx.status.write = WriteStatus.SKIPPED
            logger.trace("Updater: line-based insertion yields no changes for %s", ctx.path)
            return ctx
        ctx.updated_file_lines = new_lines
        ctx.status.write = WriteStatus.INSERTED if apply else WriteStatus.PREVIEWED
        logger.trace("Updated file (line-based):\n%s", "".join(ctx.updated_file_lines or []))
        return ctx
