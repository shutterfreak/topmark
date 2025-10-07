# topmark:header:start
#
#   project      : TopMark
#   file         : io.py
#   file_relpath : src/topmark/config/io.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Lightweight I/O helpers for TopMark configuration.

This module centralizes small, **pure** functions used by the configuration
layer to read/write TOML content. Keeping these helpers in a separate module
ensures a clean separation of concerns:

- `topmark.config.__init__` contains only data models and merge logic
  (``MutableConfig`` builder and frozen ``Config`` snapshot).
- This module contains small utilities to *load* packaged defaults, *load*
  external TOML files, and *normalize* TOML text without retaining comments.

These functions are deliberately side-effect free and do not mutate the
configuration models. They can be unit-tested in isolation.
"""

from __future__ import annotations

from importlib.resources import files
from typing import TYPE_CHECKING, Any, TypeGuard

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


# Type guards
def is_str_any_dict(val: Any) -> TypeGuard[dict[str, Any]]:
    """Type guard for a TOML table-like mapping.

    Args:
        val (Any): Value to test.

    Returns:
        TypeGuard[dict[str, Any]]: True if val is a dict[str, Any].
    """
    return isinstance(val, dict)


def is_any_list(val: Any) -> TypeGuard[list[Any]]:
    """Type guard for a generic list value.

    Args:
        val (Any): Value to test.

    Returns:
        TypeGuard[list[Any]]: True if val is a list.
    """
    return isinstance(val, list)


# Helpers
def get_table_value(table: dict[str, Any], key: str) -> dict[str, Any]:
    """Extract a sub-table from a TOML table.

    Args:
        table (dict[str, Any]): Parent table mapping.
        key (str): Sub-table key.

    Returns:
        dict[str, Any]: The sub-table if present and a mapping, otherwise an empty dict.
    """
    # Safely extract a sub-table (dict) from the TOML data
    value: Any | None = table.get(key)
    return value if is_str_any_dict(value) else {}


def get_string_value(table: dict[str, Any], key: str, default: str = "") -> str:
    """Extract a string value from a TOML table.

    If the value is not a string but is an ``int``, ``float``, or ``bool``, it is
    coerced to a string. When the key is missing or the value is not coercible,
    ``default`` is returned.

    Args:
        table (dict[str, Any]): Table to query.
        key (str): Key to extract.
        default (str): Default value if the key is not found.

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


def get_string_value_or_none(table: dict[str, Any], key: str) -> str | None:
    """Extract an optional string value from a TOML table.

    If the value is an ``int``, ``float``, or ``bool``, it is coerced to a string.
    When the key is missing, ``None`` is returned.

    Args:
        table (dict[str, Any]): Table to query.
        key (str): Key to extract.

    Returns:
        str | None: The extracted or coerced string value, or ``None`` when absent.
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


def get_bool_value(table: dict[str, Any], key: str, default: bool = False) -> bool:
    """Extract a boolean value from a TOML table.

    If the value is an integer, it is coerced via ``bool(value)``. When the key is
    missing or not coercible, ``default`` is returned.

    Args:
        table (dict[str, Any]): Table to query.
        key (str): Key to extract.
        default (bool): Default value if the key is not found.

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


def get_bool_value_or_none(table: dict[str, Any], key: str) -> bool | None:
    """Extract an optional boolean value from a TOML table.

    If the value is an integer, it is coerced via ``bool(value)``. When the key is
    missing, ``None`` is returned.

    Args:
        table (dict[str, Any]): Table to query.
        key (str): Key to extract.

    Returns:
        bool | None: The extracted or coerced boolean value, or ``None`` when absent.
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


def get_list_value(table: dict[str, Any], key: str, default: list[Any] | None = None) -> list[Any]:
    """Extract a list value from a TOML table.

    If the key is present and the value is a list, it is returned unchanged;
    otherwise, ``default`` is returned (or ``[]`` when ``default`` is ``None``).

    Args:
        table (dict[str, Any]): Table to query.
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


def load_defaults_dict() -> dict[str, Any]:
    """Return the packaged default configuration as a Python dict.

    The default TOML is shipped as a package resource (see
    ``DEFAULT_TOML_CONFIG_RESOURCE``). This function reads the resource
    and parses it into a dictionary using ``toml``.

    Returns:
        dict[str, Any]: The parsed default configuration.
    """
    res: Traversable = files("topmark.config") / DEFAULT_TOML_CONFIG_RESOURCE
    logger.debug("Loading defaults from package resource: %s", res)

    return toml.loads(res.read_text(encoding="utf-8"))


def load_toml_dict(path: "Path") -> dict[str, Any]:
    """Load and parse a TOML file from the filesystem.

    Args:
        path (Path): Path to a TOML document (e.g., ``topmark.toml`` or
            ``pyproject.toml``).

    Returns:
        dict[str, Any]: The parsed TOML content.
    """
    try:
        val: dict[str, Any] = toml.load(path)
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

    This is useful for presenting a canonicalized view of a TOML document,
    for example in ``topmark dump-config`` outputs or for snapshotting.

    Args:
        text (str): Raw TOML content.

    Returns:
        str: A normalized TOML string produced by round-tripping through the
            TOML parser and dumper.
    """
    # Parse the default config TOML and re-dump it to normalize formatting
    return toml.dumps(toml.loads(text))


def to_toml(toml_dict: dict[str, Any]) -> str:
    """Serialize a TOML mapping to a string.

    Args:
        toml_dict (dict[str, Any]): TOML mapping to render.

    Returns:
        str: The rendered TOML document as a string.
    """
    return toml.dumps(toml_dict)
