# topmark:header:start
#
#   project      : TopMark
#   file         : __init__.py
#   file_relpath : src/topmark/diagnostic/machine/__init__.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Machine-output helpers for diagnostics.

This package contains reusable diagnostic schemas and NDJSON shape builders used
by multiple TopMark domains when emitting machine formats.

Layers:

- **schemas**: Typed payload schemas for JSON envelopes (for example,
  `MachineDiagnosticEntry` and `MachineDiagnosticCounts`).
- **shapes**: NDJSON record builders that operate on internal `Diagnostic`
  objects and yield one record per diagnostic.

Notes:
    This package intentionally re-exports only the shared NDJSON shape helper
    (`iter_diagnostic_ndjson_records`). Typed payload schemas remain available
    from [`topmark.diagnostic.machine.schemas`][topmark.diagnostic.machine.schemas]
    so callers can be explicit about which layer they depend on.

See Also:
- [`topmark.core.machine`][topmark.core.machine]: shared machine-output primitives
  (keys/kinds/domains, envelopes/records, normalization, JSON/NDJSON serialization helpers).
"""

from __future__ import annotations

from topmark.diagnostic.machine.shapes import iter_diagnostic_ndjson_records

# Keep schemas import paths explicit (e.g. "...machine.schemas") to preserve layer intent.

__all__ = [
    "iter_diagnostic_ndjson_records",
]
