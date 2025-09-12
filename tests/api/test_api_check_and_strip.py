# topmark:header:start
#
#   project      : TopMark
#   file         : test_api_check_and_strip.py
#   file_relpath : tests/api/test_api_check_and_strip.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""End-to-end API checks for check()/strip() on two Python files."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.api.conftest import api_check_dir, api_strip_dir, by_path_outcome, has_header, read_text

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.pipeline.processors.base import HeaderProcessor


def test_check_dry_run_reports_one_change_and_one_unchanged(
    repo_py_with_and_without_header: Path,
) -> None:
    """Dry-run: a.py would change, b.py is unchanged."""
    r = api_check_dir(repo_py_with_and_without_header, apply=False)
    by_path = by_path_outcome(r)
    a = repo_py_with_and_without_header / "src" / "without_header.py"
    b = repo_py_with_and_without_header / "src" / "with_header.py"

    # assert by_path.get(a) in {"would_change", "changed"}
    assert by_path.get(a) == "would_change"
    assert by_path.get(b) == "unchanged"
    assert r.written == 0 and r.failed == 0


def test_check_apply_add_only_inserts_header_for_missing(
    repo_py_with_and_without_header: Path, proc_py: HeaderProcessor
) -> None:
    """Apply add-only: only a.py gets a new header."""
    a = repo_py_with_and_without_header / "src" / "without_header.py"
    b = repo_py_with_and_without_header / "src" / "with_header.py"

    assert not has_header(read_text(a), proc_py)
    assert has_header(read_text(b), proc_py)

    r = api_check_dir(
        repo_py_with_and_without_header, apply=True, add_only=True
    )  # only add missing
    assert r.had_errors is False
    assert r.written >= 1

    # a.py now has a header, b.py unchanged
    assert has_header(read_text(a), proc_py)
    assert has_header(read_text(b), proc_py)


def test_check_apply_update_only_does_not_add_new_headers(
    repo_py_with_and_without_header: Path, proc_py: HeaderProcessor
) -> None:
    """Apply update-only: does not add header to missing a.py."""
    # Remove header from a.py (simulate a missing header)
    a = repo_py_with_and_without_header / "src" / "without_header.py"
    a.write_text("print('hello')\n", encoding="utf-8")

    r = api_check_dir(repo_py_with_and_without_header, apply=True, update_only=True)
    # Should not create a header in a.py because update_only=True
    assert r.had_errors is False
    assert has_header(read_text(a), proc_py) is False


def test_skip_compliant_filters_out_b_py_in_view(repo_py_with_and_without_header: Path) -> None:
    """skip_compliant: b.py filtered out, a.py remains."""
    r = api_check_dir(repo_py_with_and_without_header, apply=False, skip_compliant=True)
    returned_paths = {fr.path for fr in r.files}
    a = repo_py_with_and_without_header / "src" / "without_header.py"
    b = repo_py_with_and_without_header / "src" / "with_header.py"

    assert a in returned_paths  # non-compliant remains visible
    assert b not in returned_paths  # compliant filtered out
    assert r.skipped >= 1


def test_strip_dry_run_reports_would_change_on_files_with_headers(
    repo_py_with_and_without_header: Path,
) -> None:
    """Dry-run strip: would_change on files with headers."""
    r = api_strip_dir(repo_py_with_and_without_header, apply=False)
    # At least b.py has a header; strip would remove it
    assert r.summary.get("would_change", 0) >= 1


def test_strip_apply_removes_headers(
    repo_py_with_and_without_header: Path, proc_py: HeaderProcessor
) -> None:
    """Apply strip: removes header from b.py."""
    b = repo_py_with_and_without_header / "src" / "with_header.py"

    assert has_header(read_text(b), proc_py)

    r = api_strip_dir(repo_py_with_and_without_header, apply=True)
    assert r.had_errors is False
    assert r.written >= 1
    # Header gone
    assert not has_header(read_text(b), proc_py)
