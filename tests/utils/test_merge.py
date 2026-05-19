# topmark:header:start
#
#   project      : TopMark
#   file         : test_merge.py
#   file_relpath : tests/utils/test_merge.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Unit tests for generic merge helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from topmark.utils.merge import merge_mappings_last_wins
from topmark.utils.merge import merge_mappings_last_wins_or_none
from topmark.utils.merge import merge_unique_iterables
from topmark.utils.merge import merge_unique_iterables_or_none
from topmark.utils.merge import none_if_empty

if TYPE_CHECKING:
    from collections.abc import Iterable


def _numbers() -> Iterable[int]:
    """Yield duplicate numbers for generator-consumption tests."""
    yield 1
    yield 2
    yield 2


@pytest.mark.parametrize(
    "items",
    [
        [],
        (),
        iter(()),
    ],
)
def test_none_if_empty_returns_none_for_empty_iterables(items: Iterable[object]) -> None:
    """none_if_empty() should collapse empty iterables to None."""
    assert none_if_empty(items) is None


@pytest.mark.parametrize(
    ("items", "expected"),
    [
        (["a"], ["a"]),
        (("a", "b"), ["a", "b"]),
    ],
)
def test_none_if_empty_returns_list_for_non_empty_sized_iterables(
    items: Iterable[str],
    expected: list[str],
) -> None:
    """none_if_empty() should materialize non-empty sized iterables."""
    assert none_if_empty(items) == expected


def test_none_if_empty_preserves_non_empty_generator_values() -> None:
    """none_if_empty() should materialize generators without dropping values."""
    assert none_if_empty(_numbers()) == [1, 2, 2]


def test_merge_unique_iterables_returns_empty_list_for_two_none_inputs() -> None:
    """merge_unique_iterables() should always return a list."""
    assert merge_unique_iterables(None, None) == []


def test_merge_unique_iterables_preserves_first_occurrence_order() -> None:
    """Unique iterable merge should preserve first occurrence order across inputs."""
    result: list[str] = merge_unique_iterables(
        current=["a", "b", "a", "c"],
        incoming=["b", "d", "c", "e"],
    )

    assert result == ["a", "b", "c", "d", "e"]


def test_merge_unique_iterables_handles_empty_current_and_incoming_values() -> None:
    """Unique iterable merge should handle empty and None sides symmetrically."""
    assert merge_unique_iterables([], ["a", "a", "b"]) == ["a", "b"]
    assert merge_unique_iterables(["a", "a", "b"], None) == ["a", "b"]


def test_merge_unique_iterables_does_not_mutate_input_lists() -> None:
    """Unique iterable merge should return a new list without mutating inputs."""
    current: list[str] = ["a", "b"]
    incoming: list[str] = ["b", "c"]

    result: list[str] = merge_unique_iterables(current, incoming)

    assert result == ["a", "b", "c"]
    assert current == ["a", "b"]
    assert incoming == ["b", "c"]
    assert result is not current
    assert result is not incoming


def test_merge_unique_iterables_consumes_generators_once() -> None:
    """Unique iterable merge should work with one-shot generator inputs."""
    result: list[str] = merge_unique_iterables(
        current=(item for item in ["a", "b", "a"]),
        incoming=(item for item in ["b", "c", "c"]),
    )

    assert result == ["a", "b", "c"]


def test_merge_unique_iterables_or_none_preserves_none_when_both_inputs_are_none() -> None:
    """Optional unique merge should preserve the None/None sentinel case."""
    assert merge_unique_iterables_or_none(None, None) is None


@pytest.mark.parametrize(
    ("current", "incoming", "expected"),
    [
        (None, [], []),
        ([], None, []),
        (["a", "a"], None, ["a"]),
        (None, ["a", "a"], ["a"]),
    ],
)
def test_merge_unique_iterables_or_none_returns_list_when_any_input_is_present(
    current: Iterable[str] | None,
    incoming: Iterable[str] | None,
    expected: list[str],
) -> None:
    """Optional unique merge should return a list when either input is present."""
    assert merge_unique_iterables_or_none(current, incoming) == expected


def test_merge_mappings_last_wins_returns_empty_dict_for_two_none_inputs() -> None:
    """Mapping merge should always return a dict."""
    assert merge_mappings_last_wins(None, None) == {}


def test_merge_mappings_last_wins_uses_incoming_precedence() -> None:
    """Mapping merge should let incoming values override current values."""
    result: dict[str, int] = merge_mappings_last_wins(
        current={"a": 1, "b": 2},
        incoming={"b": 20, "c": 3},
    )

    assert result == {"a": 1, "b": 20, "c": 3}


def test_merge_mappings_last_wins_returns_new_dict_without_mutating_inputs() -> None:
    """Mapping merge should not mutate either input mapping."""
    current: dict[str, int] = {"a": 1}
    incoming: dict[str, int] = {"a": 2, "b": 3}

    result: dict[str, int] = merge_mappings_last_wins(current, incoming)

    assert result == {"a": 2, "b": 3}
    assert current == {"a": 1}
    assert incoming == {"a": 2, "b": 3}
    assert result is not current
    assert result is not incoming


@pytest.mark.parametrize(
    ("current", "incoming", "expected"),
    [
        ({}, None, {}),
        (None, {}, {}),
        ({"a": "current"}, None, {"a": "current"}),
        (None, {"a": "incoming"}, {"a": "incoming"}),
    ],
)
def test_merge_mappings_last_wins_handles_one_sided_inputs(
    current: dict[str, str] | None,
    incoming: dict[str, str] | None,
    expected: dict[str, str],
) -> None:
    """Mapping merge should handle empty, current-only, and incoming-only inputs."""
    assert merge_mappings_last_wins(current, incoming) == expected


def test_merge_mappings_last_wins_or_none_preserves_none_when_both_inputs_are_none() -> None:
    """Optional mapping merge should preserve the None/None sentinel case."""
    assert merge_mappings_last_wins_or_none(None, None) is None


@pytest.mark.parametrize(
    ("current", "incoming", "expected"),
    [
        ({}, None, {}),
        (None, {}, {}),
        ({"a": 1}, None, {"a": 1}),
        (None, {"a": 2}, {"a": 2}),
        ({"a": 1}, {"a": 2}, {"a": 2}),
    ],
)
def test_merge_mappings_last_wins_or_none_returns_dict_when_any_input_is_present(
    current: dict[str, int] | None,
    incoming: dict[str, int] | None,
    expected: dict[str, int],
) -> None:
    """Optional mapping merge should return a dict when either input is present."""
    assert merge_mappings_last_wins_or_none(current, incoming) == expected
