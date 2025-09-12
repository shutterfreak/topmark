# topmark:header:start
#
#   project      : TopMark
#   file         : init_config.py
#   file_relpath : src/topmark/cli/commands/init_config.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""TopMark `init-config` command.

Prints an initial TopMark configuration file to stdout. The output includes a
generated header block and the default TOML configuration. Intended as a
starting point for customizing a project's configuration.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import click

from topmark.cli.cmd_common import get_effective_verbosity
from topmark.config import MutableConfig

if TYPE_CHECKING:
    from topmark.cli_shared.console_api import ConsoleLike


@click.command(
    name="init-config",
    help="Display an initial TopMark configuration file.",
)
def init_config_command() -> None:
    """Print a starter config file to stdout.

    Outputs an initial TopMark configuration file with default values.
    Intended as a starting point for customization in your own project.
    """
    ctx = click.get_current_context()
    ctx.ensure_object(dict)
    console: ConsoleLike = ctx.obj["console"]

    # Determine effective program-output verbosity for gating extra details
    vlevel = get_effective_verbosity(ctx)

    # Banner
    if vlevel > 0:
        console.print(
            console.styled(
                "Initial TopMark Configuration (TOML):",
                bold=True,
                underline=True,
            )
        )

        console.print(
            console.styled(
                "# === BEGIN ===",
                fg="cyan",
                dim=True,
            )
        )

    console.print(
        console.styled(
            MutableConfig.get_default_config_toml(),
            fg="cyan",
        )
    )

    if vlevel > 0:
        console.print(
            console.styled(
                "# === END ===",
                fg="cyan",
                dim=True,
            )
        )

    # No explicit return needed for Click commands.
