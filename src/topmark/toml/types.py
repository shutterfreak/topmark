# topmark:header:start
#
#   project      : TopMark
#   file         : types.py
#   file_relpath : src/topmark/toml/types.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Shared TOML type aliases for TopMark TOML document handling.

These aliases model TOML-compatible in-memory structures used across parsing,
validation, and serialization. They intentionally exclude `None`, since TOML
has no null value — absent values must be omitted from tables rather than
represented explicitly.
"""

from __future__ import annotations

from typing import TypeAlias

TomlScalar: TypeAlias = str | int | float | bool
"""Scalar TOML value.

Represents the set of primitive values directly supported by TOML.
"""

TomlValue: TypeAlias = TomlScalar | list["TomlValue"] | dict[str, "TomlValue"]
"""Recursive TOML-compatible value.

A TOML value may be a scalar, a list of TOML values, or a nested table
represented as a dictionary. `None` is intentionally excluded — callers must
omit keys for absent values.
"""

TomlTable: TypeAlias = dict[str, TomlValue]
"""TOML table representation.

Represents a mapping from string keys to TOML values, corresponding to a
single TOML table ready for validation or serialization.
"""

TomlTableMap: TypeAlias = dict[str, TomlTable]
"""Mapping of table names to TOML tables.

Used for mappings whose values are TOML tables, including grouped top-level or nested tables,
where each key corresponds to a top-level table name and each value is a TOML table.
"""
