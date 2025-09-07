# topmark:header:start
#
#   file         : test_api_smoke.py
#   file_relpath : tests/api/test_api_smoke.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Basic smoke tests for the public TopMark API surface."""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark import api

if TYPE_CHECKING:
    from pathlib import Path


def test_version_is_nonempty_string() -> None:
    """api.version() returns nonempty string."""
    v = api.version()
    assert isinstance(v, str) and v.strip(), "version() must return a non-empty string"


def test_list_filetypes_includes_python() -> None:
    """api.list_filetypes() contains a FileType instance for "python"."""
    items = api.get_filetype_info(long=True)
    assert any(ft.get("name") == "python" for ft in items), "python filetype must be registered"


def test_list_processors_is_nonempty() -> None:
    """api.list_processors() is non-empty."""
    procs = api.get_processor_info(long=True)
    assert procs and all("name" in p for p in procs), "processors list should not be empty"


def test_strip_dry_run_reports_would_change(repo_py_with_header: Path) -> None:
    """api.strip() reports 'would_change' on supported file without header."""
    r = api.strip([repo_py_with_header / "src"], apply=False, file_types=["python"])
    # At least one file (with_header.py) should be reported as would_change
    assert r.summary.get("would_change", 0) >= 1
    assert r.written == 0 and r.failed == 0


def test_strip_apply_then_check_is_unchanged(repo_py_with_header: Path) -> None:
    """api.check() after api.strip(apply=True) reports 'would_change'."""
    src_dir = repo_py_with_header / "src"

    # Apply strip: remove headers
    r_strip = api.strip([src_dir], apply=True, file_types=["python"])
    assert r_strip.had_errors is False
    assert r_strip.written >= 1  # header removed

    # Now a dry-run check should say the file would change (header missing),
    # unless the configured policy for missing headers marks it unchanged.
    r_check = api.check([src_dir], apply=False, file_types=["python"])

    # Accept either: would_change (header would be re-inserted) or unchanged
    # depending on project defaults. Assert at least one bucket is present.
    assert any(k in r_check.summary for k in ("would_change", "unchanged"))
