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

from topmark.config.logging import get_logger
from topmark.pipeline.context.policy import check_permitted_by_policy
from topmark.pipeline.hints import Axis, Cluster, KnownCode
from topmark.pipeline.processors.types import BoundsKind, HeaderBounds
from topmark.pipeline.status import (
    ContentStatus,
    FsStatus,
    HeaderStatus,
)
from topmark.pipeline.steps.base import BaseStep
from topmark.pipeline.views import HeaderView

if TYPE_CHECKING:
    from topmark.config.logging import TopmarkLogger
    from topmark.pipeline.context.model import ProcessingContext
    from topmark.pipeline.processors.types import HeaderParseResult

logger: TopmarkLogger = get_logger(__name__)


class ScannerStep(BaseStep):
    """Detect and parse TopMark headers from the file image.

    Uses the active `HeaderProcessor` to locate header bounds and parse fields into
    a `HeaderView`. Leaves unrelated axes untouched.

    Preconditions:
      - `ctx.image` is available (typically set by ReaderStep).
      - `ctx.header_processor` is set.

    Axes written:
      - header

    Sets:
      - HeaderStatus: {PENDING, MISSING, EMPTY, DETECTED,
                       MALFORMED, MALFORMED_SOME_FIELDS, MALFORMED_ALL_FIELDS}
    """

    def __init__(self) -> None:
        super().__init__(
            name=self.__class__.__name__,
            primary_axis=Axis.HEADER,
            axes_written=(Axis.HEADER,),
        )

    def may_proceed(self, ctx: ProcessingContext) -> bool:
        """Determine if processing can proceed to the scan step.

        Processing can proceed if:
        - The file was successfully resolved (ctx.status.resolve is RESOLVED)
        - The file type was resolved (ctx.file_type is not None)
        - A header processor is available (ctx.header_processor is not None)

        Args:
            ctx (ProcessingContext): The processing context for the current file.

        Returns:
            bool: True if processing can proceed to the build step, False otherwise.
        """
        if ctx.is_halted:
            return False
        return (
            ctx.header_processor is not None
            and ctx.status.content == ContentStatus.OK
            and ctx.status.content
            not in {
                ContentStatus.PENDING,
                ContentStatus.UNSUPPORTED,
                ContentStatus.UNREADABLE,
            }
        )

    def run(self, ctx: ProcessingContext) -> None:
        """Detect and extract a TopMark header from the file image.

        Behavior with discriminated ``HeaderBounds``:
            - ``NONE`` → mark ``HeaderStatus.MISSING`` and return.
            - ``MALFORMED`` → build a minimal ``HeaderView`` (when possible), set
              ``HeaderStatus.MALFORMED``, attach a diagnostic hint, and stop flow.
            - ``SPAN`` → slice the span, build ``HeaderView``, parse fields, and set
              one of ``{DETECTED, EMPTY, MALFORMED_SOME_FIELDS, MALFORMED_ALL_FIELDS}``.

        Args:
            ctx (ProcessingContext): Processing context with the file image and a header processor.

        Mutations:
            ProcessingContext: The same context updated with:
            - ``ctx.header``: a ``HeaderView`` containing range/lines/block/mapping
            - ``ctx.status.header``: one of {MISSING, EMPTY, DETECTED, MALFORMED}
        """
        logger.debug(
            "Scanning file %s of type %s for header fields",
            ctx.path,
            ctx.file_type,
        )
        logger.debug("ctx: %s", ctx)

        assert ctx.header_processor  # Satisfy static code analysis

        if ctx.status.fs == FsStatus.EMPTY:
            # An empty file is considered to have no header, but we can still proceed
            logger.info("File %s is empty; no header to scan.", ctx.path)
            ctx.status.header = HeaderStatus.MISSING
            return

        if ctx.image_line_count() == 0:
            # Defensive guard; upstream reader should have set UNREADABLE or EMPTY_FILE
            # TODO: check if ctx.status.header must be set (is now DEFAULT)
            logger.error("scan(): No file lines available for %s", ctx.path)
            return

        # Use header_processor.get_header_bounds() to locate header start and end indices
        hb: HeaderBounds = ctx.header_processor.get_header_bounds(
            lines=ctx.iter_image_lines(),
            newline_style=ctx.newline_style,
        )

        # NONE → MISSING
        if hb.kind is BoundsKind.NONE:
            logger.info("No header found in '%s'", ctx.path)
            ctx.status.header = HeaderStatus.MISSING
            return

        # MALFORMED → terminal (always)
        if hb.kind is BoundsKind.MALFORMED:
            s_opt: int | None
            e_opt: int | None
            s_opt, e_opt = hb.start, hb.end
            if s_opt is not None and e_opt is not None and s_opt < e_opt:
                # materialize minimal view for diagnostics
                lines: list[str] = list(islice(ctx.iter_image_lines(), s_opt, e_opt))
                ctx.views.header = HeaderView(
                    range=(s_opt, e_opt - 1),  # store inclusive range for views
                    lines=lines,
                    block="".join(lines),
                    mapping=None,
                )
            ctx.status.header = HeaderStatus.MALFORMED
            reason: str = hb.reason or "Malformed header markers"
            ctx.warn(reason)
            ctx.hint(
                axis=Axis.HEADER,
                code=KnownCode.HEADER_MALFORMED,
                cluster=Cluster.ERROR,
                message=reason,
                terminal=True,
            )
            ctx.request_halt(reason=f"scanner: {reason}", at_step=self)
            return

        # SPAN → slice, parse, classify
        s_excl: int | None = hb.start
        e_excl: int | None = hb.end  # exclusive
        assert s_excl is not None and e_excl is not None and s_excl < e_excl

        # Header found and valid: ensure we have inclusive indices
        # Slice via iterator to avoid materializing the full file
        header_lines: list[str] = list(islice(ctx.iter_image_lines(), s_excl, e_excl))
        header_block: str = "".join(header_lines)

        # 1) Create the view first (mapping=None for now). Store an inclusive range for the view.
        ctx.views.header = HeaderView(
            range=(s_excl, e_excl - 1),
            lines=header_lines,
            block=header_block,
            mapping=None,
        )

        # 2) Parse fields (parse_fields reads from context.header)
        parse_result: HeaderParseResult = ctx.header_processor.parse_fields(ctx)

        # 3) Attach mapping and counts to the view
        ctx.views.header.mapping = parse_result.fields
        ctx.views.header.success_count = parse_result.success_count
        ctx.views.header.error_count = parse_result.error_count

        # Now we no longer write to ctx.views.header
        header_view: HeaderView = ctx.views.header
        total_count: int = header_view.success_count + header_view.error_count

        logger.debug(
            "Header extracted from lines %d to %d, found %d header lines (%d ok, %d with errors), "
            "header block:\n%s",
            s_excl + 1,
            e_excl + 1,
            total_count,
            header_view.success_count,
            header_view.error_count,
            header_view.block,
        )

        if header_view.error_count > 0:
            # At least one header fleid line errored
            reason = (
                f"Header markers present at line {s_excl + 1} and {e_excl + 1}, "
                f"total: {total_count}, "
                f"ok: {header_view.success_count}, errors: {header_view.error_count}, "
            )

            if header_view.success_count == 0:
                # All header lines in the header block are malformed
                ctx.status.header = HeaderStatus.MALFORMED_ALL_FIELDS
                ctx.warn(f"{reason} - header contains no valid header lines.")
                return
            else:
                # At least one remaining valid header line
                ctx.status.header = HeaderStatus.MALFORMED_SOME_FIELDS
                ctx.warn(f"{reason} - header contains valid and invalid header lines.")
                return

        if not header_view.mapping:
            ctx.status.header = HeaderStatus.EMPTY
            logger.info("Header markers present but no fields in '%s'", ctx.path)
            ctx.warn(f"Header markers present at line {s_excl + 1} and {e_excl + 1} but no fields.")
        else:
            ctx.status.header = HeaderStatus.DETECTED

        logger.debug(
            "File status: %s, resolve status: %s, content status: %s, header status: %s",
            ctx.status.fs.value,
            ctx.status.resolve.value,
            ctx.status.content.value,
            ctx.status.header.value,
        )
        logger.trace(
            "Existing header dict: %s",
            header_view.mapping,
        )

        return

    def hint(self, ctx: ProcessingContext) -> None:
        """Attach header detection hints (non-binding).

        Args:
            ctx (ProcessingContext): The processing context.
        """
        st: HeaderStatus = ctx.status.header

        # May proceed to next step (always):
        permitted_by_policy: bool | None = check_permitted_by_policy(ctx)
        if st == HeaderStatus.DETECTED:
            if permitted_by_policy is False:
                ctx.request_halt(reason="stopped by policy", at_step=self)
            pass  # detected; normal path
        elif st == HeaderStatus.MISSING:
            ctx.hint(
                axis=Axis.HEADER,
                code=KnownCode.HEADER_MISSING,
                cluster=Cluster.PENDING,
                message="no TopMark header detected",
            )
            if permitted_by_policy is False:
                ctx.request_halt(reason="stopped by policy", at_step=self)

        elif st == HeaderStatus.EMPTY:
            ctx.hint(
                axis=Axis.HEADER,
                code=KnownCode.HEADER_EMPTY,
                cluster=Cluster.PENDING,
                message="empty TopMark header",
            )
            if permitted_by_policy is False:
                ctx.request_halt(reason="stopped by policy", at_step=self)
        # May proceed to next step (policy):
        elif st == HeaderStatus.MALFORMED_ALL_FIELDS:
            ctx.hint(
                axis=Axis.HEADER,
                code=KnownCode.HEADER_MALFORMED,
                cluster=Cluster.BLOCKED_POLICY,
                message="some header fields malformed",
            )
        elif st == HeaderStatus.MALFORMED_SOME_FIELDS:
            ctx.hint(
                axis=Axis.HEADER,
                code=KnownCode.HEADER_MALFORMED,
                cluster=Cluster.BLOCKED_POLICY,
                message="all header fields malformed",
            )
        # Stop processing:
        elif st == HeaderStatus.MALFORMED:
            ctx.hint(
                axis=Axis.HEADER,
                code=KnownCode.HEADER_MALFORMED,
                cluster=Cluster.SKIPPED,
                message="malformed TopMark header",
                terminal=True,
            )
        elif st == HeaderStatus.PENDING:
            # scanner did not complete
            ctx.request_halt(reason=f"{self.__class__.__name__} did not set state.", at_step=self)
