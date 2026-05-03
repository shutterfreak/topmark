# topmark:header:start
#
#   project      : TopMark
#   file         : test_stdin_lists.py
#   file_relpath : tests/cli/test_stdin_lists.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""List/pattern-list STDIN CLI behavior tests.

This module covers valid STDIN list modes:
- `--files-from -` for newline-delimited file paths,
- `--include-from -` for include patterns,
- `--exclude-from -` for exclude patterns.

Invalid STDIN mode combinations are covered in `tests/cli/test_stdin_errors.py`.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from click.testing import Result

from tests.cli.conftest import assert_SUCCESS
from tests.cli.conftest import assert_WOULD_CHANGE
from tests.cli.conftest import run_cli_in
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt

if TYPE_CHECKING:
    from pathlib import Path

    from click.testing import Result


# --- File-list STDIN mode ---


@pytest.mark.parametrize(
    "command,expected_exit",
    [
        (CliCmd.CHECK, "WOULD_CHANGE"),
        (CliCmd.STRIP, "SUCCESS"),
    ],
)
def test_files_from_stdin_reads_newline_delimited_paths(
    tmp_path: Path,
    command: str,
    expected_exit: str,
) -> None:
    """`--files-from -` should read newline-delimited paths from STDIN."""
    f: Path = tmp_path / "t.py"
    f.write_text("print('y')\n", "utf-8")
    result: Result = run_cli_in(
        tmp_path,
        [
            command,
            CliOpt.FILES_FROM,
            "-",
        ],
        input_text=f.name + "\n",
    )
    if expected_exit == "WOULD_CHANGE":
        assert_WOULD_CHANGE(result)
    else:
        assert_SUCCESS(result)


# --- Pattern-list STDIN mode: include filters ---
def test_include_from_stdin_narrows_candidate_paths(tmp_path: Path) -> None:
    """`--include-from -` should narrow candidates using patterns from STDIN."""
    a: Path = tmp_path / "a.py"
    a.write_text("print()\n", "utf-8")
    b: Path = tmp_path / "b.txt"
    b.write_text("x\n", "utf-8")
    # Provide a superset as paths; include-from narrows the candidates to *.py.
    result: Result = run_cli_in(
        tmp_path,
        [
            CliCmd.CHECK,
            CliOpt.INCLUDE_FROM,
            "-",
            "a.py",
            "b.txt",
        ],
        input_text="*.py\n",
    )
    # Only a.py is considered, and it needs a header.
    assert_WOULD_CHANGE(result)


# --- Pattern-list STDIN mode: exclude filters ---
def test_exclude_from_stdin_removes_candidate_paths(tmp_path: Path) -> None:
    """`--exclude-from -` should remove candidates using patterns from STDIN."""
    a: Path = tmp_path / "a.py"
    a.write_text("print()\n", "utf-8")
    b: Path = tmp_path / "b.py"
    b.write_text("print()\n", "utf-8")
    # Exclude b.py from the candidate set; only a.py remains and needs a header.
    result: Result = run_cli_in(
        tmp_path,
        [
            CliCmd.CHECK,
            CliOpt.EXCLUDE_FROM,
            "-",
            "a.py",
            "b.py",
        ],
        input_text="b.py\n",
    )
    assert_WOULD_CHANGE(result)


# --- Empty STDIN list/pattern input ---
@pytest.mark.parametrize("opt", [CliOpt.FILES_FROM, CliOpt.INCLUDE_FROM, CliOpt.EXCLUDE_FROM])
def test_empty_stdin_for_from_options_keeps_explicit_path_candidates(
    tmp_path: Path, opt: str
) -> None:
    """Empty `*-from -` input should not remove explicit path candidates."""
    # Empty STDIN contributes no additional paths or patterns.
    # The explicit path remains selected, so the command should still run.
    f: Path = tmp_path / "x.py"
    f.write_text("print()\n", "utf-8")
    result: Result = run_cli_in(
        tmp_path,
        [
            CliCmd.CHECK,
            opt,
            "-",
            f.name,
        ],
        input_text="",
    )
    # x.py remains selected and needs a header.
    assert_WOULD_CHANGE(result)
