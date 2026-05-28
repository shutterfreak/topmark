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
import rich_click

from topmark.cli.cmd_common import init_common_state
from topmark.cli.emitters.machine import emit_config_machine
from topmark.cli.help import HelpExample
from topmark.cli.help import render_examples_epilog
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt
from topmark.cli.options import GROUP_CONTEXT_SETTINGS
from topmark.cli.options import common_color_options
from topmark.cli.options import common_output_format_options
from topmark.cli.options import common_text_output_verbosity_options
from topmark.cli.options import config_pyproject_options
from topmark.cli.options import config_root_options
from topmark.cli.state import TopmarkCliState
from topmark.cli.state import bootstrap_cli_state
from topmark.cli.validators import apply_color_policy_for_output_format
from topmark.cli.validators import apply_ignore_positional_paths_policy
from topmark.cli.validators import validate_human_only_config_flags_for_machine_format
from topmark.config.resolution.bridge import resolve_default_template_and_build_mutable_config
from topmark.core.formats import OutputFormat
from topmark.core.machine.payloads import build_meta_payload
from topmark.presentation.markdown.config import render_config_init_markdown
from topmark.presentation.shared.config import ConfigInitHumanReport
from topmark.presentation.shared.config import build_config_init_human_report
from topmark.presentation.text.config import render_config_init_text

if TYPE_CHECKING:
    from topmark.cli.console.color import ColorMode
    from topmark.cli.console.protocols import ConsoleProtocol
    from topmark.config.resolution.bridge import ResolvedConfigDraft
    from topmark.core.machine.schemas import MetaPayload


@rich_click.command(
    name=CliCmd.CONFIG_INIT,
    context_settings=GROUP_CONTEXT_SETTINGS,
    help=(
        "Print a starter TopMark configuration file. "
        "This command is file-agnostic: positional PATHS "
        "and file-processing STDIN modes are rejected. "
        f"Use {CliOpt.OUTPUT_FORMAT}={OutputFormat.JSON.value}/{OutputFormat.NDJSON.value} "
        "for machine-readable output."
    ),
    epilog=render_examples_epilog(
        examples=(
            HelpExample(
                summary="Print a starter topmark.toml configuration",
                command_line=f"topmark {CliCmd.CONFIG} {CliCmd.CONFIG_INIT}",
            ),
            HelpExample(
                summary="Print a starter pyproject.toml configuration section",
                command_line=(
                    f"topmark {CliCmd.CONFIG} {CliCmd.CONFIG_INIT} {CliOpt.CONFIG_FOR_PYPROJECT}"
                ),
            ),
            HelpExample(
                summary="Write a starter configuration file",
                command_line=f"topmark {CliCmd.CONFIG} {CliCmd.CONFIG_INIT} > topmark.toml",
            ),
            HelpExample(
                summary="Emit machine-readable configuration",
                command_line=(
                    f"topmark {CliCmd.CONFIG} {CliCmd.CONFIG_INIT} "
                    f"{CliOpt.OUTPUT_FORMAT}={OutputFormat.JSON.value}"
                ),
            ),
        ),
        notes=(
            "Human formats use the annotated, commented template bundled with TopMark.",
            "Machine-readable formats emit a minimal Config snapshot "
            "without comments or diagnostics.",
        ),
    ),
)
# Common option decorators
@common_color_options
@common_text_output_verbosity_options
@config_pyproject_options
@config_root_options
@common_output_format_options
def config_init_command(
    *,
    # common_ui_options (verbosity, color):
    verbosity: int,
    color_mode: ColorMode | None,
    no_color: bool,
    # config_pyproject_options:
    for_pyproject: bool,
    # config_root_options:
    config_root: bool,
    # common_output_format_options:
    output_format: OutputFormat | None,
) -> None:
    """Print a starter TopMark configuration file.

    Human formats render the annotated starter template bundled with TopMark.
    Machine-readable formats emit a minimal Config snapshot without comments or diagnostics.

    Notes:
        - In JSON/NDJSON modes, this command emits only a Config snapshot
          (no diagnostics).

    Args:
        verbosity: Increase TEXT output detail.
        color_mode: Color mode for text format (default: auto).
        no_color: If set, disable color mode.
        for_pyproject: If True, render as subtable under `[tool.topmark]`
            (default: False: plain topmark.toml TOML config format).
        config_root: If True, set config as root (stops further config resoution).
        output_format: Output format to use (``text``, ``markdown``, ``json``, or ``ndjson``).
            Verbosity applies only to TEXT output; this command does not support
            ``--quiet``.

    Raises:
        NotImplementedError: When providing an unsupported OutputType.
    """
    ctx: click.Context = click.get_current_context()
    state: TopmarkCliState = bootstrap_cli_state(ctx)

    # Effective output format (stored early so shared initialization sees it).
    state.output_format = output_format or OutputFormat.TEXT

    # Initialize the common state (verbosity, color mode) and initialize console
    init_common_state(
        ctx,
        verbosity=verbosity,
        quiet=False,  # Pure informational command; no ``--quiet`` option is registered.
        color_mode=color_mode,
        no_color=no_color,
    )

    # Retrieve effective human facing program-output verbosity for gating extra details
    verbosity_level: int = state.verbosity

    # Select the console
    console: ConsoleProtocol = state.console

    # Machine metadata
    meta: MetaPayload = build_meta_payload()

    # Output format
    fmt: OutputFormat = state.output_format

    apply_color_policy_for_output_format(ctx, fmt=fmt)
    enable_color: bool = state.color_enabled

    # `config init` is file-agnostic: ignore positional PATHS
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
        resolved_config: ResolvedConfigDraft = resolve_default_template_and_build_mutable_config()
        emit_config_machine(
            console=console,
            meta=meta,
            config=resolved_config.draft.freeze(),
            resolved_toml=resolved_config.resolved,
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
