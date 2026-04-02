# topmark:header:start
#
#   project      : TopMark
#   file         : utils.py
#   file_relpath : src/topmark/toml/utils.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Small helpers for building and normalizing TopMark TOML values and tables.

These helpers keep TOML construction and rendering code concise while
preserving the strict invariant enforced by
[`TomlValue`][topmark.toml.types.TomlValue]: absent values must be omitted from
TopMark TOML tables rather than represented explicitly as `None`.

This module also contains small, side-effect-free builders for TOML-compatible
list values whose static types remain compatible with `TomlValue` under Pyright
strict mode.
"""

from __future__ import annotations

from collections.abc import Iterable
from collections.abc import Mapping
from typing import TYPE_CHECKING
from typing import cast

from topmark.core.logging import get_logger
from topmark.toml.types import TomlTable

if TYPE_CHECKING:
    from topmark.core.logging import TopmarkLogger
    from topmark.toml.types import TomlTable
    from topmark.toml.types import TomlValue

logger: TopmarkLogger = get_logger(__name__)


def insert_if_present(table: TomlTable, key: str, value: TomlValue | None) -> None:
    """Insert a TOML key only when a value is present.

    Args:
        table: TOML table being constructed.
        key: TOML key to insert.
        value: TOML value to store. When `None`, the key is omitted.
    """
    if value is not None:
        table[key] = value


def strip_none_for_toml(value: object) -> object:
    """Remove TOML-incompatible `None` values from nested TOML-shaped data.

    TOML has no `null`. During rendering, keys with `None` values are omitted
    and `None` items are dropped from lists.

    Notes:
        - The input is typed as `object` (not `Any`) so Pyright does not treat
        mapping/list iterators as `Unknown`.
        - Mapping keys are defensively normalized to strings, since TOML tables
        are string-keyed.
    """
    # Recursively normalize mappings/lists into TOML-compatible plain-Python
    # shapes while dropping `None` entries.
    if isinstance(value, Mapping):
        out: dict[str, object] = {}
        m: Mapping[object, object] = cast("Mapping[object, object]", value)
        for k_any, v_any in m.items():
            if v_any is None:
                logger.debug("Ignoring `None` entry in Mapping for key %s", k_any)
                continue
            k: str = k_any if isinstance(k_any, str) else str(k_any)
            out[k] = strip_none_for_toml(v_any)
        return out

    if isinstance(value, list):
        out_list: list[object] = []
        seq: list[object] = cast("list[object]", value)
        for v_any in seq:
            if v_any is None:
                logger.debug("Ignoring `None` entry in list")
                continue
            out_list.append(strip_none_for_toml(v_any))
        return out_list

    return value


def as_toml_string_list(values: Iterable[str]) -> list[TomlValue]:
    """Return a TOML-compatible list of strings.

    Pyright treats `list[str]` as incompatible with the recursive `TomlValue`
    alias because `list` is invariant. Building the list through the wider
    element type keeps TOML serializer code strict-typing friendly without
    casts.

    Args:
        values: String values to expose as a TOML-compatible list.

    Returns:
        A list whose static type is compatible with `TomlValue`.
    """
    result: list[TomlValue] = list(values)
    return result


def as_toml_table_list(values: Iterable[TomlTable]) -> list[TomlValue]:
    """Return a TOML-compatible list of TOML tables.

    This helper mirrors `as_toml_string_list`, but for iterables of TOML
    tables that need to be stored in a list position accepted by `TomlValue`.

    Args:
        values: TOML tables to expose as a TOML-compatible list.

    Returns:
        A list whose static type is compatible with `TomlValue`.
    """
    result: list[TomlValue] = list(values)
    return result
