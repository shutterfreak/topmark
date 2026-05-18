# topmark:header:start
#
#   project      : TopMark
#   file         : conftest.py
#   file_relpath : tests/presentation/conftest.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Shared helpers for presentation rendering tests.

The helpers in this module intentionally focus on semantic assertions for
rendered Markdown tables. They normalize table-cell spacing so tests can verify
row shape and cell values without depending on formatter-specific padding.
"""

from __future__ import annotations


def table_cells(row: str) -> list[str]:
    """Return normalized Markdown table cells without outer separators."""
    return [cell.strip() for cell in row.strip().strip("|").split("|")]


def find_table_row(output: str, marker: str) -> list[str]:
    """Return normalized cells for the first Markdown table row containing `marker`.

    Non-table lines are ignored so prose, legends, headings, and bullet lists do
    not accidentally satisfy table assertions.
    """
    row: str = next(
        line for line in output.splitlines() if line.lstrip().startswith("|") and marker in line
    )
    return table_cells(row)
