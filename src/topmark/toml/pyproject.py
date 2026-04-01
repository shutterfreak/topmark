# topmark:header:start
#
#   project      : TopMark
#   file         : pyproject.py
#   file_relpath : src/topmark/toml/pyproject.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Helpers for extracting TopMark TOML content from `pyproject.toml`.

This module contains small, schema-aware helpers for locating TopMark's
`[tool.topmark]` table inside a parsed `pyproject.toml` document.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.core.logging import get_logger

if TYPE_CHECKING:
    from topmark.core.logging import TopmarkLogger
    from topmark.toml.types import TomlTable
    from topmark.toml.types import TomlValue


logger: TopmarkLogger = get_logger(__name__)


def extract_pyproject_topmark_table(data: TomlTable) -> TomlTable | None:
    """Return the `[tool.topmark]` table from a parsed `pyproject.toml` mapping.

    Args:
        data: Parsed TOML document mapping.

    Returns:
        The nested `[tool.topmark]` table if present and well-formed;
        otherwise `None`.
    """
    tool_section: TomlValue | None = data.get("tool")
    if not isinstance(tool_section, dict):
        return None

    topmark_section: TomlValue | None = tool_section.get("topmark")
    if not isinstance(topmark_section, dict):
        return None

    return topmark_section
