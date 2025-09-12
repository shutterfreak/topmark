# topmark:header:start
#
#   project      : TopMark
#   file         : dump_config.py
#   file_relpath : src/topmark/cli/commands/dump_config.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""TopMark `dump-config` command.

Emits the effective TopMark configuration as TOML after applying defaults,
project/user config files, and any CLI overrides. The output is wrapped
between `# === BEGIN ===` and `# === END ===` markers for easy parsing in
tests or tooling.

Input modes:
  * This command is file-agnostic: positional PATHS and --files-from are ignored
    (with a warning if present).
  * --include-from - and --exclude-from - are honored for config resolution.
  * '-' as a PATH (content-on-STDIN) is ignored in dump-config.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import click

from topmark.cli.cmd_common import build_config_common, get_effective_verbosity
from topmark.cli.io import plan_cli_inputs
from topmark.cli.options import (
    CONTEXT_SETTINGS,
    common_config_options,
    common_file_and_filtering_options,
    common_header_formatting_options,
)
from topmark.cli_shared.utils import safe_unlink
from topmark.config.logging import get_logger

if TYPE_CHECKING:
    from topmark.cli_shared.console_api import ConsoleLike
    from topmark.rendering.formats import HeaderOutputFormat

logger = get_logger(__name__)


@click.command(
    name="dump-config",
    help=(
        "Dump the final merged TopMark configuration as TOML. "
        "This command is file‑agnostic: positional PATHS and --files-from are ignored. "
        "Filter flags are honored (e.g., --include/--exclude and --include-from/--exclude-from). "
        "Use --include-from - / --exclude-from - to read patterns from STDIN; "
        "'-' as a PATH (content on STDIN) is ignored for dump-config."
    ),
    epilog=(
        "Notes:\n"
        "  • File lists are inputs, not configuration; they are ignored by dump-config.\n"
        "  • Pattern sources are part of configuration and are included in the dump.\n"
        "  • Output is wrapped between '# === BEGIN ===' and '# === END ===' markers."
    ),
    context_settings=CONTEXT_SETTINGS,
)
@common_config_options
@common_file_and_filtering_options
@common_header_formatting_options
def dump_config_command(
    # Command arguments
    *,
    # Command options: common_file_filtering_options
    files_from: list[str] | None = None,
    include_patterns: list[str],
    include_from: list[str],
    exclude_patterns: list[str],
    exclude_from: list[str],
    file_types: list[str],
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

    Args:
        files_from (list[str] | None): Files that contain newline‑delimited *paths* to add to the
            candidate set before filtering. Use ``-`` to read from STDIN.
        include_patterns (list[str]): Glob patterns to *include* (intersection).
        include_from (list[str]): Files that contain include glob patterns (one per line).
            Use ``-`` to read patterns from STDIN.
        exclude_patterns (list[str]): Glob patterns to *exclude* (subtraction).
        exclude_from (list[str]): Files that contain exclude glob patterns (one per line).
            Use ``-`` to read patterns from STDIN.
        file_types (list[str]): Restrict processing to the given TopMark file type identifiers.
        relative_to (str | None): Base directory used to compute relative paths in outputs.
        stdin_filename (str | None): Assumed filename when  reading content from STDIN).
        no_config (bool): If True, skip loading project/user configuration files.
        config_paths (list[str]): Additional configuration file paths to load and merge.
        align_fields (bool): Whether to align header fields when rendering (captured in config).
        header_format (HeaderOutputFormat | None): Optional output format override for header
            rendering (captured in config).
    """
    ctx = click.get_current_context()
    ctx.ensure_object(dict)
    console: ConsoleLike = ctx.obj["console"]

    # dump-config is file-agnostic: ignore positional PATHS and --files-from
    original_args = list(ctx.args)
    if original_args:
        if "-" in original_args:
            console.warn(
                "Note: dump-config is file-agnostic; '-' (content from STDIN) is ignored.",
            )
        console.warn("Note: dump-config is file-agnostic; positional paths are ignored.")
        ctx.args = []
    if files_from:
        console.warn(
            "Note: dump-config ignores --files-from "
            "(file lists are not part of the configuration).",
        )
        files_from = []

    plan = plan_cli_inputs(
        ctx=ctx,
        files_from=files_from or [],
        include_from=include_from,
        exclude_from=exclude_from,
        include_patterns=include_patterns,
        exclude_patterns=exclude_patterns,
        stdin_filename=stdin_filename,
        allow_empty_paths=True,
    )

    draft_config = build_config_common(
        ctx=ctx,
        plan=plan,
        no_config=no_config,
        config_paths=config_paths,
        file_types=file_types,
        relative_to=relative_to,
        align_fields=align_fields,
        header_format=header_format,
    )

    temp_path = plan.temp_path  # for cleanup/STDIN-apply branch
    config = draft_config.freeze()
    # Determine effective program-output verbosity for gating extra details
    vlevel = get_effective_verbosity(ctx, config)

    logger.trace("Config after merging CLI and discovered config: %s", draft_config)

    # We don't actually care about the file list here; just dump the config
    import toml

    merged_config = toml.dumps(config.to_toml_dict())

    # Banner
    if vlevel > 0:
        console.print(
            console.styled(
                "TopMark Config Dump (TOML):\n",
                bold=True,
                underline=True,
            )
        )

        console.print(
            console.styled(
                "# === BEGIN ===",
                fg="cyan",
                dim=True,
            )
        )

    console.print(
        console.styled(
            merged_config,
            fg="cyan",
        )
    )

    if vlevel > 0:
        console.print(
            console.styled(
                "# === END ===",
                fg="cyan",
                dim=True,
            )
        )

    # Cleanup any temp file created by content-on-STDIN mode (defensive)
    if temp_path and temp_path.exists():
        safe_unlink(temp_path)

    # No explicit return needed for Click commands.
