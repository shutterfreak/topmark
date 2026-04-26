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

from topmark.cli.cmd_common import init_common_state
from topmark.cli.emitters.machine import emit_machine
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt
from topmark.cli.options import GROUP_CONTEXT_SETTINGS
from topmark.cli.options import common_color_options
from topmark.cli.options import common_output_format_options
from topmark.cli.options import common_text_output_quiet_options
from topmark.cli.options import common_text_output_verbosity_options
from topmark.cli.options import version_format_options
from topmark.cli.state import TopmarkCliState
from topmark.cli.state import bootstrap_cli_state
from topmark.cli.validators import apply_color_policy_for_output_format
from topmark.cli.validators import apply_ignore_positional_paths_policy
from topmark.core.formats import OutputFormat
from topmark.core.machine.payloads import build_meta_payload
from topmark.presentation.markdown.version import render_version_markdown
from topmark.presentation.shared.version import VersionHumanReport
from topmark.presentation.shared.version import make_version_human_report
from topmark.presentation.text.version import render_version_text
from topmark.version.machine.serializers import serialize_version

if TYPE_CHECKING:
    from collections.abc import Iterable

    from topmark.cli.console.color import ColorMode
    from topmark.cli.console.protocols import ConsoleProtocol
    from topmark.core.machine.schemas import MetaPayload


@click.command(
    name=CliCmd.VERSION,
    context_settings=GROUP_CONTEXT_SETTINGS,
    help="Print the installed TopMark version.",
    epilog=(
        "\b\n"
        "Examples:\n"
        "  # Print the installed TopMark version\n"
        f"  topmark {CliCmd.VERSION}\n"
        "  # Print the version in SemVer form when possible\n"
        f"  topmark {CliCmd.VERSION} {CliOpt.SEMVER_VERSION}\n"
        "  # Emit machine-readable version metadata\n"
        f"  topmark {CliCmd.VERSION} "
        f"{CliOpt.OUTPUT_FORMAT}={OutputFormat.JSON.value}\n"
        "Notes:\n"
        "  • Default output uses the installed package version.\n"
        "  • Machine formats emit structured version metadata.\n"
    ),
)
@common_color_options
@common_text_output_verbosity_options
@common_text_output_quiet_options
@version_format_options
@common_output_format_options
def version_command(
    *,
    # common_ui_options (verbosity, color):
    verbosity: int,
    quiet: bool,
    color_mode: ColorMode | None,
    no_color: bool,
    # version_format_options:
    semver: bool = False,
    # common_output_format_options:
    output_format: OutputFormat | None,
) -> None:
    """Print the installed TopMark version.

    Renders the installed package version for human-readable or machine-readable
    output, optionally normalized to SemVer when possible.

    Args:
        verbosity: Increase TEXT output detail.
        quiet: Suppresses default TEXT output.
        color_mode: Set the color mode (default: auto).
        no_color: bool: If set, disable color mode.
        semver: Whether to attempt to render the version as SemVer (default: PEP 440).
        output_format: Output format to use (``text``, ``markdown``, ``json``, or ``ndjson``).
            Verbosity and quiet controls apply only to TEXT output.

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

    # Select the console
    console: ConsoleProtocol = state.console

    # Machine metadata
    meta: MetaPayload = build_meta_payload()

    # Output format
    fmt: OutputFormat = state.output_format

    apply_color_policy_for_output_format(ctx, fmt=fmt)
    enable_color: bool = state.color_enabled

    # `version` is file-agnostic: ignore positional PATHS
    apply_ignore_positional_paths_policy(ctx, warn_stdin_dash=True)

    # Machine formats
    if fmt in (OutputFormat.JSON, OutputFormat.NDJSON):
        serialized: str | Iterable[str] = serialize_version(
            meta=meta,
            fmt=fmt,
            semver=semver,
        )
        # Do not emit trailing newline for JSON
        nl: bool = fmt != OutputFormat.JSON
        emit_machine(serialized, console=console, nl=nl)
        return

    report: VersionHumanReport = make_version_human_report(
        verbosity_level=state.verbosity,
        quiet=state.quiet,
        styled=enable_color,
        semver=semver,
    )

    if fmt == OutputFormat.TEXT:
        rendered: str = render_version_text(report)
        # Quiet TEXT output renders as an empty string; avoid emitting a blank line.
        if rendered:
            console.print(rendered)
        return

    if fmt == OutputFormat.MARKDOWN:
        console.print(
            render_version_markdown(report),
            nl=False,
        )
        return

    # Defensive guard
    raise ValueError(f"Unsupported output format: {fmt!r}")
