# topmark:header:start
#
#   project      : TopMark
#   file         : diagnostic.py
#   file_relpath : src/topmark/cli/emitters/default/diagnostic.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""ANSI (DEFAULT) diagnostic rendering helpers for CLI commands.

This module contains Click-dependent helpers that render diagnostics for
human-facing output formats (primarily `OutputFormat.DEFAULT`). These helpers
are intentionally kept out of machine-format code paths.

Notes:
    - This module is Click-bound: it reads from `click.Context.obj` to resolve
      the active console and to determine effective verbosity.
    - Machine formats must not call these helpers; use domain serializers
      instead.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.cli.cmd_common import get_effective_verbosity
from topmark.core.keys import ArgKey
from topmark.diagnostic.model import (
    DiagnosticLevel,
    DiagnosticStats,
    FrozenDiagnosticLog,
    compute_diagnostic_stats,
)

if TYPE_CHECKING:
    import click

    from topmark.cli_shared.console_api import ConsoleLike
    from topmark.cli_shared.emitters.shared.config import HumanDiagnosticLine
    from topmark.config import Config


def render_human_diagnostics_default(
    *,
    console: ConsoleLike,
    counts: object,
    diagnostics: list[HumanDiagnosticLine],
    verbosity_level: int,
) -> None:
    """Render prepared human diagnostics to ConsoleLike (DEFAULT).

    Args:
        console: ConsoleLike for output.
        counts: HumanDiagnosticCounts (object with .error, .warning, .info).
        diagnostics: List of HumanDiagnosticLine (object with .level, .message).
        verbosity_level: Controls detail.
    """
    if not diagnostics:
        return
    err = getattr(counts, "error", 0)
    warn = getattr(counts, "warning", 0)
    info = getattr(counts, "info", 0)
    console.print(f"Config diagnostics: {err} error(s), {warn} warning(s), {info} information(s)")
    if verbosity_level > 0:
        for d in diagnostics:
            level = getattr(d, "level", "")
            message = getattr(d, "message", "")
            console.print(f"- {level}: {message}")


def render_config_diagnostics(
    *,
    ctx: click.Context,
    config: Config,
) -> None:
    """Render config-level diagnostics to the console for human output.

    This helper prints configuration resolution/validation diagnostics that were
    accumulated while building the effective `Config`. It is intended for
    human-facing output only (DEFAULT/ANSI), not for machine formats.

    Behavior:
        - If there are no diagnostics, do nothing.
        - At verbosity 0, emit a single triage line with a hint to use `-v`.
        - At verbosity >= 1, emit a summary line and then one line per diagnostic.

    Args:
        ctx: Click context providing access to `ctx.obj` values (console, meta, etc.).
        config: Effective frozen configuration containing an immutable diagnostic log.

    Returns:
        None. Output is written to the configured console.
    """
    diags: FrozenDiagnosticLog = config.diagnostics
    if not diags:
        return

    console: ConsoleLike = ctx.obj[ArgKey.CONSOLE]
    verbosity: int = get_effective_verbosity(ctx, config)

    # Aggregate counts per level once (used for triage summary and verbosity gating).
    stats: DiagnosticStats = compute_diagnostic_stats(diags)
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

    if verbosity <= 0:
        # Keep verbosity 0 output intentionally compact.
        console.print(
            console.styled(
                f"ℹ️  Config diagnostics: {triage} (use '-v' to view details)",
                fg="blue",
            )
        )
        return

    # Verbose mode: show the triage header and then each diagnostic message.
    console.print(
        console.styled(
            f"ℹ️  Config diagnostics: {triage}",
            fg="blue",
            bold=True,
        )
    )
    for d in diags:
        # Color by severity; keep level label stable via `.value`.
        fg: str
        if d.level == DiagnosticLevel.ERROR:
            fg = "red"
        elif d.level == DiagnosticLevel.WARNING:
            fg = "yellow"
        else:
            fg = "blue"
        console.print(
            console.styled(
                f"  [{d.level.value}] {d.message}",
                fg=fg,
            )
        )
