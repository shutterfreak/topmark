# topmark:header:start
#
#   project      : TopMark
#   file         : config_defaults.py
#   file_relpath : src/topmark/cli/commands/config_defaults.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""TopMark `config defaults` command.

Prints TopMark's *runtime* default configuration as TOML.

This command is intended as a copy/paste reference for users. It differs from
`topmark config init`, which emits the annotated packaged template (when
available) intended to be written as an initial config file.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import click

from topmark.cli.cmd_common import init_common_state
from topmark.cli.emitters.machine import emit_config_machine
from topmark.cli.emitters.text.config import emit_config_defaults_text
from topmark.cli.keys import CliCmd
from topmark.cli.options import GROUP_CONTEXT_SETTINGS
from topmark.cli.options import common_output_format_options
from topmark.cli.options import common_ui_options
from topmark.cli.options import config_pyproject_options
from topmark.cli.options import config_root_options
from topmark.cli.validators import apply_color_policy_for_output_format
from topmark.cli.validators import apply_ignore_positional_paths_policy
from topmark.cli.validators import validate_human_only_config_flags_for_machine_format
from topmark.cli_shared.emitters.markdown.config import emit_config_defaults_markdown
from topmark.cli_shared.emitters.shared.config import ConfigDefaultsPrepared
from topmark.cli_shared.emitters.shared.config import prepare_config_defaults
from topmark.config.model import MutableConfig
from topmark.core.formats import OutputFormat
from topmark.core.keys import ArgKey

if TYPE_CHECKING:
    from topmark.cli_shared.color import ColorMode
    from topmark.cli_shared.console_api import ConsoleLike
    from topmark.core.machine.schemas import MetaPayload


@click.command(
    name=CliCmd.CONFIG_DEFAULTS,
    context_settings=GROUP_CONTEXT_SETTINGS,
    help=(
        "Display TopMark’s built-in runtime default configuration. "
        "This command is file-agnostic: positional PATHS are ignored "
        "and --stdin-filename is not allowed. "
        "Use --output-format json/ndjson for a machine-readable config snapshot."
    ),
    epilog=(
        "Notes:\n"
        "  • text/markdown output is a cleaned TOML view of the runtime defaults (comment-free).\n"
        "  • json/ndjson output emits a minimal Config snapshot (no diagnostics).\n"
        "  • See docs/dev/machine_outputs.md for machine output conventions.\n"
    ),
)
@common_ui_options
@config_pyproject_options
@config_root_options
@common_output_format_options
def config_defaults_command(
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
    """Display the runtime default configuration.

    Outputs a cleaned TOML document derived from TopMark's built-in defaults.
    This is a reference representation of the defaults that TopMark would apply
    when no config files are discovered or provided.

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
    console: ConsoleLike = ctx.obj[ArgKey.CONSOLE]

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

    validate_human_only_config_flags_for_machine_format(
        ctx,
        fmt=fmt,
        config_root=config_root,
        for_pyproject=for_pyproject,
    )

    if fmt in (OutputFormat.JSON, OutputFormat.NDJSON):
        # Machine-readable formats: emit JSON/NDJSON without human banners
        emit_config_machine(
            meta=meta,
            config=MutableConfig.from_defaults().freeze(),
            fmt=fmt,
        )
        return

    prepared: ConfigDefaultsPrepared = prepare_config_defaults(
        for_pyproject=for_pyproject,
        root=config_root,
    )
    if fmt == OutputFormat.MARKDOWN:
        md: str = emit_config_defaults_markdown(
            prepared=prepared,
            verbosity_level=verbosity_level,
        )
        console.print(md, nl=False)
        return

    if fmt == OutputFormat.TEXT:
        emit_config_defaults_text(
            console=console,
            prepared=prepared,
            verbosity_level=verbosity_level,
        )
        return

    # Defensive guard in case OutputFormat gains new members
    raise NotImplementedError(f"Unsupported output format: {fmt!r}")
