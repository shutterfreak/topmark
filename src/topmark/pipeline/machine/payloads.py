# topmark:header:start
#
#   project      : TopMark
#   file         : payloads.py
#   file_relpath : src/topmark/pipeline/machine/payloads.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Payload builders for pipeline-related machine output.

This module contains **pure** helpers that build the *payload fragments* used by
pipeline machine outputs for `check` / `strip`.

Scope:

    These helpers do **not**:
    - add `"meta"` / `"kind"` envelopes,
    - choose between JSON vs NDJSON record layout,
    - serialize (`json.dumps`) or print.

    They only construct the domain payload shapes consumed by shape builders in
    [`topmark.core.machine.shapes`][topmark.core.machine.shapes] (JSON envelopes and
    NDJSON records).

Naming conventions:

    - `build_*_payload(...) -> <payload object>`: constructs an eager payload object.
    - `iter_*_payload_items(...) -> Iterator[...]`: yields payload items lazily.

See Also:
    - [`topmark.pipeline.machine.schemas`][topmark.pipeline.machine.schemas]: `TypedDict` schema
        fragments for these payloads.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.pipeline.context.model import ProcessingContext
from topmark.pipeline.outcomes import collect_outcome_counts

if TYPE_CHECKING:
    from collections.abc import Iterator

    from topmark.pipeline.context.model import ProcessingContext
    from topmark.pipeline.machine.schemas import (
        OutcomeSummaryMapEntry,
        OutcomeSummaryRecordPayload,
    )


def iter_processing_results_payload_items(
    results: list[ProcessingContext],
) -> Iterator[dict[str, object]]:
    """Yield per-file processing result objects for machine output (detail mode).

    Each yielded mapping corresponds to one processed file and is produced by
    [`ProcessingContext.to_dict()`][topmark.pipeline.context.model.ProcessingContext.to_dict].

    Args:
        results: Ordered list of per-file processing contexts.

    Yields:
        One per-file result mapping per processed context, in the same order as `results`.
    """
    for r in results:
        yield r.to_dict()


def build_processing_results_summary_map_payload(
    results: list[ProcessingContext],
) -> dict[str, OutcomeSummaryMapEntry]:
    """Build a JSON-friendly summary map payload for processing results (summary mode).

    The returned mapping is keyed by outcome string (the value of `Outcome`),
    for example `"unchanged"` or `"would insert"`.

    This payload is intended for **JSON envelopes** where the summary is a single
    object, e.g.::

        "summary": {
          "unchanged": {"count": 3, "label": "no changes needed"},
          "would insert": {"count": 1, "label": "header missing, changes found"}
        }

    Args:
        results: Ordered list of per-file processing contexts.

    Returns:
        Mapping from outcome key to an `OutcomeSummaryMapEntry` containing `count`
        and `label`.
    """
    counts: dict[str, tuple[int, str]] = collect_outcome_counts(results)
    return {key: {"count": n, "label": label} for key, (n, label) in counts.items()}


def iter_processing_results_summary_entries(
    results: list[ProcessingContext],
) -> Iterator[OutcomeSummaryRecordPayload]:
    """Yield NDJSON-friendly summary entries for processing results (summary mode).

    Each yielded object is suitable as the payload under `"summary"` in an NDJSON
    record with `kind="summary"`, e.g.::

        {"kind": "summary", "meta": {...},
         "summary": {"key": "unchanged", "count": 3, "label": "no changes needed"}}

    Args:
        results: Ordered list of per-file processing contexts.

    Yields:
        One summary payload per outcome bucket, with keys `"key"`, `"count"`, and `"label"`.
    """
    counts: dict[str, tuple[int, str]] = collect_outcome_counts(results)

    for key, (n, label) in counts.items():
        yield {"key": key, "count": n, "label": label}
