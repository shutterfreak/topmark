# topmark:header:start
#
#   project      : TopMark
#   file         : machine_output.py
#   file_relpath : src/topmark/cli_shared/machine_output.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Machine-readable payload builders for TopMark CLI output.

This module defines JSON-friendly TypedDict payloads and helper functions
used to build machine-readable data structures for TopMark's CLI:

- ConfigPayload: snapshot of the effective configuration, derived from
  Config.to_toml_dict() with JSON-safe normalization.
- ConfigDiagnosticsPayload: per-level diagnostic counts and messages for
  configuration-related diagnostics.
- ProcessingSummaryEntry and build_processing_results_payload(): payloads
  for per-file results and aggregated outcome counts.

These helpers are deliberately Click-free and do not perform any I/O.
They are consumed by [`topmark.cli.utils`][topmark.cli.utils]
to render JSON/NDJSON output for
`--output-format json` and `--output-format ndjson`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypedDict

from topmark.pipeline.outcomes import collect_outcome_counts

if TYPE_CHECKING:
    from topmark.pipeline.context.model import ProcessingContext


class ProcessingSummaryEntry(TypedDict):
    """Machine-readable summary entry for per-outcome counts."""

    count: int
    label: str


def build_processing_results_payload(
    results: list[ProcessingContext],
    *,
    summary_mode: bool,
) -> dict[str, Any]:
    """Build the machine-readable payload for processing results.

    For JSON:
      - summary_mode=False: this will be nested under "results".
      - summary_mode=True: this will be nested under "summary".
    """
    if summary_mode:
        counts: dict[str, tuple[int, str]] = collect_outcome_counts(results)
        summary: dict[str, ProcessingSummaryEntry] = {
            key: {"count": cnt, "label": label} for key, (cnt, label) in counts.items()
        }
        return {"summary": summary}
    else:
        details: list[dict[str, object]] = [r.to_dict() for r in results]
        return {"results": details}
