# topmark:header:start
#
#   project      : TopMark
#   file         : test_pipelines.py
#   file_relpath : tests/pipeline/test_pipelines.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Pipeline tests."""

from __future__ import annotations

import pytest

from topmark.pipeline.pipelines import CHECK_APPLY_PIPELINE
from topmark.pipeline.pipelines import CHECK_PATCH_PIPELINE
from topmark.pipeline.pipelines import CHECK_SUMMMARY_PIPELINE
from topmark.pipeline.pipelines import PIPELINE_DEFINITIONS
from topmark.pipeline.pipelines import PROBE_PIPELINE
from topmark.pipeline.pipelines import STRIP_APPLY_PIPELINE
from topmark.pipeline.pipelines import STRIP_PATCH_PIPELINE
from topmark.pipeline.pipelines import STRIP_PIPELINE
from topmark.pipeline.pipelines import Pipeline
from topmark.pipeline.pipelines import PipelineDefinition
from topmark.pipeline.pipelines import PipelineSelection
from topmark.pipeline.pipelines import select_pipeline


@pytest.mark.parametrize(
    ("pipeline", "expected_name", "expected_family", "expected_steps"),
    [
        (Pipeline.PROBE, "probe", "probe", PROBE_PIPELINE),
        (Pipeline.CHECK, "check", "check", CHECK_SUMMMARY_PIPELINE),
        (Pipeline.CHECK_PATCH, "check-patch", "check", CHECK_PATCH_PIPELINE),
        (Pipeline.CHECK_APPLY, "check-apply", "check", CHECK_APPLY_PIPELINE),
        (Pipeline.STRIP, "strip", "strip", STRIP_PIPELINE),
        (Pipeline.STRIP_PATCH, "strip-patch", "strip", STRIP_PATCH_PIPELINE),
        (Pipeline.STRIP_APPLY, "strip-apply", "strip", STRIP_APPLY_PIPELINE),
    ],
)
def test_pipeline_definition_metadata(
    pipeline: Pipeline,
    expected_name: str,
    expected_family: str,
    expected_steps: object,
) -> None:
    """Pipeline enum members expose their registered executable definitions."""
    definition: PipelineDefinition = pipeline.definition

    assert PIPELINE_DEFINITIONS[pipeline] is definition
    assert definition.name == expected_name
    assert definition.family == expected_family
    assert definition.steps is expected_steps
    assert pipeline.steps is expected_steps
    assert pipeline.family == expected_family


@pytest.mark.parametrize(
    ("pipeline", "mutates", "emits_patch"),
    [
        (Pipeline.PROBE, False, False),
        (Pipeline.CHECK, False, False),
        (Pipeline.CHECK_PATCH, False, True),
        (Pipeline.CHECK_APPLY, True, False),
        (Pipeline.STRIP, False, False),
        (Pipeline.STRIP_PATCH, False, True),
        (Pipeline.STRIP_APPLY, True, False),
    ],
)
def test_pipeline_capability_flags(
    pipeline: Pipeline,
    *,
    mutates: bool,
    emits_patch: bool,
) -> None:
    """Pipeline capability flags describe selected side effects and outputs."""
    assert pipeline.definition.mutates is mutates
    assert pipeline.definition.emits_patch is emits_patch
    assert pipeline.mutates is mutates
    assert pipeline.emits_patch is emits_patch


@pytest.mark.parametrize(
    ("apply", "diff", "expected"),
    [
        (False, False, Pipeline.CHECK),
        (False, True, Pipeline.CHECK_PATCH),
        (True, False, Pipeline.CHECK_APPLY),
    ],
)
def test_select_pipeline_for_check_variants(
    *,
    apply: bool,
    diff: bool,
    expected: Pipeline,
) -> None:
    """Check selection maps apply/diff flags to the expected catalogue variant."""
    selection: PipelineSelection = select_pipeline(
        "check",
        apply=apply,
        diff=diff,
    )

    assert selection.kind == "check"
    assert selection.apply is apply
    assert selection.diff is diff
    assert selection.definition is expected.definition
    assert selection.steps is expected.steps


@pytest.mark.parametrize(
    ("apply", "diff", "expected"),
    [
        (False, False, Pipeline.STRIP),
        (False, True, Pipeline.STRIP_PATCH),
        (True, False, Pipeline.STRIP_APPLY),
    ],
)
def test_select_pipeline_for_strip_variants(
    *,
    apply: bool,
    diff: bool,
    expected: Pipeline,
) -> None:
    """Strip selection maps apply/diff flags to the expected catalogue variant."""
    selection: PipelineSelection = select_pipeline(
        "strip",
        apply=apply,
        diff=diff,
    )

    assert selection.kind == "strip"
    assert selection.apply is apply
    assert selection.diff is diff
    assert selection.definition is expected.definition
    assert selection.steps is expected.steps


@pytest.mark.parametrize(
    ("apply", "diff"), [(False, False), (False, True), (True, False), (True, True)]
)
def test_select_pipeline_for_probe_ignores_variant_flags(*, apply: bool, diff: bool) -> None:
    """Probe always selects the read-only probe pipeline."""
    selection: PipelineSelection = select_pipeline(
        "probe",
        apply=apply,
        diff=diff,
    )

    assert selection.kind == "probe"
    assert selection.apply is apply
    assert selection.diff is diff
    assert selection.definition is Pipeline.PROBE.definition
    assert selection.steps is PROBE_PIPELINE


def test_pipeline_selection_accepts_familyless_internal_definition() -> None:
    """Family-less definitions support no-op test pipelines without catalogue leaks."""
    definition = PipelineDefinition(
        name="test-noop",
        family=None,
        steps=(),
    )

    selection = PipelineSelection(
        kind="check",
        apply=False,
        diff=False,
        definition=definition,
    )

    assert selection.definition is definition
    assert selection.steps == ()


def test_pipeline_selection_rejects_mismatched_family() -> None:
    """Selections must not pair one command family with another family definition."""
    with pytest.raises(ValueError, match="family does not match selection kind"):
        PipelineSelection(
            kind="check",
            apply=False,
            diff=False,
            definition=Pipeline.STRIP.definition,
        )


def test_select_pipeline_rejects_unknown_kind() -> None:
    """Selection fails defensively for invalid runtime pipeline families."""
    with pytest.raises(RuntimeError, match="Invalid pipeline kind"):
        select_pipeline("unknown", apply=False, diff=False)  # pyright: ignore[reportArgumentType]
