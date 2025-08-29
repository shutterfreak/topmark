# topmark:header:start
#
#   file         : diff.py
#   file_relpath : src/topmark/utils/diff.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Patch (diff) generation step for the TopMark pipeline.

This step compares the original file content with the pipeline's updated content
and produces a unified diff (header patch). It also formats a colorized preview
for logging and CLI display.
"""

import os
from typing import Sequence

from yachalk import chalk

from topmark.config.logging import get_logger

logger = get_logger(__name__)


def render_patch(patch: Sequence[str] | str, show_line_numbers: bool = False) -> str:
    """Render a colorized preview of a unified diff.

    Args:
        patch: A unified diff as **either** a list/sequence of lines **or** a single
            multiline string.
        show_line_numbers: Whether to prefix output with line numbers.

    Returns:
        The formatted, colorized diff preview.
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
        result = chalk.gray(
            "".join(f"{i:04d}|{process_line(line)}\n" for i, line in enumerate(lines, 1))
        )
    else:
        result = chalk.gray("".join(f"{process_line(line)}\n" for line in lines))
    return result


def write_patch(patch_content: str, output_path: str) -> None:
    """Write patch content to a file with overwrite protection.

    Prompts if the destination already exists and refuses to overwrite unless
    confirmed by the user.

    Args:
        patch_content: The full diff text to write.
        output_path: Destination path for the patch file.

    Returns:
        None.

    Raises:
        IOError: If an I/O error occurs during writing (reported to the user).
    """
    if os.path.exists(output_path):
        response = input(f"File '{output_path}' already exists. Overwrite? (y/n): ")
        if response.lower() not in ["y", "yes"]:
            print("Operation canceled: file was not overwritten.")
            return

    try:
        with open(output_path, "w", encoding="utf-8") as patch_file:
            patch_file.write(patch_content)
        print(f"Patch content successfully written to '{output_path}'")
    except FileNotFoundError:
        print(f"Error: The directory for '{output_path}' does not exist.")
    except IOError as e:
        print(f"An I/O error occurred while writing the file: {e}")
