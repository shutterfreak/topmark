# topmark:header:start
#
#   project      : TopMark
#   file         : __init__.py
#   file_relpath : src/topmark/diagnostic/__init__.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Diagnostic primitives and helpers.

This package provides internal, strongly-typed diagnostic objects used throughout TopMark to report
informational messages, warnings, and errors in a consistent way.

Design:
    - Internal diagnostics are represented by immutable `Diagnostic` instances.
    - During processing, diagnostics are accumulated in a mutable `DiagnosticLog`.
    - Frozen snapshots (e.g. `Config`) store diagnostics as an immutable
      `FrozenDiagnosticLog`.

Machine output:
    Machine-readable JSON/NDJSON representations live under
    [`topmark.diagnostic.machine`][topmark.diagnostic.machine]
    and are reused by multiple domains (config, pipeline, registry, etc.).
"""

from __future__ import annotations

from topmark.diagnostic.model import (
    Diagnostic,
    DiagnosticLevel,
    DiagnosticLog,
    DiagnosticStats,
    FrozenDiagnosticLog,
    compute_diagnostic_stats,
    diagnostics_counts_to_dict,
)
from topmark.diagnostic.types import DiagnosticsLike

__all__ = [
    "Diagnostic",
    "DiagnosticLevel",
    "DiagnosticLog",
    "DiagnosticStats",
    "DiagnosticsLike",
    "FrozenDiagnosticLog",
    "compute_diagnostic_stats",
    "diagnostics_counts_to_dict",
]
