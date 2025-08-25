# topmark:header:start
#
#   file         : patcher.py
#   file_relpath : src/topmark/pipeline/steps/patcher.py
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

from yachalk import chalk

from topmark.config.logging import get_logger
from topmark.pipeline.context import ComparisonStatus, ProcessingContext

logger = get_logger(__name__)


def patch(ctx: ProcessingContext) -> ProcessingContext:
    """Generate and attach a unified diff to the processing context.

    The step runs only when the comparison status is either ``CHANGED`` or
    ``UNCHANGED``. For unchanged inputs, the diff is empty and the status is
    normalized to ``UNCHANGED``.

    Args:
        ctx: The processing context holding original/updated lines and statuses.

    Returns:
        ProcessingContext: The same context with ``header_diff`` set when a
        change is detected, and with comparison status updated.
    """
    # Safeguard: Only run when comparison was performed
    if ctx.status.comparison not in [
        ComparisonStatus.CHANGED,
        ComparisonStatus.UNCHANGED,
    ]:
        return ctx

    logger.debug(
        "File '%s' : header status %s, header comparison status: %s",
        ctx.path,
        ctx.status.header.value,
        ctx.status.comparison.value,
    )

    # Generate unified diff using the actual lines from the file for the existing header
    import difflib

    logger.trace("Current file lines: %d: %r", len(ctx.file_lines or []), ctx.file_lines)
    logger.trace(
        "Updated file lines: %d: %r",
        len(ctx.updated_file_lines or []),
        ctx.updated_file_lines,
    )

    patch_lines = list(
        difflib.unified_diff(
            ctx.file_lines or [],
            ctx.updated_file_lines or [],
            fromfile=f"{ctx.path} (current)",
            tofile=f"{ctx.path} (updated)",
            n=3,
            lineterm=ctx.newline_style,
        )
    )

    if len(patch_lines) == 0:
        ctx.status.comparison = ComparisonStatus.UNCHANGED
        logger.debug("File header unchanged: %s", ctx.path)
        return ctx

    logger.info("Patch (rendered):\n%s", render_patch(patch_lines))

    # Join exactly as produced by difflib. Do not introduce CRLF conversions.
    ctx.header_diff = "".join(patch_lines)

    # write_patch(context.header_diff, context.path.as_posix() + ".diff")

    logger.debug(
        "\n===DIFF START ===\n%s=== DIFF END ===",
        chalk.yellow_bright.bg_blue(ctx.header_diff),
    )

    # Note: this step does not print; the CLI decides how to display diffs.

    return ctx


def render_patch(patch: list[str], show_line_numbers: bool = False) -> str:
    """Render a colorized preview of a unified diff.

    Args:
        patch: Lines of a unified diff as produced by :func:`difflib.unified_diff`.
        show_line_numbers: Whether to prefix output with line numbers.

    Returns:
        str: The formatted, colorized diff preview.
    """

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
    result: str
    if show_line_numbers is True:
        result = chalk.gray(
            "".join(f"{i:04d}|{process_line(line)}\n" for i, line in enumerate(patch, 1))
        )
    else:
        result = chalk.gray("".join(f"{process_line(line)}\n" for line in patch))
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
