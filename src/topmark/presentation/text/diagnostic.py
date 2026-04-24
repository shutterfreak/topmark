# topmark:header:start
#
#   project      : TopMark
#   file         : diagnostic.py
#   file_relpath : src/topmark/presentation/text/diagnostic.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""TEXT diagnostic rendering helpers for CLI commands.

This module contains helpers that render diagnostics for human-facing TEXT output formats.
These generate no I/O.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.cli.keys import CliShortOpt
from topmark.cli.presentation import TextStyler
from topmark.cli.presentation import style_for_role
from topmark.core.presentation import StyleRole
from topmark.diagnostic.model import DiagnosticLog
from topmark.diagnostic.model import DiagnosticStats
from topmark.diagnostic.model import FrozenDiagnosticLog
from topmark.diagnostic.model import compute_diagnostic_stats

if TYPE_CHECKING:
    from topmark.presentation.shared.config import HumanDiagnosticLine
    from topmark.presentation.shared.diagnostic import HumanDiagnosticCounts


def render_human_diagnostics_text(
    *,
    counts: HumanDiagnosticCounts,
    diagnostics: list[HumanDiagnosticLine],
    verbosity_level: int,
) -> str:
    """Render prepared human diagnostics as text for human output.

    Args:
        counts: Aggregated human-facing diagnostic counts.
        diagnostics: Prepared human-facing diagnostic lines.
        verbosity_level: Effective verbosity for gating extra details.

    Returns:
        Text document as single string.
    """
    if not diagnostics:
        return ""

    summary: str = (
        f"Diagnostics: {counts.error} error(s), "
        f"{counts.warning} warning(s), "
        f"{counts.info} information(s)"
    )

    if verbosity_level <= 0:
        return f"{summary} (use '{CliShortOpt.VERBOSE}' to view details)"

    parts: list[str] = [summary]
    for d in diagnostics:
        parts.append(f"- {d.level}: {d.message}")

    return "\n".join(parts)


def render_diagnostics_text(
    *,
    diagnostics: FrozenDiagnosticLog | DiagnosticLog,
    verbosity_level: int,
    color: bool,
) -> str:
    """Render diagnostics as text for human output.

    Behavior:
        - If there are no diagnostics, do nothing.
        - At verbosity 0, emit a single triage line with a hint to use `-v`.
        - At verbosity >= 1, emit a summary line and then one line per diagnostic.

    Args:
        diagnostics: An immutable or mutable diagnostic log.
        verbosity_level: Effective verbosity level.
        color: Render in color if True, as plain text otherwise.

    Returns:
        Text document as single string.
    """
    if len(diagnostics.items) == 0:
        return ""

    # Note: the stylers already check `report.styled` so we don't need `maybe_style()`
    info_styler: TextStyler = style_for_role(StyleRole.INFO, styled=color)

    parts: list[str] = []

    # Aggregate counts per level once (used for triage summary and verbosity gating).
    stats: DiagnosticStats = compute_diagnostic_stats(diagnostics)
    n_info: int = stats.n_info
    n_warn: int = stats.n_warning
    n_err: int = stats.n_error

    # Compact triage summary like "1 error, 2 warnings".
    diag_parts: list[str] = []
    if n_err:
        diag_parts.append(f"{n_err} error" + ("s" if n_err != 1 else ""))
    if n_warn:
        diag_parts.append(f"{n_warn} warning" + ("s" if n_warn != 1 else ""))
    # Only mention info when there are no higher-severity diagnostics.
    if n_info and not (n_err or n_warn):
        diag_parts.append(f"{n_info} info" + ("s" if n_info != 1 else ""))

    triage: str = ", ".join(diag_parts) if diag_parts else "info"

    if verbosity_level <= 0:
        # Keep verbosity 0 output intentionally compact.
        parts.append(
            info_styler(
                f"ℹ️  Diagnostics: {triage} (use '{CliShortOpt.VERBOSE}' to view details)",
            )
        )
        return "\n".join(parts)

    # Display diagnostics triage info.
    parts.append(
        info_styler(
            f"ℹ️  Diagnostics: {triage}",
        )
    )

    # Display diagnostics log.
    for d in diagnostics:
        styler: TextStyler = style_for_role(d.level.role, styled=color)
        parts.append(
            styler(
                f"  [{d.level.value}] {d.message}",
            )
        )

    return "\n".join(parts)
