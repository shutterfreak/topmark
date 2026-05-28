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

Provides subcommands for validating, inspecting, and scaffolding TopMark
configuration:

  * ``topmark config check``: validate the effective runtime configuration.
  * ``topmark config dump``: print the effective runtime configuration.
  * ``topmark config defaults``: print the canonical built-in default TOML document.
  * ``topmark config init``: print a starter configuration file.
"""

from __future__ import annotations

import rich_click

from topmark.cli.commands.config_check import config_check_command
from topmark.cli.commands.config_defaults import config_defaults_command
from topmark.cli.commands.config_dump import config_dump_command
from topmark.cli.commands.config_init import config_init_command
from topmark.cli.help import HelpExample
from topmark.cli.help import render_examples_epilog
from topmark.cli.keys import CliCmd
from topmark.cli.options import GROUP_CONTEXT_SETTINGS


@rich_click.group(
    cls=rich_click.RichGroup,
    name=CliCmd.CONFIG,
    context_settings=GROUP_CONTEXT_SETTINGS,
    help="Validate, inspect, and scaffold TopMark configuration.",
    epilog=render_examples_epilog(
        examples=(
            HelpExample(
                summary="Validate the effective runtime configuration",
                command_line=f"topmark {CliCmd.CONFIG} {CliCmd.CONFIG_CHECK}",
            ),
            HelpExample(
                summary="Print the effective runtime configuration",
                command_line=f"topmark {CliCmd.CONFIG} {CliCmd.CONFIG_DUMP}",
            ),
            HelpExample(
                summary="Print the built-in default configuration reference",
                command_line=f"topmark {CliCmd.CONFIG} {CliCmd.CONFIG_DEFAULTS}",
            ),
            HelpExample(
                summary="Create a starter configuration file for projects",
                command_line=f"topmark {CliCmd.CONFIG} {CliCmd.CONFIG_INIT} > topmark.toml",
            ),
        ),
    ),
)
def config_command() -> None:
    """Group for configuration-related subcommands.

    This group performs no action itself; use one of its subcommands:

      * ``check``: validate the effective runtime configuration.
      * ``dump``: print the effective runtime configuration.
      * ``defaults``: print the canonical built-in defaults.
      * ``init``: print a starter configuration file for projects.
    """
    # No-op: behavior is provided by subcommands only.


# Attach existing commands as subcommands of `topmark config`
config_command.add_command(
    config_check_command,
    name=CliCmd.CONFIG_CHECK,
)
config_command.add_command(
    config_dump_command,
    name=CliCmd.CONFIG_DUMP,
)
config_command.add_command(
    config_defaults_command,
    name=CliCmd.CONFIG_DEFAULTS,
)
config_command.add_command(
    config_init_command,
    name=CliCmd.CONFIG_INIT,
)
