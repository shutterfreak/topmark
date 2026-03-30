# topmark:header:start
#
#   project      : TopMark
#   file         : resolver.py
#   file_relpath : src/topmark/pipeline/steps/resolver.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Resolve file type and select header processor.

Determines `ctx.file_type` from name/content signals and attaches a registered
`HeaderProcessor` if available. Sets `ctx.status.resolve` accordingly.

Sets:
  - `ResolveStatus` → {RESOLVED, TYPE_RESOLVED_HEADERS_UNSUPPORTED,
                       TYPE_RESOLVED_NO_PROCESSOR_REGISTERED, UNSUPPORTED}
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.constants import VALUE_NOT_SET
from topmark.core.logging import get_logger
from topmark.pipeline.hints import Axis
from topmark.pipeline.hints import Cluster
from topmark.pipeline.hints import KnownCode
from topmark.pipeline.status import ResolveStatus
from topmark.pipeline.steps.base import BaseStep
from topmark.processors.base import HeaderProcessor
from topmark.resolution.filetypes import ResolvedBinding
from topmark.resolution.filetypes import resolve_binding_for_path

if TYPE_CHECKING:
    from topmark.core.logging import TopmarkLogger
    from topmark.filetypes.model import FileType
    from topmark.pipeline.context.model import ProcessingContext
    from topmark.processors.base import HeaderProcessor

logger: TopmarkLogger = get_logger(__name__)


class ResolverStep(BaseStep):
    """Resolve file type and attach a header processor (no I/O).

    This step evaluates name rules (extensions, filenames, patterns) and, if
    allowed by the file type's content gate, optional content probes to select
    the best matching `FileType`. Multiple candidates may match a path; the
    shared resolver applies a deterministic precedence and tie-break policy and
    returns at most one effective winner.

    Axes written:
      - resolve

    Sets:
      - ResolveStatus: {PENDING, RESOLVED, TYPE_RESOLVED_HEADERS_UNSUPPORTED,
                        TYPE_RESOLVED_NO_PROCESSOR_REGISTERED, UNSUPPORTED}
    """

    def __init__(self) -> None:
        super().__init__(
            name=self.__class__.__name__,
            primary_axis=Axis.RESOLVE,
            axes_written=(Axis.RESOLVE,),
        )

    def may_proceed(self, ctx: ProcessingContext) -> bool:
        """Return True (resolver is the first step and always runs).

        Args:
            ctx: The processing context for the current file.

        Returns:
            True if processing can proceed to the build step, False otherwise.
        """
        return True

    def run(self, ctx: ProcessingContext) -> None:
        """Resolve and assign the file type and header processor for the file.

        Updates these fields on the context when successful: `ctx.file_type`,
        `ctx.header_processor`, and `ctx.status.resolve`. On failure it appends a
        human-readable diagnostic and sets an appropriate resolve status.

        Args:
            ctx: Processing context representing the file being handled.

        Side effects:
            Sets `ctx.file_type`, `ctx.header_processor`, and `ctx.status.resolve`.
            Appends human-readable diagnostics when resolution fails or is partial.
        """
        ctx.status.resolve = ResolveStatus.PENDING

        logger.debug(
            "Resolve start: file='%s', fs status='%s', type=%s, processor=%s",
            ctx.path,
            ctx.status.fs.value,
            ctx.file_type.local_key if ctx.file_type else VALUE_NOT_SET,
            (ctx.header_processor.__class__.__name__ if ctx.header_processor else VALUE_NOT_SET),
        )

        resolved: ResolvedBinding = resolve_binding_for_path(
            ctx.path,
            include_file_types=ctx.config.include_file_types or None,
            exclude_file_types=ctx.config.exclude_file_types or None,
        )
        file_type: FileType | None = resolved.file_type
        processor: HeaderProcessor | None = resolved.processor

        if file_type is not None:
            ctx.file_type = file_type
            logger.debug("File '%s' resolved to type: %s", ctx.path, file_type.local_key)

            if file_type.skip_processing:
                logger.info(
                    "Skipping header processing for '%s' "
                    "(file type '%s' marked skip_processing=True)",
                    ctx.path,
                    file_type.local_key,
                )
                ctx.status.resolve = ResolveStatus.TYPE_RESOLVED_HEADERS_UNSUPPORTED
                reason: str = (
                    f"File type '{file_type.local_key}' "
                    f"(namespace: {file_type.namespace}) recognized; "
                    "headers are not supported for this format."
                )
                ctx.diagnostics.add_info(reason)
                ctx.request_halt(reason=reason, at_step=self)
                return

            if processor is None:
                logger.info(
                    "No header processor registered for file type '%s' (file '%s')",
                    file_type.local_key,
                    ctx.path,
                )
                ctx.status.resolve = ResolveStatus.TYPE_RESOLVED_NO_PROCESSOR_REGISTERED
                reason = f"No header processor registered for file type '{file_type.local_key}'."
                ctx.diagnostics.add_info(reason)
                ctx.request_halt(reason=reason, at_step=self)
                return

            # Success: attach the processor and mark the file as resolved
            ctx.header_processor = processor
            ctx.status.resolve = ResolveStatus.RESOLVED
            logger.debug(
                "Resolve success: file='%s' type='%s' processor=%s",
                ctx.path,
                file_type.local_key,
                processor.__class__.__name__,
            )
            return

        # No FileType matched
        logger.info("Unsupported file type for '%s' (no matcher)", ctx.path)
        ctx.status.resolve = ResolveStatus.UNSUPPORTED
        reason = "No file type associated with this file."
        ctx.diagnostics.add_info(reason)
        ctx.request_halt(reason=reason, at_step=self)
        return

    def hint(self, ctx: ProcessingContext) -> None:
        """Advise about resolution outcome (non-binding).

        Args:
            ctx: The processing context.
        """
        st: ResolveStatus = ctx.status.resolve

        # May proceed to next step:
        if st == ResolveStatus.RESOLVED:
            # Implies file_type and header_processor are defined
            pass  # healthy, no hint
        # Stop processing:
        elif st == ResolveStatus.TYPE_RESOLVED_NO_PROCESSOR_REGISTERED:
            ctx.hint(
                axis=Axis.RESOLVE,
                code=KnownCode.DISCOVERY_NO_PROCESSOR,
                cluster=Cluster.SKIPPED,
                message="no header processor registered",
                terminal=True,
            )
        elif st == ResolveStatus.TYPE_RESOLVED_HEADERS_UNSUPPORTED:
            ctx.hint(
                axis=Axis.RESOLVE,
                code=KnownCode.DISCOVERY_UNSUPPORTED,
                cluster=Cluster.SKIPPED,
                message="headers not supported for this type",
                terminal=True,
            )
        elif st == ResolveStatus.UNSUPPORTED:
            ctx.hint(
                axis=Axis.RESOLVE,
                code=KnownCode.DISCOVERY_UNSUPPORTED,
                cluster=Cluster.SKIPPED,
                message="file type is not supported",
                terminal=True,
            )
        elif st == ResolveStatus.PENDING:
            # resolver did not complete
            ctx.request_halt(reason=f"{self.__class__.__name__} did not set state.", at_step=self)
