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
    - Parsed argument destination keys are defined in [`topmark.core.keys.ArgKey`][].
    - This module is intentionally behavior-free; it is a pure namespace of constants.
"""

from __future__ import annotations

from typing import Final


class CliCmd:
    """Command names exposed by the TopMark CLI.

    These values are the Click command names (e.g., `topmark check`).
    """

    CHECK: Final[str] = "check"
    STRIP: Final[str] = "strip"
    CONFIG: Final[str] = "config"
    CONFIG_CHECK: Final[str] = "check"
    CONFIG_DUMP: Final[str] = "dump"
    CONFIG_DEFAULTS: Final[str] = "defaults"
    CONFIG_INIT: Final[str] = "init"
    FILETYPES: Final[str] = "filetypes"
    PROCESSORS: Final[str] = "processors"
    VERSION: Final[str] = "version"


class CliOpt:
    """User-facing long option spellings for the TopMark CLI.

    Notes:
        - Each constant is the canonical **long** option spelling exposed to users.
        - Values include the leading `--`.
        - Short options are defined alongside Click options in command modules,
          not in this namespace.
    """

    # File selection & filters
    INCLUDE_FILE_TYPES: Final[str] = "--include-file-types"
    INCLUDE_FILE_TYPE: Final[str] = "--include-file-type"
    EXCLUDE_FILE_TYPES: Final[str] = "--exclude-file-types"
    EXCLUDE_FILE_TYPE: Final[str] = "--exclude-file-type"
    INCLUDE_FROM: Final[str] = "--include-from"
    EXCLUDE_FROM: Final[str] = "--exclude-from"
    INCLUDE_PATTERNS: Final[str] = "--include"
    EXCLUDE_PATTERNS: Final[str] = "--exclude"
    FILES_FROM: Final[str] = "--files-from"
    RELATIVE_TO: Final[str] = "--relative-to"

    # Config discovery
    CONFIG_PATHS: Final[str] = "--config"
    NO_CONFIG: Final[str] = "--no-config"

    # Header rendering
    HEADER_FORMAT: Final[str] = "--header-format"
    ALIGN_FIELDS: Final[str] = "--align-fields"
    NO_ALIGN_FIELDS: Final[str] = "--no-align-fields"

    # Policy
    POLICY_CHECK_ADD_ONLY: Final[str] = "--add-only"
    POLICY_CHECK_UPDATE_ONLY: Final[str] = "--update-only"

    # Output / write behavior
    WRITE_MODE: Final[str] = "--write-mode"
    APPLY_CHANGES: Final[str] = "--apply"
    RENDER_DIFF: Final[str] = "--diff"
    RESULTS_SUMMARY_MODE: Final[str] = "--summary"
    OUTPUT_FORMAT: Final[str] = "--output-format"
    SHOW_DETAILS: Final[str] = "--long"
    SKIP_COMPLIANT: Final[str] = "--skip-compliant"
    SKIP_UNSUPPORTED: Final[str] = "--skip-unsupported"

    # Logging / UX
    VERBOSE: Final[str] = "--verbose"
    QUIET: Final[str] = "--quiet"
    COLOR_MODE: Final[str] = "--color"
    NO_COLOR_MODE: Final[str] = "--no-color"

    # Stdin / misc
    STDIN_FILENAME: Final[str] = "--stdin-filename"
    HELP: Final[str] = "--help"
    CONFIG_FOR_PYPROJECT: Final[str] = "--pyproject"
    SEMVER_VERSION: Final[str] = "--semver"

    # Config checking
    STRICT_CONFIG_CHECKING: Final[str] = "--strict"
    NO_STRICT_CONFIG_CHECKING: Final[str] = "--no-strict"
