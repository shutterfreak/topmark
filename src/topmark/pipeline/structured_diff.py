# topmark:header:start
#
#   project      : TopMark
#   file         : structured_diff.py
#   file_relpath : src/topmark/pipeline/structured_diff.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Structured unified-diff rendering for contiguous TopMark edits.

This module renders a unified diff from explicit planned-edit metadata instead
of rediscovering the edit through a generic sequence comparison. The initial
implementation intentionally supports one contiguous splice only. Callers should
fall back to generic diff generation when no structured edit is available or
when multiple edits are present.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from topmark.pipeline.views import PlannedEdit


def _format_range_unified(*, start: int, length: int) -> str:
    """Format a zero-based range using unified-diff line-number conventions.

    Args:
        start: Zero-based start index in the file image.
        length: Number of lines in the range.

    Returns:
        str: Unified-diff range fragment without the leading ``+`` or ``-``.
    """
    beginning: int = start + 1
    if length == 0:
        beginning -= 1
    if length == 1:
        return str(beginning)
    return f"{beginning},{length}"


def render_structured_unified_diff(
    *,
    original_lines: Sequence[str],
    edit: PlannedEdit,
    fromfile: str,
    tofile: str,
    fromfiledate: str,
    tofiledate: str,
    lineterm: str,
    context: int = 3,
) -> list[str] | None:
    """Render a unified diff for a single contiguous splice.

    Args:
        original_lines: Original file image lines with line endings preserved.
        edit: Planned contiguous edit to render.
        fromfile: Label for the original file image.
        tofile: Label for the updated file image.
        fromfiledate: Timestamp label for the original image.
        tofiledate: Timestamp label for the updated image.
        lineterm: Line terminator used for diff control lines.
        context: Number of surrounding context lines.

    Returns:
        list[str] | None: Unified diff lines, or ``None`` when the edit is not
        representable as a safe single-splice diff.
    """
    if edit.old_start < 0 or edit.old_end < edit.old_start:
        return None
    if edit.old_end > len(original_lines):
        return None
    if context < 0:
        return None

    new_lines: tuple[str, ...] = edit.new_lines
    if edit.old_start == edit.old_end and not new_lines:
        return []

    prefix_start: int = max(0, edit.old_start - context)
    suffix_end: int = min(len(original_lines), edit.old_end + context)

    old_range_start: int = prefix_start
    old_range_length: int = suffix_end - prefix_start
    new_range_start: int = prefix_start
    new_range_length: int = (
        (edit.old_start - prefix_start) + len(new_lines) + (suffix_end - edit.old_end)
    )

    diff_lines: list[str] = [
        f"--- {fromfile}\t{fromfiledate}{lineterm}",
        f"+++ {tofile}\t{tofiledate}{lineterm}",
        (
            f"@@ -{_format_range_unified(start=old_range_start, length=old_range_length)} "
            f"+{_format_range_unified(start=new_range_start, length=new_range_length)} @@"
            f"{lineterm}"
        ),
    ]

    for line in original_lines[prefix_start : edit.old_start]:
        diff_lines.append(f" {line}")
    for line in original_lines[edit.old_start : edit.old_end]:
        diff_lines.append(f"-{line}")
    for line in new_lines:
        diff_lines.append(f"+{line}")
    for line in original_lines[edit.old_end : suffix_end]:
        diff_lines.append(f" {line}")

    return diff_lines
