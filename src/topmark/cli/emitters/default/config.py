# topmark:header:start
#
#   project      : TopMark
#   file         : config.py
#   file_relpath : src/topmark/cli/emitters/default/config.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Default (ANSI-styled) emitters for TopMark config commands.

This module is reserved for Click-free helpers that render human-facing config
output in `OutputFormat.DEFAULT`, using `ConsoleLike` for styling.

Notes:
    Config commands currently rely on shared helpers such as `emit_toml_block`.
    As the CLI refactor progresses, config-specific default emitters may be
    added here to keep `cli/commands/*` thin.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.cli.emitters.default.diagnostic import render_human_diagnostics_default
from topmark.cli.emitters.utils import emit_toml_block

if TYPE_CHECKING:
    from topmark.cli_shared.console_api import ConsoleLike
    from topmark.cli_shared.emitters.shared.config import (
        ConfigCheckPrepared,
        ConfigDefaultsPrepared,
        ConfigDumpPrepared,
        ConfigInitPrepared,
        HumanDiagnosticCounts,
        HumanDiagnosticLine,
    )


# --- Generate initial / default Config ---


def emit_config_init_default(
    *,
    console: ConsoleLike,
    prepared: ConfigInitPrepared,
    verbosity_level: int,
) -> None:
    """Emit `topmark config init` output in the DEFAULT (ANSI-styled) format.

    This helper is Click-free: it performs no Click-specific I/O and instead
    writes via the provided `ConsoleLike`.

    Args:
        console: Console abstraction used by the CLI for styled output.
        prepared: Prepared TOML text and optional fallback error.
        verbosity_level: Effective verbosity for gating extra details.
    """
    if prepared.error is not None:
        console.print(
            console.styled(
                f"Warning: falling back to synthesized default config: {prepared.error}",
                dim=True,
            )
        )

    emit_toml_block(
        console=console,
        title="Initial TopMark Configuration (TOML):",
        toml_text=prepared.toml_text,
        verbosity_level=verbosity_level,
    )


def emit_config_defaults_default(
    *,
    console: ConsoleLike,
    prepared: ConfigDefaultsPrepared,
    verbosity_level: int,
) -> None:
    """Emit `topmark config defaults` output in the DEFAULT (ANSI-styled) format.

    This helper is Click-free: it performs no Click-specific I/O and instead
    writes via the provided `ConsoleLike`.

    Args:
        console: Console abstraction used by the CLI for styled output.
        prepared: Prepared default configuration TOML (may include `root = true`).
        verbosity_level: Effective verbosity for gating extra details.
    """
    emit_toml_block(
        console=console,
        title="Default TopMark Configuration (TOML):",
        toml_text=prepared.toml_text,
        verbosity_level=verbosity_level,
    )


# --- Check a resolved Config


def emit_config_check_default(
    *,
    console: ConsoleLike,
    ok: bool,
    strict: bool,
    prepared: ConfigCheckPrepared,
    verbosity_level: int,
) -> None:
    """Emit `topmark config check` output in the DEFAULT (ANSI-styled) format.

    Args:
        console: Console abstraction used by the CLI for styled output.
        ok: Whether the configuration passed validation.
        strict: Whether strict checking was enabled.
        prepared: Prepared human-facing data (files, optional TOML, diagnostics).
        verbosity_level: Effective verbosity for gating extra details.
    """
    status_icon: str = "✅" if ok else "❌"

    # Keep strict visible (even if currently only affects exit status)
    strict_str: str = "on" if strict else "off"

    counts: HumanDiagnosticCounts = prepared.counts
    diags: list[HumanDiagnosticLine] = prepared.diagnostics

    if not diags:
        console.print(f"{status_icon} Config OK (no diagnostics). [strict: {strict_str}]")
    else:
        render_human_diagnostics_default(
            console=console,
            counts=counts,
            diagnostics=diags,
            verbosity_level=verbosity_level,
        )

    if verbosity_level > 0:
        console.print(f"Config files processed: {len(prepared.config_files)}")
        for i, p in enumerate(prepared.config_files, start=1):
            console.print(f"Loaded config {i}: {p}")

    if verbosity_level > 1 and prepared.merged_toml is not None:
        emit_toml_block(
            console=console,
            title="TopMark Config (TOML):",
            toml_text=prepared.merged_toml,
            verbosity_level=verbosity_level,
        )

    console.print(f"{status_icon} {'OK' if ok else 'FAILED'}")


# --- Dump a resolved Config


def emit_config_dump_default(
    *,
    console: ConsoleLike,
    prepared: ConfigDumpPrepared,
    verbosity_level: int,
) -> None:
    """Emit `topmark config dump` output in the DEFAULT (ANSI-styled) format.

    This helper is Click-free: it performs no Click-specific I/O and instead
    writes via the provided `ConsoleLike`.

    Args:
        console: Console abstraction used by the CLI for styled output.
        prepared: Prepared human-facing data (files, optional TOML).
        verbosity_level: Effective verbosity for gating extra details.
    """
    if verbosity_level > 0:
        console.print(f"Config files processed: {len(prepared.config_files)}")
        for i, p in enumerate(prepared.config_files, start=1):
            console.print(f"Loaded config {i}: {p}")

    emit_toml_block(
        console=console,
        title="TopMark Config Dump (TOML):",
        toml_text=prepared.merged_toml,
        verbosity_level=verbosity_level,
    )
