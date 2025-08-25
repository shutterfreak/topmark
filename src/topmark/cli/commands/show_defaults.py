# topmark:header:start
#
#   file         : show_defaults.py
#   file_relpath : src/topmark/cli/commands/show_defaults.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""TopMark `show-defaults` command.

Displays the built-in default TopMark configuration. This includes the default
header template and the default TOML configuration bundled with the package.
Intended as a reference for users customizing their own configuration files.
"""

import click
from yachalk import chalk

from topmark.cli.utils import default_header_overrides
from topmark.config import Config
from topmark.constants import PYPROJECT_TOML_PATH
from topmark.rendering.api import render_header_for_path


def show_defaults_command() -> None:
    """Display the built-in default configuration.

    Prints the TopMark default configuration as bundled with the package, including a header.
    Useful as a reference for configuration structure and default values.

    Returns:
        None. Prints output to stdout.
    """
    header_overrides = default_header_overrides(
        info="Default TopMark Configuration", file_label="topmark.toml"
    )
    topmark_header = render_header_for_path(
        config=Config.from_defaults(),
        path=PYPROJECT_TOML_PATH,
        header_fields_overrides=["file", "version", "info", "license", "copyright"],
        header_overrides=header_overrides,
    )

    click.echo(chalk.bold.underline("Default TopMark Configuration:"))
    click.echo(
        chalk.gray(
            f"""\
{topmark_header}
{Config.to_cleaned_toml(Config.get_default_config_toml())}
## === END of TopMark Configuration ==="""
        )
    )
