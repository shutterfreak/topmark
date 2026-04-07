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

This package contains the *version domain* implementation of TopMark's
machine-readable output for `topmark version`.

Layers:

- **schemas**: Typed schema fragments for version-specific payloads (static typing only)
- **payloads**: Pure payload builders for the version domain (no `meta`/`kind`, no serialization) -
  [`topmark.version.machine.payloads`][topmark.version.machine.payloads]
- **envelopes**: Composition of domain payloads into full machine envelopes -
  [`topmark.version.machine.envelopes`][topmark.version.machine.envelopes]:
  - JSON envelope (`meta` + version payloads)
  - NDJSON record stream (Pattern A: every record includes `kind` and `meta`)
- **serializers**: Pure JSON/NDJSON helpers that turn shaped objects/records into strings
  (no Click/Console printing) -
  [`topmark.version.machine.serializers`][topmark.version.machine.serializers]

See Also:
- [`topmark.core.machine`][topmark.core.machine]: shared machine-output primitives
  (keys/kinds/domains, envelopes/records, normalization, JSON/NDJSON serialization helpers).
"""

from __future__ import annotations
