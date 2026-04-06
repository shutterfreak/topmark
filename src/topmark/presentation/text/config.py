# topmark:header:start
#
#   project      : TopMark
#   file         : config.py
#   file_relpath : src/topmark/presentation/text/config.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Default (ANSI-styled) renderers for TopMark config commands.

This module is reserved for Click-free helpers that render human-facing config
output in `OutputFormat.TEXT`. These generate no I/O.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.cli.presentation import TextStyler
from topmark.cli.presentation import style_for_role
from topmark.core.presentation import StyleRole
from topmark.presentation.text.diagnostic import render_human_diagnostics_text
from topmark.presentation.text.utils import render_toml_text

if TYPE_CHECKING:
    from topmark.presentation.shared.config import ConfigCheckHumanReport
    from topmark.presentation.shared.config import ConfigDefaultsHumanReport
    from topmark.presentation.shared.config import ConfigDumpHumanReport
    from topmark.presentation.shared.config import ConfigInitHumanReport
    from topmark.presentation.shared.config import HumanDiagnosticCounts
    from topmark.presentation.shared.config import HumanDiagnosticLine


# --- Generate initial / default Config ---


def render_config_init_text(
    prepared: ConfigInitHumanReport,
) -> str:
    """Render `topmark config init` output in the TEXT (ANSI-styled) format.

    Args:
        prepared: Prepared TOML text and optional fallback error.

    Returns:
        Text document as single string.
    """
    parts: list[str] = []

    # Note: the stylers already check `report.styled` so we don't need `maybe_style()`
    warning_styler: TextStyler = style_for_role(StyleRole.WARNING, styled=prepared.styled)

    if prepared.error is not None:
        parts.append(
            warning_styler(
                f"Warning: falling back to synthesized default config: {prepared.error}",
            )
        )

    parts.append(
        render_toml_text(
            title="Initial TopMark Configuration (TOML):",
            toml_text=prepared.toml_text,
            verbosity_level=prepared.verbosity_level,
            styled=prepared.styled,
        )
    )

    return "\n".join(parts)


def render_config_defaults_text(
    prepared: ConfigDefaultsHumanReport,
) -> str:
    """Render `topmark config defaults` output in the TEXT (ANSI-styled) format.

    Args:
        prepared: Prepared default configuration TOML (may include `root = true`).

    Returns:
        Text document as single string.
    """
    return render_toml_text(
        title="Default TopMark Configuration (TOML):",
        toml_text=prepared.toml_text,
        verbosity_level=prepared.verbosity_level,
        styled=prepared.styled,
    )


# --- Check a resolved Config


def render_config_check_text(
    prepared: ConfigCheckHumanReport,
) -> str:
    """Emit `topmark config check` output in the TEXT (ANSI-styled) format.

    Args:
        prepared: Prepared human-facing data (files, optional TOML, diagnostics).

    Returns:
        Text document as single string.
    """
    parts: list[str] = []
    status_icon: str = "✅" if prepared.ok else "❌"

    # Keep strict visible (even if currently only affects exit status)
    strict_str: str = "on" if prepared.strict else "off"

    counts: HumanDiagnosticCounts = prepared.counts
    diags: list[HumanDiagnosticLine] = prepared.diagnostics

    if not diags:
        parts.append(f"{status_icon} Config OK (no diagnostics). [strict: {strict_str}]")
    else:
        parts.append(
            render_human_diagnostics_text(
                counts=counts,
                diagnostics=diags,
                verbosity_level=prepared.verbosity_level,
            )
        )

    if prepared.verbosity_level > 0:
        parts.append(f"Config files processed: {len(prepared.config_files)}")
        for i, p in enumerate(prepared.config_files, start=1):
            parts.append(f"Loaded config {i}: {p}")

    if prepared.verbosity_level > 1 and prepared.merged_toml is not None:
        parts.append(
            render_toml_text(
                title="TopMark Config (TOML):",
                toml_text=prepared.merged_toml,
                verbosity_level=prepared.verbosity_level,
                styled=prepared.styled,
            )
        )

    parts.append(f"{status_icon} {'OK' if prepared.ok else 'FAILED'}")

    return "\n".join(parts)


# --- Dump a resolved Config


def render_config_dump_text(
    prepared: ConfigDumpHumanReport,
) -> str:
    """Render `topmark config dump` output in the TEXT (ANSI-styled) format.

    Args:
        prepared: Prepared human-facing data (files, flattened TOML, optional provenance).

    Returns:
        Text document as single string.
    """
    parts: list[str] = []
    if prepared.verbosity_level > 0:
        parts.append(f"Config files processed: {len(prepared.config_files)}")
        for i, p in enumerate(prepared.config_files, start=1):
            parts.append(f"Loaded config {i}: {p}")

    if prepared.show_config_layers and prepared.provenance_toml is not None:
        section_verbosity_level: int = max(prepared.verbosity_level, 1)
        parts.append(
            render_toml_text(
                title="TopMark Config Provenance Layers (TOML):",
                toml_text=prepared.provenance_toml,
                verbosity_level=section_verbosity_level,
                styled=prepared.styled,
            )
        )
        parts.append("")
        parts.append(
            render_toml_text(
                title="TopMark Config Dump (Flattened TOML):",
                toml_text=prepared.merged_toml,
                verbosity_level=section_verbosity_level,
                styled=prepared.styled,
            )
        )
        return "\n".join(parts)

    parts.append(
        render_toml_text(
            title="TopMark Config Dump (TOML):",
            toml_text=prepared.merged_toml,
            verbosity_level=prepared.verbosity_level,
            styled=prepared.styled,
        )
    )

    return "\n".join(parts)
