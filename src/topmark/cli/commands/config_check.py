# topmark:header:start
#
#   project      : TopMark
#   file         : config_check.py
#   file_relpath : src/topmark/cli/commands/config_check.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""TopMark `config check` command.

Validates the effective TopMark configuration after applying defaults,
project/user config files, and any CLI overrides.

Input modes:
  * This command is file-agnostic: positional PATHS and '-' STDIN content mode are ignored (with a
    warning if present).
  * `--files-from/--include-from/--exclude-from` are accepted and used to populate pattern/path
    sources (as inputs with empty PATH list).

Resolution mechanism:
  * This command uses the same layered config discovery rules as other CLI commands,
    via `topmark.cli.config_resolver`, to build the effective config snapshot.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import click

from topmark.api.runtime import is_config_valid
from topmark.cli.cmd_common import init_common_state
from topmark.cli.emitters.machine import emit_config_check_machine
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt
from topmark.cli.options import GROUP_CONTEXT_SETTINGS
from topmark.cli.options import common_config_resolution_options
from topmark.cli.options import common_output_format_options
from topmark.cli.options import common_ui_options
from topmark.cli.options import config_strict_checking_options
from topmark.cli.state import TopmarkCliState
from topmark.cli.state import bootstrap_cli_state
from topmark.cli.validators import apply_color_policy_for_output_format
from topmark.cli.validators import apply_ignore_positional_paths_policy
from topmark.config.resolution.bridge import resolve_toml_sources_and_build_config_draft
from topmark.core.exit_codes import ExitCode
from topmark.core.formats import OutputFormat
from topmark.core.logging import get_logger
from topmark.core.machine.payloads import build_meta_payload
from topmark.presentation.markdown.config import render_config_check_markdown
from topmark.presentation.shared.config import ConfigCheckHumanReport
from topmark.presentation.shared.config import build_config_check_human_report
from topmark.presentation.text.config import render_config_check_text

if TYPE_CHECKING:
    from topmark.cli.console.color import ColorMode
    from topmark.cli.console.protocols import ConsoleProtocol
    from topmark.config.model import Config
    from topmark.core.logging import TopmarkLogger
    from topmark.core.machine.schemas import MetaPayload

logger: TopmarkLogger = get_logger(__name__)


@click.command(
    name=CliCmd.CONFIG_CHECK,
    context_settings=GROUP_CONTEXT_SETTINGS,
    help=(
        "Validate the effective merged TopMark configuration and report diagnostics. "
        f"This command is file-agnostic: positional PATHS and {CliOpt.STDIN_FILENAME} are ignored. "
        f"Use {CliOpt.STRICT_CONFIG_CHECKING} to treat warnings as errors and "
        f"{CliOpt.OUTPUT_FORMAT}={OutputFormat.JSON.value}/{OutputFormat.NDJSON.value} "
        "for machine-readable output."
    ),
    epilog=(
        "\b\n"
        "Examples:\n"
        "  # Validate the effective merged configuration\n"
        f"  topmark {CliCmd.CONFIG} {CliCmd.CONFIG_CHECK}\n"
        "  # Fail on warnings (strict mode)\n"
        f"  topmark {CliCmd.CONFIG} {CliCmd.CONFIG_CHECK} {CliOpt.STRICT_CONFIG_CHECKING}\n"
        "  # Emit machine-readable diagnostics\n"
        f"  topmark {CliCmd.CONFIG} {CliCmd.CONFIG_CHECK} "
        f"{CliOpt.OUTPUT_FORMAT}={OutputFormat.JSON.value}\n"
        "\n"
        "Notes:\n"
        "  • Configuration is built from defaults, discovered files, "
        f"explicit {CliOpt.CONFIG_FILES} files, and CLI overrides.\n"
        "  • Exit status is non-zero on validation failure "
        f"(errors, or warnings with {CliOpt.STRICT_CONFIG_CHECKING}).\n"
        "  • NDJSON emits a sequence of structured records.\n"
    ),
)
@common_ui_options
@common_config_resolution_options
@config_strict_checking_options
@common_output_format_options
def config_check_command(
    *,
    # common_ui_options (verbosity, color):
    verbosity: int,
    quiet: bool,
    color_mode: ColorMode | None,
    no_color: bool,
    # common_config_resolution_options:
    no_config: bool,
    config_files: list[str],
    # config_strict_checking_options:
    strict_config_checking: bool | None,
    # common_output_format_options:
    output_format: OutputFormat | None,
) -> None:
    """Validate the final merged TopMark configuration.

    Builds the effective configuration from defaults, discovered and explicit
    config files, and CLI overrides, then validates it and reports diagnostics.

    Args:
        verbosity: Increase human-output detail.
        quiet: Suppress human-readable output.
        color_mode: Color mode for text format (default: auto).
        no_color: If set, disable color mode.
        no_config: If True, skip loading project/user configuration files.
        config_files: Additional configuration file paths to load and merge.
        strict_config_checking: if True, report warnings as errors.
        output_format: Output format to use (``text``, ``markdown``, ``json``, or ``ndjson``).

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
        quiet=quiet,
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

    # `config check` is file-agnostic w.r.t. positional PATHS and STDIN content mode ('-').
    # However, we still accept `*_from` options so callers can validate pattern/path sources.
    apply_ignore_positional_paths_policy(
        ctx,
        warn_stdin_dash=True,
    )

    # Build a merged draft config (we do not need an InputPlan since we're not processing files)
    resolved, draft_config = resolve_toml_sources_and_build_config_draft(
        strict_config_checking=strict_config_checking,
        no_config=no_config,
        extra_config_files=[Path(p) for p in config_files],
    )

    # Freeze ensures sanitize + schema validation runs (and produces diagnostics)
    config: Config = draft_config.freeze()
    logger.trace("Run config after layered CLI overrides: %s", config)

    # Check config validity:
    config_valid: bool = is_config_valid(
        config,
        resolved=resolved,
    )

    logger.trace("Config after merging CLI and discovered config: %s", draft_config)

    def _exit(ctx: click.Context, *, success: bool) -> None:
        """Select exit code depending on outcome."""
        ctx.exit(0 if success else ExitCode.FAILURE)

    if fmt in (OutputFormat.JSON, OutputFormat.NDJSON):
        emit_config_check_machine(
            console=console,
            meta=meta,
            config=config,
            strict=bool(resolved.strict_config_checking),
            ok=config_valid,
            fmt=fmt,
        )
        _exit(ctx, success=config_valid)

    # Human formats: prepare shared data once for TEXT/MARKDOWN emitters.
    report: ConfigCheckHumanReport = build_config_check_human_report(
        config=config,
        ok=config_valid,
        strict=bool(resolved.strict_config_checking),
        verbosity_level=verbosity_level,
        styled=enable_color,
    )

    if fmt == OutputFormat.MARKDOWN:
        console.print(
            render_config_check_markdown(report),
            nl=False,
        )
        _exit(ctx, success=config_valid)

    if fmt == OutputFormat.TEXT:
        console.print(render_config_check_text(report))
        _exit(ctx, success=config_valid)

    # Defensive guard in case OutputFormat gains new members
    raise NotImplementedError(f"Unsupported output format: {fmt!r}")
