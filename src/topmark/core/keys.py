# topmark:header:start
#
#   project      : TopMark
#   file         : keys.py
#   file_relpath : src/topmark/core/keys.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Shared canonical argument keys.

This module defines the *stable destination keys* used across TopMark to represent
parsed arguments and options (from the CLI and API). These keys are the internal
contract between argument parsing and downstream consumers (configuration merging,
policy evaluation, and runtime execution).

Notes:
    - Values are Python identifiers (snake_case), not CLI spellings.
    - The CLI spellings (e.g. ``--include-file-types``) live in
      [`topmark.cli.keys`][topmark.cli.keys].
    - Keep this module behavior-free; it should remain a pure namespace for
      constants so it can be imported from anywhere without causing cycles.
"""

from __future__ import annotations

from typing import Final


class ArgKey:
    """Canonical argument keys used by the TopMark CLI / API.

    Notes:
        - Each constant is a canonical destination key (`dest`) used by Click.
        - These keys are the internal contract between CLI parsing and downstream
          consumers (config application and runtime execution).
        - Values are Python identifiers (snake_case), not CLI spellings.
    """

    # File selection & filters
    FILES: Final[str] = "files"
    INCLUDE_PATTERNS: Final[str] = "include_patterns"
    EXCLUDE_PATTERNS: Final[str] = "exclude_patterns"
    INCLUDE_FROM: Final[str] = "include_from"
    EXCLUDE_FROM: Final[str] = "exclude_from"
    FILES_FROM: Final[str] = "files_from"
    RELATIVE_TO: Final[str] = "relative_to"
    INCLUDE_FILE_TYPES: Final[str] = "include_file_types"
    EXCLUDE_FILE_TYPES: Final[str] = "exclude_file_types"

    # Config discovery
    CONFIG_PATHS: Final[str] = "config_paths"
    CONFIG_FILES: Final[str] = "config_files"
    NO_CONFIG: Final[str] = "no_config"
    CONFIG_FOR_PYPROJECT: Final[str] = "pyproject"

    # Header rendering
    HEADER_FORMAT: Final[str] = "header_format"
    ALIGN_FIELDS: Final[str] = "align_fields"

    # Policy
    POLICY_CHECK_ADD_ONLY: Final[str] = "add_only"
    POLICY_CHECK_UPDATE_ONLY: Final[str] = "update_only"

    # Output / write behavior
    WRITE_MODE: Final[str] = "write_mode"
    APPLY_CHANGES: Final[str] = "apply_changes"
    RENDER_DIFF: Final[str] = "diff"
    RESULTS_SUMMARY_MODE: Final[str] = "summary_mode"
    OUTPUT_FORMAT: Final[str] = "output_format"
    SHOW_DETAILS: Final[str] = "show_details"
    SKIP_COMPLIANT: Final[str] = "skip_compliant"
    SKIP_UNSUPPORTED: Final[str] = "skip_unsupported"

    # Logging / UX
    VERBOSE: Final[str] = "verbose"
    QUIET: Final[str] = "quiet"
    VERBOSITY_LEVEL: Final[str] = "verbosity_level"
    LOG_LEVEL: Final[str] = "log_level"
    COLOR_MODE: Final[str] = "color_mode"
    NO_COLOR_MODE: Final[str] = "no_color"
    COLOR_ENABLED: Final[str] = "color_enabled"
    CONSOLE: Final[str] = "console"

    # Stdin / misc
    STDIN_MODE: Final[str] = "stdin_mode"
    STDIN_FILENAME: Final[str] = "stdin_filename"
    SEMVER_VERSION: Final[str] = "semver"

    # Config checking
    STRICT_CONFIG_CHECKING: Final[str] = "strict_config_checking"

    # Machine metadata payload
    META: Final[str] = "meta_payload"
