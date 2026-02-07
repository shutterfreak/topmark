# topmark:header:start
#
#   project      : TopMark
#   file         : schemas.py
#   file_relpath : src/topmark/diagnostic/machine/schemas.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Typed payload schemas for machine-readable diagnostics.

This module defines small, JSON-friendly dataclasses used by multiple TopMark
domains to represent diagnostics in machine output. These classes belong to the
payload layer (schemas → payloads → shapes → serializers):

- `MachineDiagnosticEntry` represents a single diagnostic (level + message).
- `MachineDiagnosticCounts` represents aggregated per-level counts.

The NDJSON shape layer emits one record per *internal* `Diagnostic`. For JSON
envelopes, domains typically prebuild lists of `MachineDiagnosticEntry` and a
`MachineDiagnosticCounts` instance.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from topmark.diagnostic.model import (
    DiagnosticStats,
    compute_diagnostic_stats,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    from topmark.diagnostic.model import Diagnostic


@dataclass(slots=True)
class MachineDiagnosticEntry:
    """Machine-readable diagnostic entry.

    Attributes:
        level: Severity level string (e.g. "info", "warning", "error").
        message: Human-readable diagnostic message.
    """

    level: str
    message: str

    @classmethod
    def from_diagnostic(cls, d: Diagnostic) -> MachineDiagnosticEntry:
        """Create a machine-readable entry from an internal diagnostic.

        Args:
            d: Internal diagnostic instance.

        Returns:
            A `MachineDiagnosticEntry` containing the severity level and message.
        """
        return cls(level=d.level.value, message=d.message)

    def to_dict(self) -> dict[str, str]:
        """Return a JSON-friendly dict of this diagnostic entry."""
        return {
            "level": self.level,
            "message": self.message,
        }


@dataclass(slots=True)
class MachineDiagnosticCounts:
    """Aggregated per-level counts for machine output.

    Attributes:
        info: Count of info-level diagnostics.
        warning: Count of warning-level diagnostics.
        error: Count of error-level diagnostics.
    """

    info: int
    warning: int
    error: int

    @classmethod
    def from_iterable(cls, diagnostics: Iterable[Diagnostic]) -> MachineDiagnosticCounts:
        """Compute per-level counts from an iterable of internal diagnostics.

        Args:
            diagnostics: Internal diagnostics to aggregate.

        Returns:
            A `MachineDiagnosticCounts` instance with per-level totals.
        """
        stats: DiagnosticStats = compute_diagnostic_stats(diagnostics)
        return cls(info=stats.n_info, warning=stats.n_warning, error=stats.n_error)

    def to_dict(self) -> dict[str, int]:
        """Return a JSON-friendly dict of the per-level counts."""
        return {
            "info": self.info,
            "warning": self.warning,
            "error": self.error,
        }
