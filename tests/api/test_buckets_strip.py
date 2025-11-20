# topmark:header:start
#
#   project      : TopMark
#   file         : test_buckets_strip.py
#   file_relpath : tests/api/test_buckets_strip.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Tests covering how various header situations map to bucket outcomes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark import api
from topmark.api.types import Outcome

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path


def _summary_keys(run: api.RunResult) -> set[str]:
    summary: Mapping[str, int] | None = run.bucket_summary
    return set(summary.keys()) if summary else set()


def test_bucket_strip_ready_dry_run(repo_py_with_header: Path) -> None:
    """Stripping a file that has a header should produce `strip:ready` (dry-run)."""
    root: Path = repo_py_with_header
    target = root / "src" / "with_header.py"
    r: api.RunResult = api.strip([target], apply=False, file_types=["python"])
    keys: set[str] = _summary_keys(r)
    assert Outcome.WOULD_STRIP.value in keys


def test_bucket_strip_none_when_no_header(tmp_path: Path) -> None:
    """No header present should land in `strip:none`."""
    f: Path = tmp_path / "no_header.py"
    f.write_text("print('x')\n", encoding="utf-8")
    r: api.RunResult = api.strip([f], apply=False, file_types=["python"])
    keys: set[str] = _summary_keys(r)
    # assert "strip:none" in keys
    assert Outcome.UNCHANGED.value in keys
