# topmark:header:start
#
#   project      : TopMark
#   file         : shapes.py
#   file_relpath : src/topmark/core/machine/shapes.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Envelope and record shaping utilities for machine output.

This module defines *shape builders* for TopMark machine output:
- JSON envelopes (single JSON objects) containing `"meta"` plus named payloads.
- NDJSON record objects containing `"kind"`, `"meta"`, and a payload container.

This module is intentionally:
- Console-free (no printing)
- Click-free
- serialization-free (no `json.dumps`)

Where things live:
- [`topmark.core.machine.payloads`][topmark.core.machine.payloads]: build *payload* objects
    (domain data).
- [`topmark.core.machine.shapes`][topmark.core.machine.shapes]: build *envelopes/records*
    around payloads.
- [`topmark.core.machine.serializers`][topmark.core.machine.serializers]: serialize
    envelopes/records to strings.

NDJSON convention (Pattern A):
- Every record includes `"kind"` and `"meta"`.
- Prefer omitting `container_key` so the container key equals `kind`.
"""

from __future__ import annotations

from topmark.core.machine.schemas import (
    MachineKey,
    MetaPayload,
    normalize_payload,
)


def build_json_envelope(
    *,
    meta: MetaPayload,
    **payloads: object,
) -> dict[str, object]:
    """Build a JSON envelope with `meta` plus one or more named payloads.

    Args:
        meta: Metadata payload (tool/version).
        **payloads: One or more named payload objects.

    Returns:
        JSON-serializable envelope dict.
    """
    out: dict[str, object] = {MachineKey.META: dict(meta)}
    for name, payload in payloads.items():
        out[name] = normalize_payload(payload)
    return out


def build_ndjson_record(
    *,
    kind: str,
    meta: MetaPayload,
    container_key: str | None = None,
    payload: object,
) -> dict[str, object]:
    """Build a single NDJSON record with a uniform envelope (Pattern A).

    Shape:
        `{"kind": <kind>, "meta": <meta>, <container_key>: <payload>}`

    Where `<container_key>` defaults to `kind` when omitted.

    Args:
        kind: NDJSON record kind.
        meta: NDJSON payload meta.
        container_key: Optional payload container key; defaults to `kind`.
        payload: The payload object (dict-like or object exposing `.to_dict()`).

    Returns:
        NDJSON record dict in canonical envelope shape.

    Notes:
        This function does **not** serialize to JSON; see `serializers.py`.
    """
    # Ensure JSON object keys are strings and keep the envelope uniform.
    resolved_payload_name: str = container_key if container_key else kind
    record: dict[str, object] = {
        MachineKey.KIND: kind,
        MachineKey.META: dict(meta),
        resolved_payload_name: normalize_payload(
            payload
        ),  # payload may be a dict or an object with to_dict()
    }
    return record
