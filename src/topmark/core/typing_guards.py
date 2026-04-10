# topmark:header:start
#
#   project      : TopMark
#   file         : typing_guards.py
#   file_relpath : src/topmark/core/typing_guards.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Generic type guards and normalization helpers for TopMark.

This module provides `TypeGuard`-based predicates that help Pyright narrow runtime values coming
from weakly typed objects, e.g. values stored in the Click context.

It also includes small, side-effect-free normalization helpers such as `as_object_dict`, plus
permissive generic mapping-extraction helpers used by runtime/config payload shaping. These helpers
are meant for already-normalized Python mappings, not TOML-schema validation.

See Also:
- [`topmark.toml.typing_guards`][topmark.toml.typing_guards]: type guards and normalization helpers
  for TOML parsing.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TypeGuard
from typing import cast

# --- Type guards / narrowers: pure Python ---


def is_mapping(obj: object) -> TypeGuard[Mapping[object, object]]:
    """Type guard for a Mapping value.

    Checks only that the value is a ``Mapping``; does not validate item types.

    Args:
        obj: Value to test.

    Returns:
        True if obj is a Mapping.
    """
    return isinstance(obj, Mapping)


def is_any_list(obj: object) -> TypeGuard[list[object]]:
    """Type guard for a generic list value.

    Checks only that the value is a ``list``; does not validate item types.

    Args:
        obj: Value to test.

    Returns:
        True if obj is a list.
    """
    return isinstance(obj, list)


def is_str_list(obj: object) -> TypeGuard[list[str]]:
    """Type guard for a string list value.

    Checks that the value is a ``list[str]``.

    Args:
        obj: Value to test.

    Returns:
        True if obj is a list[str].
    """
    return is_any_list(obj) and all(isinstance(x, str) for x in obj)


# --- “Casting / normalization” helpers ---


def as_object_dict(value: object) -> dict[str, object]:
    """Return `value` as a shallow `dict[str, object]` when possible.

    This helper is intentionally permissive and is meant for post-normalization
    payload shaping, not TOML-schema validation. Non-dictionary inputs yield an
    empty dictionary. Dictionary keys are stringified to provide a stable
    ``dict[str, object]`` result for downstream machine-payload builders.

    Args:
        value: Arbitrary runtime value.

    Returns:
        A shallow dictionary with string keys when `value` is a plain `dict`;
        otherwise ``{}``.
    """
    if not isinstance(value, dict):
        return {}

    items: Mapping[object, object] = cast("Mapping[object, object]", value)
    return {str(key): item for key, item in items.items()}


# ---- Generic mapping helpers ----


def get_object_dict_value(mapping: Mapping[str, object], key: str) -> dict[str, object]:
    """Return a shallow `dict[str, object]` value for `key` when present.

    This helper is intentionally permissive and is meant for generic mapping
    extraction from already-normalized runtime/config payloads. It is not a TOML
    schema-validation helper.

    Args:
        mapping: Mapping to inspect.
        key: Key to extract.

    Returns:
        A shallow dictionary with stringified keys when the value at `key` is a
        plain `dict`; otherwise ``{}``.
    """
    value: object = mapping.get(key)
    return as_object_dict(value)


def get_string_dict_value(mapping: Mapping[str, object], key: str) -> dict[str, str]:
    """Return a `dict[str, str]` value for `key`, filtering invalid items.

    Args:
        mapping: Mapping to inspect.
        key: Key to extract.

    Returns:
        A dictionary containing only `str -> str` entries from the value stored
        at `key`, or ``{}`` when the value is absent or not a plain `dict`.
    """
    value: object = mapping.get(key)
    if not isinstance(value, dict):
        return {}

    # Tell Pyright this is a dict, treat the keys/values as base objects:
    items = cast("Mapping[object, object]", value)

    result: dict[str, str] = {}
    for item_key, item_value in items.items():
        if isinstance(item_key, str) and isinstance(item_value, str):
            result[item_key] = item_value
    return result


def get_string_list_dict_value(mapping: Mapping[str, object], key: str) -> dict[str, list[str]]:
    """Return a `dict[str, list[str]]` value for `key`, filtering invalid items.

    Args:
        mapping: Mapping to inspect.
        key: Key to extract.

    Returns:
        A dictionary containing only `str -> list[str]` entries from the value
        stored at `key`, or ``{}`` when the value is absent or not a plain
        `dict`.
    """
    value: object = mapping.get(key)
    if not isinstance(value, dict):
        return {}

    # Tell Pyright this is a dict, treat the keys/values as base objects:
    items = cast("Mapping[object, object]", value)

    result: dict[str, list[str]] = {}
    for item_key, item_value in items.items():
        if not isinstance(item_key, str) or not is_str_list(item_value):
            continue
        result[item_key] = list(item_value)
    return result
