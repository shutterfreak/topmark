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
from topmark.cli.emitters.default.version import emit_version_default
from topmark.cli.keys import CliCmd, CliOpt
from topmark.cli.machine_emitters import emit_machine
from topmark.cli.options import underscored_trap_option
from topmark.cli_shared.emitters.markdown.version import emit_version_markdown
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
        output_format: Optional output format (default, markdown, json, ndjson).
        semver: If True, attempt to render the version as SemVer; otherwise use PEP 440.

    Raises:
        ValueError: If an unsupported output format is requested.
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
        return

    version_text, version_format, err = compute_version_text(semver=semver)

    if fmt == OutputFormat.DEFAULT:
        emit_version_default(
            console=console,
            version_text=version_text,
            version_format=version_format,
            verbosity_level=vlevel,
            error=err,
        )
        return

    if fmt == OutputFormat.MARKDOWN:
        md: str = emit_version_markdown(
            version_text=version_text,
            version_format=version_format,
            error=err,
        )
        click.echo(md, nl=False)
        return

    # Defensive guard
    raise ValueError(f"Unsupported output format: {fmt!r}")
