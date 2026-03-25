# topmark:header:start
#
#   project      : TopMark
#   file         : registry.py
#   file_relpath : src/topmark/cli/commands/registry.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""TopMark `registry` command group.

Provides a family of subcommands for inspecting the TopMark registry:

  * ``topmark registry bindings``: show the registered bindings.
  * ``topmark registry filetypes``: show the registered file types.
  * ``topmark registry processors``: show the registered processors.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import click

from topmark.cli.commands.registry_bindings import registry_bindings_command
from topmark.cli.commands.registry_filetypes import registry_filetypes_command
from topmark.cli.commands.registry_processors import registry_processors_command
from topmark.cli.keys import CliCmd
from topmark.cli.options import GROUP_CONTEXT_SETTINGS
from topmark.core.logging import get_logger

if TYPE_CHECKING:
    from topmark.core.logging import TopmarkLogger


logger: TopmarkLogger = get_logger(__name__)


@click.group(
    name=CliCmd.REGISTRY,
    context_settings=GROUP_CONTEXT_SETTINGS,
    help="Inspect the TopMark registry.",
)
def registry_command() -> None:
    """Group for registry-related subcommands.

    This group itself performs no action; use one of its subcommands:

      * ``filetypes``: show the registered filetypes.
      * ``processors``: show the registered processors.
      * ``bindings``: show the registered bindings.
    """
    # No-op: behavior is provided by subcommands only.


# Attach existing commands as subcommands of `topmark config`
registry_command.add_command(registry_filetypes_command, name=CliCmd.REGISTRY_FILETYPES)
registry_command.add_command(registry_processors_command, name=CliCmd.REGISTRY_PROCESSORS)
registry_command.add_command(registry_bindings_command, name=CliCmd.REGISTRY_BINDINGS)
