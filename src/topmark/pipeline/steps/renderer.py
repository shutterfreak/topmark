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
(``ctx.views.build.selected``) and renders it into header text using the active
file type’s formatting rules. It preserves the file’s newline convention,
mutates only the processing context, and performs no I/O.

Outputs:
  * ``ctx.views.render.lines`` – rendered header lines (keepends).
  * ``ctx.views.render.block`` – concatenated rendered text.

Notes:
  * The builder remains the single source of field dictionaries
    (``ctx.views.build.builtins`` / ``ctx.views.build.selected``).
  * The renderer does **not** compute diffs nor write to disk.
"""

from __future__ import annotations

from itertools import islice
from typing import TYPE_CHECKING

from topmark.config.logging import get_logger
from topmark.pipeline.context.policy import allow_empty_header_by_policy
from topmark.pipeline.hints import Axis
from topmark.pipeline.status import GenerationStatus, RenderStatus
from topmark.pipeline.steps.base import BaseStep
from topmark.pipeline.views import BuilderView, HeaderView, RenderView

if TYPE_CHECKING:
    from topmark.config.logging import TopmarkLogger
    from topmark.pipeline.context.model import ProcessingContext


logger: TopmarkLogger = get_logger(__name__)


class RendererStep(BaseStep):
    """Render expected header text from the selected field mapping.

    Consumes `BuilderView.selected` and produces a `RenderView` with lines/block.
    Preserves newline style and indentation where applicable.

    Axes written:
      - render

    Sets:
      - RenderStatus: {PENDING, RENDERED}
    """

    def __init__(self) -> None:
        super().__init__(
            name=self.__class__.__name__,
            primary_axis=Axis.RENDER,
            axes_written=(Axis.RENDER,),
        )

    def may_proceed(self, ctx: ProcessingContext) -> bool:
        """Determine if processing can proceed to the render step.

        Processing can proceed if:
        - The header was successfully generated (ctx.status.generation is RENDERED or GENERATED)

        Args:
            ctx (ProcessingContext): The processing context for the current file.

        Returns:
            bool: True if processing can proceed to the render step, False otherwise.
        """
        if ctx.flow.halt:
            outcome: bool = False
        else:
            outcome = ctx.status.generation in {
                GenerationStatus.GENERATED,
                GenerationStatus.NO_FIELDS,
            }
        logger.debug("%s may_proceed is %s", self.__class__.__name__, outcome)
        return outcome

    def run(self, ctx: ProcessingContext) -> None:
        """Render the expected header text from ``ctx.views.build.selected``.

        Args:
            ctx (ProcessingContext): Mutable context with:
                * ``header_processor`` – strategy providing ``render_header_lines()``;
                * ``build.selected`` – expected fields (for ``GENERATED``);
                * ``image`` – file image view (for indentation preservation and newline style).

        Mutations:
            ProcessingContext: The same context with ``ctx.views.render`` populated depending on
            the generation status:
                * ``NO_FIELDS`` – no‑op; sets ``ctx.views.render
                  = RenderView(lines=None, block=None)``.
                * ``GENERATED`` – sets ``ctx.views.render.lines`` and ``ctx.views.render.block``.
                If the selected mapping is empty, produces an empty render defensively.
                * any other status – returns unchanged.

        Notes:
            This step mutates ``ctx`` in place and performs no I/O.
        """
        logger.debug("ctx: %s", ctx)

        assert ctx.header_processor  # static type check

        # Nothing to render when no fields were generated; short-circuit safely.
        if ctx.status.generation == GenerationStatus.NO_FIELDS:
            if allow_empty_header_by_policy(ctx):
                # Render markers-only (empty header) to enable deterministic compare/update.
                rendered_lines: list[str] = ctx.header_processor.render_header_lines(
                    header_values={},  # no fields
                    config=ctx.config,
                    newline_style=ctx.newline_style,
                    header_indent_override=None,
                )
                ctx.views.render = RenderView(lines=rendered_lines, block="".join(rendered_lines))
                ctx.status.render = RenderStatus.RENDERED
            else:
                # Make it explicit that there is no “expected header” to compare against.
                ctx.views.render = RenderView(lines=None, block=None)
                ctx.status.render = RenderStatus.SKIPPED
                # leave status as-is (PENDING) or set a neutral value if you add one
            return

        # Now ctx.status.generation == GenerationStatus.GENERATED

        # Use builder output as the source of fields
        header_view: HeaderView | None = ctx.views.header
        builder_view: BuilderView | None = ctx.views.build
        fields: dict[str, str] = (
            builder_view.selected if builder_view and builder_view.selected else {}
        )

        # Compute header_indent_override using the header view and file lines
        # Preserve pre-prefix indentation when replacing an existing header
        # (spaces/tabs before the prefix, e.g., "    //"). This keeps nested/indented
        # headers (like JSONC inside an object) visually stable after replacement.
        header_indent_override: str | None = None
        if header_view and header_view.range is not None:
            start_idx: int
            _end_idx: int
            start_idx, _end_idx = header_view.range
            # Fetch the first header line via iterator without materializing the file
            first_line_iter: islice[str] = islice(ctx.iter_image_lines(), start_idx, start_idx + 1)
            first_line: str | None = next(first_line_iter, None)
            if first_line is not None:
                leading_ws: str = first_line[: len(first_line) - len(first_line.lstrip())]
                if leading_ws and first_line.lstrip().startswith(ctx.header_processor.line_prefix):
                    header_indent_override = leading_ws

        # Defensive: if mapping is empty, produce an empty render
        if not fields:
            ctx.views.render = RenderView(lines=[], block="")
            return

        rendered_lines = ctx.header_processor.render_header_lines(
            header_values=fields,
            config=ctx.config,
            newline_style=ctx.newline_style,
            # keep any other overrides you already pass (block_prefix/suffix,
            # line_prefix/suffix, etc.)
            header_indent_override=header_indent_override,  # preserve pre-prefix indent
            # line_indent_override stays as default so fields still use processor’s
            # after-prefix spacing
        )

        # Generate the expected (updated) header block, preserving the file newline style
        ctx.status.render = RenderStatus.RENDERED
        ctx.views.render = RenderView(lines=rendered_lines, block="".join(rendered_lines))

        logger.debug("Rendered header block for %s:\n%s", ctx.path, ctx.views.render.block or "")

        return

    def hint(self, ctx: ProcessingContext) -> None:
        """Attach render hints (non-binding).

        Args:
            ctx (ProcessingContext): The processing context.
        """
        st: RenderStatus = ctx.status.render

        # May proceed to next step (always):
        if st == RenderStatus.RENDERED:
            pass  # normal; no hint
        # Stop processing:
        elif st == RenderStatus.SKIPPED:
            # renderer skipped
            ctx.stop_flow(reason=f"{self.__class__.__name__} skipped.", at_step=self)
        elif st == RenderStatus.PENDING:
            # renderer did not complete
            ctx.stop_flow(reason=f"{self.__class__.__name__} did not set state.", at_step=self)
