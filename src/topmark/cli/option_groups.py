# topmark:header:start
#
#   project      : TopMark
#   file         : option_groups.py
#   file_relpath : src/topmark/cli/option_groups.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Command applicability groups for CLI options.

This module is a narrow metadata layer for command-applicability test coverage.
It groups already-declared option spellings by the path-oriented commands that
may accept them. Click remains the authoritative parser: commands that do not
declare these options reject them as parser-level unknown options.
"""

from __future__ import annotations

from typing import Final

from topmark.cli.keys import CliOpt

CHECK_ONLY_OPTION_REASON: Final[str] = "Use this only with `topmark check`."
"""Reason shown when a check-only option is used with another command."""

CHECK_OR_STRIP_ONLY_OPTION_REASON: Final[str] = (
    "Use this only with `topmark check` or `topmark strip`."
)
"""Reason shown when a check-or-strip-only option is used with another command."""

CHECK_ONLY_GENERATED_HEADER_OPTIONS: Final[tuple[str, ...]] = (
    CliOpt.POLICY_HEADER_MUTATION_MODE,
    CliOpt.POLICY_ALLOW_HEADER_IN_EMPTY_FILES,
    CliOpt.POLICY_NO_ALLOW_HEADER_IN_EMPTY_FILES,
    CliOpt.POLICY_EMPTY_INSERT_MODE,
    CliOpt.POLICY_RENDER_EMPTY_HEADER_WHEN_NO_FIELDS,
    CliOpt.POLICY_NO_RENDER_EMPTY_HEADER_WHEN_NO_FIELDS,
    CliOpt.POLICY_ALLOW_REFLOW,
    CliOpt.POLICY_NO_ALLOW_REFLOW,
    CliOpt.HEADER_FIELDS,
    CliOpt.FIELD_VALUES,
    CliOpt.ALIGN_FIELDS,
    CliOpt.NO_ALIGN_FIELDS,
    CliOpt.RELATIVE_TO,
)
"""Header generation/update controls accepted only by `topmark check`.

These options configure generated header content or update policy. They are not
meaningful for `topmark strip`, which removes headers, or `topmark probe`, which
only reports file resolution and type support.
"""

CHECK_OR_STRIP_ONLY_PIPELINE_OPTIONS: Final[tuple[str, ...]] = (
    CliOpt.POLICY_BOM_BEFORE_SHEBANG,
    CliOpt.APPLY_CHANGES,
    CliOpt.WRITE_MODE,
    CliOpt.RENDER_DIFF,
    CliOpt.RESULTS_SUMMARY_MODE,
    CliOpt.REPORT,
)
"""Pipeline mutation/reporting controls accepted by `check` and `strip`.

These options either control writes, patch/diff previews, or report scope. They
are intentionally rejected by `topmark probe`, which remains read-only and
focused on discovery diagnostics.
"""

PROBE_FORBIDDEN_OPTIONS: Final[dict[str, str]] = {
    **dict.fromkeys(
        CHECK_OR_STRIP_ONLY_PIPELINE_OPTIONS,
        CHECK_OR_STRIP_ONLY_OPTION_REASON,
    ),
    **dict.fromkeys(
        CHECK_ONLY_GENERATED_HEADER_OPTIONS,
        CHECK_ONLY_OPTION_REASON,
    ),
}
"""Options that `topmark probe` must not declare.

The values document the historical command-applicability rationale and keep test
parameterization close to production option metadata.
"""

STRIP_FORBIDDEN_OPTIONS: Final[dict[str, str]] = dict.fromkeys(
    CHECK_ONLY_GENERATED_HEADER_OPTIONS,
    CHECK_ONLY_OPTION_REASON,
)
"""Options that `topmark strip` must not declare.

The values document the historical command-applicability rationale and keep test
parameterization close to production option metadata.
"""
