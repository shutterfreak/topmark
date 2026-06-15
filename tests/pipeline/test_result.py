# topmark:header:start
#
#   project      : TopMark
#   file         : test_result.py
#   file_relpath : tests/pipeline/test_result.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Unit tests for durable pipeline result reduction."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.helpers.pipeline import make_context_from_text
from topmark.config.io.deserializers import mutable_config_from_defaults
from topmark.core.typing_guards import is_mapping
from topmark.pipeline.hints import Axis
from topmark.pipeline.hints import KnownCode
from topmark.pipeline.result import ProcessingResult
from topmark.pipeline.status import HeaderStatus
from topmark.pipeline.status import ResolveStatus
from topmark.pipeline.status import WriteStatus
from topmark.runtime.model import RunOptions
from topmark.utils.path import format_machine_path

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.config.model import FrozenConfig
    from topmark.pipeline.context.model import ProcessingContext
    from topmark.pipeline.kinds import PipelineKindLiteral


def _make_result_context(
    tmp_path: Path,
    *,
    pipeline_kind: PipelineKindLiteral = "check",
    apply_changes: bool = False,
) -> ProcessingContext:
    """Create a small post-reader context suitable for result-reduction tests."""
    cfg: FrozenConfig = mutable_config_from_defaults().freeze()
    ctx: ProcessingContext = make_context_from_text(
        "print('hello')\n",
        cfg=cfg,
        path=tmp_path / "sample.py",
    )
    ctx.run_options = RunOptions(
        pipeline_kind=pipeline_kind,
        apply_changes=apply_changes,
    )
    return ctx


def test_processing_result_reduces_context_identity(
    tmp_path: Path,
) -> None:
    """ProcessingResult should capture durable identity fields from a context."""
    ctx: ProcessingContext = _make_result_context(tmp_path)
    assert ctx.file_type is not None

    ctx.status.header = HeaderStatus.MISSING
    ctx.hint(
        axis=Axis.HEADER,
        code=KnownCode.HEADER_MISSING,
        message="Header is missing",
    )

    result: ProcessingResult = ProcessingResult.from_context(ctx)

    assert result.path == ctx.path
    assert result.file_type is not None
    assert result.file_type.qualified_key == ctx.file_type.qualified_key
    assert result.file_type.description == ctx.file_type.description
    assert result.status.resolve is ResolveStatus.RESOLVED
    assert result.status.header is HeaderStatus.MISSING
    assert result.hints == tuple(ctx.diagnostic_hints)


def test_processing_result_snapshots_status(
    tmp_path: Path,
) -> None:
    """ProcessingResult should not retain mutable ProcessingStatus state."""
    ctx: ProcessingContext = _make_result_context(tmp_path)
    ctx.status.header = HeaderStatus.MISSING
    ctx.status.write = WriteStatus.WRITTEN

    result: ProcessingResult = ProcessingResult.from_context(ctx)

    ctx.status.header = HeaderStatus.PENDING
    ctx.status.write = WriteStatus.PENDING

    assert result.status.header is HeaderStatus.MISSING
    assert result.status.write is WriteStatus.WRITTEN


def test_processing_result_to_dict_excludes_runtime_views(
    tmp_path: Path,
) -> None:
    """ProcessingResult serialization should omit volatile runtime view state."""
    ctx: ProcessingContext = _make_result_context(tmp_path)

    payload: dict[str, object] = ProcessingResult.from_context(ctx).to_dict()

    assert "views" not in payload
    assert payload["path"] == format_machine_path(tmp_path / "sample.py")
    assert "status" in payload
    assert "diagnostics" in payload
    assert "diagnostic_counts" in payload
    assert "hints" in payload


def test_processing_result_to_dict_preserves_outcome_shape(
    tmp_path: Path,
) -> None:
    """ProcessingResult serialization should preserve the current outcome payload shape."""
    ctx: ProcessingContext = _make_result_context(tmp_path)

    payload: dict[str, object] = ProcessingResult.from_context(ctx).to_dict()
    outcome: object = payload["outcome"]

    assert is_mapping(outcome)
    assert set(outcome) == {
        "would_change",
        "can_change",
        "permitted_by_policy",
        "check",
        "strip",
    }
    assert is_mapping(outcome["check"])
    assert set(outcome["check"]) == {
        "would_add_or_update",
        "effective_would_add_or_update",
    }
    assert is_mapping(outcome["strip"])
    assert set(outcome["strip"]) == {
        "would_strip",
        "effective_would_strip",
    }


def test_processing_result_to_dict_preserves_execution_mode(
    tmp_path: Path,
) -> None:
    """ProcessingResult serialization should preserve durable execution mode."""
    ctx: ProcessingContext = _make_result_context(
        tmp_path,
        apply_changes=True,
    )

    result: ProcessingResult = ProcessingResult.from_context(ctx)
    payload: dict[str, object] = result.to_dict()
    execution_mode: object = payload["execution_mode"]

    assert result.execution_mode.pipeline_kind == "check"
    assert result.execution_mode.apply_changes is True
    assert result.execution_mode.to_dict() == {
        "pipeline_kind": "check",
        "apply_changes": True,
    }
    assert is_mapping(execution_mode)
    assert execution_mode == {
        "pipeline_kind": "check",
        "apply_changes": True,
    }
