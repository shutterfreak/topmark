# topmark:header:start
#
#   project      : TopMark
#   file         : config.py
#   file_relpath : src/topmark/cli_shared/emitters/markdown/config.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Markdown emitters for TopMark config commands.

This module contains pure, Click-free helpers that render human-facing output
for config-related commands in `OutputFormat.MARKDOWN`.

Notes:
    These helpers return strings and do not perform any I/O.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.cli_shared.emitters.markdown.diagnostic import render_human_diagnostics_markdown
from topmark.cli_shared.emitters.markdown.utils import render_toml_markdown
from topmark.config.logging import TopmarkLogger, get_logger

if TYPE_CHECKING:
    from topmark.cli_shared.emitters.shared.config import (
        ConfigCheckPrepared,
        ConfigDefaultsPrepared,
        ConfigDumpPrepared,
        ConfigInitPrepared,
        HumanDiagnosticCounts,
        HumanDiagnosticLine,
    )

logger: TopmarkLogger = get_logger(__name__)


# --- Generate initial / default Config ---


def emit_config_init_markdown(
    *,
    prepared: ConfigInitPrepared,
    verbosity_level: int,
) -> str:
    """Render `topmark config init` output as Markdown.

    Args:
        prepared: Prepared TOML text and optional fallback error.
        verbosity_level: Effective verbosity for gating extra details.

    Returns:
        Markdown document string (with trailing newline).
    """
    md: str = render_toml_markdown(
        heading="Initial TopMark Configuration (TOML)",
        toml_text=prepared.toml_text,
    )
    if prepared.error is None:
        return md

    # Prepend a warning blockquote (keeps the TOML block unchanged)
    warning: str = (
        f"> **Warning:** falling back to synthesized default config: {prepared.error}\n\n"
    )
    return warning + md


def emit_config_defaults_markdown(
    *,
    prepared: ConfigDefaultsPrepared,
    verbosity_level: int,
) -> str:
    """Render `topmark config defaults` output as Markdown.

    Args:
        prepared: Prepared default configuration TOML (may include `root = true`).
        verbosity_level: Effective verbosity for gating extra details.

    Returns:
        Markdown document string (with trailing newline).
    """
    return render_toml_markdown(
        heading="Default TopMark Configuration (TOML)",
        toml_text=prepared.toml_text,
    )


# --- Check a resolved Config


def emit_config_check_markdown(
    *,
    ok: bool,
    strict: bool,
    prepared: ConfigCheckPrepared,
    verbosity_level: int,
) -> str:
    """Render `topmark config check` output as Markdown.

    Args:
        ok: Whether the configuration passed validation.
        strict: Whether strict checking was enabled.
        prepared: Prepared human-facing data (files, optional TOML, diagnostics).
        verbosity_level: Effective verbosity for gating extra details.

    Returns:
        Markdown document string (with trailing newline).
    """
    lines: list[str] = []
    lines.append("## topmark config check\n")

    status: str = "OK" if ok else "FAILED"
    counts: HumanDiagnosticCounts = prepared.counts
    diags: list[HumanDiagnosticLine] = prepared.diagnostics

    # Summary
    lines.append("### Summary\n")
    lines.append(f"- **Status:** {status}")
    lines.append(f"- **Strict:** {str(strict).lower()}")
    lines.append(f"- **Errors:** {counts.error}")
    lines.append(f"- **Warnings:** {counts.warning}\n")

    # Diagnostics
    diag_md: str = render_human_diagnostics_markdown(
        title="Diagnostics",
        counts=counts,
        diagnostics=diags,
        verbosity_level=verbosity_level,
    )
    if diag_md:
        lines.append(diag_md.rstrip())
        lines.append("")

    # Config files
    if verbosity_level > 0:
        lines.append(f"### Config files processed ({len(prepared.config_files)})\n")
        for i, p in enumerate(prepared.config_files, start=1):
            lines.append(f"{i}. {p}")
        lines.append("")

    if verbosity_level > 1 and prepared.merged_toml is not None:
        lines.append("### Effective merged TOML\n")
        lines.append("```toml")
        lines.append(prepared.merged_toml.rstrip())
        lines.append("```")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


# --- Dump a resolved Config


def emit_config_dump_markdown(
    *,
    prepared: ConfigDumpPrepared,
    verbosity_level: int,
) -> str:
    """Render `topmark config dump` output as Markdown.

    Args:
        prepared: Prepared config dump data (files, merged TOML).
        verbosity_level: Effective verbosity for gating extra details.

    Returns:
        Markdown document string (with trailing newline).
    """
    lines: list[str] = []
    lines.append("## topmark config dump\n")
    lines.append(
        render_toml_markdown(
            heading="TopMark Config Dump (TOML)",
            toml_text=prepared.merged_toml,
        ).rstrip()
    )

    if verbosity_level > 0:
        lines.append("")
        lines.append(f"### Config files processed ({len(prepared.config_files)})\n")
        for i, p in enumerate(prepared.config_files, start=1):
            lines.append(f"{i}. {p}")

    return "\n".join(lines).rstrip() + "\n"
