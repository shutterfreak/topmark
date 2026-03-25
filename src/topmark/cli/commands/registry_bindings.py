# topmark:header:start
#
#   project      : TopMark
#   file         : registry_bindings.py
#   file_relpath : src/topmark/cli/commands/registry_bindings.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI command to list effective file type to processor bindings.

This module defines a command-line interface (CLI) command that lists all bindings
registered in TopMark. It supports various output formats,
including JSON, NDJSON, Markdown, and a default human-readable format.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import click

from topmark.cli.cmd_common import init_common_state
from topmark.cli.emitters.machine import emit_bindings_machine
from topmark.cli.keys import CliCmd
from topmark.cli.options import GROUP_CONTEXT_SETTINGS
from topmark.cli.options import common_output_format_options
from topmark.cli.options import common_ui_options
from topmark.cli.options import registry_details_options
from topmark.cli.validators import apply_color_policy_for_output_format
from topmark.cli.validators import apply_ignore_positional_paths_policy
from topmark.core.formats import OutputFormat
from topmark.core.keys import ArgKey
from topmark.core.machine.payloads import build_meta_payload
from topmark.core.machine.payloads import with_detail_level
from topmark.presentation.markdown.registry import render_bindings_markdown
from topmark.presentation.shared.registry import BindingsHumanReport
from topmark.presentation.shared.registry import build_bindings_human_report
from topmark.presentation.text.registry import render_bindings_text

if TYPE_CHECKING:
    from topmark.cli.console.color import ColorMode
    from topmark.cli.console.protocols import ConsoleProtocol
    from topmark.core.machine.schemas import DetailedMetaPayload


@click.command(
    name=CliCmd.REGISTRY_BINDINGS,
    context_settings=GROUP_CONTEXT_SETTINGS,
    help="List registered header bindings.",
    epilog="""
Lists all effective file type to processor bindings resolved by TopMark.
Use this command to inspect how file types are mapped to header processors.""",
)
# Common option decorators
@common_ui_options
@registry_details_options
@common_output_format_options
def registry_bindings_command(
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
    """List registered bindings.

    Prints all bindings supported by TopMark, including the file types they handle.
    Useful for reference when configuring file type filters.

    Args:
        verbose: Incements the verbosity level,
        quiet: Decrements the verbosity level,
        color_mode: Set the color mode (derfault: autp),
        no_color: bool: If set, disable color mode.
        show_details: Whether to show extended information about each binding.
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

    # Machine metadata: extend with show_details:
    meta: DetailedMetaPayload = with_detail_level(
        build_meta_payload(),
        show_details=show_details,
    )

    # Output format
    fmt: OutputFormat = output_format or OutputFormat.TEXT

    apply_color_policy_for_output_format(ctx, fmt=fmt)
    enable_color: bool = ctx.obj[ArgKey.COLOR_ENABLED]

    # config_check_command() is file-agnostic: ignore positional PATHS
    apply_ignore_positional_paths_policy(
        ctx,
        warn_stdin_dash=True,
    )

    # Machine formats
    if fmt in (OutputFormat.JSON, OutputFormat.NDJSON):
        emit_bindings_machine(
            meta=meta,
            fmt=fmt,
            show_details=show_details,
        )
        return

    # Human-facing formats (Markdown / Default) share a single Click-free preparer.
    report: BindingsHumanReport = build_bindings_human_report(
        show_details=show_details,
        verbosity_level=verbosity_level,
        styled=enable_color,
    )

    if fmt == OutputFormat.MARKDOWN:
        console.print(render_bindings_markdown(report=report))
        return

    if fmt == OutputFormat.TEXT:
        console.print(render_bindings_text(report=report))
        return

    # Defensive guard
    raise ValueError(f"Unsupported output format: {fmt!r}")
