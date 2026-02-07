# topmark:header:start
#
#   project      : TopMark
#   file         : shapes.py
#   file_relpath : src/topmark/diagnostic/machine/shapes.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""NDJSON shape builders for diagnostic machine output.

This module defines shared helpers for emitting diagnostics as **NDJSON records**
according to TopMark's machine-output contract.

Scope:
    - Build one NDJSON record per diagnostic (`kind="diagnostic"`).
    - Attach shared `meta` information and a stable `domain` identifier
      (e.g. `"config"` or `"pipeline"`).
    - Remain independent of any concrete diagnostic container by relying on
      the structural `DiagnosticsLike` protocol.

Design notes:
    - This module operates on *internal* diagnostics (`Diagnostic`) and is
      intentionally decoupled from JSON payload schemas such as
      `MachineDiagnosticEntry`, which are used only for JSON envelopes.
    - NDJSON records are yielded as plain mappings; serialization to strings
      is handled at a higher layer.
    - The helpers here are reused by multiple domains (config, pipeline, etc.)
      to guarantee consistent diagnostic streaming semantics.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.core.machine.schemas import (
    MachineKey,
    MachineKind,
    MetaPayload,
)
from topmark.core.machine.shapes import build_ndjson_record
from topmark.diagnostic.types import DiagnosticsLike

if TYPE_CHECKING:
    from collections.abc import Iterator

    from topmark.diagnostic.types import DiagnosticsLike


def iter_diagnostic_ndjson_records(
    *,
    meta: MetaPayload,
    domain: str,
    diagnostics: DiagnosticsLike,
) -> Iterator[dict[str, object]]:
    """Yield one NDJSON diagnostic record per internal diagnostic.

    Notes:
        This helper is shared across multiple domains (config, pipeline, etc.) to
        ensure diagnostic streaming is consistent.

    Args:
        meta: Shared metadata payload.
        domain: Stable domain identifier (e.g. `MachineDomain.CONFIG`).
        diagnostics: Diagnostic container yielding internal `Diagnostic` objects.

    Yields:
        One mapping per diagnostic. Each mapping is shaped as an NDJSON record with
        `kind="diagnostic"`, `meta=<MetaPayload>`, and a payload containing the
        keys `"domain"`, `"level"`, and `"message"`.
    """

    def _level_to_str(level_obj: object) -> str:
        if isinstance(level_obj, str):
            return level_obj
        # Accept Enum-like values (e.g. DiagnosticLevel).
        value: object = getattr(level_obj, "value", None)
        if isinstance(value, str):
            return value
        # Last resort: keep output stable even for unexpected objects.
        return str(level_obj)

    for d in diagnostics:
        level_obj: object = getattr(d, "level", "")
        msg_obj: object = getattr(d, "message", "")
        yield build_ndjson_record(
            kind=MachineKind.DIAGNOSTIC,
            meta=meta,
            payload={
                MachineKey.DOMAIN: domain,
                MachineKey.LEVEL: _level_to_str(level_obj),
                MachineKey.MESSAGE: str(msg_obj),
            },
        )
