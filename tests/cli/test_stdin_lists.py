# topmark:header:start
#
#   file         : test_stdin_lists.py
#   file_relpath : tests/cli/test_stdin_lists.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Test reading file list from stdin with unified CLI semantics and dry-run behavior."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.cli.conftest import assert_SUCCESS, assert_WOULD_CHANGE, run_cli_in

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize(
    "command,expect",
    [
        ("check", "WOULD_CHANGE"),
        ("strip", "SUCCESS"),
    ],
)
def test_files_from_stdin_list_basic(tmp_path: Path, command: str, expect: str) -> None:
    """--files-from - reads newline-delimited paths from STDIN."""
    f = tmp_path / "t.py"
    f.write_text("print('y')\n", "utf-8")
    result = run_cli_in(tmp_path, [command, "--files-from", "-"], input_text=f.name + "\n")
    if expect == "WOULD_CHANGE":
        assert_WOULD_CHANGE(result)
    else:
        assert_SUCCESS(result)


def test_include_from_stdin_filters_candidates(tmp_path: Path) -> None:
    """--include-from - adds include globs from STDIN (intersection)."""
    a = tmp_path / "a.py"
    a.write_text("print()\n", "utf-8")
    b = tmp_path / "b.txt"
    b.write_text("x\n", "utf-8")
    # Provide a superset as PATHS; include-from - narrows to *.py
    result = run_cli_in(
        tmp_path,
        ["check", "--include-from", "-", "a.py", "b.txt"],
        input_text="*.py\n",
    )
    # Only a.py is considered → WOULD_CHANGE (header would be added)
    assert_WOULD_CHANGE(result)


def test_exclude_from_stdin_filters_candidates(tmp_path: Path) -> None:
    """--exclude-from - adds exclude globs from STDIN (subtraction)."""
    a = tmp_path / "a.py"
    a.write_text("print()\n", "utf-8")
    b = tmp_path / "b.py"
    b.write_text("print()\n", "utf-8")
    # Exclude b.py from the candidate set; only a.py remains → WOULD_CHANGE
    result = run_cli_in(
        tmp_path,
        ["check", "--exclude-from", "-", "a.py", "b.py"],
        input_text="b.py\n",
    )
    assert_WOULD_CHANGE(result)


@pytest.mark.parametrize("opt", ["--files-from", "--include-from", "--exclude-from"])
def test_from_stdin_empty_is_noop(tmp_path: Path, opt: str) -> None:
    """Empty STDIN with …-from - yields empty additions and should not crash."""
    # No paths → no effect. The CLI should treat as nothing added/filtered.
    # With no positional inputs either, your CLI currently prints guidance and exits usage.
    # Here we give a benign PATH so the command runs.
    f = tmp_path / "x.py"
    f.write_text("print()\n", "utf-8")
    result = run_cli_in(tmp_path, ["check", opt, "-", f.name], input_text="")
    # With only x.py left, we expect WOULD_CHANGE
    assert_WOULD_CHANGE(result)
