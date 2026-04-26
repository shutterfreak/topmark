# topmark:header:start
#
#   project      : TopMark
#   file         : config.py
#   file_relpath : src/topmark/presentation/markdown/config.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Markdown emitters for TopMark config commands.

This module contains helpers that render human-facing output for config-related
commands in `OutputFormat.MARKDOWN`.

Notes:
    These helpers return strings and do not perform any I/O.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.core.logging import TopmarkLogger
from topmark.core.logging import get_logger
from topmark.presentation.markdown.diagnostic import render_human_diagnostics_markdown
from topmark.presentation.markdown.utils import render_toml_markdown
from topmark.presentation.markdown.version import render_version_footer_markdown

if TYPE_CHECKING:
    from topmark.presentation.shared.config import ConfigCheckHumanReport
    from topmark.presentation.shared.config import ConfigDefaultsHumanReport
    from topmark.presentation.shared.config import ConfigDumpHumanReport
    from topmark.presentation.shared.config import ConfigInitHumanReport
    from topmark.presentation.shared.config import HumanDiagnosticCounts
    from topmark.presentation.shared.config import HumanDiagnosticLine

logger: TopmarkLogger = get_logger(__name__)


# --- Generate initial / default Config ---


def render_config_init_markdown(
    prepared: ConfigInitHumanReport,
) -> str:
    """Render `topmark config init` output as Markdown.

    Args:
        prepared: Prepared TOML text and optional fallback error.

    Returns:
        Markdown document string (with trailing newline).
    """
    md: str = render_toml_markdown(
        heading="Initial TopMark Configuration (TOML)",
        heading_level=1,
        toml_text=prepared.toml_text,
    )

    parts: list[str] = [
        md,
    ]

    if prepared.error is None:
        return md

    if prepared.error:
        # Prepend a warning blockquote (keeps the TOML block unchanged)
        warning: str = (
            f"> **Warning:** falling back to synthesized default config: {prepared.error}\n\n"
        )
        parts.append(warning)

    parts.append(render_version_footer_markdown())

    return "\n".join(parts)


def render_config_defaults_markdown(
    prepared: ConfigDefaultsHumanReport,
) -> str:
    """Render `topmark config defaults` output as Markdown.

    Args:
        prepared: Prepared default configuration TOML (may include `root = true`).

    Returns:
        Markdown document string (with trailing newline).
    """
    toml_md: str = render_toml_markdown(
        heading="Default TopMark Configuration (TOML)",
        heading_level=1,
        toml_text=prepared.toml_text,
    )
    footer: str = render_version_footer_markdown()

    return "\n".join(
        [
            toml_md,
            footer,
        ]
    )


# --- Check a resolved Config


def render_config_check_markdown(
    prepared: ConfigCheckHumanReport,
) -> str:
    """Render `topmark config check` output as Markdown.

    Args:
        prepared: Prepared human-facing data (files, optional TOML, diagnostics).

    Returns:
        Markdown document string (with trailing newline).
    """
    lines: list[str] = []
    lines.append("## topmark config check\n")

    status: str = "OK" if prepared.ok else "FAILED"
    counts: HumanDiagnosticCounts = prepared.counts
    diags: list[HumanDiagnosticLine] = prepared.diagnostics

    # Summary
    lines.append("### Summary\n")
    lines.append(f"- **Status:** {status}")
    lines.append(f"- **Strict:** {str(prepared.strict).lower()}")
    lines.append(f"- **Errors:** {counts.error}")
    lines.append(f"- **Warnings:** {counts.warning}\n")

    # Diagnostics
    diag_md: str = render_human_diagnostics_markdown(
        title="Diagnostics",
        counts=counts,
        diagnostics=diags,
    )
    if diag_md:
        lines.append(diag_md.rstrip())
        lines.append("")

    # Config files
    lines.append(f"### Config files processed ({len(prepared.config_files)})\n")
    for i, p in enumerate(prepared.config_files, start=1):
        lines.append(f"{i}. {p}")
    lines.append("")

    if prepared.merged_toml is not None:
        lines.append("### Effective merged TOML\n")
        lines.append("```toml")
        lines.append(prepared.merged_toml.rstrip())
        lines.append("```")
        lines.append("")

    lines.append(render_version_footer_markdown())

    return "\n".join(lines).rstrip() + "\n"


# --- Dump a resolved Config


def render_config_dump_markdown(
    prepared: ConfigDumpHumanReport,
) -> str:
    """Render `topmark config dump` output as Markdown.

    Args:
        prepared: Prepared config dump data (files, flattened TOML, optional provenance).

    Returns:
        Markdown document string (with trailing newline).
    """
    lines: list[str] = []

    if prepared.show_config_layers and prepared.provenance_toml is not None:
        lines.append(
            render_toml_markdown(
                heading="TopMark Config Provenance Layers (TOML)",
                heading_level=1,
                toml_text=prepared.provenance_toml,
            ).rstrip()
        )
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append(
            render_toml_markdown(
                heading="TopMark Config Dump (Flattened TOML)",
                heading_level=1,
                toml_text=prepared.merged_toml,
            ).rstrip()
        )
    else:
        lines.append(
            render_toml_markdown(
                heading="TopMark Config Dump (TOML)",
                heading_level=1,
                toml_text=prepared.merged_toml,
            ).rstrip()
        )

    lines.append("")
    lines.append(f"### Config files processed ({len(prepared.config_files)})\n")
    for i, p in enumerate(prepared.config_files, start=1):
        lines.append(f"{i}. {p}")

    lines.append(render_version_footer_markdown())

    return "\n".join(lines).rstrip() + "\n"
