# topmark:header:start
#
#   project      : TopMark
#   file         : __init__.py
#   file_relpath : src/topmark/version/machine/__init__.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Machine-output helpers for version commands.

This package contains the *version domain* implementation of TopMark’s
machine-readable output for `topmark version`.

Layers:

- **schemas**: Typed schema fragments for version-specific payloads (static typing only).
- **payloads**: Pure payload builders for the version domain (no `meta`/`kind`, no serialization).
- **shapes**: Composition of domain payloads into full machine shapes:
  - JSON envelope (`meta` + version payloads)
  - NDJSON record stream (Pattern A: every record includes `kind` and `meta`)
- **serializers**: Pure JSON/NDJSON helpers that turn shaped objects/records into strings
  (no Click/Console printing).

Notes:
    This package intentionally re-exports only the shared serializer façade
    (`serialize_version`).
    Typed payload schemas, payloads and shapes remain available from
    [`topmark.version.machine.schemas`][topmark.version.machine.schemas],
    [`topmark.version.machine.payloads`][topmark.version.machine.payloads] and
    [`topmark.version.machine.shapes`][topmark.version.machine.shapes],
    so callers can be explicit about which layer they depend on.

See Also:
- [`topmark.core.machine`][topmark.core.machine]: shared machine-output primitives
  (keys/kinds/domains, envelopes/records, normalization, JSON/NDJSON serialization helpers).
"""

from __future__ import annotations

from topmark.version.machine.serializers import serialize_version

__all__ = [
    "serialize_version",
]
