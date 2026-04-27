# topmark:header:start
#
#   project      : TopMark
#   file         : prober.py
#   file_relpath : src/topmark/pipeline/steps/prober.py
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

from topmark.core.logging import get_logger
from topmark.pipeline.hints import Axis
from topmark.pipeline.status import ResolveStatus
from topmark.pipeline.steps.base import BaseStep
from topmark.registry.registry import Registry
from topmark.resolution.filetypes import probe_resolution_for_path
from topmark.resolution.probe import ResolutionProbeStatus

if TYPE_CHECKING:
    from topmark.core.logging import TopmarkLogger
    from topmark.filetypes.model import FileType
    from topmark.pipeline.context.model import ProcessingContext
    from topmark.processors.base import HeaderProcessor
    from topmark.resolution.probe import ResolutionProbeResult

logger: TopmarkLogger = get_logger(__name__)


class ProberStep(BaseStep):
    """Resolve file type and processor with probe diagnostics.

    This step is intended for the probe pipeline. It records the full
    resolution explanation on `ctx.resolution_probe` while also mirroring the
    effective resolution outcome onto the normal resolve axis.

    Axes written:
      - resolve

    Sets:
      - `ctx.resolution_probe`
      - `ctx.file_type`
      - `ctx.header_processor`
      - `ctx.status.resolve`
    """

    def __init__(self) -> None:
        super().__init__(
            name=self.__class__.__name__,
            primary_axis=Axis.RESOLVE,
            axes_written=(Axis.RESOLVE,),
        )

    def may_proceed(self, ctx: ProcessingContext) -> bool:
        """Return True because probing is the first and only probe step.

        Args:
            ctx: The processing context for the current file.

        Returns:
            True.
        """
        return True

    def run(self, ctx: ProcessingContext) -> None:
        """Resolve and store probe-visible diagnostic details.

        Args:
            ctx: Processing context representing the file being probed.
        """
        ctx.status.resolve = ResolveStatus.PENDING

        probe: ResolutionProbeResult = probe_resolution_for_path(
            ctx.path,
            include_file_types=ctx.config.include_file_types or None,
            exclude_file_types=ctx.config.exclude_file_types or None,
        )
        ctx.resolution_probe = probe

        if probe.selected_file_type is None:
            ctx.status.resolve = ResolveStatus.UNSUPPORTED
            reason: str = "No file type associated with this file."
            ctx.diagnostics.add_info(reason)
            ctx.request_halt(reason=reason, at_step=self)
            return

        file_type: FileType | None = Registry.get_filetype(probe.selected_file_type.qualified_key)
        if file_type is not None:
            ctx.file_type = file_type

        if probe.status == ResolutionProbeStatus.NO_PROCESSOR:
            ctx.status.resolve = ResolveStatus.TYPE_RESOLVED_NO_PROCESSOR_REGISTERED
            reason = (
                f"No header processor registered for file type "
                f"'{probe.selected_file_type.local_key}'."
            )
            ctx.diagnostics.add_info(reason)
            ctx.request_halt(reason=reason, at_step=self)
            return

        if probe.selected_processor is None:
            ctx.status.resolve = ResolveStatus.TYPE_RESOLVED_NO_PROCESSOR_REGISTERED
            reason = (
                f"No header processor registered for file type "
                f"'{probe.selected_file_type.local_key}'."
            )
            ctx.diagnostics.add_info(reason)
            ctx.request_halt(reason=reason, at_step=self)
            return

        processor: HeaderProcessor | None = Registry.resolve_processor(
            probe.selected_file_type.qualified_key
        )
        if processor is None:
            ctx.status.resolve = ResolveStatus.TYPE_RESOLVED_NO_PROCESSOR_REGISTERED
            reason = (
                f"No header processor registered for file type "
                f"'{probe.selected_file_type.local_key}'."
            )
            ctx.diagnostics.add_info(reason)
            ctx.request_halt(reason=reason, at_step=self)
            return

        ctx.header_processor = processor

        if file_type is not None and file_type.skip_processing:
            ctx.status.resolve = ResolveStatus.TYPE_RESOLVED_HEADERS_UNSUPPORTED
            reason = (
                f"File type '{file_type.local_key}' "
                f"(namespace: {file_type.namespace}) recognized; "
                "headers are not supported for this format."
            )
            ctx.diagnostics.add_info(reason)
            ctx.request_halt(reason=reason, at_step=self)
            return

        ctx.status.resolve = ResolveStatus.RESOLVED
        ctx.request_halt(reason="Resolution probe completed.", at_step=self)

    def hint(self, ctx: ProcessingContext) -> None:
        """Advise about probe resolution outcome.

        Args:
            ctx: The processing context.
        """
        from topmark.pipeline.steps.resolver import ResolverStep

        ResolverStep().hint(ctx)
