# topmark:header:start
#
#   project      : TopMark
#   file         : registry_processors.py
#   file_relpath : src/topmark/cli/commands/registry_processors.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""TopMark `registry processors` command.

Prints registered header processor metadata for human inspection or machine-readable output.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import click
import rich_click

from topmark.cli.cmd_common import init_common_state
from topmark.cli.documentation import command_reference_url
from topmark.cli.emitters.machine import emit_processors_machine
from topmark.cli.help import HelpExample
from topmark.cli.help import registry_queries_argument
from topmark.cli.help import render_examples_epilog
from topmark.cli.help import rich_click_option_panel
from topmark.cli.help_panels import DISPLAY_PANEL_OPTIONS
from topmark.cli.help_panels import OUTPUT_AND_HELP_PANEL_OPTIONS
from topmark.cli.help_panels import REGISTRY_DETAIL_PANEL_OPTIONS
from topmark.cli.help_panels import REGISTRY_IDENTITY_FILTERING_PANEL_OPTIONS
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt
from topmark.cli.options import GROUP_CONTEXT_SETTINGS
from topmark.cli.options import common_color_options
from topmark.cli.options import common_output_format_options
from topmark.cli.options import common_text_output_verbosity_options
from topmark.cli.options import registry_details_options
from topmark.cli.options import registry_identity_query_options
from topmark.cli.state import TopmarkCliState
from topmark.cli.state import bootstrap_cli_state
from topmark.cli.validators import apply_color_policy_for_output_format
from topmark.core.formats import OutputFormat
from topmark.core.machine.errors import unsupported_machine_readable_format
from topmark.core.machine.payloads import build_meta_payload
from topmark.core.machine.payloads import with_detail_level
from topmark.presentation.markdown.registry import render_processors_markdown
from topmark.presentation.shared.registry import ProcessorsHumanReport
from topmark.presentation.shared.registry import build_processors_human_report
from topmark.presentation.text.registry import render_processors_text
from topmark.registry.query import RegistryIdentityQuery
from topmark.registry.query import RegistryRegex
from topmark.registry.query import RegistrySelection

if TYPE_CHECKING:
    from topmark.cli.console.color import ColorMode
    from topmark.cli.console.protocols import ConsoleProtocol
    from topmark.core.machine.schemas import DetailedMetaPayload


@rich_click.command(
    name=CliCmd.REGISTRY_PROCESSORS,
    context_settings=GROUP_CONTEXT_SETTINGS,
    help="Inspect registered TopMark header processors.",
    epilog=render_examples_epilog(
        examples=(
            HelpExample(
                summary="Inspect registered header processors",
                command_line=f"topmark {CliCmd.REGISTRY} {CliCmd.REGISTRY_PROCESSORS}",
            ),
            HelpExample(
                summary="Show extended processor metadata",
                command_line=(
                    f"topmark {CliCmd.REGISTRY} {CliCmd.REGISTRY_PROCESSORS} {CliOpt.SHOW_DETAILS}"
                ),
            ),
            HelpExample(
                summary="Emit machine-readable processor metadata",
                command_line=(
                    f"topmark {CliCmd.REGISTRY} {CliCmd.REGISTRY_PROCESSORS} "
                    f"{CliOpt.OUTPUT_FORMAT}={OutputFormat.JSON.value}"
                ),
            ),
            HelpExample(
                summary="Inspect the built-in Markdown processor",
                command_line=(
                    f"topmark {CliCmd.REGISTRY} {CliCmd.REGISTRY_PROCESSORS} "
                    f"{CliOpt.REGISTRY_BUILTIN} markdown"
                ),
            ),
        ),
        notes=(
            "Processors define how TopMark detects and renders headers for file types.",
            "Machine-readable formats emit registry metadata without human formatting.\n",
        ),
        reference_url=command_reference_url("commands/registry/processors"),
    ),
)
@rich_click_option_panel(
    "Registry filtering",
    options=[
        *REGISTRY_IDENTITY_FILTERING_PANEL_OPTIONS,
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
@registry_identity_query_options
@registry_queries_argument()
def registry_processors_command(
    *,
    # common_ui_options (verbosity, color):
    verbosity: int,
    color_mode: ColorMode | None,
    no_color: bool,
    # registry_details_options:
    show_details: bool = False,
    # positional registry queries and registry_identity_query_options
    registry_queries: tuple[RegistryIdentityQuery, ...] = (),
    registry_regexes: tuple[RegistryRegex, ...] = (),
    registry_builtin: bool = False,
    # common_output_format_options:
    output_format: OutputFormat | None,
) -> None:
    """Inspect registered TopMark header processors.

    Builds a registry report for processor identifiers, supported file types,
    and optional extended binding metadata.

    Args:
        verbosity: Increase TEXT output detail.
        color_mode: Set the color mode (default: auto).
        no_color: bool: If set, disable color mode.
        show_details: Whether to show extended information about each processor,
            including associated file types and their descriptions.
        registry_queries: Positional identity inclusion predicates.
        registry_regexes: Whole-identity regular-expression inclusion predicates.
        registry_builtin: Restrict entries to the built-in `topmark` namespace.
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

    selection: RegistrySelection = RegistrySelection(
        identity_queries=registry_queries,
        regexes=registry_regexes,
        builtin_only=registry_builtin,
    )

    if fmt in (OutputFormat.JSON, OutputFormat.NDJSON):
        emit_processors_machine(
            console=console,
            meta=meta,
            fmt=fmt,
            show_details=show_details,
            selection=selection,
        )
        return

    # Human-facing formats (Markdown / Default) share a single Click-free preparer.
    report: ProcessorsHumanReport = build_processors_human_report(
        show_details=show_details,
        verbosity_level=verbosity_level,
        styled=enable_color,
        selection=selection,
    )

    if fmt == OutputFormat.MARKDOWN:
        console.print(
            render_processors_markdown(report=report),
        )
        return

    if fmt == OutputFormat.TEXT:
        console.print(
            render_processors_text(report=report),
        )
        return

    # Defensive guard for direct callback use with an invalid format object.
    raise unsupported_machine_readable_format(fmt)
