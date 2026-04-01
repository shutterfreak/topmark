# topmark:header:start
#
#   project      : TopMark
#   file         : utils.py
#   file_relpath : src/topmark/toml/utils.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Small helpers for building TOML-compatible tables.

These helpers keep TOML construction code concise while preserving the strict
invariant enforced by [`TomlValue`][topmark.toml.types.TomlValue]: absent values
must be omitted from tables rather than represented explicitly as `None`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from topmark.toml.types import TomlTable
    from topmark.toml.types import TomlValue


def insert_if_present(table: TomlTable, key: str, value: TomlValue | None) -> None:
    """Insert a TOML key only when a value is present.

    Args:
        table: TOML table being constructed.
        key: TOML key to insert.
        value: TOML value to store. When `None`, the key is omitted.
    """
    if value is not None:
        table[key] = value
