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
from topmark.config.types import PatternGroup
from topmark.constants import CLI_OVERRIDE_STR
from topmark.core.logging import get_logger

if TYPE_CHECKING:
    from topmark.config.model import MutableConfig
    from topmark.config.policy import EmptyInsertMode
    from topmark.config.policy import HeaderMutationMode
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

    Attributes:
        config_origin: provenance marker or path
        config_base: real filesystem base for relative patterns and sources
        strict_config_checking: If True, enforce strict config checking
            (fail on warnings and errors).
        policy: Global, resolved, immutable runtime policy (plain booleans),
            applied after discovery.
        policy_by_type: Per-file-type resolved policy overrides
            (plain booleans), applied after discovery.
        files: List of files to process.
        files_from: Paths to files that list newline-delimited candidate
            file paths to add before filtering.
        include_from: Files containing include patterns.
        exclude_from: Files containing exclude patterns.
        include_patterns: Glob patterns to include.
        exclude_patterns: Glob patterns to exclude.
        include_file_types: Whitelist of file type identifiers to restrict
            file discovery.
        exclude_file_types: Blacklist of file type identifiers to exclude from
            file discovery.
        header_fields: List of header fields from the [header] section.
        field_values: Mapping of field names to their string values
            from [fields].
        align_fields: Whether to align fields, from [formatting].
        relative_to: Base path used only for header metadata (e.g., file_relpath).
            Note: Glob expansion and filtering are resolved relative to their declaring source
            (config file dir or CWD for CLI), not relative_to.
    """

    # Config-related options
    config_origin: Path | str = CLI_OVERRIDE_STR
    config_base: Path = field(default_factory=lambda: Path.cwd().resolve())
    strict_config_checking: bool | None = None

    # Policy (global and overrides by file type)
    policy: PolicyOverrides = field(default_factory=PolicyOverrides)
    policy_by_type: dict[str, PolicyOverrides] = field(default_factory=lambda: {})

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

    This helper updates an already-resolved `MutableConfig` with the final highest-precedence
    override layer. It intentionally does **not** handle config discovery concerns such as
    `--no-config` or `--config`; those belong to
    [`topmark.config.io.resolution`][topmark.config.io.resolution].

    Args:
        config: Mutable config draft to mutate in place.
        overrides: Structured override values coming from CLI/API.

    Returns:
        The same `MutableConfig` instance after in-place mutation.

    Notes:
        - Path-to-file options (`--include-from`, `--exclude-from`, `--files-from`) are normalized
          against `overrides.config_base`, which defaults to the invocation working directory
          but may differ for API callers.
        - `relative_to` influences only header metadata generation. It does not change how
          config-declared glob sources are interpreted.
        - Provenance information is appended to `overrides.config_origin` so downstream views
          can show that a highest-precedence override layer was applied.
        - Execution-only runtime intent (apply mode, STDIN routing, output target, file write
          strategy, pruning) is out of scope here and must be handled separately via
          [`topmark.runtime.model.RunOptions`][topmark.runtime.model.RunOptions].
    """
    # strict_config_checking
    if overrides.strict_config_checking is not None:
        config.strict_config_checking = overrides.strict_config_checking

    # Record that a highest-precedence CLI/API override layer was applied.
    # This is provenance-only; explicit `--config` files are merged earlier by
    # the resolution layer.
    if config.config_files:
        config.config_files.append(overrides.config_origin)
    else:
        config.config_files = [overrides.config_origin]

    # Note: CLI config paths are already merged elsewhere
    # so we don't extend config.config_files here.

    # policy always exists via default_factory
    _apply_policy_overrides(config.policy, overrides.policy)

    for ft, policy_override in overrides.policy_by_type.items():
        dst: MutablePolicy = config.policy_by_type.get(ft) or MutablePolicy()
        _apply_policy_overrides(dst, policy_override)
        config.policy_by_type[ft] = dst

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

    # CLI/API override paths and pattern groups are interpreted against the override base.
    base_dir: Path = overrides.config_base.resolve()

    if overrides.include_patterns is not None:
        include_patterns: tuple[str, ...] = tuple(s for s in overrides.include_patterns if s)
        if include_patterns:
            config.include_pattern_groups = [
                PatternGroup(
                    patterns=include_patterns,
                    base=base_dir,
                )
            ]
        else:
            config.include_pattern_groups = []

    if overrides.exclude_patterns is not None:
        exclude_patterns: tuple[str, ...] = tuple(s for s in overrides.exclude_patterns if s)
        if exclude_patterns:
            config.exclude_pattern_groups = [
                PatternGroup(
                    patterns=exclude_patterns,
                    base=base_dir,
                )
            ]
        else:
            config.exclude_pattern_groups = []

    # Path-to-file options: include_from, exclude_from, files_from (validate list[str])
    # Strategy: replace-or-clear
    if overrides.include_from is not None:
        config.include_from = []
        vals: list[str] = [s for s in overrides.include_from if s]
        extend_pattern_sources(
            vals,
            dst=config.include_from,
            mk=pattern_source_from_cwd,
            kind="override include_from",
            base=base_dir,
        )
    if overrides.exclude_from is not None:
        config.exclude_from = []
        vals = [s for s in overrides.exclude_from if s]
        extend_pattern_sources(
            vals,
            dst=config.exclude_from,
            mk=pattern_source_from_cwd,
            kind="override exclude_from",
            base=base_dir,
        )

    if overrides.files_from is not None:
        config.files_from = []
        vals = [s for s in overrides.files_from if s]
        extend_pattern_sources(
            vals,
            dst=config.files_from,
            mk=pattern_source_from_cwd,
            kind="override files_from",
            base=base_dir,
        )

    # Header-building overrides apply only when explicitly provided.

    # relative_to: string or None, only override if non-empty string (not just whitespace)
    if overrides.relative_to and (rel_str := overrides.relative_to.strip()):
        config.relative_to_raw = rel_str
        rel_path = Path(rel_str)
        config.relative_to = (
            rel_path.resolve() if rel_path.is_absolute() else (base_dir / rel_path).resolve()
        )

    # align_fields: checked bool
    if overrides.align_fields is not None:
        config.align_fields = overrides.align_fields

    # Absent override values intentionally preserve whatever came from layered
    # config discovery / TOML resolution.

    # include_file_types / exclude_file_types: set of strings, only override if present
    if overrides.include_file_types is not None:
        # Only override when the user actually passes a value; `()` clears the property
        filtered: list[str] = [s for s in overrides.include_file_types if s]  # drop empty strings
        deduped: set[str] = set(filtered)
        config.include_file_types = deduped
        dup_count: int = len(filtered) - len(deduped)
        if dup_count:
            config.diagnostics.add_info(
                f"Ignored {dup_count} duplicate values for override include_file_types"
            )

    if overrides.exclude_file_types is not None:
        # Only override when the user actually passes a value; `()` clears the property
        filtered: list[str] = [s for s in overrides.exclude_file_types if s]  # drop empty strings
        deduped: set[str] = set(filtered)
        config.exclude_file_types = deduped
        dup_count: int = len(filtered) - len(deduped)
        if dup_count:
            config.diagnostics.add_info(
                f"Ignored {dup_count} duplicate values for override exclude_file_types"
            )

    # NOTE: header_fields and field_values still bypass any provenance-aware normalization
    if overrides.header_fields is not None:
        config.header_fields = overrides.header_fields
    if overrides.field_values is not None:
        config.field_values = overrides.field_values

    logger.debug("Patched MutableConfig: %s", config)
    logger.info("Applied argument mapping overrides to MutableConfig")
    logger.debug("Finalized override application for files=%s", config.files)

    return config
