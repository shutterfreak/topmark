# topmark:header:start
#
#   project      : TopMark
#   file         : markdown_rendering.py
#   file_relpath : src/topmark/cli_shared/markdown_rendering.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Rendering helpers for TopMark CLI.

This module contains pure helpers which prepare ready-to-emit messages for the CLI,
decoupling presentation format from CLI implementation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.config.logging import TopmarkLogger, get_logger

if TYPE_CHECKING:
    from topmark.diagnostic.machine.schemas import (
        MachineDiagnosticCounts,
        MachineDiagnosticEntry,
    )

logger: TopmarkLogger = get_logger(__name__)


def render_config_check_markdown(
    *,
    ok: bool,
    strict: bool,
    counts: MachineDiagnosticCounts,
    diagnostics: list[MachineDiagnosticEntry],
    config_files: list[str],
    verbosity_level: int,
) -> str:
    """Render `topmark config check` output as Markdown."""
    lines: list[str] = []
    lines.append("## topmark config check\n")
    status = "OK" if ok else "FAILED"

    # Summary
    lines.append("### Summary\n")
    lines.append(f"- **Status:** {status}")
    lines.append(f"- **Strict:** {str(strict).lower()}")
    lines.append(f"- **Errors:** {counts.error}")
    lines.append(f"- **Warnings:** {counts.warning}\n")

    # Diagnostics
    if diagnostics:
        lines.append("### Diagnostics\n")
        for d in diagnostics:
            lines.append(f"- **{d.level}**: {d.message}")
        lines.append("")

    # Config files
    if verbosity_level > 0:
        lines.append(f"### Config files processed ({len(config_files)})\n")
        for i, p in enumerate(config_files, start=1):
            lines.append(f"{i}. {p}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
