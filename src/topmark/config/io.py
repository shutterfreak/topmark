# topmark:header:start
#
#   project      : TopMark
#   file         : io.py
#   file_relpath : src/topmark/config/io.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Lightweight TOML I/O helpers for TopMark configuration.

This module centralizes **pure** helpers for reading and writing TOML used by
TopMark's configuration layer. Keeping these utilities separate avoids import
cycles and keeps the model classes small and focused.

Design goals:
    * Minimal side effects: functions **do not** mutate configuration objects.
    * Clear typing: public helpers use small aliases (``TomlTable``, ``TomlTableMap``)
      and TypeGuards where possible to help Pyright catch mistakes.
    * Reusability: functions are used by both CLI and API paths.

Typical flow:
    1. Load defaults from the packaged resource (``load_defaults_dict``).
    2. Load project/user TOML files (``load_toml_dict``).
    3. Normalize and inspect values using typed helpers
       (``get_table_value``, ``get_string_value``, etc.).
    4. Serialize back to TOML when needed (``to_toml``).
"""

from __future__ import annotations

from importlib.resources import files
from typing import TYPE_CHECKING, Any, TypeGuard, cast

import toml

from topmark.config.logging import TopmarkLogger, get_logger
from topmark.constants import DEFAULT_TOML_CONFIG_RESOURCE

if TYPE_CHECKING:
    import sys

    if sys.version_info >= (3, 14):
        # Python 3.14+: Traversable moved here
        from importlib.resources.abc import Traversable
    else:
        # Python <=3.13
        from importlib.abc import Traversable
    from pathlib import Path

logger: TopmarkLogger = get_logger(__name__)

TomlTable = dict[str, Any]
TomlTableMap = dict[str, TomlTable]

__all__: list[str] = [
    "TomlTable",
    "TomlTableMap",
    "as_toml_table",
    "as_toml_table_map",
    "is_toml_table",
    "is_any_list",
    "get_table_value",
    "get_string_value",
    "get_string_value_or_none",
    "get_bool_value",
    "get_bool_value_or_none",
    "get_list_value",
    "load_defaults_dict",
    "load_toml_dict",
    "clean_toml",
    "to_toml",
]


def as_toml_table(obj: object) -> TomlTable | None:
    """Return the object as a TOML table when possible.

    A TOML table is represented as ``dict[str, Any]`` in this module.

    Args:
        obj (object): Arbitrary object obtained from parsed TOML.

    Returns:
        TomlTable | None: ``obj`` cast to ``TomlTable`` when it is a ``dict``,
        otherwise ``None``.
    """
    return obj if isinstance(obj, dict) else None  # type: ignore[return-value]


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
    return out


def is_toml_table(val: Any) -> TypeGuard[TomlTable]:
    """Type guard for a TOML table‑like mapping.

    Args:
        val (Any): Value to test.

    Returns:
        TypeGuard[TomlTable]: ``True`` if ``val`` is a ``dict[str, Any]``.
    """
    return isinstance(val, dict)


def is_any_list(val: Any) -> TypeGuard[list[Any]]:
    """Type guard for a generic list value.

    Checks only that the value is a ``list``; does not validate item types.

    Args:
        val (Any): Value to test.

    Returns:
        TypeGuard[list[Any]]: True if val is a list.
    """
    return isinstance(val, list)


# Helpers
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


def get_string_value(table: TomlTable, key: str, default: str = "") -> str:
    """Extract a string value from a TOML table.

    If the value is a ``str``, it is returned as is. If the value is of type
    ``int``, ``float``, or ``bool``, it is coerced to a string using ``str(...)``.
    When the key is missing or the value is not coercible, ``default`` is returned.

    Args:
        table (TomlTable): Table to query.
        key (str): Key to extract.
        default (str): Default value if the key is not found or not coercible.

    Returns:
        str: The extracted or coerced string value, or ``default``.
    """
    # Coerce various types to string if possible; fallback to default
    value: Any | None = table.get(key)
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    return default


def get_string_value_or_none(table: TomlTable, key: str) -> str | None:
    """Extract an optional string value from a TOML table.

    If the value is a ``str``, it is returned as is. If the value is of type
    ``int``, ``float``, or ``bool``, it is coerced to a string using ``str(...)``.
    When the key is missing, ``None`` is returned. If the key is present but
    the value is not coercible, ``None`` is returned.

    Args:
        table (TomlTable): Table to query.
        key (str): Key to extract.

    Returns:
        str | None: The extracted or coerced string value, or ``None`` when absent or not coercible.
    """
    # Coerce various types to string if possible
    value: Any | None = table.get(key)
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    return None


def get_bool_value(table: TomlTable, key: str, default: bool = False) -> bool:
    """Extract a boolean value from a TOML table.

    If the value is a ``bool``, it is returned as is. If the value is an integer,
    it is coerced via ``bool(value)``. When the key is missing or the value is not
    coercible, ``default`` is returned.

    Args:
        table (TomlTable): Table to query.
        key (str): Key to extract.
        default (bool): Default value if the key is not found or not coercible.

    Returns:
        bool: The extracted or coerced boolean value, or ``default``.
    """
    # Extract boolean value, coercing int to bool if needed; fallback to default
    value: Any | None = table.get(key)
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return bool(value)
    return default


def get_bool_value_or_none(table: TomlTable, key: str) -> bool | None:
    """Extract an optional boolean value from a TOML table.

    If the value is a ``bool``, it is returned as is. If the value is an integer,
    it is coerced via ``bool(value)``. When the key is missing, ``None`` is returned.
    If the key is present but not coercible, ``None`` is returned.

    Args:
        table (TomlTable): Table to query.
        key (str): Key to extract.

    Returns:
        bool | None: The extracted or coerced boolean value, or ``None``
            when absent or not coercible.
    """
    # Extract boolean value, coercing int to bool if needed
    value: Any | None = table.get(key)
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return bool(value)
    return None


def get_list_value(table: TomlTable, key: str, default: list[Any] | None = None) -> list[Any]:
    """Extract a list value from a TOML table.

    If the key is present and the value is a list, it is returned (shallow copy;
    no item-level validation).
    Otherwise, ``default`` is returned (or ``[]`` when ``default`` is ``None``).

    Args:
        table (TomlTable): Table to query.
        key (str): Key to extract.
        default (list[Any] | None): Default list when the key is missing or not a list.

    Returns:
        list[Any]: The list value, ``default``, or an empty list.
    """
    # Extract list value, ensure list type or fallback to default
    value: Any | None = table.get(key)
    if is_any_list(value):
        return value
    return default or []


def load_defaults_dict() -> TomlTable:
    """Return the packaged default configuration as a Python dict.

    Reads from ``DEFAULT_TOML_CONFIG_RESOURCE`` in the ``topmark.config`` package.
    May log errors and returns an empty dict on failure.

    Returns:
        TomlTable: The parsed default configuration.
    """
    res: Traversable = files("topmark.config") / DEFAULT_TOML_CONFIG_RESOURCE
    logger.debug("Loading defaults from package resource: %s", res)

    return toml.loads(res.read_text(encoding="utf-8"))


def load_toml_dict(path: "Path") -> TomlTable:
    """Load and parse a TOML file from the filesystem.

    Args:
        path (Path): Path to a TOML document (e.g., ``topmark.toml`` or
            ``pyproject.toml``).

    Returns:
        TomlTable: The parsed TOML content.

    Notes:
        - Errors are logged and an empty dict is returned on failure.
        - Encoding is assumed to be UTF‑8.
    """
    try:
        val: TomlTable = toml.load(path)
    except IOError as e:
        logger.error("Error loading TOML from %s: %s", path, e)
        val = {}
    except toml.TomlDecodeError as e:
        logger.error("Error decoding TOML from %s: %s", path, e)
        val = {}
    except Exception as e:
        logger.error("Unknown error while reading TOML from %s: %s", path, e)
        val = {}
    return val


def clean_toml(text: str) -> str:
    """Normalize a TOML document, removing comments and formatting noise.

    This function round-trips the input through the ``toml`` parser and dumper,
    dropping comments and normalizing formatting. Useful for presenting a canonicalized
    view (e.g., ``topmark dump-config``) or for snapshotting.

    Args:
        text (str): Raw TOML content.

    Returns:
        str: A normalized TOML string produced by round-tripping through the
            TOML parser and dumper.
    """
    # Parse the default config TOML and re-dump it to normalize formatting
    return toml.dumps(toml.loads(text))


def to_toml(toml_dict: TomlTable) -> str:
    """Serialize a TOML mapping to a string.

    Args:
        toml_dict (TomlTable): TOML mapping to render.

    Returns:
        str: The rendered TOML document as a string.
    """
    return toml.dumps(toml_dict)
