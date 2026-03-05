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

from enum import Enum


class ArgKey(str, Enum):
    """Canonical argument keys used by the TopMark CLI / API.

    Notes:
        - Each constant is a canonical destination key (`dest`) used by Click.
        - These keys are the internal contract between CLI parsing and downstream
          consumers (config application and runtime execution).
        - Values are Python identifiers (snake_case), not CLI spellings.
    """

    # File selection & filters
    FILES = "files"
    INCLUDE_PATTERNS = "include_patterns"
    EXCLUDE_PATTERNS = "exclude_patterns"
    INCLUDE_FROM = "include_from"
    EXCLUDE_FROM = "exclude_from"
    FILES_FROM = "files_from"
    INCLUDE_FILE_TYPES = "include_file_types"
    EXCLUDE_FILE_TYPES = "exclude_file_types"

    # Config discovery
    CONFIG_FILES = "config_files"
    NO_CONFIG = "no_config"
    CONFIG_FOR_PYPROJECT = "for_pyproject"

    # Header rendering
    ALIGN_FIELDS = "align_fields"
    RELATIVE_TO = "relative_to"

    # Policy
    POLICY_CHECK_ADD_ONLY = "add_only"
    POLICY_CHECK_UPDATE_ONLY = "update_only"

    # Output / write behavior
    WRITE_MODE = "write_mode"
    APPLY_CHANGES = "apply_changes"
    RENDER_DIFF = "diff"
    RESULTS_SUMMARY_MODE = "summary_mode"
    OUTPUT_FORMAT = "output_format"
    SHOW_DETAILS = "show_details"
    SKIP_COMPLIANT = "skip_compliant"
    SKIP_UNSUPPORTED = "skip_unsupported"

    # Logging / UX
    VERBOSE = "verbose"
    QUIET = "quiet"
    VERBOSITY_LEVEL = "verbosity_level"
    LOG_LEVEL = "log_level"
    COLOR_MODE = "color_mode"
    NO_COLOR_MODE = "no_color"
    COLOR_ENABLED = "color_enabled"
    CONSOLE = "console"

    # Stdin / misc
    STDIN_MODE = "stdin_mode"
    STDIN_FILENAME = "stdin_filename"
    SEMVER_VERSION = "semver"

    # Config checking
    STRICT_CONFIG_CHECKING = "strict_config_checking"

    # Config root
    CONFIG_ROOT = "config_root"

    # Machine metadata payload
    META = "meta_payload"
