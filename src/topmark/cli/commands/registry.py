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

Provides subcommands for inspecting TopMark registry metadata:

  * ``topmark registry filetypes``: inspect registered file types.
  * ``topmark registry processors``: inspect registered header processors.
  * ``topmark registry bindings``: inspect file-type-to-processor bindings.
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
    help="Inspect TopMark registry metadata.",
    epilog=(
        "\b\n"
        "Examples:\n"
        "  # Inspect registered file types\n"
        f"  topmark {CliCmd.REGISTRY} {CliCmd.REGISTRY_FILETYPES}\n"
        "  # Inspect registered header processors\n"
        f"  topmark {CliCmd.REGISTRY} {CliCmd.REGISTRY_PROCESSORS}\n"
        "  # Inspect file-type-to-processor bindings\n"
        f"  topmark {CliCmd.REGISTRY} {CliCmd.REGISTRY_BINDINGS}\n"
    ),
)
def registry_command() -> None:
    """Group for registry-related subcommands.

    This group performs no action itself; use one of its subcommands:

      * ``filetypes``: inspect registered file types.
      * ``processors``: inspect registered header processors.
      * ``bindings``: inspect file-type-to-processor bindings.
    """
    # No-op: behavior is provided by subcommands only.


# Attach existing commands as subcommands of `topmark registry`
registry_command.add_command(
    registry_filetypes_command,
    name=CliCmd.REGISTRY_FILETYPES,
)
registry_command.add_command(
    registry_processors_command,
    name=CliCmd.REGISTRY_PROCESSORS,
)
registry_command.add_command(
    registry_bindings_command,
    name=CliCmd.REGISTRY_BINDINGS,
)
