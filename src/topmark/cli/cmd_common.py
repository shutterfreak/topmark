# topmark:header:start
#
#   project      : TopMark
#   file         : cmd_common.py
#   file_relpath : src/topmark/cli/cmd_common.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Common command utilities for Click-based commands.

This module holds small, focused helpers used by multiple CLI commands.
They intentionally avoid policy (exit code rules, messages) and only
encapsulate plumbing such as running pipelines, filtering, and error exits.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import click

from topmark.cli.config_resolver import resolve_config_from_click
from topmark.cli.console_helpers import get_console_safely
from topmark.cli_shared.console_api import ConsoleLike
from topmark.config.logging import get_logger
from topmark.config.model import MutableConfig
from topmark.core.diagnostics import (
    Diagnostic,
    DiagnosticLevel,
    DiagnosticStats,
    compute_diagnostic_stats,
)
from topmark.file_resolver import resolve_file_list

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.cli.io import InputPlan
    from topmark.cli_shared.console_api import ConsoleLike
    from topmark.config import Config, MutableConfig
    from topmark.config.logging import TopmarkLogger
    from topmark.core.exit_codes import ExitCode
    from topmark.rendering.formats import HeaderOutputFormat

logger: TopmarkLogger = get_logger(__name__)


def get_effective_verbosity(ctx: click.Context, config: Config | None = None) -> int:
    """Return the effective program-output verbosity for this command.

    Resolution order (tri-state aware):
        1. Config.verbosity_level if set (not None)
        2. ctx.obj["verbosity_level"] if present
        3. 0 (terse)
    """
    cfg_level: int | None = config.verbosity_level if config else None
    if cfg_level is not None:
        return int(cfg_level)
    return int(ctx.obj.get("verbosity_level", 0))


def build_file_list(config: Config, *, stdin_mode: bool, temp_path: Path | None) -> list[Path]:
    """Return the files to process, respecting STDIN content mode.

    - If content-on-STDIN mode, return the single temp path.
    - Otherwise, delegate to the unified resolver that uses `config.files`,
      `files_from`, include/exclude patterns, and file types.
    """
    if stdin_mode:
        assert temp_path is not None
        return [temp_path]
    return resolve_file_list(config)


def exit_if_no_files(file_list: list[Path]) -> bool:
    """Echo a friendly message and return True if there is nothing to process."""
    if not file_list:
        console: ConsoleLike = get_console_safely()
        console.print(console.styled("\nℹ️  No files to process.\n", fg="blue"))
        return True
    return False


def maybe_exit_on_error(*, code: ExitCode | None, temp_path: Path | None) -> None:
    """If an error code was encountered, cleanup and exit with it."""
    if code is not None:
        from topmark.cli_shared.utils import safe_unlink

        safe_unlink(temp_path)
        click.get_current_context().exit(code)


def build_config_common(
    *,
    ctx: click.Context,
    plan: InputPlan,
    no_config: bool,
    config_paths: list[str],
    include_file_types: list[str],
    exclude_file_types: list[str],
    relative_to: str | None,
    align_fields: bool | None,
    header_format: HeaderOutputFormat | None,
) -> MutableConfig:
    """Materialize Config from an input plan (no file list resolution).

    Uses layered config discovery:
      * defaults → user → project chain (root→cwd; pyproject.toml then topmark.toml per dir)
        → extra files → CLI.
      * The discovery anchor is the first provided path (or CWD if none/STDIN).
    """
    draft: MutableConfig = resolve_config_from_click(
        ctx=ctx,
        verbosity_level=ctx.obj.get("verbosity_level"),  # Global context
        apply_changes=ctx.obj.get("apply_changes"),  # Command context for check, strip
        write_mode=ctx.obj.get("write_mode"),  # Command context for check, strip
        files=plan.paths,
        files_from=plan.files_from,
        stdin_mode=plan.stdin_mode,
        stdin_filename=plan.stdin_filename,
        include_patterns=plan.include_patterns,
        include_from=plan.include_from,
        exclude_patterns=plan.exclude_patterns,
        exclude_from=plan.exclude_from,
        include_file_types=include_file_types,
        exclude_file_types=exclude_file_types,
        relative_to=relative_to,
        no_config=no_config,
        config_paths=config_paths,
        align_fields=align_fields,
        header_format=header_format,
    )

    return draft


def render_config_diagnostics(
    *,
    ctx: click.Context,
    config: Config,
) -> None:
    """Render any config-level diagnostics to the console (human output only).

    Behavior:
      - If there are no diagnostics, do nothing.
      - At verbosity 0, emit a single triage line with a 'use -v' hint.
      - At verbosity >= 1, emit a summary and then one line per diagnostic.
    """
    diags: tuple[Diagnostic, ...] = config.diagnostics
    if not diags:
        return

    console: ConsoleLike = ctx.obj["console"]
    verbosity: int = get_effective_verbosity(ctx, config)

    # Count per level
    stats: DiagnosticStats = compute_diagnostic_stats(diags)
    n_info: int = stats.n_info
    n_warn: int = stats.n_warning
    n_err: int = stats.n_error

    # Compact triage summary like "1 error, 2 warnings"
    parts: list[str] = []
    if n_err:
        parts.append(f"{n_err} error" + ("s" if n_err != 1 else ""))
    if n_warn:
        parts.append(f"{n_warn} warning" + ("s" if n_warn != 1 else ""))
    if n_info and not (n_err or n_warn):
        parts.append(f"{n_info} info" + ("s" if n_info != 1 else ""))

    triage: str = ", ".join(parts) if parts else "info"

    if verbosity <= 0:
        console.print(
            console.styled(
                f"ℹ️  Config diagnostics: {triage} (use '-v' to view details)",
                fg="blue",
            )
        )
        return

    # Verbose mode: show all messages
    console.print(
        console.styled(
            f"ℹ️  Config diagnostics: {triage}",
            fg="blue",
            bold=True,
        )
    )
    for d in diags:
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
