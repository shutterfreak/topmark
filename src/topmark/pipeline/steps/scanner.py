# topmark:header:start
#
#   file         : scanner.py
#   file_relpath : src/topmark/pipeline/steps/scanner.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Scanner for detecting and extracting structured TopMark headers from source files.

This module is part of the TopMark pipeline steps and provides logic to detect and extract
structured header blocks from a file's contents. It interacts with a registered HeaderProcessor
to locate the presence and boundaries of a header block in a file and to parse the fields
defined within that header.

The scanner itself is file format agnostic and relies on the HeaderProcessor to handle
format-specific parsing. It operates on a ProcessingContext, assuming the file content
has already been read into ``context.file_lines`` (with original line endings preserved).
It updates the context with the header range, extracted lines, a reconstructed header block,
and parsed key-value fields.
"""

from topmark.config.logging import get_logger
from topmark.constants import TOPMARK_END_MARKER, TOPMARK_START_MARKER, VALUE_NOT_SET
from topmark.pipeline.context import FileStatus, HeaderStatus, ProcessingContext

logger = get_logger(__name__)


def scan(ctx: ProcessingContext) -> ProcessingContext:
    """Detect and extract a TopMark header from file lines.

    Precondition:
      - `ctx.status.file` is RESOLVED or EMPTY_FILE.
      - `ctx.file_lines` populated by the reader step.
      - `ctx.header_processor` is set.

    Args:
      ctx: Processing context with file lines and a header processor.

    Returns:
      The same context updated with:
        - existing_header_range / existing_header_lines / existing_header_block
        - existing_header_dict (parsed)
        - status.header (MISSING, EMPTY, DETECTED, MALFORMED)
    """
    # Pipeline safeguard
    if ctx.status.file not in [FileStatus.RESOLVED, FileStatus.EMPTY_FILE]:
        # Stop processing if the file is neither resolved nor empty (which implies resolved)
        return ctx

    logger.debug(
        "Phase 2 - Scanning file %s of type %s for header fields",
        ctx.path,
        ctx.file_type,
    )

    assert ctx.header_processor, (
        "context.header_processor not defined"
    )  # This should always be defined!

    lines = ctx.file_lines
    if not lines:
        # Defensive guard; upstream reader should have set UNREADABLE or EMPTY_FILE
        logger.error("scan(): No file lines available for %s", ctx.path)
        return ctx

    # Use header_processor.get_header_bounds() to locate header start and end indices
    start_idx: int | None = None
    end_idx: int | None = None
    bounds = (
        ctx.header_processor.get_header_bounds(lines)
        if hasattr(ctx.header_processor, "get_header_bounds")
        else None
    )
    if bounds:
        start_idx, end_idx = bounds

    # Validate header boundaries and update status accordingly

    if start_idx is None and end_idx is None:
        logger.info("No header found in '%s'", ctx.path)
        ctx.status.header = HeaderStatus.MISSING
        return ctx

    if start_idx is not None and end_idx is None:
        logger.warning("Malformed header: found header start but no matching end in %s", ctx.path)
        ctx.status.header = HeaderStatus.MALFORMED
        return ctx

    if start_idx is None and end_idx is not None:
        logger.warning("Malformed header: found header end but no matching start in %s", ctx.path)
        ctx.status.header = HeaderStatus.MALFORMED
        return ctx

    if start_idx is None or end_idx is None:
        logger.warning(
            "Malformed header: header must be enclosed between '%s' and '%s'",
            TOPMARK_START_MARKER,
            TOPMARK_END_MARKER,
        )
        ctx.status.header = HeaderStatus.MALFORMED
        return ctx

    if end_idx < start_idx:
        logger.warning(
            "Malformed header: end marker found before start marker",
        )
        ctx.status.header = HeaderStatus.MALFORMED
        return ctx

    # Header found and valid
    # Extract header lines including start and end markers
    ctx.existing_header_range = (start_idx, end_idx)
    ctx.existing_header_lines = lines[start_idx : end_idx + 1]
    # Preserve header block exactly as in source
    ctx.existing_header_block = "".join(ctx.existing_header_lines)
    logger.debug(
        "Header extracted from lines %d to %d:\n%s",
        start_idx + 1,
        end_idx + 1,
        ctx.existing_header_block,
    )

    # Parse the header fields using the header processor
    ctx.existing_header_dict = ctx.header_processor.parse_fields(ctx)
    if not ctx.existing_header_dict:
        logger.info("Header markers present but no fields in '%s'", ctx.path)
        ctx.status.header = HeaderStatus.EMPTY
    else:
        ctx.status.header = HeaderStatus.DETECTED

    logger.debug(
        "File status: %s, header status: %s, existing header range: %s",
        ctx.status.file.value,
        ctx.status.header.value,
        ctx.existing_header_range or VALUE_NOT_SET,
    )
    logger.trace(
        "Existing header dict: %s",
        ctx.existing_header_dict,
    )

    return ctx
