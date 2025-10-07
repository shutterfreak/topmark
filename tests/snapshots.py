# topmark:header:start
#
#   project      : TopMark
#   file         : snapshots.py
#   file_relpath : tests/snapshots.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Tiny snapshot helpers for tests (no external dependency)."""

# pyright: strict
from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def write_and_read(path: Path, data: str) -> str:
    """Write ``data`` to ``path`` and read it back (UTF-8)."""
    path.write_text(data, encoding="utf-8")
    return path.read_text(encoding="utf-8")


def assert_snapshot(actual: str, snapshot_path: Path) -> None:
    """Assert that ``actual`` equals the contents of ``snapshot_path``.

    If the file does not exist yet, it is created and the test fails with a
    message prompting a re-run (to review/commit the snapshot).
    """
    # If the snapshot doesn’t exist yet, create it (first run UX).
    if not snapshot_path.exists():
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        snapshot_path.write_text(actual, encoding="utf-8")
        # Explicitly fail to force review/commit of the new snapshot.
        raise AssertionError(f"Snapshot created at {snapshot_path}. Re-run to validate.")
    expected: str = snapshot_path.read_text(encoding="utf-8")
    if actual != expected:
        # Show a short stable diff hint via hashes to avoid huge output noise
        raise AssertionError(
            f"Snapshot mismatch for {snapshot_path}\n"
            f"expected_sha256={hashlib.sha256(expected.encode()).hexdigest()}\n"
            f"actual_sha256=  {hashlib.sha256(actual.encode()).hexdigest()}"
        )
