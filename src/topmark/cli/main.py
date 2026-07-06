# topmark:header:start
#
#   project      : TopMark
#   file         : main.py
#   file_relpath : src/topmark/cli/main.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""TopMark CLI entry point.

Defines the root Click command group and wires together all subcommands.

Key ideas:
- The root Click group bootstraps a shared typed CLI state.
- Subcommands own verbosity/color options and initialize shared human-output state.
- The root command ensures help output has a console available.

This module intentionally stays compact to keep CLI wiring explicit and predictable.
"""

from __future__ import annotations

import click
import rich_click

from topmark.cli.cmd_common import init_common_state
from topmark.cli.commands.check import check_command
from topmark.cli.commands.config import config_command
from topmark.cli.commands.probe import probe_command
from topmark.cli.commands.registry import registry_command
from topmark.cli.commands.strip import strip_command
from topmark.cli.commands.version import version_command
from topmark.cli.console.color import ColorMode
from topmark.cli.help import HelpExample
from topmark.cli.help import render_examples_epilog
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt
from topmark.cli.options import GROUP_CONTEXT_SETTINGS
from topmark.cli.state import TopmarkCliState
from topmark.cli.state import bootstrap_cli_state
from topmark.core.formats import OutputFormat
from topmark.utils.version import check_python_version


@rich_click.group(
    cls=rich_click.RichGroup,
    context_settings=GROUP_CONTEXT_SETTINGS,
    invoke_without_command=True,  # Always invoke the cli() function
    help="Inspect, validate, and manage TopMark headers and configuration.",
    epilog=render_examples_epilog(
        examples=(
            HelpExample(
                summary="Validate headers in a project (dry-run)",
                command_line=f"topmark {CliCmd.CHECK} src",
            ),
            HelpExample(
                summary="Apply header updates in place",
                command_line=f"topmark {CliCmd.CHECK} --apply .",
            ),
            HelpExample(
                summary="Write a starter configuration file",
                command_line=f"topmark {CliCmd.CONFIG} {CliCmd.CONFIG_INIT} > topmark.toml",
            ),
            HelpExample(
                summary="Validate the merged configuration",
                command_line=f"topmark {CliCmd.CONFIG} check",
            ),
            HelpExample(
                summary="Inspect file types (machine-readable output)",
                command_line=(
                    f"topmark {CliCmd.REGISTRY} {CliCmd.REGISTRY_FILETYPES} "
                    f"{CliOpt.OUTPUT_FORMAT}={OutputFormat.JSON.value}"
                ),
            ),
            HelpExample(
                summary="Print the installed TopMark version",
                command_line=f"topmark {CliCmd.VERSION}",
            ),
        ),
    ),
)
@click.pass_context
def cli(
    ctx: click.Context,
) -> None:
    """TopMark CLI entry point.

    Bootstraps shared CLI state and delegates execution to subcommands.
    When invoked without a subcommand, renders the root help page explicitly.
    """
    # Check the Python version (may exit)
    check_python_version()

    # Subcommands own verbosity/color options and call init_common_state().
    # The root command has no command-specific options, but `topmark` without a
    # subcommand still renders help explicitly through the configured console.
    # Match the default human-output policy used by command help: auto color,
    # non-quiet text output.

    if ctx.invoked_subcommand is None:
        # Ensure we still have a console for the root group help output.
        init_common_state(
            ctx,
            verbosity=0,
            quiet=False,
            color_mode=ColorMode.AUTO,
            no_color=False,
        )
        state: TopmarkCliState = bootstrap_cli_state(ctx)
        state.console.print(ctx.get_help())


cli.add_command(config_command)
cli.add_command(probe_command)
cli.add_command(check_command)
cli.add_command(strip_command)
cli.add_command(registry_command)
cli.add_command(version_command)
