# topmark:header:start
#
#   project      : TopMark
#   file         : outcome_snapshot.py
#   file_relpath : src/topmark/pipeline/outcome_snapshot.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Durable outcome snapshot values for reduced pipeline results.

The mutable [`ProcessingContext`][topmark.pipeline.context.model.ProcessingContext]
remains the execution object used by pipeline steps. This module provides the
immutable outcome-facing value object used when reducing that context into a
[ProcessingResult][topmark.pipeline.result.ProcessingResult].

`OutcomeSnapshot` deliberately stores computed flags rather than retaining the
source context. That keeps result objects independent from volatile execution
state and provides the policy-aware fields needed by result-oriented classification
without retaining the mutable context.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from topmark.pipeline.context.policy import can_change
from topmark.pipeline.context.policy import check_permitted_by_policy
from topmark.pipeline.context.policy import effective_would_add_or_update
from topmark.pipeline.context.policy import effective_would_strip
from topmark.pipeline.context.policy import is_empty_for_insert_unchanged_by_default
from topmark.pipeline.context.policy import would_add_or_update
from topmark.pipeline.context.policy import would_change
from topmark.pipeline.context.policy import would_strip

if TYPE_CHECKING:
    from topmark.pipeline.context.protocols import SupportsPolicyEvaluation


@dataclass(frozen=True, kw_only=True, slots=True)
class OutcomeSnapshot:
    """Durable outcome-facing flags captured from a processing context.

    These flags mirror the current high-level outcome payload produced by
    `ProcessingContext.to_dict()` without retaining the mutable context itself.
    They also provide the stable policy-aware inputs consumed by outcome
    bucketing once a context has been reduced to a result.

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
        empty_for_insert_unchanged_by_default: Whether empty-for-insert files should
            default to unchanged under current policy.
    """

    would_change: bool | None
    can_change: bool
    permitted_by_policy: bool | None
    would_add_or_update: bool
    effective_would_add_or_update: bool
    would_strip: bool
    effective_would_strip: bool
    empty_for_insert_unchanged_by_default: bool

    @classmethod
    def from_context(cls, ctx: SupportsPolicyEvaluation) -> OutcomeSnapshot:
        """Create an outcome snapshot from a mutable processing context.

        Args:
            ctx: Source object exposing the policy-evaluation protocol. In normal
                pipeline execution this is a `ProcessingContext`, but the snapshot
                constructor depends only on the structural protocol to avoid a
                concrete context import cycle.

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
            empty_for_insert_unchanged_by_default=(is_empty_for_insert_unchanged_by_default(ctx)),
        )

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-friendly outcome payload.

        Returns:
            Mapping matching the existing high-level outcome payload shape. The
            helper intentionally omits internal-only classification fields that
            are not part of the current serialized outcome payload.
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
