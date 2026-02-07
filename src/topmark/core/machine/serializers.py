# topmark:header:start
#
#   project      : TopMark
#   file         : serializers.py
#   file_relpath : src/topmark/core/machine/serializers.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

r"""Pure JSON/NDJSON serialization utilities for machine output.

This module converts *already-shaped* machine output objects (envelopes or NDJSON
record mappings) into strings.

It is intentionally:
- Console-free (no `ConsoleLike`, no printing)
- Click-free
- side-effect-free (serialization only)

Separation of concerns:
- [`topmark.core.machine.payloads`][topmark.core.machine.payloads] builds payload objects
    (domain data, no envelope).
- [`topmark.core.machine.shapes`][topmark.core.machine.shapes] builds envelopes/records
    (adds meta/kind/container keys).
- This module serializes those shapes to JSON/NDJSON strings.

Conventions:
- `json.dumps()` does not append a trailing newline.
- `serialize_ndjson()` returns a string that *does* end with a final `\\n`,
  which is convenient for CLI printing and piping.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import TYPE_CHECKING

from topmark.core.machine.schemas import (
    MetaPayload,
    normalize_payload,
)
from topmark.core.machine.shapes import (
    build_json_envelope,
)

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping


def serialize_json_object(obj: object) -> str:
    """Serialize an object to pretty-printed JSON (no trailing newline).

    Args:
        obj: The object to serialize.

    Returns:
        A pretty-printed JSON string (no trailing newline).
    """
    normalized: object = normalize_payload(obj)
    # json.dumps() doesn't append a trailing newline
    return json.dumps(normalized, indent=2)


def serialize_json_envelope(meta: MetaPayload, **payloads: object) -> str:
    """Serialize a JSON envelope with `meta` plus named payloads.

    Args:
        meta: Metadata payload (tool/version).
        **payloads: Named payload objects. Each value may be a dict-like object or
            an object exposing `to_dict()`.

    Returns:
        Pretty-printed JSON string (no trailing newline).
    """
    envelope: dict[str, object] = build_json_envelope(
        meta=meta,
        **payloads,
    )
    # json.dumps() doesn't append a trailing newline
    return serialize_json_object(envelope)


def iter_ndjson_strings(records: Iterator[Mapping[str, object]]) -> Iterator[str]:
    r"""Serialize shaped NDJSON records into per-line JSON strings.

    Each record mapping must already include its envelope (typically `"kind"` and `"meta"`).

    Args:
        records: Iterator of shaped NDJSON record mappings.

    Yields:
        One JSON string per record (no trailing newline).
    """
    for record in records:
        # json.dumps() doesn't append a trailing newline
        yield json.dumps(record)


def serialize_ndjson(records: Iterator[Mapping[str, object]]) -> str:
    """Serialize NDJSON record mappings into a newline-delimited string.

    Args:
        records: Iterator of shaped NDJSON record mappings.

    Returns:
        A string containing one JSON object per line, ending with a trailing newline.
    """
    return "\n".join(iter_ndjson_strings(records)) + "\n"
