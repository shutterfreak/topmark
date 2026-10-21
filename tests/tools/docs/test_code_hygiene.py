# topmark:header:start
#
#   project      : TopMark
#   file         : test_code_hygiene.py
#   file_relpath : tests/tools/docs/test_code_hygiene.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Tests for code-prose hygiene tooling."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tools.docs import check_code_hygiene as code_hygiene
from tools.docs.check_code_hygiene import Diagnostic
from tools.docs.check_code_hygiene import check_python_file
from tools.docs.check_code_hygiene import iter_python_files
from tools.docs.check_code_hygiene import main

if TYPE_CHECKING:
    from collections.abc import Iterable
    from collections.abc import Iterator
    from pathlib import Path

    import pytest


def test_python_file_check_reports_smart_punctuation_in_prose(
    tmp_path: Path,
) -> None:
    """The checker reports smart punctuation with 1-based source positions."""
    source_path: Path = tmp_path / "sample.py"
    source_path.write_text(
        '"""Use \u201cplain quotes\u201d in documentation."""\n'
        "value = 1  # Avoid \u2014 here.\n"
        'message = """\nUse \u2026 here.\n"""\n',
        encoding="utf-8",
    )

    diagnostics: list[Diagnostic] = check_python_file(source_path)

    assert [
        (diagnostic.line, diagnostic.column, diagnostic.character, diagnostic.replacement)
        for diagnostic in diagnostics
    ] == [
        (1, 8, "\u201c", '"'),
        (1, 21, "\u201d", '"'),
        (2, 20, "\u2014", "-"),
        (4, 5, "\u2026", "..."),
    ]


def test_python_file_discovery_skips_excluded_and_gitignored_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Python discovery excludes generated, absent, non-Python, and Git-ignored paths."""
    included_path: Path = tmp_path / "tools" / "check.py"
    excluded_path: Path = tmp_path / ".venv" / "generated.py"
    gitignored_path: Path = tmp_path / "tools" / "generated.py"
    non_python_path: Path = tmp_path / "notes.txt"
    for path in (included_path, excluded_path, gitignored_path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("value = 1\n", encoding="utf-8")
    non_python_path.write_text("Notes\n", encoding="utf-8")

    def filter_gitignored_paths(paths: Iterable[Path]) -> Iterator[Path]:
        """Yield paths except the fixture's Git-ignored Python file."""
        yield from (path for path in paths if path != gitignored_path)

    monkeypatch.setattr(
        code_hygiene,
        "iter_non_gitignored_paths",
        filter_gitignored_paths,
    )

    assert list(
        iter_python_files(
            (
                tmp_path / "missing",
                tmp_path,
                non_python_path,
            )
        )
    ) == [included_path]


def test_code_hygiene_main_returns_failure_with_actionable_diagnostic(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The command reports the file, line, and column for invalid prose."""
    source_path: Path = tmp_path / "sample.py"
    source_path.write_text("# Avoid \u2026 here.\n", encoding="utf-8")

    assert main([str(source_path)]) == 1
    assert capsys.readouterr().out == f"{source_path}:1:9: replace '\u2026' with '...'\n"
