# topmark:header:start
#
#   project      : TopMark
#   file         : scanner.py
#   file_relpath : src/topmark/pipeline/steps/scanner.py
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
format-specific parsing. It operates on a ProcessingContext that already exposes the file
image via `ctx.image` (see ``FileImageView``). The scanner updates the context with a
[`topmark.pipeline.views.HeaderView`][] that contains the header range, extracted lines,
a reconstructed header block and parsed key‑value fields. Legacy ``existing_header_*`` fields
are kept in sync during the migration.
"""

from __future__ import annotations

from itertools import islice
from typing import TYPE_CHECKING

from topmark.config.logging import TopmarkLogger, get_logger
from topmark.constants import TOPMARK_END_MARKER, TOPMARK_START_MARKER, VALUE_NOT_SET
from topmark.pipeline.context import (
    FsStatus,
    HeaderStatus,
    ProcessingContext,
    may_proceed_to_scanner,
)
from topmark.pipeline.views import HeaderView

if TYPE_CHECKING:
    from topmark.pipeline.processors.types import HeaderParseResult

logger: TopmarkLogger = get_logger(__name__)


def scan(ctx: ProcessingContext) -> ProcessingContext:
    """Detect and extract a TopMark header from the file image.

    Precondition:
        - ``ctx.status.file`` is RESOLVED or EMPTY_FILE.
        - ``ctx.image`` (or legacy backing) is populated by the reader step.
        - ``ctx.header_processor`` is set.

    Args:
        ctx (ProcessingContext): Processing context with the file image and a header processor.

    Returns:
        ProcessingContext: The same context updated with:
        - ``ctx.header``: a ``HeaderView`` containing range/lines/block/mapping
        - ``ctx.status.header``: one of {MISSING, EMPTY, DETECTED, MALFORMED}
    """
    logger.debug("ctx: %s", ctx)

    if not may_proceed_to_scanner(ctx):
        logger.info("Scanner skipped by may_proceed_to_scanner()")
        return ctx

    logger.debug(
        "Phase 2 - Scanning file %s of type %s for header fields",
        ctx.path,
        ctx.file_type,
    )

    assert ctx.header_processor, (
        "context.header_processor not defined"
    )  # This should always be defined!

    if ctx.status.fs == FsStatus.EMPTY:
        # An empty file is considered to have no header, but we can still proceed
        logger.info("File %s is empty; no header to scan.", ctx.path)
        ctx.status.header = HeaderStatus.MISSING
        return ctx

    if ctx.file_line_count() == 0:
        # Defensive guard; upstream reader should have set UNREADABLE or EMPTY_FILE
        logger.error("scan(): No file lines available for %s", ctx.path)
        return ctx

    # Use header_processor.get_header_bounds() to locate header start and end indices
    start_idx: int | None = None
    end_idx: int | None = None
    bounds: tuple[int | None, int | None] | None = (
        ctx.header_processor.get_header_bounds(
            lines=ctx.iter_file_lines(),
            newline_style=ctx.newline_style,
        )
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
        ctx.status.header = HeaderStatus.MALFORMED
        ctx.add_warning(
            f"Malformed header: found header start at line {start_idx + 1} but no matching end."
        )
        logger.warning("Malformed header: found header start but no matching end in %s", ctx.path)
        return ctx

    if start_idx is None and end_idx is not None:
        ctx.status.header = HeaderStatus.MALFORMED
        ctx.add_warning(
            f"Malformed header: found header end at line {end_idx + 1} but no matching start."
        )
        logger.warning("Malformed header: found header end but no matching start in %s", ctx.path)
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
        ctx.status.header = HeaderStatus.MALFORMED
        ctx.add_warning(
            f"Malformed header: end marker at line {end_idx + 1} "
            f"before start marker at line {start_idx + 1}."
        )
        logger.warning(
            "Malformed header: end marker found before start marker",
        )
        return ctx

    # Header found and valid: ensure we have inclusive indices
    existing_header_range: tuple[int, int] = (start_idx, end_idx)
    # Slice via iterator to avoid materializing the full file
    header_iter: islice[str] = islice(ctx.iter_file_lines(), start_idx, end_idx + 1)
    existing_header_lines: list[str] = list(header_iter)
    existing_header_block: str = "".join(existing_header_lines)

    # 1) Create the view first (mapping=None for now)
    ctx.header = HeaderView(
        range=existing_header_range,
        lines=existing_header_lines,
        block=existing_header_block,
        mapping=None,
    )

    # 2) Now parse fields (parse_fields reads from context.header)
    parse_result: HeaderParseResult = ctx.header_processor.parse_fields(ctx)

    # 3) Attach mapping and counts to the view
    ctx.header.mapping = parse_result.fields
    ctx.header.success_count = parse_result.success_count
    ctx.header.error_count = parse_result.error_count

    logger.debug(
        "Header extracted from lines %d to %d (success: %d, error: %d):\n%s",
        start_idx + 1,
        end_idx + 1,
        ctx.header.success_count,
        ctx.header.error_count,
        ctx.header.block,
    )

    total_count: int = ctx.header.success_count + ctx.header.error_count
    logger.debug(
        "Header markers present, found %d header lines (%d ok, %d with errors): %s",
        total_count,
        ctx.header.success_count,
        ctx.header.error_count,
        ctx.path,
    )

    if ctx.header.error_count > 0:
        # At least one header fleid line errored

        if ctx.header.success_count == 0:
            # All header lines in the header block are malformed
            ctx.status.header = HeaderStatus.MALFORMED_ALL_FIELDS
            logger.info("Header markers present, all header field lines invalid.")
            ctx.add_warning(
                f"Header markers present at line {start_idx + 1} and {end_idx + 1}, "
                f"skipped {ctx.header.error_count} invalid header lines, "
                "no valid header lines found."
            )
            return ctx
        else:
            # At least one remaining valid header line
            ctx.status.header = HeaderStatus.MALFORMED_SOME_FIELDS
            logger.info(
                "Header markers present, %d of %d field lines invalid.",
                ctx.header.error_count,
                total_count,
            )
            ctx.add_warning(
                f"Header markers present at line {start_idx + 1} and {end_idx + 1}, "
                f"skipped {ctx.header.error_count} invalid header lines, "
                f"{ctx.header.success_count} valid header lines found."
            )
            return ctx

    if not ctx.header.mapping:
        ctx.status.header = HeaderStatus.EMPTY
        logger.info("Header markers present but no fields in '%s'", ctx.path)
        ctx.add_warning(
            f"Header markers present at line {start_idx + 1} and {end_idx + 1} but no fields."
        )
    else:
        ctx.status.header = HeaderStatus.DETECTED

    logger.debug(
        "File status: %s, resolve status: %s, content status: %s, header status: %s, "
        + "existing header range: %s",
        ctx.status.fs.value,
        ctx.status.resolve.value,
        ctx.status.content.value,
        ctx.status.header.value,
        ctx.header.range or VALUE_NOT_SET,
    )
    logger.trace(
        "Existing header dict: %s",
        ctx.header.mapping,
    )

    return ctx
