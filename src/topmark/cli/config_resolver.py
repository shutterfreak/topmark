# topmark:header:start
#
#   project      : TopMark
#   file         : config_resolver.py
#   file_relpath : src/topmark/cli/config_resolver.py
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

from pathlib import Path
from typing import TYPE_CHECKING

from topmark.cli.cli_types import ArgsNamespace, build_args_namespace
from topmark.config import MutableConfig
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
) -> MutableConfig:
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
        MutableConfig: The merged configuration.
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

    # Resolution order (most specific last):
    #   1) packaged defaults
    #   2) discovered project config in CWD (pyproject.toml → [tool.topmark], else topmark.toml),
    #      unless --no-config is set OR explicit config files were provided
    #   3) any explicitly provided config files, in the given order
    #   4) CLI overrides (flags/args)
    #
    # The result is a MutableConfig (builder) which callers can .freeze() before running.

    draft = MutableConfig.from_defaults()

    # (2) discover a single local project config if allowed and none explicitly provided
    if not args.get("no_config") and not (args.get("config_files") or []):
        cwd = Path.cwd()
        pyproject = cwd / "pyproject.toml"
        topmark_toml = cwd / "topmark.toml"
        discovered: Path | None = None
        if pyproject.exists():
            discovered = pyproject
        elif topmark_toml.exists():
            discovered = topmark_toml

        if discovered is not None:
            logger.info("Loading discovered project config: %s", discovered)
            found = MutableConfig.from_toml_file(discovered)
            if found is not None:
                draft = draft.merge_with(found)
            else:
                logger.warning(
                    "Discovered config is missing [tool.topmark] or invalid: %s",
                    discovered,
                )

    # (3) apply any explicit config files next (these override discovered/defaults)
    for entry in args.get("config_files") or []:
        p = Path(entry)
        if not p.exists():
            logger.warning("Config file not found: %s", p)
            continue
        logger.info("Loading explicit config: %s", p)
        extra = MutableConfig.from_toml_file(p)
        if extra is not None:
            draft = draft.merge_with(extra)
        else:
            logger.warning("Ignoring config without [tool.topmark]: %s", p)

    # (4) finally, CLI args override everything
    draft = draft.apply_cli_args(args)

    return draft
