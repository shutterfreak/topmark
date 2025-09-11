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

This module provides helpers to convert Click command-line parameters into a
[`topmark.config.Config`][topmark.config.Config] object. It bridges CLI parsing and the core
configuration system by building an ArgsNamespace and merging user, project,
and default config sources.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.cli.cli_types import ArgsNamespace, build_args_namespace
from topmark.config import Config
from topmark.config.logging import get_logger

if TYPE_CHECKING:
    import click

    from topmark.rendering.formats import HeaderOutputFormat

logger = get_logger(__name__)


# Helper: Build Config from Click params using ArgsNamespace and merged config logic
def resolve_config_from_click(
    *,
    ctx: click.Context,
    verbosity_level: int | None,
    apply_changes: bool | None,
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
    """Build a [`Config`][topmark.config.Config] from Click parameters.

    Args:
        ctx (click.Context): Click context that provides the resolved log level.
        verbosity_level (int | None): Program-output verbosity (0=terse, 1=verbose);
            None = inherit from parent context.
        apply_changes (bool | None): Whether to apply the changed (dry-run if not set ot False).
        files (list[str]): File paths passed on the command line.
        files_from (list[str]): Paths to files that contain lists of file paths.
        stdin (bool): Whether to read file paths from standard input.
        include_patterns (list[str]): Glob patterns of files to include.
        include_from (list[str]): Paths to files that contain include patterns.
        exclude_patterns (list[str]): Glob patterns of files to exclude.
        exclude_from (list[str]): Paths to files that contain exclude patterns.
        file_types (list[str]): File type identifiers to restrict processing to.
        relative_to (str | None): Root directory used to compute relative paths.
        no_config (bool): If True, ignore local project config files.
        config_paths (list[str]): Extra config TOML file paths to merge.
        align_fields (bool): Whether to align header fields with colons.
        header_format (HeaderOutputFormat | None): Selected header output format.

    Returns:
        Config: The merged configuration.
    """
    args: ArgsNamespace = build_args_namespace(
        verbosity_level=verbosity_level,
        apply_changes=apply_changes,
        files=files,
        files_from=files_from,
        stdin=stdin,
        include_patterns=include_patterns,
        include_from=include_from,
        exclude_patterns=exclude_patterns,
        exclude_from=exclude_from,
        no_config=no_config,
        config_files=config_paths,
        file_types=file_types,
        relative_to=relative_to,
        align_fields=align_fields,
        header_format=header_format,
    )
    logger.trace("ArgsNamespace: %s", args)
    return Config.load_merged(args)
