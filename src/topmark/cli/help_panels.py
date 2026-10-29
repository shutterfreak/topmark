# topmark:header:start
#
#   project      : TopMark
#   file         : help_panels.py
#   file_relpath : src/topmark/cli/help_panels.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Declarative Rich Click option-panel membership shared by CLI commands."""

from __future__ import annotations

from typing import Final

from topmark.cli.keys import CliOpt

DISPLAY_PANEL_OPTIONS: Final[tuple[str, ...]] = (
    CliOpt.NO_COLOR_MODE,
    CliOpt.COLOR_MODE,
    CliOpt.VERBOSE,
)
"""Shared display controls shown together in command help."""

TEXT_OUTPUT_PANEL_OPTIONS: Final[tuple[str, ...]] = (CliOpt.QUIET,)
"""Shared controls that suppress or otherwise alter human text output."""

OUTPUT_AND_HELP_PANEL_OPTIONS: Final[tuple[str, ...]] = (
    CliOpt.OUTPUT_FORMAT,
    CliOpt.HELP,
)
"""Shared output-format and built-in help controls shown together in command help."""

PATH_FILTERING_PANEL_OPTIONS: Final[tuple[str, ...]] = (
    CliOpt.INCLUDE_FROM,
    CliOpt.EXCLUDE_FROM,
    CliOpt.INCLUDE_PATTERNS,
    CliOpt.EXCLUDE_PATTERNS,
)
"""Shared path-pattern filtering controls."""

FILE_TYPE_ASSIGNMENT_PANEL_OPTIONS: Final[tuple[str, ...]] = (
    CliOpt.ASSIGN_FILETYPE,
    CliOpt.INFER_FILETYPE,
)
"""Shared ordered file-type assignment and inference controls."""

FILE_TYPE_FILTERING_PANEL_OPTIONS: Final[tuple[str, ...]] = (
    *FILE_TYPE_ASSIGNMENT_PANEL_OPTIONS,
    CliOpt.INCLUDE_FILE_TYPES,
    CliOpt.EXCLUDE_FILE_TYPES,
    CliOpt.OPT_IN_FILE_TYPE,
)
"""Shared file-type filtering and activation controls."""

HEADER_METADATA_PANEL_OPTIONS: Final[tuple[str, ...]] = (
    CliOpt.RELATIVE_TO,
    CliOpt.ALIGN_FIELDS,
)
"""Shared header-rendering metadata controls."""

PATH_INPUT_AND_FILTERING_PANEL_OPTIONS: Final[tuple[str, ...]] = (
    CliOpt.STDIN_FILENAME,
    CliOpt.FILES_FROM,
    *PATH_FILTERING_PANEL_OPTIONS,
    *FILE_TYPE_FILTERING_PANEL_OPTIONS,
)
"""Shared path-input and filtering controls for processing commands."""

CONFIGURATION_RESOLUTION_PANEL_OPTIONS: Final[tuple[str, ...]] = (
    CliOpt.CONFIG_FILES,
    CliOpt.NO_CONFIG,
)
"""Shared configuration-source controls."""

CONFIGURATION_STRICTNESS_PANEL_OPTIONS: Final[tuple[str, ...]] = (CliOpt.STRICT,)
"""Shared override that promotes configuration warnings to errors."""

PROBE_RESOLUTION_POLICY_PANEL_OPTIONS: Final[tuple[str, ...]] = (CliOpt.POLICY_ALLOW_CONTENT_PROBE,)
"""Resolution policy controls specific to ``topmark probe``."""

GENERATED_CONFIGURATION_PANEL_OPTIONS: Final[tuple[str, ...]] = (
    CliOpt.CONFIG_FOR_PYPROJECT,
    CliOpt.CONFIG_ROOT,
)
"""Shared controls for generated configuration documents."""

REGISTRY_DETAIL_PANEL_OPTIONS: Final[tuple[str, ...]] = (CliOpt.SHOW_DETAILS,)
"""Shared registry-detail control."""

REGISTRY_FILTERING_PANEL_OPTIONS: Final[tuple[str, ...]] = (CliOpt.ACTIVATION,)
"""Shared registry activation filter."""

REGISTRY_IDENTITY_FILTERING_PANEL_OPTIONS: Final[tuple[str, ...]] = (
    CliOpt.MATCH_REGEX,
    CliOpt.REGISTRY_BUILTIN,
)
"""Shared registry identity-selection options."""

REGISTRY_BINDING_IDENTITY_FILTERING_PANEL_OPTIONS: Final[tuple[str, ...]] = (CliOpt.MATCH_REGEX,)
"""Endpoint-identity selection options for registry binding relationships."""

REMEDIATION_HEADER_POLICY_PANEL_OPTIONS: Final[tuple[str, ...]] = (
    CliOpt.POLICY_MIXED_LINE_ENDINGS,
    CliOpt.POLICY_BOM_BEFORE_SHEBANG,
    CliOpt.POLICY_ALLOW_CONTENT_PROBE,
)
"""Header policies shared by commands that can remediate existing files."""

CHECK_HEADER_POLICY_PANEL_OPTIONS: Final[tuple[str, ...]] = (
    CliOpt.POLICY_HEADER_MUTATION_MODE,
    CliOpt.POLICY_ALLOW_HEADER_IN_EMPTY_FILES,
    CliOpt.POLICY_EMPTY_INSERT_MODE,
    CliOpt.POLICY_RENDER_EMPTY_HEADER_WHEN_NO_FIELDS,
    CliOpt.POLICY_ALLOW_REFLOW,
    *REMEDIATION_HEADER_POLICY_PANEL_OPTIONS,
    *HEADER_METADATA_PANEL_OPTIONS,
)
"""Header policies and rendering metadata specific to ``topmark check``."""

PROCESSING_OUTPUT_AND_CHANGES_PANEL_OPTIONS: Final[tuple[str, ...]] = (
    CliOpt.APPLY_CHANGES,
    CliOpt.WRITE_MODE,
    CliOpt.RENDER_DIFF,
    CliOpt.REPORT,
    CliOpt.RESULTS_SUMMARY_MODE,
    *OUTPUT_AND_HELP_PANEL_OPTIONS,
)
"""Shared output and mutation controls for processing commands."""

VERSION_FORMAT_PANEL_OPTIONS: Final[tuple[str, ...]] = (CliOpt.SEMVER_VERSION,)
"""Version-format selection control specific to ``topmark version``."""

CONFIG_DUMP_CONFIGURATION_SOURCES_PANEL_OPTIONS: Final[tuple[str, ...]] = (
    *CONFIGURATION_RESOLUTION_PANEL_OPTIONS,
    CliOpt.SHOW_CONFIG_LAYERS,
)
"""Configuration-source and provenance controls for ``topmark config dump``."""

CONFIG_DUMP_FILTERING_AND_HEADER_METADATA_PANEL_OPTIONS: Final[tuple[str, ...]] = (
    CliOpt.FILES_FROM,
    *PATH_FILTERING_PANEL_OPTIONS,
    *FILE_TYPE_FILTERING_PANEL_OPTIONS,
    *HEADER_METADATA_PANEL_OPTIONS,
)
"""Filtering and header-metadata controls for ``topmark config dump``."""
