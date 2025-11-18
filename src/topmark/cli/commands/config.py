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

  * ``topmark config dump``: show the effective merged configuration.
  * ``topmark config defaults``: show the built-in default configuration.
  * ``topmark config init``: print a starter configuration file.
"""

from __future__ import annotations

import click

from topmark.cli.options import CONTEXT_SETTINGS
from topmark.config.logging import TopmarkLogger, get_logger

from .config_defaults import config_defaults_command
from .config_dump import config_dump_command
from .config_init import config_init_command

logger: TopmarkLogger = get_logger(__name__)


@click.group(
    name="config",
    help="Inspect and scaffold TopMark configuration.",
    context_settings=CONTEXT_SETTINGS,
)
def config_command() -> None:
    """Group for configuration-related subcommands.

    This group itself performs no action; use one of its subcommands:

      * ``dump``: show the effective merged configuration.
      * ``defaults``: show the built-in default configuration reference.
      * ``init``: print a starter configuration file for projects.
    """
    # No-op: behavior is provided by subcommands only.


# Attach existing commands as subcommands of `topmark config`
config_command.add_command(config_dump_command, name="dump")
config_command.add_command(config_defaults_command, name="defaults")
config_command.add_command(config_init_command, name="init")
