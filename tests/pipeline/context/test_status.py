# topmark:header:start
#
#   project      : TopMark
#   file         : test_status.py
#   file_relpath : tests/pipeline/context/test_status.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Contract tests for mutable and durable pipeline status models."""

from __future__ import annotations

from dataclasses import fields
from typing import TYPE_CHECKING

import pytest

from topmark.pipeline.context.status import ProcessingStatus
from topmark.pipeline.context.status import StatusSnapshot
from topmark.pipeline.context.status import StepStatus
from topmark.pipeline.hints import Axis
from topmark.pipeline.status import ComparisonStatus
from topmark.pipeline.status import ContentStatus
from topmark.pipeline.status import FsStatus
from topmark.pipeline.status import GenerationStatus
from topmark.pipeline.status import HeaderStatus
from topmark.pipeline.status import PatchStatus
from topmark.pipeline.status import PlanStatus
from topmark.pipeline.status import RenderStatus
from topmark.pipeline.status import ResolveStatus
from topmark.pipeline.status import StripStatus
from topmark.pipeline.status import WriteStatus

if TYPE_CHECKING:
    from topmark.pipeline.context.status import AxisStatusPayload
    from topmark.pipeline.status import BaseStatus


PENDING_BY_AXIS: dict[Axis, BaseStatus] = {
    Axis.RESOLVE: ResolveStatus.PENDING,
    Axis.FS: FsStatus.PENDING,
    Axis.CONTENT: ContentStatus.PENDING,
    Axis.HEADER: HeaderStatus.PENDING,
    Axis.GENERATION: GenerationStatus.PENDING,
    Axis.RENDER: RenderStatus.PENDING,
    Axis.STRIP: StripStatus.PENDING,
    Axis.COMPARISON: ComparisonStatus.PENDING,
    Axis.PLAN: PlanStatus.PENDING,
    Axis.PATCH: PatchStatus.PENDING,
    Axis.WRITE: WriteStatus.PENDING,
}

NON_PENDING_BY_AXIS: dict[Axis, BaseStatus] = {
    Axis.RESOLVE: ResolveStatus.RESOLVED,
    Axis.FS: FsStatus.OK,
    Axis.CONTENT: ContentStatus.OK,
    Axis.HEADER: HeaderStatus.DETECTED,
    Axis.GENERATION: GenerationStatus.GENERATED,
    Axis.RENDER: RenderStatus.RENDERED,
    Axis.STRIP: StripStatus.READY,
    Axis.COMPARISON: ComparisonStatus.CHANGED,
    Axis.PLAN: PlanStatus.REPLACED,
    Axis.PATCH: PatchStatus.GENERATED,
    Axis.WRITE: WriteStatus.WRITTEN,
}


def _set_status_for_axis(
    status: ProcessingStatus,
    axis: Axis,
    value: BaseStatus,
) -> None:
    """Set one status axis using its stable machine-facing axis value."""
    setattr(status, axis.value, value)


def test_processing_status_defaults_align_with_all_pipeline_axes() -> None:
    """Fresh mutable status should expose one pending value for every axis."""
    status = ProcessingStatus()

    assert [item.name for item in fields(status)] == [axis.value for axis in Axis]
    assert {axis: status.get(axis) for axis in Axis} == PENDING_BY_AXIS


@pytest.mark.parametrize(
    ("axis", "expected"),
    list(NON_PENDING_BY_AXIS.items()),
)
def test_processing_status_get_returns_status_for_requested_axis(
    axis: Axis,
    expected: BaseStatus,
) -> None:
    """Typed axis lookup should return the value stored on that exact axis."""
    status = ProcessingStatus()
    _set_status_for_axis(status, axis, expected)

    assert status.get(axis) == expected


def test_status_snapshot_captures_detached_values() -> None:
    """A durable snapshot should not change when mutable status changes later."""
    status = ProcessingStatus(
        resolve=ResolveStatus.RESOLVED,
        fs=FsStatus.OK,
        header=HeaderStatus.DETECTED,
        comparison=ComparisonStatus.CHANGED,
        write=WriteStatus.WRITTEN,
    )

    snapshot: StatusSnapshot = StatusSnapshot.from_status(status)

    status.resolve = ResolveStatus.UNSUPPORTED
    status.fs = FsStatus.NOT_FOUND
    status.header = HeaderStatus.MALFORMED
    status.comparison = ComparisonStatus.UNCHANGED
    status.write = WriteStatus.FAILED

    assert snapshot.resolve == ResolveStatus.RESOLVED
    assert snapshot.fs == FsStatus.OK
    assert snapshot.header == HeaderStatus.DETECTED
    assert snapshot.comparison == ComparisonStatus.CHANGED
    assert snapshot.write == WriteStatus.WRITTEN


@pytest.mark.parametrize(
    ("axis", "expected"),
    list(NON_PENDING_BY_AXIS.items()),
)
def test_status_snapshot_get_returns_status_for_requested_axis(
    axis: Axis,
    expected: BaseStatus,
) -> None:
    """Snapshot axis lookup should mirror mutable status lookup."""
    status = ProcessingStatus()
    _set_status_for_axis(status, axis, expected)
    snapshot: StatusSnapshot = StatusSnapshot.from_status(status)

    assert snapshot.get(axis) == expected


@pytest.mark.parametrize("use_snapshot", [False, True])
def test_status_serialization_exposes_stable_axis_payloads(
    use_snapshot: bool,
) -> None:
    """Mutable and durable status models should emit the same machine payload."""
    mutable = ProcessingStatus(
        resolve=ResolveStatus.RESOLVED,
        fs=FsStatus.OK,
        content=ContentStatus.OK,
        header=HeaderStatus.DETECTED,
        generation=GenerationStatus.GENERATED,
        render=RenderStatus.RENDERED,
        strip=StripStatus.READY,
        comparison=ComparisonStatus.CHANGED,
        plan=PlanStatus.REPLACED,
        patch=PatchStatus.GENERATED,
        write=WriteStatus.WRITTEN,
    )
    status: ProcessingStatus | StatusSnapshot = (
        StatusSnapshot.from_status(mutable) if use_snapshot else mutable
    )

    payload: dict[str, AxisStatusPayload] = status.to_dict()

    assert list(payload) == [axis.value for axis in Axis]
    assert payload == {
        axis.value: {
            "axis": axis.value,
            "name": NON_PENDING_BY_AXIS[axis].name,
            "label": NON_PENDING_BY_AXIS[axis].value,
        }
        for axis in Axis
    }


def test_processing_status_reset_restores_every_axis_to_pending() -> None:
    """Reset should restore all mutable axes without replacing the object."""
    status = ProcessingStatus()

    for axis, value in NON_PENDING_BY_AXIS.items():
        _set_status_for_axis(status, axis, value)

    original_identity: int = id(status)

    status.reset()

    assert id(status) == original_identity
    assert {axis: status.get(axis) for axis in Axis} == PENDING_BY_AXIS


@pytest.mark.parametrize(
    ("write_status", "expected"),
    [
        (WriteStatus.PENDING, False),
        (WriteStatus.WRITTEN, True),
        (WriteStatus.SKIPPED, True),
        (WriteStatus.FAILED, True),
    ],
)
def test_write_outcome_detection_matches_write_axis_state(
    write_status: WriteStatus,
    expected: bool,
) -> None:
    """Any completed write-axis state should count as a write outcome."""
    mutable = ProcessingStatus(write=write_status)
    snapshot: StatusSnapshot = StatusSnapshot.from_status(mutable)

    assert mutable.has_write_outcome() is expected
    assert snapshot.has_write_outcome() is expected


def test_step_status_preserves_step_name_and_typed_status() -> None:
    """Step diagnostics should retain their public name and coarse status."""
    step_status = StepStatus(
        step="ReaderStep",
        status=ContentStatus.OK,
    )

    assert step_status.step == "ReaderStep"
    assert step_status.status == ContentStatus.OK
