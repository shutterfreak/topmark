# topmark:header:start
#
#   project      : TopMark
#   file         : diff.py
#   file_relpath : src/topmark/utils/diff.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Patch (diff) generation step for the TopMark pipeline.

This step compares the original file content with the pipeline's updated content
and produces a unified diff (header patch). It also formats a colorized preview
for logging and CLI display.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from yachalk import chalk

from topmark.config.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Sequence

    from topmark.config.logging import TopmarkLogger

logger: TopmarkLogger = get_logger(__name__)


def render_patch(patch: Sequence[str] | str, show_line_numbers: bool = False) -> str:
    """Render a colorized preview of a unified diff.

    Args:
        patch (Sequence[str] | str): A unified diff as **either** a list/sequence of lines
            **or** a single multiline string.
        show_line_numbers (bool): Whether to prefix output with line numbers.

    Returns:
        str: The formatted, colorized diff preview.
    """
    # Normalize input to a list of lines
    if isinstance(patch, str):
        lines: list[str] = patch.splitlines(keepends=False)
    else:
        # Convert to list to allow multiple passes
        lines = list(patch)

    # Map diff markers to colors and show control characters explicitly.
    def process_line(line: str) -> str:
        # Handle the line content first
        content = line.replace("\r", "\\r").replace("\n", "\\n")

        result: str = ""
        # Use match to determine the color
        match line[0]:
            case "-":
                result = chalk.bold.red(content)
                return result
            case "+":
                result = chalk.bold.green(content)
                return result
            case "?":
                result = chalk.yellow(content)
                return result
            case _:  # The catch-all case for all other lines
                result = chalk.bold.white(content)
                return result

    # Optionally prefix each rendered line with a 4-digit line number.
    if show_line_numbers is True:
        result: str = chalk.gray(
            "".join(f"{i:04d}|{process_line(line)}\n" for i, line in enumerate(lines, 1))
        )
    else:
        result = chalk.gray("".join(f"{process_line(line)}\n" for line in lines))
    return result
