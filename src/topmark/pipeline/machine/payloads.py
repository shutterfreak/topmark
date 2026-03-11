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
from topmark.pipeline.outcomes import OutcomeReasonCount
from topmark.pipeline.outcomes import collect_outcome_reason_counts

if TYPE_CHECKING:
    from collections.abc import Iterator

    from topmark.pipeline.context.model import ProcessingContext


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
) -> list[dict[str, object]]:
    """Build a JSON-friendly summary payload for processing results (summary mode).

    The returned payload is a flat list of summary rows, each preserving both
    bucketing axes:

    - `outcome`
    - `reason`
    - `count`

    This avoids collapsing distinct reasons inside the same outcome bucket.

    This payload is intended for **JSON envelopes** where the summary is a single
    object, e.g.::

        "summary": {
          "unchanged": {"count": 3, "label": "no changes needed"},
          "would insert": {"count": 1, "label": "header missing, changes found"}
        }

    Args:
        results: Ordered list of per-file processing contexts.

    Returns:
        List of JSON-friendly summary row objects.
    """
    counts: list[OutcomeReasonCount] = collect_outcome_reason_counts(results)
    return [
        {"outcome": row.outcome.value, "reason": row.reason, "count": row.count} for row in counts
    ]


def iter_processing_results_summary_entries(
    results: list[ProcessingContext],
) -> Iterator[dict[str, object]]:
    """Yield NDJSON-friendly summary rows for processing results.

    Each yielded object preserves the full `(outcome, reason, count)` tuple so
    NDJSON summary mode does not collapse sub-buckets inside the same outcome, e.g.:

        {"kind": "summary", "meta": {...},
         "summary": {"key": "unchanged", "count": 3, "label": "no changes needed"}}

    Args:
        results: Ordered list of per-file processing contexts.

    Yields:
        One summary row object per `(outcome, reason)` bucket.
    """
    counts: list[OutcomeReasonCount] = collect_outcome_reason_counts(results)

    for row in counts:
        yield {"outcome": row.outcome.value, "reason": row.reason, "count": row.count}
