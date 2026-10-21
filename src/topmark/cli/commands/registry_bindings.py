# topmark:header:start
#
#   project      : TopMark
#   file         : registry_bindings.py
#   file_relpath : src/topmark/cli/commands/registry_bindings.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""TopMark `registry bindings` command.

Prints file-type-to-processor binding metadata for human inspection or
machine-readable output.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import click
import rich_click

from topmark.cli.cmd_common import init_common_state
from topmark.cli.documentation import command_reference_url
from topmark.cli.emitters.machine import emit_bindings_machine
from topmark.cli.help import HelpExample
from topmark.cli.help import registry_queries_argument
from topmark.cli.help import render_examples_epilog
from topmark.cli.help import rich_click_option_panel
from topmark.cli.help_panels import DISPLAY_PANEL_OPTIONS
from topmark.cli.help_panels import OUTPUT_AND_HELP_PANEL_OPTIONS
from topmark.cli.help_panels import REGISTRY_BINDING_IDENTITY_FILTERING_PANEL_OPTIONS
from topmark.cli.help_panels import REGISTRY_DETAIL_PANEL_OPTIONS
from topmark.cli.help_panels import REGISTRY_FILTERING_PANEL_OPTIONS
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt
from topmark.cli.options import GROUP_CONTEXT_SETTINGS
from topmark.cli.options import common_color_options
from topmark.cli.options import common_output_format_options
from topmark.cli.options import common_text_output_verbosity_options
from topmark.cli.options import registry_binding_query_options
from topmark.cli.options import registry_details_options
from topmark.cli.options import registry_file_type_activation_options
from topmark.cli.state import TopmarkCliState
from topmark.cli.state import bootstrap_cli_state
from topmark.cli.validators import apply_color_policy_for_output_format
from topmark.cli.validators import apply_ignore_positional_paths_policy
from topmark.core.formats import OutputFormat
from topmark.core.machine.errors import unsupported_machine_readable_format
from topmark.core.machine.payloads import build_meta_payload
from topmark.core.machine.payloads import with_detail_level
from topmark.presentation.markdown.registry import render_bindings_markdown
from topmark.presentation.shared.registry import BindingsHumanReport
from topmark.presentation.shared.registry import build_bindings_human_report
from topmark.presentation.text.registry import render_bindings_text
from topmark.registry.query import BindingSelection
from topmark.registry.query import RegistryIdentityQuery
from topmark.registry.query import RegistryRegex

if TYPE_CHECKING:
    from topmark.cli.console.color import ColorMode
    from topmark.cli.console.protocols import ConsoleProtocol
    from topmark.core.machine.schemas import DetailedMetaPayload
    from topmark.registry.query import RegistryActivationFilter


@rich_click.command(
    name=CliCmd.REGISTRY_BINDINGS,
    context_settings=GROUP_CONTEXT_SETTINGS,
    help="Inspect TopMark file-type-to-processor bindings.",
    epilog=render_examples_epilog(
        examples=(
            HelpExample(
                summary="Inspect file-type-to-processor bindings",
                command_line=f"topmark {CliCmd.REGISTRY} {CliCmd.REGISTRY_BINDINGS}",
            ),
            HelpExample(
                summary="Show extended binding metadata",
                command_line=(
                    f"topmark {CliCmd.REGISTRY} {CliCmd.REGISTRY_BINDINGS} {CliOpt.SHOW_DETAILS}"
                ),
            ),
            HelpExample(
                summary="Emit machine-readable binding metadata",
                command_line=(
                    f"topmark {CliCmd.REGISTRY} {CliCmd.REGISTRY_BINDINGS} "
                    f"{CliOpt.OUTPUT_FORMAT}={OutputFormat.JSON.value}"
                ),
            ),
        ),
        notes=(
            "Bindings show which header processor handles each file type.",
            "Machine-readable formats emit registry metadata without human formatting.",
        ),
        reference_url=command_reference_url("commands/registry/bindings"),
    ),
)
@rich_click_option_panel(
    "Registry filtering",
    options=[
        *REGISTRY_FILTERING_PANEL_OPTIONS,
        *REGISTRY_BINDING_IDENTITY_FILTERING_PANEL_OPTIONS,
    ],
)
@rich_click_option_panel(
    "Output and display",
    options=[
        *DISPLAY_PANEL_OPTIONS,
        *REGISTRY_DETAIL_PANEL_OPTIONS,
        *OUTPUT_AND_HELP_PANEL_OPTIONS,
    ],
)
@common_color_options
@common_text_output_verbosity_options
@registry_details_options
@common_output_format_options
@registry_file_type_activation_options
@registry_binding_query_options
@registry_queries_argument()
def registry_bindings_command(
    *,
    # common_ui_options (verbosity, color):
    verbosity: int,
    color_mode: ColorMode | None,
    no_color: bool,
    # registry_details_options:
    show_details: bool = False,
    # registry_file_type_activation_options
    activation: RegistryActivationFilter | None = None,
    # positional registry queries and registry_identity_query_options
    registry_queries: tuple[RegistryIdentityQuery, ...] = (),
    registry_regexes: tuple[RegistryRegex, ...] = (),
    # common_output_format_options:
    output_format: OutputFormat | None,
) -> None:
    """Inspect TopMark file-type-to-processor bindings.

    Builds a registry report for resolved bindings between file type identifiers
    and header processors, with optional extended metadata.

    Args:
        verbosity: Increase TEXT output detail.
        color_mode: Set the color mode (default: auto).
        no_color: If set, disable color mode.
        show_details: Whether to show extended information about each binding.
        activation: Optional declared activation filters.
        registry_queries: Positional endpoint-identity inclusion predicates.
        registry_regexes: Whole-endpoint-identity regular-expression predicates.
        output_format: Output format to use (``text``, ``markdown``, ``json``, or ``ndjson``).

    Raises:
        ValueError: If an unsupported output format is requested.
    """  # noqa: DOC503 - raises ValueError via exception factory helper
    ctx: click.Context = click.get_current_context()
    state: TopmarkCliState = bootstrap_cli_state(ctx)

    # Effective output format (stored early so shared initialization sees it).
    state.output_format = output_format or OutputFormat.TEXT

    # Initialize the common state (verbosity, color mode) and initialize console
    init_common_state(
        ctx,
        verbosity=verbosity,
        quiet=False,
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

    selection: BindingSelection = BindingSelection(
        identity_queries=registry_queries,
        regexes=registry_regexes,
    )

    # `registry bindings` is file-agnostic: ignore positional PATHS
    apply_ignore_positional_paths_policy(
        ctx,
        warn_stdin_dash=True,
    )

    # Machine-readable formats
    if fmt in (OutputFormat.JSON, OutputFormat.NDJSON):
        emit_bindings_machine(
            console=console,
            meta=meta,
            fmt=fmt,
            show_details=show_details,
            activation=activation,
            selection=selection,
        )
        return

    # Human-facing formats (Markdown / Default) share a single Click-free preparer.
    report: BindingsHumanReport = build_bindings_human_report(
        show_details=show_details,
        verbosity_level=verbosity_level,
        styled=enable_color,
        activation=activation,
        selection=selection,
    )

    if fmt == OutputFormat.MARKDOWN:
        console.print(
            render_bindings_markdown(report=report),
        )
        return

    if fmt == OutputFormat.TEXT:
        console.print(
            render_bindings_text(report=report),
        )
        return

    # Defensive guard for direct callback use with an invalid format object.
    raise unsupported_machine_readable_format(fmt)
