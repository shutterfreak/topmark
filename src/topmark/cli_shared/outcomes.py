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

This module layers terminal presentation concerns (ANSI coloring) on top of the
pure bucketing logic in [`topmark.pipeline.outcomes`][topmark.pipeline.outcomes].

It is Click-free by design, so it can be reused from tests and other frontends.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from yachalk import chalk

from topmark.api.types import Outcome
from topmark.pipeline.outcomes import OutcomeReasonCount
from topmark.pipeline.outcomes import collect_outcome_reason_counts

if TYPE_CHECKING:
    from topmark.pipeline.context.model import ProcessingContext


FormatCallable = Callable[[str], str]


_OUTCOME_COLOR: dict[Outcome, FormatCallable] = {
    Outcome.PENDING: chalk.gray,
    Outcome.SKIPPED: chalk.yellow,
    Outcome.WOULD_CHANGE: chalk.red_bright,
    Outcome.CHANGED: chalk.yellow_bright,
    Outcome.UNCHANGED: chalk.green,
    Outcome.WOULD_INSERT: chalk.yellow,
    Outcome.WOULD_UPDATE: chalk.yellow,
    Outcome.WOULD_STRIP: chalk.yellow,
    Outcome.INSERTED: chalk.yellow_bright,
    Outcome.UPDATED: chalk.yellow_bright,
    Outcome.STRIPPED: chalk.yellow_bright,
    Outcome.ERROR: chalk.red_bright,
}


def _outcome_color(outcome: Outcome) -> FormatCallable:
    """Return the formatter used to colorize a given outcome.

    Args:
        outcome: The Outcome.

    Returns:
        The matching `FormatCallable` for the given `Outcome`.
    """
    return _OUTCOME_COLOR[outcome]


def collect_outcome_counts_colored(
    results: list[ProcessingContext],
) -> list[tuple[OutcomeReasonCount, Callable[[str], str]]]:
    """Return colored summary rows grouped by `(outcome, reason)`.

    Args:
        results: Processing contexts to classify and count.

    Returns:
        Stable summary rows paired with the formatter for their `Outcome`.
    """
    counts: list[OutcomeReasonCount] = collect_outcome_reason_counts(results)
    return [(row, _outcome_color(row.outcome)) for row in counts]
