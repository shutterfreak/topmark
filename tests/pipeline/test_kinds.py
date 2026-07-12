# topmark:header:start
#
#   project      : TopMark
#   file         : test_kinds.py
#   file_relpath : tests/pipeline/test_kinds.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Contract tests for shared pipeline-family identifiers."""

from __future__ import annotations

from typing import get_args

from topmark.pipeline.kinds import PipelineKindLiteral


def _accept_pipeline_kind(kind: PipelineKindLiteral) -> PipelineKindLiteral:
    """Return a statically validated pipeline kind for contract assertions."""
    return kind


def test_pipeline_kind_literal_exposes_stable_family_vocabulary() -> None:
    """The shared runtime vocabulary should remain probe, check, and strip."""
    assert get_args(PipelineKindLiteral) == ("probe", "check", "strip")


def test_pipeline_kind_literal_accepts_each_supported_family() -> None:
    """Every declared family should satisfy the public type contract."""
    assert tuple(_accept_pipeline_kind(kind) for kind in ("probe", "check", "strip")) == (
        "probe",
        "check",
        "strip",
    )
