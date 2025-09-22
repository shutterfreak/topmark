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
from topmark.utils.version import pep440_to_semver

if TYPE_CHECKING:
    from topmark.cli_shared.console_api import ConsoleLike


@click.command(
    name="version",
    help="Show the current version of TopMark.",
)
@click.option(
    "--semver",
    is_flag=True,
    default=False,
    help="Render the version as SemVer instead of PEP 440 (maps rc→-rc.N, dev→-dev.N).",
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
    semver: bool = False,
) -> None:
    """Show the current version of TopMark.

    Prints the TopMark version as installed in the current Python environment.

    Args:
        output_format (OutputFormat | None): Optional output format (plain text or markdown).
        semver (bool): Return version identifier in `semver` if True, PEP440 (default) if False.
    """
    ctx = click.get_current_context()
    ctx.ensure_object(dict)
    console: ConsoleLike = ctx.obj["console"]

    # Determine effective program-output verbosity for gating extra details
    vlevel = get_effective_verbosity(ctx)

    topmark_version: str = TOPMARK_VERSION
    fmt: OutputFormat = output_format or OutputFormat.DEFAULT
    version_text: str = topmark_version
    if semver:
        try:
            version_text = pep440_to_semver(topmark_version)
        except ValueError as exc:
            # Fall back to raw version; if verbose, surface the reason.
            if vlevel > 0:
                console.print(console.styled(f"[warn] {exc}", bold=True))

    format: str = "semver" if semver else "pep440"
    if fmt in (OutputFormat.JSON, OutputFormat.NDJSON):
        import json

        console.print(json.dumps({"version": version_text, "format": format}))
    elif fmt == OutputFormat.MARKDOWN:
        console.print("# TopMark Version\n")
        console.print(f"**TopMark version ({format}): {version_text}**")
    else:  # Plain text (default)
        if vlevel > 0:
            console.print(
                console.styled(f"TopMark version ({format}):\n", bold=True, underline=True)
            )
            console.print(f"    {console.styled(version_text, bold=True)}")
        else:
            console.print(console.styled(version_text, bold=True))

    # No explicit return needed for Click commands.
