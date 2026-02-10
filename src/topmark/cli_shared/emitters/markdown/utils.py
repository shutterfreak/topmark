# topmark:header:start
#
#   project      : TopMark
#   file         : utils.py
#   file_relpath : src/topmark/cli_shared/emitters/markdown/utils.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Markdown rendering utilities shared by CLI emitters.

This module provides Click-free helpers to render Markdown fragments that are
used by TopMark's human-facing output formats (e.g. ``OutputFormat.MARKDOWN``).

Scope:
- Pure string rendering only (no I/O, no Click/Rich console usage).
- Safe to import from any frontend (CLI, API tests, etc.).

The helpers here are intentionally small and composable; command-specific
formatting belongs in the command's emitter module.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence


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


def render_toml_markdown(*, heading: str, toml_text: str) -> str:
    """Render a Markdown H1 heading followed by a fenced TOML code block.

    Args:
        heading: Heading text without the leading ``#``.
        toml_text: TOML content to place inside the fenced code block.

    Returns:
        A Markdown string ending with a newline.
    """
    lines: list[str] = []
    lines.append(f"# {heading}")
    lines.append("")
    lines.append("```toml")
    lines.append(toml_text.rstrip("\n"))
    lines.append("```")
    return "\n".join(lines).rstrip() + "\n"
