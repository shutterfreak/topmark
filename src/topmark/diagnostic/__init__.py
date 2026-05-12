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
    - Internal diagnostics are represented by immutable
      [`Diagnostic`][topmark.diagnostic.model.Diagnostic] instances.
    - During processing, diagnostics are accumulated in a mutable
      [`MutableDiagnosticLog`][topmark.diagnostic.model.MutableDiagnosticLog].
    - Frozen snapshots (e.g. [`FrozenConfig`][topmark.config.model.FrozenConfig])
      store diagnostics as an immutable
      [`FrozenDiagnosticLog`][topmark.diagnostic.model.FrozenDiagnosticLog].

Machine-readable output:
    Machine-readable JSON/NDJSON representations live under
    [`topmark.diagnostic.machine`][topmark.diagnostic.machine]
    and are reused by multiple domains (config, pipeline, registry, etc.).
"""

from __future__ import annotations
