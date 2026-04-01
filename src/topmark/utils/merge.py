# topmark:header:start
#
#   project      : TopMark
#   file         : merge.py
#   file_relpath : src/topmark/utils/merge.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Field merge helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import TypeVar

from topmark.core.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Iterable

    from topmark.core.logging import TopmarkLogger


logger: TopmarkLogger = get_logger(__name__)


# ------------------ Helpers ------------------

T = TypeVar("T")


# --- List Helpers ---


def none_if_empty(items: Iterable[T]) -> list[T] | None:
    """Return `None` if an Iterable is empty."""
    return list(items) if items else None


def merge_unique_iterables(
    current: Iterable[T] | None,
    incoming: Iterable[T] | None,
) -> list[T]:
    """Returns a new list with unique items from current and incoming.

    Preserves order. Always returns a list (empty if both are None).
    """
    # Use a set for O(1) lookups to avoid O(N^2) performance hits
    result: list[T] = []
    seen: set[T] = set()

    for item in current or []:
        if item not in seen:
            result.append(item)
            seen.add(item)

    if incoming:
        for item in incoming:
            if item not in seen:
                result.append(item)
                seen.add(item)

    return result


def merge_unique_iterables_or_none(
    current: Iterable[T] | None,
    incoming: Iterable[T] | None,
) -> list[T] | None:
    """Returns None if both inputs are None, otherwise merges uniquely."""
    if current is None and incoming is None:
        return None
    return merge_unique_iterables(current, incoming)


# --- Dict Helpers ---


def merge_mappings_last_wins(
    current: dict[str, T] | None,
    incoming: dict[str, T] | None,
) -> dict[str, T]:
    """Merges two dicts (incoming overrides current).

    Always returns a dict (empty if both are None).
    """
    # Python 3.9+ merge operator (|) handles the copy and update logic cleanly
    return (current or {}) | (incoming or {})


def merge_mappings_last_wins_or_none(
    current: dict[str, T] | None,
    incoming: dict[str, T] | None,
) -> dict[str, T] | None:
    """Returns None if both inputs are None, otherwise merges dicts."""
    if current is None and incoming is None:
        return None
    return merge_mappings_last_wins(current, incoming)
