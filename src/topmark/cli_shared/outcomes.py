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
pure bucketing logic in `topmark.pipeline.outcomes`.

It is Click-free by design, so it can be reused from tests and other frontends.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from yachalk import chalk

from topmark.api.types import Outcome
from topmark.pipeline.outcomes import (
    collect_outcome_counts,
)

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
        outcome (Outcome): The Outcome.

    Returns:
        FormatCallable: The matching `FormatCallable` for the given `Outcome`.
    """
    return _OUTCOME_COLOR[outcome]


def _outcome_from_value(value: str) -> Outcome | None:
    """Return the matching Outcome member, or None if not found.

    Args:
        value (str): The Outome value to look for.

    Returns:
        Outcome | None: The matching `Outcome` or `None` if no match.
    """
    try:
        result = Outcome(value)
    except ValueError:
        # This should not happen
        return None

    return result


def collect_outcome_counts_colored(
    results: list[ProcessingContext],
) -> dict[str, tuple[int, str, Callable[[str], str]]]:
    """Count results by classification key and include a colorizer.

    Keeps the first-seen label and color for each key.

    Args:
        results (list[ProcessingContext]): Processing contexts to classify and count.

    Returns:
        dict[str, tuple[int, str, Callable[[str], str]]]: Mapping from classification
            key to ``(count, label, color_fn)``.
    """
    counts: dict[str, tuple[int, str]] = collect_outcome_counts(results)
    colored_counts: dict[str, tuple[int, str, Callable[[str], str]]] = {
        outcome_value: (
            count,
            label,
            _outcome_color(_outcome_from_value(outcome_value) or Outcome.ERROR),
        )
        for outcome_value, (count, label) in counts.items()
    }
    return colored_counts
