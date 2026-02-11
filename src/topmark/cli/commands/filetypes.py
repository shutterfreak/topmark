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

from topmark.cli.cmd_common import (
    get_effective_verbosity,
    init_common_state,
)
from topmark.cli.emitters.text.registry import emit_filetypes_text
from topmark.cli.keys import CliCmd, CliOpt
from topmark.cli.machine_emitters import emit_filetypes_machine
from topmark.cli.options import (
    common_output_format_options,
    common_ui_options,
)
from topmark.cli.validators import (
    apply_color_policy_for_output_format,
    apply_ignore_positional_paths_policy,
)
from topmark.cli_shared.emitters.markdown.registry import render_filetypes_markdown
from topmark.cli_shared.emitters.shared.registry import (
    FileTypesHumanReport,
    build_filetypes_human_report,
)
from topmark.core.formats import OutputFormat
from topmark.core.keys import ArgKey

if TYPE_CHECKING:
    from topmark.cli_shared.color import ColorMode
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
# Common option decorators
@common_ui_options
@common_output_format_options
# Command-specific option decorators
@click.option(
    CliOpt.SHOW_DETAILS,
    ArgKey.SHOW_DETAILS,
    is_flag=True,
    help="Show extended information (extensions, filenames, patterns, skip policy, header policy).",
)
def filetypes_command(
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
    """List supported file types.

    Prints all file types supported by TopMark, including their identifiers and descriptions.
    Useful for reference when configuring file type filters.

    Args:
        verbose: Incements the verbosity level,
        quiet: Decrements  the verbosity level,
        color_mode: Set the color mode (derfault: autp),
        no_color: bool: If set, disable color mode.
        output_format: Output format to use
            (``text``, ``markdown``, ``json``, or ``ndjson``).
        show_details: If True, shows extended information about each file type,
            including associated extensions, filenames, patterns, skip policy, and header policy.

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

    if fmt == OutputFormat.TEXT:
        report = build_filetypes_human_report(
            show_details=show_details,
            verbosity_level=vlevel,
        )
        emit_filetypes_text(console=console, report=report)
        return

    # Defensive guard
    raise ValueError(f"Unsupported output format: {fmt!r}")
