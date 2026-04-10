# topmark:header:start
#
#   project      : TopMark
#   file         : schemas.py
#   file_relpath : src/topmark/pipeline/machine/schemas.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Typed schema fragments for pipeline-related machine output.

This module defines small, stable *shape types* used by TopMark's machine-readable
outputs for pipeline processing (`check` / `strip`).

These types intentionally model only the **pipeline summary fragments** (not full
JSON/NDJSON envelopes):

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

Notes:
    - These are `TypedDict` definitions (static typing only). Runtime validation is
      intentionally out-of-scope.
    - `outcome` is the stable machine identifier (string value of `Outcome`).
    - `reason` is the stable bucket reason emitted by the current summary serializer.
"""

from __future__ import annotations

from enum import Enum
from typing import TypedDict


class PipelineKey(str, Enum):
    """Stable pipeline-domain keys for machine-readable payloads.

    Attributes:
        RESULT: Container key for a single processing result.
        RESULTS: Container key for a JSON list of processing results.
        SUMMARY: Container key for pipeline outcome summaries.
    """

    RESULT = "result"
    RESULTS = "results"
    SUMMARY = "summary"


class PipelineKind(str, Enum):
    """Stable NDJSON kinds emitted by the pipeline machine-output domain.

    Attributes:
        RESULT: One per-file processing result record.
        SUMMARY: One per-summary-row record.
    """

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
