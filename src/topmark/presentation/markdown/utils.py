# topmark:header:start
#
#   project      : TopMark
#   file         : utils.py
#   file_relpath : src/topmark/presentation/markdown/utils.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Shared presentation utilities for MARKDOWN.

This module provides helpers to render Markdown fragments.

Scope:
- Pure string rendering only (no I/O, no Click/Rich console usage).
- Safe to import from any frontend (CLI, API tests, etc.).

The helpers here are intentionally small and composable; command-specific
formatting belongs in the command's presentation module.
"""

from __future__ import annotations

import re
import typing

if typing.TYPE_CHECKING:
    from collections.abc import Mapping
    from collections.abc import Sequence


def markdown_code_span(text: str) -> str:
    """Render `text` as a Markdown inline code span.

    This chooses a backtick fence that is one longer than the longest run of
    backticks in `text`, which safely supports filenames that contain backticks.

    Args:
        text: Raw text to wrap.

    Returns:
        Markdown inline code span.
    """
    max_run: int = 0
    run: int = 0
    for ch in text:
        if ch == "`":
            run += 1
            if run > max_run:
                max_run = run
        else:
            run = 0

    fence: str = "`" * (max_run + 1)
    return f"{fence}{text}{fence}"


def markdown_escape(text: str) -> str:
    """Safely render `text` as backticked str."""
    # Find the longest sequence of backticks in the input
    backtick_sequences = re.findall(r"`+", text)
    max_backticks: int = len(max(backtick_sequences, key=len)) if backtick_sequences else 0

    # Use one more backtick than the max sequence found
    fence: str = "`" * (max_backticks + 1)

    # Add padding spaces if the text starts or ends with a backtick
    padding: str = " " if text.startswith("`") or text.endswith("`") else ""

    return f"{fence}{padding}{text}{padding}{fence}"


def render_markdown_table(
    headers: Sequence[str],
    rows: Sequence[Sequence[str]],
    *,
    align: Mapping[int, str] | None = None,
) -> str:
    """Render a GitHub-flavoured Markdown table with padded columns.

    Args:
        headers: Column headers.
        rows: Table rows. Each row must have the same number of columns as ``headers``.
        align: Optional mapping of column index to alignment: ``"left"`` (default),
            ``"right"``, or ``"center"``.

    Returns:
        The Markdown table as a single string, ending with a newline.

    Notes:
        - Widths are computed from the visible string lengths of headers and cells.
        - Alignment uses Markdown syntax: ``:---`` (left), ``:---:`` (center), ``---:`` (right).
        - This function is pure string rendering and suitable for reuse in any frontend.

    Raises:
        ValueError: If any row has a different number of columns than ``headers``.
    """
    if not headers:
        return ""
    ncols: int = len(headers)
    for r in rows:
        if len(r) != ncols:
            raise ValueError("All rows must have the same number of columns as headers")

    # Compute column widths
    widths: list[int] = [len(str(h)) for h in headers]
    for r in rows:
        for i, cell in enumerate(r):
            widths[i] = max(widths[i], len(str(cell)))

    def _pad(text: str, w: int) -> str:
        return f"{text:<{w}}"

    # Header line
    header_line: str = " | ".join(_pad(str(headers[i]), widths[i]) for i in range(ncols))

    # Separator line with alignment markers
    def _sep_for(i: int) -> str:
        style: str = (align or {}).get(i, "left").lower()
        w: int = max(1, widths[i])
        if style == "right":
            return "-" * (w - 1) + ":" if w > 1 else ":"
        if style == "center":
            return ":" + ("-" * (w - 2) if w > 2 else "-") + ":"
        # left/default
        return "-" * w

    sep_line: str = " | ".join(_sep_for(i) for i in range(ncols))

    # Data lines
    data_lines: list[str] = [
        " | ".join(_pad(str(r[i]), widths[i]) for i in range(ncols)) for r in rows
    ]

    return (
        "| "
        + header_line
        + " |\n"
        + "| "
        + sep_line
        + " |\n"
        + "\n".join("| " + line + " |" for line in data_lines)
        + "\n"
    )


def render_toml_markdown(
    *,
    toml_text: str,
    heading: str | None,
    heading_level: int = 2,
) -> str:
    """Render a Markdown heading followed by a fenced TOML code block.

    Args:
        toml_text: TOML content to place inside the fenced code block.
        heading: Optional heading text without the leading '#'.
        heading_level: Heading level (normalized to 1..6).

    Returns:
        A Markdown string ending with a newline.
    """
    lines: list[str] = []

    if heading:
        level: int = max(1, min(heading_level, 6))
        lines.append(f"{'#' * level} {heading}\n")

    # Handle nested fences: find the longest backtick chain
    backtick_matches = re.findall(r"`{3,}", toml_text)
    fence_len: int = max([len(m) for m in backtick_matches] + [2]) + 1
    fence: str = "`" * fence_len

    lines.append(f"{fence}toml")
    lines.append(toml_text.strip("\n"))
    lines.append(fence)

    return "\n".join(lines) + "\n"
