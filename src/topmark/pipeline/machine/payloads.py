# topmark:header:start
#
#   project      : TopMark
#   file         : payloads.py
#   file_relpath : src/topmark/pipeline/machine/payloads.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Payload builders for pipeline-related machine-readable output.

This module contains **pure** helpers that build the *payload fragments* used by
pipeline machine-readable output for `check`, `strip`, and `probe`.

Scope:

    These helpers do **not**:
    - add `"meta"` / `"kind"` envelopes,
    - choose between JSON vs NDJSON record layout,
    - serialize (`json.dumps`) or print.

    They only construct the domain payload shapes consumed by envelope builders
    in [`topmark.core.machine.envelopes`][topmark.core.machine.envelopes]
    (JSON envelopes and NDJSON records).

Naming conventions:

    - `build_*_payload(...) -> <payload object>`: constructs an eager payload object.
    - `iter_*_payload_items(...) -> Iterator[...]`: yields payload items lazily.

Probe payloads:

    Probe payloads are built from durable `ProcessingResult.probe` snapshots and include
    both ordinary file-type probe results and synthetic filtered results for
    explicit inputs excluded during discovery before file-type probing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.pipeline.outcomes import OutcomeReasonCount
from topmark.pipeline.outcomes import collect_outcome_reason_counts
from topmark.utils.path import format_machine_path

if TYPE_CHECKING:
    from collections.abc import Iterable
    from collections.abc import Iterator

    from topmark.pipeline.machine.schemas import OutcomeSummaryRow
    from topmark.pipeline.result import ProcessingResult


def build_probe_result_payload(
    result: ProcessingResult,
) -> dict[str, object]:
    """Build a machine payload for one durable resolution probe result.

    Args:
        result: Durable processing result containing a probe snapshot.

    Returns:
        JSON-compatible probe result payload preserving the existing probe shape.
    """
    if result.probe is None:
        return {
            "path": format_machine_path(result.path),
            "status": "probe_missing",
            "reason": "no_resolution_probe_result",
            "selected_file_type": None,
            "selected_processor": None,
            "candidates": [],
        }
    return result.probe.to_dict()


def iter_probe_results_payload_items(
    results: Iterable[ProcessingResult],
) -> Iterator[dict[str, object]]:
    """Yield per-path resolution probe payloads for machine-readable output.

    Args:
        results: Ordered durable probe results. The list may contain normal
            file-backed probe results and synthetic results for explicit inputs
            filtered before file-type probing.

    Yields:
        One probe result payload per durable result, in the same order.
    """
    for result in results:
        yield build_probe_result_payload(result)


def iter_processing_results_payload_items(
    results: Iterable[ProcessingResult],
) -> Iterator[dict[str, object]]:
    """Yield per-file processing result objects for machine-readable output (detail mode).

    Each yielded mapping corresponds to one processed file and is produced by
    [`ProcessingResult.to_dict()`][topmark.pipeline.result.ProcessingResult.to_dict].

    Args:
        results: Ordered iterable of durable per-file processing results.

    Yields:
        One per-file result mapping per processed context, in the same order as `results`.
    """
    for r in results:
        yield r.to_dict()


def _summary_rows_from_counts(
    counts: list[OutcomeReasonCount],
) -> list[OutcomeSummaryRow]:
    """Build JSON-friendly summary rows from grouped outcome counts.

    Args:
        counts: Ordered outcome/reason/count rows.

    Returns:
        List of [`OutcomeSummaryRow`][topmark.pipeline.machine.schemas.OutcomeSummaryRow] objects.
    """
    return [
        {"outcome": row.outcome.value, "reason": row.reason, "count": row.count} for row in counts
    ]


def build_processing_results_summary_rows_payload(
    results: Iterable[ProcessingResult],
) -> list[OutcomeSummaryRow]:
    """Build a JSON-friendly summary payload for processing results (summary mode).

    The returned payload is a flat list of summary rows, each preserving both
    bucketing axes:

    - `outcome`
    - `reason`
    - `count`

    This avoids collapsing distinct reasons inside the same outcome bucket.

    This payload is intended for **JSON envelopes** where the summary is a flat
    list, e.g.::

        "summary": [
          {"outcome": "unchanged", "reason": "no changes needed", "count": 3},
          {"outcome": "would insert", "reason": "header missing, changes found", "count": 1}
        ]

    Args:
        results: Ordered iterable of per-file processing results.

    Returns:
        List of [`OutcomeSummaryRow`][topmark.pipeline.machine.schemas.OutcomeSummaryRow] objects.
    """
    counts: list[OutcomeReasonCount] = collect_outcome_reason_counts(
        results,
    )
    return _summary_rows_from_counts(counts)


def iter_processing_results_summary_entries(
    results: Iterable[ProcessingResult],
) -> Iterator[OutcomeSummaryRow]:
    """Yield NDJSON-friendly summary rows for processing results.

    Each yielded object preserves the full `(outcome, reason, count)` tuple so
    NDJSON summary mode does not collapse sub-buckets inside the same outcome, e.g.:

        {"kind": "summary", "meta": {...},
         "summary": {"outcome": "unchanged", "reason": "no changes needed", "count": 3}}

    Args:
        results: Ordered iterable of per-file processing results.

    Yields:
        One summary row object per `(outcome, reason)` bucket.
    """
    counts: list[OutcomeReasonCount] = collect_outcome_reason_counts(
        results,
    )

    yield from _summary_rows_from_counts(counts)
