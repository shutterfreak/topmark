# topmark:header:start
#
#   project      : TopMark
#   file         : registry_filetypes.py
#   file_relpath : src/topmark/cli/commands/registry_filetypes.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""TopMark `registry filetypes` command.

Prints registered file type metadata for human inspection or machine-readable output.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import click

from topmark.cli.cmd_common import init_common_state
from topmark.cli.emitters.machine import emit_filetypes_machine
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt
from topmark.cli.options import GROUP_CONTEXT_SETTINGS
from topmark.cli.options import common_output_format_options
from topmark.cli.options import common_ui_options
from topmark.cli.options import registry_details_options
from topmark.cli.state import TopmarkCliState
from topmark.cli.state import bootstrap_cli_state
from topmark.cli.validators import apply_color_policy_for_output_format
from topmark.cli.validators import apply_ignore_positional_paths_policy
from topmark.core.formats import OutputFormat
from topmark.core.machine.payloads import build_meta_payload
from topmark.core.machine.payloads import with_detail_level
from topmark.presentation.markdown.registry import render_filetypes_markdown
from topmark.presentation.shared.registry import FileTypesHumanReport
from topmark.presentation.shared.registry import build_filetypes_human_report
from topmark.presentation.text.registry import render_filetypes_text

if TYPE_CHECKING:
    from topmark.cli.console.color import ColorMode
    from topmark.cli.console.protocols import ConsoleProtocol
    from topmark.core.machine.schemas import DetailedMetaPayload


@click.command(
    name=CliCmd.REGISTRY_FILETYPES,
    context_settings=GROUP_CONTEXT_SETTINGS,
    help="Inspect registered TopMark file types.",
    epilog=(
        "\b\n"
        "Examples:\n"
        "  # Inspect registered file types\n"
        f"  topmark {CliCmd.REGISTRY} {CliCmd.REGISTRY_FILETYPES}\n"
        "  # Show extended file type metadata\n"
        f"  topmark {CliCmd.REGISTRY} {CliCmd.REGISTRY_FILETYPES} {CliOpt.SHOW_DETAILS}\n"
        "  # Emit machine-readable file type metadata\n"
        f"  topmark {CliCmd.REGISTRY} {CliCmd.REGISTRY_FILETYPES} "
        f"{CliOpt.OUTPUT_FORMAT}={OutputFormat.JSON.value}\n"
        "\n"
        "Notes:\n"
        "  • Use file type identifiers in configuration filters.\n"
        "  • Machine formats emit registry metadata without human formatting.\n"
    ),
)
@common_ui_options
@registry_details_options
@common_output_format_options
def registry_filetypes_command(
    *,
    # common_ui_options (verbosity, color):
    verbosity: int,
    quiet: bool,
    color_mode: ColorMode | None,
    no_color: bool,
    # registry_details_options:
    show_details: bool = False,
    # common_output_format_options:
    output_format: OutputFormat | None,
) -> None:
    """Inspect registered TopMark file types.

    Builds a registry report for file type identifiers, matching metadata, and
    optional extended policy details.

    Args:
        verbosity: Increase human-output detail.
        quiet: Suppress human-readable output.
        color_mode: Set the color mode (default: auto).
        no_color: bool: If set, disable color mode.
        show_details: Whether to show extended information about each file type,
            including associated extensions, filenames, patterns, skip policy, and header policy.
        output_format: Output format to use (``text``, ``markdown``, ``json``, or ``ndjson``).

    Raises:
        ValueError: If an unsupported output format is requested.
    """
    ctx: click.Context = click.get_current_context()
    state: TopmarkCliState = bootstrap_cli_state(ctx)

    # Effective output format (stored early so shared initialization sees it).
    state.output_format = output_format or OutputFormat.TEXT

    # Initialize the common state (verbosity, color mode) and initialize console
    init_common_state(
        ctx,
        verbosity=verbosity,
        quiet=quiet,
        color_mode=color_mode,
        no_color=no_color,
    )

    # Retrieve effective human facing program-output verbosity for gating extra details
    verbosity_level: int = state.verbosity

    # Select the console
    console: ConsoleProtocol = state.console

    # Machine metadata: extend with show_details:
    meta: DetailedMetaPayload = with_detail_level(
        build_meta_payload(),
        show_details=show_details,
    )

    # Output format
    fmt: OutputFormat = state.output_format

    apply_color_policy_for_output_format(ctx, fmt=fmt)
    enable_color: bool = state.color_enabled

    # `registry filetypes` is file-agnostic: ignore positional PATHS
    apply_ignore_positional_paths_policy(
        ctx,
        warn_stdin_dash=True,
    )

    # Machine formats
    if fmt in (OutputFormat.JSON, OutputFormat.NDJSON):
        emit_filetypes_machine(
            console=console,
            meta=meta,
            fmt=fmt,
            show_details=show_details,
        )
        return

    # Human-facing formats (Markdown / Default) share a single Click-free preparer.
    report: FileTypesHumanReport = build_filetypes_human_report(
        show_details=show_details,
        verbosity_level=verbosity_level,
        styled=enable_color,
    )

    if fmt == OutputFormat.MARKDOWN:
        console.print(
            render_filetypes_markdown(report=report),
        )
        return

    if fmt == OutputFormat.TEXT:
        console.print(
            render_filetypes_text(report),
        )
        return

    # Defensive guard
    raise ValueError(f"Unsupported output format: {fmt!r}")
