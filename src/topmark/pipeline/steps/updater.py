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

Note:
    This is an early, untested implementation and may require further validation and testing.
"""

from topmark.config.logging import get_logger
from topmark.pipeline.context import ProcessingContext, WriteStatus

logger = get_logger(__name__)


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

    Behavior:
        - If no rendered header lines are available, the step is skipped and a diagnostic
          message is appended.
        - If no header processor is assigned, the step is skipped and a diagnostic
          message is appended.
        - If an existing header is found, it is replaced by the new expected header.
        - If no existing header is found, the new header is inserted at the position
          determined by the header processor.
        - If the insertion index cannot be determined, the step fails and a diagnostic
          message is appended.
    """
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
        ctx.status.write = WriteStatus.REPLACED
    else:
        # Insert new header at index determined by header processor based on file type and content
        insert_index = ctx.header_processor.get_header_insertion_index(original_lines)
        if insert_index is None:
            logger.error("No header insertion index found for file: %s", ctx.path)
            ctx.status.write = WriteStatus.FAILED
            ctx.diagnostics.append(f"No header insertion index found for file: {ctx.path}")
            return ctx

        # Optional text-based insertion path for processors that provide a char offset
        try:
            original_text = "".join(original_lines)
            char_offset = None
            if hasattr(ctx.header_processor, "get_header_insertion_char_offset"):
                char_offset = ctx.header_processor.get_header_insertion_char_offset(original_text)
            if char_offset is not None:
                header_text = "".join(rendered_expected_header_lines)
                if hasattr(ctx.header_processor, "prepare_header_for_insertion_text"):
                    header_text = ctx.header_processor.prepare_header_for_insertion_text(
                        original_text,
                        char_offset,
                        header_text,
                    )
                new_text = original_text[:char_offset] + header_text + original_text[char_offset:]
                new_lines = new_text.splitlines(keepends=True)
                ctx.updated_file_lines = new_lines
                ctx.status.write = WriteStatus.INSERTED
                logger.trace(
                    "Updated file (text-based):\n%s", "".join(ctx.updated_file_lines or [])
                )
                return ctx
        except Exception as e:
            logger.warning("text-based insertion failed for %s: %s", ctx.path, e)

        # Let the header processor adjust whitespace/padding around the header
        try:
            rendered_expected_header_lines = ctx.header_processor.prepare_header_for_insertion(
                original_lines,
                insert_index,
                rendered_expected_header_lines,
            )
        except Exception as e:
            logger.warning("prepare_header_for_insertion failed for %s: %s", ctx.path, e)

        new_lines = (
            original_lines[:insert_index]
            + rendered_expected_header_lines
            + original_lines[insert_index:]
        )
        ctx.status.write = WriteStatus.INSERTED

    ctx.updated_file_lines = new_lines

    logger.trace("Updated file:\n%s", "".join(ctx.updated_file_lines or []))

    return ctx
