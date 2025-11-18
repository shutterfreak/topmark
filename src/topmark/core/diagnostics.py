# topmark:header:start
#
#   project      : TopMark
#   file         : diagnostics.py
#   file_relpath : src/topmark/core/diagnostics.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Diagnostics support."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import cast

from yachalk import chalk


class DiagnosticLevel(Enum):
    """Severity levels for diagnostics collected during processing.

    Levels map to terminal colors and are ordered by importance: ERROR > WARNING > INFO.
    This enum is **internal**; the public API exposes string literals.
    """

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"

    @property
    def color(self) -> Callable[[str], str]:
        """Return the `yachalk` color function associated with this severity level.

        Intended for human-readable output only; machine formats should not use colors.

        Returns:
            Callable[[str], str]: The `yachalk` color function associated with this severity level.
        """
        return cast(
            "Callable[[str], str]",
            {
                DiagnosticLevel.INFO: chalk.blue,
                DiagnosticLevel.WARNING: chalk.yellow,
                DiagnosticLevel.ERROR: chalk.red_bright,
            }[self],
        )


@dataclass(frozen=True)
class Diagnostic:
    """Internal structured diagnostic with a severity level and message.

    Note:
        This type is **not** part of the public API surface. Conversions to
        `PublicDiagnostic` happen at the API boundary.
    """

    level: DiagnosticLevel
    message: str


@dataclass(frozen=True)
class DiagnosticStats:
    """Aggregated counts for diagnostics by severity level."""

    n_info: int
    n_warning: int
    n_error: int

    @property
    def total(self) -> int:
        """Return the total count of diagnostics."""
        return self.n_info + self.n_warning + self.n_error


def compute_diagnostic_stats(diags: Sequence[Diagnostic]) -> DiagnosticStats:
    """Return per-level counts for a sequence of diagnostics."""
    n_info: int = sum(1 for d in diags if d.level == DiagnosticLevel.INFO)
    n_warn: int = sum(1 for d in diags if d.level == DiagnosticLevel.WARNING)
    n_err: int = sum(1 for d in diags if d.level == DiagnosticLevel.ERROR)
    return DiagnosticStats(n_info=n_info, n_warning=n_warn, n_error=n_err)
