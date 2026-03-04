# topmark:header:start
#
#   project      : TopMark
#   file         : config.py
#   file_relpath : src/topmark/cli/commands/config.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""TopMark `config` command group.

Provides a family of subcommands for inspecting and scaffolding TopMark
configuration:

  * ``topmark config check``: check merged configuration for errors.
  * ``topmark config dump``: show the effective merged configuration.
  * ``topmark config defaults``: show the built-in default configuration.
  * ``topmark config init``: print a starter configuration file.
"""

from __future__ import annotations

import click

from topmark.cli.commands.config_check import config_check_command
from topmark.cli.commands.config_defaults import config_defaults_command
from topmark.cli.commands.config_dump import config_dump_command
from topmark.cli.commands.config_init import config_init_command
from topmark.cli.keys import CliCmd
from topmark.cli.options import GROUP_CONTEXT_SETTINGS


@click.group(
    name=CliCmd.CONFIG,
    context_settings=GROUP_CONTEXT_SETTINGS,
    help="Inspect and scaffold TopMark configuration.",
)
def config_command() -> None:
    """Group for configuration-related subcommands.

    This group itself performs no action; use one of its subcommands:

      * ``check``: check the configuration for errors.
      * ``dump``: show the effective merged configuration.
      * ``defaults``: show the built-in default configuration reference.
      * ``init``: print a starter configuration file for projects.
    """
    # No-op: behavior is provided by subcommands only.


# Attach existing commands as subcommands of `topmark config`
config_command.add_command(config_check_command, name=CliCmd.CONFIG_CHECK)
config_command.add_command(config_dump_command, name=CliCmd.CONFIG_DUMP)
config_command.add_command(config_defaults_command, name=CliCmd.CONFIG_DEFAULTS)
config_command.add_command(config_init_command, name=CliCmd.CONFIG_INIT)
