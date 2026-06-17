# topmark:header:start
#
#   project      : TopMark
#   file         : outcomes.py
#   file_relpath : src/topmark/pipeline/outcomes.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Pure outcome bucketing and counting helpers used across frontends.

This module owns the presentation-free *bucketing* logic that maps a
[`ProcessingContext`][topmark.pipeline.context.model.ProcessingContext]
to a stable public outcome and an optional human-facing reason.

Design goals:
- Presentation-free: no ANSI styling, markdown, or CLI-only wording.
- Reusable across frontends: CLI, docs tooling, and the public API.
- Stable outcomes: bucketing produces shared
  [`Outcome`][topmark.core.outcomes.Outcome] values that are independent of the
  chosen frontend.
- Deterministic summaries: `(outcome, reason)` counting is stable and ordered
  using `OUTCOME_ORDER` defined in [topmark.core.outcomes][].

Outcome primitives live in [`topmark.core.outcomes`][topmark.core.outcomes]
rather than `topmark.api.types` so this pipeline layer does not import the API
package while classifying results.

Notes:
    Styling is layered on top in frontend modules such as
    [`topmark.presentation.shared.outcomes`][topmark.presentation.shared.outcomes],
    [`topmark.core.presentation`][topmark.core.presentation] and
    [`topmark.cli.presentation`][topmark.cli.presentation].
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING
from typing import Protocol

from topmark.core.logging import get_logger
from topmark.core.outcomes import NO_REASON_PROVIDED
from topmark.core.outcomes import OUTCOME_ORDER
from topmark.core.outcomes import Outcome
from topmark.pipeline.status import ComparisonStatus  # temporary
from topmark.pipeline.status import ContentStatus  # temporary
from topmark.pipeline.status import FsStatus  # temporary
from topmark.pipeline.status import GenerationStatus  # temporary
from topmark.pipeline.status import HeaderStatus  # temporary
from topmark.pipeline.status import PlanStatus  # temporary
from topmark.pipeline.status import ResolveStatus  # temporary
from topmark.pipeline.status import StripStatus  # temporary
from topmark.pipeline.status import WriteStatus  # temporary

if TYPE_CHECKING:
    from collections.abc import Iterable

    from topmark.core.logging import TopmarkLogger
    from topmark.pipeline.result import ProcessingResult


logger: TopmarkLogger = get_logger(__name__)


class SupportsOutcomeStatus(Protocol):
    """Minimum status surface required for outcome classification."""

    @property
    def resolve(self) -> ResolveStatus:
        """Resolution status used by the classifier."""
        ...

    @property
    def fs(self) -> FsStatus:
        """Filesystem status used by the classifier."""
        ...

    @property
    def content(self) -> ContentStatus:
        """Content status used by the classifier."""
        ...

    @property
    def header(self) -> HeaderStatus:
        """Header status used by the classifier."""
        ...

    @property
    def generation(self) -> GenerationStatus:
        """Generation status used by the classifier."""
        ...

    @property
    def strip(self) -> StripStatus:
        """Strip status used by the classifier."""
        ...

    @property
    def comparison(self) -> ComparisonStatus:
        """Comparison status used by the classifier."""
        ...

    @property
    def plan(self) -> PlanStatus:
        """Plan status used by the classifier."""
        ...

    @property
    def write(self) -> WriteStatus:
        """Write status used by the classifier."""
        ...


class SupportsOutcomeFlags(Protocol):
    """Minimum precomputed outcome-flag surface required for bucketing."""

    @property
    def would_change(self) -> bool | None:
        """Whether the context/result represents a pending or completed change."""
        ...

    @property
    def can_change(self) -> bool:
        """Whether the context/result can change according to feasibility checks."""
        ...

    @property
    def permitted_by_policy(self) -> bool | None:
        """Whether policy permits the effective change, when inferable."""
        ...

    @property
    def would_add_or_update(self) -> bool:
        """Whether check/update processing would add or update a header."""
        ...

    @property
    def effective_would_add_or_update(self) -> bool:
        """Policy-aware add/update result used by dry-run bucketing."""
        ...

    @property
    def would_strip(self) -> bool:
        """Whether strip processing would remove a header."""
        ...

    @property
    def effective_would_strip(self) -> bool:
        """Policy-aware strip result used by dry-run bucketing."""
        ...

    @property
    def empty_for_insert_unchanged_by_default(self) -> bool:
        """Whether empty-for-insert files default to unchanged under policy."""
        ...


class SupportsOutcomeClassification(Protocol):
    """Minimum durable surface required by outcome classification helpers."""

    @property
    def status(self) -> SupportsOutcomeStatus:
        """Per-axis status values used by the classifier."""
        ...

    @property
    def outcome(self) -> SupportsOutcomeFlags:
        """Precomputed policy-aware outcome flags used by the classifier."""
        ...


class ResultActionIntent(str, Enum):
    """Per-result action intent inferred from pipeline status.

    `ResultActionIntent` is a small internal classification used by
    `map_bucket()` to decide whether a detected change should be reported as an
    insert, update, strip, or a more generic change.

    This is intentionally derived from status axes rather than from the chosen
    pipeline name so that bucketing remains robust across pipeline variants.
    """

    STRIP = "strip"
    INSERT = "insert"
    UPDATE = "update"
    NONE = "none"  # insufficient information to infer a concrete action


def determine_result_action_intent(
    ctx: SupportsOutcomeClassification,
) -> ResultActionIntent:
    """Infer the per-result action intent from the current context.

    The inferred intent is used only for public bucketing. It is intentionally
    derived from status axes so that it still works when different pipeline
    variants omit certain steps (for example, strip-summary pipelines may not
    run the comparer).

    Inference rules:
    - `STRIP`: the strip axis is non-pending, meaning a strip-oriented pipeline ran.
    - `INSERT`: the header axis reports a missing header.
    - `UPDATE`: the header axis is decided (not `PENDING`) and not missing.
    - `NONE`: there is not yet enough information to infer a concrete action.

    Args:
        ctx: The processing context.

    Returns:
        The inferred bucketing action intent.
    """
    if ctx.status.strip != StripStatus.PENDING:
        return ResultActionIntent.STRIP
    if ctx.status.header == HeaderStatus.MISSING:
        return ResultActionIntent.INSERT
    if ctx.status.header != HeaderStatus.PENDING:
        return ResultActionIntent.UPDATE
    return ResultActionIntent.NONE


@dataclass(frozen=True, kw_only=True, slots=True)
class ResultBucket:
    """Outcome + optional human-facing reason used for bucketing.

    `ResultBucket` is the small value object returned by `map_bucket()`. It
    couples the stable public outcome with the reason text used in summaries.

    Attributes:
        outcome: The classified public outcome.
        reason: Optional human-facing reason used in summary output.
    """

    outcome: Outcome
    reason: str | None = None

    def __repr__(self) -> str:
        """Return a compact debug representation of the bucket."""
        return f"{self.outcome.value}: {self.reason or NO_REASON_PROVIDED}"


@dataclass(frozen=True, kw_only=True, slots=True)
class OutcomeReasonCount:
    """Count for a specific `(outcome, reason)` summary bucket.

    This value object is the canonical summary row used by human and machine
    output layers. It preserves both axes of classification:

    - `outcome`: the stable public `Outcome`
    - `reason`: the human-facing bucket reason used within that outcome

    Keeping both axes avoids collapsing multiple distinct reasons into a single
    per-outcome count in summary views.
    """

    outcome: Outcome
    reason: str
    count: int


def map_bucket(
    ctx: SupportsOutcomeClassification,
    *,
    apply: bool,
) -> ResultBucket:
    """Map a processing context to a public bucket (`Outcome` + reason).

    This logic is precedence-ordered: the first matching rule wins. The ordering matters because
    some axes may remain `PENDING` depending on the chosen pipeline (for example, `strip` pipelines
    may omit comparison).

    Precedence (high → low):
        1) Hard skips/errors (resolve/fs/content fatal states).
        2) Content-level soft skips (mixed newlines / BOM-before-shebang / reflow).
        3) Empty-file default compliance: empty files are `UNCHANGED` unless policy allows inserting
           headers into empty files.
        4) Strip intent mapping based on the strip axis (`READY`/`NOT_NEEDED`/`FAILED`). This must
           not depend on comparison.
        5) Malformed headers that TopMark cannot safely interpret.
        6) Policy veto (add-only / update-only).
        7) Comparison/write outcomes (for pipelines that ran compare and/or write).
        8) Dry-run previews and remaining fallbacks (`NO_FIELDS`, plan status, generic would-change
           cases).
        9) Pending fallback.

    Args:
        ctx: The per-file pipeline context.
        apply: Whether the run is in apply mode.

    Returns:
        Bucket containing public Outcome and a human label.
    """
    intent: ResultActionIntent = determine_result_action_intent(ctx)
    logger.trace("intent: %s; apply: %s; status: %s", intent.value, apply, ctx.status)

    def ret(
        *,
        debug_tag: str,
        outcome: Outcome,
        reason: str | None,
    ) -> ResultBucket:
        """Return a bucket while emitting a structured debug trace.

        The `debug_tag` is debug-only and is intended to make it easy to locate the matching
        precedence branch in logs.

        Args:
            debug_tag: Stable debug tag for the matching branch.
            outcome: Public outcome for CLI/API.
            reason: Human-facing bucket label.

        Returns:
            Constructed bucket.
        """
        logger.debug(
            "bucket[%s] intent='%s' apply='%s' outcome='%s' reason='%s'",
            debug_tag,
            intent.value,
            apply,
            outcome.value,
            reason or NO_REASON_PROVIDED,
        )
        return ResultBucket(outcome=outcome, reason=reason)

    # 1) Hard skips/errors (resolve/fs/content fatal states)

    # Filesystem failures can be discovered before file-type resolution, for example
    # synthetic contexts for explicit missing inputs. Classify these before resolve
    # status so they do not fall through as "resolve pending" skips.
    if ctx.status.fs in {
        FsStatus.NOT_FOUND,
        FsStatus.NO_READ_PERMISSION,
        FsStatus.UNREADABLE,
    }:
        return ret(
            debug_tag="error:fs-read",
            outcome=Outcome.ERROR,
            reason=ctx.status.fs.value,
        )
    if ctx.status.fs == FsStatus.HARD_LINK_DUPLICATE:
        return ret(
            debug_tag="skip:fs-hard-link-duplicate",
            outcome=Outcome.SKIPPED,
            reason=ctx.status.fs.value,
        )
    if ctx.status.resolve != ResolveStatus.RESOLVED:
        return ret(
            debug_tag="skip:resolve",
            outcome=Outcome.SKIPPED,
            reason=ctx.status.resolve.value,
        )
    if apply and ctx.status.fs == FsStatus.NO_WRITE_PERMISSION:
        return ret(
            debug_tag="error:fs-write",
            outcome=Outcome.ERROR,
            reason=ctx.status.fs.value,
        )
    if ctx.status.content in {
        ContentStatus.PENDING,
        ContentStatus.UNSUPPORTED,
        ContentStatus.UNREADABLE,
    }:
        return ret(
            debug_tag="skip:content",
            outcome=Outcome.SKIPPED,
            reason=ctx.status.content.value,
        )

    # 2) Content-level soft skips (policy may override)
    if ctx.status.content in {
        ContentStatus.SKIPPED_MIXED_LINE_ENDINGS,
        ContentStatus.SKIPPED_POLICY_BOM_BEFORE_SHEBANG,
        ContentStatus.SKIPPED_REFLOW,
    }:
        return ret(
            debug_tag="skip:content-soft",
            outcome=Outcome.SKIPPED,
            reason=ctx.status.content.value,
        )

    # 3) Empty-for-insert default compliance
    #
    # Files classified as "empty for insertion" are treated as compliant /
    # unchanged by default when policy does not allow inserting into that class.
    #
    # This covers true empty files as well as empty-like placeholders such as
    # BOM-only, newline-only, or other images covered by the configured
    # `EmptyInsertMode`.
    if ctx.outcome.empty_for_insert_unchanged_by_default:
        return ret(
            debug_tag="unchanged:empty-for-insert",
            outcome=Outcome.UNCHANGED,
            reason="empty-like file (policy)",
        )

    # 4) Strip mapping (strip pipelines may omit comparer; do not depend on comparison)
    if intent == ResultActionIntent.STRIP:
        if ctx.status.strip == StripStatus.READY:
            return ret(
                debug_tag="strip:ready",
                outcome=Outcome.STRIPPED if apply else Outcome.WOULD_STRIP,
                reason=ctx.status.strip.value,
            )
        if ctx.status.strip == StripStatus.NOT_NEEDED:
            return ret(
                debug_tag="strip:not-needed",
                outcome=Outcome.UNCHANGED,
                reason=ctx.status.strip.value,
            )
        if ctx.status.strip == StripStatus.FAILED:
            return ret(
                debug_tag="strip:failed",
                outcome=Outcome.ERROR,
                reason=ctx.status.strip.value,
            )

    # 5) Malformed header that TopMark cannot safely interpret
    if ctx.status.header == HeaderStatus.MALFORMED:
        return ret(
            debug_tag="error:header-malformed",
            outcome=Outcome.ERROR,
            reason=ctx.status.header.value,
        )

    # 6) Policy veto (add-only / update-only)
    # Policy veto is tri-state: False means forbidden; True/None both mean "not vetoed".
    permitted_by_policy: bool | None = ctx.outcome.permitted_by_policy
    if permitted_by_policy is False:
        return ret(
            debug_tag="skip:policy",
            outcome=Outcome.SKIPPED,
            reason="skipped by policy",
        )

    logger.debug("map_bucket: permitted_by_policy=%s", permitted_by_policy)

    header_lbl: str = ctx.status.header.value
    comparison_lbl: str = ctx.status.comparison.value
    strip_lbl: str = ctx.status.strip.value

    # Helper for constructing the most specific reason for a detected change.
    def changed_reason_for(current_intent: ResultActionIntent) -> str:
        """Return the most specific human-facing reason for a detected change."""
        if current_intent == ResultActionIntent.STRIP:
            return f"{header_lbl}, {strip_lbl}"
        return f"{header_lbl}, {comparison_lbl}"

    # 7) Comparison/write outcomes
    if ctx.status.comparison == ComparisonStatus.UNCHANGED:
        return ret(
            debug_tag="unchanged:up-to-date",
            outcome=Outcome.UNCHANGED,
            reason="up-to-date",
        )

    # Compute the Outcome value for a change (only meaningful when change is intended/detected).
    outcome_if_changed: Outcome
    if apply:
        if intent == ResultActionIntent.STRIP:
            outcome_if_changed = Outcome.STRIPPED
        elif intent == ResultActionIntent.INSERT:
            outcome_if_changed = Outcome.INSERTED
        elif intent == ResultActionIntent.UPDATE:
            outcome_if_changed = Outcome.UPDATED
        else:
            outcome_if_changed = Outcome.CHANGED
    else:
        if intent == ResultActionIntent.STRIP:
            outcome_if_changed = Outcome.WOULD_STRIP
        elif intent == ResultActionIntent.INSERT:
            outcome_if_changed = Outcome.WOULD_INSERT
        elif intent == ResultActionIntent.UPDATE:
            outcome_if_changed = Outcome.WOULD_UPDATE
        else:
            outcome_if_changed = Outcome.WOULD_CHANGE

    reason_if_changed: str = changed_reason_for(intent)
    logger.debug(
        "Outcome if changed: '%s', reason if changed: '%s'",
        outcome_if_changed.value,
        reason_if_changed,
    )

    # Apply path: the writer has the final word.
    if ctx.status.write == WriteStatus.WRITTEN:
        return ret(
            debug_tag="changed:written",
            outcome=outcome_if_changed,
            reason=reason_if_changed,
        )
    if ctx.status.write == WriteStatus.FAILED:
        return ret(
            debug_tag="error:write",
            outcome=Outcome.ERROR,
            reason=ctx.status.write.value,
        )

    # Changed comparison: map to the appropriate change outcome.
    if ctx.status.comparison == ComparisonStatus.CHANGED:
        return ret(
            debug_tag="changed:strip"
            if intent == ResultActionIntent.STRIP
            else (
                "changed:header"
                if intent in (ResultActionIntent.INSERT, ResultActionIntent.UPDATE)
                else "changed:generic"
            ),
            outcome=outcome_if_changed,
            reason=reason_if_changed,
        )

    # 8) Dry-run previews and remaining fallbacks.
    # These branches matter most for summary/dry-run pipelines where later mutation
    # steps (planner/writer) may not have run.
    if not apply:
        if intent in (ResultActionIntent.INSERT, ResultActionIntent.UPDATE):
            if ctx.outcome.effective_would_add_or_update:
                return ret(
                    debug_tag="would-change:header",
                    outcome=outcome_if_changed,
                    reason=header_lbl,
                )
            return ret(
                debug_tag="would-change:header-fallthrough",
                outcome=outcome_if_changed,
                reason=header_lbl,
            )
        if intent == ResultActionIntent.STRIP:
            if ctx.outcome.effective_would_strip:
                # Prefer the strip axis label for summaries.
                return ret(
                    debug_tag="would-strip",
                    outcome=outcome_if_changed,
                    reason=StripStatus.READY.value,
                )
            if ctx.status.strip == StripStatus.NOT_NEEDED:
                return ret(
                    debug_tag="unchanged:strip-not-needed",
                    outcome=Outcome.UNCHANGED,
                    reason=ctx.status.strip.value,
                )
        if ctx.status.plan == PlanStatus.PREVIEWED:
            return ret(
                debug_tag="preview:plan",
                outcome=outcome_if_changed,
                reason=reason_if_changed,
            )

    if ctx.status.generation == GenerationStatus.NO_FIELDS:
        return ret(
            debug_tag="unchanged:no-fields",
            outcome=Outcome.UNCHANGED,
            reason=ctx.status.generation.value,
        )

    if ctx.status.plan in (
        PlanStatus.SKIPPED,
        PlanStatus.FAILED,
    ):
        return ret(
            debug_tag="skip:plan",
            outcome=Outcome.SKIPPED,
            reason=ctx.status.plan.value,  # or other e.g. reason_if_changed?
        )

    # 9) Pending fallback.
    # Reaching this branch means no earlier precedence rule matched. Keeping a
    # distinct `PENDING` outcome is more honest than silently collapsing to
    # `UNCHANGED`.
    return ret(
        debug_tag="pending",
        outcome=Outcome.PENDING,
        reason=NO_REASON_PROVIDED,
    )


def classify_outcome(
    ctx: SupportsOutcomeClassification,
    *,
    apply: bool,
) -> Outcome:
    """Return the public `Outcome` classification for a processing context.

    This is a thin convenience wrapper around `map_bucket()` when only the
    public `Outcome` (and not the human-facing reason) is needed.

    Args:
        ctx: The processing context to classify.
        apply: Whether the run is in apply mode.

    Returns:
        The public outcome classification derived by `map_bucket()`.
    """
    return map_bucket(ctx, apply=apply).outcome


# Helper functions for bucketing and sorting outcome reasons/counts.
def _count_buckets(
    buckets: Iterable[ResultBucket],
) -> dict[tuple[Outcome, str], int]:
    """Count result buckets by `(outcome, reason)`.

    Args:
        buckets: Buckets to count.

    Returns:
        Mapping from `(outcome, reason)` to occurrence count.
    """
    counts: dict[tuple[Outcome, str], int] = {}
    for bucket in buckets:
        outcome: Outcome = bucket.outcome
        reason: str = bucket.reason or NO_REASON_PROVIDED
        key: tuple[Outcome, str] = (outcome, reason)
        counts[key] = counts.get(key, 0) + 1
    return counts


def _sorted_outcome_reason_rows(
    counts: dict[tuple[Outcome, str], int],
) -> list[OutcomeReasonCount]:
    """Return sorted outcome summary rows for counted buckets.

    Args:
        counts: Mapping from `(outcome, reason)` to occurrence count.

    Returns:
        Sorted list of `OutcomeReasonCount` rows.
    """
    order_index: dict[Outcome, int] = {outcome: idx for idx, outcome in enumerate(OUTCOME_ORDER)}

    rows: list[OutcomeReasonCount] = [
        OutcomeReasonCount(outcome=outcome, reason=reason, count=count)
        for (outcome, reason), count in counts.items()
    ]
    rows.sort(key=lambda row: (order_index.get(row.outcome, 10_000), row.reason))
    return rows


def collect_outcome_reason_counts(
    results: Iterable[ProcessingResult],
) -> list[OutcomeReasonCount]:
    """Collect summary counts grouped by `(outcome, reason)`.

    Unlike a plain per-outcome aggregation, this helper preserves the second
    bucketing axis (`reason`) so summary views do not collapse distinct
    sub-buckets inside the same `Outcome`.

    Ordering is deterministic and stable:
    1. Fixed public `OUTCOME_ORDER`
    2. Alphabetical `reason` within each outcome

    Args:
        results: Durable results to bucket and count.

    Returns:
        Sorted list of `OutcomeReasonCount` rows.
    """
    buckets: Iterable[ResultBucket] = (
        map_bucket(r, apply=r.execution_mode.apply_changes) for r in results
    )
    return _sorted_outcome_reason_rows(_count_buckets(buckets))
