# topmark:header:start
#
#   project      : TopMark
#   file         : serializers.py
#   file_relpath : src/topmark/pipeline/machine/serializers.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Pure JSON/NDJSON serializers for TopMark processing and probe machine-readable output.

This module is intentionally console- and Click-free: it takes already-shaped
processing/probe envelopes or record streams and produces serialized strings
(or streams of strings).

Responsibilities:
- JSON: serialize a single, already-shaped processing or probe envelope mapping.
- NDJSON: serialize a stream of already-shaped processing or probe record mappings
  as newline-delimited JSON (one JSON object per line).

Creation of envelopes (adding `meta`/`kind`, selecting container keys, etc.) happens in
[`topmark.pipeline.machine.envelopes`][topmark.pipeline.machine.envelopes], using shared helpers
from [`topmark.core.machine.envelopes`][topmark.core.machine.envelopes].
Payload normalization for JSON-compatibility is handled by
[`topmark.core.machine.schemas.normalize_payload`][topmark.core.machine.schemas.normalize_payload].
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.core.formats import OutputFormat
from topmark.core.machine.serializers import iter_ndjson_strings
from topmark.core.machine.serializers import serialize_json_object
from topmark.pipeline.machine.envelopes import build_probe_results_stream_json_envelope
from topmark.pipeline.machine.envelopes import build_processing_results_stream_json_envelope
from topmark.pipeline.machine.envelopes import iter_probe_results_ndjson_records
from topmark.pipeline.machine.envelopes import iter_processing_results_ndjson_records
from topmark.pipeline.machine.streaming import iter_machine_processing_stream

if TYPE_CHECKING:
    from collections.abc import Iterable
    from collections.abc import Iterator

    from topmark.config.model import FrozenConfig
    from topmark.core.machine.schemas import MetaPayload
    from topmark.pipeline.result import ProcessingResult
    from topmark.toml.resolution import ResolvedTopmarkTomlSources


def serialize_probe_results(
    *,
    meta: MetaPayload,
    config: FrozenConfig,
    resolved_toml: ResolvedTopmarkTomlSources,
    results: Iterable[ProcessingResult],
    fmt: OutputFormat,
) -> str | Iterator[str]:
    """Serialize resolution probe results in a machine-readable format.

    Probe results may include normal file-backed probe contexts and synthetic
    contexts for explicit inputs filtered during discovery before file-type
    probing.

    Args:
        meta: Shared machine-readable output metadata payload.
        config: Effective configuration for the run.
        resolved_toml: ResolvedTopmarkTomlSources,
        results: Ordered list of probe contexts to serialize.
        fmt: Output format (`OutputFormat.JSON` or `OutputFormat.NDJSON`).

    Returns:
        Serialized JSON string or iterator of NDJSON strings.

    Raises:
        ValueError: If `fmt` is not a supported machine-readable format.
    """
    if fmt == OutputFormat.JSON:
        envelope: dict[str, object] = build_probe_results_stream_json_envelope(
            meta=meta,
            config=config,
            resolved_toml=resolved_toml,
            events=iter_machine_processing_stream(results, command="probe"),
        )
        return serialize_json_object(envelope)

    if fmt == OutputFormat.NDJSON:
        records: Iterator[dict[str, object]] = iter_probe_results_ndjson_records(
            meta=meta,
            config=config,
            resolved_toml=resolved_toml,
            results=results,
        )
        return iter_ndjson_strings(records)

    # Defensive guard
    raise ValueError(f"Unsupported machine-readable output format: {fmt!r}")


def serialize_processing_results(
    *,
    meta: MetaPayload,
    config: FrozenConfig,
    resolved_toml: ResolvedTopmarkTomlSources,
    results: Iterable[ProcessingResult],
    fmt: OutputFormat,
    summary_mode: bool,
) -> str | Iterator[str]:
    """Serialize processing results for `check` / `strip` in a machine-readable format.

    Args:
        meta: Shared machine-readable output metadata payload.
        config: Effective configuration for the run.
        resolved_toml: ResolvedTopmarkTomlSources,
        results: Ordered list of durable per-file check/strip processing results.
        fmt: Output format (`OutputFormat.JSON` or `OutputFormat.NDJSON`).
        summary_mode: If True, emit aggregated outcome summaries instead of per-file entries.

    Returns:
        - If `fmt` is JSON: a single pretty-printed JSON string (no trailing newline).
        - If `fmt` is NDJSON: an iterable of JSON strings (one per record), where each
            yielded string has no trailing newline. The caller controls line joining and
            whether a final newline is printed.

    Raises:
        ValueError: If `fmt` is not a supported machine-readable format.
    """
    if fmt == OutputFormat.JSON:
        return serialize_processing_results_json(
            meta=meta,
            config=config,
            resolved_toml=resolved_toml,
            results=results,
            summary_mode=summary_mode,
        )

    if fmt == OutputFormat.NDJSON:
        return serialize_processing_results_ndjson(
            meta=meta,
            config=config,
            resolved_toml=resolved_toml,
            results=results,
            summary_mode=summary_mode,
        )

    # Defensive guard
    raise ValueError(f"Unsupported machine-readable output format: {fmt!r}")


def serialize_processing_results_json(
    *,
    meta: MetaPayload,
    config: FrozenConfig,
    resolved_toml: ResolvedTopmarkTomlSources,
    results: Iterable[ProcessingResult],
    summary_mode: bool,
) -> str:
    """Serialize processing results for `check` / `strip` in a machine-readable format.

    Args:
        meta: Shared machine-readable output metadata payload.
        config: Effective configuration for the run.
        resolved_toml: ResolvedTopmarkTomlSources,
        results: Ordered list of durable per-file check/strip processing results.
        summary_mode: If True, emit aggregated outcome summaries instead of per-file entries.

    Returns:
        Single pretty-printed JSON string (no trailing newline).
    """
    # Legacy processing serializers predate command-aware durable streams.
    # Their public/internal signature intentionally has no command parameter,
    # and the JSON compatibility envelope is command-neutral. The primary
    # CLI path uses command-aware stream emitters directly; if these legacy
    # helpers remain after follow-up cleanup, add a `command` parameter
    # consistently across JSON and NDJSON processing serializers/emitters.
    envelope: dict[str, object] = build_processing_results_stream_json_envelope(
        meta=meta,
        config=config,
        resolved_toml=resolved_toml,
        events=iter_machine_processing_stream(results, command="check"),
        summary_mode=summary_mode,
    )
    return serialize_json_object(envelope)


def serialize_processing_results_ndjson(
    *,
    meta: MetaPayload,
    config: FrozenConfig,
    resolved_toml: ResolvedTopmarkTomlSources,
    results: Iterable[ProcessingResult],
    summary_mode: bool,
) -> Iterator[str]:
    """Serialize processing results for `check` / `strip` in a machine-readable format.

    Args:
        meta: Shared machine-readable output metadata payload.
        config: Effective configuration for the run.
        resolved_toml: ResolvedTopmarkTomlSources,
        results: Ordered list of durable per-file check/strip processing results.
        summary_mode: If True, emit aggregated outcome summaries instead of per-file entries.

    Returns:
        Iterator of JSON strings (one per record), where each yielded string has
        no trailing newline. The caller controls line joining and whether a final
        newline is printed.
    """
    # Legacy processing serializers predate command-aware durable streams. This
    # helper preserves the existing command-neutral signature; the primary CLI
    # path uses command-aware stream emitters directly. If retained after
    # follow-up cleanup, wire an explicit `command` parameter consistently with
    # the JSON serializer and legacy processing emitters.
    iter_records: Iterator[dict[str, object]] = iter_processing_results_ndjson_records(
        meta=meta,
        config=config,
        resolved_toml=resolved_toml,
        results=results,
        summary_mode=summary_mode,
    )
    return iter_ndjson_strings(iter_records)
