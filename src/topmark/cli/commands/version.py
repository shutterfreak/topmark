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

from topmark.cli.cli_types import EnumChoiceParam
from topmark.cli_shared.utils import OutputFormat
from topmark.constants import TOPMARK_VERSION


@click.command(
    name="version",
    help="Show the current version of TopMark.",
)
@click.option(
    "--format",
    "output_format",
    type=EnumChoiceParam(OutputFormat),
    default=None,
    help=f"Output format ({', '.join(v.value for v in OutputFormat)}).",
)
def version_command(
    *,
    output_format: OutputFormat | None = None,
) -> None:
    """Show the current version of TopMark.

    Prints the TopMark version as installed in the current Python environment.

    Args:
        output_format: Optional output format (plain text or markdown).

    Returns:
        None. Prints output to stdout.
    """
    topmark_version = TOPMARK_VERSION
    fmt: OutputFormat = output_format or OutputFormat.DEFAULT

    if fmt in (OutputFormat.JSON, OutputFormat.NDJSON):
        import json

        click.echo(json.dumps({"topmark_version": topmark_version}))
    elif fmt == OutputFormat.MARKDOWN:
        click.echo("# TopMark Version\n")
        click.echo(f"**TopMark version {topmark_version}**")
    else:  # Plain text (default)
        click.secho(f"TopMark version: {click.style(topmark_version, bold=True)}")

    # No explicit return needed for Click commands.
