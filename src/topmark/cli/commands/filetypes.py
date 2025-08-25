# topmark:header:start
#
#   file         : filetypes.py
#   file_relpath : src/topmark/cli/commands/filetypes.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""TopMark `filetypes` command.

Lists all file types supported by TopMark along with their identifiers and
descriptions. Useful for discovering available file type filters when
configuring headers.
"""

import click
from yachalk import chalk

from topmark.filetypes.instances import get_file_type_registry


def filetypes_command() -> None:
    """List supported file types.

    Prints all file types supported by TopMark, including their identifiers and descriptions.
    Useful for reference when configuring file type filters.

    Returns:
        None. Prints output to stdout.
    """
    click.echo(chalk.bold.underline("Supported file types:"))

    file_types = get_file_type_registry()
    for key, value in sorted(file_types.items()):
        # key is file type identifier (name)
        # value contains the file type fields (e.g., description)
        click.echo(f"  - {key:<12} {chalk.dim(value.description)}")
