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

    Probe payloads are built from `ProcessingContext.resolution_probe` and include
    both ordinary file-type probe results and synthetic filtered results for
    explicit inputs excluded during discovery before file-type probing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.pipeline.context.model import ProcessingContext
from topmark.pipeline.outcomes import OutcomeReasonCount
from topmark.pipeline.outcomes import collect_outcome_reason_counts
from topmark.pipeline.outcomes import collect_outcome_reason_counts_for_apply
from topmark.utils.path import format_machine_path

if TYPE_CHECKING:
    from collections.abc import Iterable
    from collections.abc import Iterator

    from topmark.pipeline.context.model import ProcessingContext
    from topmark.pipeline.machine.schemas import OutcomeSummaryRow
    from topmark.pipeline.outcomes import SupportsOutcomeClassification
    from topmark.resolution.probe import ResolutionProbeCandidate
    from topmark.resolution.probe import ResolutionProbeMatchSignals
    from topmark.resolution.probe import ResolutionProbeResult
    from topmark.resolution.probe import ResolutionProbeSelection


def build_probe_selection_payload(
    selection: ResolutionProbeSelection | None,
) -> dict[str, object] | None:
    """Build a machine payload for a selected file type or processor.

    Args:
        selection: Probe selection to serialize, or `None` for unresolved, unbound,
            or filtered probe results.

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
    """Build a machine payload for candidate match signals.

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
        JSON-compatible candidate payload including score, selection state, rank,
        and match signals.
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

    Filtered explicit inputs are represented as probe results with:

    - `status="filtered"`
    - `selected_file_type=None`
    - `selected_processor=None`
    - `candidates=[]`

    Args:
        result: Processing context containing a resolution probe result. Contexts
            without a probe result are serialized as `probe_missing` fallback
            payloads.

    Returns:
        JSON-compatible probe result payload.
    """
    probe: ResolutionProbeResult | None = result.resolution_probe
    if probe is None:
        return {
            "path": format_machine_path(result.path),
            "status": "probe_missing",
            "reason": "no_resolution_probe_result",
            "selected_file_type": None,
            "selected_processor": None,
            "candidates": [],
        }

    return {
        "path": format_machine_path(probe.path),
        "status": probe.status.value,
        "reason": probe.reason.value,
        "selected_file_type": build_probe_selection_payload(probe.selected_file_type),
        "selected_processor": build_probe_selection_payload(probe.selected_processor),
        "candidates": [build_probe_candidate_payload(candidate) for candidate in probe.candidates],
    }


def iter_probe_results_payload_items(
    results: list[ProcessingContext],
) -> Iterator[dict[str, object]]:
    """Yield per-path resolution probe payloads for machine-readable output.

    Args:
        results: Ordered list of processing contexts. The list may contain normal
            file-backed probe contexts and synthetic contexts for explicit inputs
            filtered before file-type probing.

    Yields:
        One probe result payload per context, in the same order as `results`.
    """
    for result in results:
        yield build_probe_result_payload(result)


def iter_processing_results_payload_items(
    results: list[ProcessingContext],
) -> Iterator[dict[str, object]]:
    """Yield per-file processing result objects for machine-readable output (detail mode).

    Each yielded mapping corresponds to one processed file and is produced by
    [`ProcessingContext.to_dict()`][topmark.pipeline.context.model.ProcessingContext.to_dict].

    Args:
        results: Ordered list of per-file processing contexts.

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


def build_processing_results_summary_rows_payload_for_apply(
    results: Iterable[SupportsOutcomeClassification],
    *,
    apply: bool,
) -> list[OutcomeSummaryRow]:
    """Build a JSON-friendly summary payload for an explicit execution mode.

    This result-compatible helper accepts either mutable processing contexts or
    durable processing results. The execution mode is supplied explicitly so
    callers do not need to retain runtime options only for outcome summary
    classification.

    Args:
        results: Ordered list of processing contexts or durable results.
        apply: Whether to classify the supplied results as apply-mode output.

    Returns:
        List of [`OutcomeSummaryRow`][topmark.pipeline.machine.schemas.OutcomeSummaryRow] objects.
    """
    counts: list[OutcomeReasonCount] = collect_outcome_reason_counts_for_apply(
        results,
        apply=apply,
    )
    return _summary_rows_from_counts(counts)


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
    return _summary_rows_from_counts(counts)


def iter_processing_results_summary_entries_for_apply(
    results: Iterable[SupportsOutcomeClassification],
    *,
    apply: bool,
) -> Iterator[OutcomeSummaryRow]:
    """Yield NDJSON-friendly summary rows for an explicit execution mode.

    This result-compatible helper accepts either mutable processing contexts or
    durable processing results. Each yielded object preserves the full
    `(outcome, reason, count)` tuple so NDJSON summary mode does not collapse
    sub-buckets inside the same outcome.

    Args:
        results: Ordered list of processing contexts or durable results.
        apply: Whether to classify the supplied results as apply-mode output.

    Yields:
        One summary row object per `(outcome, reason)` bucket.
    """
    yield from build_processing_results_summary_rows_payload_for_apply(
        results,
        apply=apply,
    )


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

    yield from _summary_rows_from_counts(counts)
