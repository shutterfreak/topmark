# topmark:header:start
#
#   project      : TopMark
#   file         : renderer.py
#   file_relpath : src/topmark/pipeline/steps/renderer.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Header renderer step for the TopMark pipeline (view‑based).

This step takes the **selected field mapping** built in the previous step
(``ctx.build.selected``) and renders it into header text using the active
file type’s formatting rules. It preserves the file’s newline convention,
mutates only the processing context, and performs no I/O.

Outputs:
  * ``ctx.render.lines`` – rendered header lines (keepends).
  * ``ctx.render.block`` – concatenated rendered text.

Notes:
  * The builder remains the single source of field dictionaries
    (``ctx.build.builtins`` / ``ctx.build.selected``).
  * The renderer does **not** compute diffs nor write to disk.
"""

from __future__ import annotations

from itertools import islice

from topmark.config.logging import TopmarkLogger, get_logger
from topmark.pipeline.context import GenerationStatus, ProcessingContext, may_proceed_to_renderer
from topmark.pipeline.views import RenderView

logger: TopmarkLogger = get_logger(__name__)


def render(ctx: ProcessingContext) -> ProcessingContext:
    """Render the expected header text from ``ctx.build.selected``.

    Args:
        ctx (ProcessingContext): Mutable context with:
            * ``header_processor`` – strategy providing ``render_header_lines()``;
            * ``build.selected`` – expected fields (for ``GENERATED``);
            * ``image`` – file image view (for indentation preservation and newline style).

    Returns:
        ProcessingContext: The same context with ``ctx.render`` populated depending on
        the generation status:
            * ``NO_FIELDS`` – no‑op; sets ``ctx.render = RenderView(lines=None, block=None)``.
            * ``GENERATED`` – sets ``ctx.render.lines`` and ``ctx.render.block``.
              If the selected mapping is empty, produces an empty render defensively.
            * any other status – returns unchanged.

    Notes:
        This step mutates ``ctx`` in place and performs no I/O.
    """
    logger.debug("ctx: %s", ctx)

    if not may_proceed_to_renderer(ctx):
        logger.info("Renderer skipped by may_proceed_to_renderer()")
        return ctx

    # Nothing to render when no fields were generated; short-circuit safely.
    if ctx.status.generation == GenerationStatus.NO_FIELDS:
        # Make it explicit that there is no “expected header” to compare against.
        ctx.render = RenderView(lines=None, block=None)
        return ctx

    assert ctx.header_processor
    # Use builder output as the source of fields
    fields: dict[str, str] = ctx.build.selected if ctx.build and ctx.build.selected else {}

    # Compute header_indent_override using the header view and file lines
    # Preserve pre-prefix indentation when replacing an existing header
    # (spaces/tabs before the prefix, e.g., "    //"). This keeps nested/indented
    # headers (like JSONC inside an object) visually stable after replacement.
    header_indent_override: str | None = None
    if ctx.header and ctx.header.range is not None:
        start_idx: int
        _end_idx: int
        start_idx, _end_idx = ctx.header.range
        # Fetch the first header line via iterator without materializing the file
        first_line_iter: islice[str] = islice(ctx.iter_file_lines(), start_idx, start_idx + 1)
        first_line: str | None = next(first_line_iter, None)
        if first_line is not None:
            leading_ws: str = first_line[: len(first_line) - len(first_line.lstrip())]
            if leading_ws and first_line.lstrip().startswith(ctx.header_processor.line_prefix):
                header_indent_override = leading_ws

    # Defensive: if mapping is empty, produce an empty render
    if not fields:
        ctx.render = RenderView(lines=[], block="")
        return ctx

    rendered_lines: list[str] = ctx.header_processor.render_header_lines(
        header_values=fields,
        config=ctx.config,
        newline_style=ctx.newline_style,
        # keep any other overrides you already pass (block_prefix/suffix, line_prefix/suffix, etc.)
        header_indent_override=header_indent_override,  # preserve pre-prefix indent
        # line_indent_override stays as default so fields still use processor’s after-prefix spacing
    )

    # Generate the expected (updated) header block, preserving the file newline style
    ctx.render = RenderView(lines=rendered_lines, block="".join(rendered_lines))

    logger.debug("Rendered header block for %s:\n%s", ctx.path, ctx.render.block or "")

    return ctx
