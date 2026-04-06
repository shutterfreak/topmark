# topmark:header:start
#
#   project      : TopMark
#   file         : keys.py
#   file_relpath : src/topmark/cli/keys.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Canonical CLI option spellings for TopMark.

This module defines the *stable string spellings* exposed by the TopMark CLI layer,
primarily long option names (e.g. ``--include-file-types``).

Centralizing these values avoids string duplication, prevents drift between command
definitions, and makes refactors (renames, aliases, deprecations) explicit and auditable.

Design notes:
    - CLI option spellings (``CliOpt``) are user-facing and should be changed with care.
    - Parsed argument destination keys are defined in [topmark.core.keys.ArgKey][].
    - This module is intentionally behavior-free; it is a pure namespace of constants.
"""

from __future__ import annotations

from typing import Final


class CliCmd:
    """Command names exposed by the TopMark CLI.

    These values are the Click command names (e.g., `topmark check`).
    """

    CHECK: Final = "check"
    STRIP: Final = "strip"
    CONFIG: Final = "config"
    CONFIG_CHECK: Final = "check"
    CONFIG_DUMP: Final = "dump"
    CONFIG_DEFAULTS: Final = "defaults"
    CONFIG_INIT: Final = "init"
    REGISTRY: Final = "registry"
    REGISTRY_BINDINGS: Final = "bindings"
    REGISTRY_FILETYPES: Final = "filetypes"
    REGISTRY_PROCESSORS: Final = "processors"
    VERSION: Final = "version"


class CliOpt:
    """User-facing long option spellings for the TopMark CLI.

    Notes:
        - Each constant is the canonical **long** option spelling exposed to users.
        - Values include the leading `--`.
        - Short options are defined in `CliShortOpt`, not in this namespace.
    """

    # File selection & filters
    INCLUDE_FILE_TYPES: Final = "--include-file-types"
    INCLUDE_FILE_TYPE: Final = "--include-file-type"
    EXCLUDE_FILE_TYPES: Final = "--exclude-file-types"
    EXCLUDE_FILE_TYPE: Final = "--exclude-file-type"
    INCLUDE_FROM: Final = "--include-from"
    EXCLUDE_FROM: Final = "--exclude-from"
    INCLUDE_PATTERNS: Final = "--include"
    EXCLUDE_PATTERNS: Final = "--exclude"
    FILES_FROM: Final = "--files-from"

    # Config discovery
    CONFIG_FILES: Final = "--config"
    NO_CONFIG: Final = "--no-config"

    # Config: provenance of include/exclude lists/patterns, ...
    SHOW_CONFIG_LAYERS: Final = "--show-layers"

    # Header fields
    HEADER_FIELDS: Final = "--header-fields"
    FIELD_VALUES: Final = "--field-values"

    # Header rendering
    ALIGN_FIELDS: Final = "--align-fields"
    NO_ALIGN_FIELDS: Final = "--no-align-fields"
    RELATIVE_TO: Final = "--relative-to"

    # Policy
    POLICY_HEADER_MUTATION_MODE: Final = "--header-mutation-mode"
    POLICY_ALLOW_HEADER_IN_EMPTY_FILES: Final = "--allow-header-in-empty-files"
    POLICY_NO_ALLOW_HEADER_IN_EMPTY_FILES: Final = "--no-allow-header-in-empty-files"
    POLICY_EMPTY_INSERT_MODE: Final = "--empty-insert-mode"
    POLICY_RENDER_EMPTY_HEADER_WHEN_NO_FIELDS: Final = "--render-empty-header-when-no-fields"
    POLICY_NO_RENDER_EMPTY_HEADER_WHEN_NO_FIELDS: Final = "--no-render-empty-header-when-no-fields"
    POLICY_ALLOW_REFLOW: Final = "--allow-reflow"
    POLICY_NO_ALLOW_REFLOW: Final = "--no-allow-reflow"
    POLICY_ALLOW_CONTENT_PROBE: Final = "--allow-content-probe"
    POLICY_NO_ALLOW_CONTENT_PROBE: Final = "--no-allow-content-probe"

    # Pipeline result reporting
    REPORT: Final = "--report"

    # Output / write behavior
    WRITE_MODE: Final = "--write-mode"
    APPLY_CHANGES: Final = "--apply"
    RENDER_DIFF: Final = "--diff"
    RESULTS_SUMMARY_MODE: Final = "--summary"
    OUTPUT_FORMAT: Final = "--output-format"
    SHOW_DETAILS: Final = "--long"

    # Logging / UX
    VERBOSE: Final = "--verbose"
    QUIET: Final = "--quiet"
    COLOR_MODE: Final = "--color"
    NO_COLOR_MODE: Final = "--no-color"

    # Stdin / misc
    STDIN_FILENAME: Final = "--stdin-filename"
    HELP: Final = "--help"
    CONFIG_FOR_PYPROJECT: Final = "--pyproject"
    SEMVER_VERSION: Final = "--semver"

    # Config checking
    STRICT_CONFIG_CHECKING: Final = "--strict"
    NO_STRICT_CONFIG_CHECKING: Final = "--no-strict"

    # Config root
    CONFIG_ROOT: Final = "--root"


class CliShortOpt:
    """User-facing short option spellings for the TopMark CLI.

    Notes:
        - Each constant is the canonical **short** option spelling exposed to users.
        - Values include the leading `-`.
        - Long options are defined in `CliOpt`, not in this namespace.
    """

    HELP: Final = "-h"
    VERBOSE: Final = "-v"
    QUIET: Final = "-q"
    INCLUDE_FILE_TYPES: Final = "-t"
    EXCLUDE_FILE_TYPES: Final = "-T"
    CONFIG_FILES: Final = "-c"
    INCLUDE_PATTERNS: Final = "-i"
    EXCLUDE_PATTERNS: Final = "-e"
    SHOW_DETAILS: Final = "-l"
