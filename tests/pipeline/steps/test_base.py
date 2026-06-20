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


def _make_context(
    tmp_path: Path,
) -> ProcessingContext:
    """Create a default processing context for BaseStep tests."""
    cfg: FrozenConfig = mutable_config_from_defaults().freeze()
    return make_pipeline_context(tmp_path / "x.py", cfg)


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


def test_base_step_default_run_is_noop(
    tmp_path: Path,
) -> None:
    """Default run hook is intentionally a no-op for lifecycle subclasses."""
    ctx: ProcessingContext = _make_context(tmp_path)
    step = BaseStep(name="BaseStep", primary_axis=None)

    step.run(ctx)

    assert ctx.halt_state is None
