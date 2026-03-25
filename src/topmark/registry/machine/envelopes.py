# topmark:header:start
#
#   project      : TopMark
#   file         : envelopes.py
#   file_relpath : src/topmark/registry/machine/envelopes.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Envelope/record builders for registry machine output.

This module is responsible for *shaping* registry payloads into TopMark’s
canonical machine-output envelopes.

Layers:
- [`topmark.registry.machine.payloads`][topmark.registry.machine.payloads] builds plain
    JSON-serializable payloads.
- This module wraps those payloads into canonical envelopes / NDJSON record objects.
- [`topmark.registry.machine.serializers`][topmark.registry.machine.serializers] converts shaped
    objects into JSON/NDJSON wire strings.

Conventions:
- JSON: one envelope object:
    `{"meta": ..., <payload_key>: ...}`
- NDJSON: one record per entity:
    `{"kind": <kind>, "meta": ..., <payload>}`

This module is Click-free and console-free.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.core.machine.schemas import MachineKind
from topmark.core.machine.shapes import build_json_envelope
from topmark.core.machine.shapes import build_ndjson_record

if TYPE_CHECKING:
    from collections.abc import Iterator

    from topmark.core.machine.schemas import MetaPayload
    from topmark.registry.machine.schemas import BindingEntry
    from topmark.registry.machine.schemas import BindingsPayload
    from topmark.registry.machine.schemas import FileTypeEntry
    from topmark.registry.machine.schemas import FileTypeRef
    from topmark.registry.machine.schemas import FileTypesPayload
    from topmark.registry.machine.schemas import ProcessorEntry
    from topmark.registry.machine.schemas import ProcessorRef
    from topmark.registry.machine.schemas import ProcessorsPayload


def build_filetypes_json_envelope(
    *,
    meta: MetaPayload,
    payload: FileTypesPayload,
) -> dict[str, object]:
    """Build the JSON envelope for `topmark registry filetypes`.

    Args:
        meta: Machine metadata payload.
        payload: List of file type entries.

    Returns:
        JSON envelope with keys `meta` and `filetypes`.
    """
    return build_json_envelope(
        meta=meta,
        filetypes=payload,
    )


def iter_filetypes_ndjson_records(
    *,
    meta: MetaPayload,
    payload: FileTypesPayload,
) -> Iterator[dict[str, object]]:
    """Iterate NDJSON record objects for `topmark registry filetypes`.

    Produces one `filetype` record per file type entry.

    Args:
        meta: Machine metadata payload.
        payload: List of file type entries.

    Yields:
        NDJSON record objects (not yet serialized to strings).
    """
    for item in payload:
        entry: FileTypeEntry = item
        yield build_ndjson_record(
            kind=MachineKind.FILETYPE,
            meta=meta,
            payload=entry,
        )


def build_processors_json_envelope(
    *,
    meta: MetaPayload,
    payload: ProcessorsPayload,
) -> dict[str, object]:
    """Build the JSON envelope for `topmark registry processors`.

    Args:
        meta: Machine metadata payload.
        payload: Processors payload.

    Returns:
        JSON envelope with keys `meta` and `processors`.
    """
    return build_json_envelope(
        meta=meta,
        processors=payload,
    )


def iter_processors_ndjson_records(
    *,
    meta: MetaPayload,
    payload: ProcessorsPayload,
) -> Iterator[dict[str, object]]:
    """Iterate NDJSON record objects for `topmark registry processors`.

    Emits:
    - one `processor` record per processor entry

    Args:
        meta: Machine metadata payload.
        payload: Processors payload.

    Yields:
        NDJSON record objects (not yet serialized to strings).
    """
    for proc_item in payload["processors"]:
        proc_entry: ProcessorEntry = proc_item
        yield build_ndjson_record(
            kind=MachineKind.PROCESSOR,
            meta=meta,
            payload=proc_entry,
        )


def build_bindings_json_envelope(
    *,
    meta: MetaPayload,
    payload: BindingsPayload,
) -> dict[str, object]:
    """Build the JSON envelope for `topmark registry bindings`.

    Args:
        meta: Machine metadata payload.
        payload: Bindings payload.

    Returns:
        JSON envelope with keys `meta` and `bindings`.
    """
    return build_json_envelope(
        meta=meta,
        bindings=payload,
    )


def iter_bindings_ndjson_records(
    *,
    meta: MetaPayload,
    payload: BindingsPayload,
) -> Iterator[dict[str, object]]:
    """Iterate NDJSON record objects for `topmark registry bindings`.

    Emits:
    - one `binding` record per binding entry
    - one `unbound_filetype` record per unbound file type reference
    - one `unused_processor` record per unused processor reference

    Args:
        meta: Machine metadata payload.
        payload: Bindings payload.

    Yields:
        NDJSON record objects (not yet serialized to strings).
    """
    for binding_item in payload["bindings"]:
        binding_entry: BindingEntry = binding_item
        yield build_ndjson_record(
            kind=MachineKind.BINDING,
            meta=meta,
            payload=binding_entry,
        )

    for uft_item in payload["unbound_filetypes"]:
        uft_entry: FileTypeRef = uft_item
        yield build_ndjson_record(
            kind=MachineKind.UNBOUND_FILETYPE,
            meta=meta,
            payload=uft_entry,
        )

    for unused_item in payload["unused_processors"]:
        proc_entry: ProcessorRef = unused_item
        yield build_ndjson_record(
            kind=MachineKind.UNUSED_PROCESSOR,
            meta=meta,
            payload=proc_entry,
        )
