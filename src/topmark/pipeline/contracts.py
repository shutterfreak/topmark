# topmark:header:start
#
#   project      : TopMark
#   file         : contracts.py
#   file_relpath : src/topmark/pipeline/contracts.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Type contracts for pipeline steps (engine-facing).

This module defines the minimal protocol that all pipeline steps must implement.
Steps are instantiated objects that are *callable*; the engine invokes them as
`step(ctx)` where `ctx` is a `ProcessingContext`.

Lifecycle
---------
1) The runner calls ``step.may_proceed(ctx)`` to gate execution.
2) If allowed, it calls ``step.run(ctx)`` (which mutates ``ctx`` in place).
3) Regardless, it calls ``step.hint(ctx)`` so a step can attach non-binding
   reason/telemetry hints (diagnostics). Final outcome classification is handled
   centrally, not by steps.

Attributes:
----------
name : str
    Fully qualified name used for tracing/telemetry.
axes_written : tuple[str, ...]
    Declares which status axes this step is allowed to set (e.g. ("fs", "content")).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from .context import ProcessingContext
    from .hints import Axis


class Step(Protocol):
    """Protocol for a single pipeline step.

    A step is a callable object that mutates a `ProcessingContext` and
    declares which status axes it is responsible for. Implementations typically
    subclass [`topmark.pipeline.steps.base.BaseStep`][].
    """

    name: str
    axes_written: tuple[Axis, ...]  # e.g. ("fs","content")

    def may_proceed(self, ctx: "ProcessingContext") -> bool:
        """Return whether the step should run given the current context.

        Args:
            ctx (ProcessingContext): The mutable processing context.

        Returns:
            bool: True if the step may run; False to skip this step.
        """
        ...

    def run(self, ctx: "ProcessingContext") -> None:
        """Execute the step, mutating the context in place.

        Implementations must **only** write to axes they own (as declared in
        ``axes_written``) and must not raise for expected control flow. I/O or
        parser errors should update the appropriate status axis and diagnostics.

        Args:
            ctx (ProcessingContext): The mutable processing context.
        """
        ...

    def hint(self, ctx: "ProcessingContext") -> None:
        """Attach non-binding hints/telemetry to the context.

        A step can add structured reason hints or metrics to aid later
        human-readable summaries. This must not change final outcome
        classification.

        Args:
            ctx (ProcessingContext): The mutable processing context.
        """
        ...

    def __call__(self, ctx: "ProcessingContext") -> "ProcessingContext":
        """Run the step lifecycle: gate → run (optional) → hint.

        Args:
            ctx (ProcessingContext): The mutable processing context.

        Returns:
            ProcessingContext: The same context object, for chaining.
        """
        ...
