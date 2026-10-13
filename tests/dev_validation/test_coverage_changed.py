# topmark:header:start
#
#   project      : TopMark
#   file         : test_coverage_changed.py
#   file_relpath : tests/dev_validation/test_coverage_changed.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Tests for the changed-lines coverage diagnostic."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from tools.coverage_changed import ChangedFile
from tools.coverage_changed import assess_coverage
from tools.coverage_changed import format_assessment
from tools.coverage_changed import main
from tools.coverage_changed import parse_unified_diff

if TYPE_CHECKING:
    from pathlib import Path

    from _pytest.capture import CaptureResult

    from tools.coverage_changed import CoverageAssessment


@pytest.fixture
def coverage_report(tmp_path: Path) -> Path:
    """Create a small canonical coverage JSON fixture."""
    report: Path = tmp_path / "coverage.json"
    report.write_text(
        json.dumps(
            {
                "meta": {"format": 3, "version": "7.0"},
                "files": {
                    "src/topmark/example.py": {
                        "executed_lines": [1, 3, 7],
                        "missing_lines": [2, 5],
                        "excluded_lines": [4],
                        "missing_branches": [[3, 5], [7, 8]],
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    return report


@pytest.fixture
def source_tree(tmp_path: Path) -> Path:
    """Create source text used for diagnostic context."""
    source: Path = tmp_path / "src" / "topmark" / "example.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        "one\nmissing statement\nif condition:\nexcluded\nuntested branch\nend\nother branch\n",
        encoding="utf-8",
    )
    return tmp_path


@pytest.mark.dev_validation
def test_missing_report_is_not_assessed(tmp_path: Path) -> None:
    """An absent coverage report is a clear non-successful assessment state."""
    assessment: CoverageAssessment = assess_coverage(
        tmp_path / "coverage.json",
        [ChangedFile("src/topmark/example.py", frozenset({2}))],
        repository_root=tmp_path,
    )

    assert not assessment.assessed
    assert assessment.diagnostics == ()
    assert "not assessed" in format_assessment(assessment)
    assert "make coverage" in format_assessment(assessment)


@pytest.mark.dev_validation
def test_assessment_reports_uncovered_lines_and_branches(
    coverage_report: Path,
    source_tree: Path,
) -> None:
    """Missing changed statements and branch exits include useful source context."""
    assessment: CoverageAssessment = assess_coverage(
        coverage_report,
        [ChangedFile("src/topmark/example.py", frozenset({2, 3, 7}))],
        repository_root=source_tree,
    )

    assert assessment.assessed
    assert [(item.line, item.kind) for item in assessment.diagnostics] == [
        (2, "line"),
        (3, "branch"),
        (7, "branch"),
    ]
    output: str = format_assessment(assessment)
    assert "src/topmark/example.py:2: line" in output
    assert "missing statement" in output
    assert "branch to line 5 not taken" in output


@pytest.mark.dev_validation
def test_assessment_ignores_excluded_non_executable_and_unchanged_lines(
    coverage_report: Path,
    source_tree: Path,
) -> None:
    """Only changed executable coverage entries produce diagnostics."""
    assessment: CoverageAssessment = assess_coverage(
        coverage_report,
        [ChangedFile("src/topmark/example.py", frozenset({1, 4, 6, 99}))],
        repository_root=source_tree,
    )

    assert assessment.assessed
    assert assessment.diagnostics == ()


@pytest.mark.dev_validation
def test_parse_unified_diff_handles_added_modified_renamed_and_deleted_files() -> None:
    """Diff parsing uses current paths, skips deletions, and handles zero-length hunks."""
    patch = """\
diff --git a/src/topmark/old.py b/src/topmark/new.py
similarity index 80%
rename from src/topmark/old.py
rename to src/topmark/new.py
--- a/src/topmark/old.py
+++ b/src/topmark/new.py
@@ -3 +3,2 @@
+new line one
+new line two
@@ -10,2 +11,0 @@
-removed one
-removed two
diff --git a/src/topmark/deleted.py b/src/topmark/deleted.py
deleted file mode 100644
--- a/src/topmark/deleted.py
+++ /dev/null
@@ -1 +0,0 @@
-gone
diff --git a/src/topmark/added.py b/src/topmark/added.py
new file mode 100644
--- /dev/null
+++ b/src/topmark/added.py
@@ -0,0 +1 @@
+added
"""

    assert parse_unified_diff(patch) == (
        ChangedFile("src/topmark/added.py", frozenset({1})),
        ChangedFile("src/topmark/new.py", frozenset({3, 4})),
    )


@pytest.mark.dev_validation
def test_main_reports_missing_report_without_git_or_traceback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The command is safe when coverage has not been generated yet."""

    def changed(_: str) -> tuple[ChangedFile, ...]:
        return (ChangedFile("src/topmark/example.py", frozenset({1})),)

    def base(_: str | None) -> str:
        return "main"

    monkeypatch.setattr(
        "tools.coverage_changed.changed_files",
        changed,
    )
    monkeypatch.setattr("tools.coverage_changed.choose_base_reference", base)
    monkeypatch.chdir(tmp_path)

    assert main([]) == 0
    captured: CaptureResult[str] = capsys.readouterr()
    assert "Coverage was not assessed" in captured.out
    assert captured.err == ""
