# topmark:header:start
#
#   project      : TopMark
#   file         : utils.py
#   file_relpath : src/topmark/presentation/formatters/utils.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Shared presentation helpers."""

from __future__ import annotations


def bool_to_str(value: bool) -> str:
    """Render a boolean value as string.

    Represents ``True``as `'true'` and ``False`` as `'false'`.
    """
    return "true" if value else "false"
