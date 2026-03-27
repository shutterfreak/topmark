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

from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import TYPE_CHECKING

from topmark.config.model import MutableConfig
from topmark.config.paths import extend_pattern_sources
from topmark.config.paths import pattern_source_from_cwd
from topmark.config.policy import MutablePolicy
from topmark.constants import CLI_OVERRIDE_STR
from topmark.core.logging import get_logger

if TYPE_CHECKING:
    from topmark.config.model import MutableConfig
    from topmark.config.policy import EmptyInsertMode
    from topmark.config.policy import HeaderMutationMode
    from topmark.config.types import FileWriteStrategy
    from topmark.config.types import OutputTarget
    from topmark.core.logging import TopmarkLogger

logger: TopmarkLogger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class PolicyOverrides:
    """Optional overrides for global or per-file-type policy values.

    `None` means "no override provided" for the corresponding policy field.
    """

    header_mutation_mode: HeaderMutationMode | None = None
    allow_header_in_empty_files: bool | None = None
    empty_insert_mode: EmptyInsertMode | None = None
    render_empty_header_when_no_fields: bool | None = None
    allow_reflow: bool | None = None
    allow_content_probe: bool | None = None


@dataclass(frozen=True, slots=True)
class ConfigOverrides:
    """Highest-precedence config overrides from CLI or API inputs.

    `None` means "no override provided". Empty collections are meaningful and
    should therefore be preserved.
    """

    # Policy (global and overrides by file type)
    policy: PolicyOverrides = field(default_factory=PolicyOverrides)
    policy_by_type: dict[str, PolicyOverrides] = field(default_factory=lambda: {})

    # Pipeline intent
    apply_changes: bool | None = None

    # Write options
    output_target: OutputTarget | None = None
    file_write_strategy: FileWriteStrategy | None = None

    # STDIN mode
    stdin_mode: bool | None = None
    stdin_filename: str | None = None

    # Files
    files: list[str] | None = None
    files_from: list[str] | None = None
    include_from: list[str] | None = None
    exclude_from: list[str] | None = None
    include_patterns: list[str] | None = None
    exclude_patterns: list[str] | None = None

    # Pipeline: filter per type
    include_file_types: list[str] | None = None
    exclude_file_types: list[str] | None = None

    # Headers:
    header_fields: list[str] | None = None
    field_values: dict[str, str] | None = None
    align_fields: bool | None = None
    relative_to: str | None = None

    # Config-related options
    strict_config_checking: bool | None = None


def _apply_policy_overrides(dst: MutablePolicy, src: PolicyOverrides) -> None:
    """Apply structured policy overrides to a mutable policy in place.

    Args:
        dst: Mutable policy target to update.
        src: Structured policy overrides to apply.
    """
    if src.header_mutation_mode is not None:
        dst.header_mutation_mode = src.header_mutation_mode
    if src.allow_header_in_empty_files is not None:
        dst.allow_header_in_empty_files = src.allow_header_in_empty_files
    if src.empty_insert_mode is not None:
        dst.empty_insert_mode = src.empty_insert_mode
    if src.render_empty_header_when_no_fields is not None:
        dst.render_empty_header_when_no_fields = src.render_empty_header_when_no_fields
    if src.allow_reflow is not None:
        dst.allow_reflow = src.allow_reflow
    if src.allow_content_probe is not None:
        dst.allow_content_probe = src.allow_content_probe


def apply_config_overrides(
    config: MutableConfig,
    overrides: ConfigOverrides,
) -> MutableConfig:
    """Apply CLI/API override intent to an existing mutable config draft.

    This helper updates an already-resolved `MutableConfig` with the final
    highest-precedence override layer. It intentionally does **not** handle
    config discovery concerns such as `--no-config` or `--config`; those belong
    to `topmark.config.io.resolution`.

    Args:
        config: Mutable config draft to mutate in place.
        overrides: Structured override values coming from CLI/API.

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
          `config.config_files` so downstream views can show that a highest-
          precedence override layer was applied.
    """
    # strict_config_checking
    if overrides.strict_config_checking is not None:
        config.strict_config_checking = overrides.strict_config_checking

    # Record that a highest-precedence CLI/API override layer was applied.
    # This is provenance-only; explicit `--config` files are merged earlier by
    # the resolution layer.
    if config.config_files:
        config.config_files.append(CLI_OVERRIDE_STR)
    else:
        config.config_files = [CLI_OVERRIDE_STR]

    # Note: CLI config paths are already merged elsewhere
    # so we don't extend config.config_files here.

    # policy always exists via default_factory
    _apply_policy_overrides(config.policy, overrides.policy)

    for ft, policy_override in overrides.policy_by_type.items():
        dst: MutablePolicy = config.policy_by_type.get(ft) or MutablePolicy()
        _apply_policy_overrides(dst, policy_override)
        config.policy_by_type[ft] = dst

    if overrides.apply_changes is not None:
        config.apply_changes = overrides.apply_changes

    # Explicit file inputs replace any previously resolved file list.
    if overrides.files is not None:
        raw_files: list[str] = overrides.files
        empties: list[str] = [s for s in raw_files if not s]
        if empties:
            config.diagnostics.add_warning(
                f"Ignoring empty string entries in override files: {empties!r}"
            )
        # Keep only the non-empty entries
        config.files = [s for s in raw_files if s]
        if config.files:
            config.stdin_mode = False

    # CLI/API include/exclude sources are normalized against the invocation CWD.
    cwd: Path = Path.cwd().resolve()

    # Glob patterns: include_patterns / exclude_patterns (extend)
    if overrides.include_patterns is not None:
        vals: list[str] = [s for s in overrides.include_patterns if s]
        if vals:
            config.include_patterns.extend(vals)

    if overrides.exclude_patterns is not None:
        vals = [s for s in overrides.exclude_patterns if s]
        if vals:
            config.exclude_patterns.extend(vals)

    # Path-to-file options: include_from, exclude_from, files_from (validate list[str])
    if overrides.include_from is not None:
        vals = [s for s in overrides.include_from if s]
        extend_pattern_sources(
            config.include_from,
            vals,
            pattern_source_from_cwd,
            "override include_from",
            cwd,
        )
    if overrides.exclude_from is not None:
        vals = [s for s in overrides.exclude_from if s]
        extend_pattern_sources(
            config.exclude_from,
            vals,
            pattern_source_from_cwd,
            "override exclude_from",
            cwd,
        )

    if overrides.files_from is not None:
        vals = [s for s in overrides.files_from if s]
        extend_pattern_sources(
            config.files_from,
            vals,
            pattern_source_from_cwd,
            "override files_from",
            cwd,
        )

    # Header-building overrides apply only when explicitly provided.

    # relative_to: string or None, only override if non-empty string (not just whitespace)
    if overrides.relative_to and (rel_str := overrides.relative_to.strip()):
        config.relative_to_raw = rel_str
        config.relative_to = Path(rel_str).resolve()

    # align_fields: checked bool
    if overrides.align_fields is not None:
        config.align_fields = overrides.align_fields

    # Absent override values intentionally preserve whatever came from layered
    # config discovery / TOML resolution.

    # include_file_types / exclude_file_types: set of strings, only override if present
    if overrides.include_file_types:
        # Only override when the user actually passes a value
        # TODO decide whether `()` clears the property or whether we always extend the set
        filtered: list[str] = [s for s in overrides.include_file_types if s]  # drop empty strings
        deduped: set[str] = set(filtered)
        config.include_file_types = deduped
        dup_count: int = len(filtered) - len(deduped)
        if dup_count:
            config.diagnostics.add_info(
                f"Ignored {dup_count} duplicate values for override include_file_types"
            )

    if overrides.exclude_file_types:
        # Only override when the user actually passes a value
        # TODO decide whether `()` clears the property or whether we always extend the set
        filtered: list[str] = [s for s in overrides.exclude_file_types if s]  # drop empty strings
        deduped: set[str] = set(filtered)
        config.exclude_file_types = deduped
        dup_count: int = len(filtered) - len(deduped)
        if dup_count:
            config.diagnostics.add_info(
                f"Ignored {dup_count} duplicate values for override exclude_file_types"
            )

    if overrides.header_fields is not None:
        config.header_fields = overrides.header_fields

    if overrides.field_values is not None:
        config.field_values = overrides.field_values

    # STDIN mode flags must preserve explicit False as an override, so apply
    # them only when the caller provided a concrete value.
    if overrides.stdin_mode is not None:
        # honor False explicitly
        config.stdin_mode = overrides.stdin_mode

    if overrides.stdin_filename:
        # `stdin_filename` is only meaningful when non-empty.
        config.stdin_filename = overrides.stdin_filename

    # Write mode logic: OutputTarget and FileWriteStrategy
    if overrides.output_target is not None:
        config.output_target = overrides.output_target

    if overrides.file_write_strategy is not None:
        config.file_write_strategy = overrides.file_write_strategy

    logger.debug("Patched MutableConfig: %s", config)
    logger.info("Applied argument mapping overrides to MutableConfig")
    logger.debug("Finalized _mode=%s files=%s", config.stdin_mode, config.files)

    return config
