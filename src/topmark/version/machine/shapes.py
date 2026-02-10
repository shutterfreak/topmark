# topmark:header:start
#
#   project      : TopMark
#   file         : shapes.py
#   file_relpath : src/topmark/version/machine/shapes.py
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

from typing import TYPE_CHECKING

from topmark.core.machine.schemas import (
    MachineDomain,
    MachineKey,
    MachineKind,
    MetaPayload,
)
from topmark.core.machine.shapes import build_ndjson_record
from topmark.diagnostic.model import DiagnosticLevel
from topmark.version.machine.payloads import build_version_payload

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping


def build_version_ndjson_record(
    *,
    meta: MetaPayload,
    payload: Mapping[str, object],
) -> dict[str, object]:
    """Build an NDJSON version record for the `version` command.

    Args:
        meta: Metadata payload (tool/version).
        payload: Version payload with version info.

    Returns:
        Shaped NDJSON record mapping:
        `{"kind": "version", "meta": {...}, "version": {...}}`
    """
    return build_ndjson_record(
        kind=MachineKind.VERSION,
        meta=meta,
        payload=payload,
        # Prefer omitting container_key so it defaults to kind ("version").
    )


def build_version_diagnostic_ndjson_record(
    *,
    meta: MetaPayload,
    message: str,
    level: DiagnosticLevel = DiagnosticLevel.WARNING,
) -> dict[str, object]:
    """Build an NDJSON diagnostic record for the `version` command.

    Emitted when SemVer conversion was requested but failed and TopMark fell back
    to the original PEP 440 version string.

    Args:
        meta: Metadata payload (tool/version).
        message: Human-readable diagnostic message.
        level: Diagnostic severity (defaults to WARNING).

    Returns:
        Shaped NDJSON record:
        {"kind": "diagnostic", "meta": {...}, "diagnostic": {...}}
    """
    return build_ndjson_record(
        kind=MachineKind.DIAGNOSTIC,
        meta=meta,
        payload={
            MachineKey.DOMAIN: MachineDomain.VERSION,
            MachineKey.LEVEL: level.value,
            MachineKey.MESSAGE: message,
        },
    )


def iter_version_ndjson_records(
    *,
    meta: MetaPayload,
    semver: bool,
) -> Iterator[dict[str, object]]:
    """Build NDJSON records for `topmark version` (Pattern A).

    Contract: every record includes `kind` and `meta`.

    Records:
      1) kind="version" with payload under key "version"
      2) (optional) kind="diagnostic" if SemVer conversion was requested and failed

    Args:
        meta: Metadata payload (tool/version).
        semver: Whether to attempt SemVer conversion of the tool version.

    Yields:
        Shaped NDJSON record mappings.
    """
    payload, err = build_version_payload(semver=semver)

    yield build_version_ndjson_record(
        meta=meta,
        payload=payload,
    )
    if err is not None:
        yield build_version_diagnostic_ndjson_record(
            meta=meta,
            message=str(err),
        )
