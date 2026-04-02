# topmark:header:start
#
#   project      : TopMark
#   file         : enums.py
#   file_relpath : src/topmark/toml/enums.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Enums for TopMark TOML export and rendering helpers.

This module contains small enums that influence how TopMark TOML documents or
TOML tables are serialized for export, debugging, or copy/paste-friendly CLI
output.
"""

from __future__ import annotations

from enum import Enum


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
