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

    The ordering of constants mirrors `topmark-default.toml` to make it easy to
    audit schema changes and keep defaults/docs/parsing aligned.

    Notes:
        - Values must match user-facing TOML keys exactly.
        - Renaming or removing a key is a breaking change.
        - CLI keys are defined separately in `topmark.cli.keys`.
    """

    # Root / discovery
    KEY_ROOT: Final[str] = "root"

    # [header]
    SECTION_HEADER: Final[str] = "header"

    KEY_FIELDS: Final[str] = "fields"

    # [fields]
    SECTION_FIELDS: Final[str] = "fields"

    # [formatting]
    SECTION_FORMATTING: Final[str] = "formatting"

    KEY_ALIGN_FIELDS: Final[str] = "align_fields"
    KEY_HEADER_FORMAT: Final[str] = "header_format"

    # [writer]
    SECTION_WRITER: Final[str] = "writer"

    # [writer] Output destination key ("file" or "stdout").
    KEY_TARGET: Final[str] = "target"
    KEY_STRATEGY: Final[str] = "strategy"

    # [policy] and [policy_by_type]
    SECTION_POLICY: Final[str] = "policy"
    SECTION_POLICY_BY_TYPE: Final[str] = "policy_by_type"

    KEY_POLICY_CHECK_ADD_ONLY: Final[str] = "add_only"
    KEY_POLICY_CHECK_UPDATE_ONLY: Final[str] = "update_only"
    KEY_POLICY_ALLOW_HEADER_IN_EMPTIES: Final[str] = "allow_header_in_empty_files"

    # [files]
    SECTION_FILES: Final[str] = "files"

    KEY_INCLUDE_FILE_TYPES: Final[str] = "include_file_types"
    KEY_EXCLUDE_FILE_TYPES: Final[str] = "exclude_file_types"
    KEY_INCLUDE_FROM: Final[str] = "include_from"
    KEY_EXCLUDE_FROM: Final[str] = "exclude_from"
    KEY_INCLUDE_PATTERNS: Final[str] = "include_patterns"
    KEY_EXCLUDE_PATTERNS: Final[str] = "exclude_patterns"
    KEY_FILES_FROM: Final[str] = "files_from"
    KEY_RELATIVE_TO: Final[str] = "relative_to"
    KEY_CONFIG_FILES: Final[str] = "config_files"
    KEY_FILES: Final[str] = "files"
