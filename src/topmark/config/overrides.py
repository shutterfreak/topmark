# topmark:header:start
#
#   project      : TopMark
#   file         : overrides.py
#   file_relpath : src/topmark/config/overrides.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Apply external override intent to a resolved `MutableConfig` draft.

This module sits *after* layered config discovery/resolution. Its job is to
apply the highest-precedence override layer coming from CLI or API inputs
without reimplementing config-file discovery.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from topmark.cli.keys import CliOpt
from topmark.config.model import MutableConfig
from topmark.config.paths import extend_pattern_sources
from topmark.config.paths import pattern_source_from_cwd
from topmark.config.types import FileWriteStrategy
from topmark.config.types import OutputTarget
from topmark.constants import CLI_OVERRIDE_STR
from topmark.core.keys import ArgKey
from topmark.core.logging import get_logger

if TYPE_CHECKING:
    from topmark.config.model import MutableConfig
    from topmark.core.logging import TopmarkLogger

logger: TopmarkLogger = get_logger(__name__)


def apply_config_overrides(
    config: MutableConfig,
    *,
    # Pipeline: policy
    add_only: bool | None = None,
    update_only: bool | None = None,
    # Pipeline intent
    apply_changes: bool | None = None,
    # Write mode
    write_mode: str | None = None,
    # STDIN mode
    stdin_mode: bool | None = None,
    stdin_filename: str | None = None,
    # Files
    files: list[str] | None = None,
    files_from: list[str] | None = None,
    include_patterns: list[str] | None = None,
    include_from: list[str] | None = None,
    exclude_patterns: list[str] | None = None,
    exclude_from: list[str] | None = None,
    # Pipeline: filter per type
    include_file_types: list[str] | None = None,
    exclude_file_types: list[str] | None = None,
    # Header fields
    header_fields: list[str] | None = None,
    field_values: dict[str, str] | None = None,
    # Headers: formatting
    align_fields: bool | None = None,
    # Headers: relative path anchor
    relative_to: str | None = None,
    # Config - TODO decide whether to keeo or remove
    strict_config_checking: bool | None = None,
) -> MutableConfig:
    """Apply CLI/API override intent to an existing mutable config draft.

    This helper updates an already-resolved `MutableConfig` with the final
    highest-precedence override layer. It intentionally does **not** handle
    config discovery concerns such as `--no-config` or `--config`; those belong
    to `topmark.config.io.resolution`.

    Args:
        config: Mutable config draft to mutate in place.
        add_only: Only add missing headers; do not update existing ones.
        update_only: Only update existing headers; do not add new ones.
        apply_changes: Whether changes should be written instead of previewed.
        write_mode: Requested output/write mode (`stdout`, `atomic`, `inplace`,
            or `None` to keep the resolved config value).
        stdin_mode: Whether the command is operating in STDIN mode.
        stdin_filename: Synthetic filename used to resolve file type / relative
            context in STDIN mode.
        files: Explicit file paths passed on the command line or by the caller.
        files_from: Files containing file lists.
        include_patterns: Include glob patterns.
        include_from: Files containing include glob patterns.
        exclude_patterns: Exclude glob patterns.
        exclude_from: Files containing exclude glob patterns.
        include_file_types: File-type allowlist override.
        exclude_file_types: File-type denylist override.
        header_fields: Explicit ordered list of header fields to render.
        field_values: Explicit header field values.
        align_fields: Override for header field alignment.
        relative_to: Override for header-relative metadata generation
            (e.g. `file_relpath`).
        strict_config_checking: Override for strict config checking.

    Returns:
        The same `MutableConfig` instance after in-place mutation.

    Notes:
        - Path-to-file options (`--include-from`, `--exclude-from`,
          `--files-from`) are normalized against the current working directory,
          because they originate from the invocation site rather than a config
          file directory.
        - `relative_to` influences only header metadata generation. It does not
          change how config-declared glob sources are interpreted.
        - The special `CLI_OVERRIDE_STR` provenance marker is appended to
          `config.config_files` so downstream views can show that a CLI/API
          override layer was applied.
    """
    # strict_config_checking
    if strict_config_checking is not None:
        config.strict_config_checking = strict_config_checking

    # Record that a highest-precedence CLI/API override layer was applied.
    # This is provenance-only; explicit `--config` files are merged earlier by
    # the resolution layer.
    if config.config_files:
        config.config_files.append(CLI_OVERRIDE_STR)
    else:
        config.config_files = [CLI_OVERRIDE_STR]

    # Note: CLI config paths are already merged elsewhere
    # so we don't extend config.config_files here.

    # Policy flags (add_only, update_only)
    if add_only is not None:
        config.policy.add_only = add_only
    if update_only is not None:
        config.policy.update_only = update_only
    # ... but do not zero-out policy_by_type when ConfigMapping says nothing

    if apply_changes is not None:
        config.apply_changes = apply_changes

    # Explicit file inputs replace any previously resolved file list.
    if files is not None:
        raw_files: list[str] = files
        empties: list[str] = [s for s in raw_files if not s]
        if empties:
            config.diagnostics.add_warning(
                f"Ignoring empty string entries in {ArgKey.FILES.value}: {empties!r}"
            )
        # Keep only the non-empty entries
        config.files = [s for s in raw_files if s]
        if config.files:
            config.stdin_mode = False

    # CLI/API include/exclude sources are normalized against the invocation CWD.
    cwd: Path = Path.cwd().resolve()

    # Glob patterns: include_patterns / exclude_patterns (extend)
    if include_patterns is not None:
        vals: list[str] = [s for s in include_patterns if s]
        if vals:
            config.include_patterns.extend(vals)

    if exclude_patterns is not None:
        vals = [s for s in exclude_patterns if s]
        if vals:
            config.exclude_patterns.extend(vals)

    # Path-to-file options: include_from, exclude_from, files_from (validate list[str])
    if include_from is not None:
        vals = [s for s in include_from if s]
        extend_pattern_sources(
            config.include_from,
            vals,
            pattern_source_from_cwd,
            f"CLI {CliOpt.INCLUDE_FROM}",
            cwd,
        )
    if exclude_from is not None:
        vals = [s for s in exclude_from if s]
        extend_pattern_sources(
            config.exclude_from,
            vals,
            pattern_source_from_cwd,
            f"CLI {CliOpt.EXCLUDE_FROM}",
            cwd,
        )

    if files_from is not None:
        vals = [s for s in files_from if s]
        extend_pattern_sources(
            config.files_from,
            vals,
            pattern_source_from_cwd,
            f"CLI {CliOpt.FILES_FROM}",
            cwd,
        )

    # Header-building overrides apply only when explicitly provided.

    # relative_to: string or None, only override if non-empty string (not just whitespace)
    if relative_to and (rel_str := relative_to.strip()):
        config.relative_to_raw = rel_str
        config.relative_to = Path(rel_str).resolve()

    # align_fields: checked bool
    if align_fields is not None:
        config.align_fields = align_fields

    # Absent override values intentionally preserve whatever came from layered
    # config discovery / TOML resolution.

    # include_file_types / exclude_file_types: set of strings, only override if present
    if include_file_types:
        # Only override when the user actually passes a value
        # TODO decide whether `()` clears the property or whether we always extend the set
        filtered: list[str] = [s for s in include_file_types if s]  # drop empty strings
        deduped: set[str] = set(filtered)
        config.include_file_types = deduped
        dup_count: int = len(filtered) - len(deduped)
        if dup_count:
            config.diagnostics.add_info(
                f"Ignored {dup_count} duplicate values for {ArgKey.INCLUDE_FILE_TYPES.value}"
            )

    if exclude_file_types:
        # Only override when the user actually passes a value
        # TODO decide whether `()` clears the property or whether we always extend the set
        filtered: list[str] = [s for s in exclude_file_types if s]  # drop empty strings
        deduped: set[str] = set(filtered)
        config.exclude_file_types = deduped
        dup_count: int = len(filtered) - len(deduped)
        if dup_count:
            config.diagnostics.add_info(
                f"Ignored {dup_count} duplicate values for {ArgKey.EXCLUDE_FILE_TYPES.value}"
            )

    if header_fields is not None:
        config.header_fields = header_fields

    if field_values is not None:
        config.field_values = field_values

    # STDIN mode flags must preserve explicit False as an override, so apply
    # them only when the caller provided a concrete value.
    if stdin_mode is not None:
        # honor False explicitly
        config.stdin_mode = stdin_mode

    if stdin_filename:
        # `stdin_filename` is only meaningful when non-empty.
        config.stdin_filename = stdin_filename

    # `write_mode` is a convenience selector:
    #   - `stdout`  -> emit rewritten content to STDOUT
    #   - `atomic`  -> write to file via atomic replacement
    #   - `inplace` -> write to file in place
    if write_mode:
        # CLI uses ArgKey.WRITE_MODE as a convenience selector:
        #   - "stdout" -> output to STDOUT (no file strategy)
        #   - "atomic"/"inplace" -> output to FILE + set strategy
        if write_mode == "stdout":
            config.output_target = OutputTarget.STDOUT
            config.file_write_strategy = None
        else:
            config.output_target = OutputTarget.FILE
            file_write_strategy: FileWriteStrategy | None = FileWriteStrategy.parse(write_mode)
            if file_write_strategy is None:
                config.diagnostics.add_warning(
                    f"Invalid '{ArgKey.WRITE_MODE.value}' value specified "
                    f"in the arguments: {write_mode} - "
                    "using defaults: output to file, atomic file write strategy."
                )
                file_write_strategy = FileWriteStrategy.ATOMIC
            config.file_write_strategy = file_write_strategy

    logger.debug("Patched MutableConfig: %s", config)
    logger.info("Applied argument mapping overrides to MutableConfig")
    logger.debug("Finalized _mode=%s files=%s", config.stdin_mode, config.files)

    return config
