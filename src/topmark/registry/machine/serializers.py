# topmark:header:start
#
#   project      : TopMark
#   file         : serializers.py
#   file_relpath : src/topmark/registry/machine/serializers.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Pure serializers for registry machine output.

This module converts *shaped* registry machine-output objects into serialized
wire representations.

Layers:
- `payloads` builds JSON-serializable payload structures.
- `shapes` wraps payloads into canonical JSON envelopes / NDJSON record objects.
- This module serializes those objects:
    - JSON: one pretty-printed JSON string (no trailing newline).
    - NDJSON: an iterable of per-line JSON strings (no trailing newline per item).

Consumers (CLI commands) are responsible for emitting these strings to the active
ConsoleLike (or stdout).
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING

from topmark.core.formats import OutputFormat
from topmark.core.machine.serializers import (
    iter_ndjson_strings,
    serialize_json_object,
)
from topmark.registry.machine.payloads import (
    build_filetypes_payload,
    build_processors_payload,
)
from topmark.registry.machine.shapes import (
    build_filetypes_json_envelope,
    build_processors_json_envelope,
    iter_filetypes_ndjson_records,
    iter_processors_ndjson_records,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from topmark.core.machine.schemas import MetaPayload
    from topmark.registry.machine.schemas import (
        FileTypeBriefEntry,
        FileTypeDetailEntry,
        ProcessorsPayload,
    )


def serialize_filetypes(
    *,
    fmt: OutputFormat,
    meta: MetaPayload,
    show_details: bool,
) -> str | Iterator[str]:
    """Serialize machine output for `topmark filetypes`.

    Args:
        fmt: Target output format (JSON or NDJSON).
        meta: Machine metadata payload.
        show_details: If True, include extended fields.

    Returns:
        - JSON: pretty-printed JSON string (no trailing newline)
        - NDJSON: iterable of JSON strings (one per record; no trailing newline per item)

    Raises:
        ValueError: If `fmt` is not JSON or NDJSON.
    """
    if fmt == OutputFormat.JSON:
        return serialize_filetypes_json(
            meta=meta,
            show_details=show_details,
        )

    if fmt == OutputFormat.NDJSON:
        return serialize_filetypes_ndjson(
            meta=meta,
            show_details=show_details,
        )

    raise ValueError(f"Unsupported machine output format: {fmt!r}")


def serialize_filetypes_json(
    *,
    meta: MetaPayload,
    show_details: bool,
) -> str | Iterator[str]:
    """Serialize machine output for `topmark filetypes`.

    Args:
        meta: Machine metadata payload.
        show_details: If True, include extended fields.

    Returns:
        - JSON: pretty-printed JSON string (no trailing newline)
        - NDJSON: iterable of JSON strings (one per record; no trailing newline per item)
    """
    payload: list[FileTypeBriefEntry | FileTypeDetailEntry] = build_filetypes_payload(
        show_details=show_details,
    )
    envelope: dict[str, object] = build_filetypes_json_envelope(
        meta=meta,
        payload=payload,
    )
    return serialize_json_object(envelope)


def serialize_filetypes_ndjson(
    *,
    meta: MetaPayload,
    show_details: bool,
) -> Iterator[str]:
    """Serialize machine output for `topmark filetypes`.

    Args:
        meta: Machine metadata payload.
        show_details: If True, include extended fields.

    Returns:
        Iterator of JSON strings (one per record; no trailing newline per item)
    """
    payload: list[FileTypeBriefEntry | FileTypeDetailEntry] = build_filetypes_payload(
        show_details=show_details,
    )
    records: Iterator[dict[str, object]] = iter_filetypes_ndjson_records(
        meta=meta,
        payload=payload,
    )
    return iter_ndjson_strings(records)


def serialize_processors(
    *,
    fmt: OutputFormat,
    meta: MetaPayload,
    show_details: bool,
) -> str | Iterator[str]:
    """Serialize machine output for `topmark processors`.

    Args:
        fmt: Target output format (JSON or NDJSON).
        meta: Machine metadata payload.
        show_details: If True, include extended fields.

    Returns:
        - JSON: pretty-printed JSON string (no trailing newline)
        - NDJSON: iterable of JSON strings (one per record; no trailing newline per item)

    Raises:
        ValueError: If `fmt` is not JSON or NDJSON.
    """
    if fmt == OutputFormat.JSON:
        return serialize_processors_json(
            meta=meta,
            show_details=show_details,
        )

    if fmt == OutputFormat.NDJSON:
        return serialize_processors_ndjson(
            meta=meta,
            show_details=show_details,
        )

    raise ValueError(f"Unsupported machine output format: {fmt!r}")


def serialize_processors_json(
    *,
    meta: MetaPayload,
    show_details: bool,
) -> str:
    """Serialize machine output for `topmark processors`.

    Args:
        meta: Machine metadata payload.
        show_details: If True, include extended fields.

    Returns:
        Pretty-printed JSON string (no trailing newline)
    """
    payload: ProcessorsPayload = build_processors_payload(
        show_details=show_details,
    )
    envelope: dict[str, object] = build_processors_json_envelope(
        meta=meta,
        payload=payload,
    )
    return serialize_json_object(envelope)


def serialize_processors_ndjson(
    *,
    meta: MetaPayload,
    show_details: bool,
) -> Iterator[str]:
    """Serialize machine output for `topmark processors`.

    Args:
        meta: Machine metadata payload.
        show_details: If True, include extended fields.

    Returns:
        Iterator of JSON strings (one per record; no trailing newline per item)
    """
    payload: ProcessorsPayload = build_processors_payload(
        show_details=show_details,
    )
    records: Iterator[dict[str, object]] = iter_processors_ndjson_records(
        meta=meta,
        payload=payload,
    )
    return iter_ndjson_strings(records)
