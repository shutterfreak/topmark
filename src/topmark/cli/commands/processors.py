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

from topmark.cli.cmd_common import (
    get_effective_verbosity,
    init_common_state,
)
from topmark.cli.emitters.text.registry import emit_processors_text
from topmark.cli.keys import CliCmd, CliOpt
from topmark.cli.machine_emitters import emit_processors_machine
from topmark.cli.options import (
    common_output_format_options,
    common_ui_options,
)
from topmark.cli.validators import (
    apply_color_policy_for_output_format,
    apply_ignore_positional_paths_policy,
)
from topmark.cli_shared.emitters.markdown.registry import render_processors_markdown
from topmark.cli_shared.emitters.shared.registry import (
    ProcessorsHumanReport,
    build_processors_human_report,
)
from topmark.core.formats import OutputFormat
from topmark.core.keys import ArgKey

if TYPE_CHECKING:
    from topmark.cli_shared.color import ColorMode
    from topmark.cli_shared.console_api import ConsoleLike
    from topmark.core.machine.schemas import MetaPayload


@click.command(
    name=CliCmd.PROCESSORS,
    help="List registered header processors.",
    epilog="""
Lists all header processors currently registered in TopMark, along with the file types they handle.
Use this command to see which processors are available and which file types they support.""",
)
# Common option decorators
@common_ui_options
@common_output_format_options
# Command-specific option decorators
@click.option(
    CliOpt.SHOW_DETAILS,
    ArgKey.SHOW_DETAILS,
    is_flag=True,
    help="Show extended information (file types and their description).",
)
def processors_command(
    *,
    # Command options: common options (verbosity, color)
    verbose: int,
    quiet: int,
    color_mode: ColorMode | None,
    no_color: bool,
    # Command options: output format
    output_format: OutputFormat | None,
    # Command-specific options:
    show_details: bool = False,
) -> None:
    """List registered header processors.

    Prints all header processors supported by TopMark, including the file types they handle.
    Useful for reference when configuring file type filters.

    Args:
        verbose: Incements the verbosity level,
        quiet: Decrements  the verbosity level,
        color_mode: Set the color mode (derfault: autp),
        no_color: bool: If set, disable color mode.
        output_format: Output format to use
            (``text``, ``markdown``, ``json``, or ``ndjson``).
        show_details: If True, shows extended information about each processor,
            including associated file types and their descriptions.

    Raises:
        ValueError: If an unsupported output format is requested.
    """
    ctx: click.Context = click.get_current_context()
    ctx.ensure_object(dict)

    # Initialize the common state (verbosity, color mode) and initialize console
    init_common_state(
        ctx,
        verbose=verbose,
        quiet=quiet,
        color_mode=color_mode,
        no_color=no_color,
    )

    # Select the console
    console: ConsoleLike = ctx.obj[ArgKey.CONSOLE]

    # Machine metadata
    meta: MetaPayload = ctx.obj[ArgKey.META]

    # Output format
    fmt: OutputFormat = output_format or OutputFormat.TEXT

    apply_color_policy_for_output_format(ctx, fmt=fmt)

    # config_check_command() is file-agnostic: ignore positional PATHS
    apply_ignore_positional_paths_policy(ctx, warn_stdin_dash=True)

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

    if fmt == OutputFormat.TEXT:
        emit_processors_text(console=console, report=report)
        return

    # Defensive guard
    raise ValueError(f"Unsupported output format: {fmt!r}")
