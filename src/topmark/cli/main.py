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

from typing import TYPE_CHECKING

import click

from topmark.cli.commands.check import check_command
from topmark.cli.commands.config import config_command
from topmark.cli.commands.probe import probe_command
from topmark.cli.commands.registry import registry_command
from topmark.cli.commands.strip import strip_command
from topmark.cli.commands.version import version_command
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt
from topmark.cli.options import GROUP_CONTEXT_SETTINGS
from topmark.cli.state import TopmarkCliState
from topmark.cli.state import bootstrap_cli_state
from topmark.core.formats import OutputFormat
from topmark.utils.version import check_python_version

if TYPE_CHECKING:
    from topmark.cli.console.protocols import ConsoleProtocol


@click.group(
    cls=click.Group,
    context_settings=GROUP_CONTEXT_SETTINGS,
    invoke_without_command=True,  # Always invoke the cli() function
    help="Inspect, validate, and manage TopMark headers and configuration.",
    epilog=(
        "\b\n"
        "Examples:\n"
        "  # Validate headers in a project (dry-run)\n"
        f"  topmark {CliCmd.CHECK} src\n"
        "  # Apply header updates in place\n"
        f"  topmark {CliCmd.CHECK} --apply .\n"
        "  # Write a starter configuration file\n"
        f"  topmark {CliCmd.CONFIG} {CliCmd.CONFIG_INIT} > topmark.toml\n"
        "  # Validate the merged configuration\n"
        f"  topmark {CliCmd.CONFIG} check\n"
        "  # Inspect file types (machine-readable output)\n"
        f"  topmark {CliCmd.REGISTRY} {CliCmd.REGISTRY_FILETYPES} "
        f"{CliOpt.OUTPUT_FORMAT}={OutputFormat.JSON.value}\n"
        "  # Print the installed TopMark version\n"
        f"  topmark {CliCmd.VERSION}\n"
    ),
)
@click.pass_context
def cli(
    ctx: click.Context,
) -> None:
    """TopMark CLI entry point.

    Bootstraps shared CLI state and delegates execution to subcommands.
    When invoked without a subcommand, prints a short hint and the help text.
    """
    # Check the Python version (may exit)
    check_python_version()

    # Subcommands now own verbosity/color options and call init_common_state().
    # Ensure we still have a console for the root group help output.
    state: TopmarkCliState = bootstrap_cli_state(ctx)
    console: ConsoleProtocol = state.console

    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())


cli.add_command(config_command)
cli.add_command(probe_command)
cli.add_command(check_command)
cli.add_command(strip_command)
cli.add_command(registry_command)
cli.add_command(version_command)
