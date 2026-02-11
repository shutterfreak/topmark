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
  * This command is file-agnostic: positional PATHS and --files-from are ignored
    (with a warning if present).
  * '-' as a PATH (content-on-STDIN) is ignored in `topmark config check`.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import click

from topmark.cli.cmd_common import (
    get_effective_verbosity,
    init_common_state,
)
from topmark.cli.emitters.text.config import emit_config_check_text
from topmark.cli.keys import CliCmd, CliOpt
from topmark.cli.machine_emitters import emit_config_check_machine
from topmark.cli.options import (
    common_config_options,
    common_output_format_options,
    common_ui_options,
)
from topmark.cli.validators import (
    apply_color_policy_for_output_format,
    apply_ignore_positional_paths_policy,
)
from topmark.cli_shared.emitters.markdown.config import (
    emit_config_check_markdown,
)
from topmark.cli_shared.emitters.shared.config import (
    ConfigCheckPrepared,
    prepare_config_check,
)
from topmark.config import Config, MutableConfig
from topmark.config.logging import get_logger
from topmark.config.machine.payloads import (
    build_config_diagnostics_payload,
)
from topmark.core.exit_codes import ExitCode
from topmark.core.formats import (
    OutputFormat,
)
from topmark.core.keys import ArgKey

if TYPE_CHECKING:
    from topmark.cli_shared.color import ColorMode
    from topmark.cli_shared.console_api import ConsoleLike
    from topmark.config.logging import TopmarkLogger
    from topmark.config.machine.schemas import (
        ConfigDiagnosticsPayload,
    )
    from topmark.core.machine.schemas import MetaPayload
    from topmark.diagnostic.machine.schemas import (
        MachineDiagnosticCounts,
    )

logger: TopmarkLogger = get_logger(__name__)


@click.command(
    name=CliCmd.CONFIG_CHECK,
    help="Validate merged configuration and report any diagnostics.",
)
# Common option decorators
@common_ui_options
@common_config_options
@common_output_format_options
# Command-specific option decorators
@click.option(
    f"{CliOpt.STRICT_CONFIG_CHECKING}/{CliOpt.NO_STRICT_CONFIG_CHECKING}",
    ArgKey.STRICT_CONFIG_CHECKING,
    default=False,
    show_default=True,
    help="Fail if any warnings are present (in addition to errors).",
)
def config_check_command(
    *,
    # Command options: common options (verbosity, color)
    verbose: int,
    quiet: int,
    color_mode: ColorMode | None,
    no_color: bool,
    # Command options: output format
    output_format: OutputFormat | None,
    # Command options: config
    no_config: bool,
    config_paths: list[str],
    strict_config_checking: bool,
) -> None:
    """Validates and verifies the final merged configuration.

    Builds the effective configuration from defaults, discovered/explicit
    config files, and CLI overrides, then validates it.
    This is useful for debugging or for external tools
    that need to consume the resolved configuration.

    Args:
        verbose: Incements the verbosity level,
        quiet: Decrements  the verbosity level,
        color_mode: Set the color mode (derfault: autp),
        no_color: bool: If set, disable color mode.
        output_format: Output format to use
            (``text``, ``markdown``, ``json``, or ``ndjson``).
        no_config: If True, skip loading project/user configuration files.
        config_paths: Additional configuration file paths to load and merge.
        strict_config_checking: if True, report warnings as errors.

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

    # Build a merged draft config (we do not need an InputPlan since we're not processing files)
    draft_config: MutableConfig = MutableConfig.load_merged(
        strict_config_checking=strict_config_checking,
        no_config=no_config,
        extra_config_files=[Path(p) for p in config_paths],
    )

    # Freeze ensures sanitize + schema validation runs (and produces diagnostics)
    config: Config = draft_config.freeze()

    # Diagnostics payload;
    diag_payload: ConfigDiagnosticsPayload = build_config_diagnostics_payload(config)
    counts: MachineDiagnosticCounts = diag_payload.diagnostic_counts
    n_warn: int = counts.warning
    n_err: int = counts.error
    fail: bool = (n_err > 0) or (strict_config_checking and n_warn > 0)

    # Determine effective program-output verbosity for gating extra details
    vlevel: int = get_effective_verbosity(ctx, config)

    logger.trace("Config after merging CLI and discovered config: %s", draft_config)

    def _exit(ctx: click.Context, *, fail: bool) -> None:
        """Select exit code depending on outcome."""
        ctx.exit(ExitCode.FAILURE if fail else 0)

    if fmt in (OutputFormat.JSON, OutputFormat.NDJSON):
        emit_config_check_machine(
            meta=meta,
            config=config,
            strict=strict_config_checking,
            ok=not fail,
            fmt=fmt,
        )
        _exit(ctx, fail=fail)

    # Human formats: prepare shared data once for TEXT/MARKDOWN emitters.
    prepared: ConfigCheckPrepared = prepare_config_check(
        config=config,
        verbosity_level=vlevel,
    )

    if fmt == OutputFormat.MARKDOWN:
        md: str = emit_config_check_markdown(
            ok=not fail,
            strict=strict_config_checking,
            prepared=prepared,
            verbosity_level=vlevel,
        )
        console.print(md, nl=False)
        _exit(ctx, fail=fail)

    if fmt == OutputFormat.TEXT:
        emit_config_check_text(
            console=console,
            ok=not fail,
            strict=strict_config_checking,
            prepared=prepared,
            verbosity_level=vlevel,
        )
        _exit(ctx, fail=fail)

    # Defensive guard in case OutputFormat gains new members
    raise NotImplementedError(f"Unsupported output format: {fmt!r}")
