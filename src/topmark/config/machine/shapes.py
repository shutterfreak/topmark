# topmark:header:start
#
#   project      : TopMark
#   file         : shapes.py
#   file_relpath : src/topmark/config/machine/shapes.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Shape builders for config-related machine output.

Shapes are small, JSON-friendly Python mappings that follow TopMark's machine
output conventions:

- JSON: a single envelope object containing `meta` plus one or more named payloads.
- NDJSON: one JSON object per line, each carrying the `kind` and `meta` envelope.

This module is pure (no I/O, no `ConsoleLike`) and delegates payload construction
to [`topmark.config.machine.payloads`][topmark.config.machine.payloads].
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING

from topmark.config.machine.payloads import (
    build_config_check_summary_payload,
    build_config_diagnostics_payload,
    build_config_payload,
)
from topmark.config.machine.schemas import (
    ConfigDiagnosticsPayload,
    ConfigPayload,
)
from topmark.config.model import Config
from topmark.core.machine.schemas import (
    MachineDomain,
    MachineKey,
    MachineKind,
    MetaPayload,
)
from topmark.core.machine.shapes import (
    build_json_envelope,
    build_ndjson_record,
)
from topmark.diagnostic.machine.shapes import iter_diagnostic_ndjson_records

if TYPE_CHECKING:
    from collections.abc import Iterator

    from topmark.config.machine.schemas import (
        ConfigDiagnosticsPayload,
        ConfigPayload,
    )
    from topmark.config.model import Config
    from topmark.core.machine.schemas import MetaPayload
    from topmark.diagnostic.machine.schemas import MachineDiagnosticCounts


# -- JSON shapes --
def build_config_json_envelope(
    *,
    config: Config,
    meta: MetaPayload,
) -> dict[str, object]:
    """Build the JSON envelope for a Config snapshot.

    Shape:
        {"meta": <MetaPayload>, "config": <ConfigPayload>}

    Args:
        config: Immutable runtime configuration to serialize.
        meta: Machine-output metadata (tool/version).

    Returns:
        A JSON-envelope mapping (not yet serialized).
    """
    payload: ConfigPayload = build_config_payload(config)
    return build_json_envelope(meta=meta, config=payload)


def iter_config_ndjson_records(
    *,
    config: Config,
    meta: MetaPayload,
) -> Iterator[dict[str, object]]:
    """Iterate NDJSON records for a Config snapshot.

    Shape (single record):
        {"kind": "config", "meta": <MetaPayload>, "config": <ConfigPayload>}

    Args:
        config: Immutable runtime configuration to serialize.
        meta: Machine-output metadata (tool/version).

    Yields:
        An iterable of NDJSON record mappings (not yet serialized).
    """
    payload: ConfigPayload = build_config_payload(config)
    yield build_ndjson_record(
        kind=MachineKind.CONFIG,
        meta=meta,
        payload=payload,
    )


def build_config_diagnostics_json_envelope(
    *,
    config: Config,
    meta: MetaPayload,
) -> dict[str, object]:
    """Build the JSON envelope for config diagnostics.

    Shape:
        {"meta": <MetaPayload>, "config_diagnostics": <ConfigDiagnosticsPayload>}

    Args:
        config: Immutable runtime configuration providing diagnostics.
        meta: Machine-output metadata (tool/version).

    Returns:
        A JSON-envelope mapping (not yet serialized).
    """
    payload: ConfigDiagnosticsPayload = build_config_diagnostics_payload(config)
    return build_json_envelope(meta=meta, config_diagnostics=payload)


def iter_config_diagnostics_ndjson_records(
    *,
    config: Config,
    meta: MetaPayload,
) -> Iterator[dict[str, object]]:
    """Iterate NDJSON records for config diagnostics.

    Shapes:
      - counts-only record:
            {"kind": "config_diagnostics", "meta": ...,
            "config_diagnostics": {"diagnostic_counts": ...}}
      - one `diagnostic` record per entry (domain="config")

    Args:
        config: Immutable runtime configuration providing diagnostics.
        meta: Machine-output metadata (tool/version).

    Yields:
        TODO update - An iterable of NDJSON record mappings (not yet serialized).
    """
    payload: ConfigDiagnosticsPayload = build_config_diagnostics_payload(config)

    # NDJSON counts-only + streamed diagnostics
    counts: MachineDiagnosticCounts = payload.diagnostic_counts

    yield build_ndjson_record(
        kind=MachineKind.CONFIG_DIAGNOSTICS,
        meta=meta,
        payload={
            MachineKey.DIAGNOSTIC_COUNTS: counts.to_dict(),
        },
    )
    # One diagnostic per line
    yield from iter_diagnostic_ndjson_records(
        meta=meta,
        domain=MachineDomain.CONFIG,
        diagnostics=config.diagnostics,
    )


def build_config_check_json_envelope(
    *,
    config: Config,
    meta: MetaPayload,
    strict: bool,
    ok: bool,
) -> dict[str, object]:
    """Build the JSON envelope for `topmark config check`.

    Shape:
        {"meta": ..., "config": ..., "config_diagnostics": ..., "summary": ...}

    Args:
        config: Immutable runtime configuration.
        meta: Machine-output metadata (tool/version).
        strict: Whether warnings are treated as failures.
        ok: Whether the config passed validation.

    Returns:
        A JSON-envelope mapping (not yet serialized).
    """
    cfg_diag_payload: ConfigDiagnosticsPayload = build_config_diagnostics_payload(config)
    cfg_payload: ConfigPayload = build_config_payload(config)

    summary: dict[str, object] = build_config_check_summary_payload(
        config=config,
        cfg_diag_payload=cfg_diag_payload,
        strict=strict,
        ok=ok,
    )

    envelope: dict[str, object] = build_json_envelope(
        meta=meta,
        config=cfg_payload,
        config_diagnostics=cfg_diag_payload,
        summary=summary,
    )
    return envelope


def iter_config_prefix_ndjson_records(
    *,
    config: Config,
    meta: MetaPayload,
    cfg_payload: ConfigPayload | None = None,
    cfg_diag_payload: ConfigDiagnosticsPayload | None = None,
) -> Iterator[dict[str, object]]:
    """Yield the standard NDJSON prefix records for config-aware machine streams.

    Prefix:
      1) `config` record with the effective config snapshot
      2) `config_diagnostics` record containing *counts only*

    Callers that want per-diagnostic records should additionally emit
    `iter_diagnostic_ndjson_records(...)`.

    Args:
        config: Effective configuration instance.
        meta: Shared metadata payload.
        cfg_payload: Optional precomputed `ConfigPayload`.
        cfg_diag_payload: Optional precomputed `ConfigDiagnosticsPayload`.

    Yields:
        NDJSON records for `config` and counts-only `config_diagnostics`.
    """
    payload: ConfigPayload = (
        cfg_payload if cfg_payload is not None else build_config_payload(config)
    )
    diag_payload: ConfigDiagnosticsPayload = (
        cfg_diag_payload
        if cfg_diag_payload is not None
        else build_config_diagnostics_payload(config)
    )
    counts_only: MachineDiagnosticCounts = diag_payload.diagnostic_counts

    yield build_ndjson_record(
        kind=MachineKind.CONFIG,
        meta=meta,
        payload=payload,
    )

    yield build_ndjson_record(
        kind=MachineKind.CONFIG_DIAGNOSTICS,
        meta=meta,
        payload={
            MachineKey.DIAGNOSTIC_COUNTS: counts_only.to_dict(),
        },
    )


def iter_config_check_ndjson_records(
    *,
    config: Config,
    meta: MetaPayload,
    strict: bool,
    ok: bool,
) -> Iterator[dict[str, object]]:
    """Iterate NDJSON records for `topmark config check`.

    Record sequence:
        1) config
        2) config_diagnostics (counts-only)
        3) summary
        4+) diagnostic (domain="config") one per diagnostic

    Args:
        config: Immutable runtime configuration.
        meta: Machine-output metadata (tool/version).
        strict: Whether warnings are treated as failures.
        ok: Whether the config passed validation.

    Yields:
        TODO UPDATE - An iterable of NDJSON record mappings (not yet serialized).
    """
    cfg_diag_payload: ConfigDiagnosticsPayload = build_config_diagnostics_payload(config)
    summary: dict[str, object] = build_config_check_summary_payload(
        config=config,
        cfg_diag_payload=cfg_diag_payload,
        strict=strict,
        ok=ok,
    )

    cfg_payload: ConfigPayload = build_config_payload(config)
    yield from iter_config_prefix_ndjson_records(
        config=config,
        cfg_payload=cfg_payload,
        meta=meta,
        cfg_diag_payload=cfg_diag_payload,
    )

    yield build_ndjson_record(
        kind=MachineKind.SUMMARY,
        meta=meta,
        payload=summary,
    )

    # One diagnostic per line
    yield from iter_diagnostic_ndjson_records(
        meta=meta,
        domain=MachineDomain.CONFIG,
        diagnostics=config.diagnostics,
    )
