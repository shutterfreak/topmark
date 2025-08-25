# topmark:header:start
#
#   file         : renderer.py
#   file_relpath : src/topmark/pipeline/steps/renderer.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Header renderer step for the TopMark pipeline.

This step takes the expected header field dictionary (built by previous steps)
and renders it into a list of text lines according to the active file type's
header style. It preserves the file's newline convention and performs no I/O.
"""

from topmark.config.logging import get_logger
from topmark.pipeline.context import GenerationStatus, ProcessingContext

logger = get_logger(__name__)


def render(ctx: ProcessingContext) -> ProcessingContext:
    """Render the expected header to text lines for the current file.

    Args:
        ctx: Mutable processing context. Requires:
            * `ctx.header_processor`: File-type strategy exposing `render_header_lines()`.
            * `ctx.expected_header_dict`: Expected header field dictionary.
            * `ctx.file_lines`: Original file lines (for style decisions).

    Returns:
        ProcessingContext: The same context with `expected_header_lines` and
        `expected_header_block` populated, and diagnostics possibly appended.

    Notes:
        Mutates fields on `ctx`; performs no I/O.
    """
    # Safeguard: only render when generation status indicates values are ready
    if ctx.status.generation not in [
        GenerationStatus.GENERATED,
        GenerationStatus.NO_FIELDS,
    ]:
        return ctx

    assert ctx.header_processor
    assert ctx.expected_header_dict
    assert ctx.config

    # Render using the file-type processor, honoring the detected newline style.
    ctx.expected_header_lines = ctx.header_processor.render_header_lines(
        header_values=ctx.expected_header_dict,
        config=ctx.config,
        newline_style=ctx.newline_style,
    )

    # Generate the expected (updated) header block, preserving the file newline style
    ctx.expected_header_block = "".join(ctx.expected_header_lines)  # Already has newlines

    logger.debug("Existing header block: %r", ctx.existing_header_block)
    logger.debug("Expected header block: %r", ctx.expected_header_block)

    return ctx
