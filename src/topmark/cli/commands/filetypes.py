# topmark:header:start
#
#   project      : TopMark
#   file         : filetypes.py
#   file_relpath : src/topmark/cli/commands/filetypes.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""TopMark `filetypes` command.

Lists all file types supported by TopMark along with their identifiers and descriptions. Useful for
discovering available file type filters when configuring headers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import click

from topmark.cli.cli_types import EnumChoiceParam
from topmark.cli.cmd_common import get_effective_verbosity
from topmark.cli.emitters.default.registry import emit_filetypes_default
from topmark.cli.keys import CliCmd, CliOpt
from topmark.cli.machine_emitters import emit_filetypes_machine
from topmark.cli.options import underscored_trap_option
from topmark.cli_shared.emitters.markdown.registry import render_filetypes_markdown
from topmark.cli_shared.emitters.shared.registry import (
    FileTypesHumanReport,
    build_filetypes_human_report,
)
from topmark.core.formats import OutputFormat, is_machine_format
from topmark.core.keys import ArgKey

if TYPE_CHECKING:
    from topmark.cli_shared.console_api import ConsoleLike
    from topmark.core.machine.schemas import MetaPayload


@click.command(
    name=CliCmd.FILETYPES,
    help="List all supported file types.",
    epilog="""
Lists all file types currently supported by TopMark, along with a brief description of each.
Use this command to see which file types can be processed and referenced in configuration.
""",
)
@click.option(
    CliOpt.OUTPUT_FORMAT,
    ArgKey.OUTPUT_FORMAT,
    type=EnumChoiceParam(OutputFormat),
    default=None,
    help=f"Output format ({', '.join(v.value for v in OutputFormat)}).",
)
@underscored_trap_option("--output_format")
@click.option(
    CliOpt.SHOW_DETAILS,
    ArgKey.SHOW_DETAILS,
    is_flag=True,
    help="Show extended information (extensions, filenames, patterns, skip policy, header policy).",
)
def filetypes_command(
    *,
    show_details: bool = False,
    output_format: OutputFormat | None = None,
) -> None:
    """List supported file types.

    Prints all file types supported by TopMark, including their identifiers and descriptions.
    Useful for reference when configuring file type filters.

    Args:
        show_details: If True, shows extended information about each file type,
            including associated extensions, filenames, patterns, skip policy, and header policy.
        output_format: Output format to use
            (``default``, ``json``, or ``ndjson``).
            If ``None``, uses the default human-readable format.

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

    fmt: OutputFormat = output_format or OutputFormat.DEFAULT

    # Determine effective program-output verbosity for gating extra details
    vlevel: int = get_effective_verbosity(ctx)

    if fmt in (OutputFormat.JSON, OutputFormat.NDJSON):
        emit_filetypes_machine(
            meta=meta,
            fmt=fmt,
            show_details=show_details,
        )
        return

    if fmt == OutputFormat.MARKDOWN:
        report: FileTypesHumanReport = build_filetypes_human_report(
            show_details=show_details,
            verbosity_level=vlevel,
        )
        console.print(render_filetypes_markdown(report=report))
        return

    if fmt == OutputFormat.DEFAULT:
        report = build_filetypes_human_report(
            show_details=show_details,
            verbosity_level=vlevel,
        )
        emit_filetypes_default(console=console, report=report)
        return

    # Defensive guard
    raise ValueError(f"Unsupported output format: {fmt!r}")
