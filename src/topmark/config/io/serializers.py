# topmark:header:start
#
#   project      : TopMark
#   file         : serializers.py
#   file_relpath : src/topmark/config/io/serializers.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Serialize TopMark configuration objects to TopMark TOML tables.

This module provides helpers to convert immutable `Config` instances into
TopMark TOML-compatible tables for export, debugging, or documentation.

TOML has no `null` value, so `None` entries are stripped during rendering.

Responsibilities:
    - convert layered `Config` into TopMark TOML tables
    - normalize config values into stable TOML-compatible tokens
    - control inclusion of optional sections (for example large file lists)

Design notes:
    - This module is the inverse of
      [`topmark.config.io.deserializers`][topmark.config.io.deserializers].
    - Serialization is intentionally kept out of `config.model` to preserve
      a clean separation between data structures and I/O concerns.
    - Execution-only runtime intent is intentionally out of scope here and is
      modeled separately via [`topmark.runtime.model.RunOptions`][topmark.runtime.model.RunOptions].
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from topmark.core.errors import TomlRenderError
from topmark.core.logging import get_logger
from topmark.toml.enums import FilesSerializationMode
from topmark.toml.keys import Toml
from topmark.toml.utils import as_toml_string_list
from topmark.toml.utils import as_toml_table_list
from topmark.toml.utils import insert_if_present
from topmark.utils.file import rebase_glob_patterns

if TYPE_CHECKING:
    from topmark.config.model import Config
    from topmark.core.logging import TopmarkLogger
    from topmark.diagnostic.model import DiagnosticLog
    from topmark.toml.types import TomlTable
    from topmark.toml.types import TomlValue

logger: TopmarkLogger = get_logger(__name__)


def config_to_topmark_toml_table(
    config: Config,
    *,
    include_files: bool = False,
    files_serialization_mode: FilesSerializationMode = FilesSerializationMode.REBASED,
    diagnostics: DiagnosticLog | None = None,
) -> TomlTable:
    """Convert an immutable `Config` into a TopMark TOML table.

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
        The TopMark TOML table representing the supplied configuration.

    Raises:
        TomlRenderError: If an invalid files serialization mode is specified.

    Note:
        Export-only convenience for documentation and snapshots. Parsing and
        loading live on the mutable side (see `MutableConfig` and
        [`topmark.config.io.deserializers`][topmark.config.io.deserializers]).

        Pattern groups and pattern-source bases are serialized based on the value of
        `files_serialization_mode`. When set to `FilesSerializationMode.ORIGIN`, provenance-rich
        structures are emitted for serialization.
    """
    # Header fields to render in headers
    fields_tbl: TomlTable = dict(config.field_values)

    # Header field definitions
    header_tbl: TomlTable = {
        Toml.KEY_FIELDS: list(config.header_fields),
    }
    insert_if_present(
        header_tbl,
        Toml.KEY_RELATIVE_TO,
        config.relative_to_raw,
    )

    # Header formatting
    formatting_tbl: TomlTable = {}
    insert_if_present(
        formatting_tbl,
        Toml.KEY_ALIGN_FIELDS,
        config.align_fields,
    )

    # ---- Files ----

    # Deterministic ordering for file types
    include_file_types_sorted: list[TomlValue] = as_toml_string_list(
        sorted(config.include_file_types)
    )
    exclude_file_types_sorted: list[TomlValue] = as_toml_string_list(
        sorted(config.exclude_file_types)
    )

    # Build base files_tbl
    files_tbl: TomlTable = {
        Toml.KEY_INCLUDE_FILE_TYPES: include_file_types_sorted,
        Toml.KEY_EXCLUDE_FILE_TYPES: exclude_file_types_sorted,
        Toml.KEY_CONFIG_FILES: as_toml_string_list(
            str(p) if isinstance(p, Path) else str(p) for p in config.config_files
        ),
    }
    insert_if_present(
        files_tbl,
        Toml.KEY_RELATIVE_TO,
        config.relative_to_raw,
    )

    if include_files and config.files:
        insert_if_present(
            files_tbl,
            Toml.KEY_FILES,
            as_toml_string_list(config.files),
        )

    # Patterns/Groups serialization
    if files_serialization_mode == FilesSerializationMode.REBASED:
        # Add files_from, include_from, exclude_from as flattened lists
        files_tbl[Toml.KEY_FILES_FROM] = as_toml_string_list(
            str(ps.path) for ps in config.files_from
        )
        files_tbl[Toml.KEY_INCLUDE_FROM] = as_toml_string_list(
            str(ps.path) for ps in config.include_from
        )
        files_tbl[Toml.KEY_EXCLUDE_FROM] = as_toml_string_list(
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
        files_tbl[Toml.KEY_INCLUDE_PATTERNS] = as_toml_string_list(include_patterns)
        files_tbl[Toml.KEY_EXCLUDE_PATTERNS] = as_toml_string_list(exclude_patterns)
    elif files_serialization_mode == FilesSerializationMode.ORIGIN:
        # Omit flattened pattern/path lists, emit provenance-oriented tables
        files_tbl[Toml.KEY_INCLUDE_PATTERN_GROUPS] = as_toml_table_list(
            {
                Toml.KEY_BASE: str(group.base),
                Toml.KEY_PATTERNS: as_toml_string_list(group.patterns),
            }
            for group in config.include_pattern_groups
        )
        files_tbl[Toml.KEY_EXCLUDE_PATTERN_GROUPS] = as_toml_table_list(
            {
                Toml.KEY_BASE: str(group.base),
                Toml.KEY_PATTERNS: as_toml_string_list(group.patterns),
            }
            for group in config.exclude_pattern_groups
        )
        files_tbl[Toml.KEY_INCLUDE_FROM_SOURCES] = as_toml_table_list(
            {
                Toml.KEY_BASE: str(ps.base),
                Toml.KEY_PATH: str(ps.path),
            }
            for ps in config.include_from
        )
        files_tbl[Toml.KEY_EXCLUDE_FROM_SOURCES] = as_toml_table_list(
            {
                Toml.KEY_BASE: str(ps.base),
                Toml.KEY_PATH: str(ps.path),
            }
            for ps in config.exclude_from
        )
        files_tbl[Toml.KEY_FILES_FROM_SOURCES] = as_toml_table_list(
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

    # Assemble the TOML shape representing the configuration
    toml_dict: TomlTable = {
        Toml.SECTION_FIELDS: fields_tbl,
        Toml.SECTION_HEADER: header_tbl,
        Toml.SECTION_FORMATTING: formatting_tbl,
        Toml.SECTION_POLICY: policy_tbl,
        Toml.SECTION_FILES: files_tbl,
    }

    # If defined, add the per-type policy
    if config.policy_by_type:
        toml_dict[Toml.SECTION_POLICY_BY_TYPE] = policy_by_type_tbl

    return toml_dict
