# topmark:header:start
#
#   project      : TopMark
#   file         : result.py
#   file_relpath : src/topmark/pipeline/result.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Durable result snapshots for completed TopMark pipeline contexts.

This module contains immutable value objects that capture the result-facing
portion of a mutable
[`ProcessingContext`][topmark.pipeline.context.model.ProcessingContext]. The
objects defined here are deliberately reduced: they keep durable information
such as path identity, statuses, diagnostics, hints, and outcome-facing flags,
but they do not retain volatile runtime state such as file views, processors,
configuration objects, policy registries, or flow-control objects.

The initial reducer is intentionally conservative. Existing runners, CLI code,
and public API adapters may continue to return and consume
`ProcessingContext`; this module provides the vocabulary and conversion seam
for staged migration toward durable post-run results. The batch handover helper
lives in [`topmark.pipeline.reduction`][topmark.pipeline.reduction].
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from typing_extensions import Self

from topmark.pipeline.context.status import StatusSnapshot
from topmark.pipeline.outcome_snapshot import OutcomeSnapshot
from topmark.pipeline.pre_insert_advisory import PreInsertAdvisorySnapshot
from topmark.utils.path import format_machine_path

if TYPE_CHECKING:
    from collections.abc import Mapping

    from topmark.diagnostic.model import FrozenDiagnosticLog
    from topmark.filetypes.model import FileType
    from topmark.pipeline.context.model import ProcessingContext
    from topmark.pipeline.hints import Hint
    from topmark.pipeline.kinds import PipelineKindLiteral
    from topmark.runtime.model import RunOptions


@dataclass(frozen=True, kw_only=True, slots=True)
class FileTypeSnapshot:
    """Durable file-type identity captured from a processing context.

    Attributes:
        qualified_key: Canonical qualified file-type key.
        description: Human-facing file-type description.
    """

    qualified_key: str
    description: str

    @classmethod
    def from_file_type(
        cls,
        file_type: FileType,
    ) -> Self:
        """Create a file-type snapshot from a resolved file type.

        Args:
            file_type: Resolved file type to snapshot.

        Returns:
            Durable file-type identity snapshot.
        """
        return cls(
            qualified_key=file_type.qualified_key,
            description=file_type.description,
        )

    def to_dict(self) -> dict[str, str]:
        """Return a JSON-friendly file-type payload.

        Returns:
            Mapping containing the qualified key and description.
        """
        return {
            "qualified_key": self.qualified_key,
            "description": self.description,
        }


@dataclass(frozen=True, kw_only=True, slots=True)
class StepAxesSnapshot:
    """Durable step-to-axes relationship captured from an executed step.

    Attributes:
        step: Executed step name.
        axes: Tuple of axis names the step declared it may write.
    """

    step: str
    axes: tuple[str, ...]


@dataclass(frozen=True, kw_only=True, slots=True)
class ExecutionModeSnapshot:
    """Durable invocation-mode facts captured from runtime options.

    `ExecutionModeSnapshot` intentionally stores only the execution facts that
    remain meaningful after reducing a mutable processing context. It does not
    retain the full `RunOptions` object because that object also carries
    runtime-only presentation, STDIN, and output-target configuration.

    Attributes:
        pipeline_kind: Pipeline family selected for the run (`check`, `strip`,
            or `probe`). `None` is reserved for non-pipeline helper contexts.
        apply_changes: Whether this run applied file mutations instead of
            previewing them.
    """

    pipeline_kind: PipelineKindLiteral | None
    apply_changes: bool

    @classmethod
    def from_run_options(
        cls,
        run_options: RunOptions,
    ) -> Self:
        """Create an execution-mode snapshot from runtime options.

        Args:
            run_options: Runtime options for one TopMark invocation.

        Returns:
            Reduced execution-mode metadata suitable for storing in a durable
            processing result.
        """
        return cls(
            pipeline_kind=run_options.pipeline_kind,
            apply_changes=bool(run_options.apply_changes),
        )

    def to_dict(self) -> dict[str, object]:
        """Return a machine-readable execution-mode payload.

        Returns:
            JSON-serializable mapping containing the reduced pipeline kind and
            apply-mode flag.
        """
        return {
            "apply_changes": self.apply_changes,
            "pipeline_kind": self.pipeline_kind,
        }


@dataclass(frozen=True, kw_only=True, slots=True)
class ProcessingResult:
    """Durable reduced outcome for one processed file.

    A `ProcessingResult` is an immutable snapshot of the result-facing state of
    a completed or partially completed
    [`ProcessingContext`][topmark.pipeline.context.model.ProcessingContext]. It
    intentionally does not retain runtime-only fields such as configuration,
    policy registries, processors, mutable views, or flow-control objects.

    Attributes:
        path: Processing path for the file.
        file_type: Durable resolved file-type identity, if any.
        execution_mode: The execution-mode snapshot for this context.
        steps: Names of executed steps in execution order.
        step_axes: Axes declared by each executed step.
        status: Immutable per-axis status snapshot.
        diagnostics: Immutable diagnostic log snapshot.
        diagnostic_counts: Diagnostic counts by severity.
        hints: Hints captured in insertion order.
        pre_insert_check: Durable pre-insert advisory snapshot.
        outcome: Durable high-level outcome flag snapshot.
    """

    path: Path
    file_type: FileTypeSnapshot | None
    execution_mode: ExecutionModeSnapshot
    steps: tuple[str, ...]
    step_axes: tuple[StepAxesSnapshot, ...]
    status: StatusSnapshot
    diagnostics: FrozenDiagnosticLog
    diagnostic_counts: Mapping[str, int]
    hints: tuple[Hint, ...]
    pre_insert_check: PreInsertAdvisorySnapshot
    outcome: OutcomeSnapshot

    @classmethod
    def from_context(
        cls,
        ctx: ProcessingContext,
    ) -> Self:
        """Reduce a mutable processing context to a durable result snapshot.

        Args:
            ctx: Source mutable context.

        Returns:
            Detached durable result snapshot.
        """
        diagnostics: FrozenDiagnosticLog = ctx.diagnostics.freeze()
        return cls(
            path=Path(ctx.path),
            file_type=(
                FileTypeSnapshot.from_file_type(ctx.file_type)
                if ctx.file_type is not None
                else None
            ),
            execution_mode=ExecutionModeSnapshot.from_run_options(ctx.run_options),
            steps=tuple(step.name for step in ctx.steps),
            step_axes=tuple(
                StepAxesSnapshot(
                    step=step.name,
                    axes=tuple(axis.value for axis in step.axes_written),
                )
                for step in ctx.steps
            ),
            status=StatusSnapshot.from_status(ctx.status),
            diagnostics=diagnostics,
            diagnostic_counts=diagnostics.to_dict(),
            hints=tuple(ctx.diagnostic_hints),
            pre_insert_check=PreInsertAdvisorySnapshot.from_context(ctx),
            outcome=OutcomeSnapshot.from_context(ctx),
        )

    @property
    def step_axes_dict(self) -> dict[str, list[str]]:
        """Return step axes in the current machine-output mapping shape.

        Returns:
            Mapping from step name to a list of axis names.
        """
        return {item.step: list(item.axes) for item in self.step_axes}

    def to_dict(self) -> dict[str, object]:
        """Return a machine-readable representation of this durable result.

        The shape intentionally mirrors the result-facing subset of
        `ProcessingContext.to_dict()` while omitting volatile view details.

        Returns:
            JSON-serializable mapping describing the durable processing result.
        """
        return {
            "path": format_machine_path(self.path),
            "file_type": self.file_type.to_dict() if self.file_type is not None else None,
            "execution_mode": self.execution_mode.to_dict(),
            "steps": list(self.steps),
            "step_axes": self.step_axes_dict,
            "status": self.status.to_dict(),
            "diagnostics": [
                {"level": diagnostic.level.value, "message": diagnostic.message}
                for diagnostic in self.diagnostics
            ],
            "diagnostic_counts": self.diagnostic_counts,
            "hints": [
                {
                    "axis": hint.axis.value,
                    "code": hint.code,
                    "message": hint.message,
                    "detail": hint.detail,
                    "cluster": hint.cluster,
                    "terminal": hint.terminal,
                    "reason": hint.reason,
                    "meta": hint.meta,
                }
                for hint in self.hints
            ],
            "pre_insert_check": self.pre_insert_check.to_dict(),
            "outcome": self.outcome.to_dict(),
        }
