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

This module owns the *bucketing* logic that maps a `ProcessingContext` to a
stable public outcome key and a human-facing bucket label.

Design goals:
- Presentation-free: no ANSI, no chalk/yachalk, no console logic.
- Reusable across frontends: CLI, docs tooling, and the public API.
- Stable keys/labels: keys are `Outcome.value` strings; labels are the
  first-seen bucket reason.

Coloring/styling is intentionally layered on top (e.g. in `cli_shared`).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from topmark.api.types import Outcome
from topmark.config.logging import TopmarkLogger, get_logger
from topmark.pipeline.context.model import ProcessingContext
from topmark.pipeline.context.policy import (
    can_change,
    check_permitted_by_policy,
    effective_would_add_or_update,
    effective_would_strip,
)
from topmark.pipeline.status import (  # temporary
    ComparisonStatus,
    ContentStatus,
    FsStatus,
    GenerationStatus,
    HeaderStatus,
    PlanStatus,
    ResolveStatus,
    StripStatus,
    WriteStatus,
)

if TYPE_CHECKING:
    from topmark.pipeline.context.model import ProcessingContext


NO_REASON_PROVIDED: str = "(no reason provided)"

logger: TopmarkLogger = get_logger(__name__)


class Intent(Enum):
    """High-level action intent inferred from pipeline statuses."""

    STRIP = "strip"
    INSERT = "insert"
    UPDATE = "update"
    NONE = "none"  # no clear action (compare skipped, etc.)


def determine_intent(ctx: ProcessingContext) -> Intent:
    """Derive the high-level intent for bucketing from the current context.

    Intent is inferred from statuses that indicate what the pipeline is trying
    to do for this file:

    - STRIP: the strip axis is non-pending (strip pipeline ran).
    - INSERT: header axis indicates a missing header.
    - UPDATE: header axis is decided (not PENDING) and not missing.
    - NONE: insufficient information to infer an action (early termination).

    Args:
        ctx (ProcessingContext): The processing context.

    Returns:
        Intent: The inferred bucketing intent.
    """
    if ctx.status.strip != StripStatus.PENDING:
        return Intent.STRIP
    if ctx.status.header == HeaderStatus.MISSING:
        return Intent.INSERT
    if ctx.status.header != HeaderStatus.PENDING:
        return Intent.UPDATE
    return Intent.NONE


@dataclass
class ResultBucket:
    """Outcome + optional human label used for bucketing.

    The bucket is a small value object that couples a public `Outcome` with an
    optional human-facing label used in summaries.

    Args:
        outcome (Outcome | None): The classified outcome to set. If ``None``,
            the default value is preserved.
        reason (str | None): Human-facing bucket label (summary text). If
            ``None``, the default value is preserved.

    Attributes:
        outcome (Outcome): The classified outcome.
        reason (str | None): Human-facing bucket label (summary text). This is
            intentionally independent of internal debug tracing.
    """

    outcome: Outcome = Outcome.PENDING
    reason: str | None = None

    def __init__(self, *, outcome: Outcome | None, reason: str | None) -> None:
        if outcome is not None:
            self.outcome = outcome
        if reason is not None:
            self.reason = reason

        logger.debug("ResultBucket: '%s'", self.__repr__())

    def __repr__(self) -> str:
        """Return a `str` representation of a `ResultBucket` instance.

        Returns:
            str: The `str` representation of the `ResultBucket` instance.
        """
        return f"{self.outcome.value}: {self.reason or NO_REASON_PROVIDED}"


def map_bucket(ctx: ProcessingContext, *, apply: bool) -> ResultBucket:
    """Map a file context to a public bucket (Outcome + label).

    This logic is precedence-ordered: the first matching rule wins. The ordering
    matters because some axes may remain `PENDING` depending on the chosen pipeline
    (for example, `strip` pipelines may omit comparison).

    Precedence (high → low):
        1) Hard skips/errors (resolve/fs/content fatal states).
        2) Content-level soft skips (mixed newlines / BOM-before-shebang / reflow).
        3) Empty-file default compliance: empty files are UNCHANGED unless policy allows
           inserting headers into empty files.
        4) Strip intent mapping based on the strip axis (READY/NOT_NEEDED/FAILED). This
           must not depend on comparison.
        5) Malformed headers that TopMark cannot safely interpret.
        6) Policy veto (add-only / update-only).
        7) Comparison/write outcomes (UNCHANGED/CHANGED and write WRITTEN/FAILED).
        8) Dry-run previews and remaining fallbacks (NO_FIELDS, plan skipped).
        9) Pending (no rule matched).

    Args:
        ctx (ProcessingContext): The per-file pipeline context.
        apply (bool): Whether the run is in apply mode.

    Returns:
        ResultBucket: Bucket containing public Outcome and a human label.
    """
    intent: Intent = determine_intent(ctx)
    logger.trace("intent: %s; apply: %s; status: %s", intent.value, apply, ctx.status)

    def ret(
        *,
        debug_tag: str,
        outcome: Outcome,
        reason: str | None,
    ) -> ResultBucket:
        """Return a bucket while emitting a structured debug trace.

        The `tag` is debug-only and is intended to make it easy to locate the
        matching precedence branch in logs.

        Args:
            debug_tag (str): Stable debug tag for the matching branch.
            outcome (Outcome): Public outcome for CLI/API.
            reason (str | None): Human-facing bucket label.

        Returns:
            ResultBucket: Constructed bucket.
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
    if ctx.status.resolve != ResolveStatus.RESOLVED:
        return ret(
            debug_tag="skip:resolve",
            outcome=Outcome.SKIPPED,
            reason=ctx.status.resolve.value,
        )
    if ctx.status.fs in {FsStatus.NOT_FOUND, FsStatus.NO_READ_PERMISSION, FsStatus.UNREADABLE}:
        return ret(
            debug_tag="error:fs-read",
            outcome=Outcome.ERROR,
            reason=ctx.status.fs.value,
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

    # 3) Empty-file default compliance
    # Empty files are compliant by default (not a non-compliance). If policy allows inserting
    # into empties, `can_change(r)` will be True and we fall through to normal change bucketing.
    if ctx.status.fs == FsStatus.EMPTY and not can_change(ctx):
        return ret(
            debug_tag="unchanged:empty-default",
            outcome=Outcome.UNCHANGED,
            reason="empty_file",
        )

    # TODO: Also check 'pseudo-empty' file containing only BOM

    # 4) Strip mapping (strip pipelines may omit comparer; do not depend on comparison)
    if intent == Intent.STRIP:
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
    # Policy veto is tri-state: False means forbidden; True/None both mean “not vetoed”.
    permitted_by_policy: bool | None = check_permitted_by_policy(ctx)
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
        if intent == Intent.STRIP:
            outcome_if_changed = Outcome.STRIPPED
        elif intent == Intent.INSERT:
            outcome_if_changed = Outcome.INSERTED
        elif intent == Intent.UPDATE:
            outcome_if_changed = Outcome.UPDATED
        else:
            outcome_if_changed = Outcome.CHANGED
    else:
        if intent == Intent.STRIP:
            outcome_if_changed = Outcome.WOULD_STRIP
        elif intent == Intent.INSERT:
            outcome_if_changed = Outcome.WOULD_INSERT
        elif intent == Intent.UPDATE:
            outcome_if_changed = Outcome.WOULD_UPDATE
        else:
            outcome_if_changed = Outcome.WOULD_CHANGE

    reason_if_changed: str = f"{header_lbl}, {comparison_lbl}"
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
        if intent == Intent.STRIP:
            return ret(
                debug_tag="changed:strip",
                outcome=outcome_if_changed,
                reason=f"{header_lbl}, {strip_lbl}",
            )
        elif intent in (Intent.INSERT, Intent.UPDATE):
            return ret(
                debug_tag="changed:header",
                outcome=outcome_if_changed,
                reason=reason_if_changed,
            )
        else:
            return ret(
                debug_tag="changed:generic",
                outcome=outcome_if_changed,
                reason=reason_if_changed,
            )

    # 8) Dry-run previews and remaining fallbacks
    if not apply:
        if intent in (Intent.INSERT, Intent.UPDATE):
            if effective_would_add_or_update(ctx):
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
        if intent == Intent.STRIP:
            if effective_would_strip(ctx):
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

    # 9) Pending (optional)
    # If you prefer to collapse this to UNCHANGED, return that here instead.
    return ret(
        debug_tag="pending",
        outcome=Outcome.PENDING,
        reason=NO_REASON_PROVIDED,
    )


def classify_outcome(ctx: ProcessingContext, *, apply: bool) -> Outcome:
    """Translate a `ProcessingContext` status into a public `Outcome`.

    Args:
        ctx (ProcessingContext): The processing context to classify.
        apply (bool): Whether the run is in apply mode; influences CHANGED/Would-change.

    Returns:
        Outcome: The public outcome classification.

    Notes:
        - Non-resolved *skipped* statuses (e.g., unsupported or known-no-headers)
          are treated as `UNCHANGED` in the API layer.
        - When `apply=False`, changed files are reported as `WOULD_CHANGE`.
        - When `apply=True`, changed files are reported as `CHANGED`.
    """
    return map_bucket(ctx, apply=apply).outcome


def collect_outcome_counts(
    results: list[ProcessingContext],
) -> dict[str, tuple[int, str]]:
    """Collect outcome counts by classification key.

    The key is the public outcome value (e.g. "unchanged", "error"). The label
    is the first-seen human-facing bucket label (reason).

    Args:
        results (list[ProcessingContext]): Processing contexts to bucket and count.

    Returns:
        dict[str, tuple[int, str]]: Mapping from classification key to ``(count, label)``.
    """
    counts: dict[str, tuple[int, str]] = {}
    for r in results:
        apply: bool = r.config.apply_changes is True
        bucket: ResultBucket = map_bucket(r, apply=apply)
        key: str = bucket.outcome.value
        initial_label: str = bucket.reason or NO_REASON_PROVIDED
        n, label = counts.get(key, (0, initial_label))
        counts[key] = (n + 1, label)
    return counts
