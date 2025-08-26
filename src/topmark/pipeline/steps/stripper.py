# topmark:header:start
#
#   file         : stripper.py
#   file_relpath : src/topmark/pipeline/steps/stripper.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Pipeline step that removes the TopMark header.

The step uses the scanner‑detected header span when available
(``ctx.existing_header_range``) and delegates removal to the active header
processor. It sets ``ctx.updated_file_lines`` only when a removal is performed
and updates ``StripStatus`` to ``READY`` or ``NOT_NEEDED`` accordingly.
"""

from topmark.config.logging import get_logger
from topmark.pipeline.context import HeaderStatus, ProcessingContext, StripStatus

logger = get_logger(__name__)


def strip(ctx: ProcessingContext) -> ProcessingContext:
    """Remove the TopMark header using the processor and known span if available.

    Args:
      ctx (ProcessingContext): Pipeline context. Must contain file lines, the
        active header processor, and (optionally) the scanner‑detected header span.

    Returns:
      ProcessingContext: The same context, with ``updated_file_lines`` populated
        when a removal occurs and ``StripStatus`` updated to reflect the outcome.

    Notes:
      - Leaves ``HeaderStatus`` untouched (owned by the scanner).
      - Trims a single leading blank line when the header starts at the top of the file
        (handled inside the processor).
    """
    if ctx.status.header is HeaderStatus.MISSING:
        ctx.status.strip = StripStatus.NOT_NEEDED
        return ctx
    if ctx.status.header not in [HeaderStatus.EMPTY, HeaderStatus.DETECTED]:
        # No header to be stripped
        ctx.status.strip = StripStatus.FAILED
        ctx.diagnostics.append(
            f"stripper: skipping {ctx.path}, header status is {ctx.status.header.value}"
        )
        return ctx

    if ctx.header_processor is None:
        return ctx

    lines = ctx.file_lines or []
    if not lines:
        # Empty file
        return ctx

    # Prefer the span detected by the scanner; fall back to processor logic otherwise.
    span = ctx.existing_header_range

    new_lines, removed = ctx.header_processor.strip_header_block(lines=lines, span=span)
    if removed is None or new_lines == lines:
        # Nothing to remove
        ctx.status.strip = StripStatus.NOT_NEEDED
        return ctx

    logger.info("Updated file lines: %s", new_lines[:15])
    ctx.updated_file_lines = new_lines
    # A header was present and removed
    ctx.status.strip = StripStatus.READY
    ctx.diagnostics.append(
        f"stripper: removed header lines at span {removed[0]}..{removed[1]} in {ctx.path}"
    )
    return ctx
