#
#   project      : TopMark
#   file         : test_api_report_scope.py
#   file_relpath : tests/api/test_api_report_scope.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""API report-scope contract tests for path-based pipeline commands.

These tests pin how `check()` and `strip()` filter their returned `RunResult`
file views for `report="actionable"`, `report="noncompliant"`, and
`report="all"`. Report scopes must change only the returned view, not pipeline
execution or aggregate counters.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from topmark import api

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.pipeline.kinds import PipelineKindLiteral


def _paths_by_report_scope(
    *,
    paths: list[Path],
    pipeline_kind: PipelineKindLiteral,
) -> dict[str, set[Path]]:
    """Return visible file paths for each public report scope."""
    scopes: tuple[str, ...] = ("actionable", "noncompliant", "all")
    paths_by_scope: dict[str, set[Path]] = {}

    for scope in scopes:
        match pipeline_kind:
            case "check":
                result: api.RunResult = api.check(
                    paths,
                    apply=False,
                    include_file_types=None,
                    report=scope,
                )
            case "strip":
                result = api.strip(
                    paths,
                    apply=False,
                    include_file_types=None,
                    report=scope,
                )
            case _:
                msg: str = f"Unsupported API command: {pipeline_kind}"
                raise ValueError(msg)

        paths_by_scope[scope] = {file_result.path for file_result in result.files}

    return paths_by_scope


@pytest.mark.parametrize("pipeline_kind", ["check", "strip"])
def test_check_and_strip_report_scope_for_known_header_unsupported_file(
    pipeline_kind: PipelineKindLiteral,
    tmp_path: Path,
) -> None:
    """Known header-unsupported files are noncompliant but not actionable."""
    py_typed: Path = tmp_path / "py.typed"
    py_typed.touch()
    paths_by_scope: dict[str, set[Path]] = _paths_by_report_scope(
        paths=[py_typed],
        pipeline_kind=pipeline_kind,
    )

    assert paths_by_scope["actionable"] == set()
    assert paths_by_scope["noncompliant"] == {py_typed}
    assert paths_by_scope["all"] == {py_typed}


def test_check_report_scope_hides_compliant_and_non_actionable_files(
    repo_py_with_header_and_xyz: Path,
) -> None:
    """`check()` separates compliant, unsupported, and actionable results."""
    root: Path = repo_py_with_header_and_xyz
    compliant: Path = root / "src" / "with_header.py"
    unsupported: Path = root / "src" / "notes.xyz"
    paths_by_scope: dict[str, set[Path]] = _paths_by_report_scope(
        paths=[compliant, unsupported],
        pipeline_kind="check",
    )

    assert paths_by_scope["actionable"] == set()
    assert paths_by_scope["noncompliant"] == {unsupported}
    assert paths_by_scope["all"] == {compliant, unsupported}


def test_check_report_actionable_keeps_supported_headerless_file(
    repo_py_with_and_without_header: Path,
) -> None:
    """`check(report="actionable")` keeps files that can receive a header."""
    root: Path = repo_py_with_and_without_header
    actionable: Path = root / "src" / "without_header.py"
    compliant: Path = root / "src" / "with_header.py"

    result: api.RunResult = api.check(
        [root],
        apply=False,
        report="actionable",
    )
    visible_paths: set[Path] = {file_result.path for file_result in result.files}

    assert actionable in visible_paths
    assert compliant not in visible_paths
    assert result.skipped >= 1


def test_check_report_scope_distinguishes_actionable_from_noncompliant(
    repo_py_toml_xyz_no_header: Path,
) -> None:
    """`check()` treats supported headerless files as actionable."""
    src: Path = repo_py_toml_xyz_no_header / "src"
    actionable: Path = src / "without_header.py"
    unsupported: Path = src / "note.xyz"
    paths_by_scope: dict[str, set[Path]] = _paths_by_report_scope(
        paths=[actionable, unsupported],
        pipeline_kind="check",
    )

    assert paths_by_scope["actionable"] == {actionable}
    assert paths_by_scope["noncompliant"] == {actionable, unsupported}
    assert paths_by_scope["all"] == {actionable, unsupported}


def test_strip_report_scope_hides_supported_headerless_file_when_not_all(
    tmp_path: Path,
) -> None:
    """`strip()` treats a supported headerless file as already compliant."""
    headerless: Path = tmp_path / "test.py"
    headerless.write_text("print('Hello, World!')\n", encoding="utf-8")
    paths_by_scope: dict[str, set[Path]] = _paths_by_report_scope(
        paths=[headerless],
        pipeline_kind="strip",
    )

    assert paths_by_scope["actionable"] == set()
    assert paths_by_scope["noncompliant"] == set()
    assert paths_by_scope["all"] == {headerless}


def test_strip_report_scope_distinguishes_actionable_from_noncompliant(
    repo_py_with_header_and_xyz: Path,
) -> None:
    """`strip()` treats supported headered files as actionable."""
    src: Path = repo_py_with_header_and_xyz / "src"
    actionable: Path = src / "with_header.py"
    unsupported: Path = src / "notes.xyz"
    paths_by_scope: dict[str, set[Path]] = _paths_by_report_scope(
        paths=[actionable, unsupported],
        pipeline_kind="strip",
    )

    assert paths_by_scope["actionable"] == {actionable}
    assert paths_by_scope["noncompliant"] == {actionable, unsupported}
    assert paths_by_scope["all"] == {actionable, unsupported}
