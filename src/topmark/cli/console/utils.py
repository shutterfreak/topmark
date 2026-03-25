# topmark:header:start
#
#   project      : TopMark
#   file         : utils.py
#   file_relpath : src/topmark/cli/console/utils.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Small terminal-layout helpers for CLI console output."""

from __future__ import annotations

import shutil


def get_console_line_width(
    *,
    default: int = 80,
    max_width: int = 100,
) -> int:
    """Return a safe line width for human-facing console rendering.

    Args:
        default: Fallback terminal width when no terminal size is available.
        max_width: Upper bound applied to wide terminals to keep output readable.

    Returns:
        The smaller of the detected terminal width and `max_width`. If terminal
        size detection fails, `default` is used.
    """
    try:
        columns, _ = shutil.get_terminal_size(fallback=(default, 24))
    except OSError:
        columns: int = default
    return min(columns, max_width)
