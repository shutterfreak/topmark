# topmark:header:start
#
#   project      : TopMark
#   file         : diagnostic.py
#   file_relpath : src/topmark/cli/emitters/text/diagnostic.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""ANSI (TEXT) diagnostic rendering helpers for CLI commands.

This module contains Click-dependent helpers that render diagnostics for
human-facing output formats (primarily `OutputFormat.TEXT`). These helpers
are intentionally kept out of machine-format code paths.

Notes:
    - This module is Click-bound: it reads from `click.Context.obj` to resolve
      the active console and to determine effective verbosity.
    - Machine formats must not call these helpers; use domain serializers
      instead.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.cli.console_helpers import get_console_safely
from topmark.cli.keys import CliShortOpt
from topmark.cli.presentation import TextStyler
from topmark.cli.presentation import maybe_style
from topmark.cli.presentation import style_for_role
from topmark.core.presentation import StyleRole
from topmark.diagnostic.model import DiagnosticLog
from topmark.diagnostic.model import DiagnosticStats
from topmark.diagnostic.model import FrozenDiagnosticLog
from topmark.diagnostic.model import compute_diagnostic_stats

if TYPE_CHECKING:
    from topmark.cli_shared.console_api import ConsoleLike
    from topmark.cli_shared.emitters.shared.config import HumanDiagnosticLine
    from topmark.cli_shared.emitters.shared.diagnostic import HumanDiagnosticCounts


def render_human_diagnostics_text(
    *,
    counts: HumanDiagnosticCounts,
    diagnostics: list[HumanDiagnosticLine],
    verbosity_level: int,
) -> None:
    """Render prepared human diagnostics to ConsoleLike (TEXT).

    Args:
        counts: HumanDiagnosticCounts (object with .error, .warning, .info).
        diagnostics: List of HumanDiagnosticLine (object with .level, .message).
        verbosity_level: Controls detail.
    """
    if not diagnostics:
        return

    console: ConsoleLike = get_console_safely()
    console.print(
        f"Diagnostics: {counts.error} error(s), "
        f"{counts.warning} warning(s), "
        f"{counts.info} information(s)"
    )
    if verbosity_level > 0:
        for d in diagnostics:
            console.print(f"- {d.level}: {d.message}")


def render_diagnostics_text(
    *,
    diagnostics: FrozenDiagnosticLog | DiagnosticLog,
    verbosity_level: int,
    color: bool,
) -> None:
    """Render diagnostics to the console for human output.

    It is intended for human-facing output only (TEXT/ANSI), not for machine formats.

    Behavior:
        - If there are no diagnostics, do nothing.
        - At verbosity 0, emit a single triage line with a hint to use `-v`.
        - At verbosity >= 1, emit a summary line and then one line per diagnostic.

    Args:
        diagnostics: An immutable or mutable diagnostic log.
        verbosity_level: Effective verbosity level.
        color: Render in color if True, as plain text otherwise.

    Returns:
        None. Output is written to the configured console.
    """
    if len(diagnostics.items) == 0:
        return

    console: ConsoleLike = get_console_safely()

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

    info_styler: TextStyler = style_for_role(StyleRole.INFO, styled=color)
    if verbosity_level <= 0:
        # Keep verbosity 0 output intentionally compact.
        console.print(
            maybe_style(
                info_styler,
                f"ℹ️  Diagnostics: {triage} (use '{CliShortOpt.VERBOSE}' to view details)",
                styled=color,
            )
        )
        return

    # Display diagnostics triage info.
    console.print(
        maybe_style(
            info_styler,
            f"ℹ️  Diagnostics: {triage}",
            styled=color,
        )
    )

    # Display diagnostics log.
    for d in diagnostics:
        styler: TextStyler = style_for_role(d.level.role, styled=color)
        console.print(
            maybe_style(
                styler,
                f"  [{d.level.value}] {d.message}",
                styled=color,
            )
        )
