# topmark:header:start
#
#   project      : TopMark
#   file         : test_base.py
#   file_relpath : tests/pipeline/steps/test_base.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Unit tests for the shared pipeline step lifecycle."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.helpers.pipeline import make_pipeline_context
from topmark.config.io.deserializers import mutable_config_from_defaults
from topmark.pipeline.hints import Axis
from topmark.pipeline.status import ComparisonStatus
from topmark.pipeline.steps.base import BaseStep

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.config.model import FrozenConfig
    from topmark.pipeline.context.model import ProcessingContext


class PendingComparisonStep(BaseStep):
    """Test step that runs but does not set its primary-axis status."""

    def __init__(self) -> None:
        super().__init__(
            name=self.__class__.__name__,
            primary_axis=Axis.COMPARISON,
            axes_written=(Axis.COMPARISON,),
        )

    def run(
        self,
        ctx: ProcessingContext,
    ) -> None:
        """Leave the comparison status pending."""
        del ctx


class GatedPendingComparisonStep(PendingComparisonStep):
    """Test step that should not run because its gate is closed."""

    def may_proceed(
        self,
        ctx: ProcessingContext,
    ) -> bool:
        """Prevent lifecycle pending-state protection from running."""
        del ctx
        return False

    def run(
        self,
        ctx: ProcessingContext,
    ) -> None:
        """Fail if the closed gate is ignored."""
        del ctx
        raise AssertionError("run() should not execute when may_proceed() is false")


class ChangedComparisonStep(PendingComparisonStep):
    """Test step that sets its primary-axis status."""

    def run(
        self,
        ctx: ProcessingContext,
    ) -> None:
        """Set a non-pending comparison status."""
        ctx.status.comparison = ComparisonStatus.CHANGED


class SpecificallyHaltedComparisonStep(PendingComparisonStep):
    """Test step that requests its own specific halt reason."""

    def run(
        self,
        ctx: ProcessingContext,
    ) -> None:
        """Request a specific halt while leaving comparison pending."""
        ctx.request_halt(reason="specific halt", at_step=self)


class LifecycleStep(BaseStep):
    """Instrumented step that records public lifecycle observations."""

    def __init__(
        self,
        *,
        gate_open: bool,
        primary_axis: Axis | None = Axis.COMPARISON,
        complete_primary_axis: bool = False,
    ) -> None:
        super().__init__(
            name=self.__class__.__name__,
            primary_axis=primary_axis,
            axes_written=(Axis.COMPARISON,),
        )
        self.gate_open = gate_open
        self.complete_primary_axis = complete_primary_axis
        self.calls: list[str] = []
        self.bookkeeping_seen_by_gate: list[tuple[int, bool]] = []
        self.halted_when_hint_started: list[bool] = []

    def may_proceed(
        self,
        ctx: ProcessingContext,
    ) -> bool:
        """Record that bookkeeping precedes the gate."""
        self.calls.append("may_proceed")
        self.bookkeeping_seen_by_gate.append((len(ctx.steps), ctx.steps[-1] is self))
        return self.gate_open

    def run(
        self,
        ctx: ProcessingContext,
    ) -> None:
        """Optionally complete the primary status while recording execution."""
        self.calls.append("run")
        if self.complete_primary_axis:
            ctx.status.comparison = ComparisonStatus.CHANGED

    def hint(
        self,
        ctx: ProcessingContext,
    ) -> None:
        """Record whether fallback halt processing already completed."""
        self.calls.append("hint")
        self.halted_when_hint_started.append(ctx.is_halted)


class RepairingHintStep(LifecycleStep):
    """Test step whose hint tries to repair an omitted state transition."""

    def hint(
        self,
        ctx: ProcessingContext,
    ) -> None:
        """Set the primary status only after observing lifecycle fallback state."""
        super().hint(ctx)
        ctx.status.comparison = ComparisonStatus.CHANGED


def _make_context(
    tmp_path: Path,
) -> ProcessingContext:
    """Create a default processing context for BaseStep tests."""
    cfg: FrozenConfig = mutable_config_from_defaults().freeze()
    return make_pipeline_context(tmp_path / "x.py", cfg)


def test_base_step_runs_normal_lifecycle_and_records_invocation_before_gate(
    tmp_path: Path,
) -> None:
    """An accepted gate should run, then hint, with one prior history entry."""
    ctx: ProcessingContext = _make_context(tmp_path)
    step = LifecycleStep(gate_open=True, complete_primary_axis=True)

    result: ProcessingContext = step(ctx)

    assert result is ctx
    assert step.calls == ["may_proceed", "run", "hint"]
    assert step.bookkeeping_seen_by_gate == [(1, True)]
    assert step.halted_when_hint_started == [False]
    assert ctx.steps == [step]


def test_base_step_runs_gated_lifecycle_without_running_step(
    tmp_path: Path,
) -> None:
    """A rejected gate should skip run but still apply fallback before hinting."""
    ctx: ProcessingContext = _make_context(tmp_path)
    step = LifecycleStep(gate_open=False)

    result: ProcessingContext = step(ctx)

    assert result is ctx
    assert step.calls == ["may_proceed", "hint"]
    assert step.bookkeeping_seen_by_gate == [(1, True)]
    assert step.halted_when_hint_started == [True]
    assert ctx.steps == [step]


def test_base_step_records_each_invocation_once_before_its_gate(
    tmp_path: Path,
) -> None:
    """Repeated gated invocations should each append one entry before gating."""
    ctx: ProcessingContext = _make_context(tmp_path)
    step = LifecycleStep(gate_open=False, primary_axis=None)

    step(ctx)
    step(ctx)

    assert step.bookkeeping_seen_by_gate == [(1, True), (2, True)]
    assert ctx.steps == [step, step]


def test_base_step_halts_when_running_step_leaves_primary_axis_pending(
    tmp_path: Path,
) -> None:
    """Request a lifecycle halt when a running step leaves its primary status pending."""
    ctx: ProcessingContext = _make_context(tmp_path)

    PendingComparisonStep()(ctx)

    assert ctx.status.comparison is ComparisonStatus.PENDING
    assert ctx.halt_state is not None
    assert ctx.halt_state.step_name == "PendingComparisonStep"
    assert ctx.halt_state.reason_code == "PendingComparisonStep did not set state."


def test_base_step_halts_when_gated_step_leaves_primary_axis_pending(
    tmp_path: Path,
) -> None:
    """Apply pending-state protection when a gate closes without an earlier halt."""
    ctx: ProcessingContext = _make_context(tmp_path)

    GatedPendingComparisonStep()(ctx)

    assert ctx.status.comparison is ComparisonStatus.PENDING
    assert ctx.halt_state is not None
    assert ctx.halt_state.step_name == "GatedPendingComparisonStep"
    assert ctx.halt_state.reason_code == "GatedPendingComparisonStep did not set state."


def test_base_step_does_not_halt_when_primary_axis_is_set(
    tmp_path: Path,
) -> None:
    """Do not halt when a running step sets its primary status."""
    ctx: ProcessingContext = _make_context(tmp_path)

    ChangedComparisonStep()(ctx)

    assert ctx.status.comparison is ComparisonStatus.CHANGED
    assert ctx.halt_state is None


def test_base_step_keeps_specific_halt_reason(
    tmp_path: Path,
) -> None:
    """Do not replace a step's explicit halt reason with lifecycle fallback text."""
    ctx: ProcessingContext = _make_context(tmp_path)

    SpecificallyHaltedComparisonStep()(ctx)

    assert ctx.status.comparison is ComparisonStatus.PENDING
    assert ctx.halt_state is not None
    assert ctx.halt_state.step_name == "SpecificallyHaltedComparisonStep"
    assert ctx.halt_state.reason_code == "specific halt"


def test_base_step_preserves_preexisting_halt_without_implicitly_gating_run(
    tmp_path: Path,
) -> None:
    """Fallback should keep an earlier halt even though the open gate still runs."""
    ctx: ProcessingContext = _make_context(tmp_path)
    owner = PendingComparisonStep()
    ctx.request_halt(reason="earlier halt", at_step=owner)
    step = LifecycleStep(gate_open=True)

    step(ctx)

    assert step.calls == ["may_proceed", "run", "hint"]
    assert ctx.halt_state is not None
    assert ctx.halt_state.step_name == "PendingComparisonStep"
    assert ctx.halt_state.reason_code == "earlier halt"


def test_base_step_establishes_pending_halt_before_hint_can_repair_status(
    tmp_path: Path,
) -> None:
    """A late hint transition should not undo the already established fallback halt."""
    ctx: ProcessingContext = _make_context(tmp_path)
    step = RepairingHintStep(gate_open=True)

    step(ctx)

    assert step.halted_when_hint_started == [True]
    assert ctx.status.comparison is ComparisonStatus.CHANGED
    assert ctx.halt_state is not None
    assert ctx.halt_state.reason_code == "RepairingHintStep did not set state."


def test_base_step_primary_axis_none_disables_pending_guard_for_full_lifecycle(
    tmp_path: Path,
) -> None:
    """A metadata-only step should run and hint without pending-state fallback."""
    ctx: ProcessingContext = _make_context(tmp_path)
    step = LifecycleStep(gate_open=True, primary_axis=None)

    step(ctx)

    assert step.calls == ["may_proceed", "run", "hint"]
    assert step.halted_when_hint_started == [False]
    assert ctx.status.comparison is ComparisonStatus.PENDING
    assert ctx.halt_state is None


def test_base_step_default_hooks_complete_public_lifecycle(
    tmp_path: Path,
) -> None:
    """Default hooks should form a coherent no-op lifecycle without a primary axis."""
    ctx: ProcessingContext = _make_context(tmp_path)
    step = BaseStep(name="BaseStep", primary_axis=None)

    result: ProcessingContext = step(ctx)

    assert result is ctx
    assert ctx.steps == [step]
    assert ctx.halt_state is None
