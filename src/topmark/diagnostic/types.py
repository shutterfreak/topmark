# topmark:header:start
#
#   project      : TopMark
#   file         : types.py
#   file_relpath : src/topmark/diagnostic/types.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Shared typing helpers for TopMark diagnostics.

This module defines small Protocols used to express "diagnostic-carrying"
objects structurally. It allows code to accept either mutable or frozen
containers (e.g., `DiagnosticLog` or `FrozenDiagnosticLog`) without depending
on concrete classes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Iterator

    from topmark.diagnostic.model import (
        Diagnostic,
        DiagnosticStats,
    )


class DiagnosticsLike(Protocol):
    """Structural interface for objects that carry diagnostics."""

    def __iter__(self) -> Iterator[Diagnostic]:
        """Iterate over contained diagnostics in insertion order."""
        ...

    def stats(self) -> DiagnosticStats:
        """Return aggregated per-level counts for the contained diagnostics."""
        ...

    def to_dict(self) -> dict[str, int]:
        """Return a JSON-friendly mapping of counts by severity."""
        ...
