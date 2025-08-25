# topmark:header:start
#
#   file         : version.py
#   file_relpath : src/topmark/cli/commands/version.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""TopMark `version` command.

Prints the current TopMark version as installed in the active Python environment.
"""

from __future__ import annotations

import click

from topmark.constants import TOPMARK_VERSION


def version_command() -> None:
    """Show the current version of TopMark.

    Prints the TopMark version as installed in the current Python environment.

    Returns:
        None. Prints output to stdout.
    """
    topmark_version = TOPMARK_VERSION
    click.echo(f"TopMark version: {topmark_version}")
