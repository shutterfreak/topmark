# topmark:header:start
#
#   project      : TopMark
#   file         : __init__.py
#   file_relpath : src/topmark/registry/machine/__init__.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Machine-output support for registry-related TopMark commands.

This package implements the machine-readable JSON/NDJSON output shapes for
commands that expose TopMark’s internal registries, such as:

- `topmark filetypes`
- `topmark processors`

The design follows TopMark’s general machine-output layering:

1) **Schema types** (`schemas.py`)
   TypedDict-based types describing the payload shapes emitted by registry commands.

2) **Payload builders** (`payloads.py`)
   Pure, deterministic builders that convert runtime registry objects into
   JSON-serializable Python structures (dicts/lists). These functions are
   Click-free, Console-free, and do not serialize JSON.

3) **Shape builders** (`shapes.py`)
   Wrap payloads into canonical TopMark machine envelopes:
   - JSON envelope: `{"meta": ..., <payload_key>: ...}`
   - NDJSON record: `{"kind": ..., "meta": ..., <container_key>: ...}`

4) **Serializers** (`serializers.py`)
   Convert shaped envelopes/records into JSON/NDJSON strings without printing.
   CLI commands are responsible for emitting serialized strings to the active console.

This package intentionally does not depend on Click and does not print to the console.

Notes:
    This package intentionally re-exports only the shared serializer façade
    (`serialize_filetypes`, `serialize_processors`).
    Typed payload schemas, payloads and shapes remain available from
    [`topmark.registry.machine.schemas`][topmark.registry.machine.schemas],
    [`topmark.registry.machine.payloads`][topmark.registry.machine.payloads] and
    [`topmark.registry.machine.shapes`][topmark.registry.machine.shapes],
    so callers can be explicit about which layer they depend on.

See Also:
- [`topmark.core.machine`][topmark.core.machine]: shared machine-output primitives
  (keys/kinds/domains, envelopes/records, normalization, JSON/NDJSON serialization helpers).
"""

from __future__ import annotations

from topmark.registry.machine.serializers import (
    serialize_filetypes,
    serialize_processors,
)

__all__ = [
    "serialize_filetypes",
    "serialize_processors",
]
