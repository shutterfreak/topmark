# topmark:header:start
#
#   project      : TopMark
#   file         : serializers.py
#   file_relpath : src/topmark/config/machine/serializers.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end


"""Serialization helpers for config-related machine output.

This module turns *shaped* config records/envelopes into JSON or NDJSON strings.

Responsibilities:
  - Validate that the requested format is a supported machine format.
  - Delegate *shape* construction to
    [`topmark.config.machine.shapes`][topmark.config.machine.shapes].
  - Delegate JSON/NDJSON string rendering to
    [`topmark.core.machine.serializers`][topmark.core.machine.serializers].

This module is intentionally I/O-free: it returns strings (JSON) or iterators of
strings (NDJSON lines) for the CLI layer to print.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.config.machine.shapes import (
    build_config_check_json_envelope,
    build_config_diagnostics_json_envelope,
    build_config_json_envelope,
    iter_config_check_ndjson_records,
    iter_config_diagnostics_ndjson_records,
    iter_config_ndjson_records,
)
from topmark.core.formats import OutputFormat, is_machine_format
from topmark.core.machine.serializers import (
    iter_ndjson_strings,
    serialize_json_object,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from topmark.config.model import Config
    from topmark.core.machine.schemas import MetaPayload


def serialize_config(
    *,
    meta: MetaPayload,
    config: Config,
    fmt: OutputFormat,
) -> str | Iterator[str]:
    """Serialize the effective Config snapshot in a machine-readable format.

    Shapes:
      - JSON: one envelope object: {"meta": ..., "config": ...}
      - NDJSON: one record line: {"kind": "config", "meta": ..., "config": ...}

    Args:
        meta: Machine-output metadata (tool/version).
        config: Immutable runtime configuration to serialize.
        fmt: Target machine format (JSON or NDJSON).

    Returns:
        A pretty-printed JSON string, or an iterator of NDJSON lines, depending on `fmt`
        (no trailing newline).

    Raises:
        ValueError: If `fmt` is not a supported machine format.
    """
    if not is_machine_format(fmt):
        raise ValueError(f"Unsupported machine output format: {fmt!r}")

    if fmt == OutputFormat.JSON:
        return serialize_config_json(
            meta=meta,
            config=config,
        )

    if fmt == OutputFormat.NDJSON:
        return serialize_config_ndjson(
            meta=meta,
            config=config,
        )

    # Defensive guard
    raise ValueError(f"Unsupported machine output format: {fmt!r}")


def serialize_config_json(
    *,
    meta: MetaPayload,
    config: Config,
) -> str:
    """Serialize the effective Config snapshot as a JSON envelope.

    Shape:
        {"meta": <MetaPayload>, "config": <ConfigPayload>}

    Args:
        meta: Machine-output metadata (tool/version).
        config: Immutable runtime configuration to serialize.

    Returns:
        Pretty-printed JSON string (no trailing newline).
    """
    envelope: dict[str, object] = build_config_json_envelope(
        config=config,
        meta=meta,
    )
    return serialize_json_object(envelope)


def serialize_config_ndjson(
    *,
    meta: MetaPayload,
    config: Config,
) -> Iterator[str]:
    """Serialize the effective Config snapshot as NDJSON.

    Shape (single record line):
        {"kind": "config", "meta": <MetaPayload>, "config": <ConfigPayload>}

    Args:
        meta: Machine-output metadata (tool/version).
        config: Immutable runtime configuration to serialize.

    Returns:
        Iterator of NDJSON lines (no trailing newline).
    """
    iter_records: Iterator[dict[str, object]] = iter_config_ndjson_records(
        config=config,
        meta=meta,
    )
    return iter_ndjson_strings(iter_records)


def serialize_config_diagnostics(
    *,
    meta: MetaPayload,
    config: Config,
    fmt: OutputFormat,
) -> str | Iterator[str]:
    """Serialize Config diagnostics in a machine-readable format.

    Shapes:
      - JSON: one envelope object: {"meta": ..., "config_diagnostics": ...}
      - NDJSON: counts-only record + streamed diagnostic records.

    Args:
        meta: Machine-output metadata (tool/version).
        config: Immutable runtime configuration providing diagnostics.
        fmt: Target machine format (JSON or NDJSON).

    Returns:
        Rendered JSON string or iterable of NDJSON lines (no trailing newline).

    Raises:
        ValueError: if `fmt` is not a supported machine format.
    """
    if not is_machine_format(fmt):
        raise ValueError(f"Unsupported machine output format: {fmt!r}")

    if fmt == OutputFormat.JSON:
        return serialize_config_diagnostics_json(
            meta=meta,
            config=config,
        )

    if fmt == OutputFormat.NDJSON:
        return serialize_config_diagnostics_ndjson(
            meta=meta,
            config=config,
        )

    # Defensive guard
    raise ValueError(f"Unsupported machine output format: {fmt!r}")


def serialize_config_diagnostics_json(
    *,
    meta: MetaPayload,
    config: Config,
) -> str:
    """Serialize Config diagnostics as a JSON envelope.

    Shape:
        {"meta": <MetaPayload>, "config_diagnostics": <ConfigDiagnosticsPayload>}

    Args:
        meta: Machine-output metadata (tool/version).
        config: Immutable runtime configuration providing diagnostics.

    Returns:
        Pretty-printed JSON string (no trailing newline).
    """
    envelope: dict[str, object] = build_config_diagnostics_json_envelope(
        config=config,
        meta=meta,
    )
    return serialize_json_object(envelope)


def serialize_config_diagnostics_ndjson(
    *,
    meta: MetaPayload,
    config: Config,
) -> Iterator[str]:
    """Serialize Config diagnostics as NDJSON.

    Record sequence:
      1) config_diagnostics (counts-only)
      2+) diagnostic (domain="config") one per diagnostic

    Args:
        meta: Machine-output metadata (tool/version).
        config: Immutable runtime configuration providing diagnostics.

    Returns:
        Iterator of NDJSON lines (no trailing newline).
    """
    iter_records: Iterator[dict[str, object]] = iter_config_diagnostics_ndjson_records(
        config=config,
        meta=meta,
    )
    return iter_ndjson_strings(iter_records)


def serialize_config_check(
    *,
    meta: MetaPayload,
    config: Config,
    strict: bool,
    ok: bool,
    fmt: OutputFormat,
) -> str | Iterator[str]:
    """Serialize `topmark config check` results in a machine-readable format.

    JSON:
      - One envelope: meta, config, config_diagnostics (full), summary.

    NDJSON record sequence:
      1) config
      2) config_diagnostics (counts-only)
      3) summary (command="config", subcommand="check")
      4+) diagnostic (domain="config") one per diagnostic

    Args:
        meta: Machine-output metadata (tool/version).
        config: Immutable runtime configuration providing diagnostics.
        strict: If True, warnings are treated as failures.
        ok: Whether the config passed validation
        fmt: Target machine format (JSON or NDJSON).

    Returns:
        Rendered JSON string or iterator of NDJSON lines (no trailing newline).

    Raises:
        ValueError: If `fmt` is not a supported machine format.
    """
    if not is_machine_format(fmt):
        raise ValueError(f"Unsupported machine output format: {fmt!r}")

    if fmt == OutputFormat.JSON:
        return serialize_config_check_json(
            meta=meta,
            config=config,
            strict=strict,
            ok=ok,
        )

    if fmt == OutputFormat.NDJSON:
        return serialize_config_check_ndjson(
            meta=meta,
            config=config,
            strict=strict,
            ok=ok,
        )

    # Defensive guard
    raise ValueError(f"Unsupported machine output format: {fmt!r}")


def serialize_config_check_json(
    *,
    meta: MetaPayload,
    config: Config,
    strict: bool,
    ok: bool,
) -> str:
    """Serialize `topmark config check` results as a JSON envelope.

    Shape:
        {"meta": ..., "config": ..., "config_diagnostics": ..., "summary": ...}

    Args:
        meta: Machine-output metadata (tool/version).
        config: Immutable runtime configuration providing diagnostics.
        strict: If True, warnings are treated as failures.
        ok: Whether the config passed validation

    Returns:
        Pretty-printed JSON string (no trailing newline).
    """
    envelope: dict[str, object] = build_config_check_json_envelope(
        meta=meta,
        config=config,
        strict=strict,
        ok=ok,
    )
    return serialize_json_object(envelope)


def serialize_config_check_ndjson(
    *,
    meta: MetaPayload,
    config: Config,
    strict: bool,
    ok: bool,
) -> Iterator[str]:
    """Serialize `topmark config check` results as NDJSON.

    Record sequence:
      1) config
      2) config_diagnostics (counts-only)
      3) summary
      4+) diagnostic (domain="config") one per diagnostic

    Args:
        meta: Machine-output metadata (tool/version).
        config: Immutable runtime configuration providing diagnostics.
        strict: If True, warnings are treated as failures.
        ok: Whether the config passed validation

    Returns:
        Iterator of NDJSON lines (no trailing newline).
    """
    iter_records: Iterator[dict[str, object]] = iter_config_check_ndjson_records(
        meta=meta,
        config=config,
        strict=strict,
        ok=ok,
    )
    return iter_ndjson_strings(iter_records)
