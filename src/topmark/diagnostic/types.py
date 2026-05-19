# topmark:header:start
#
#   project      : TopMark
#   file         : types.py
#   file_relpath : src/topmark/diagnostic/types.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Structural typing helpers for TopMark diagnostic containers.

This module defines small protocols for code that only needs to observe
contained diagnostics and aggregated counts. The protocols allow callers to
accept mutable or frozen diagnostic containers without depending on concrete
implementations such as
[`MutableDiagnosticLog`][topmark.diagnostic.model.MutableDiagnosticLog] or
[`FrozenDiagnosticLog`][topmark.diagnostic.model.FrozenDiagnosticLog].
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Protocol

if TYPE_CHECKING:
    from collections.abc import Iterator
    from collections.abc import Mapping

    from topmark.diagnostic.model import Diagnostic
    from topmark.diagnostic.model import DiagnosticStats


class DiagnosticsLike(Protocol):
    """Read-only structural interface for diagnostic containers."""

    def __iter__(self) -> Iterator[Diagnostic]:
        """Iterate over contained diagnostics in insertion order."""
        ...

    def stats(self) -> DiagnosticStats:
        """Return aggregated per-level counts for the contained diagnostics."""
        ...

    def to_dict(self) -> Mapping[str, int]:
        """Return a read-only JSON-friendly mapping of counts by severity."""
        ...
