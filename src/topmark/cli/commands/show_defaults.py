# topmark:header:start
#
#   project      : TopMark
#   file         : show_defaults.py
#   file_relpath : src/topmark/cli/commands/show_defaults.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""TopMark `show-defaults` command.

Displays the built-in default TopMark configuration. This includes the default
header template and the default TOML configuration bundled with the package.
Intended as a reference for users customizing their own configuration files.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import click

from topmark.cli.cmd_common import get_effective_verbosity
from topmark.config import MutableConfig

if TYPE_CHECKING:
    from topmark.cli_shared.console_api import ConsoleLike


@click.command(
    name="show-defaults",
    help="Display the built-in default TopMark configuration file.",
)
def show_defaults_command() -> None:
    """Display the built-in default configuration.

    Outputs the TopMark default configuration file as bundled with the package.
    Useful as a reference for configuration structure and default values.
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
                "Default TopMark Configuration (TOML):",
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
            MutableConfig.to_cleaned_toml(MutableConfig.get_default_config_toml()),
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
