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
from topmark.cli.keys import CliCmd, CliOpt
from topmark.cli.machine_emitters import emit_machine
from topmark.cli.options import underscored_trap_option
from topmark.core.formats import (
    OutputFormat,
    is_machine_format,
)
from topmark.core.keys import ArgKey
from topmark.utils.version import compute_version_text
from topmark.version.machine import serialize_version

if TYPE_CHECKING:
    from collections.abc import Iterable

    from topmark.cli_shared.console_api import ConsoleLike
    from topmark.core.machine.schemas import MetaPayload


@click.command(
    name=CliCmd.VERSION,
    help="Show the current version of TopMark.",
)
@click.option(
    CliOpt.SEMVER_VERSION,
    ArgKey.SEMVER_VERSION,
    is_flag=True,
    default=False,
    help="Render the version as SemVer instead of PEP 440 (maps rc→-rc.N, dev→-dev.N).",
)
@click.option(
    CliOpt.OUTPUT_FORMAT,
    ArgKey.OUTPUT_FORMAT,
    type=EnumChoiceParam(OutputFormat),
    default=None,
    help=f"Output format ({', '.join(v.value for v in OutputFormat)}).",
)
@underscored_trap_option("--output_format")
def version_command(
    *,
    output_format: OutputFormat | None = None,
    semver: bool = False,
) -> None:
    """Show the current version of TopMark.

    Prints the TopMark version as installed in the current Python environment.

    Args:
        output_format: Optional output format (plain text or markdown).
        semver: Return version identifier in `semver` if True, PEP440 (default) if False.
    """
    ctx: click.Context = click.get_current_context()
    ctx.ensure_object(dict)

    # Machine metadata
    meta: MetaPayload = ctx.obj[ArgKey.META]

    if output_format and is_machine_format(output_format):
        # Disable color mode for machine formats
        ctx.obj[ArgKey.COLOR_ENABLED] = False

    console: ConsoleLike = ctx.obj[ArgKey.CONSOLE]

    # Determine effective program-output verbosity for gating extra details
    vlevel: int = get_effective_verbosity(ctx)

    fmt: OutputFormat = output_format or OutputFormat.DEFAULT

    if fmt in (OutputFormat.JSON, OutputFormat.NDJSON):
        serialized: str | Iterable[str] = serialize_version(
            meta=meta,
            fmt=fmt,
            semver=semver,
        )
        # Do not emit trailing newline for JSON
        nl: bool = fmt != OutputFormat.JSON
        emit_machine(serialized, nl=nl)
    else:
        version_text, version_format, _err = compute_version_text(semver=semver)
        # TODO: decide how to render the error

        if fmt == OutputFormat.MARKDOWN:
            console.print("# TopMark Version\n")
            console.print(f"**TopMark version ({version_format}): {version_text}**")
        else:  # Plain text (default)
            if vlevel > 0:
                console.print(
                    console.styled(
                        f"TopMark version ({version_format}):\n", bold=True, underline=True
                    )
                )
                console.print(f"    {console.styled(version_text, bold=True)}")
            else:
                console.print(console.styled(version_text, bold=True))

    # No explicit return needed for Click commands.
