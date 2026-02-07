# topmark:header:start
#
#   project      : TopMark
#   file         : markdown.py
#   file_relpath : src/topmark/cli_shared/markdown.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Markdown utilities for TopMark."""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.config.logging import TopmarkLogger, get_logger

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

logger: TopmarkLogger = get_logger(__name__)

# --- Markdown rendering helpers ---------------------------------------------


def render_markdown_table(
    headers: Sequence[str],
    rows: Sequence[Sequence[str]],
    *,
    align: Mapping[int, str] | None = None,
) -> str:
    """Render a GitHub‑flavoured Markdown table with padded columns.

    Args:
        headers: Column headers.
        rows: A sequence of row sequences (each row same length
            as ``headers``).
        align: Optional mapping of column index to alignment:
            ``"left"`` (default), ``"right"``, or ``"center"``.

    Returns:
        The Markdown table as a single string (ending with a newline).

    Notes:
        - Widths are computed from the visible string lengths of headers and cells.
        - Alignment uses Markdown syntax: ``:---`` (left), ``:---:`` (center), ``---:`` (right).
        - This function is Click‑free and suitable for reuse in any frontend.

    Raises:
        ValueError: If any row length differs from the number of headers.
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
