# topmark:header:start
#
#   project      : TopMark
#   file         : validation.py
#   file_relpath : src/topmark/toml/validation.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Structured TOML schema-validation issues and diagnostic adapters.

This module defines TOML-specific validation issue types used by the static
schema layer in [`topmark.toml.schema`][topmark.toml.schema]. The goal is to
keep schema validation structured and machine-friendly while still allowing the
existing diagnostic log to receive ordinary
[`Diagnostic`][topmark.diagnostic.model.Diagnostic] entries.

The issue model is intentionally narrow for phase 1 of the TOML schema
refactor:
    - it captures unknown sections and keys,
    - it distinguishes invalid table shapes,
    - it preserves section/key/path metadata for later machine output.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from topmark.diagnostic.model import DiagnosticLevel

if TYPE_CHECKING:
    from collections.abc import Iterable

    from topmark.diagnostic.model import DiagnosticLog


class TomlDiagnosticCode(str, Enum):
    """Stable codes for TOML schema-validation diagnostics.

    These codes identify the structural kind of TOML validation issue without
    depending on a human-facing message string.
    """

    UNKNOWN_TOP_LEVEL_SECTION = "toml.unknown_top_level_section"
    UNKNOWN_TOP_LEVEL_KEY = "toml.unknown_top_level_key"
    MISSING_SECTION = "toml.missing_section"
    UNKNOWN_SECTION_KEY = "toml.unknown_section_key"
    INVALID_SECTION_TYPE = "toml.invalid_section_type"
    INVALID_NESTED_SECTION_TYPE = "toml.invalid_nested_section_type"
    DUMP_ONLY_KEY_IN_INPUT = "toml.dump_only_key_in_input"


@dataclass(
    frozen=True,
    kw_only=True,
    slots=True,
)
class TomlValidationIssue:
    """Structured TOML schema-validation issue.

    The validator emits these issues first so callers can later map them to the
    internal diagnostic log, machine-readable output, or test assertions.

    Attributes:
        code: Stable TOML validation code.
        level: Diagnostic severity.
        message: Human-readable diagnostic message.
        path: Full TOML path to the offending element.
        section: Section name, or `None` for top-level unknown sections.
        key: Offending key name when applicable.
        allowed_keys: Candidate keys valid in the relevant context.
        suggestion: Suggested replacement key when a close match exists.
    """

    code: TomlDiagnosticCode
    level: DiagnosticLevel
    message: str
    path: tuple[str, ...]
    section: str | None = None
    key: str | None = None
    allowed_keys: tuple[str, ...] = ()
    suggestion: str | None = None


def add_toml_issues(
    log: DiagnosticLog,
    issues: Iterable[TomlValidationIssue],
) -> None:
    """Record TOML validation issues through the diagnostic log.

    This preserves the existing level-specific logging behavior by routing each
    issue through the corresponding `DiagnosticLog` helper.

    Args:
        log: Mutable diagnostic log receiving the TOML validation issues.
        issues: Structured TOML validation issues to record.

    Raises:
        RuntimeError: If an invalid diagnostic level was provided.
    """
    for issue in issues:
        msg: str = issue.message
        lvl: DiagnosticLevel = issue.level
        if lvl == DiagnosticLevel.INFO:
            log.add_info(msg)
        elif lvl == DiagnosticLevel.WARNING:
            log.add_warning(msg)
        elif lvl == DiagnosticLevel.ERROR:
            log.add_error(msg)
        else:
            # Defensive guard
            raise RuntimeError(f"Invalid diagnostic level {lvl}")
