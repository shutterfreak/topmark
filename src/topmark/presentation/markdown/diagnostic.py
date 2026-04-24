# topmark:header:start
#
#   project      : TopMark
#   file         : diagnostic.py
#   file_relpath : src/topmark/presentation/markdown/diagnostic.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Markdown diagnostic rendering helpers for CLI-shared emitters.

This module contains Click-free helpers that render diagnostics as Markdown for
human-facing output (`OutputFormat.MARKDOWN`). These helpers are intentionally
kept independent from machine formats.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.cli.keys import CliShortOpt
from topmark.diagnostic.model import DiagnosticLevel
from topmark.diagnostic.model import DiagnosticLog
from topmark.diagnostic.model import DiagnosticStats
from topmark.diagnostic.model import FrozenDiagnosticLog
from topmark.diagnostic.model import compute_diagnostic_stats

if TYPE_CHECKING:
    from topmark.presentation.shared.config import HumanDiagnosticLine
    from topmark.presentation.shared.diagnostic import HumanDiagnosticCounts


def render_human_diagnostics_markdown(
    *,
    title: str,
    counts: HumanDiagnosticCounts,
    diagnostics: list[HumanDiagnosticLine],
    verbosity_level: int,
) -> str:
    """Render human diagnostics as Markdown from prepared data.

    Args:
        title: Section heading.
        counts: Aggregated human-facing diagnostic counts.
        diagnostics: Prepared human-facing diagnostic lines.
        verbosity_level: Effective verbosity for gating extra details.

    Returns:
        Markdown fragment string (may be empty). Includes a trailing newline when non-empty.
    """
    if not diagnostics:
        return ""

    summary: str = (
        f"{counts.error} error(s), {counts.warning} warning(s), {counts.info} information(s)"
    )

    # Summary at verbosity 0.
    if verbosity_level <= 0:
        return f"> **Diagnostics:** {summary} (use `{CliShortOpt.VERBOSE}` to view details)\n"

    # Verbose output: emit section with summary and bullet list.
    lines: list[str] = [
        f"### {title}",
        "",
        f"**Diagnostics:** {summary}",
    ]
    for d in diagnostics:
        lines.append(f"- **{d.level}**: {d.message}")
    return "\n".join(lines).rstrip() + "\n"


def render_diagnostics_markdown(
    *,
    diagnostics: FrozenDiagnosticLog | DiagnosticLog,
    verbosity_level: int,
) -> str:
    """Render diagnostics as a Markdown fragment for human output.

    Behavior:
        - If there are no diagnostics, return an empty string.
        - At verbosity 0, emit a single triage line with a hint to use `-v`.
        - At verbosity >= 1, emit a triage summary and then one bullet per diagnostic.

    Args:
        diagnostics: An immutable or mutable diagnostic log.
        verbosity_level: Effective verbosity for gating extra details.

    Returns:
        Markdown fragment string (may be empty). Includes a trailing newline when non-empty.
    """
    if len(diagnostics.items) == 0:
        return ""

    # Aggregate counts per level once (used for triage summary and verbosity gating).
    stats: DiagnosticStats = compute_diagnostic_stats(diagnostics)
    n_info: int = stats.n_info
    n_warn: int = stats.n_warning
    n_err: int = stats.n_error

    # Compact triage summary like "1 error, 2 warnings".
    parts: list[str] = []
    if n_err:
        parts.append(f"{n_err} error" + ("s" if n_err != 1 else ""))
    if n_warn:
        parts.append(f"{n_warn} warning" + ("s" if n_warn != 1 else ""))
    # Only mention info when there are no higher-severity diagnostics.
    if n_info and not (n_err or n_warn):
        parts.append(f"{n_info} info" + ("s" if n_info != 1 else ""))

    triage: str = ", ".join(parts) if parts else "info"

    # Verbosity 0: keep output intentionally compact.
    if verbosity_level <= 0:
        return f"> ℹ️ **Diagnostics:** {triage} (use `{CliShortOpt.VERBOSE}` to view details)\n"

    # Display diagnostics triage info.
    lines: list[str] = []
    lines.append("> ℹ️ **Diagnostics:** " + triage)
    lines.append("")

    # Display diagnostics log.
    for d in diagnostics:
        level: str = d.level.value
        # Use stable label; optionally decorate with emoji for quick scanning.
        if d.level == DiagnosticLevel.ERROR:
            prefix = "❌"
        elif d.level == DiagnosticLevel.WARNING:
            prefix = "⚠️"
        else:
            prefix = "ℹ️"
        lines.append(f"- {prefix} **[{level}]** {d.message}")

    return "\n".join(lines).rstrip() + "\n"
