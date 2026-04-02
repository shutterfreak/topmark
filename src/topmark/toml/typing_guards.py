# topmark:header:start
#
#   project      : TopMark
#   file         : typing_guards.py
#   file_relpath : src/topmark/toml/typing_guards.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Type guards and TOML-shape normalization helpers for TopMark TOML handling.

This module provides `TypeGuard`-based predicates that help Pyright narrow
runtime values coming from TOML parsing, including `tomlkit` objects.

It focuses on:
- recognizing plain-Python TOML-compatible shapes
- normalizing parsed objects into the recursive TOML table aliases used across
  TopMark
- narrowing nested TOML table mappings such as grouped subtable collections

See Also:
- [`topmark.core.typing_guards`][topmark.core.typing_guards]: generic type guards and normalization
  helpers for parsing weakly typed objects.
- [`topmark.toml.utils`][topmark.toml.utils]: small builders and normalization
  helpers for TOML-compatible values and tables.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import TypeGuard
from typing import cast

from tomlkit.items import Table

from topmark.core.logging import get_logger
from topmark.core.typing_guards import is_any_list
from topmark.core.typing_guards import is_mapping
from topmark.toml.types import TomlTable

if TYPE_CHECKING:
    from collections.abc import Mapping

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
