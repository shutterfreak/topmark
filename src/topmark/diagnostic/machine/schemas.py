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
from enum import Enum
from typing import TYPE_CHECKING

from topmark.diagnostic.model import DiagnosticStats
from topmark.diagnostic.model import compute_diagnostic_stats

if TYPE_CHECKING:
    from collections.abc import Iterable

    from topmark.diagnostic.model import Diagnostic


class DiagnosticKey(str, Enum):
    """Stable keys used by diagnostic machine-output payloads.

    These keys belong to the shared diagnostic domain and are reused by other
    machine-output packages when embedding lists of diagnostics or aggregate
    diagnostic counts.

    Attributes:
        DIAGNOSTIC_COUNTS: Container key for aggregate per-level counts.
        DIAGNOSTICS: Container key for a list of diagnostic entries.
        LEVEL: Severity level field for a single diagnostic entry.
        MESSAGE: Human-readable diagnostic text for a single entry.
        INFO: Count key for info-level diagnostics.
        WARNING: Count key for warning-level diagnostics.
        ERROR: Count key for error-level diagnostics.
    """

    # diagnostics (cross-domain)
    DIAGNOSTIC_COUNTS = "diagnostic_counts"
    DIAGNOSTICS = "diagnostics"
    LEVEL = "level"
    MESSAGE = "message"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class DiagnosticKind(str, Enum):
    """Stable NDJSON record kinds owned by the diagnostic domain.

    Attributes:
        DIAGNOSTIC: One diagnostic record in an NDJSON stream.
    """

    DIAGNOSTIC = "diagnostic"


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
            DiagnosticKey.LEVEL.value: self.level,
            DiagnosticKey.MESSAGE.value: self.message,
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
            DiagnosticKey.INFO.value: self.info,
            DiagnosticKey.WARNING.value: self.warning,
            DiagnosticKey.ERROR.value: self.error,
        }
