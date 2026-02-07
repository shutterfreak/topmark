# topmark:header:start
#
#   project      : TopMark
#   file         : model.py
#   file_relpath : src/topmark/diagnostic/model.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Core diagnostic types and helpers for TopMark.

This module defines internal diagnostic primitives used throughout the
project to report informational messages, warnings, and errors. These are
intentionally separate from the public API schemas so that internal
diagnostics can evolve without breaking external contracts.

Sections:
    * DiagnosticLevel: severity levels with associated terminal colors.
    * Diagnostic: immutable structured diagnostic payload (level + message).
    * DiagnosticStats: aggregated per-level counts.
    * DiagnosticLog: mutable per-context collection with helpers for
      adding and summarizing diagnostics.
    * FrozenDiagnosticLog: immutable snapshot container for frozen contexts.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, cast

from yachalk import chalk

from topmark.config.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator

    from topmark.config.logging import TopmarkLogger


logger: TopmarkLogger = get_logger(__name__)


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


@dataclass
class DiagnosticLog:
    """Mutable, per-context collection of diagnostics.

    This wrapper keeps track of all diagnostics emitted during processing
    of a single context. It provides convenience helpers for adding
    diagnostics at a given level and exposes simple aggregation helpers
    (`stats`, `to_dict`) for reporting.
    """

    items: list[Diagnostic] = field(default_factory=lambda: [])

    @classmethod
    def from_iterable(cls, diagnostics: Iterable[Diagnostic]) -> DiagnosticLog:
        """Create a DiagnosticLog from an iterable of diagnostics.

        Args:
            diagnostics: Existing diagnostics (e.g., from a frozen snapshot).

        Returns:
            A new DiagnosticLog containing the provided diagnostics.
        """
        return cls(items=list(diagnostics))

    def freeze(self) -> FrozenDiagnosticLog:
        """Return an immutable snapshot of this log's diagnostics."""
        return FrozenDiagnosticLog(items=tuple(self.items))

    def _add(self, diagnostic: Diagnostic) -> None:
        """Add a diagnostic to the diagnostic log.

        The diagnostic is appended to the context in place.

        Args:
            diagnostic: The diagnostic object.
        """
        self.items.append(diagnostic)
        logger.trace("Adding [%s]: %r", diagnostic.level.value, diagnostic.message)

    def add_info(self, message: str) -> None:
        """Add an ``info`` diagnostic to the diagnostic log.

        The diagnostic is appended to the context in place.

        Args:
            message: The diagnostic message.

        """
        self._add(Diagnostic(DiagnosticLevel.INFO, message))

    def add_warning(self, message: str) -> None:
        """Add a ``warning`` diagnostic to the diagnostic log.

        Args:
            message: The diagnostic message.
        """
        self._add(Diagnostic(DiagnosticLevel.WARNING, message))

    def add_error(self, message: str) -> None:
        """Add an ``error`` diagnostic to the diagnostic log.

        The diagnostic is appended to the context in place.

        Args:
            message: The diagnostic message.
        """
        self._add(Diagnostic(DiagnosticLevel.ERROR, message))

    def stats(self) -> DiagnosticStats:
        """Return per-level counts for diagnostics in this log.

        The returned `DiagnosticStats` object can be used both for human
        summaries and for machine-readable reporting via `to_dict`.
        """
        return compute_diagnostic_stats(self.items)

    def has_info(self) -> bool:
        """Return True if the DiagnosticLog contains info diagnostics."""
        return any(d.level == DiagnosticLevel.INFO for d in self.items)

    def has_warning(self) -> bool:
        """Return True if the DiagnosticLog contains warning diagnostics."""
        return any(d.level == DiagnosticLevel.WARNING for d in self.items)

    def has_error(self) -> bool:
        """Return True if the DiagnosticLog contains error diagnostics."""
        return any(d.level == DiagnosticLevel.ERROR for d in self.items)

    def to_dict(self) -> dict[str, int]:
        """Return a JSON-friendly mapping of counts by severity.

        Returns:
            Mapping with keys ``"info"``, ``"warning"``, and ``"error"``
            reflecting the number of diagnostics at each level.
        """
        return diagnostics_counts_to_dict(self.items)

    def __iter__(self) -> Iterator[Diagnostic]:
        """Iterate over all diagnostics stored in this log.

        Returns:
            An iterator yielding diagnostics in insertion order.
        """
        return iter(self.items)

    def __len__(self) -> int:
        """Return the number of diagnostics stored in this log.

        Returns:
            The number of diagnostic entries.
        """
        return len(self.items)


@dataclass(frozen=True, slots=True)
class FrozenDiagnosticLog:
    """Immutable, per-context diagnostic container.

    `FrozenDiagnosticLog` is the immutable counterpart to `DiagnosticLog`. It is
    intended for storing diagnostics on frozen snapshots (e.g., `Config`) where
    mutation is not permitted.
    """

    items: tuple[Diagnostic, ...]

    def __iter__(self) -> Iterator[Diagnostic]:
        """Iterate over contained diagnostics in insertion order."""
        return iter(self.items)

    def stats(self) -> DiagnosticStats:
        """Return aggregated per-level counts for the contained diagnostics."""
        return compute_diagnostic_stats(self.items)

    def to_dict(self) -> dict[str, int]:
        """Return a JSON-friendly mapping of counts by severity."""
        return diagnostics_counts_to_dict(self.items)


def compute_diagnostic_stats(diagnostics: Iterable[Diagnostic]) -> DiagnosticStats:
    """Return per-level counts for a sequence of diagnostics.

    The returned `DiagnosticStats` object can be used both for human
    summaries and for machine-readable reporting via `to_dict`.

    Args:
        diagnostics: the diagnostic log.

    Returns:
        Per-level counts for diagnostics in this log.
    """
    n_info: int = sum(1 for d in diagnostics if d.level == DiagnosticLevel.INFO)
    n_warn: int = sum(1 for d in diagnostics if d.level == DiagnosticLevel.WARNING)
    n_err: int = sum(1 for d in diagnostics if d.level == DiagnosticLevel.ERROR)
    return DiagnosticStats(n_info=n_info, n_warning=n_warn, n_error=n_err)


def diagnostics_counts_to_dict(diagnostics: Iterable[Diagnostic]) -> dict[str, int]:
    """Return a JSON-friendly mapping of counts by severity for any iterable."""
    stats: DiagnosticStats = compute_diagnostic_stats(diagnostics)
    return {
        "info": stats.n_info,
        "warning": stats.n_warning,
        "error": stats.n_error,
    }
