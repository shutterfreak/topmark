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
from typing import TYPE_CHECKING, Any

import click

from topmark.cli.cli_types import EnumChoiceParam
from topmark.cli.cmd_common import get_effective_verbosity
from topmark.cli.keys import CliCmd, CliOpt
from topmark.cli.options import (
    common_config_options,
)
from topmark.cli.utils import (
    emit_config_check_machine,
    render_config_check_markdown,
    render_toml_block,
)
from topmark.cli_shared.utils import OutputFormat
from topmark.config import Config, MutableConfig
from topmark.config.io import to_toml
from topmark.config.logging import get_logger
from topmark.config.machine.payloads import (
    build_config_diagnostics_payload,
)
from topmark.core.exit_codes import ExitCode
from topmark.core.keys import ArgKey

if TYPE_CHECKING:
    from topmark.cli_shared.console_api import ConsoleLike
    from topmark.config.logging import TopmarkLogger
    from topmark.config.machine.schemas import (
        ConfigDiagnosticCounts,
        ConfigDiagnosticEntry,
        ConfigDiagnosticsPayload,
    )

logger: TopmarkLogger = get_logger(__name__)


@click.command(
    name=f"{CliCmd.CONFIG}-{CliCmd.CONFIG_CHECK}",
    help="Validate merged configuration and report any diagnostics.",
)
@common_config_options
@click.option(
    f"{CliOpt.STRICT_CONFIG_CHECKING}/{CliOpt.NO_STRICT_CONFIG_CHECKING}",
    ArgKey.STRICT_CONFIG_CHECKING,
    default=False,
    show_default=True,
    help="Fail if any warnings are present (in addition to errors).",
)
@click.option(
    CliOpt.OUTPUT_FORMAT,
    ArgKey.OUTPUT_FORMAT,
    type=EnumChoiceParam(OutputFormat),
    default=None,
    help=f"Output format ({', '.join(v.value for v in OutputFormat)}).",
)
def config_check_command(
    *,
    # Command options: config
    strict_config_checking: bool,
    no_config: bool,
    config_paths: list[str],
    # Ouptut format
    output_format: OutputFormat | None,
) -> None:
    """Validates and verifies the final merged configuration.

    Builds the effective configuration from defaults, discovered/explicit
    config files, and CLI overrides, then validates it.
    This is useful for debugging or for external tools
    that need to consume the resolved configuration.

    Args:
        strict_config_checking (bool): if True, report warnings as errors.
        no_config (bool): If True, skip loading project/user configuration files.
        config_paths (list[str]): Additional configuration file paths to load and merge.
        output_format (OutputFormat | None): Output format to use
            (``default``, ``markdown``, ``json``, or ``ndjson``).

    Raises:
        NotImplementedError: When providing an unsupported OutputType.
    """
    ctx: click.Context = click.get_current_context()
    ctx.ensure_object(dict)
    console: ConsoleLike = ctx.obj[ArgKey.CONSOLE]

    fmt: OutputFormat = output_format or OutputFormat.DEFAULT

    # config_check_command() is file-agnostic: ignore positional PATHS
    original_args: list[str] = list(ctx.args)
    if original_args:
        if "-" in original_args:
            console.warn(
                f"Note: {CliCmd.CONFIG} {CliCmd.CONFIG_CHECK} is file-agnostic; "
                "'-' (content from STDIN) is ignored.",
            )
        console.warn(
            f"Note: {CliCmd.CONFIG} {CliCmd.CONFIG_CHECK} is file-agnostic; "
            "positional paths are ignored.",
        )
        ctx.args = []

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
    diags: list[ConfigDiagnosticEntry] = diag_payload.diagnostics
    counts: ConfigDiagnosticCounts = diag_payload.diagnostic_counts
    n_info: int = counts.info
    n_warn: int = counts.warning
    n_err: int = counts.error
    fail: bool = (n_err > 0) or (strict_config_checking and n_warn > 0)

    # Determine effective program-output verbosity for gating extra details
    vlevel: int = get_effective_verbosity(ctx, config)

    logger.trace("Config after merging CLI and discovered config: %s", draft_config)

    if fmt in (OutputFormat.JSON, OutputFormat.NDJSON):
        emit_config_check_machine(
            config,
            strict=strict_config_checking,
            ok=not fail,
            fmt=fmt,
        )

    elif fmt == OutputFormat.MARKDOWN:
        md: str = render_config_check_markdown(
            ok=not fail,
            strict=strict_config_checking,
            counts=counts,
            diagnostics=diags,
            config_files=[str(p) for p in config.config_files],
            verbosity_level=vlevel,
        )
        click.echo(md, nl=False)

    elif fmt == OutputFormat.DEFAULT:
        # Human-readable output.
        if not diags:
            click.echo("✅ Config OK (no diagnostics).")
        else:
            click.echo(
                "Config diagnostics: "
                f"{n_err} error(s), {n_warn} warning(s), {n_info} information(s)"
            )
            if vlevel > 0:
                for d in diags:
                    click.echo(f"- {d.level}: {d.message}")

        if vlevel > 0:
            # Render the list of config files
            click.echo(f"Config files processed: {len(config.config_files)}")
            for i, c in enumerate(config.config_files, start=1):
                click.echo(f"Loaded config {i}: {c}")

        if vlevel > 1:
            config_toml_dict: dict[str, Any] = config.to_toml_dict()
            merged_config: str = to_toml(config_toml_dict)
            render_toml_block(
                console=console,
                title="TopMark Config (TOML):",
                toml_text=merged_config,
                verbosity_level=vlevel,
            )

        click.echo("✅ OK" if not fail else "❌ FAILED")
    else:
        # Defensive guard in case OutputFormat gains new members
        raise NotImplementedError(f"Unsupported output format: {fmt!r}")

    ctx.exit(ExitCode.FAILURE if fail else 0)
