# topmark:header:start
#
#   project      : TopMark
#   file         : emitters.py
#   file_relpath : src/topmark/core/machine/emitters.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Pure JSON/NDJSON serialization helpers for TopMark machine output.

This module is intentionally console- and Click-free: it takes already-shaped
payload mappings/objects and produces serialized strings.
These helpers only perform serialization and do not shape records.

Responsibilities:
- JSON: build and serialize a single "envelope" object.
- NDJSON: serialize a stream of record mappings as newline-delimited JSON.

The shaping of envelopes/records (e.g., adding `kind`/`meta`, payload names,
normalizing values) lives in [`topmark.core.machine.formats`][topmark.core.machine.formats].
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from topmark.core.machine.formats import MetaPayload, build_json_envelope

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Mapping


def serialize_json_envelope(meta: MetaPayload, **payloads: object) -> str:
    """Serialize a JSON envelope.

    Args:
        meta (MetaPayload): Metadata payload (tool/version).
        **payloads (object): One or more named payload objects (may be dict-like
            or expose `to_dict()`).

    Returns:
        str: A pretty-printed JSON string.
    """
    envelope: dict[str, object] = build_json_envelope(
        meta=meta,
        **payloads,
    )
    return json.dumps(envelope, indent=2)


def iter_ndjson_strings(records: Iterable[Mapping[str, object]]) -> Iterator[str]:
    r"""Serialize an iterable of NDJSON records.

    Each input item must already be a fully shaped record mapping (typically
    produced by `topmark.core.machine.formats.build_ndjson_record`).

    Args:
        records (Iterable[Mapping[str, object]]): Iterable of NDJSON record mappings.

    Yields:
        str: A JSON-serialized string for a single record.
    """
    for record in records:
        yield json.dumps(record)


def serialize_ndjson(records: Iterable[Mapping[str, object]]) -> str:
    """Serialize NDJSON records to a single newline-delimited string.

    Args:
        records (Iterable[Mapping[str, object]]): Iterable of NDJSON record mappings.

    Returns:
        str: JSON string representation of the NDJSON records.
    """
    return "\n".join(iter_ndjson_strings(records)) + "\n"
