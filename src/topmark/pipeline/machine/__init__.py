# topmark:header:start
#
#   project      : TopMark
#   file         : __init__.py
#   file_relpath : src/topmark/pipeline/machine/__init__.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Machine-output helpers for pipeline processing commands.

This package contains the *pipeline domain* implementation of TopMark’s
machine-readable output for `topmark check` and `topmark strip`.

Layers:

- **schemas**: Typed schema fragments for pipeline-specific payloads (static typing only).
- **payloads**: Pure payload builders for the pipeline domain (no `meta`/`kind`, no serialization).
- **shapes**: Composition of domain payloads into full machine shapes:
  - JSON envelope (`meta` + `config` + `config_diagnostics` + `results`/`summary`)
  - NDJSON record stream (Pattern A: every record includes `kind` and `meta`)
- **serializers**: Pure JSON/NDJSON serialization helpers that turn shaped objects/records
  into strings (no Click/Console printing).

Design goals:
- Console-/Click-free (safe to reuse from non-CLI frontends).
- Serialization separated from shaping (stable shapes, consistent output).
- Shared conventions (keys/kinds/domains, normalization) come from
  [`topmark.core.machine`][topmark.core.machine].

Notes:
    This package intentionally re-exports only the shared serializezs
    (`serialize_processing_results`).
    Typed payload schemas, payloads and shapes remain available
    from [`topmark.pipeline.machine.schemas`][topmark.pipeline.machine.schemas],
    [`topmark.pipeline.machine.payloads`][topmark.pipeline.machine.schemas] and
    [`topmark.pipeline.machine.shapes`][topmark.pipeline.machine.schemas],
    so callers can be explicit about which layer they depend on.

See Also:
- [`topmark.core.machine`][topmark.core.machine]: shared machine-output primitives
  (keys/kinds/domains, envelopes/records, normalization, JSON/NDJSON serialization helpers).
"""

from __future__ import annotations

from topmark.pipeline.machine.serializers import serialize_processing_results

__all__ = [
    "serialize_processing_results",
]
