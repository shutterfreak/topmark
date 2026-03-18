# topmark:header:start
#
#   project      : TopMark
#   file         : outcomes.py
#   file_relpath : src/topmark/cli_shared/outcomes.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI-oriented outcome helpers.

This module layers CLI semantic styling concerns on top of the pure bucketing
logic in [`topmark.pipeline.outcomes`][topmark.pipeline.outcomes].

It is Click-free by design, so it can be reused from tests and other frontends.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.api.types import Outcome
from topmark.cli.presentation import style_for_role
from topmark.core.presentation import StyleRole
from topmark.pipeline.outcomes import OutcomeReasonCount
from topmark.pipeline.outcomes import collect_outcome_reason_counts

if TYPE_CHECKING:
    from topmark.cli.presentation import TextStyler
    from topmark.pipeline.context.model import ProcessingContext


_OUTCOME_STYLE_ROLE: dict[Outcome, StyleRole] = {
    Outcome.PENDING: StyleRole.PENDING,
    Outcome.SKIPPED: StyleRole.SKIPPED,
    Outcome.WOULD_CHANGE: StyleRole.WOULD_CHANGE,
    Outcome.CHANGED: StyleRole.CHANGED,
    Outcome.UNCHANGED: StyleRole.UNCHANGED,
    Outcome.WOULD_INSERT: StyleRole.WOULD_CHANGE,
    Outcome.WOULD_UPDATE: StyleRole.WOULD_CHANGE,
    Outcome.WOULD_STRIP: StyleRole.WOULD_CHANGE,
    Outcome.INSERTED: StyleRole.CHANGED,
    Outcome.UPDATED: StyleRole.CHANGED,
    Outcome.STRIPPED: StyleRole.CHANGED,
    Outcome.ERROR: StyleRole.ERROR,
}


def get_outcome_style_role(outcome: Outcome) -> StyleRole:
    """Return the semantic style role used for a given outcome.

    Args:
        outcome: The public outcome.

    Returns:
        The semantic `StyleRole` corresponding to `outcome`.
    """
    role: StyleRole = _OUTCOME_STYLE_ROLE.get(outcome, StyleRole.NO_STYLE)
    return role


def get_outcome_styler(outcome: Outcome) -> TextStyler:
    """Return the semantic text styler used for a given outcome.

    Args:
        outcome: The public outcome.

    Returns:
        The CLI text styler resolved from the mapped semantic `StyleRole`.
    """
    role: StyleRole = get_outcome_style_role(outcome)
    return style_for_role(role)


def collect_outcome_counts_styled(
    results: list[ProcessingContext],
) -> list[tuple[OutcomeReasonCount, TextStyler]]:
    """Return styled summary rows grouped by `(outcome, reason)`.

    Args:
        results: Processing contexts to classify and count.

    Returns:
        Stable summary rows paired with the CLI text styler for their semantic outcome role.
    """
    counts: list[OutcomeReasonCount] = collect_outcome_reason_counts(results)
    return [(row, get_outcome_styler(row.outcome)) for row in counts]
