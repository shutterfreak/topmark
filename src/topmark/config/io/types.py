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

from enum import Enum
from typing import TypeAlias

TomlValue: TypeAlias = str | int | float | bool | list["TomlValue"] | dict[str, "TomlValue"] | None
"""Define a recursive type for TOML-compatible structures.
This allows strings, bools, lists of TomlValue, or nested dicts.
"""


TomlTable: TypeAlias = dict[str, TomlValue]
"""Define the base shape of a TOML table once read in memory."""

TomlTableMap: TypeAlias = dict[str, TomlTable]
"""Mapping of TOML subtable names to TOML tables."""


class FilesSerializationMode(str, Enum):
    """How to serialize the `[files]` section when exporting configuration.

    Modes:
        REBASED:
            Emit flattened lists that are meaningful from the current working directory (CWD),
            e.g. `[files].include_patterns`, `[files].exclude_patterns`, and `*_from` path lists.
            This is the default “as seen from here” view used for copy/paste friendly dumps.

        ORIGIN:
            Emit provenance-oriented structured tables that retain each declaring base directory,
            e.g. `[[files.*_pattern_groups]]` and `[[files.*_from_sources]]`. In this mode, the
            flattened lists are omitted.
    """

    REBASED = "rebased"
    ORIGIN = "origin"
