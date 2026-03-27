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

from topmark.config.keys import Toml

if TYPE_CHECKING:
    from topmark.config.io.types import TomlTable
    from topmark.config.io.types import TomlValue
    from topmark.config.model import Config


def config_to_toml_dict(config: Config, *, include_files: bool = False) -> TomlTable:
    """Convert this immutable Config into a TOML-serializable dict.

    Args:
        config: Config object to serialize to TOML dict.
        include_files: Whether to include the `files` list in the output.
            Defaults to False to avoid spamming the output with potentially
            large file lists. Set to True for full export.

    Returns:
        The TOML-serializable dict representing the Config

    Note:
        Export-only convenience for documentation/snapshots. Parsing and
        loading live on the **mutable** side (see `MutableConfig` and
        [`topmark.config.io`][topmark.config.io]).
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

    # Files to process
    files_tbl: TomlTable = {
        Toml.KEY_INCLUDE_FILE_TYPES: list(config.include_file_types),
        Toml.KEY_EXCLUDE_FILE_TYPES: list(config.exclude_file_types),
        Toml.KEY_FILES_FROM: [str(ps.path) for ps in config.files_from],
        Toml.KEY_INCLUDE_FROM: [str(ps.path) for ps in config.include_from],
        Toml.KEY_EXCLUDE_FROM: [str(ps.path) for ps in config.exclude_from],
        Toml.KEY_INCLUDE_PATTERNS: list(config.include_patterns),
        Toml.KEY_EXCLUDE_PATTERNS: list(config.exclude_patterns),
        Toml.KEY_CONFIG_FILES: [
            str(p) if isinstance(p, Path) else str(p) for p in config.config_files
        ],
    }

    # Writer settings
    writer_tbl: TomlTable = {
        # self.output_target is an Enum type
        Toml.KEY_TARGET: config.output_target.value if config.output_target else None,
        Toml.KEY_STRATEGY: writer_strategy,
    }

    # Policy serialization (global and per-type)
    policy_tbl: TomlTable = {
        Toml.KEY_POLICY_CHECK_ADD_ONLY: config.policy.add_only,
        Toml.KEY_POLICY_CHECK_UPDATE_ONLY: config.policy.update_only,
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
                Toml.KEY_POLICY_CHECK_ADD_ONLY: p.add_only,
                Toml.KEY_POLICY_CHECK_UPDATE_ONLY: p.update_only,
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
        files_value: list[TomlValue] = [str(path) for path in config.files]
        files_tbl[Toml.KEY_FILES] = files_value

    return toml_dict
