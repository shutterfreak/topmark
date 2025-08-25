# topmark:header:start
#
#   file         : dump_config.py
#   file_relpath : src/topmark/cli/commands/dump_config.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""TopMark `dump-config` command.

Emits the effective TopMark configuration as TOML after applying defaults,
project/user config files, and any CLI overrides. The output is wrapped
between `# === BEGIN ===` and `# === END ===` markers for easy parsing in
tests or tooling.
"""

import click
from yachalk import chalk

from topmark.cli.config_resolver import resolve_config_from_click
from topmark.cli.options import (
    common_config_options,
    common_file_and_filtering_options,
    common_header_formatting_options,
    typed_argument,
)
from topmark.rendering.formats import HeaderOutputFormat


@typed_argument("files", nargs=-1)
@common_config_options
@common_file_and_filtering_options
@common_header_formatting_options
def dump_config_command(
    # Command arguments
    files: list[str],
    # Command options: common_file_filtering_options
    stdin: bool,
    include_patterns: list[str],
    include_from: list[str],
    exclude_patterns: list[str],
    exclude_from: list[str],
    file_types: list[str],
    relative_to: str | None,
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
        files: Positional file or directory paths used to influence config
            discovery or resolution (may be empty).
        stdin: If True, read newline‑separated paths from standard input
            when resolving files (may affect config discovery).
        include_patterns: Additional include glob patterns to consider.
        include_from: Paths to files containing include patterns (one per line).
        exclude_patterns: Glob patterns to exclude from consideration.
        exclude_from: Paths to files containing exclude patterns (one per line).
        file_types: Explicit file‑type filters to restrict processing.
        relative_to: Optional base directory for resolving relative paths.
        no_config: If True, skip loading project/user configuration files.
        config_paths: Additional TOML config files to merge into the effective config.
        align_fields: Whether to align header fields when rendering (captured in config).
        header_format: Optional output format override for header rendering (captured in config).

    Returns:
        None. Prints the merged configuration as TOML to stdout.
    """
    ctx = click.get_current_context()
    ctx.ensure_object(dict)

    config = resolve_config_from_click(
        ctx=ctx,
        files=list(files),
        stdin=stdin,
        include_patterns=list(include_patterns),
        include_from=list(include_from),
        exclude_patterns=list(exclude_patterns),
        exclude_from=list(exclude_from),
        file_types=list(file_types),
        relative_to=relative_to,
        no_config=no_config,
        config_paths=list(config_paths),
        align_fields=align_fields,
        header_format=header_format,
    )

    import toml

    merged_config = toml.dumps(config.to_toml_dict())
    click.echo(chalk.bold.underline("TopMark Config Dump:"))
    click.echo(
        chalk.dim(
            f"# Merged TopMark config (TOML):\n\n# === BEGIN ===\n{merged_config}# === END ==="
        )
    )
    return
