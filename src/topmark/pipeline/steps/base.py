# topmark:header:start
#
#   project      : TopMark
#   file         : base.py
#   file_relpath : src/topmark/pipeline/steps/base.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Base class for class-based pipeline steps.

The engine and CLI invoke steps as *callables*. `BaseStep` implements
the common lifecycle:

    ctx = step(ctx)  # internally: may_proceed → run? → hint

Design goals
------------
- Single place for per-step bookkeeping (invocation counts, tracing hooks).
- Clear separation of concerns: step gating, mutation, advisory hints.
- Zero impact on final classification: the outcome is derived elsewhere.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from topmark.config.logging import get_logger

if TYPE_CHECKING:
    from topmark.config.logging import TopmarkLogger
    from topmark.pipeline.context.model import ProcessingContext
    from topmark.pipeline.hints import Axis

logger: TopmarkLogger = get_logger(__name__)


@dataclass
class BaseStep:
    """Reusable foundation for pipeline steps.

    Subclass this to implement a concrete step by overriding ``may_proceed()``,
    ``run()``, and optionally ``hint()``. Do not override ``__call__`` unless
    you need custom lifecycle behavior.

    Attributes:
        name (str): Fully qualified, stable step identifier for logs/tracing.
        primary_axis (Axis | None): The axis this step “represents” in summaries
        axes_written (tuple[Axis, ...]): Status axes this step is allowed to write (e.g. ("fs",)).
    """

    name: str
    primary_axis: Axis | None  # new: axis this step “represents” in summaries
    axes_written: tuple[Axis, ...] = ()

    def __call__(self, ctx: "ProcessingContext") -> "ProcessingContext":
        """Invoke the step lifecycle: gate → run (if allowed) → hint.

        This method centralizes per-step bookkeeping (e.g., invocation counts).
        Steps should not log their own lifecycle start/finish unless they add
        additional, step-specific details.

        Args:
            ctx (ProcessingContext): The mutable processing context for the current file.

        Returns:
             ProcessingContext: The same context instance after mutation/hints.
        """
        # unified bookkeeping
        # ctx.steps[self.name] = ctx.steps.get(self.name, 0) + 1
        ctx.steps.append(self)
        logger.info("BaseStep: Pipeline status before may_proceed(): : %s", ctx.steps)

        if self.may_proceed(ctx):
            logger.info("BaseStep:   Pipeline step %s - running", self.name)
            self.run(ctx)
            # Check flow status
            if ctx.flow.halt is True:
                logger.info(
                    "BaseStep: ⚠️ Pipeline halted by %s: %s", ctx.flow.at_step, ctx.flow.reason
                )
                # still call hint() for consistent diagnostics
                self.hint(ctx)
                return ctx

        else:
            logger.info("BaseStep: ⚠️ Pipeline step %s may not proceed", self.name)

        self.hint(ctx)
        return ctx

    def may_proceed(self, ctx: "ProcessingContext") -> bool:
        """Return whether the step should run given the current context.

        Default: ``True`` (always run). Override in subclasses to respect
        pipeline gates.

        Args:
            ctx (ProcessingContext): The mutable processing context.

        Returns:
            bool: True to run ``run()``, False to skip.
        """
        return True

    def run(self, ctx: "ProcessingContext") -> None:
        """Perform the step's primary work, mutating ``ctx`` in place.

        Subclasses must implement this method and only write to declared axes.

        Args:
            ctx (ProcessingContext): The mutable processing context.
        """
        pass

    def hint(self, ctx: "ProcessingContext") -> None:
        """Attach non-binding hints/telemetry to ``ctx`` (optional).

        This method should never influence the final outcome directly.

        Args:
            ctx (ProcessingContext): The mutable processing context.
        """
        pass
