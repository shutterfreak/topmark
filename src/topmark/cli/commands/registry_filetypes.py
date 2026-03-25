# topmark:header:start
#
#   project      : TopMark
#   file         : registry_filetypes.py
#   file_relpath : src/topmark/cli/commands/registry_filetypes.py
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

from topmark.cli.cmd_common import init_common_state
from topmark.cli.emitters.machine import emit_filetypes_machine
from topmark.cli.emitters.text.registry import emit_filetypes_text
from topmark.cli.keys import CliCmd
from topmark.cli.options import GROUP_CONTEXT_SETTINGS
from topmark.cli.options import common_output_format_options
from topmark.cli.options import common_ui_options
from topmark.cli.options import registry_details_options
from topmark.cli.validators import apply_color_policy_for_output_format
from topmark.cli.validators import apply_ignore_positional_paths_policy
from topmark.cli_shared.emitters.markdown.registry import render_filetypes_markdown
from topmark.cli_shared.emitters.shared.registry import FileTypesHumanReport
from topmark.cli_shared.emitters.shared.registry import build_filetypes_human_report
from topmark.core.formats import OutputFormat
from topmark.core.keys import ArgKey

if TYPE_CHECKING:
    from topmark.cli.console.color import ColorMode
    from topmark.cli.console.protocols import ConsoleProtocol
    from topmark.core.machine.schemas import MetaPayload


@click.command(
    name=CliCmd.REGISTRY_FILETYPES,
    context_settings=GROUP_CONTEXT_SETTINGS,
    help="List all supported file types.",
    epilog="""
Lists all file types currently supported by TopMark, along with a brief description of each.
Use this command to see which file types can be processed and referenced in configuration.
""",
)
@common_ui_options
@registry_details_options
@common_output_format_options
def registry_filetypes_command(
    *,
    # common_ui_options (verbosity, color):
    verbose: int,
    quiet: int,
    color_mode: ColorMode | None,
    no_color: bool,
    # registry_details_options:
    show_details: bool = False,
    # common_output_format_options:
    output_format: OutputFormat | None,
) -> None:
    """List supported file types.

    Prints all file types supported by TopMark, including their identifiers and descriptions.
    Useful for reference when configuring file type filters.

    Args:
        verbose: Incements the verbosity level,
        quiet: Decrements  the verbosity level,
        color_mode: Set the color mode (derfault: autp),
        no_color: bool: If set, disable color mode.
        show_details: Whether to show extended information about each file type,
            including associated extensions, filenames, patterns, skip policy, and header policy.
        output_format: Output format to use (``text``, ``markdown``, ``json``, or ``ndjson``).

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

    # Retrieve effective human facing program-output verbosity for gating extra details
    verbosity_level: int = ctx.obj[ArgKey.VERBOSITY_LEVEL]

    # Select the console
    console: ConsoleProtocol = ctx.obj[ArgKey.CONSOLE]

    # Machine metadata
    meta: MetaPayload = ctx.obj[ArgKey.META]

    # Output format
    fmt: OutputFormat = output_format or OutputFormat.TEXT

    apply_color_policy_for_output_format(ctx, fmt=fmt)

    # config_check_command() is file-agnostic: ignore positional PATHS
    apply_ignore_positional_paths_policy(
        ctx,
        warn_stdin_dash=True,
    )

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
            verbosity_level=verbosity_level,
        )
        console.print(render_filetypes_markdown(report=report))
        return

    if fmt == OutputFormat.TEXT:
        report = build_filetypes_human_report(
            show_details=show_details,
            verbosity_level=verbosity_level,
        )
        emit_filetypes_text(console=console, report=report)
        return

    # Defensive guard
    raise ValueError(f"Unsupported output format: {fmt!r}")
