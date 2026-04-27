# topmark:header:start
#
#   project      : TopMark
#   file         : prober.py
#   file_relpath : src/topmark/pipeline/steps/prober.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Probe file type and processor resolution.

Runs the shared resolution probe and applies the same effective resolution
mapping as `ResolverStep`, then halts after successful probing because the probe
pipeline is intentionally resolution-only.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.pipeline.hints import Axis
from topmark.pipeline.status import ResolveStatus
from topmark.pipeline.steps.base import BaseStep
from topmark.pipeline.steps.resolver import apply_probe_resolution_to_context

if TYPE_CHECKING:
    from topmark.pipeline.context.model import ProcessingContext


class ProberStep(BaseStep):
    """Run resolution probing and stop the probe pipeline.

    This step is intended for the probe pipeline. It records the full resolution
    explanation on `ctx.resolution_probe`, mirrors the effective resolution
    outcome onto the normal resolve axis, and halts after successful resolution.

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
        apply_probe_resolution_to_context(ctx=ctx, step=self)
        if ctx.status.resolve == ResolveStatus.RESOLVED:
            ctx.request_halt(reason="Resolution probe completed.", at_step=self)

    def hint(self, ctx: ProcessingContext) -> None:
        """Advise about probe resolution outcome.

        Args:
            ctx: The processing context.
        """
        return
