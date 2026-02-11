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

from topmark.cli.cmd_common import (
    get_effective_verbosity,
    init_common_state,
)
from topmark.cli.emitters.text.config import emit_config_init_text
from topmark.cli.keys import CliCmd, CliOpt
from topmark.cli.machine_emitters import emit_config_machine
from topmark.cli.options import (
    common_config_options,
    common_output_format_options,
    common_ui_options,
)
from topmark.cli.validators import (
    apply_color_policy_for_output_format,
    apply_ignore_positional_paths_policy,
    validate_human_only_config_flags_for_machine_format,
)
from topmark.cli_shared.emitters.markdown.config import emit_config_init_markdown
from topmark.cli_shared.emitters.shared.config import (
    ConfigInitPrepared,
    prepare_config_init,
)
from topmark.config import MutableConfig
from topmark.core.formats import OutputFormat
from topmark.core.keys import ArgKey

if TYPE_CHECKING:
    from topmark.cli_shared.color import ColorMode
    from topmark.cli_shared.console_api import ConsoleLike
    from topmark.core.machine.schemas import MetaPayload


@click.command(
    name=CliCmd.CONFIG_INIT,
    help="Display an initial TopMark configuration file.",
)
# Common option decorators
@common_ui_options
@common_config_options
@common_output_format_options
# Command-specific option decorators
@click.option(
    CliOpt.CONFIG_FOR_PYPROJECT,
    ArgKey.CONFIG_FOR_PYPROJECT,
    is_flag=True,
    help="Generate config for inclusion in pyproject.toml.",
)
@click.option(
    CliOpt.CONFIG_ROOT,
    ArgKey.CONFIG_ROOT,
    is_flag=True,
    help="Set generated config as root.",
)
def config_init_command(
    *,
    # Command options: common options (verbosity, color)
    verbose: int,
    quiet: int,
    color_mode: ColorMode | None,
    no_color: bool,
    # Command options: output format
    output_format: OutputFormat | None,
    # Command-specific options:
    for_pyproject: bool,
    config_root: bool,
) -> None:
    """Print a starter config file to stdout.

    Outputs an initial TopMark configuration file with default values.
    Intended as a starting point for customization in your own project.

    Notes:
        - In JSON/NDJSON modes, this command emits only a Config snapshot
          (no diagnostics).

    Args:
        verbose: Incements the verbosity level,
        quiet: Decrements  the verbosity level,
        color_mode: Set the color mode (derfault: autp),
        no_color: bool: If set, disable color mode.
        output_format: Output format to use
            (``text``, ``markdown``, ``json``, or ``ndjson``).
        for_pyproject: If True, render as subtable under `[tool.topmark]`
            (default: False: plain topmark.toml TOML config format).
        config_root: If True, set config as root (stops further config resoution).

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

    # Select the console
    console: ConsoleLike = ctx.obj[ArgKey.CONSOLE]

    # Machine metadata
    meta: MetaPayload = ctx.obj[ArgKey.META]

    # Output format
    fmt: OutputFormat = output_format or OutputFormat.TEXT

    apply_color_policy_for_output_format(ctx, fmt=fmt)

    # config_check_command() is file-agnostic: ignore positional PATHS
    apply_ignore_positional_paths_policy(ctx, warn_stdin_dash=True)

    validate_human_only_config_flags_for_machine_format(
        ctx, fmt=fmt, config_root=config_root, for_pyproject=for_pyproject
    )

    # Determine effective program-output verbosity for gating extra details
    vlevel: int = get_effective_verbosity(ctx)

    if fmt in (OutputFormat.JSON, OutputFormat.NDJSON):
        # Machine-readable formats: emit JSON/NDJSON without human banners
        mutable_config: MutableConfig = MutableConfig.from_defaults()
        emit_config_machine(
            meta=meta,
            config=mutable_config.freeze(),
            fmt=fmt,
        )
        return

    # Human formats: use the full annotated default configuration template
    prepared: ConfigInitPrepared = prepare_config_init(
        for_pyproject=for_pyproject,
        root=config_root,
    )

    if fmt == OutputFormat.MARKDOWN:
        md: str = emit_config_init_markdown(
            prepared=prepared,
            verbosity_level=vlevel,
        )
        console.print(md, nl=False)
        return

    if fmt == OutputFormat.TEXT:
        emit_config_init_text(
            console=console,
            prepared=prepared,
            verbosity_level=vlevel,
        )
        return

    # Defensive guard in case OutputFormat gains new members
    raise NotImplementedError(f"Unsupported output format: {fmt!r}")
