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

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

import topmark.core.outcomes
from tests.api.conftest import has_header
from tests.helpers.api import api_check_dir
from tests.helpers.api import api_strip_dir
from tests.helpers.api import by_path_outcome
from tests.helpers.io import read_text
from topmark import api
from topmark.api.runtime import ApiPipelineResultRun
from topmark.api.runtime import run_pipeline_results
from topmark.api.types import PublicPolicy
from topmark.api.types import PublicReportScopeLiteral
from topmark.core.constants import TOPMARK_START_MARKER
from topmark.core.errors import InvalidReportScopeError
from topmark.pipeline.pipelines import PipelineSelection
from topmark.pipeline.pipelines import select_pipeline
from topmark.runtime.model import RunOptions

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.pipeline.kinds import PipelineKindLiteral
    from topmark.processors.base import HeaderProcessor


def test_check_dry_run_reports_one_change_and_one_unchanged(
    repo_py_with_and_without_header: Path,
) -> None:
    """Dry-run: a.py would change, b.py is unchanged."""
    r: api.RunResult = api_check_dir(repo_py_with_and_without_header, apply=False)
    by_path: dict[Path, str] = by_path_outcome(r)
    a: Path = repo_py_with_and_without_header / "src" / "without_header.py"
    b: Path = repo_py_with_and_without_header / "src" / "with_header.py"

    # assert by_path.get(a) in {"would_change", "changed"}
    assert by_path.get(a) == topmark.core.outcomes.Outcome.WOULD_INSERT  # "would_change"
    assert by_path.get(b) == topmark.core.outcomes.Outcome.UNCHANGED  # "unchanged"
    assert r.written == 0 and r.failed == 0


def test_check_apply_add_only_inserts_header_for_missing(
    repo_py_with_and_without_header: Path, proc_py: HeaderProcessor
) -> None:
    """Apply add-only: only a.py gets a new header."""
    a: Path = repo_py_with_and_without_header / "src" / "without_header.py"
    b: Path = repo_py_with_and_without_header / "src" / "with_header.py"

    assert not has_header(read_text(a), proc_py, "\n")
    assert has_header(read_text(b), proc_py, "\n")

    r: api.RunResult = api_check_dir(
        repo_py_with_and_without_header,
        apply=True,
        policy=PublicPolicy(
            header_mutation_mode="add_only",
        ),
    )  # only add missing
    assert r.had_errors is False
    assert r.written >= 1

    # a.py now has a header, b.py unchanged
    assert has_header(read_text(a), proc_py, "\n")
    assert has_header(read_text(b), proc_py, "\n")


def test_check_apply_update_only_does_not_add_new_headers(
    repo_py_with_and_without_header: Path, proc_py: HeaderProcessor
) -> None:
    """Apply update-only: does not add header to missing a.py."""
    # Remove header from a.py (simulate a missing header)
    a: Path = repo_py_with_and_without_header / "src" / "without_header.py"
    a.write_text("print('hello')\n", encoding="utf-8")

    r: api.RunResult = api_check_dir(
        repo_py_with_and_without_header,
        apply=True,
        policy=PublicPolicy(
            header_mutation_mode="update_only",
        ),
        prune=False,
    )
    # Should not create a header in a.py because update_only=True
    assert r.bucket_summary is not None
    assert topmark.core.outcomes.Outcome.UPDATED.value not in r.bucket_summary
    assert r.had_errors is False
    assert has_header(read_text(a), proc_py, "\n") is False


def test_strip_dry_run_reports_would_change_on_files_with_headers(
    repo_py_with_and_without_header: Path,
) -> None:
    """Dry-run strip: would_change on files with headers."""
    r: api.RunResult = api_strip_dir(repo_py_with_and_without_header, apply=False)
    # At least b.py has a header; strip would remove it
    # assert r.summary.get("would_change", 0) >= 1
    assert topmark.core.outcomes.Outcome.WOULD_STRIP in r.summary


def test_strip_apply_removes_headers(
    repo_py_with_and_without_header: Path, proc_py: HeaderProcessor
) -> None:
    """Apply strip: removes header from b.py."""
    b: Path = repo_py_with_and_without_header / "src" / "with_header.py"

    assert has_header(read_text(b), proc_py, "\n")

    r: api.RunResult = api_strip_dir(repo_py_with_and_without_header, apply=True)
    assert r.had_errors is False
    assert r.written >= 1
    # Header gone
    assert not has_header(read_text(b), proc_py, "\n")


# ---- diff tests


def test_check_diff_is_available_when_views_are_pruned(
    repo_py_with_and_without_header: Path,
) -> None:
    """API check diff output should survive internal view pruning when requested."""
    path: Path = repo_py_with_and_without_header / "src" / "without_header.py"

    r: api.RunResult = api.check(
        [path],
        apply=False,
        diff=True,
        config=None,
        include_file_types=["python"],
        prune_views=True,
    )

    assert len(r.files) == 1
    diff: str | None = r.files[0].diff

    assert diff is not None
    assert f"--- {path}" in diff
    assert f"+++ {path}" in diff
    assert "@@" in diff
    assert f"+# {TOPMARK_START_MARKER}" in diff


def test_strip_diff_is_available_when_views_are_pruned(
    repo_py_with_and_without_header: Path,
) -> None:
    """API strip diff output should survive internal view pruning when requested."""
    path: Path = repo_py_with_and_without_header / "src" / "with_header.py"

    r: api.RunResult = api.strip(
        [path],
        apply=False,
        diff=True,
        config=None,
        include_file_types=["python"],
        prune_views=True,
    )

    assert len(r.files) == 1
    diff: str | None = r.files[0].diff

    assert diff is not None
    assert f"--- {path}" in diff
    assert f"+++ {path}" in diff
    assert "@@" in diff
    assert f"-# {TOPMARK_START_MARKER}" in diff


def test_run_pipeline_results_handles_empty_file_list(tmp_path: Path) -> None:
    """Empty file discovery yields an empty durable ProcessingResult batch.

    Verifies the result-oriented runtime path introduced for streaming-capable
    reduction handles runs with no selected files without producing results or
    pipeline-level errors.
    """
    pipeline: PipelineSelection = select_pipeline(
        "check",
        apply=False,
        diff=False,
    )
    run_options: RunOptions = RunOptions.from_pipeline_selection(pipeline)

    result: ApiPipelineResultRun = run_pipeline_results(
        pipeline=pipeline,
        paths=[tmp_path],
        run_options=run_options,
        base_config={
            "files": {"include": ["*.does-not-exist"]},
        },
    )

    assert result.file_list == []
    assert result.results == ()
    assert result.exit_code is None


@pytest.mark.parametrize("cmd", ["check", "strip"])
@pytest.mark.parametrize("scope", ["actionable", "noncompliant", "all"])
def test_check_and_strip_accept_public_report_scopes(
    repo_py_with_and_without_header: Path,
    cmd: PipelineKindLiteral,
    scope: PublicReportScopeLiteral,
) -> None:
    """Public check/strip entry points accept every supported report scope."""
    path: Path = repo_py_with_and_without_header / "src" / "without_header.py"

    match cmd:
        case "check":
            api_cmd = api.check
        case "strip":
            api_cmd = api.strip
        case _:
            pytest.fail(f"Invalid API command: {cmd}")

    result: api.RunResult = api_cmd(
        [path],
        apply=False,
        diff=False,
        config=None,
        include_file_types=["python"],
        report=scope,
        prune_views=True,
    )

    assert result.had_errors is False
    assert result.bucket_summary is not None


@pytest.mark.parametrize("cmd", ["check", "strip"])
def test_check_and_strip_reject_invalid_report_scope(
    repo_py_with_and_without_header: Path,
    cmd: PipelineKindLiteral,
) -> None:
    """Public check/strip entry points reject unsupported report scopes."""
    path: Path = repo_py_with_and_without_header / "src" / "without_header.py"

    match cmd:
        case "check":
            api_cmd = api.check
        case "strip":
            api_cmd = api.strip
        case _:
            pytest.fail(f"Invalid API command: {cmd}")

    with pytest.raises(InvalidReportScopeError):
        api_cmd(
            [path],
            apply=False,
            diff=False,
            config=None,
            include_file_types=["python"],
            report="non-existing",  # pyright: ignore[reportArgumentType]
            prune_views=True,
        )
