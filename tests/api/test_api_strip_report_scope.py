# topmark:header:start
#
#   project      : TopMark
#   file         : test_api_strip_report_scope.py
#   file_relpath : tests/api/test_api_strip_report_scope.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""API tests dedicated to `strip()` report-scope filtering."""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark import api

if TYPE_CHECKING:
    from pathlib import Path


def test_strip_report_scope_filters_view(repo_py_with_header_and_xyz: Path) -> None:
    """`strip(..., report=...)` should filter the returned view by report scope."""
    src: Path = repo_py_with_header_and_xyz / "src"
    paths: list[Path] = [src / "with_header.py", src / "notes.xyz"]

    res_all: api.RunResult = api.strip(
        paths,
        apply=False,
        include_file_types=None,
        report="all",
    )
    view_all: set[Path] = {fr.path for fr in res_all.files}
    assert src / "with_header.py" in view_all
    assert src / "notes.xyz" in view_all

    res_actionable: api.RunResult = api.strip(
        paths,
        apply=False,
        include_file_types=None,
        report="actionable",
    )
    view_actionable: set[Path] = {fr.path for fr in res_actionable.files}
    assert src / "with_header.py" in view_actionable
    assert src / "notes.xyz" not in view_actionable

    res_noncompliant: api.RunResult = api.strip(
        paths,
        apply=False,
        include_file_types=None,
        report="noncompliant",
    )
    view_noncompliant: set[Path] = {fr.path for fr in res_noncompliant.files}
    assert src / "with_header.py" in view_noncompliant
    assert src / "notes.xyz" in view_noncompliant
