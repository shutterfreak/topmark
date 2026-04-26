# topmark:header:start
#
#   project      : TopMark
#   file         : config_dump.py
#   file_relpath : src/topmark/cli/commands/config_dump.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""TopMark `config dump` command.

Emits the effective TopMark configuration as TOML after applying defaults,
project/user config files, and any CLI overrides.

The output is wrapped between `TOML_BLOCK_START` and `TOML_BLOCK_END` markers
for easy parsing in tests or tooling.

Input modes:
  * This command is file-agnostic: positional PATHS and --files-from are ignored
    (with a warning if present).
  * --include-from - and --exclude-from - are honored for config resolution.
  * '-' as a PATH (content-on-STDIN) is ignored in `topmark config dump`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import click

from topmark.cli.cmd_common import build_resolved_toml_sources_and_config_for_plan
from topmark.cli.cmd_common import build_run_options
from topmark.cli.cmd_common import init_common_state
from topmark.cli.cmd_common import maybe_route_console_to_stderr
from topmark.cli.emitters.machine import emit_config_machine
from topmark.cli.io import plan_cli_inputs
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt
from topmark.cli.options import GROUP_CONTEXT_SETTINGS
from topmark.cli.options import common_color_options
from topmark.cli.options import common_config_resolution_options
from topmark.cli.options import common_file_filtering_options
from topmark.cli.options import common_file_type_filtering_options
from topmark.cli.options import common_from_sources_options
from topmark.cli.options import common_header_formatting_options
from topmark.cli.options import common_output_format_options
from topmark.cli.options import common_text_output_quiet_options
from topmark.cli.options import common_text_output_verbosity_options
from topmark.cli.options import config_dump_provenance_options
from topmark.cli.state import TopmarkCliState
from topmark.cli.state import bootstrap_cli_state
from topmark.cli.validators import apply_color_policy_for_output_format
from topmark.cli.validators import validate_stdin_dash_requires_piped_input
from topmark.core.exit_codes import ExitCode
from topmark.core.formats import OutputFormat
from topmark.core.logging import get_logger
from topmark.core.machine.payloads import build_meta_payload
from topmark.presentation.markdown.config import render_config_dump_markdown
from topmark.presentation.markdown.diagnostic import render_diagnostics_markdown
from topmark.presentation.shared.config import ConfigDumpHumanReport
from topmark.presentation.shared.config import build_config_dump_human_report
from topmark.presentation.text.config import render_config_dump_text
from topmark.presentation.text.diagnostic import render_diagnostics_text
from topmark.utils.file import safe_unlink

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.cli.console.color import ColorMode
    from topmark.cli.console.protocols import ConsoleProtocol
    from topmark.cli.io import InputPlan
    from topmark.config.model import Config
    from topmark.core.logging import TopmarkLogger
    from topmark.core.machine.schemas import MetaPayload
    from topmark.diagnostic.model import FrozenDiagnosticLog
    from topmark.runtime.model import RunOptions

logger: TopmarkLogger = get_logger(__name__)


@click.command(
    name=CliCmd.CONFIG_DUMP,
    context_settings=GROUP_CONTEXT_SETTINGS,
    help=(
        "Print the effective merged TopMark configuration as TOML. "
        f"This command is file-agnostic: positional PATHS and {CliOpt.STDIN_FILENAME} are ignored. "
        f"Use {CliOpt.OUTPUT_FORMAT}={OutputFormat.JSON.value}/{OutputFormat.NDJSON.value} "
        "for machine-readable output."
    ),
    epilog=(
        "\b\n"
        "Examples:\n"
        "  # Print the effective merged configuration\n"
        f"  topmark {CliCmd.CONFIG} {CliCmd.CONFIG_DUMP}\n"
        "  # Include configuration provenance layers\n"
        f"  topmark {CliCmd.CONFIG} {CliCmd.CONFIG_DUMP} {CliOpt.SHOW_CONFIG_LAYERS}\n"
        "  # Read include patterns from STDIN\n"
        f"  topmark {CliCmd.CONFIG} {CliCmd.CONFIG_DUMP} {CliOpt.INCLUDE_FROM} -\n"
        "  # Emit machine-readable configuration\n"
        f"  topmark {CliCmd.CONFIG} {CliCmd.CONFIG_DUMP} "
        f"{CliOpt.OUTPUT_FORMAT}={OutputFormat.JSON.value}\n"
        "\n"
        "Notes:\n"
        "  • File lists are inputs, not configuration; they are ignored by this command.\n"
        "  • Pattern sources are configuration and are included in the dump.\n"
        "  • Human output may include TOML block markers when verbosity is enabled.\n"
        "  • Machine formats emit a Config snapshot and optional provenance records.\n"
    ),
)
@common_color_options
@common_text_output_verbosity_options
@common_text_output_quiet_options
@common_config_resolution_options
@config_dump_provenance_options
@common_from_sources_options
@common_file_filtering_options
@common_file_type_filtering_options
@common_header_formatting_options
@common_output_format_options
def config_dump_command(
    *,
    # common_ui_options (verbosity, color):
    verbosity: int,
    quiet: bool,
    color_mode: ColorMode | None,
    no_color: bool,
    # common_config_resolution_options:
    no_config: bool,
    config_files: list[str],
    # config_dump_provenance_options:
    show_config_layers: bool,
    # common_from_sources_options:
    files_from: list[str],
    include_from: list[str],
    exclude_from: list[str],
    # common_file_filtering_options:
    include_patterns: list[str],
    exclude_patterns: list[str],
    # common_file_type_filtering_options:
    include_file_types: list[str],
    exclude_file_types: list[str],
    # common_header_formatting_options:
    align_fields: bool,
    relative_to: str | None,
    # common_output_format_options:
    output_format: OutputFormat | None,
) -> None:
    """Print the effective merged TopMark configuration.

    Builds the effective configuration from defaults, discovered and explicit
    config files, and CLI overrides, then renders it for human or machine output.

    Notes:
        - In JSON/NDJSON modes, this command emits a Config snapshot and,
          when `--show-layers` is enabled, also emits machine-readable
          config provenance (still without diagnostics).

    Args:
        verbosity: Increase TEXT output detail.
        quiet: Suppress TEXT output.
        color_mode: Set the color mode (default: auto).
        no_color: bool: If set, disable color mode.
        no_config: If True, skip loading project/user configuration files.
        config_files: Additional configuration file paths to load and merge.
        show_config_layers: If True, include a layered TOML provenance view before
            the final flattened config dump.
        files_from: Files that contain newline‑delimited *paths* to add to the
            candidate set before filtering. Use ``-`` to read from STDIN.
        include_from: Files that contain include glob patterns (one per line).
            Use ``-`` to read patterns from STDIN.
        exclude_from: Files that contain exclude glob patterns (one per line).
            Use ``-`` to read patterns from STDIN.
        include_patterns: Glob patterns to *include* (intersection).
        exclude_patterns: Glob patterns to *exclude* (subtraction).
        include_file_types: Restrict processing to the given file type identifiers.
        exclude_file_types: Exclude processing for the given file type identifiers.
        align_fields: Whether to align header fields when rendering (captured in config).
        relative_to: Base path used only for resolving header metadata (e.g., `file_relpath`).
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

    # Machine metadata
    meta: MetaPayload = build_meta_payload()

    # Output format
    fmt: OutputFormat = state.output_format

    apply_color_policy_for_output_format(ctx, fmt=fmt)
    enable_color: bool = state.color_enabled

    # common_from_sources_options - Fail fast if a `--*-from -` option is used without piped STDIN.
    validate_stdin_dash_requires_piped_input(
        ctx,
        files_from=files_from,
        include_from=include_from,
        exclude_from=exclude_from,
    )

    # config_dump_command() is file-agnostic: ignore positional PATHS

    plan: InputPlan = plan_cli_inputs(
        ctx=ctx,
        files_from=files_from or [],
        include_from=include_from,
        exclude_from=exclude_from,
        include_patterns=include_patterns,
        exclude_patterns=exclude_patterns,
        stdin_filename=None,  # We ignore STDIN processing in `config dump`
        allow_empty_paths=True,  # We ignore paths in `config dump`
    )

    resolved_toml, draft_config = build_resolved_toml_sources_and_config_for_plan(
        ctx=ctx,
        plan=plan,
        no_config=no_config,
        config_paths=config_files,
        strict_config_checking=None,
        include_file_types=include_file_types,
        exclude_file_types=exclude_file_types,
        align_fields=align_fields,
        relative_to=relative_to,
    )

    run_options: RunOptions = build_run_options(
        apply_changes=False,  # Not relevant for `config dump``
        write_mode=None,  # Not relevant for `config dump``
        stdin_mode=plan.stdin_mode,
        stdin_filename=plan.stdin_filename,
    )

    logger.debug("run options: %s", run_options)

    # Content-to-STDOUT modes: keep stdout clean for the rewritten file content.
    #
    # - STDIN content mode emits the updated file to stdout when --apply is set.
    # - write_mode="stdout" also emits updated content to stdout.
    #
    # In both cases, route all human-facing console output (summaries, warnings,
    # diagnostics) to stderr.
    #
    # Console selection must happen after planning inputs because stdin mode affects routing.
    console: ConsoleProtocol = maybe_route_console_to_stderr(
        ctx,
        run_options=run_options,
        enable_color=enable_color,
    )

    config: Config = draft_config.freeze()
    logger.trace("Run config after layered CLI overrides: %s", config)

    # Render flattened config validation diagnostics before emitting the final dump.
    flattened_diagnostics: FrozenDiagnosticLog = config.validation_logs.flattened()

    if fmt == OutputFormat.TEXT:
        if not state.quiet:
            console.print(
                render_diagnostics_text(
                    diagnostics=flattened_diagnostics,
                    verbosity_level=verbosity_level,
                    color=enable_color,
                )
            )
    elif fmt == OutputFormat.MARKDOWN:
        console.print(
            render_diagnostics_markdown(
                diagnostics=flattened_diagnostics,
            )
        )

    temp_path: Path | None = plan.temp_path  # for cleanup/STDIN-apply branch

    logger.trace("Config after merging CLI and discovered config: %s", draft_config)

    def _exit() -> None:
        # Cleanup any temp file created by content-on-STDIN mode (defensive)
        if temp_path and temp_path.exists():
            safe_unlink(temp_path)
        ctx.exit(ExitCode.SUCCESS)

    # We don't actually care about the file list here; just dump the config

    if fmt in (OutputFormat.JSON, OutputFormat.NDJSON):
        # Machine-readable formats: emit JSON/NDJSON without human banners
        emit_config_machine(
            console=console,
            meta=meta,
            config=config,
            fmt=fmt,
            resolved_toml=resolved_toml,
            show_config_layers=show_config_layers,
        )
        _exit()

    # Human formats
    report: ConfigDumpHumanReport = build_config_dump_human_report(
        config=config,
        resolved_toml=resolved_toml,
        show_config_layers=show_config_layers,
        verbosity_level=verbosity_level,
        styled=enable_color,
    )

    if fmt == OutputFormat.MARKDOWN:
        console.print(
            render_config_dump_markdown(report),
            nl=False,
        )
        _exit()

    if fmt == OutputFormat.TEXT:
        if not state.quiet:
            console.print(render_config_dump_text(report))
        _exit()

    # Defensive guard in case OutputFormat gains new members
    raise NotImplementedError(f"Unsupported output format: {fmt!r}")
