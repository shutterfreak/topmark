# topmark:header:start
#
#   project      : TopMark
#   file         : validation.py
#   file_relpath : src/topmark/config/validation.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Stage-aware validation logs for config loading and preflight checks.

This module defines small, typed containers that group shared diagnostics by
validation stage during TopMark's config-loading lifecycle. It complements the
generic diagnostic substrate in
[`topmark.diagnostic.model`][topmark.diagnostic.model] rather than replacing
it: diagnostics remain ordinary `Diagnostic` entries collected in
`DiagnosticLog` / `FrozenDiagnosticLog`, while this module adds stage-aware
structure around those logs.

The staged model currently distinguishes three validation stages:

- `TOML_SOURCE`: whole-source TOML validation and other source-local TOML issues.
- `MERGED_CONFIG`: layered-config deserialization, merge-time checks, config
  invariants, and typed override-application diagnostics.
- `RUNTIME_APPLICABILITY`: sanitization recoveries and other preflight/runtime
  applicability diagnostics.

These containers serve two roles in the current staged config-validation
model:

- preserve stage-local diagnostics so validation boundaries remain explicit,
- provide a flattened compatibility view in stage order for callers that still
  consume a single `DiagnosticLog` at reporting or output boundaries.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from enum import Enum

from topmark.diagnostic.model import DiagnosticLog
from topmark.diagnostic.model import FrozenDiagnosticLog


class ValidationStage(str, Enum):
    """Named validation stages for config-loading and preflight diagnostics."""

    TOML_SOURCE = "toml_source"
    MERGED_CONFIG = "merged_config"
    RUNTIME_APPLICABILITY = "runtime_applicability"


@dataclass(slots=True, kw_only=True)
class ValidationLogs:
    """Mutable staged diagnostic logs for config validation.

    Attributes:
        toml_source: Diagnostics from whole-source TOML validation and
            source-local TOML issues.
        merged_config: Diagnostics from layered config deserialization,
            merge-time checks, invariants, and typed override application.
        runtime_applicability: Diagnostics from sanitization and recoverable
            runtime/preflight applicability checks.
    """

    toml_source: DiagnosticLog = field(default_factory=DiagnosticLog)
    merged_config: DiagnosticLog = field(default_factory=DiagnosticLog)
    runtime_applicability: DiagnosticLog = field(default_factory=DiagnosticLog)

    def freeze(self) -> FrozenValidationLogs:
        """Return an immutable snapshot of the staged validation logs."""
        return FrozenValidationLogs(
            toml_source=self.toml_source.freeze(),
            merged_config=self.merged_config.freeze(),
            runtime_applicability=self.runtime_applicability.freeze(),
        )

    def merge_with(self, other: ValidationLogs) -> ValidationLogs:
        """Return staged validation logs merged with a higher-precedence draft.

        Diagnostics accumulate within each validation stage. The merged result keeps
        this instance's diagnostics first and appends diagnostics from the
        higher-precedence `other` draft afterward, preserving insertion order within
        each stage.

        Args:
            other: Higher-precedence staged validation logs to append.

        Returns:
            A new staged validation-log container containing the merged result.
        """
        return ValidationLogs(
            toml_source=DiagnosticLog.from_iterable(
                [
                    *self.toml_source,
                    *other.toml_source,
                ],
            ),
            merged_config=DiagnosticLog.from_iterable(
                [
                    *self.merged_config.items,
                    *other.merged_config.items,
                ]
            ),
            runtime_applicability=DiagnosticLog.from_iterable(
                [
                    *self.runtime_applicability.items,
                    *other.runtime_applicability.items,
                ]
            ),
        )

    def flattened(self) -> DiagnosticLog:
        """Return a flattened compatibility view in stage order.

        Diagnostics are concatenated without rewriting their messages so the
        flattened compatibility diagnostic view remains stable at reporting and
        output boundaries.
        """
        return DiagnosticLog.from_iterable(
            list(self.toml_source) + list(self.merged_config) + list(self.runtime_applicability)
        )


@dataclass(frozen=True, slots=True)
class FrozenValidationLogs:
    """Immutable staged diagnostic logs for frozen config snapshots."""

    toml_source: FrozenDiagnosticLog
    merged_config: FrozenDiagnosticLog
    runtime_applicability: FrozenDiagnosticLog

    def thaw(self) -> ValidationLogs:
        """Return a mutable copy of these staged validation logs."""
        return ValidationLogs(
            toml_source=self.toml_source.thaw(),
            merged_config=self.merged_config.thaw(),
            runtime_applicability=self.runtime_applicability.thaw(),
        )

    def flattened(self) -> FrozenDiagnosticLog:
        """Return a flattened immutable compatibility view in stage order.

        This helper is intended for reporting and output boundaries that still
        consume a single immutable diagnostic log.
        """
        return DiagnosticLog.from_iterable(
            list(self.toml_source) + list(self.merged_config) + list(self.runtime_applicability)
        ).freeze()
