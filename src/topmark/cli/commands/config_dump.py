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

from topmark.cli.cmd_common import (
    build_config_for_plan,
    get_effective_verbosity,
    init_common_state,
)
from topmark.cli.emitters.text.config import emit_config_dump_text
from topmark.cli.emitters.text.diagnostic import render_config_diagnostics_text
from topmark.cli.io import plan_cli_inputs
from topmark.cli.keys import CliCmd, CliOpt
from topmark.cli.machine_emitters import emit_config_machine
from topmark.cli.options import (
    CONTEXT_SETTINGS,
    common_config_options,
    common_file_and_filtering_options,
    common_header_formatting_options,
    common_output_format_options,
    common_ui_options,
)
from topmark.cli.validators import (
    apply_color_policy_for_output_format,
    apply_ignore_files_from_policy,
    apply_ignore_positional_paths_policy,
)
from topmark.cli_shared.emitters.markdown.config import (
    emit_config_dump_markdown,
)
from topmark.cli_shared.emitters.shared.config import (
    ConfigDumpPrepared,
    prepare_config_dump,
)
from topmark.config.logging import get_logger
from topmark.constants import TOML_BLOCK_END, TOML_BLOCK_START
from topmark.core.exit_codes import ExitCode
from topmark.core.formats import OutputFormat
from topmark.core.keys import ArgKey
from topmark.utils.file import safe_unlink

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.cli.io import InputPlan
    from topmark.cli_shared.color import ColorMode
    from topmark.cli_shared.console_api import ConsoleLike
    from topmark.config import Config, MutableConfig
    from topmark.config.logging import TopmarkLogger
    from topmark.core.machine.schemas import MetaPayload
    from topmark.rendering.formats import HeaderOutputFormat

logger: TopmarkLogger = get_logger(__name__)


@click.command(
    name=CliCmd.CONFIG_DUMP,
    help=(
        "Dump the final merged TopMark configuration as TOML. "
        f"This command is file‑agnostic: positional PATHS and {CliOpt.FILES_FROM} are ignored. "
        f"Filter flags are honored (e.g., {CliOpt.INCLUDE_PATTERNS}/{CliOpt.EXCLUDE_PATTERNS} "
        f"and {CliOpt.INCLUDE_FROM}/{CliOpt.EXCLUDE_FROM}). "
        f"Use {CliOpt.INCLUDE_FROM} - / {CliOpt.EXCLUDE_FROM} - to read patterns from STDIN; "
        f"'-' as a PATH (content on STDIN) is ignored for {CliCmd.CONFIG} {CliCmd.CONFIG_DUMP}."
    ),
    epilog=(
        "Notes:\n"
        "  • File lists are inputs, not configuration; they are ignored by "
        f"{CliCmd.CONFIG} {CliCmd.CONFIG_DUMP}.\n"
        "  • Pattern sources are part of configuration and are included in the dump.\n"
        "  • In the default (human) format, output is wrapped between "
        f"'{TOML_BLOCK_START}' and '{TOML_BLOCK_END}' markers."
    ),
    context_settings=CONTEXT_SETTINGS,
)
# Common option decorators
@common_ui_options
@common_config_options
@common_output_format_options
# Command-specific option decorators
@common_file_and_filtering_options
@common_header_formatting_options
def config_dump_command(
    *,
    # Command options: common options (verbosity, color)
    verbose: int,
    quiet: int,
    color_mode: ColorMode | None,
    no_color: bool,
    # Command options: output format
    output_format: OutputFormat | None,
    # Command options: common_file_filtering_options
    files_from: list[str] | None = None,
    include_patterns: list[str],
    include_from: list[str],
    exclude_patterns: list[str],
    exclude_from: list[str],
    include_file_types: list[str],
    exclude_file_types: list[str],
    relative_to: str | None,
    stdin_filename: str | None,
    # Command options: config
    no_config: bool,
    config_paths: list[str],
    # Command options: formatting
    align_fields: bool,
    header_format: HeaderOutputFormat | None,
) -> None:
    """Dump the final merged configuration as TOML.

    Builds the effective configuration from defaults, discovered/explicit
    config files, and CLI overrides, then prints it as TOML surrounded by
    BEGIN/END markers. This is useful for debugging or for external tools
    that need to consume the resolved configuration.

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
        files_from: Files that contain newline‑delimited *paths* to add to the
            candidate set before filtering. Use ``-`` to read from STDIN.
        include_patterns: Glob patterns to *include* (intersection).
        include_from: Files that contain include glob patterns (one per line).
            Use ``-`` to read patterns from STDIN.
        exclude_patterns: Glob patterns to *exclude* (subtraction).
        exclude_from: Files that contain exclude glob patterns (one per line).
            Use ``-`` to read patterns from STDIN.
        include_file_types: Restrict processing to the given file type identifiers.
        exclude_file_types: Exclude processing for the given file type identifiers.
        relative_to: Base directory used to compute relative paths in outputs.
        stdin_filename: Assumed filename when  reading content from STDIN).
        no_config: If True, skip loading project/user configuration files.
        config_paths: Additional configuration file paths to load and merge.
        align_fields: Whether to align header fields when rendering (captured in config).
        header_format: Optional output format override for header
            rendering (captured in config).

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

    # config_dump_command() is file-agnostic: ignore positional PATHS and --files-from
    apply_ignore_positional_paths_policy(ctx, warn_stdin_dash=True)
    files_from = apply_ignore_files_from_policy(
        ctx,
        files_from=files_from,
    )

    plan: InputPlan = plan_cli_inputs(
        ctx=ctx,
        files_from=files_from or [],
        include_from=include_from,
        exclude_from=exclude_from,
        include_patterns=include_patterns,
        exclude_patterns=exclude_patterns,
        stdin_filename=stdin_filename,
        allow_empty_paths=True,
    )

    draft_config: MutableConfig = build_config_for_plan(
        ctx=ctx,
        plan=plan,
        no_config=no_config,
        config_paths=config_paths,
        include_file_types=include_file_types,
        exclude_file_types=exclude_file_types,
        relative_to=relative_to,
        align_fields=align_fields,
        header_format=header_format,
    )

    config: Config = draft_config.freeze()

    # Display Config diagnostics before resolving files
    if fmt == OutputFormat.TEXT:
        render_config_diagnostics_text(ctx=ctx, config=config)

    temp_path: Path | None = plan.temp_path  # for cleanup/STDIN-apply branch
    # Determine effective program-output verbosity for gating extra details
    vlevel: int = get_effective_verbosity(ctx, config)

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
            meta=meta,
            config=config,
            fmt=fmt,
        )
        _exit()

    # Human formats
    prepared: ConfigDumpPrepared = prepare_config_dump(config=config)

    if fmt == OutputFormat.MARKDOWN:
        md: str = emit_config_dump_markdown(
            prepared=prepared,
            verbosity_level=vlevel,
        )
        console.print(md, nl=False)
        _exit()

    if fmt == OutputFormat.TEXT:
        emit_config_dump_text(
            console=console,
            prepared=prepared,
            verbosity_level=vlevel,
        )
        _exit()

    # Defensive guard in case OutputFormat gains new members
    raise NotImplementedError(f"Unsupported output format: {fmt!r}")
