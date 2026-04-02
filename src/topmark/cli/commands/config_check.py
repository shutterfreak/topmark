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

from topmark.cli.cmd_common import init_common_state
from topmark.cli.emitters.machine import emit_config_check_machine
from topmark.cli.keys import CliCmd
from topmark.cli.options import GROUP_CONTEXT_SETTINGS
from topmark.cli.options import common_config_resolution_options
from topmark.cli.options import common_output_format_options
from topmark.cli.options import common_ui_options
from topmark.cli.options import config_strict_checking_options
from topmark.cli.validators import apply_color_policy_for_output_format
from topmark.cli.validators import apply_ignore_positional_paths_policy
from topmark.config.machine.payloads import build_config_diagnostics_payload
from topmark.config.resolution import resolve_toml_sources_and_build_config_draft
from topmark.core.exit_codes import ExitCode
from topmark.core.formats import OutputFormat
from topmark.core.keys import ArgKey
from topmark.core.logging import get_logger
from topmark.core.machine.payloads import build_meta_payload
from topmark.presentation.markdown.config import render_config_check_markdown
from topmark.presentation.shared.config import ConfigCheckHumanReport
from topmark.presentation.shared.config import build_config_check_human_report
from topmark.presentation.text.config import render_config_check_text

if TYPE_CHECKING:
    from topmark.cli.console.color import ColorMode
    from topmark.cli.console.protocols import ConsoleProtocol
    from topmark.config.machine.schemas import ConfigDiagnosticsPayload
    from topmark.config.model import Config
    from topmark.core.logging import TopmarkLogger
    from topmark.core.machine.schemas import MetaPayload
    from topmark.diagnostic.machine.schemas import MachineDiagnosticCounts

logger: TopmarkLogger = get_logger(__name__)


@click.command(
    name=CliCmd.CONFIG_CHECK,
    context_settings=GROUP_CONTEXT_SETTINGS,
    help=(
        "Validate the effective merged TopMark configuration and report diagnostics. "
        "This command is file-agnostic: positional PATHS and --stdin-filename are ignored. "
        "Use --strict to fail on warnings, and --output-format json/ndjson "
        "for machine-readable output."
    ),
    epilog=(
        "Notes:\n"
        "  • The effective configuration is built from defaults, discovered config files, "
        "explicit --config files, and CLI overrides.\n"
        "  • Exit status is non-zero when validation fails (errors, or warnings with --strict).\n"
        "  • NDJSON output begins with 'config' and 'config_diagnostics' records, followed by a "
        "'config_check' record and then one 'diagnostic' record per configuration diagnostic.\n"
        "  • See docs/dev/machine_outputs.md for canonical machine-output conventions."
    ),
)
@common_ui_options
@common_config_resolution_options
@config_strict_checking_options
@common_output_format_options
def config_check_command(
    *,
    # common_ui_options (verbosity, color):
    verbose: int,
    quiet: int,
    color_mode: ColorMode | None,
    no_color: bool,
    # common_config_resolution_options:
    no_config: bool,
    config_files: list[str],
    # config_strict_checking_options:
    strict_config_checking: bool,
    # common_output_format_options:
    output_format: OutputFormat | None,
) -> None:
    """Validates and verifies the final merged configuration.

    Builds the effective configuration from defaults, discovered/explicit
    config files, and CLI overrides, then validates it.
    This is useful for debugging or for external tools
    that need to consume the resolved configuration.

    Args:
        verbose: Increment verbosity level.
        quiet: Decrement verbosity level.
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

    # `config check` is file-agnostic w.r.t. positional PATHS and STDIN content mode ('-').
    # However, we still accept `*_from` options so callers can validate pattern/path sources.
    apply_ignore_positional_paths_policy(ctx, warn_stdin_dash=True)

    # Build a merged draft config (we do not need an InputPlan since we're not processing files)
    _resolved, draft_config = resolve_toml_sources_and_build_config_draft(
        strict_config_checking=strict_config_checking,
        no_config=no_config,
        extra_config_files=[Path(p) for p in config_files],
    )

    # Freeze ensures sanitize + schema validation runs (and produces diagnostics)
    config: Config = draft_config.freeze()

    logger.trace("Run config after layered CLI overrides: %s", config)

    # Diagnostics payload;
    diag_payload: ConfigDiagnosticsPayload = build_config_diagnostics_payload(config)
    counts: MachineDiagnosticCounts = diag_payload.diagnostic_counts
    n_warn: int = counts.warning
    n_err: int = counts.error
    fail: bool = (n_err > 0) or (strict_config_checking and n_warn > 0)

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
    report: ConfigCheckHumanReport = build_config_check_human_report(
        config=config,
        ok=not fail,
        strict=strict_config_checking,
        verbosity_level=verbosity_level,
        styled=enable_color,
    )

    if fmt == OutputFormat.MARKDOWN:
        console.print(
            render_config_check_markdown(report),
            nl=False,
        )
        _exit(ctx, fail=fail)

    if fmt == OutputFormat.TEXT:
        console.print(render_config_check_text(report))
        _exit(ctx, fail=fail)

    # Defensive guard in case OutputFormat gains new members
    raise NotImplementedError(f"Unsupported output format: {fmt!r}")
