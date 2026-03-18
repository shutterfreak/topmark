# topmark:header:start
#
#   project      : TopMark
#   file         : unified_diff.py
#   file_relpath : src/topmark/rendering/unified_diff.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

r"""Patch (diff) generation step for the TopMark pipeline.

Unified diff rendering helpers (plain text).

This module contains small, backend-agnostic helpers for formatting unified diffs as plain text.

The pipeline may generate unified diff *data* elsewhere; this module only normalizes and formats
that diff for display (for example in logs or tests).

Notes:
    - Control characters such as CR/LF are escaped ("\\r", "\\n") so previews are stable.
    - This module does **not** perform ANSI styling.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence


def format_patch_plain(
    *,
    patch: Sequence[str] | str,
    show_line_numbers: bool = False,
) -> str:
    """Render a plain-text preview of a unified diff.

    Args:
        patch: A unified diff as either a list/sequence of lines or a single multiline string.
        show_line_numbers: Whether to prefix output with line numbers.

    Returns:
        The plain-text diff preview.
    """
    # Normalize input to a list of lines
    if isinstance(patch, str):
        lines: list[str] = patch.splitlines(keepends=False)
    else:
        # Convert to list so we can iterate more than once if needed.
        lines = list(patch)

    # Show control characters explicitly so previews are stable.
    def _escape_controls(line: str) -> str:
        content: str = line.replace("\r", "\\r").replace("\n", "\\n")
        return content

    # Optionally prefix each rendered line with a 4-digit line number.
    if show_line_numbers is True:
        result: str = "".join(
            f"{i:04d}|{_escape_controls(line)}\n" for i, line in enumerate(lines, 1)
        )
    else:
        result = "".join(f"{_escape_controls(line)}\n" for line in lines)
    return result
