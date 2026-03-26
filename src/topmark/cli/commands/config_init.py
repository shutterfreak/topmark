# topmark:header:start
#
#   project      : TopMark
#   file         : config_init.py
#   file_relpath : src/topmark/cli/commands/config_init.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""TopMark `config init` command.

Prints a starter TopMark configuration file to stdout. Uses the annotated,
commented default TOML template bundled with the package as a scaffold.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import click

from topmark.cli.cmd_common import init_common_state
from topmark.cli.emitters.machine import emit_config_machine
from topmark.cli.keys import CliCmd
from topmark.cli.options import GROUP_CONTEXT_SETTINGS
from topmark.cli.options import common_output_format_options
from topmark.cli.options import common_ui_options
from topmark.cli.options import config_pyproject_options
from topmark.cli.options import config_root_options
from topmark.cli.validators import apply_color_policy_for_output_format
from topmark.cli.validators import apply_ignore_positional_paths_policy
from topmark.cli.validators import validate_human_only_config_flags_for_machine_format
from topmark.config.io.deserializers import mutable_config_from_defaults
from topmark.core.formats import OutputFormat
from topmark.core.keys import ArgKey
from topmark.core.machine.payloads import build_meta_payload
from topmark.presentation.markdown.config import render_config_init_markdown
from topmark.presentation.shared.config import ConfigInitHumanReport
from topmark.presentation.shared.config import build_config_init_human_report
from topmark.presentation.text.config import render_config_init_text

if TYPE_CHECKING:
    from topmark.cli.console.color import ColorMode
    from topmark.cli.console.protocols import ConsoleProtocol
    from topmark.config.model import MutableConfig
    from topmark.core.machine.schemas import MetaPayload


@click.command(
    name=CliCmd.CONFIG_INIT,
    context_settings=GROUP_CONTEXT_SETTINGS,
    help=(
        "Print a starter TopMark configuration file. "
        "This command is file-agnostic: positional PATHS are ignored "
        "and --stdin-filename is not allowed. "
        "Use --output-format json/ndjson for a machine-readable config snapshot."
    ),
    epilog=(
        "Notes:\n"
        "  • text/markdown output uses the annotated, commented template bundled with TopMark.\n"
        "  • json/ndjson output emits a minimal Config snapshot (no comments, no diagnostics).\n"
        "  • See docs/dev/machine_outputs.md for machine output conventions.\n"
    ),
)
# Common option decorators
@common_ui_options
@config_pyproject_options
@config_root_options
@common_output_format_options
def config_init_command(
    *,
    # common_ui_options (verbosity, color):
    verbose: int,
    quiet: int,
    color_mode: ColorMode | None,
    no_color: bool,
    # config_pyproject_options:
    for_pyproject: bool,
    # config_root_options:
    config_root: bool,
    # common_output_format_options:
    output_format: OutputFormat | None,
) -> None:
    """Print a starter config file to stdout.

    Outputs an initial TopMark configuration file with default values.
    Intended as a starting point for customization in your own project.

    Notes:
        - In JSON/NDJSON modes, this command emits only a Config snapshot
          (no diagnostics).

    Args:
        verbose: Increment verbosity level.
        quiet: Decrement verbosity level.
        color_mode: Color mode for text format (default: auto).
        no_color: If set, disable color mode.
        for_pyproject: If True, render as subtable under `[tool.topmark]`
            (default: False: plain topmark.toml TOML config format).
        config_root: If True, set config as root (stops further config resoution).
        output_format: Output format to use (``text``, ``markdown``, ``json``, or ``ndjson``).

    Raises:
        NotImplementedError: When providing an unsupported OutputType.
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
    meta: MetaPayload = build_meta_payload()

    # Output format
    fmt: OutputFormat = output_format or OutputFormat.TEXT

    apply_color_policy_for_output_format(ctx, fmt=fmt)
    enable_color: bool = ctx.obj[ArgKey.COLOR_ENABLED]

    # config_check_command() is file-agnostic: ignore positional PATHS
    apply_ignore_positional_paths_policy(
        ctx,
        warn_stdin_dash=True,
    )

    validate_human_only_config_flags_for_machine_format(
        ctx,
        fmt=fmt,
        config_root=config_root,
        for_pyproject=for_pyproject,
    )

    if fmt in (OutputFormat.JSON, OutputFormat.NDJSON):
        # Machine-readable formats: emit JSON/NDJSON without human banners
        mutable_config: MutableConfig = mutable_config_from_defaults()
        emit_config_machine(
            meta=meta,
            config=mutable_config.freeze(),
            fmt=fmt,
        )
        return

    # Human formats: use the full annotated default configuration template
    report: ConfigInitHumanReport = build_config_init_human_report(
        for_pyproject=for_pyproject,
        root=config_root,
        verbosity_level=verbosity_level,
        styled=enable_color,
    )

    if fmt == OutputFormat.MARKDOWN:
        console.print(
            render_config_init_markdown(report),
            nl=False,
        )
        return

    if fmt == OutputFormat.TEXT:
        console.print(render_config_init_text(report))
        return

    # Defensive guard in case OutputFormat gains new members
    raise NotImplementedError(f"Unsupported output format: {fmt!r}")
