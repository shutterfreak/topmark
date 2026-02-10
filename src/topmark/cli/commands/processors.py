# topmark:header:start
#
#   project      : TopMark
#   file         : processors.py
#   file_relpath : src/topmark/cli/commands/processors.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI command to list registered header processors.

This module defines a command-line interface (CLI) command that lists all header processors
registered in TopMark, along with the file types they handle. It supports various output formats,
including JSON, NDJSON, Markdown, and a default human-readable format.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import click

from topmark.cli.cli_types import EnumChoiceParam
from topmark.cli.cmd_common import get_effective_verbosity
from topmark.cli.emitters.default.registry import emit_processors_default
from topmark.cli.keys import CliCmd, CliOpt
from topmark.cli.machine_emitters import emit_processors_machine
from topmark.cli.options import underscored_trap_option
from topmark.cli_shared.emitters.markdown.registry import render_processors_markdown
from topmark.cli_shared.emitters.shared.registry import (
    ProcessorsHumanReport,
    build_processors_human_report,
)
from topmark.core.formats import (
    OutputFormat,
    is_machine_format,
)
from topmark.core.keys import ArgKey

if TYPE_CHECKING:
    from topmark.cli_shared.console_api import ConsoleLike
    from topmark.core.machine.schemas import MetaPayload


@click.command(
    name=CliCmd.PROCESSORS,
    help="List registered header processors.",
    epilog="""
Lists all header processors currently registered in TopMark, along with the file types they handle.
Use this command to see which processors are available and which file types they support.""",
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
    help="Show extended information (file types and their description).",
)
def processors_command(
    *,
    show_details: bool = False,
    output_format: OutputFormat | None = None,
) -> None:
    """List registered header processors.

    Prints all header processors supported by TopMark, including the file types they handle.
    Useful for reference when configuring file type filters.

    Args:
        show_details: If True, shows extended information about each processor,
            including associated file types and their descriptions.
        output_format: Output format to use
            (``default``, ``json``, ``ndjson``, or ``markdown``).
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

    # Machine formats
    if fmt in (OutputFormat.JSON, OutputFormat.NDJSON):
        emit_processors_machine(
            meta=meta,
            fmt=fmt,
            show_details=show_details,
        )
        return

    # Human-facing formats (Markdown / Default) share a single Click-free preparer.
    report: ProcessorsHumanReport = build_processors_human_report(
        show_details=show_details,
        verbosity_level=vlevel,
    )

    if fmt == OutputFormat.MARKDOWN:
        console.print(render_processors_markdown(report=report))
        return

    if fmt == OutputFormat.DEFAULT:
        emit_processors_default(console=console, report=report)
        return

    # Defensive guard
    raise ValueError(f"Unsupported output format: {fmt!r}")
