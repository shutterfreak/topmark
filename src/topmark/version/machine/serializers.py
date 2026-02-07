# topmark:header:start
#
#   project      : TopMark
#   file         : serializers.py
#   file_relpath : src/topmark/version/machine/serializers.py
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
- [`topmark.version.machine.payloads`][topmark.version.machine.payloads] builds payload objects
    (domain data, no envelope).
- [`topmark.version.machine.shapes`][topmark.version.machine.shapes] builds envelopes/records
    (adds meta/kind/container keys).
- This module serializes those shapes to JSON/NDJSON strings.

Conventions:
- `json.dumps()` does not append a trailing newline.
- `serialize_ndjson()` returns a string that *does* end with a final `\\n`,
  which is convenient for CLI printing and piping.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.core.formats import OutputFormat
from topmark.core.machine.schemas import MachineKey, MetaPayload
from topmark.core.machine.serializers import serialize_json_envelope, serialize_ndjson
from topmark.version.machine.payloads import build_version_payload
from topmark.version.machine.shapes import iter_version_ndjson_records

if TYPE_CHECKING:
    from collections.abc import Iterator


def serialize_version(
    *,
    meta: MetaPayload,
    fmt: OutputFormat,
    semver: bool,
) -> str | Iterator[str]:
    """Serialize `topmark version` output in machine-readable JSON/NDJSON form.

    JSON envelope:
        `{"meta": {...}, "version_info": {"version": "...", "version_format": "..."}}`

    NDJSON stream:
        1) `{"kind": "version", "meta": {...}, "version": {...}}`
        2) Optional diagnostic record if SemVer conversion failed and a fallback occurred.

    Args:
        meta: Metadata payload (tool/version).
        fmt: Output format. Only JSON and NDJSON are supported here.
        semver: Whether to attempt SemVer conversion of the tool version.

    Returns:
        Serialized JSON string or or NDJSON string iterable.

    Raises:
        ValueError: If `fmt` is not JSON or NDJSON.
    """
    if fmt == OutputFormat.JSON:
        return serialize_version_json(meta=meta, semver=semver)

    if fmt == OutputFormat.NDJSON:
        return serialize_version_ndjson(meta=meta, semver=semver)

    # Defensive guard
    raise ValueError(f"Unsupported machine output format: {fmt!r}")


def serialize_version_json(
    *,
    meta: MetaPayload,
    semver: bool,
) -> str:
    """Serialize `topmark version` output in machine-readable JSON/NDJSON form.

    JSON envelope:
        `{"meta": {...}, "version_info": {"version": "...", "version_format": "..."}}`

    Args:
        meta: Metadata payload (tool/version).
        semver: Whether to attempt SemVer conversion of the tool version.

    Returns:
        Serialized NDJSON string.
    """
    payload, _err = build_version_payload(semver=semver)
    return serialize_json_envelope(
        meta=meta,
        **{MachineKey.VERSION_INFO: payload},
    )


def serialize_version_ndjson(
    *,
    meta: MetaPayload,
    semver: bool,
) -> Iterator[str]:
    """Serialize `topmark version` output in machine-readable JSON/NDJSON form.

    NDJSON stream:
        1) `{"kind": "version", "meta": {...}, "version": {...}}`
        2) Optional diagnostic record if SemVer conversion failed and a fallback occurred.

    Args:
        meta: Metadata payload (tool/version).
        semver: Whether to attempt SemVer conversion of the tool version.

    Yields:
        Serialized JSON string.
    """
    records: Iterator[dict[str, object]] = iter_version_ndjson_records(meta=meta, semver=semver)
    yield serialize_ndjson(records)
