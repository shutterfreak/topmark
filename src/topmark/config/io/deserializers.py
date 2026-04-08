# topmark:header:start
#
#   project      : TopMark
#   file         : deserializers.py
#   file_relpath : src/topmark/config/io/deserializers.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Deserialize TOML-backed configuration data into `MutableConfig` drafts.

This module contains the TOML-to-model parsing layer for TopMark configuration.

Responsibilities:
    - parse already-loaded TOML mappings into `MutableConfig`
    - validate section/key shapes and attach config diagnostics
    - normalize config-local filesystem references against the source TOML file
    - deserialize layered config sections such as policy, files, header, and formatting
    - deserialize built-in and caller-provided TopMark TOML tables into mutable draft configs

Design notes:
    - This module is intentionally separate from `topmark.config.model`.
      The model layer defines configuration data structures and merge behavior,
      while this module handles TOML-aware deserialization and normalization.
    - The result of deserialization is a `MutableConfig`, not a frozen `Config`.
      Callers may still merge, override, sanitize, and finally freeze the draft.
    - Execution-only runtime intent is intentionally out of scope here and is
      handled separately via [`topmark.runtime.model.RunOptions`][topmark.runtime.model.RunOptions].
    - Parsing is diagnostics-friendly: invalid shapes/types are reported through
      the draft config's diagnostic log instead of failing fast on first issue.

Typical entry points:
    - `mutable_config_from_layered_toml_table()`
    - `mutable_config_from_defaults()`
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Final

from topmark.config.model import MutableConfig
from topmark.config.paths import abs_path_from
from topmark.config.paths import extend_pattern_sources
from topmark.config.paths import pattern_source_from_config
from topmark.config.paths import pattern_source_from_cwd
from topmark.config.policy import EmptyInsertMode
from topmark.config.policy import HeaderMutationMode
from topmark.config.policy import MutablePolicy
from topmark.config.types import PatternGroup
from topmark.core.logging import get_logger
from topmark.toml.defaults import build_default_topmark_toml_table
from topmark.toml.getters import get_bool_value_or_none_checked
from topmark.toml.getters import get_enum_value_checked
from topmark.toml.getters import get_string_list_value_checked
from topmark.toml.getters import get_string_value_checked
from topmark.toml.getters import get_table_value
from topmark.toml.keys import Toml
from topmark.toml.typing_guards import as_toml_table_map
from topmark.toml.typing_guards import toml_table_from_mapping

if TYPE_CHECKING:
    from collections.abc import Mapping

    from topmark.core.logging import TopmarkLogger
    from topmark.toml.types import TomlTable
    from topmark.toml.types import TomlTableMap
    from topmark.toml.types import TomlValue


logger: TopmarkLogger = get_logger(__name__)


# ------------------ Extracted TOML table bundles  ------------------


@dataclass(frozen=True, slots=True)
class ExtractedLayeredTomlTables:
    """Structured bundle of well-known layered TOML subtables.

    This keeps the extraction/parsing flow self-documenting and avoids fragile
    position-based tuple unpacking when deserializing a TopMark TOML table into
    a `MutableConfig` draft.
    """

    field_tbl: TomlTable
    header_tbl: TomlTable
    formatting_tbl: TomlTable
    files_tbl: TomlTable
    policy_tbl: TomlTable
    policy_by_type_tbl: TomlTableMap


def mutable_config_from_layered_toml_table(
    data: TomlTable,
    config_file: Path | None = None,
    use_defaults: bool = False,
) -> MutableConfig:
    """Create a draft config from a layered TopMark TOML fragment.

    - Path-to-file entries declared in the config are normalized to absolute paths
      using the *config file's* directory (config-local base).
    - Glob strings are kept as-is (evaluated later against `relative_to`).
    - `[fields]` is a free-form mapping of field_name -> field_value; only names listed
      in `[header].fields` are rendered later by `BuilderStep`.

    Args:
        data: The parsed TOML data as a dictionary.
        config_file: Optional path to the source TOML file.
        use_defaults: Whether to treat this data as default config (affects behavior).

    Returns:
        The resulting MutableConfig instance.
    """
    tool_tbl: TomlTable = data  # top-level tool configuration dictionary

    # Start from a fresh draft early so we can attach diagnostics while parsing.
    draft: MutableConfig = MutableConfig()

    # Config file's directory for relative path resolution
    cfg_dir: Path | None = config_file.parent.resolve() if config_file else None

    # ------------------- Policy pre-validation helpers -------------------
    def _prevalidate_policy_table(
        tbl: TomlTable,
        *,
        where: str,
    ) -> None:
        """Pre-validate a policy TOML table and attach diagnostics.

        This validates *shape* only so `MutablePolicy.from_toml_table()` can
        stay focused on parsing/merging. Boolean policy fields are checked as
        booleans, while `empty_insert_mode` is checked as a string token.
        """
        _ = get_enum_value_checked(
            tbl,
            Toml.KEY_POLICY_HEADER_MUTATION_MODE,
            enum_cls=HeaderMutationMode,
            where=where,
            diagnostics=draft.diagnostics,
        )
        _ = get_bool_value_or_none_checked(
            tbl,
            Toml.KEY_POLICY_ALLOW_HEADER_IN_EMPTIES,
            where=where,
            diagnostics=draft.diagnostics,
        )
        _ = get_enum_value_checked(
            tbl,
            Toml.KEY_POLICY_EMPTIES_INSERT_MODE,
            enum_cls=EmptyInsertMode,
            where=where,
            diagnostics=draft.diagnostics,
        )
        _ = get_bool_value_or_none_checked(
            tbl,
            Toml.KEY_POLICY_ALLOW_EMPTY_HEADER,
            where=where,
            diagnostics=draft.diagnostics,
        )
        _ = get_bool_value_or_none_checked(
            tbl,
            Toml.KEY_POLICY_ALLOW_REFLOW,
            where=where,
            diagnostics=draft.diagnostics,
        )
        _ = get_bool_value_or_none_checked(
            tbl,
            Toml.KEY_POLICY_ALLOW_CONTENT_PROBE,
            where=where,
            diagnostics=draft.diagnostics,
        )

    def _parse_policy_tables(
        *,
        policy_tbl: TomlTable,
        policy_by_type_tbl: TomlTableMap,
    ) -> None:
        """Parse global and per-type policy tables into the draft config."""
        where_policy: Final[str] = f"[{Toml.SECTION_POLICY}]"
        _prevalidate_policy_table(policy_tbl, where=where_policy)
        draft.policy = MutablePolicy.from_toml_table(policy_tbl)

        for ft, tbl in policy_by_type_tbl.items():
            where: str = f"[{Toml.SECTION_POLICY_BY_TYPE}.{ft}]"
            _prevalidate_policy_table(tbl, where=where)

        draft.policy_by_type = {
            str(ft): MutablePolicy.from_toml_table(tbl) for ft, tbl in policy_by_type_tbl.items()
        }

    def _parse_files_table(files_tbl: TomlTable) -> None:
        """Parse `[files]` settings into the draft config."""
        where_files: Final[str] = f"[{Toml.SECTION_FILES}]"

        # ---- files: normalize to absolute paths against the config file dir (when known) ----
        raw_files: list[str] = get_string_list_value_checked(
            files_tbl,
            Toml.KEY_FILES,
            where=where_files,
            diagnostics=draft.diagnostics,
        )
        if raw_files:
            if cfg_dir is not None:
                for f in raw_files:
                    absf: Path = abs_path_from(cfg_dir, raw=f)
                    draft.files.append(str(absf))
                    logger.debug("Normalized config files entry against %s: %s", cfg_dir, absf)
            else:
                draft.files.extend(raw_files)

        # ---- include_from / exclude_from / files_from: convert to PatternSource now ----
        def _normalize_sources(key: str) -> None:
            # List-valued keys under [files] (include_from/exclude_from/files_from) should be
            # a list of strings. Wrong types are treated as empty; mixed types drop non-strings.
            # Enforce "list of strings" for field selection in TOML:
            vals: list[str] = get_string_list_value_checked(
                files_tbl,
                key,
                where=where_files,
                diagnostics=draft.diagnostics,
            )
            if not vals:
                return

            if cfg_dir is not None:
                extend_pattern_sources(
                    vals,
                    dst=getattr(draft, key),
                    mk=pattern_source_from_config,
                    kind=f"config {where_files}.{key}",
                    base=cfg_dir,
                )
            else:
                # Rare fallback: without a config file path, use CWD to avoid losing info
                extend_pattern_sources(
                    vals,
                    dst=getattr(draft, key),
                    mk=pattern_source_from_cwd,
                    kind=f"config {where_files}.{key}",
                    base=Path.cwd().resolve(),
                )

        for _k in (Toml.KEY_INCLUDE_FROM, Toml.KEY_EXCLUDE_FROM, Toml.KEY_FILES_FROM):
            _normalize_sources(_k)

        # ---- glob arrays remain raw strings, but carry their declaring base ----
        # List-valued glob keys under [files] should contain strings. Wrong types are treated
        # as empty; mixed types drop non-strings with a warning + diagnostic.

        base: Path = cfg_dir if cfg_dir is not None else Path.cwd().resolve()

        include_patterns: list[str] = get_string_list_value_checked(
            files_tbl,
            Toml.KEY_INCLUDE_PATTERNS,
            where=where_files,
            diagnostics=draft.diagnostics,
        )
        if include_patterns:
            draft.include_pattern_groups.append(
                PatternGroup(
                    patterns=tuple(include_patterns),
                    base=base,
                )
            )

        exclude_patterns: list[str] = get_string_list_value_checked(
            files_tbl,
            Toml.KEY_EXCLUDE_PATTERNS,
            where=where_files,
            diagnostics=draft.diagnostics,
        )
        if exclude_patterns:
            draft.exclude_pattern_groups.append(
                PatternGroup(
                    patterns=tuple(exclude_patterns),
                    base=base,
                )
            )

        include_pattern_groups_tbl: list[TomlTable] = []
        include_pattern_groups_raw: TomlValue | None = files_tbl.get(
            Toml.KEY_INCLUDE_PATTERN_GROUPS
        )
        if isinstance(include_pattern_groups_raw, list):
            include_pattern_groups_tbl = [
                item for item in include_pattern_groups_raw if isinstance(item, dict)
            ]
        for item in include_pattern_groups_tbl:
            base_raw: str = get_string_value_checked(
                item,
                Toml.KEY_BASE,
                where=f"{where_files}.{Toml.KEY_INCLUDE_PATTERN_GROUPS}",
                diagnostics=draft.diagnostics,
                default="",
            )
            patterns: list[str] = get_string_list_value_checked(
                item,
                Toml.KEY_PATTERNS,
                where=f"{where_files}.{Toml.KEY_INCLUDE_PATTERN_GROUPS}",
                diagnostics=draft.diagnostics,
            )
            if base_raw and patterns:
                draft.include_pattern_groups.append(
                    PatternGroup(
                        patterns=tuple(patterns),
                        base=Path(base_raw).resolve(),
                    )
                )

        exclude_pattern_groups_tbl: list[TomlTable] = []
        exclude_pattern_groups_raw: TomlValue | None = files_tbl.get(
            Toml.KEY_EXCLUDE_PATTERN_GROUPS
        )
        if isinstance(exclude_pattern_groups_raw, list):
            exclude_pattern_groups_tbl = [
                item for item in exclude_pattern_groups_raw if isinstance(item, dict)
            ]
        for item in exclude_pattern_groups_tbl:
            base_raw = get_string_value_checked(
                item,
                Toml.KEY_BASE,
                where=f"{where_files}.{Toml.KEY_EXCLUDE_PATTERN_GROUPS}",
                diagnostics=draft.diagnostics,
                default="",
            )
            patterns: list[str] = get_string_list_value_checked(
                item,
                Toml.KEY_PATTERNS,
                where=f"{where_files}.{Toml.KEY_EXCLUDE_PATTERN_GROUPS}",
                diagnostics=draft.diagnostics,
            )
            if base_raw and patterns:
                draft.exclude_pattern_groups.append(
                    PatternGroup(
                        patterns=tuple(patterns),
                        base=Path(base_raw).resolve(),
                    )
                )

        # Coerce `[fields]` values to strings (the table is user-defined and may include
        # unused keys). Unsupported types are ignored with a warning.
        # ---- File-related settings ----

        # include_file_types
        include_file_types: list[str] = get_string_list_value_checked(
            files_tbl,
            Toml.KEY_INCLUDE_FILE_TYPES,
            where=where_files,
            diagnostics=draft.diagnostics,
        )
        draft.include_file_types = set(include_file_types)

        if include_file_types and len(include_file_types) != len(draft.include_file_types):
            draft.diagnostics.add_warning(
                "Duplicate included file types found in config "
                f"(key: {Toml.KEY_INCLUDE_FILE_TYPES}): "
                ", ".join(include_file_types),
            )

        # exclude_file_types
        exclude_file_types: list[str] = get_string_list_value_checked(
            files_tbl,
            Toml.KEY_EXCLUDE_FILE_TYPES,
            where=where_files,
            diagnostics=draft.diagnostics,
        )
        draft.exclude_file_types = set(exclude_file_types)

        if exclude_file_types and len(exclude_file_types) != len(draft.exclude_file_types):
            draft.diagnostics.add_warning(
                "Duplicate excluded file types found in config "
                f"(key: {Toml.KEY_EXCLUDE_FILE_TYPES}): "
                ", ".join(exclude_file_types),
            )

    def _parse_header_and_fields_tables(
        *,
        header_tbl: TomlTable,
        field_tbl: TomlTable,
    ) -> None:
        """Parse `[header]` and `[fields]` settings into the draft config."""
        field_values: dict[str, str] = {}
        for k, v in field_tbl.items():
            if isinstance(v, str | int | float | bool):
                field_values[k] = str(v)
            else:
                # [fields] is a free-form table; include the TOML location for consistency.
                loc: str = f"[{Toml.SECTION_FIELDS}].{k}"
                draft.diagnostics.add_warning(f"Ignoring unsupported field value for {loc}: {v}")
        draft.field_values = field_values

        # `[header].fields`: ordered list of field names to render (built-ins and/or
        # keys from `[fields]`).
        #
        # Enforce "list of strings" for header field selection in TOML:
        draft.header_fields = get_string_list_value_checked(
            header_tbl,
            Toml.KEY_FIELDS,
            where=f"[{Toml.SECTION_HEADER}]",
            diagnostics=draft.diagnostics,
        )

        # NOTE: If the user did not specify any header fields, this results in an empty header.
        # Fallback: if no explicit header field order is provided, use the keys of
        # the field_values table in their declared order. This preserves intuitive
        # behavior (headers render when values are present).
        if not draft.header_fields:
            draft.diagnostics.add_warning(
                f"{Toml.SECTION_HEADER}.{Toml.KEY_FIELDS} is not set (empty TopMark header)"
            )

        # Parse relative_to path if present, resolve to absolute path
        draft.relative_to_raw = get_string_value_checked(
            header_tbl,
            Toml.KEY_RELATIVE_TO,
            where=f"[{Toml.SECTION_HEADER}]",
            diagnostics=draft.diagnostics,
            default="",
        )
        if draft.relative_to_raw:
            p = Path(draft.relative_to_raw)
            if p.is_absolute():
                draft.relative_to = p.resolve()
            else:
                if cfg_dir is not None:
                    # Resolve relative-to against the CONFIG FILE’s directory
                    draft.relative_to = (cfg_dir / p).resolve()
                else:
                    # Defaults or synthetic dicts: don’t bind to CWD; let the resolver
                    # pick the project root later.
                    draft.relative_to = None
        else:
            draft.relative_to = None

    def _parse_formatting_table(formatting_tbl: TomlTable) -> None:
        """Parse `[formatting]` settings into the draft config."""
        where_fmt: Final[str] = f"[{Toml.SECTION_FORMATTING}]"
        # align_fields --  NOTE: do not set a default value if not set
        draft.align_fields = get_bool_value_or_none_checked(
            formatting_tbl,
            Toml.KEY_ALIGN_FIELDS,
            where=where_fmt,
            diagnostics=draft.diagnostics,
        )

    def _extract_toml_tables(
        tool_tbl: TomlTable,
    ) -> ExtractedLayeredTomlTables:
        """Extract well-known TOML subtables into a typed bundle."""
        # Extract sub-tables for specific config sections; fallback to empty dicts.
        #
        # NOTE: `[fields]` is an *arbitrary* user-defined mapping of name -> value.
        #       It may contain keys that are not rendered. The rendered/ordered subset
        #       is controlled by `[header].fields` and applied later by
        #       `topmark.pipeline.steps.builder.BuilderStep`.
        field_tbl: TomlTable = get_table_value(tool_tbl, Toml.SECTION_FIELDS)
        logger.trace("TOML [%s]: %s", Toml.SECTION_FIELDS, field_tbl)

        header_tbl: TomlTable = get_table_value(tool_tbl, Toml.SECTION_HEADER)
        logger.trace("TOML [%s]: %s", Toml.SECTION_HEADER, header_tbl)

        formatting_tbl: TomlTable = get_table_value(tool_tbl, Toml.SECTION_FORMATTING)
        logger.trace("TOML [%s]: %s", Toml.SECTION_FORMATTING, formatting_tbl)

        files_tbl: TomlTable = get_table_value(tool_tbl, Toml.SECTION_FILES)
        logger.trace("TOML [%s]: %s", Toml.SECTION_FILES, files_tbl)

        policy_tbl: TomlTable = get_table_value(tool_tbl, Toml.SECTION_POLICY)
        logger.trace("TOML [%s]: %s", Toml.SECTION_POLICY, policy_tbl)

        policy_by_type_raw: TomlTable = get_table_value(tool_tbl, Toml.SECTION_POLICY_BY_TYPE)
        policy_by_type_tbl: TomlTableMap = as_toml_table_map(policy_by_type_raw)
        logger.trace("TOML [%s]: %s", Toml.SECTION_POLICY_BY_TYPE, policy_by_type_tbl)

        return ExtractedLayeredTomlTables(
            field_tbl=field_tbl,
            header_tbl=header_tbl,
            formatting_tbl=formatting_tbl,
            files_tbl=files_tbl,
            policy_tbl=policy_tbl,
            policy_by_type_tbl=policy_by_type_tbl,
        )

    def _initialize_config_file_provenance() -> None:
        """Seed `draft.config_files` from the source TOML path, if any."""
        # ---- config_files: normalize to absolute paths if possible ----
        config_files: tuple[list[Path]] = ([config_file] if config_file else [],)
        draft.config_files = [str(p) for p in config_files[0]] if config_files[0] else []

    # Extract sub-tables for specific config sections; fallback to empty dicts.
    #
    # NOTE: `[fields]` is an *arbitrary* user-defined mapping of name -> value.
    #       It may contain keys that are not rendered. The rendered/ordered subset
    #       is controlled by `[header].fields` and applied later by
    #       `topmark.pipeline.steps.builder.BuilderStep`.
    toml_tables: ExtractedLayeredTomlTables = _extract_toml_tables(tool_tbl)

    # ---- config_files: normalize to absolute paths if possible ----
    _initialize_config_file_provenance()

    # ---- Global / per-type policy ----
    _parse_policy_tables(
        policy_tbl=toml_tables.policy_tbl,
        policy_by_type_tbl=toml_tables.policy_by_type_tbl,
    )

    # ---- files: normalize to absolute paths against the config file dir (when known) ----
    _parse_files_table(toml_tables.files_tbl)

    # ---- header / fields ----
    _parse_header_and_fields_tables(
        header_tbl=toml_tables.header_tbl,
        field_tbl=toml_tables.field_tbl,
    )

    # ---- Header Formatting ----
    _parse_formatting_table(toml_tables.formatting_tbl)

    # ---- File-related settings ----

    return draft


def mutable_config_from_defaults() -> MutableConfig:
    """Load the built-in default TopMark TOML table into a mutable draft.

    Returns:
        A `MutableConfig` instance populated with default values.
    """
    default_toml_data: TomlTable = build_default_topmark_toml_table()

    # Note: `config_file` is set to None because this is a package resource,
    # not a user-specified filesystem path.
    return mutable_config_from_layered_toml_table(
        default_toml_data,
        config_file=None,
        use_defaults=True,  # We ONLY include defaults when loading from defaults!
    )


def mutable_config_from_mapping(data: Mapping[str, object]) -> MutableConfig:
    """Create a mutable config draft from a generic Python mapping.

    This helper is intended for API-facing configuration inputs that are already
    available as Python mappings rather than TOML documents read from disk.

    The accepted shape currently mirrors the TOML-backed config structure, so the
    implementation delegates to `mutable_config_from_layered_toml_table()` after copying
    the input into a plain dictionary. The separate helper keeps the public/API
    coercion boundary explicit and avoids treating generic mappings as if they
    were inherently TOML documents.

    Args:
        data: Generic mapping containing configuration data.

    Returns:
        A mutable configuration draft parsed from the supplied mapping.

    Notes:
        - This helper is conceptually distinct from TOML deserialization even
          though the current mapping shape matches the TOML-backed structure.
        - The mapping is copied to a plain `dict` before delegation so parsing
          code can work with a mutable concrete mapping type.
        - If the API-facing config shape later diverges from raw TOML structure,
          this helper is the right place to absorb that change without affecting
          TOML loaders.
    """
    # Current API mapping shape mirrors the TOML-backed config structure.
    # Keep the API-facing coercion boundary explicit here so callers do not need
    # to route generic mappings through a TOML-named helper directly.
    toml_data: TomlTable = toml_table_from_mapping(data)
    return mutable_config_from_layered_toml_table(toml_data)
