# topmark:header:start
#
#   project      : TopMark
#   file         : schemas.py
#   file_relpath : src/topmark/pipeline/machine/schemas.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Typed schema fragments for pipeline-related machine-readable output.

This module defines small, stable *shape types* used by TopMark's machine-readable
outputs for pipeline processing (`check` / `strip`) and resolution probing (`probe`).

These types intentionally model the **pipeline-domain container keys and summary
fragments** (not full JSON/NDJSON envelopes):

- **JSON envelope (summary mode)** uses a flat list of summary rows, where each row
  is an `OutcomeSummaryRow`::
      ```json
      {
        "summary": [
          {"outcome": "unchanged", "reason": "no changes needed", "count": 3},
          {"outcome": "would insert", "reason": "header missing, changes found", "count": 1}
        ]
      }
      ```

- **NDJSON stream (summary mode)** emits one `kind="summary"` record per summary row.
  The payload under `"summary"` follows `OutcomeSummaryRow`::

      ```ndjson
      {"kind": "summary", "meta": {...},
       "summary": {"outcome": "unchanged", "reason": "no changes needed", "count": 3}}
      ```

- **Probe output** uses `PipelineKey.PROBES` for the JSON `"probes"` collection and
  `PipelineKind.PROBE` / `PipelineKey.PROBE` for one NDJSON `kind="probe"` record per
  probe result. Individual probe payloads are built from
  [`ResolutionProbeResult`][topmark.resolution.probe.ResolutionProbeResult], including
  filtered explicit inputs that never reached file-type probing.

Notes:
    - These are `TypedDict` definitions (static typing only). Runtime validation is
      intentionally out-of-scope.
    - `outcome` is the stable machine identifier (string value of `Outcome`).
    - `reason` is the stable bucket reason emitted by the current summary serializer.
    - Probe `status` and `reason` values are owned by
      [`topmark.resolution.probe`][topmark.resolution.probe], not duplicated here.
"""

from __future__ import annotations

from enum import Enum
from typing import TypedDict


class PipelineKey(str, Enum):
    """Stable pipeline-domain keys for machine-readable payloads.

    Attributes:
        PROBE: Container key for a single resolution probe result in NDJSON.
        PROBES: Container key for a JSON list of resolution probe results.
        RESULT: Container key for a single processing result.
        RESULTS: Container key for a JSON list of processing results.
        SUMMARY: Container key for pipeline outcome summaries.
    """

    PROBE = "probe"
    PROBES = "probes"
    RESULT = "result"
    RESULTS = "results"
    SUMMARY = "summary"


class PipelineKind(str, Enum):
    """Stable NDJSON kinds emitted by the pipeline machine-output domain.

    Attributes:
        PROBE: One per-path resolution probe record, including filtered explicit inputs.
        RESULT: One per-file processing result record.
        SUMMARY: One per-summary-row record.
    """

    PROBE = "probe"
    RESULT = "result"
    SUMMARY = "summary"


class OutcomeSummaryRow(TypedDict):
    """One pipeline summary row shared by JSON and NDJSON summary output.

    Used both:
    - as one element of the JSON `"summary"` list, and
    - as the payload under the `"summary"` container key in NDJSON summary-mode output.

    Shape:
        `{"outcome": str, "reason": str, "count": int}`

    Fields:
        outcome: Stable outcome key (string value of `Outcome`, e.g. `"unchanged"`).
        reason: Stable summary reason/bucket explanation.
        count: Number of files in this `(outcome, reason)` bucket.
    """

    outcome: str
    reason: str
    count: int
