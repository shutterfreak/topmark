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
pipeline machine outputs for `check`, `strip`, and `probe`.

Scope:

    These helpers do **not**:
    - add `"meta"` / `"kind"` envelopes,
    - choose between JSON vs NDJSON record layout,
    - serialize (`json.dumps`) or print.

    They only construct the domain payload shapes consumed by shape builders in
    [`topmark.core.machine.envelopes`][topmark.core.machine.envelopes] (JSON envelopes and
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
    from topmark.pipeline.machine.schemas import OutcomeSummaryRow
    from topmark.resolution.probe import ResolutionProbeCandidate
    from topmark.resolution.probe import ResolutionProbeMatchSignals
    from topmark.resolution.probe import ResolutionProbeResult
    from topmark.resolution.probe import ResolutionProbeSelection


def build_probe_selection_payload(
    selection: ResolutionProbeSelection | None,
) -> dict[str, object] | None:
    """Build a machine payload for a probe-selected file type or processor.

    Args:
        selection: Probe selection to serialize, or `None`.

    Returns:
        JSON-compatible selection payload, or `None`.
    """
    if selection is None:
        return None

    payload: dict[str, object] = {
        "qualified_key": selection.qualified_key,
        "namespace": selection.namespace,
        "local_key": selection.local_key,
    }
    if selection.score is not None:
        payload["score"] = selection.score
    return payload


def build_probe_match_payload(
    match: ResolutionProbeMatchSignals,
) -> dict[str, object]:
    """Build a machine payload for probe match signals.

    Args:
        match: Probe-visible match signals.

    Returns:
        JSON-compatible match payload.
    """
    return {
        "extension": match.extension,
        "filename": match.filename,
        "pattern": match.pattern,
        "content_probe_allowed": match.content_probe_allowed,
        "content_match": match.content_match,
        "content_error": match.content_error,
    }


def build_probe_candidate_payload(
    candidate: ResolutionProbeCandidate,
) -> dict[str, object]:
    """Build a machine payload for one scored probe candidate.

    Args:
        candidate: Probe candidate to serialize.

    Returns:
        JSON-compatible candidate payload.
    """
    return {
        "qualified_key": candidate.qualified_key,
        "namespace": candidate.namespace,
        "local_key": candidate.local_key,
        "score": candidate.score,
        "selected": candidate.selected,
        "tie_break_rank": candidate.tie_break_rank,
        "match": build_probe_match_payload(candidate.match),
    }


def build_probe_result_payload(
    result: ProcessingContext,
) -> dict[str, object]:
    """Build a machine payload for one resolution probe context.

    Args:
        result: Processing context containing a resolution probe result.

    Returns:
        JSON-compatible probe result payload.
    """
    probe: ResolutionProbeResult | None = result.resolution_probe
    if probe is None:
        return {
            "path": str(result.path),
            "status": "probe_missing",
            "reason": "no_resolution_probe_result",
            "selected_file_type": None,
            "selected_processor": None,
            "candidates": [],
        }

    return {
        "path": str(probe.path),
        "status": probe.status.value,
        "reason": probe.reason.value,
        "selected_file_type": build_probe_selection_payload(probe.selected_file_type),
        "selected_processor": build_probe_selection_payload(probe.selected_processor),
        "candidates": [build_probe_candidate_payload(candidate) for candidate in probe.candidates],
    }


def iter_probe_results_payload_items(
    results: list[ProcessingContext],
) -> Iterator[dict[str, object]]:
    """Yield per-file resolution probe payloads for machine output.

    Args:
        results: Ordered list of per-file processing contexts.

    Yields:
        One probe result payload per processed context, in the same order as `results`.
    """
    for result in results:
        yield build_probe_result_payload(result)


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


def build_processing_results_summary_rows_payload(
    results: list[ProcessingContext],
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
        results: Ordered list of per-file processing contexts.

    Returns:
        List of [`OutcomeSummaryRow`][topmark.pipeline.machine.schemas.OutcomeSummaryRow] objects.
    """
    counts: list[OutcomeReasonCount] = collect_outcome_reason_counts(results)
    summary_rows: list[OutcomeSummaryRow] = [
        {"outcome": row.outcome.value, "reason": row.reason, "count": row.count} for row in counts
    ]
    return summary_rows


def iter_processing_results_summary_entries(
    results: list[ProcessingContext],
) -> Iterator[OutcomeSummaryRow]:
    """Yield NDJSON-friendly summary rows for processing results.

    Each yielded object preserves the full `(outcome, reason, count)` tuple so
    NDJSON summary mode does not collapse sub-buckets inside the same outcome, e.g.:

        {"kind": "summary", "meta": {...},
         "summary": {"outcome": "unchanged", "reason": "no changes needed", "count": 3}}

    Args:
        results: Ordered list of per-file processing contexts.

    Yields:
        One summary row object per `(outcome, reason)` bucket.
    """
    counts: list[OutcomeReasonCount] = collect_outcome_reason_counts(results)

    for row in counts:
        summary_row: OutcomeSummaryRow = {
            "outcome": row.outcome.value,
            "reason": row.reason,
            "count": row.count,
        }
        yield summary_row
