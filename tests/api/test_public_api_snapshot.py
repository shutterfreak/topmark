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
    make public-api-update
```

This calls ``tools/api_snapshot.py`` to write ``tests/api/public_api_snapshot.json``.
Commit the updated file together with a version bump and CHANGELOG entry.
"""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING

import pytest

from tools.api_snapshot import collect_snapshot

if TYPE_CHECKING:
    from collections.abc import Mapping

BASELINE_JSON = "public_api_snapshot.json"
here: str = os.path.dirname(__file__)
baseline_path: str = os.path.join(here, BASELINE_JSON)


def _collect() -> Mapping[str, str]:
    return collect_snapshot()


@pytest.mark.skipif(
    not os.path.exists(baseline_path),
    reason="No baseline snapshot file found",
)
def test_public_api_snapshot() -> None:
    """Current public API signatures match the committed baseline JSON."""
    with open(baseline_path, encoding="utf-8") as f:
        baseline = json.load(f)
    assert _collect() == baseline, (
        "Public API changed. Run: make api-snapshot-update, then review, "
        "bump version & update CHANGELOG."
    )
