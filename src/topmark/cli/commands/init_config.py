# topmark:header:start
#
#   file         : init_config.py
#   file_relpath : src/topmark/cli/commands/init_config.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""TopMark `init-config` command.

Prints an initial TopMark configuration file to stdout. The output includes a
generated header block and the default TOML configuration. Intended as a
starting point for customizing a project's configuration.
"""

import click
from yachalk import chalk

from topmark.cli.utils import default_header_overrides
from topmark.config import Config
from topmark.constants import PYPROJECT_TOML_PATH
from topmark.rendering.api import render_header_for_path


def init_config_command() -> None:
    """Print a starter config file to stdout.

    Outputs an initial TopMark configuration file with default values and a header.
    Intended as a starting point for customization in your own project.

    Returns:
        None. Prints output to stdout.
    """
    # TODO: use topmark to generate this header
    click.echo(chalk.bold.underline("Initial TopMark Configuration:"))

    header_overrides = default_header_overrides(
        info="Initial TopMark configuration -- adjust according to your needs",
        file_label="topmark.toml",
    )

    topmark_header = render_header_for_path(
        config=Config.from_defaults(),
        path=PYPROJECT_TOML_PATH,
        header_fields_overrides=["file", "version", "info", "license", "copyright"],
        header_overrides=header_overrides,
    )

    click.echo(
        chalk.gray(
            f"""\
{topmark_header}

{Config.get_default_config_toml()}
## === END of TopMark Configuration ===
"""
        )
    )
