# topmark:header:start
#
#   project      : TopMark
#   file         : test_outcomes.py
#   file_relpath : tests/pipeline/test_outcomes.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Unit tests for pipeline outcome bucketing."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.helpers.pipeline import make_pipeline_context
from topmark.config.io.deserializers import mutable_config_from_defaults
from topmark.config.policy import HeaderMutationMode
from topmark.core.outcomes import NO_REASON_PROVIDED
from topmark.core.outcomes import Outcome
from topmark.pipeline.context.model import ProcessingContext
from topmark.pipeline.outcomes import OutcomeReasonCount
from topmark.pipeline.outcomes import ResultActionIntent
from topmark.pipeline.outcomes import ResultBucket
from topmark.pipeline.outcomes import classify_outcome
from topmark.pipeline.outcomes import collect_outcome_reason_counts
from topmark.pipeline.outcomes import determine_result_action_intent
from topmark.pipeline.outcomes import map_bucket
from topmark.pipeline.result import ProcessingResult
from topmark.pipeline.status import ComparisonStatus
from topmark.pipeline.status import ContentStatus
from topmark.pipeline.status import FsStatus
from topmark.pipeline.status import GenerationStatus
from topmark.pipeline.status import HeaderStatus
from topmark.pipeline.status import PlanStatus
from topmark.pipeline.status import ResolveStatus
from topmark.pipeline.status import StripStatus
from topmark.pipeline.status import WriteStatus
from topmark.runtime.model import RunOptions

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.config.model import MutableConfig
    from topmark.pipeline.context.model import ProcessingContext
    from topmark.pipeline.kinds import PipelineKindLiteral


def _make_context(
    tmp_path: Path,
    *,
    apply_changes: bool = False,
    pipeline_kind: PipelineKindLiteral = "check",
    mutation_mode: HeaderMutationMode | None = None,
) -> ProcessingContext:
    """Create a baseline context past resolve/fs/content feasibility checks."""
    mutable: MutableConfig = mutable_config_from_defaults()
    if mutation_mode is not None:
        mutable.policy.header_mutation_mode = mutation_mode

    ctx: ProcessingContext = make_pipeline_context(tmp_path / "case.py", mutable.freeze())
    ctx.run_options = RunOptions(
        pipeline_kind=pipeline_kind,
        apply_changes=apply_changes,
    )
    ctx.status.resolve = ResolveStatus.RESOLVED
    ctx.status.fs = FsStatus.OK
    ctx.status.content = ContentStatus.OK
    return ctx


def test_result_bucket_repr_uses_fallback_reason() -> None:
    """Bucket repr should use the shared fallback reason when reason is absent."""
    assert repr(ResultBucket(outcome=Outcome.PENDING)) == (f"pending: {NO_REASON_PROVIDED}")


@pytest.mark.parametrize(
    ("header", "strip", "expected"),
    [
        (HeaderStatus.PENDING, StripStatus.READY, ResultActionIntent.STRIP),
        (HeaderStatus.MISSING, StripStatus.PENDING, ResultActionIntent.INSERT),
        (HeaderStatus.DETECTED, StripStatus.PENDING, ResultActionIntent.UPDATE),
        (HeaderStatus.PENDING, StripStatus.PENDING, ResultActionIntent.NONE),
    ],
)
def test_determine_result_action_intent_from_status_axes(
    tmp_path: Path,
    header: HeaderStatus,
    strip: StripStatus,
    expected: ResultActionIntent,
) -> None:
    """Intent inference should depend on status axes, not pipeline names."""
    ctx: ProcessingContext = _make_context(tmp_path)
    ctx.status.header = header
    ctx.status.strip = strip

    assert determine_result_action_intent(ctx) is expected


@pytest.mark.parametrize(
    "fs_status",
    [
        FsStatus.NOT_FOUND,
        FsStatus.NO_READ_PERMISSION,
        FsStatus.UNREADABLE,
    ],
)
def test_map_bucket_prioritizes_read_filesystem_errors(
    tmp_path: Path,
    fs_status: FsStatus,
) -> None:
    """Read filesystem failures should win even before resolution completes."""
    ctx: ProcessingContext = _make_context(tmp_path)
    ctx.status.fs = fs_status
    ctx.status.resolve = ResolveStatus.PENDING

    bucket: ResultBucket = map_bucket(ctx, apply=False)

    assert bucket.outcome is Outcome.ERROR
    assert bucket.reason == fs_status.value


def test_map_bucket_write_permission_is_error_only_in_apply_mode(tmp_path: Path) -> None:
    """Write permission failures should be errors for apply-mode writes."""
    ctx: ProcessingContext = _make_context(tmp_path, apply_changes=True)
    ctx.status.fs = FsStatus.NO_WRITE_PERMISSION

    bucket: ResultBucket = map_bucket(ctx, apply=True)

    assert bucket.outcome is Outcome.ERROR
    assert bucket.reason == FsStatus.NO_WRITE_PERMISSION.value


@pytest.mark.parametrize(
    "resolve_status",
    [
        ResolveStatus.PENDING,
        ResolveStatus.UNSUPPORTED,
    ],
)
def test_map_bucket_skips_unresolved_contexts(
    tmp_path: Path,
    resolve_status: ResolveStatus,
) -> None:
    """Unresolved inputs should be skipped after filesystem hard errors."""
    ctx: ProcessingContext = _make_context(tmp_path)
    ctx.status.resolve = resolve_status

    bucket: ResultBucket = map_bucket(ctx, apply=False)

    assert bucket.outcome is Outcome.SKIPPED
    assert bucket.reason == resolve_status.value


@pytest.mark.parametrize(
    "content_status",
    [
        ContentStatus.PENDING,
        ContentStatus.UNSUPPORTED,
        ContentStatus.UNREADABLE,
    ],
)
def test_map_bucket_skips_fatal_content_states(
    tmp_path: Path,
    content_status: ContentStatus,
) -> None:
    """Fatal content states should map to skipped outcomes."""
    ctx: ProcessingContext = _make_context(tmp_path)
    ctx.status.content = content_status

    bucket: ResultBucket = map_bucket(ctx, apply=False)

    assert bucket.outcome is Outcome.SKIPPED
    assert bucket.reason == content_status.value


@pytest.mark.parametrize(
    "content_status",
    [
        ContentStatus.SKIPPED_MIXED_LINE_ENDINGS,
        ContentStatus.SKIPPED_POLICY_BOM_BEFORE_SHEBANG,
        ContentStatus.SKIPPED_REFLOW,
    ],
)
def test_map_bucket_skips_soft_content_policy_states(
    tmp_path: Path,
    content_status: ContentStatus,
) -> None:
    """Policy-aware soft content skips should preserve their specific reason."""
    ctx: ProcessingContext = _make_context(tmp_path)
    ctx.status.content = content_status

    bucket: ResultBucket = map_bucket(ctx, apply=False)

    assert bucket.outcome is Outcome.SKIPPED
    assert bucket.reason == content_status.value


def test_map_bucket_treats_empty_insert_as_unchanged_by_default(tmp_path: Path) -> None:
    """Empty-like insert candidates should be unchanged unless policy allows them."""
    ctx: ProcessingContext = _make_context(tmp_path)
    ctx.status.fs = FsStatus.EMPTY
    ctx.status.header = HeaderStatus.MISSING

    bucket: ResultBucket = map_bucket(ctx, apply=False)

    assert bucket.outcome is Outcome.UNCHANGED
    assert bucket.reason == "empty-like file (policy)"


@pytest.mark.parametrize(
    ("strip_status", "expected"),
    [
        (StripStatus.READY, Outcome.WOULD_STRIP),
        (StripStatus.NOT_NEEDED, Outcome.UNCHANGED),
        (StripStatus.FAILED, Outcome.ERROR),
    ],
)
def test_map_bucket_maps_strip_axis_in_dry_run(
    tmp_path: Path,
    strip_status: StripStatus,
    expected: Outcome,
) -> None:
    """Strip-axis states should not depend on comparison status."""
    ctx: ProcessingContext = _make_context(
        tmp_path,
        pipeline_kind="strip",
    )
    ctx.status.strip = strip_status

    bucket: ResultBucket = map_bucket(ctx, apply=False)

    assert bucket.outcome is expected
    assert bucket.reason == strip_status.value


def test_map_bucket_maps_strip_ready_to_stripped_in_apply_mode(tmp_path: Path) -> None:
    """Apply-mode strip-ready state should classify as stripped."""
    ctx: ProcessingContext = _make_context(
        tmp_path,
        apply_changes=True,
        pipeline_kind="strip",
    )
    ctx.status.strip = StripStatus.READY

    bucket: ResultBucket = map_bucket(ctx, apply=True)

    assert bucket.outcome is Outcome.STRIPPED
    assert bucket.reason == StripStatus.READY.value


def test_map_bucket_malformed_header_is_error(tmp_path: Path) -> None:
    """Malformed headers should be errors before policy/change mapping."""
    ctx: ProcessingContext = _make_context(tmp_path)
    ctx.status.header = HeaderStatus.MALFORMED

    bucket: ResultBucket = map_bucket(ctx, apply=False)

    assert bucket.outcome is Outcome.ERROR
    assert bucket.reason == HeaderStatus.MALFORMED.value


def test_map_bucket_policy_veto_skips_update_in_add_only_mode(tmp_path: Path) -> None:
    """Add-only policy should skip update attempts for existing headers."""
    ctx: ProcessingContext = _make_context(tmp_path, mutation_mode=HeaderMutationMode.ADD_ONLY)
    ctx.status.header = HeaderStatus.DETECTED
    ctx.status.comparison = ComparisonStatus.CHANGED

    bucket: ResultBucket = map_bucket(ctx, apply=False)

    assert bucket.outcome is Outcome.SKIPPED
    assert bucket.reason == "skipped by policy"


def test_map_bucket_comparison_unchanged_wins_after_policy(tmp_path: Path) -> None:
    """Unchanged comparison should map to the stable up-to-date reason."""
    ctx: ProcessingContext = _make_context(tmp_path)
    ctx.status.header = HeaderStatus.DETECTED
    ctx.status.comparison = ComparisonStatus.UNCHANGED

    bucket: ResultBucket = map_bucket(ctx, apply=False)

    assert bucket.outcome is Outcome.UNCHANGED
    assert bucket.reason == "up-to-date"


@pytest.mark.parametrize(
    ("header_status", "expected_dry", "expected_apply"),
    [
        (HeaderStatus.MISSING, Outcome.WOULD_INSERT, Outcome.INSERTED),
        (HeaderStatus.DETECTED, Outcome.WOULD_UPDATE, Outcome.UPDATED),
    ],
)
def test_map_bucket_changed_comparison_maps_header_intent(
    tmp_path: Path,
    header_status: HeaderStatus,
    expected_dry: Outcome,
    expected_apply: Outcome,
) -> None:
    """Changed comparison should map insert/update intent across dry/apply modes."""
    dry: ProcessingContext = _make_context(tmp_path)
    dry.status.header = header_status
    dry.status.comparison = ComparisonStatus.CHANGED

    applied: ProcessingContext = _make_context(tmp_path, apply_changes=True)
    applied.status.header = header_status
    applied.status.comparison = ComparisonStatus.CHANGED
    applied.status.write = WriteStatus.WRITTEN

    assert map_bucket(dry, apply=False).outcome is expected_dry
    assert map_bucket(applied, apply=True).outcome is expected_apply


def test_map_bucket_write_failure_overrides_change(tmp_path: Path) -> None:
    """Writer failure should classify as an error regardless of detected change."""
    ctx: ProcessingContext = _make_context(tmp_path, apply_changes=True)
    ctx.status.header = HeaderStatus.MISSING
    ctx.status.comparison = ComparisonStatus.CHANGED
    ctx.status.write = WriteStatus.FAILED

    bucket: ResultBucket = map_bucket(ctx, apply=True)

    assert bucket.outcome is Outcome.ERROR
    assert bucket.reason == WriteStatus.FAILED.value


def test_map_bucket_dry_run_plan_preview_maps_generic_pending_intent(
    tmp_path: Path,
) -> None:
    """Plan previews without concrete intent should fall back to would-change."""
    ctx: ProcessingContext = _make_context(tmp_path)
    ctx.status.plan = PlanStatus.PREVIEWED

    bucket: ResultBucket = map_bucket(ctx, apply=False)

    assert bucket.outcome is Outcome.WOULD_CHANGE
    assert bucket.reason == (f"{HeaderStatus.PENDING.value}, {ComparisonStatus.PENDING.value}")


def test_map_bucket_no_fields_is_unchanged(tmp_path: Path) -> None:
    """No generated fields should classify as unchanged."""
    ctx: ProcessingContext = _make_context(tmp_path)
    ctx.status.generation = GenerationStatus.NO_FIELDS

    bucket: ResultBucket = map_bucket(ctx, apply=False)

    assert bucket.outcome is Outcome.UNCHANGED
    assert bucket.reason == GenerationStatus.NO_FIELDS.value


@pytest.mark.parametrize(
    "plan_status",
    [
        PlanStatus.SKIPPED,
        PlanStatus.FAILED,
    ],
)
def test_map_bucket_plan_skip_or_failure_is_skipped(
    tmp_path: Path,
    plan_status: PlanStatus,
) -> None:
    """Skipped or failed plan states should classify as skipped."""
    ctx: ProcessingContext = _make_context(tmp_path)
    ctx.status.plan = plan_status

    bucket: ResultBucket = map_bucket(ctx, apply=False)

    assert bucket.outcome is Outcome.SKIPPED
    assert bucket.reason == plan_status.value


def test_map_bucket_falls_back_to_pending(tmp_path: Path) -> None:
    """Unclassified feasible-but-incomplete contexts should remain pending."""
    ctx: ProcessingContext = _make_context(tmp_path)

    bucket: ResultBucket = map_bucket(ctx, apply=False)

    assert bucket.outcome is Outcome.PENDING
    assert bucket.reason == NO_REASON_PROVIDED


def test_map_bucket_supports_processing_result_snapshot(tmp_path: Path) -> None:
    """ProcessingResult should classify like the source ProcessingContext."""
    ctx: ProcessingContext = _make_context(tmp_path)
    ctx.status.header = HeaderStatus.MISSING
    ctx.status.comparison = ComparisonStatus.CHANGED
    result: ProcessingResult = ProcessingResult.from_context(ctx)

    context_bucket: ResultBucket = map_bucket(ctx, apply=False)
    result_bucket: ResultBucket = map_bucket(result, apply=False)

    assert result_bucket == context_bucket


def test_map_bucket_supports_processing_result_empty_policy_snapshot(
    tmp_path: Path,
) -> None:
    """ProcessingResult should preserve empty-for-insert policy classification."""
    ctx: ProcessingContext = _make_context(tmp_path)
    ctx.status.fs = FsStatus.EMPTY
    ctx.status.header = HeaderStatus.MISSING
    result: ProcessingResult = ProcessingResult.from_context(ctx)

    context_bucket: ResultBucket = map_bucket(ctx, apply=False)
    result_bucket: ResultBucket = map_bucket(result, apply=False)

    assert result_bucket == context_bucket


def test_map_bucket_supports_processing_result_policy_veto_snapshot(
    tmp_path: Path,
) -> None:
    """ProcessingResult should preserve policy-veto classification."""
    ctx: ProcessingContext = _make_context(
        tmp_path,
        mutation_mode=HeaderMutationMode.ADD_ONLY,
    )
    ctx.status.header = HeaderStatus.DETECTED
    ctx.status.comparison = ComparisonStatus.CHANGED
    result: ProcessingResult = ProcessingResult.from_context(ctx)

    context_bucket: ResultBucket = map_bucket(ctx, apply=False)
    result_bucket: ResultBucket = map_bucket(result, apply=False)

    assert result_bucket == context_bucket
    assert result_bucket.outcome is Outcome.SKIPPED
    assert result_bucket.reason == "skipped by policy"


def test_map_bucket_supports_processing_result_write_failure_snapshot(
    tmp_path: Path,
) -> None:
    """ProcessingResult should preserve apply-mode write failure classification."""
    ctx: ProcessingContext = _make_context(tmp_path, apply_changes=True)
    ctx.status.header = HeaderStatus.MISSING
    ctx.status.comparison = ComparisonStatus.CHANGED
    ctx.status.write = WriteStatus.FAILED
    result: ProcessingResult = ProcessingResult.from_context(ctx)

    context_bucket: ResultBucket = map_bucket(ctx, apply=True)
    result_bucket: ResultBucket = map_bucket(result, apply=True)

    assert result_bucket == context_bucket
    assert result_bucket.outcome is Outcome.ERROR
    assert result_bucket.reason == WriteStatus.FAILED.value


@pytest.mark.parametrize(
    ("apply", "expected_outcome"),
    [
        (False, Outcome.WOULD_INSERT),
        (True, Outcome.INSERTED),
    ],
)
def test_collect_outcome_reason_counts_uses_result_execution_mode(
    tmp_path: Path,
    apply: bool,
    expected_outcome: Outcome,
) -> None:
    """Apply-explicit summaries should work without runtime options."""
    ctx: ProcessingContext = _make_context(tmp_path, apply_changes=apply)
    ctx.status.header = HeaderStatus.MISSING
    ctx.status.comparison = ComparisonStatus.CHANGED
    ctx.status.write = WriteStatus.WRITTEN
    result: ProcessingResult = ProcessingResult.from_context(ctx)

    rows: list[OutcomeReasonCount] = collect_outcome_reason_counts(
        [result],
    )

    assert [(row.outcome, row.reason, row.count) for row in rows] == [
        (
            expected_outcome,
            f"{HeaderStatus.MISSING.value}, {ComparisonStatus.CHANGED.value}",
            1,
        )
    ]


def test_collect_outcome_reason_counts_groups_processing_results(
    tmp_path: Path,
) -> None:
    """Apply-explicit summaries should group multiple reduced results by bucket."""
    first_insert: ProcessingContext = _make_context(tmp_path, apply_changes=True)
    first_insert.status.header = HeaderStatus.MISSING
    first_insert.status.comparison = ComparisonStatus.CHANGED
    first_insert.status.write = WriteStatus.WRITTEN

    second_insert: ProcessingContext = _make_context(tmp_path, apply_changes=True)
    second_insert.status.header = HeaderStatus.MISSING
    second_insert.status.comparison = ComparisonStatus.CHANGED
    second_insert.status.write = WriteStatus.WRITTEN

    policy_veto: ProcessingContext = _make_context(
        tmp_path,
        mutation_mode=HeaderMutationMode.ADD_ONLY,
    )
    policy_veto.status.header = HeaderStatus.DETECTED
    policy_veto.status.comparison = ComparisonStatus.CHANGED

    rows: list[OutcomeReasonCount] = collect_outcome_reason_counts(
        [
            ProcessingResult.from_context(first_insert),
            ProcessingResult.from_context(second_insert),
            ProcessingResult.from_context(policy_veto),
        ],
    )

    assert [(row.outcome, row.reason, row.count) for row in rows] == [
        (Outcome.SKIPPED, "skipped by policy", 1),
        (
            Outcome.INSERTED,
            f"{HeaderStatus.MISSING.value}, {ComparisonStatus.CHANGED.value}",
            2,
        ),
    ]


def test_classify_outcome_returns_bucket_outcome(tmp_path: Path) -> None:
    """Outcome-only classifier should delegate to bucket classification."""
    ctx: ProcessingContext = _make_context(tmp_path)
    ctx.status.header = HeaderStatus.MISSING
    ctx.status.comparison = ComparisonStatus.CHANGED

    assert classify_outcome(ctx, apply=False) is Outcome.WOULD_INSERT


@pytest.mark.parametrize(
    ("generation", "plan", "apply", "expected_outcome"),
    [
        (GenerationStatus.NO_FIELDS, PlanStatus.PENDING, False, Outcome.UNCHANGED),
        (GenerationStatus.PENDING, PlanStatus.PREVIEWED, False, Outcome.WOULD_CHANGE),
        (GenerationStatus.PENDING, PlanStatus.SKIPPED, False, Outcome.SKIPPED),
        (GenerationStatus.PENDING, PlanStatus.FAILED, False, Outcome.SKIPPED),
    ],
)
def test_map_bucket_matches_processing_result_for_fallback_branches(
    tmp_path: Path,
    generation: GenerationStatus,
    plan: PlanStatus,
    apply: bool,
    expected_outcome: Outcome,
) -> None:
    """Ensure map_bucket matches processing result for fall-back branches."""
    ctx: ProcessingContext = _make_context(tmp_path)
    ctx.status.header = HeaderStatus.PENDING
    ctx.status.comparison = ComparisonStatus.PENDING
    ctx.status.generation = generation
    ctx.status.plan = plan

    context_bucket: ResultBucket = map_bucket(ctx, apply=apply)
    result_bucket: ResultBucket = map_bucket(ProcessingResult.from_context(ctx), apply=apply)

    assert result_bucket == context_bucket
    assert result_bucket.outcome is expected_outcome


def test_collect_outcome_reason_counts_groups_and_sorts(tmp_path: Path) -> None:
    """Summary counts should group result snapshots by outcome/reason."""
    skipped_resolve: ProcessingContext = _make_context(tmp_path)
    skipped_resolve.status.resolve = ResolveStatus.UNSUPPORTED

    skipped_content: ProcessingContext = _make_context(tmp_path)
    skipped_content.status.content = ContentStatus.UNSUPPORTED

    unchanged: ProcessingContext = _make_context(tmp_path)
    unchanged.status.header = HeaderStatus.DETECTED
    unchanged.status.comparison = ComparisonStatus.UNCHANGED

    rows: list[OutcomeReasonCount] = collect_outcome_reason_counts(
        [
            ProcessingResult.from_context(skipped_resolve),
            ProcessingResult.from_context(unchanged),
            ProcessingResult.from_context(skipped_content),
        ]
    )

    assert [(row.outcome, row.reason, row.count) for row in rows] == [
        (Outcome.SKIPPED, ContentStatus.UNSUPPORTED.value, 1),
        (Outcome.SKIPPED, ResolveStatus.UNSUPPORTED.value, 1),
        (Outcome.UNCHANGED, "up-to-date", 1),
    ]
