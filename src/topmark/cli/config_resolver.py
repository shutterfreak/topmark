# topmark:header:start
#
#   file         : config_resolver.py
#   file_relpath : src/topmark/cli/config_resolver.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Utilities for resolving TopMark configuration from Click parameters.

This module provides helpers to convert Click command-line parameters into an
:class:`~topmark.config.Config` object. It bridges CLI parsing and the core
configuration system by building an ArgsNamespace and merging user, project,
and default config sources.
"""

import click

from topmark.cli.cli_types import ArgsNamespace, build_args_namespace
from topmark.config import Config
from topmark.config.logging import get_logger
from topmark.rendering.formats import HeaderOutputFormat

logger = get_logger(__name__)


# Helper: Build Config from Click params using ArgsNamespace and merged config logic
def resolve_config_from_click(
    *,
    ctx: click.Context,
    files: list[str],
    files_from: list[str],
    stdin: bool,
    include_patterns: list[str],
    include_from: list[str],
    exclude_patterns: list[str],
    exclude_from: list[str],
    file_types: list[str],
    relative_to: str | None,
    no_config: bool,
    config_paths: list[str],
    align_fields: bool,
    header_format: HeaderOutputFormat | None,
) -> Config:
    """Build a :class:`Config` from Click parameters.

    Args:
        ctx: Click context that provides the resolved log level.
        files: File paths passed on the command line.
        files_from: Paths to files that contain lists of file paths.
        stdin: Whether to read file paths from standard input.
        include_patterns: Glob patterns of files to include.
        include_from: Paths to files that contain include patterns.
        exclude_patterns: Glob patterns of files to exclude.
        exclude_from: Paths to files that contain exclude patterns.
        file_types: File type identifiers to restrict processing to.
        relative_to: Root directory used to compute relative paths.
        no_config: If True, ignore local project config files.
        config_paths: Extra config TOML file paths to merge.
        align_fields: Whether to align header fields with colons.
        header_format: Selected header output format.

    Returns:
        Config: The merged configuration.
    """
    args: ArgsNamespace = build_args_namespace(
        log_level=ctx.obj.get("log_level"),
        files=list(files),
        files_from=list(files_from),
        stdin=stdin,
        include_patterns=list(include_patterns),
        include_from=list(include_from),
        exclude_patterns=list(exclude_patterns),
        exclude_from=list(exclude_from),
        no_config=no_config,
        config_files=list(config_paths),
        file_types=list(file_types),
        relative_to=relative_to,
        align_fields=align_fields,
        header_format=header_format,
    )
    logger.trace("ArgsNamespace: %s", args)
    return Config.load_merged(args)
