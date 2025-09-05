# topmark:header:start
#
#   file         : updater.py
#   file_relpath : src/topmark/pipeline/steps/updater.py
#   project      : TopMark
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
  • If `status.strip == READY`, it emits the strip image (`updated_file_lines`) and
    sets `write=REMOVED` (BOM reattached when present).
  • If `status.comparison == UNCHANGED`, it **short‑circuits** and sets `write=SKIPPED`,
    preserving the original image and producing no diff.
  • For replace/insert operations, it reattaches a leading UTF‑8 BOM when the reader
    detected one, and it avoids touch‑writes by checking if the resulting image equals
    the original.
"""

from topmark.config.logging import get_logger
from topmark.pipeline.context import ComparisonStatus, ProcessingContext, StripStatus, WriteStatus
from topmark.pipeline.processors.base import NO_LINE_ANCHOR

logger = get_logger(__name__)


def _prepend_bom_to_lines_if_needed(lines: list[str], ctx: ProcessingContext) -> list[str]:
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
        lines: The updated file content as a list of lines (each with its own newline).
        ctx: The pipeline processing context (provides ``leading_bom`` and ``has_shebang``).

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
        ctx.diagnostics.append(
            "UTF-8 BOM appears before the shebang; POSIX requires '#!' at byte 0. "
            "TopMark will not modify this file by default. Consider removing the BOM "
            "or using a future '--fix-bom' option to resolve this conflict."
        )
        return lines

    # Re-attach the stripped BOM
    first = lines[0]
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
    if ctx.status.strip == StripStatus.READY:
        # Previous step computed updated_file_lines for a removal.
        # Ensure BOM policy is respected on the final output.
        ctx.updated_file_lines = _prepend_bom_to_lines_if_needed(ctx.updated_file_lines or [], ctx)
        ctx.status.write = WriteStatus.REMOVED  # actual apply path will only finalize the write
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
        ctx.diagnostics.append("Cannot update header: no rendered header available")
        ctx.status.write = WriteStatus.SKIPPED
        return ctx

    if ctx.header_processor is None:
        ctx.diagnostics.append("Cannot update header: no header processor assigned")
        ctx.status.write = WriteStatus.SKIPPED
        return ctx

    original_lines = ctx.file_lines or []
    rendered_expected_header_lines = ctx.expected_header_lines

    if ctx.existing_header_range is not None:
        # Replace existing header: remove old header lines and insert new header in place
        start, end = ctx.existing_header_range
        new_lines = (
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
        ctx.status.write = WriteStatus.REPLACED
        ctx.updated_file_lines = new_lines
        logger.trace("Updated file (replace):\n%s", "".join(ctx.updated_file_lines or []))
        return ctx
    else:
        # 1) text-based first
        try:
            original_text = "".join(original_lines)
            char_offset = None
            if hasattr(ctx.header_processor, "get_header_insertion_char_offset"):
                char_offset = ctx.header_processor.get_header_insertion_char_offset(original_text)
            if char_offset is not None:
                header_text = "".join(rendered_expected_header_lines)
                if hasattr(ctx.header_processor, "prepare_header_for_insertion_text"):
                    try:
                        header_text = ctx.header_processor.prepare_header_for_insertion_text(
                            original_text, char_offset, header_text
                        )
                    except Exception as e:
                        logger.warning(
                            "prepare_header_for_insertion_text failed for %s: %s", ctx.path, e
                        )

                new_text = original_text[:char_offset] + header_text + original_text[char_offset:]
                # Prepend BOM if needed
                if getattr(ctx, "leading_bom", False) and not new_text.startswith("\ufeff"):
                    new_text = "\ufeff" + new_text
                if new_text == original_text:
                    ctx.updated_file_lines = original_lines
                    ctx.status.write = WriteStatus.SKIPPED
                    logger.trace("Updater: text-based insertion yields no changes for %s", ctx.path)
                    return ctx
                ctx.updated_file_lines = new_text.splitlines(keepends=True)
                ctx.status.write = WriteStatus.INSERTED
                return ctx
        except Exception as e:
            logger.warning("text-based insertion failed for %s: %s", ctx.path, e)

        # 2) fallback: line-based
        insert_index = ctx.header_processor.get_header_insertion_index(original_lines)
        if insert_index == NO_LINE_ANCHOR:
            ctx.status.write = WriteStatus.FAILED
            ctx.diagnostics.append(f"No line-based insertion anchor for file: {ctx.path}")
            return ctx

        # defensive clamp
        if insert_index < 0:
            insert_index = 0
        elif insert_index > len(original_lines):
            insert_index = len(original_lines)

        # optional whitespace adjustments
        try:
            rendered_expected_header_lines = ctx.header_processor.prepare_header_for_insertion(
                original_lines, insert_index, rendered_expected_header_lines
            )
        except Exception as e:
            logger.warning("prepare_header_for_insertion failed for %s: %s", ctx.path, e)

        new_lines = (
            original_lines[:insert_index]
            + rendered_expected_header_lines
            + original_lines[insert_index:]
        )
        # Prepend BOM if needed
        new_lines = _prepend_bom_to_lines_if_needed(new_lines, ctx)
        if new_lines == original_lines:
            ctx.updated_file_lines = original_lines
            ctx.status.write = WriteStatus.SKIPPED
            logger.trace("Updater: line-based insertion yields no changes for %s", ctx.path)
            return ctx
        ctx.updated_file_lines = new_lines
        ctx.status.write = WriteStatus.INSERTED
        logger.trace("Updated file (line-based):\n%s", "".join(ctx.updated_file_lines or []))
        return ctx
