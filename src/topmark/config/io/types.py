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

from typing import Any

TomlTable = dict[str, Any]
TomlTableMap = dict[str, TomlTable]
