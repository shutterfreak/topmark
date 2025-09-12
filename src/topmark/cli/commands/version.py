# topmark:header:start
#
#   project      : TopMark
#   file         : version.py
#   file_relpath : src/topmark/cli/commands/version.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""TopMark `version` command.

Prints the current TopMark version as installed in the active Python environment.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import click

from topmark.cli.cli_types import EnumChoiceParam
from topmark.cli.cmd_common import get_effective_verbosity
from topmark.cli_shared.utils import OutputFormat
from topmark.constants import TOPMARK_VERSION

if TYPE_CHECKING:
    from topmark.cli_shared.console_api import ConsoleLike


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
        output_format (OutputFormat | None): Optional output format (plain text or markdown).
    """
    ctx = click.get_current_context()
    ctx.ensure_object(dict)
    console: ConsoleLike = ctx.obj["console"]

    # Determine effective program-output verbosity for gating extra details
    vlevel = get_effective_verbosity(ctx)

    topmark_version = TOPMARK_VERSION
    fmt: OutputFormat = output_format or OutputFormat.DEFAULT

    if fmt in (OutputFormat.JSON, OutputFormat.NDJSON):
        import json

        console.print(json.dumps({"topmark_version": topmark_version}))
    elif fmt == OutputFormat.MARKDOWN:
        console.print("# TopMark Version\n")
        console.print(f"**TopMark version {topmark_version}**")
    else:  # Plain text (default)
        if vlevel > 0:
            console.print(console.styled("TopMark version:\n", bold=True, underline=True))
            console.print(f"    {console.styled(topmark_version, bold=True)}")
        else:
            console.print(console.styled(topmark_version, bold=True))

    # No explicit return needed for Click commands.
