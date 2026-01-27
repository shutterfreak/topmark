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

from topmark.cli.cli_types import build_args_namespace
from topmark.config import MutableConfig
from topmark.config.logging import get_logger
from topmark.core.keys import ArgKey

if TYPE_CHECKING:
    import click

    from topmark.cli.cli_types import ArgsNamespace
    from topmark.config.logging import TopmarkLogger
    from topmark.rendering.formats import HeaderOutputFormat

logger: TopmarkLogger = get_logger(__name__)


# Helper: Build Config from Click params using ArgsNamespace and merged config logic
def resolve_config_from_click(
    *,
    ctx: click.Context,
    verbosity_level: int | None,
    apply_changes: bool | None,
    write_mode: str | None,
    files: list[str],
    files_from: list[str],
    stdin_mode: bool,
    stdin_filename: str | None,
    include_patterns: list[str],
    include_from: list[str],
    exclude_patterns: list[str],
    exclude_from: list[str],
    include_file_types: list[str],
    exclude_file_types: list[str],
    relative_to: str | None,
    no_config: bool,
    config_paths: list[str],
    align_fields: bool | None,
    header_format: HeaderOutputFormat | None,
) -> MutableConfig:
    """Build a [`Config`][topmark.config.Config] from Click parameters.

    Resolves a layered configuration by merging multiple sources with clear
    precedence. Discovery is anchored to the **first input path** (its parent
    if it is a file), or to the current working directory when no input paths
    are provided or when reading from STDIN.

    Resolution order (lowest → highest precedence):
      1. **Packaged defaults** (bundled `topmark-default.toml`).
      2. **User config** (if present):
         - `$XDG_CONFIG_HOME/topmark/topmark.toml` or `~/.topmark.toml`.
      3. **Discovered project configs** (root → cwd), unless `--no-config` is set:
         - In each directory, inspect both `pyproject.toml` (`[tool.topmark]`)
           and `topmark.toml`. Merge **`pyproject.toml` first** and then
           **`topmark.toml`** so tool-specific files override the table.
         - Stop discovery early if a discovered file sets `root = true` (either at
           the top level of `topmark.toml` or under `[tool.topmark]` in `pyproject.toml`).
      4. **Explicit config files** passed via `--config`, merged **in order**.
      5. **CLI overrides** (flags/args), applied last.

    Args:
        ctx (click.Context): Click context that provides the resolved log level.
        verbosity_level (int | None): Program-output verbosity (0=terse, 1=verbose);
            None = inherit from parent context.
        apply_changes (bool | None): Whether to apply the changes (dry-run if not set or False).
        write_mode (str | None): Whether to use safe atomic writing, faster in-place writing
            or writing to STDOUT (default: atomic writer).
        files (list[str]): File paths passed on the command line.
        files_from (list[str]): Paths to files that contain lists of file paths.
        stdin_mode (bool): Whether to read file contents from standard input.
        stdin_filename (str | None): The filename to use when in STDIN mode.
        include_patterns (list[str]): Glob patterns of files to include.
        include_from (list[str]): Paths to files that contain include patterns.
        exclude_patterns (list[str]): Glob patterns of files to exclude.
        exclude_from (list[str]): Paths to files that contain exclude patterns.
        include_file_types (list[str]): File type identifiers to restrict processing to.
        exclude_file_types (list[str]): File type identifiers to exclude processing for.
        relative_to (str | None): Root directory used to compute relative paths.
        no_config (bool): If True, ignore local project config files.
        config_paths (list[str]): Extra config TOML file paths to merge.
        align_fields (bool | None): Whether to align header fields with colons.
        header_format (HeaderOutputFormat | None): Selected header output format.

    Returns:
        MutableConfig: The merged configuration (mutable draft). Call `.freeze()`
            to obtain the immutable `Config` snapshot used by the pipeline.
    """
    args: ArgsNamespace = build_args_namespace(
        verbosity_level=verbosity_level,
        apply_changes=apply_changes,
        write_mode=write_mode,
        files=files,
        files_from=files_from,
        stdin_mode=stdin_mode,
        stdin_filename=stdin_filename,
        include_patterns=include_patterns,
        include_from=include_from,
        exclude_patterns=exclude_patterns,
        exclude_from=exclude_from,
        no_config=no_config,
        config_files=config_paths,
        include_file_types=include_file_types,
        exclude_file_types=exclude_file_types,
        relative_to=relative_to,
        align_fields=align_fields,
        header_format=header_format,
    )
    logger.trace("ArgsNamespace: %s", args)

    # Resolution order (lowest → highest precedence):
    # (1) defaults
    draft: MutableConfig = MutableConfig.from_defaults()

    # (2) user config (if present)
    user_cfg_path: Path | None = MutableConfig.discover_user_config_file()
    if user_cfg_path:
        logger.info("Loading user config: %s", user_cfg_path)
        user_cfg: MutableConfig | None = MutableConfig.from_toml_file(user_cfg_path)
        if user_cfg is not None:
            draft = draft.merge_with(user_cfg)

    # (3) layered discovery from anchor (first file path’s directory, else CWD)
    if not args.get(ArgKey.NO_CONFIG):
        # Determine anchor directory. If a file path was provided, start from its parent.
        raw_files: list[str] = args.get(ArgKey.FILES) or []
        cwd: Path = Path.cwd().resolve()  # Resolve symlinks and get absolute path
        anchor: Path = cwd

        # If we are reading a single file's *content* from STDIN (PATH='-'),
        # allow `--stdin-filename` to influence config discovery when it contains
        # a directory component (e.g. "app/pkg/__init__.py"). Otherwise default to CWD.
        if args.get(ArgKey.STDIN_MODE) is True:
            stdin_filename_from_args: str | None = args.get(ArgKey.STDIN_FILENAME)
            if stdin_filename_from_args:
                sf: Path = Path(stdin_filename_from_args)
                # Only treat it as an anchor hint when it includes a parent dir.
                if sf.parent != Path():
                    anchor = (sf.parent if sf.is_absolute() else (cwd / sf.parent)).resolve()
        else:
            for f in raw_files:
                # Skip STDIN marker "-" if present; use the first real path
                if f and f != "-":
                    p: Path = Path(f)
                    anchor = (p.parent if p.is_file() else p).resolve()
                    break
        logger.debug("Config discovery anchor: %s", anchor)

        discovered_paths: list[Path] = MutableConfig.discover_local_config_files(anchor)
        if discovered_paths:
            logger.trace("Discovered config chain (root→cwd): %s", discovered_paths)
        for cfg_path in discovered_paths:
            found: MutableConfig | None = MutableConfig.from_toml_file(cfg_path)
            if found is not None:
                draft = draft.merge_with(found)
            else:
                logger.warning("Ignoring discovered config without [tool.topmark]: %s", cfg_path)

    # (4) explicit config files
    raw_config_files: list[str] = args.get(ArgKey.CONFIG_FILES) or []
    for entry in raw_config_files:
        p = Path(entry)
        if not p.exists():
            logger.warning("Config file not found: %s", p)
            continue
        logger.info("Loading explicit config: %s", p)
        extra: MutableConfig | None = MutableConfig.from_toml_file(p)
        if extra is not None:
            draft = draft.merge_with(extra)
        else:
            logger.warning("Ignoring config without [tool.topmark]: %s", p)

    # (5) CLI overrides last
    draft = draft.apply_args(args)

    return draft
