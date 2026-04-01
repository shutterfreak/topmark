# topmark:header:start
#
#   project      : TopMark
#   file         : guards.py
#   file_relpath : src/topmark/toml/guards.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Type guards and normalization helpers for TopMark TOML handling.

This module provides `TypeGuard`-based predicates that help Pyright narrow
runtime values coming from TOML parsing, including `tomlkit` objects.

It also includes small, side-effect-free normalization helpers such as
`as_toml_table` and `as_toml_table_map`, used to safely coerce arbitrary parsed
values into the plain-Python table shapes used by TopMark TOML processing.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING
from typing import TypeGuard
from typing import cast

from tomlkit.items import Table

from topmark.core.logging import get_logger

if TYPE_CHECKING:
    from topmark.core.logging import TopmarkLogger
    from topmark.toml.types import TomlTable
    from topmark.toml.types import TomlTableMap
    from topmark.toml.types import TomlValue


logger: TopmarkLogger = get_logger(__name__)

# --- Type guards / narrowers: pure Python ---


def is_toml_table(obj: object) -> TypeGuard[TomlTable]:
    """Type guard for a TOML table‑like mapping.

    Args:
        obj: Value to test.

    Returns:
        ``True`` if ``obj`` is a plain ``dict`` suitable for narrowing to `TomlTable`.
    """
    return isinstance(obj, dict)


def is_toml_value(value: object) -> TypeGuard[TomlValue]:
    """Return whether `value` conforms to the recursive `TomlValue` shape."""
    if value is None:
        return False
    if isinstance(value, str | int | float | bool):
        return True
    if is_any_list(value):
        return all(is_toml_value(item) for item in value)
    if is_mapping(value):
        return all(isinstance(key, str) and is_toml_value(item) for key, item in value.items())
    return False


def toml_table_from_mapping(data: Mapping[str, object]) -> TomlTable:
    """Return a validated TOML table copied from a generic mapping.

    Args:
        data: The mapping to convert.

    Returns:
        TomlTable representation of `data`.

    Raises:
        TypeError: If the mapping contains a value that is not representable as `TomlValue`.
    """
    result: TomlTable = {}
    for key, value in data.items():
        if not is_toml_value(value):
            raise TypeError(
                f"Config mapping contains a non-TOML-compatible value for {key!r}: {value!r}"
            )
        result[key] = value
    return result


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


# --- Type guards / narrowers: tomlkit-specific ---


def is_tomlkit_table(obj: object) -> TypeGuard[Table]:
    """Type guard for a `tomlkit.items.Table`.

    Args:
        obj: Value to test.

    Returns:
        ``True`` if ``obj`` is a ``tomlkit.items.Table``.
    """
    return isinstance(obj, Table)


# --- “Casting / normalization” helpers ---


def as_toml_table(obj: object) -> TomlTable | None:
    """Return the object as a TOML table when possible.

    A TOML table is represented by the recursive `TomlTable` alias used across
    TopMark TOML handling.

    Args:
        obj: Arbitrary object obtained from parsed TOML.

    Returns:
        ``obj`` cast to ``TomlTable`` when it is a ``dict``, otherwise ``None``.
    """
    if is_toml_table(obj):
        return obj

    logger.debug("Not a TOML table: %r", obj)
    return None


def as_toml_table_map(obj: object) -> TomlTableMap:
    """Return a mapping of string keys to TOML subtables.

    This helper is useful for normalizing nested sections like ``[policy_by_type]``
    where each value must itself be a TOML table.

    Args:
        obj: Arbitrary object obtained from parsed TOML.

    Returns:
        A mapping with only ``str -> TomlTable`` entries. Non-matching items
        are silently dropped.
    """
    out: TomlTableMap = {}

    if not isinstance(obj, dict):
        return out

    # Tell Pyright this is a dict, treat the keys/values as base objects:
    items = cast("Mapping[object, object]", obj).items()

    for key, value in items:
        if not isinstance(key, str):
            logger.debug("Ignoring non-string key in TOML table map: %r", key)
            continue
        if is_toml_table(value):
            out[key] = value
        else:
            logger.debug("Ignoring non-dict entry for key %s: %r", key, value)
    return out


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
