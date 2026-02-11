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

It also contains a small initializer (`init_common_state`) that populates
`ctx.obj` with the shared UI/runtime state (verbosity, color, console, meta)
when these options are owned by individual commands rather than the root
command group.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import click

from topmark.cli.config_resolver import resolve_config_from_click
from topmark.cli.console import ClickConsole
from topmark.cli.console_helpers import get_console_safely
from topmark.cli.options import ColorMode, resolve_verbosity
from topmark.cli_shared.color import resolve_color_mode
from topmark.config.logging import (
    resolve_env_log_level,
    setup_logging,
)
from topmark.core.keys import ArgKey
from topmark.core.machine.payloads import build_meta_payload
from topmark.file_resolver import resolve_file_list

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.cli.io import InputPlan
    from topmark.cli_shared.console_api import ConsoleLike
    from topmark.config import Config
    from topmark.config.model import MutableConfig
    from topmark.core.exit_codes import ExitCode
    from topmark.rendering.formats import HeaderOutputFormat


def init_common_state(
    ctx: click.Context,
    *,
    verbose: int,
    quiet: int,
    color_mode: ColorMode | None,
    no_color: bool,
) -> None:
    """Initialize shared UI/runtime state on the Click context.

    This is the per-command equivalent of the former group-level initializer.
    It populates `ctx.obj` with:

    - `ArgKey.VERBOSITY_LEVEL`
    - `ArgKey.LOG_LEVEL` (from environment)
    - `ArgKey.COLOR_MODE` and `ArgKey.COLOR_ENABLED`
    - `ArgKey.CONSOLE`
    - `ArgKey.META`

    Args:
        ctx: Current Click context; will have ``obj`` and ``color`` set.
        verbose: Count of ``-v`` flags (0..2).
        quiet: Count of ``-q`` flags (0..2).
        color_mode: Explicit color mode from ``--color`` (or ``None``).
        no_color: Whether ``--no-color`` was passed; forces color off.
    """
    ctx.obj = ctx.obj or {}

    # Program-output verbosity (stored for downstream gating).
    level_cli: int = resolve_verbosity(verbose, quiet)
    ctx.obj[ArgKey.VERBOSITY_LEVEL] = level_cli

    # Internal logging (env-driven).
    level_env: int | None = resolve_env_log_level()
    ctx.obj[ArgKey.LOG_LEVEL] = level_env
    setup_logging(level=level_env)

    # Color policy (command decides output format later; `output_format=None` here).
    effective_color_mode: ColorMode = (
        ColorMode.NEVER if no_color else (color_mode or ColorMode.AUTO)
    )
    ctx.obj[ArgKey.COLOR_MODE] = effective_color_mode
    enable_color: bool = resolve_color_mode(
        color_mode_override=effective_color_mode,
        output_format=None,
    )
    ctx.obj[ArgKey.COLOR_ENABLED] = enable_color
    ctx.color = enable_color

    console = ClickConsole(enable_color=not no_color)
    ctx.obj[ArgKey.CONSOLE] = console

    # Machine metadata payload.
    ctx.obj[ArgKey.META] = build_meta_payload()


def get_effective_verbosity(ctx: click.Context, config: Config | None = None) -> int:
    """Return the effective program-output verbosity for this command.

    Resolution order (tri-state aware):
        1. Config.verbosity_level if set (not None)
        2. ctx.obj[ArgKey.VERBOSITY_LEVEL] if present
        3. 0 (terse)
    """
    cfg_level: int | None = config.verbosity_level if config else None
    if cfg_level is not None:
        return int(cfg_level)
    return int(ctx.obj.get(ArgKey.VERBOSITY_LEVEL, 0))


def build_file_list(config: Config, *, stdin_mode: bool, temp_path: Path | None) -> list[Path]:
    """Return the files to process, respecting STDIN content mode.

    - If content-on-STDIN mode, return the single temp path.
    - Otherwise, delegate to the unified resolver that uses `config.files`,
      `files_from`, include/exclude patterns, and file types.
    """
    if stdin_mode:
        if temp_path is None:
            raise RuntimeError("temp_path should not be undefined in stdin_mode")
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
        from topmark.utils.file import safe_unlink

        safe_unlink(temp_path)
        click.get_current_context().exit(code)


def build_config_for_plan(
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
        verbosity_level=ctx.obj.get(ArgKey.VERBOSITY_LEVEL),
        apply_changes=ctx.obj.get(ArgKey.APPLY_CHANGES),
        write_mode=ctx.obj.get(ArgKey.WRITE_MODE),
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
