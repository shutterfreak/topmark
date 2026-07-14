# topmark:header:start
#
#   project      : TopMark
#   file         : test_code_hygiene_tooling.py
#   file_relpath : tests/dev_validation/test_code_hygiene_tooling.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Developer-validation tests for code-prose hygiene tooling."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tools.docs.check_code_hygiene import check_python_file
from tools.docs.check_code_hygiene import iter_python_files
from tools.docs.check_code_hygiene import main

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.dev_validation
def test_python_file_check_reports_smart_punctuation_in_prose(tmp_path: Path) -> None:
    """The checker reports smart punctuation in strings and comments with source lines."""
    source_path: Path = tmp_path / "sample.py"
    source_path.write_text(
        '"""Use \u201cplain quotes\u201d in documentation."""\nvalue = 1  # Avoid \u2014 here.\n',
        encoding="utf-8",
    )

    diagnostics = check_python_file(source_path)

    assert [
        (diagnostic.line, diagnostic.character, diagnostic.replacement)
        for diagnostic in diagnostics
    ] == [
        (1, "\u201c", '"'),
        (1, "\u201d", '"'),
        (2, "\u2014", "-"),
    ]


@pytest.mark.dev_validation
def test_python_file_discovery_skips_excluded_environments(tmp_path: Path) -> None:
    """Python discovery excludes generated environment trees while retaining source files."""
    included_path: Path = tmp_path / "tools" / "check.py"
    excluded_path: Path = tmp_path / ".venv" / "generated.py"
    for path in (included_path, excluded_path):
        path.parent.mkdir(parents=True)
        path.write_text("value = 1\n", encoding="utf-8")

    assert list(iter_python_files((tmp_path,))) == [included_path]


@pytest.mark.dev_validation
def test_code_hygiene_main_returns_failure_with_actionable_diagnostic(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The command reports the file and line and fails when invalid prose is present."""
    source_path: Path = tmp_path / "sample.py"
    source_path.write_text("# Avoid \u2026 here.\n", encoding="utf-8")

    assert main([str(source_path)]) == 1
    assert capsys.readouterr().out == f"{source_path}:1: replace '\u2026' with '...'\n"
