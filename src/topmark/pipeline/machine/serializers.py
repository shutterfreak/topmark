# topmark:header:start
#
#   project      : TopMark
#   file         : serializers.py
#   file_relpath : src/topmark/pipeline/machine/serializers.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Pure JSON/NDJSON serialization helpers for TopMark pipeline machine output.

This module is intentionally console- and Click-free: it takes already-shaped
payload mappings/objects and produces serialized strings (or streams of strings).

Responsibilities:
- JSON: serialize a single, already-shaped envelope mapping.
- NDJSON: serialize a stream of already-shaped record mappings as
  newline-delimited JSON (one JSON object per line).

Shaping (adding `meta`/`kind`, selecting container keys, etc.) happens in
[`topmark.pipeline.machine.shapes`][topmark.pipeline.machine.shapes], using shared helpers from
[`topmark.core.machine.shapes`][topmark.core.machine.shapes].
Payload normalization for JSON-compatibility is handled by
[`topmark.core.machine.schemas.normalize_payload`][topmark.core.machine.schemas.normalize_payload].
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.core.formats import OutputFormat
from topmark.core.machine.serializers import (
    iter_ndjson_strings,
    serialize_json_object,
)
from topmark.pipeline.machine.shapes import (
    build_processing_results_json_envelope,
    iter_processing_results_ndjson_records,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from topmark.config.model import Config
    from topmark.core.machine.schemas import MetaPayload
    from topmark.pipeline.context.model import ProcessingContext


def serialize_processing_results(
    *,
    meta: MetaPayload,
    config: Config,
    results: list[ProcessingContext],
    fmt: OutputFormat,
    summary_mode: bool,
) -> str | Iterator[str]:
    """Serialize processing results for `check` / `strip` in a machine format.

    Args:
        meta: Shared machine-output metadata payload.
        config: Effective configuration for the run.
        results: Ordered list of per-file processing contexts.
        fmt: Output format (`OutputFormat.JSON` or `OutputFormat.NDJSON`).
        summary_mode: If True, emit aggregated outcome summaries instead of per-file entries.

    Returns:
        - If `fmt` is JSON: a single pretty-printed JSON string (no trailing newline).
        - If `fmt` is NDJSON: an iterable of JSON strings (one per record), where each
            yielded string has no trailing newline. The caller controls line joining and
            whether a final newline is printed.

    Raises:
        ValueError: If `fmt` is not a supported machine format.
    """
    if fmt == OutputFormat.JSON:
        return serialize_processing_results_json(
            config=config,
            meta=meta,
            results=results,
            summary_mode=summary_mode,
        )

    if fmt == OutputFormat.NDJSON:
        return serialize_processing_results_ndjson(
            config=config,
            meta=meta,
            results=results,
            summary_mode=summary_mode,
        )

    # Defensive guard
    raise ValueError(f"Unsupported machine output format: {fmt!r}")


def serialize_processing_results_json(
    *,
    meta: MetaPayload,
    config: Config,
    results: list[ProcessingContext],
    summary_mode: bool,
) -> str:
    """Serialize processing results for `check` / `strip` in a machine format.

    Args:
        meta: Shared machine-output metadata payload.
        config: Effective configuration for the run.
        results: Ordered list of per-file processing contexts.
        summary_mode: If True, emit aggregated outcome summaries instead of per-file entries.

    Returns:
        - A single pretty-printed JSON string (no trailing newline).

    """
    envelope: dict[str, object] = build_processing_results_json_envelope(
        config=config,
        meta=meta,
        results=results,
        summary_mode=summary_mode,
    )
    return serialize_json_object(envelope)


def serialize_processing_results_ndjson(
    *,
    meta: MetaPayload,
    config: Config,
    results: list[ProcessingContext],
    summary_mode: bool,
) -> Iterator[str]:
    """Serialize processing results for `check` / `strip` in a machine format.

    Args:
        meta: Shared machine-output metadata payload.
        config: Effective configuration for the run.
        results: Ordered list of per-file processing contexts.
        summary_mode: If True, emit aggregated outcome summaries instead of per-file entries.

    Returns:
        Iterator of JSON strings (one per record), where each
        yielded string has no trailing newline. The caller controls line joining and
        whether a final newline is printed.

    """
    iter_records: Iterator[dict[str, object]] = iter_processing_results_ndjson_records(
        config=config,
        meta=meta,
        results=results,
        summary_mode=summary_mode,
    )
    return iter_ndjson_strings(iter_records)
