# topmark:header:start
#
#   project      : TopMark
#   file         : test_buckets_check.py
#   file_relpath : tests/api/test_buckets_check.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Tests covering how various header situations map to bucket outcomes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from topmark import api
from topmark.api.public_types import PublicPolicy
from topmark.api.types import Outcome
from topmark.constants import TOPMARK_END_MARKER, TOPMARK_START_MARKER

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from topmark.pipeline.processors.base import HeaderProcessor


def _summary_keys(run: api.RunResult) -> set[str]:
    summary: Mapping[str, int] | None = run.bucket_summary
    return set(summary.keys()) if summary else set()


def test_bucket_insert_missing_header_dry_run(repo_py_with_and_without_header: Path) -> None:
    """When header is missing and fields are configured, we should see `insert`."""
    root: Path = repo_py_with_and_without_header
    r: api.RunResult = api.check(
        [root / "src" / "without_header.py"], apply=False, file_types=["python"]
    )
    keys: set[str] = _summary_keys(r)
    assert Outcome.WOULD_INSERT.value in keys


def test_bucket_ok_up_to_date(repo_py_with_header: Path) -> None:
    """Compliant file should land in `ok`."""
    root: Path = repo_py_with_header
    r: api.RunResult = api.check(
        [root / "src" / "with_header.py"], apply=False, file_types=["python"]
    )
    keys: set[str] = _summary_keys(r)
    assert Outcome.UNCHANGED.value in keys


def test_bucket_no_fields_when_header_fields_empty(tmp_path: Path) -> None:
    """Empty header_fields config yields `no_fields` (builder sets NO_FIELDS)."""
    f: Path = tmp_path / "a.py"
    f.write_text("print('x')\n", encoding="utf-8")

    # Minimal TOML config that results in GenerationStatus.NO_FIELDS
    cfg: Mapping[str, Any] = {"header": {"fields": []}}
    r: api.RunResult = api.check([f], apply=False, file_types=["python"], config=cfg)
    keys: set[str] = _summary_keys(r)
    assert Outcome.WOULD_INSERT.value in keys


def test_bucket_header_empty_detected(tmp_path: Path, proc_py: HeaderProcessor) -> None:
    """An existing but empty TopMark header maps to `header:empty`."""
    # Create a file with an empty TopMark header block for Python
    f: Path = tmp_path / "empty_header.py"
    f.write_text(
        # A minimal, syntactically valid empty TopMark block for the Python processor
        f"# {TOPMARK_START_MARKER}\n#\n# {TOPMARK_END_MARKER}\nprint('x')\n",
        encoding="utf-8",
    )
    r: api.RunResult = api.check([f], apply=False, file_types=["python"])
    keys: set[str] = _summary_keys(r)
    # assert "header:empty" in keys
    assert Outcome.WOULD_UPDATE.value in keys


def test_bucket_header_malformed_detected(tmp_path: Path) -> None:
    """Malformed header should map to `header:malformed`."""
    f: Path = tmp_path / "malformed.py"
    f.write_text(
        f"# {TOPMARK_START_MARKER}\n# some : field\nprint('x')\n",  # no end marker
        encoding="utf-8",
    )
    r: api.RunResult = api.check([f], apply=False, file_types=["python"])
    keys: set[str] = _summary_keys(r)
    assert Outcome.ERROR.value in keys


def test_bucket_blocked_policy_update_only_blocks_insert(tmp_path: Path) -> None:
    """When update_only is True and header is missing, expect `blocked:policy`."""
    f: Path = tmp_path / "no_header.py"
    f.write_text("print('x')\n", encoding="utf-8")
    policy = PublicPolicy(add_only=False, update_only=True)
    r: api.RunResult = api.check([f], apply=False, file_types=["python"], policy=policy)
    keys: set[str] = _summary_keys(r)
    # assert "blocked:policy" in keys
    assert Outcome.SKIPPED.value in keys
