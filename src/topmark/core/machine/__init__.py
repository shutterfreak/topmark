# topmark:header:start
#
#   project      : TopMark
#   file         : __init__.py
#   file_relpath : src/topmark/core/machine/__init__.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

r"""Core machine-output infrastructure.

This package implements TopMark’s canonical JSON/NDJSON machine formats.

Separation of concerns (naming + placement):

1) Schema primitives (keys/kinds/domains + normalization)
   - [`topmark.core.machine.schemas`][topmark.core.machine.schemas]
   - Examples:
     - `MachineKey`, `MachineKind`, `MachineDomain`, `MetaPayload`
     - `normalize_payload(...)`

2) Payload builders (domain data only; no envelope/kind/meta)
   - `topmark.<domain>.machine.payloads`
   - Naming: `build_*_payload(...)`, `iter_*_items(...)`
   - Returns: dataclass / dict / TypedDict (not an envelope)

3) Shape builders (envelopes and NDJSON records; still not serialized)
   - [`topmark.core.machine.shapes`][topmark.core.machine.shapes]
   - Naming:
     - `build_json_envelope(...)` -> dict
     - `build_ndjson_record(...)` -> dict
     - `build_*_json_envelope(...)` / `build_*_ndjson_records(...)`

4) Serialization (turn shapes into strings; no printing)
   - [`topmark.core.machine.serializers`][topmark.core.machine.serializers]
   - Naming:
     - `serialize_*` returns `str`
     - `iter_*_strings` yields per-record strings
   - Notes:
     - `json.dumps()` does not add a trailing newline.
     - `serialize_ndjson(...)` returns a string that ends with `\\n`.

5) CLI emission (printing to ConsoleLike / stdout)
   - Lives under `topmark.cli.*`
   - Naming:
     - reserve `emit_*` for side-effecting “print” operations
     - keep pure functions under `serialize_*` / `build_*`

Rule of thumb:
- If it imports `ConsoleLike` or `click`, it should not live in `core.machine`.
- If it imports `json` only, it is typically a serializer and belongs in `core.machine.serializers`.
"""

from __future__ import annotations

from topmark.core.machine.schemas import (
    MachineDomain,
    MachineKey,
    MachineKind,
    MetaPayload,
)
from topmark.core.machine.serializers import (
    iter_ndjson_strings,
    serialize_json_envelope,
    serialize_json_object,
)
from topmark.core.machine.shapes import (
    build_json_envelope,
    build_ndjson_record,
)

__all__ = [
    "MachineDomain",
    "MachineKey",
    "MachineKind",
    "MetaPayload",
    "build_json_envelope",
    "build_ndjson_record",
    "iter_ndjson_strings",
    "serialize_json_envelope",
    "serialize_json_object",
]
