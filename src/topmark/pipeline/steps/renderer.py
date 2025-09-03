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

This step turns the expected header *field dictionary* into a list of text lines
using the active file type’s header formatting rules. It preserves the file’s
newline convention, mutates only the processing context, and performs no I/O.

Behavior overview:
  • If `ctx.status.generation == NO_FIELDS`, the renderer is a **no‑op** and clears
    `ctx.expected_header_lines` / `ctx.expected_header_block` (both set to `None`).
  • If `ctx.status.generation == GENERATED`, the renderer expects
    `ctx.expected_header_dict` to be present. An empty dict is tolerated
    defensively: it produces an empty render (empty list / empty string) and
    returns without error.
  • For any other generation status, the step returns immediately without changes.

Notes:
  The renderer does not write to disk. It prepares the in‑memory representation
  (`expected_header_lines`/`expected_header_block`) that downstream steps
  (comparer/patcher/updater) will use.
"""

from topmark.config.logging import get_logger
from topmark.pipeline.context import GenerationStatus, ProcessingContext

logger = get_logger(__name__)


def render(ctx: ProcessingContext) -> ProcessingContext:
    """Render the expected header to text lines for the current file.

    Args:
      ctx (ProcessingContext): Mutable context with at least:
        * `header_processor` – strategy providing `render_header_lines()`;
        * `expected_header_dict` – expected fields (for `GENERATED`);
        * `file_lines` – original lines, used to preserve newline style.

    Returns:
      ProcessingContext: Same context with the following fields set depending on
      the generation status:
        * `NO_FIELDS` – no‑op; sets `expected_header_lines = None` and
          `expected_header_block = None`.
        * `GENERATED` – sets `expected_header_lines` and `expected_header_block`.
          If `expected_header_dict` is empty, produces an empty render defensively.
        * any other status – returns unchanged.

    Notes:
      This step mutates `ctx` in place and performs no I/O.
    """
    # Safeguard: only render when generation status indicates values are ready
    if ctx.status.generation not in [
        GenerationStatus.GENERATED,
        GenerationStatus.NO_FIELDS,
    ]:
        return ctx

    # Nothing to render when no fields were generated; short-circuit safely.
    if ctx.status.generation is GenerationStatus.NO_FIELDS:
        # Make it explicit that there is no “expected header” to compare against.
        ctx.expected_header_lines = None
        ctx.expected_header_block = None
        return ctx

    assert ctx.header_processor
    # At this point we expect a dictionary (possibly empty in edge cases).
    assert ctx.expected_header_dict is not None, (
        "expected_header_dict must be set when generation=GENERATED"
    )

    # Extremely defensive: if a GENERATED state comes with an empty dict,
    # render an empty block and return gracefully rather than crashing.
    if not ctx.expected_header_dict:
        ctx.expected_header_lines = []
        ctx.expected_header_block = ""
        return ctx

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
