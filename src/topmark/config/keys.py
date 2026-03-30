# topmark:header:start
#
#   project      : TopMark
#   file         : keys.py
#   file_relpath : src/topmark/config/keys.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Canonical TOML section and key names for TopMark configuration.

This module defines the authoritative string constants used when reading,
writing, and validating TopMark configuration from TOML sources
(``topmark.toml`` and ``[tool.topmark]`` in ``pyproject.toml``).

Centralizing TOML keys:
    - Avoids hard-coded strings scattered across the config layer
    - Ensures consistency between defaults, parsing, validation, and docs
    - Makes configuration schema changes explicit and reviewable

Design notes:
    - Keys defined here represent *external configuration API*.
    - Renaming or removing keys is a breaking change.
    - CLI keys and TOML keys are intentionally kept separate.
"""

from __future__ import annotations

from typing import Final


class Toml:
    """TOML section names and keys used by TopMark configuration.

    This file is the single source of truth for the external configuration schema.

    The constants in this namespace define TopMark’s external configuration
    schema as it appears in `topmark.toml` and in `[tool.topmark]` inside
    `pyproject.toml`.

    The ordering of constants mirrors `topmark-example.toml` to make it easy to
    audit schema changes and keep defaults/docs/parsing aligned.

    Notes:
        - Values must match user-facing TOML keys exactly.
        - Renaming or removing a key is a breaking change.
        - CLI keys are defined separately in [`topmark.cli.keys`][topmark.cli.keys].
    """

    # Root / discovery
    KEY_ROOT: Final[str] = "root"

    # Strict TOML config checking (fail on warnings)
    KEY_STRICT_CONFIG_CHECKING: Final[str] = "strict_config_checking"

    # [header]
    SECTION_HEADER: Final[str] = "header"

    KEY_FIELDS: Final[str] = "fields"
    KEY_RELATIVE_TO: Final[str] = "relative_to"

    # [fields]
    SECTION_FIELDS: Final[str] = "fields"

    # [formatting]
    SECTION_FORMATTING: Final[str] = "formatting"

    KEY_ALIGN_FIELDS: Final[str] = "align_fields"

    # [writer]
    SECTION_WRITER: Final[str] = "writer"

    # [writer] Output destination key ("file" or "stdout").
    KEY_TARGET: Final[str] = "target"
    KEY_STRATEGY: Final[str] = "strategy"

    # [policy] and [policy_by_type]
    SECTION_POLICY: Final[str] = "policy"
    SECTION_POLICY_BY_TYPE: Final[str] = "policy_by_type"

    KEY_POLICY_HEADER_MUTATION_MODE: Final[str] = "header_mutation_mode"
    KEY_POLICY_ALLOW_HEADER_IN_EMPTIES: Final[str] = "allow_header_in_empty_files"
    KEY_POLICY_EMPTIES_INSERT_MODE: Final[str] = "empty_insert_mode"
    KEY_POLICY_ALLOW_EMPTY_HEADER: Final[str] = "render_empty_header_when_no_fields"
    KEY_POLICY_ALLOW_REFLOW: Final[str] = "allow_reflow"
    KEY_POLICY_ALLOW_CONTENT_PROBE: Final[str] = "allow_content_probe"

    # [files]
    SECTION_FILES: Final[str] = "files"

    KEY_INCLUDE_FILE_TYPES: Final[str] = "include_file_types"
    KEY_EXCLUDE_FILE_TYPES: Final[str] = "exclude_file_types"
    KEY_INCLUDE_FROM: Final[str] = "include_from"
    KEY_EXCLUDE_FROM: Final[str] = "exclude_from"
    KEY_INCLUDE_PATTERNS: Final[str] = "include_patterns"
    KEY_EXCLUDE_PATTERNS: Final[str] = "exclude_patterns"
    KEY_FILES_FROM: Final[str] = "files_from"
    KEY_CONFIG_FILES: Final[str] = "config_files"
    KEY_FILES: Final[str] = "files"

    # dump/provenance-only keys (emitted by config dump -–show-origin)
    KEY_INCLUDE_PATTERN_GROUPS: Final[str] = "include_pattern_groups"
    KEY_EXCLUDE_PATTERN_GROUPS: Final[str] = "exclude_pattern_groups"
    KEY_INCLUDE_FROM_SOURCES: Final[str] = "include_from_sources"
    KEY_EXCLUDE_FROM_SOURCES: Final[str] = "exclude_from_sources"
    KEY_FILES_FROM_SOURCES: Final[str] = "files_from_sources"

    # Keys used inside dump/provenance-only structured tables
    KEY_BASE: Final[str] = "base"
    KEY_PATH: Final[str] = "path"
    KEY_PATTERNS: Final[str] = "patterns"

    # ---------------------------- Schema helpers ----------------------------

    # Allowed top-level keys under [tool.topmark] / topmark.toml.
    # Used for validation and friendly diagnostics.
    ALLOWED_TOP_LEVEL_KEYS: Final[frozenset[str]] = frozenset(
        {
            KEY_ROOT,
            KEY_STRICT_CONFIG_CHECKING,
            SECTION_HEADER,
            SECTION_FIELDS,
            SECTION_FORMATTING,
            SECTION_WRITER,
            SECTION_POLICY,
            SECTION_POLICY_BY_TYPE,
            SECTION_FILES,
        }
    )

    # Allowed keys per section. Only includes sections that are TOML tables.
    # Note: [fields] is intentionally omitted (arbitrary user-defined keys).
    ALLOWED_SECTION_KEYS: Final[dict[str, frozenset[str]]] = {
        SECTION_HEADER: frozenset(
            {
                KEY_FIELDS,
                KEY_RELATIVE_TO,
            }
        ),
        SECTION_FORMATTING: frozenset(
            {
                KEY_ALIGN_FIELDS,
            }
        ),
        SECTION_WRITER: frozenset(
            {
                KEY_TARGET,
                KEY_STRATEGY,
            }
        ),
        SECTION_POLICY: frozenset(
            {
                KEY_POLICY_HEADER_MUTATION_MODE,
                KEY_POLICY_ALLOW_HEADER_IN_EMPTIES,
                KEY_POLICY_EMPTIES_INSERT_MODE,
                KEY_POLICY_ALLOW_EMPTY_HEADER,
                KEY_POLICY_ALLOW_REFLOW,
                KEY_POLICY_ALLOW_CONTENT_PROBE,
            }
        ),
        # [policy_by_type] contains arbitrary file type keys -> policy tables.
        # Validation for those subtables is handled separately.
        SECTION_FILES: frozenset(
            {
                KEY_INCLUDE_FILE_TYPES,
                KEY_EXCLUDE_FILE_TYPES,
                KEY_INCLUDE_FROM,
                KEY_EXCLUDE_FROM,
                KEY_INCLUDE_PATTERNS,
                KEY_EXCLUDE_PATTERNS,
                KEY_FILES_FROM,
                KEY_CONFIG_FILES,
                KEY_FILES,
            }
        ),
    }

    # Allowed keys inside each [policy_by_type.<filetype>] table.
    ALLOWED_POLICY_KEYS: Final[frozenset[str]] = frozenset(
        {
            KEY_POLICY_HEADER_MUTATION_MODE,
            KEY_POLICY_ALLOW_HEADER_IN_EMPTIES,
            KEY_POLICY_EMPTIES_INSERT_MODE,
            KEY_POLICY_ALLOW_EMPTY_HEADER,
            KEY_POLICY_ALLOW_REFLOW,
            KEY_POLICY_ALLOW_CONTENT_PROBE,
        }
    )

    # dump/provenance-only keys (emitted by config dump -–show-origin)
    DUMP_ONLY_FILES_KEYS: Final[frozenset[str]] = frozenset(
        {
            KEY_INCLUDE_PATTERN_GROUPS,
            KEY_EXCLUDE_PATTERN_GROUPS,
            KEY_INCLUDE_FROM_SOURCES,
            KEY_EXCLUDE_FROM_SOURCES,
            KEY_FILES_FROM_SOURCES,
        }
    )
