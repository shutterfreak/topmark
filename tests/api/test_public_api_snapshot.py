# topmark:header:start
#
#   project      : TopMark
#   file         : test_public_api_snapshot.py
#   file_relpath : tests/api/test_public_api_snapshot.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Test the structured public API compatibility snapshot.

This test compares the current contracts exported through ``topmark.api.__all__``
against the committed, schema-versioned baseline.

How to generate the baseline:

Run the Make target to (re)generate the snapshot JSON:

```sh
    make api-snapshot-update
```

This calls ``tools/api_snapshot.py`` to write ``tests/api/public_api_snapshot.json``.
Commit the reviewed file together with the appropriate CHANGELOG entry.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.api_snapshot import SnapshotDocument
from tools.api_snapshot import collect_snapshot
from tools.api_snapshot import describe_snapshot_mismatch

BASELINE_JSON = "public_api_snapshot.json"
baseline_path: Path = Path(__file__).parent / BASELINE_JSON


def _collect() -> SnapshotDocument:
    return collect_snapshot()


@pytest.mark.skipif(
    not baseline_path.exists(),
    reason="No baseline snapshot file found. Run 'make api-snapshot-update' to generate.",
)
def test_public_api_snapshot() -> None:
    """Current public API contracts match the committed baseline JSON."""
    with baseline_path.open(encoding="utf-8") as f:
        baseline = json.load(f)
    current: SnapshotDocument = _collect()
    assert current == baseline, describe_snapshot_mismatch(baseline, current)
