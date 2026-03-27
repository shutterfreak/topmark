# topmark:header:start
#
#   project      : TopMark
#   file         : protocols.py
#   file_relpath : src/topmark/pipeline/protocols.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Type contracts for pipeline steps (engine-facing).

This module defines the minimal protocol that all pipeline steps must implement.
Steps are instantiated objects that are *callable*; the engine invokes `step(ctx)` where `ctx` is
the pipeline context (typically `ProcessingContext`).

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

from typing import TYPE_CHECKING
from typing import Protocol
from typing import TypeAlias
from typing import TypeVar

if TYPE_CHECKING:
    from collections.abc import Sequence

    from topmark.pipeline.hints import Axis


Ctx = TypeVar("Ctx")


class Step(Protocol[Ctx]):
    """Protocol for a single pipeline step.

    A step is a callable object that mutates a `ProcessingContext` and
    declares which status axes it is responsible for. Implementations typically
    subclass [`topmark.pipeline.steps.base.BaseStep`][].

    Notes:
        In this context we're not type-checking step execution; we're keeping a log of step
        instances. The concrete type we care about elsewhere is `Step[ProcessingContext]`
        (in ProcessingContext.steps and pipeline declarations). Here, it's fine to say
        "step of any context".
    """

    name: str
    primary_axis: Axis | None
    axes_written: tuple[Axis, ...]

    def may_proceed(self, ctx: Ctx) -> bool:
        """Return whether the step should run given the current context.

        Args:
            ctx: The mutable processing context.

        Returns:
            True if the step may run; False to skip this step.
        """
        ...

    def run(self, ctx: Ctx) -> None:
        """Execute the step, mutating the context in place.

        Implementations must **only** write to axes they own (as declared in
        ``axes_written``) and must not raise for expected control flow. I/O or
        parser errors should update the appropriate status axis and diagnostics.

        Args:
            ctx: The mutable processing context.
        """
        ...

    def hint(self, ctx: Ctx) -> None:
        """Attach non-binding hints/telemetry to the context.

        A step can add structured reason hints or metrics to aid later
        human-readable summaries. This must not change final outcome
        classification.

        Args:
            ctx: The mutable processing context.
        """
        ...

    def __call__(self, ctx: Ctx) -> Ctx:
        """Run the step lifecycle: gate → run (optional) → hint.

        Args:
            ctx: The mutable processing context.

        Returns:
            The same context object, for chaining.
        """
        ...


AnyStep: TypeAlias = Step[object]


class StepContext(Protocol):
    """Minimum context surface required by the step lifecycle (BaseStep/runner)."""

    @property
    def steps(self) -> Sequence[AnyStep]:
        """Executed steps (context type not relevant here)."""
        ...

    def request_halt(self, reason: str, at_step: AnyStep) -> None:
        """Record an early halt requested by a step."""
        ...

    @property
    def is_halted(self) -> bool:
        """Return True if a step has requested an early halt for this file."""
        ...
