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
from topmark.cli.commands.registry import registry_command
from topmark.cli.commands.strip import strip_command
from topmark.cli.commands.version import version_command
from topmark.cli.keys import CliCmd
from topmark.cli.options import GROUP_CONTEXT_SETTINGS
from topmark.core.keys import ArgKey
from topmark.utils.version import check_python_version

if TYPE_CHECKING:
    from topmark.cli.console.protocols import ConsoleProtocol


@click.group(
    cls=click.Group,
    context_settings=GROUP_CONTEXT_SETTINGS,
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
            verbosity=0,
            quiet=False,
            color_mode=None,
            no_color=False,
        )
    console: ConsoleProtocol = ctx.obj[ArgKey.CONSOLE]

    if ctx.invoked_subcommand is None:
        console.print(f"Hint: use 'topmark {CliCmd.CHECK} [PATHS...]' to validate headers.")
        console.print()
        console.print(ctx.get_help())


cli.add_command(config_command)
cli.add_command(check_command)
cli.add_command(strip_command)
cli.add_command(registry_command)
cli.add_command(version_command)
