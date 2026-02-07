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
envelopes/records):

- **JSON envelope (summary mode)** uses a *summary map* keyed by outcome string,
  where each value is an `OutcomeSummaryMapEntry`::

      {
        "summary": {
          "unchanged": {"count": 3, "label": "no changes needed"},
          "would insert": {"count": 1, "label": "header missing, changes found"}
        }
      }

- **NDJSON stream (summary mode)** emits one `kind="summary"` record per bucket.
  The payload under `"summary"` follows `OutcomeSummaryRecordPayload`::

      {"kind": "summary", "meta": {...},
       "summary": {"key": "unchanged", "count": 3, "label": "no changes needed"}}

Notes:
    - These are `TypedDict` definitions (static typing only). Runtime validation is
      intentionally out-of-scope.
    - The `"key"` field uses the string value of `Outcome` (e.g., `"unchanged"`),
      so producers/consumers should treat keys as stable identifiers.
"""

from __future__ import annotations

from typing import TypedDict


class OutcomeSummaryMapEntry(TypedDict):
    """Value object for a JSON processing-summary map.

    Used as the value type in a JSON envelope summary map keyed by outcome string.

    Shape:
        `{"count": int, "label": str}`

    Fields:
        count: Number of files that fell into this outcome bucket.
        label: Human-oriented bucket label/reason (stable-ish but not guaranteed as an API).
    """

    count: int
    label: str


class OutcomeSummaryRecordPayload(TypedDict):
    """Payload object for an NDJSON `kind="summary"` record.

    Used as the payload under the `"summary"` container key in NDJSON summary-mode output.

    Shape:
        `{"key": str, "count": int, "label": str}`

    Fields:
        key: Outcome key (string value of `Outcome`, e.g. `"would insert"`).
        count: Number of files in this bucket.
        label: Human-oriented bucket label/reason (stable-ish but not guaranteed as an API).
    """

    key: str
    count: int
    label: str
