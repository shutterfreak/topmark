# topmark:header:start
#
#   project      : TopMark
#   file         : test_public_api_snapshot.py
#   file_relpath : tests/api/test_public_api_snapshot.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Test the public API snapshot.

This test ensures that the public API of TopMark remains stable by comparing the current
snapshot of exported symbols and their callable signatures against a committed baseline.

How to generate the baseline:

Run the Make target to (re)generate the snapshot JSON:

```sh
    make api-snapshot-update
```

This calls ``tools/api_snapshot.py`` to write ``tests/api/public_api_snapshot.json``.
Commit the updated file together with a version bump and CHANGELOG entry.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from tools.api_snapshot import collect_snapshot

if TYPE_CHECKING:
    from collections.abc import Mapping

BASELINE_JSON = "public_api_snapshot.json"
baseline_path: Path = Path(__file__).parent / BASELINE_JSON


def _collect() -> Mapping[str, str]:
    return collect_snapshot()


@pytest.mark.skipif(
    not baseline_path.exists(),
    reason="No baseline snapshot file found. Run 'make api-snapshot-update' to generate.",
)
def test_public_api_snapshot() -> None:
    """Current public API signatures match the committed baseline JSON."""
    with baseline_path.open(encoding="utf-8") as f:
        baseline = json.load(f)
    current = _collect()
    baseline_keys = set(baseline)
    current_keys = set(current)
    missing = sorted(baseline_keys - current_keys)
    extra = sorted(current_keys - baseline_keys)
    changed = sorted(k for k in (baseline_keys & current_keys) if baseline[k] != current[k])
    msg_lines = [
        "Public API changed.\n"
        "Run 'make api-snapshot-update' to update, then review, bump version & update CHANGELOG."
    ]
    if missing:
        msg_lines.append(f"missing={missing}")
    if extra:
        msg_lines.append(f"extra={extra}")
    if changed:
        msg_lines.append(f"changed={changed}")
    assert current == baseline, "\n".join(msg_lines)
