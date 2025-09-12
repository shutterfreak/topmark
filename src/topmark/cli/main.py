# topmark:header:start
#
#   project      : TopMark
#   file         : main.py
#   file_relpath : src/topmark/cli/main.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Minimal, DRY Click CLI prototype showing a default action + real subcommands.

Key ideas:
- Group-level options are initialized once, placed into ``ctx.obj``.
- A small helper collects CLI arguments or STDIN, and enforces mutual exclusion.
- Subcommands reuse the same helpers for consistent behavior.
This file is intentionally compact so we can lift the patterns back into TopMark.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import click

from topmark.cli.commands.check import check_command
from topmark.cli.commands.dump_config import dump_config_command
from topmark.cli.commands.filetypes import filetypes_command
from topmark.cli.commands.init_config import init_config_command
from topmark.cli.commands.processors import processors_command
from topmark.cli.commands.show_defaults import show_defaults_command
from topmark.cli.commands.strip import strip_command
from topmark.cli.commands.version import version_command
from topmark.cli.console import ClickConsole

# --- We use a module import here instead of relative import
from topmark.cli.options import (
    ColorMode,
    common_color_options,
    common_verbose_options,
    resolve_color_mode,
    resolve_verbosity,
)
from topmark.config.logging import get_logger, resolve_env_log_level, setup_logging
from topmark.pipeline.processors import register_all_processors

if TYPE_CHECKING:
    from topmark.cli_shared.console_api import ConsoleLike

logger = get_logger(__name__)

register_all_processors()


def init_common_state(
    ctx: click.Context,
    *,
    verbose: int,
    quiet: int,
    color_mode: ColorMode | None,
    no_color: bool,
) -> None:
    """Initialize shared state (verbosity & color) on the Click context.

    Args:
        ctx (click.Context): Current Click context; will have ``obj`` and ``color`` set.
        verbose (int): Count of ``-v`` flags (0..2).
        quiet (int): Count of ``-q`` flags (0..2).
        color_mode (ColorMode | None): Explicit color mode from ``--color`` (or ``None``).
        no_color (bool): Whether ``--no-color`` was passed; forces color off.
    """
    ctx.obj = ctx.obj or {}

    # Configure program-output verbosity:
    level_cli = resolve_verbosity(verbose, quiet)
    ctx.obj["verbosity_level"] = level_cli

    # Configure internal logging via env:
    level_env = resolve_env_log_level()
    ctx.obj["log_level"] = level_env
    setup_logging(level=level_env)

    effective_color_mode = ColorMode.NEVER if no_color else (color_mode or ColorMode.AUTO)
    enable_color = resolve_color_mode(cli_mode=effective_color_mode, output_format=None)
    ctx.obj["color_enabled"] = enable_color
    ctx.color = enable_color

    console = ClickConsole(enable_color=not no_color)
    ctx.obj["console"] = console


@click.group(
    cls=click.Group,
    context_settings={"help_option_names": ["-h", "--help"]},
    invoke_without_command=True,  # Aalways invoke the cli() function
    help="TopMark CLI",
)
@common_verbose_options
@common_color_options
@click.pass_context
def cli(
    ctx: click.Context,
    verbose: int,
    quiet: int,
    color_mode: ColorMode | None,
    no_color: bool,
) -> None:
    """Entry point for the TopMark CLI."""
    # Initialize verbosity and color state once for all subcommands
    init_common_state(
        ctx,
        verbose=verbose,
        quiet=quiet,
        color_mode=color_mode,
        no_color=no_color,
    )
    console: ConsoleLike = ctx.obj["console"]

    if ctx.invoked_subcommand is None:
        console.print("Hint: use 'topmark check [PATHS...]' to validate headers.")
        console.print()
        console.print(ctx.get_help())


cli.add_command(version_command)

cli.add_command(show_defaults_command)

cli.add_command(init_config_command)

cli.add_command(dump_config_command)

cli.add_command(check_command)

cli.add_command(strip_command)

cli.add_command(filetypes_command)

cli.add_command(processors_command)

if __name__ == "__main__":
    cli()
