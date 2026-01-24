# topmark:header:start
#
#   project      : TopMark
#   file         : guards.py
#   file_relpath : src/topmark/config/io/guards.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Type guards and normalization helpers for TOML parsing.

This module provides `TypeGuard`-based predicates that help Pyright narrow runtime
values coming from TOML parsing (including `tomlkit` objects).

It also includes small, side-effect-free normalization helpers (e.g.
`as_toml_table`, `as_toml_table_map`) used to safely coerce arbitrary parsed values
into the plain-Python table shapes used by TopMark.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeGuard, cast

from tomlkit.items import Table

from topmark.config.logging import get_logger

if TYPE_CHECKING:
    from topmark.config.logging import TopmarkLogger

    from .types import TomlTable, TomlTableMap


logger: TopmarkLogger = get_logger(__name__)

# --- Type guards / narrowers: pure Python ---


def is_toml_table(obj: object) -> TypeGuard[TomlTable]:
    """Type guard for a TOML table‑like mapping.

    Args:
        obj (object): Value to test.

    Returns:
        TypeGuard[TomlTable]: ``True`` if ``obj`` is a ``dict[str, Any]``.
    """
    return isinstance(obj, dict)


def is_any_list(obj: object) -> TypeGuard[list[Any]]:
    """Type guard for a generic list value.

    Checks only that the value is a ``list``; does not validate item types.

    Args:
        obj (object): Value to test.

    Returns:
        TypeGuard[list[Any]]: True if obj is a list.
    """
    return isinstance(obj, list)


def is_str_list(obj: object) -> TypeGuard[list[str]]:
    """Type guard for a string list value.

    Checks that the value is a ``list[str]``.

    Args:
        obj (object): Value to test.

    Returns:
        TypeGuard[list[str]]: True if obj is a list[str].
    """
    return is_any_list(obj) and all(isinstance(x, str) for x in obj)


def is_mapping(obj: object) -> TypeGuard[Mapping[object, object]]:
    """Type guard for a Mapping value.

    Checks only that the value is a ``Mapping``; does not validate item types.

    Args:
        obj (object): Value to test.

    Returns:
        TypeGuard[Mapping[object, object]]: True if obj is a Mapping.
    """
    return isinstance(obj, Mapping)


# --- Type guards / narrowers: tomlkit-specific ---


def is_tomlkit_table(obj: object) -> TypeGuard[Table]:
    """Type guard for a `tomlkit.items.Table`.

    Args:
        obj (object): Value to test.

    Returns:
        TypeGuard[Table]: ``True`` if ``obj`` is a ``tomlkit.items.Table``.
    """
    return isinstance(obj, Table)


# --- Pure dict helpers (unchecked) ---


def get_table_value(table: TomlTable, key: str) -> TomlTable:
    """Extract a sub-table from a TOML table.

    Returns a new empty dict if the sub-table is missing or not a mapping.

    Args:
        table (TomlTable): Parent table mapping.
        key (str): Sub-table key.

    Returns:
        TomlTable: The sub-table if present and a mapping, otherwise an empty dict.
    """
    # Safely extract a sub-table (dict) from the TOML data
    value: Any | None = table.get(key)
    return value if is_toml_table(value) else {}


# --- “Casting / normalization” helpers ---


def as_toml_table(obj: object) -> TomlTable | None:
    """Return the object as a TOML table when possible.

    A TOML table is represented as ``dict[str, Any]`` in this module.

    Args:
        obj (object): Arbitrary object obtained from parsed TOML.

    Returns:
        TomlTable | None: ``obj`` cast to ``TomlTable`` when it is a ``dict``,
        otherwise ``None``.
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
        obj (object): Arbitrary object obtained from parsed TOML.

    Returns:
        TomlTableMap: A mapping with only ``str -> TomlTable`` entries. Non‑matching
        items are silently dropped.
    """
    out: TomlTableMap = {}
    if isinstance(obj, dict):
        obj_dict: TomlTable = cast("TomlTable", obj)  # narrow for Pyright
        for k, v in obj_dict.items():
            if isinstance(v, dict):
                out[k] = v
            else:
                logger.debug("Ignoring non-dict entry for key %s: %r", k, v)
    return out
