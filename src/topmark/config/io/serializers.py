# topmark:header:start
#
#   project      : TopMark
#   file         : serializers.py
#   file_relpath : src/topmark/config/io/serializers.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Serialize TopMark configuration objects to TOML-compatible structures.

This module provides helpers to convert immutable `Config` instances into
TOML-serializable dictionaries for export, debugging, or documentation.

TOML has no `null` value, so `None` entries are stripped during rendering.

Responsibilities:
    - convert `Config` into TOML-shaped dictionaries
    - normalize enum values into stable string tokens
    - control inclusion of optional sections (e.g. large file lists)

Design notes:
    - This module is the inverse of
      [`topmark.config.io.deserializers`][topmark.config.io.deserializers].
    - Serialization is intentionally kept out of `config.model` to preserve
      a clean separation between data structures and I/O concerns.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from topmark.config.io.types import FilesSerializationMode
from topmark.config.keys import Toml
from topmark.core.errors import TomlRenderError
from topmark.core.logging import get_logger
from topmark.utils.file import rebase_glob_patterns

if TYPE_CHECKING:
    from collections.abc import Iterable

    from topmark.config.io.types import TomlTable
    from topmark.config.io.types import TomlValue
    from topmark.config.model import Config
    from topmark.core.logging import TopmarkLogger
    from topmark.diagnostic.model import DiagnosticLog

logger: TopmarkLogger = get_logger(__name__)


def _toml_string_list(values: Iterable[str]) -> list[TomlValue]:
    """Return a TOML-compatible list of strings.

    Pyright treats `list[str]` as incompatible with the recursive `TomlValue`
    alias because `list` is invariant. Building the list through the wider
    element type keeps the serializer strict-typing friendly without casts.
    """
    result: list[TomlValue] = list(values)
    return result


def _toml_table_list(values: Iterable[TomlTable]) -> list[TomlValue]:
    """Return a TOML-compatible list of TOML tables."""
    result: list[TomlValue] = list(values)
    return result


def config_to_toml_dict(
    config: Config,
    *,
    include_files: bool = False,
    files_serialization_mode: FilesSerializationMode = FilesSerializationMode.REBASED,
    diagnostics: DiagnosticLog | None = None,
) -> TomlTable:
    """Convert this immutable Config into a TOML-serializable dict.

    Args:
        config: The immutable Config instance to render as TOML.
        include_files: Whether to include the `files` list in the output.
            Defaults to False to avoid spamming the output with potentially
            large file lists. Set to True for full export.
        files_serialization_mode: How to serialize the `[files]` section when dumping.
            `REBASED` emits flattened `[files]` lists (include/exclude patterns and `*-from` path
            lists) rebased to the current working directory (CWD). `ORIGIN` emits structured
            provenance tables and omits the flattened lists.
        diagnostics: Optional diagnostic sink used to record export/preparation warnings
            (e.g., pattern rebasing failures). Warnings are always logged, and also added to
            diagnostics if provided.

    Returns:
        The TOML-serializable dict representing the Config.

    Raises:
        TomlRenderError: When an invalid files serialization mode was specified.

    Note:
        Export-only convenience for documentation/snapshots. Parsing and
        loading live on the **mutable** side (see `MutableConfig` and
        [`topmark.config.io`][topmark.config.io]).

        Pattern groups and pattern-source bases are serialized based on the value of
        `files_serialization_mode`. When set to `FilesSerializationMode.ORIGIN`, provenance-rich
        structures will be provided for serlaialization.
    """
    # Normalize writer strategy for TOML (map enum to a stable, config-friendly token)
    if config.file_write_strategy is None:
        writer_strategy: str | None = None
    else:
        # FileWriteStrategy names are things like "ATOMIC" / "INPLACE";
        # map them back to lowercase tokens used in config.
        writer_strategy = config.file_write_strategy.name.lower()

    # Header fields to render in headers
    fields_tbl: TomlTable = dict(config.field_values)

    # Header field definitions
    header_tbl: TomlTable = {
        Toml.KEY_FIELDS: list(config.header_fields),
    }
    if config.relative_to_raw:
        header_tbl[Toml.KEY_RELATIVE_TO] = config.relative_to_raw

    # Header formatting
    formatting_tbl: TomlTable = {
        Toml.KEY_ALIGN_FIELDS: config.align_fields,
    }

    # ---- Files ----

    # Deterministic ordering for file types
    include_file_types_sorted: list[TomlValue] = _toml_string_list(
        sorted(config.include_file_types)
    )
    exclude_file_types_sorted: list[TomlValue] = _toml_string_list(
        sorted(config.exclude_file_types)
    )

    # Build base files_tbl
    files_tbl: TomlTable = {
        Toml.KEY_INCLUDE_FILE_TYPES: include_file_types_sorted,
        Toml.KEY_EXCLUDE_FILE_TYPES: exclude_file_types_sorted,
        Toml.KEY_RELATIVE_TO: config.relative_to_raw,
        Toml.KEY_CONFIG_FILES: _toml_string_list(
            str(p) if isinstance(p, Path) else str(p) for p in config.config_files
        ),
    }
    if include_files and config.files:
        files_tbl[Toml.KEY_FILES] = _toml_string_list(config.files)

    # Patterns/Groups serialization
    if files_serialization_mode == FilesSerializationMode.REBASED:
        # Add files_from, include_from, exclude_from as flattened lists
        files_tbl[Toml.KEY_FILES_FROM] = _toml_string_list(str(ps.path) for ps in config.files_from)
        files_tbl[Toml.KEY_INCLUDE_FROM] = _toml_string_list(
            str(ps.path) for ps in config.include_from
        )
        files_tbl[Toml.KEY_EXCLUDE_FROM] = _toml_string_list(
            str(ps.path) for ps in config.exclude_from
        )

        # Flatten pattern groups to CWD, preserving group order

        cwd: Path = Path.cwd().resolve()
        include_patterns: list[str] = []
        exclude_patterns: list[str] = []

        # Process include/exclude pattern groups in order
        for group in config.include_pattern_groups:
            rebased, warns = rebase_glob_patterns(
                patterns=group.patterns,
                from_base=group.base,
                to_base=cwd,
            )
            include_patterns.extend(rebased)
            for w in warns:
                if diagnostics is not None:
                    diagnostics.add_warning(w)
                else:
                    logger.warning(w)
        for group in config.exclude_pattern_groups:
            rebased, warns = rebase_glob_patterns(
                patterns=group.patterns,
                from_base=group.base,
                to_base=cwd,
            )
            exclude_patterns.extend(rebased)
            for w in warns:
                if diagnostics is not None:
                    diagnostics.add_warning(w)
                else:
                    logger.warning(w)
        files_tbl[Toml.KEY_INCLUDE_PATTERNS] = _toml_string_list(include_patterns)
        files_tbl[Toml.KEY_EXCLUDE_PATTERNS] = _toml_string_list(exclude_patterns)
    elif files_serialization_mode == FilesSerializationMode.ORIGIN:
        # Omit flattened pattern/path lists, emit provenance-oriented tables
        files_tbl[Toml.KEY_INCLUDE_PATTERN_GROUPS] = _toml_table_list(
            {
                Toml.KEY_BASE: str(group.base),
                Toml.KEY_PATTERNS: _toml_string_list(group.patterns),
            }
            for group in config.include_pattern_groups
        )
        files_tbl[Toml.KEY_EXCLUDE_PATTERN_GROUPS] = _toml_table_list(
            {
                Toml.KEY_BASE: str(group.base),
                Toml.KEY_PATTERNS: _toml_string_list(group.patterns),
            }
            for group in config.exclude_pattern_groups
        )
        files_tbl[Toml.KEY_INCLUDE_FROM_SOURCES] = _toml_table_list(
            {
                Toml.KEY_BASE: str(ps.base),
                Toml.KEY_PATH: str(ps.path),
            }
            for ps in config.include_from
        )
        files_tbl[Toml.KEY_EXCLUDE_FROM_SOURCES] = _toml_table_list(
            {
                Toml.KEY_BASE: str(ps.base),
                Toml.KEY_PATH: str(ps.path),
            }
            for ps in config.exclude_from
        )
        files_tbl[Toml.KEY_FILES_FROM_SOURCES] = _toml_table_list(
            {
                Toml.KEY_BASE: str(ps.base),
                Toml.KEY_PATH: str(ps.path),
            }
            for ps in config.files_from
        )
    else:
        # Defensive guard
        raise TomlRenderError(
            message=f"Invalid files_serialization_mode: {files_serialization_mode!r}",
            details=("render_config_to_toml_dict",),
        )

    # Writer settings
    writer_tbl: TomlTable = {
        # self.output_target is an Enum type
        Toml.KEY_TARGET: config.output_target.value if config.output_target else None,
        Toml.KEY_STRATEGY: writer_strategy,
    }

    # Policy serialization (global and per-type)
    policy_tbl: TomlTable = {
        Toml.KEY_POLICY_HEADER_MUTATION_MODE: config.policy.header_mutation_mode.value,
        Toml.KEY_POLICY_ALLOW_HEADER_IN_EMPTIES: config.policy.allow_header_in_empty_files,
        Toml.KEY_POLICY_EMPTIES_INSERT_MODE: config.policy.empty_insert_mode.value,
        Toml.KEY_POLICY_ALLOW_EMPTY_HEADER: config.policy.render_empty_header_when_no_fields,
        Toml.KEY_POLICY_ALLOW_REFLOW: config.policy.allow_reflow,
        Toml.KEY_POLICY_ALLOW_CONTENT_PROBE: config.policy.allow_content_probe,
    }

    # Policy serialization (per-type)
    policy_by_type_tbl: TomlTable = {}
    if config.policy_by_type:
        policy_by_type_tbl: TomlTable = {
            ft: {
                Toml.KEY_POLICY_HEADER_MUTATION_MODE: p.header_mutation_mode.value,
                Toml.KEY_POLICY_ALLOW_HEADER_IN_EMPTIES: p.allow_header_in_empty_files,
                Toml.KEY_POLICY_EMPTIES_INSERT_MODE: p.empty_insert_mode.value,
                Toml.KEY_POLICY_ALLOW_EMPTY_HEADER: p.render_empty_header_when_no_fields,
                Toml.KEY_POLICY_ALLOW_REFLOW: p.allow_reflow,
                Toml.KEY_POLICY_ALLOW_CONTENT_PROBE: p.allow_content_probe,
            }
            for ft, p in config.policy_by_type.items()
        }

    # Assemble the TOML shape representing the confgiguration
    toml_dict: TomlTable = {
        Toml.SECTION_FIELDS: fields_tbl,
        Toml.SECTION_HEADER: header_tbl,
        Toml.SECTION_FORMATTING: formatting_tbl,
        Toml.SECTION_POLICY: policy_tbl,
        Toml.SECTION_WRITER: writer_tbl,
        Toml.SECTION_FILES: files_tbl,
    }

    # If defined, add the per-type policy
    if config.policy_by_type:
        toml_dict[Toml.SECTION_POLICY_BY_TYPE] = policy_by_type_tbl

    # Include files in TOML export
    if include_files and config.files:
        files_tbl[Toml.KEY_FILES] = _toml_string_list(str(path) for path in config.files)

    return toml_dict
