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
for staged migration toward durable post-run results.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from topmark.pipeline.context.policy import can_change
from topmark.pipeline.context.policy import check_permitted_by_policy
from topmark.pipeline.context.policy import effective_would_add_or_update
from topmark.pipeline.context.policy import effective_would_strip
from topmark.pipeline.context.policy import would_add_or_update
from topmark.pipeline.context.policy import would_change
from topmark.pipeline.context.policy import would_strip
from topmark.pipeline.context.status import StatusSnapshot
from topmark.utils.path import format_machine_path

if TYPE_CHECKING:
    from collections.abc import Mapping

    from topmark.diagnostic.model import FrozenDiagnosticLog
    from topmark.filetypes.model import FileType
    from topmark.filetypes.model import InsertCapability
    from topmark.pipeline.context.model import ProcessingContext
    from topmark.pipeline.hints import Hint


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
    def from_file_type(cls, file_type: FileType) -> FileTypeSnapshot:
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
class PreInsertCheckSnapshot:
    """Durable pre-insert advisory state captured from a context.

    Attributes:
        capability: Advisory insert capability value.
        reason: Optional human-readable reason for the advisory.
        origin: Optional producer of the advisory.
    """

    capability: InsertCapability
    reason: str | None
    origin: str | None

    def to_dict(self) -> dict[str, str | None]:
        """Return a JSON-friendly pre-insert advisory payload.

        Returns:
            Mapping with capability name, reason, and origin.
        """
        return {
            "capability": self.capability.name,
            "reason": self.reason,
            "origin": self.origin,
        }


@dataclass(frozen=True, kw_only=True, slots=True)
class OutcomeSnapshot:
    """Durable outcome-facing flags captured from a processing context.

    These flags mirror the current high-level outcome payload produced by
    `ProcessingContext.to_dict()` without retaining the mutable context itself.

    Attributes:
        would_change: Whether the context represents any pending or completed change,
            or `None` when the current status is not sufficient to decide.
        can_change: Whether the context can change according to current feasibility checks.
        permitted_by_policy: Whether policy permits the effective change, or `None`
            when there is no clear mutation intent yet.
        would_add_or_update: Whether check/update processing would add or update a header.
        effective_would_add_or_update: Policy-aware add/update result.
        would_strip: Whether strip processing would remove a header.
        effective_would_strip: Policy-aware strip result.
    """

    would_change: bool | None
    can_change: bool
    permitted_by_policy: bool | None
    would_add_or_update: bool
    effective_would_add_or_update: bool
    would_strip: bool
    effective_would_strip: bool

    @classmethod
    def from_context(cls, ctx: ProcessingContext) -> OutcomeSnapshot:
        """Create an outcome snapshot from a mutable processing context.

        Args:
            ctx: Source context to evaluate.

        Returns:
            Durable outcome-facing flag snapshot.
        """
        return cls(
            would_change=would_change(ctx),
            can_change=can_change(ctx),
            permitted_by_policy=check_permitted_by_policy(ctx),
            would_add_or_update=would_add_or_update(ctx),
            effective_would_add_or_update=effective_would_add_or_update(ctx),
            would_strip=would_strip(ctx),
            effective_would_strip=effective_would_strip(ctx),
        )

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-friendly outcome payload.

        Returns:
            Mapping matching the existing high-level outcome payload shape.
        """
        return {
            "would_change": self.would_change,
            "can_change": self.can_change,
            "permitted_by_policy": self.permitted_by_policy,
            "check": {
                "would_add_or_update": self.would_add_or_update,
                "effective_would_add_or_update": self.effective_would_add_or_update,
            },
            "strip": {
                "would_strip": self.would_strip,
                "effective_would_strip": self.effective_would_strip,
            },
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
    steps: tuple[str, ...]
    step_axes: tuple[StepAxesSnapshot, ...]
    status: StatusSnapshot
    diagnostics: FrozenDiagnosticLog
    diagnostic_counts: Mapping[str, int]
    hints: tuple[Hint, ...]
    pre_insert_check: PreInsertCheckSnapshot
    outcome: OutcomeSnapshot

    @classmethod
    def from_context(cls, ctx: ProcessingContext) -> ProcessingResult:
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
            pre_insert_check=PreInsertCheckSnapshot(
                capability=ctx.pre_insert_capability,
                reason=ctx.pre_insert_reason,
                origin=ctx.pre_insert_origin,
            ),
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


def reduce_processing_context(ctx: ProcessingContext) -> ProcessingResult:
    """Reduce a mutable processing context to a durable result snapshot.

    Args:
        ctx: Source mutable context.

    Returns:
        Detached durable result snapshot.
    """
    return ProcessingResult.from_context(ctx)
