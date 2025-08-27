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
"""

from topmark.config.logging import get_logger
from topmark.pipeline.context import ProcessingContext, StripStatus, WriteStatus
from topmark.pipeline.processors.base import NO_LINE_ANCHOR

logger = get_logger(__name__)


def _prepend_bom_to_lines_if_needed(lines: list[str], leading_bom: bool) -> list[str]:
    """Prepend a UTF-8 BOM to the first line when requested.

    Args:
        lines: Updated file content lines.
        leading_bom: Whether the original file started with a BOM.

    Returns:
        The (possibly) modified list of lines. Never ``None``.
    """
    if not lines or not leading_bom:
        return lines
    first = lines[0]
    if not first.startswith("\ufeff"):
        lines = lines[:]  # shallow copy to avoid mutating caller’s list
        lines[0] = "\ufeff" + first
    return lines


def update(ctx: ProcessingContext) -> ProcessingContext:
    """Insert or replace the TopMark header in the file represented by the context.

    This pipeline step updates `context.updated_file_lines` and `context.status.write`
    by either replacing an existing header or inserting a new header based on the
    provided `expected_header_lines` and the header processor logic.

    Args:
        ctx (ProcessingContext): The processing context containing file data,
            expected header lines, header processor, and status information.

    Returns:
        ProcessingContext: The updated processing context with modified file lines
            and write status.

    Notes:
        - If no rendered header lines are available, the step is skipped and a diagnostic
          message is appended.
        - If no header processor is assigned, the step is skipped and a diagnostic
          message is appended.
        - If an existing header is found, it is replaced by the new expected header.
        - If no existing header is found, the new header is inserted at the position
          determined by the header processor.
        - If the insertion index cannot be determined, the step fails and a diagnostic
          message is appended.
        - Re-attaches a UTF-8 BOM to the first line of the output when the reader detected one
          (ctx.leading_bom == True), for replace and insert operations, and for strip-ready output.
    """
    if ctx.status.strip == StripStatus.READY:
        # Previous step computed updated_file_lines for a removal.
        # Ensure BOM policy is respected on the final output.
        ctx.updated_file_lines = _prepend_bom_to_lines_if_needed(
            ctx.updated_file_lines or [], getattr(ctx, "leading_bom", False)
        )
        ctx.status.write = WriteStatus.REMOVED  # actual apply path will only finalize the write
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
        new_lines = _prepend_bom_to_lines_if_needed(new_lines, getattr(ctx, "leading_bom", False))
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
        new_lines = _prepend_bom_to_lines_if_needed(new_lines, getattr(ctx, "leading_bom", False))
        ctx.updated_file_lines = new_lines
        ctx.status.write = WriteStatus.INSERTED
        logger.trace("Updated file (line-based):\n%s", "".join(ctx.updated_file_lines or []))
        return ctx
