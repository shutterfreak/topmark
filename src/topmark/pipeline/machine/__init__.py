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

This package contains the *pipeline domain* implementation of TopMark's
machine-readable output for `topmark check` and `topmark strip`.

Layers:

- **schemas**: Typed schema fragments for pipeline-specific payloads (static typing only).
- **payloads**: Pure payload builders for the pipeline domain (no `meta`/`kind`, no serialization).
- **envelopes**: Composition of domain payloads and durable-result stream events
  into full machine shapes:
  - JSON envelope (`meta` + `config` + `config_diagnostics` + `results`/`summary`)
  - NDJSON record stream (Pattern A: every record includes `kind` and `meta`)

Design goals:
- Console-/Click-free (safe to reuse from non-CLI frontends).
- Stream lifecycle validation separated from payload shaping (stable shapes, consistent output).
- Shared conventions (keys/kinds/domains, normalization) come from
  [`topmark.core.machine`][topmark.core.machine].

Notes:
    Typed payload schemas, payloads, envelopes, and stream events are available from:
    - [`topmark.pipeline.machine.schemas`][topmark.pipeline.machine.schemas]
    - [`topmark.pipeline.machine.payloads`][topmark.pipeline.machine.payloads]
    - [`topmark.pipeline.machine.envelopes`][topmark.pipeline.machine.envelopes]
    - [`topmark.pipeline.machine.streaming`][topmark.pipeline.machine.streaming]
    Callers can be explicit about which layer they depend on.

See Also:
- [`topmark.core.machine`][topmark.core.machine]: shared machine-readable output primitives
  (keys/kinds/domains, envelopes/records, normalization, JSON/NDJSON serialization helpers).
"""

from __future__ import annotations
