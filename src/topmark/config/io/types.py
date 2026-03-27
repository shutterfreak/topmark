# topmark:header:start
#
#   project      : TopMark
#   file         : types.py
#   file_relpath : src/topmark/config/io/types.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Shared TOML-related type aliases for the config I/O package."""

from __future__ import annotations

from typing import TypeAlias

TomlValue: TypeAlias = str | int | float | bool | list["TomlValue"] | dict[str, "TomlValue"] | None
"""Define a recursive type for TOML-compatible structures.
This allows strings, bools, lists of TomlValue, or nested dicts.
"""


TomlTable: TypeAlias = dict[str, TomlValue]
"""Define the base shape of a TOML table once read in memory."""

TomlTableMap: TypeAlias = dict[str, TomlTable]
"""TODO docstring"""
