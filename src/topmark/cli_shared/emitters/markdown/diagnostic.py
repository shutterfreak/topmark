# topmark:header:start
#
#   project      : TopMark
#   file         : diagnostic.py
#   file_relpath : src/topmark/cli_shared/emitters/markdown/diagnostic.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Markdown diagnostic rendering helpers for CLI-shared emitters.

This module contains Click-free helpers that render diagnostics as Markdown for
human-facing output (`OutputFormat.MARKDOWN`). These helpers are intentionally
kept independent from machine formats.

Notes:
    - This module is Click-free: it does not read from `click.Context` and does
      not print. It returns Markdown text to be emitted by a caller.
    - Machine formats must not call these helpers; use domain serializers and
      machine shapes/serializers instead.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.diagnostic.model import (
    DiagnosticLevel,
    DiagnosticStats,
    FrozenDiagnosticLog,
    compute_diagnostic_stats,
)

if TYPE_CHECKING:
    from topmark.cli_shared.emitters.shared.config import HumanDiagnosticLine
    from topmark.config import Config


def render_config_diagnostics_markdown(
    *,
    config: Config,
    verbosity_level: int,
) -> str:
    """Render config-level diagnostics as a Markdown fragment.

    This helper renders configuration resolution/validation diagnostics that
    were accumulated while building the effective `Config`.

    Behavior:
        - If there are no diagnostics, return an empty string.
        - At verbosity 0, emit a single triage line with a hint to use `-v`.
        - At verbosity >= 1, emit a triage summary and then one bullet per diagnostic.

    Args:
        config: Effective frozen configuration containing an immutable diagnostic log.
        verbosity_level: Effective verbosity for gating extra details.

    Returns:
        Markdown fragment string (may be empty). Includes a trailing newline when non-empty.
    """
    diags: FrozenDiagnosticLog = config.diagnostics
    if not diags:
        return ""

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

    # Verbosity 0: keep output intentionally compact.
    if verbosity_level <= 0:
        return f"> ℹ️ **Config diagnostics:** {triage} (use `-v` to view details)\n"

    # Verbose mode: emit a small section and then each diagnostic message.
    lines: list[str] = []
    lines.append("> ℹ️ **Config diagnostics:** " + triage)
    lines.append("")

    for d in diags:
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


# --- Adapter: render human-prepared diagnostics as Markdown ---
def render_human_diagnostics_markdown(
    *,
    title: str,
    counts: object,
    diagnostics: list[HumanDiagnosticLine],
    verbosity_level: int,
) -> str:
    """Render human diagnostics as Markdown from prepared data.

    Args:
        title: Section heading.
        counts: HumanDiagnosticCounts (object with .error, .warning, .info).
        diagnostics: List of HumanDiagnosticLine (object with .level, .message).
        verbosity_level: Controls detail.

    Returns:
        Markdown fragment string (may be empty). Includes a trailing newline when non-empty.
    """
    if not diagnostics and verbosity_level <= 0:
        return ""
    # For summary at verbosity 0
    if verbosity_level <= 0:
        err = getattr(counts, "error", 0)
        warn = getattr(counts, "warning", 0)
        info = getattr(counts, "info", 0)
        return (
            f"> **Diagnostics:** {err} error(s), {warn} warning(s), {info} information(s)"
            " (use `-v` to view details)\n"
        )
    # Verbose: emit section with bullet list
    lines: list[str] = []
    lines.append(f"### {title}")
    for d in diagnostics:
        level = getattr(d, "level", "")
        message = getattr(d, "message", "")
        lines.append(f"- **{level}**: {message}")
    return "\n".join(lines).rstrip() + "\n"
