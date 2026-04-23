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
from topmark.cli.options import GROUP_CONTEXT_SETTINGS
from topmark.cli.options import common_output_format_options
from topmark.cli.options import common_ui_options
from topmark.cli.options import version_format_options
from topmark.cli.validators import apply_color_policy_for_output_format
from topmark.cli.validators import apply_ignore_positional_paths_policy
from topmark.core.formats import OutputFormat
from topmark.core.keys import ArgKey
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
    help="Show the current version of TopMark.",
)
@common_ui_options
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
    """Show the current version of TopMark.

    Prints the TopMark version as installed in the current Python environment.

    Args:
        verbosity: Verbosity level.
        quiet: Suppresses human-readable output.
        color_mode: Set the color mode (default: auto).
        no_color: bool: If set, disable color mode.
        semver: Whether to attempt to render the version as SemVer (default: PEP 440).
        output_format: Output format to use (``text``, ``markdown``, ``json``, or ``ndjson``).

    Raises:
        ValueError: If an unsupported output format is requested.
    """
    ctx: click.Context = click.get_current_context()
    ctx.ensure_object(dict)

    # Initialize the common state (verbosity, color mode) and initialize console
    init_common_state(
        ctx,
        verbosity=verbosity,
        quiet=quiet,
        color_mode=color_mode,
        no_color=no_color,
    )

    # Retrieve effective human facing program-output verbosity for gating extra details
    verbosity_level: int = ctx.obj[ArgKey.VERBOSITY]

    # Select the console
    console: ConsoleProtocol = ctx.obj[ArgKey.CONSOLE]

    # Machine metadata
    meta: MetaPayload = build_meta_payload()

    # Output format
    fmt: OutputFormat = output_format or OutputFormat.TEXT

    apply_color_policy_for_output_format(ctx, fmt=fmt)
    enable_color: bool = ctx.obj[ArgKey.COLOR_ENABLED]

    # version_command() is file-agnostic: ignore positional PATHS
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
        emit_machine(serialized, nl=nl)
        return

    report: VersionHumanReport = make_version_human_report(
        verbosity_level=verbosity_level,
        styled=enable_color,
        semver=semver,
    )

    if fmt == OutputFormat.TEXT:
        console.print(render_version_text(report))
        return

    if fmt == OutputFormat.MARKDOWN:
        console.print(render_version_markdown(report), nl=False)
        return

    # Defensive guard
    raise ValueError(f"Unsupported output format: {fmt!r}")
