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

from topmark.cli.cmd_common import init_common_state
from topmark.cli.commands.check import check_command
from topmark.cli.commands.config import config_command
from topmark.cli.commands.filetypes import filetypes_command
from topmark.cli.commands.processors import processors_command
from topmark.cli.commands.strip import strip_command
from topmark.cli.commands.version import version_command
from topmark.cli.keys import CliCmd, CliOpt

# --- We use a module import here instead of relative import
from topmark.config.logging import (
    get_logger,
)
from topmark.core.keys import ArgKey
from topmark.pipeline.processors import register_all_processors
from topmark.utils.version import check_python_version

if TYPE_CHECKING:
    from topmark.cli_shared.console_api import ConsoleLike
    from topmark.config.logging import TopmarkLogger

logger: TopmarkLogger = get_logger(__name__)

register_all_processors()


@click.group(
    cls=click.Group,
    context_settings={"help_option_names": ["-h", CliOpt.HELP]},
    invoke_without_command=True,  # Aalways invoke the cli() function
    help="TopMark CLI",
)
@click.pass_context
def cli(
    ctx: click.Context,
    # verbose: int,
    # quiet: int,
    # color_mode: ColorMode | None,
    # no_color: bool,
) -> None:
    """Entry point for the TopMark CLI."""
    # Check the Python version (may exit)
    check_python_version()

    # Subcommands now own verbosity/color options and call init_common_state().
    # Ensure we still have a console for the root group help output.
    ctx.ensure_object(dict)
    if ArgKey.CONSOLE not in ctx.obj:
        init_common_state(
            ctx,
            verbose=0,
            quiet=0,
            color_mode=None,
            no_color=False,
        )
    console: ConsoleLike = ctx.obj[ArgKey.CONSOLE]

    if ctx.invoked_subcommand is None:
        console.print(f"Hint: use 'topmark {CliCmd.CHECK} [PATHS...]' to validate headers.")
        console.print()
        console.print(ctx.get_help())


cli.add_command(version_command)
cli.add_command(config_command)
cli.add_command(check_command)
cli.add_command(strip_command)
cli.add_command(filetypes_command)
cli.add_command(processors_command)
