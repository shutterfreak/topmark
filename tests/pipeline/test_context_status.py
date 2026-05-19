# topmark:header:start
#
#   project      : TopMark
#   file         : test_context_status.py
#   file_relpath : tests/pipeline/test_context_status.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Unit tests for pipeline context status helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from topmark.pipeline.context.status import ProcessingStatus
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


@pytest.mark.parametrize(
    ("axis", "status"),
    [
        (Axis.RESOLVE, ResolveStatus.RESOLVED),
        (Axis.FS, FsStatus.OK),
        (Axis.CONTENT, ContentStatus.OK),
        (Axis.HEADER, HeaderStatus.DETECTED),
        (Axis.GENERATION, GenerationStatus.GENERATED),
        (Axis.RENDER, RenderStatus.RENDERED),
        (Axis.STRIP, StripStatus.READY),
        (Axis.COMPARISON, ComparisonStatus.CHANGED),
        (Axis.PLAN, PlanStatus.PREVIEWED),
        (Axis.PATCH, PatchStatus.GENERATED),
        (Axis.WRITE, WriteStatus.WRITTEN),
    ],
)
def test_processing_status_get_returns_axis_status(
    axis: Axis,
    status: BaseStatus,
) -> None:
    """ProcessingStatus.get() should return the status for every pipeline axis."""
    processing_status = ProcessingStatus()
    setattr(processing_status, axis.value, status)

    assert processing_status.get(axis) is status


def test_processing_status_reset_restores_all_axes_to_pending() -> None:
    """reset() should restore every axis to its pending status."""
    status = ProcessingStatus(
        resolve=ResolveStatus.RESOLVED,
        fs=FsStatus.OK,
        content=ContentStatus.OK,
        header=HeaderStatus.DETECTED,
        generation=GenerationStatus.GENERATED,
        render=RenderStatus.RENDERED,
        strip=StripStatus.READY,
        comparison=ComparisonStatus.CHANGED,
        plan=PlanStatus.PREVIEWED,
        patch=PatchStatus.GENERATED,
        write=WriteStatus.WRITTEN,
    )

    status.reset()

    assert status.resolve is ResolveStatus.PENDING
    assert status.fs is FsStatus.PENDING
    assert status.content is ContentStatus.PENDING
    assert status.header is HeaderStatus.PENDING
    assert status.generation is GenerationStatus.PENDING
    assert status.render is RenderStatus.PENDING
    assert status.strip is StripStatus.PENDING
    assert status.comparison is ComparisonStatus.PENDING
    assert status.plan is PlanStatus.PENDING
    assert status.patch is PatchStatus.PENDING
    assert status.write is WriteStatus.PENDING


def test_processing_status_to_dict_serializes_every_axis() -> None:
    """to_dict() should emit stable machine-readable payloads for all axes."""
    status = ProcessingStatus(
        resolve=ResolveStatus.RESOLVED,
        fs=FsStatus.OK,
        content=ContentStatus.OK,
        header=HeaderStatus.MISSING,
        generation=GenerationStatus.NO_FIELDS,
        render=RenderStatus.RENDERED,
        strip=StripStatus.NOT_NEEDED,
        comparison=ComparisonStatus.UNCHANGED,
        plan=PlanStatus.SKIPPED,
        patch=PatchStatus.SKIPPED,
        write=WriteStatus.SKIPPED,
    )

    payload: dict[str, AxisStatusPayload] = status.to_dict()

    assert set(payload) == {axis.value for axis in Axis}
    assert payload["resolve"] == {
        "axis": "resolve",
        "name": "RESOLVED",
        "label": ResolveStatus.RESOLVED.value,
    }
    assert payload["fs"] == {
        "axis": "fs",
        "name": "OK",
        "label": FsStatus.OK.value,
    }
    assert payload["content"] == {
        "axis": "content",
        "name": "OK",
        "label": ContentStatus.OK.value,
    }
    assert payload["header"] == {
        "axis": "header",
        "name": "MISSING",
        "label": HeaderStatus.MISSING.value,
    }
    assert payload["generation"] == {
        "axis": "generation",
        "name": "NO_FIELDS",
        "label": GenerationStatus.NO_FIELDS.value,
    }
    assert payload["render"] == {
        "axis": "render",
        "name": "RENDERED",
        "label": RenderStatus.RENDERED.value,
    }
    assert payload["strip"] == {
        "axis": "strip",
        "name": "NOT_NEEDED",
        "label": StripStatus.NOT_NEEDED.value,
    }
    assert payload["comparison"] == {
        "axis": "comparison",
        "name": "UNCHANGED",
        "label": ComparisonStatus.UNCHANGED.value,
    }
    assert payload["plan"] == {
        "axis": "plan",
        "name": "SKIPPED",
        "label": PlanStatus.SKIPPED.value,
    }
    assert payload["patch"] == {
        "axis": "patch",
        "name": "SKIPPED",
        "label": PatchStatus.SKIPPED.value,
    }
    assert payload["write"] == {
        "axis": "write",
        "name": "SKIPPED",
        "label": WriteStatus.SKIPPED.value,
    }


def test_processing_status_has_write_outcome_detects_non_pending_write() -> None:
    """has_write_outcome() should only depend on the write axis."""
    status = ProcessingStatus()

    assert status.has_write_outcome() is False

    status.write = WriteStatus.SKIPPED
    assert status.has_write_outcome() is True

    status.write = WriteStatus.FAILED
    assert status.has_write_outcome() is True

    status.write = WriteStatus.PENDING
    assert status.has_write_outcome() is False


def test_step_status_holds_step_name_and_status() -> None:
    """StepStatus should preserve the step name and coarse status object."""
    step_status = StepStatus(step="reader", status=FsStatus.OK)

    assert step_status.step == "reader"
    assert step_status.status is FsStatus.OK
