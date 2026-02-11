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

from topmark.cli.cmd_common import (
    get_effective_verbosity,
    init_common_state,
)
from topmark.cli.emitters.text.version import emit_version_text
from topmark.cli.keys import CliCmd, CliOpt
from topmark.cli.machine_emitters import emit_machine
from topmark.cli.options import (
    common_output_format_options,
    common_ui_options,
)
from topmark.cli.validators import (
    apply_color_policy_for_output_format,
    apply_ignore_positional_paths_policy,
)
from topmark.cli_shared.emitters.markdown.version import emit_version_markdown
from topmark.core.formats import OutputFormat
from topmark.core.keys import ArgKey
from topmark.utils.version import compute_version_text
from topmark.version.machine import serialize_version

if TYPE_CHECKING:
    from collections.abc import Iterable

    from topmark.cli_shared.color import ColorMode
    from topmark.cli_shared.console_api import ConsoleLike
    from topmark.core.machine.schemas import MetaPayload


@click.command(
    name=CliCmd.VERSION,
    help="Show the current version of TopMark.",
)
# Common option decorators
@common_ui_options
@common_output_format_options
# Command-specific option decorators
@click.option(
    CliOpt.SEMVER_VERSION,
    ArgKey.SEMVER_VERSION,
    is_flag=True,
    default=False,
    help="Render the version as SemVer instead of PEP 440 (maps rc→-rc.N, dev→-dev.N).",
)
def version_command(
    *,
    # Command options: common options (verbosity, color)
    verbose: int,
    quiet: int,
    color_mode: ColorMode | None,
    no_color: bool,
    # Command options: output format
    output_format: OutputFormat | None,
    # Command-specific options:
    semver: bool = False,
) -> None:
    """Show the current version of TopMark.

    Prints the TopMark version as installed in the current Python environment.

    Args:
        verbose: Incements the verbosity level,
        quiet: Decrements  the verbosity level,
        color_mode: Set the color mode (derfault: autp),
        no_color: bool: If set, disable color mode.
        output_format: Output format to use
            (``text``, ``markdown``, ``json``, or ``ndjson``).
        semver: If True, attempt to render the version as SemVer; otherwise use PEP 440.

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
        serialized: str | Iterable[str] = serialize_version(
            meta=meta,
            fmt=fmt,
            semver=semver,
        )
        # Do not emit trailing newline for JSON
        nl: bool = fmt != OutputFormat.JSON
        emit_machine(serialized, nl=nl)
        return

    version_text, version_format, err = compute_version_text(semver=semver)

    if fmt == OutputFormat.TEXT:
        emit_version_text(
            console=console,
            version_text=version_text,
            version_format=version_format,
            verbosity_level=vlevel,
            error=err,
        )
        return

    if fmt == OutputFormat.MARKDOWN:
        md: str = emit_version_markdown(
            version_text=version_text,
            version_format=version_format,
            error=err,
        )
        console.print(md, nl=False)
        return

    # Defensive guard
    raise ValueError(f"Unsupported output format: {fmt!r}")
