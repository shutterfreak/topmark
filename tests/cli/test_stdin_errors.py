# topmark:header:start
#
#   project      : TopMark
#   file         : test_stdin_errors.py
#   file_relpath : tests/cli/test_stdin_errors.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""STDIN-related CLI usage-error contract tests.

This module covers invalid combinations of TopMark's STDIN modes:
- content-on-STDIN mode (`-` as the input path),
- list-on-STDIN mode (`--files-from -`),
- pattern-list-on-STDIN mode (`--include-from -` / `--exclude-from -`).

These tests pin the documented usage-error contract: invalid STDIN mode
combinations exit with `USAGE_ERROR` (64) and emit actionable diagnostics.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from click.testing import Result

from tests.cli.conftest import assert_human_output_contains
from tests.cli.conftest import assert_USAGE_ERROR
from tests.cli.conftest import run_cli
from tests.cli.conftest import run_cli_in
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt

if TYPE_CHECKING:
    from pathlib import Path

    from click.testing import Result


# All tests in this module pin documented CLI usage-error behavior.
pytestmark: pytest.MarkDecorator = pytest.mark.exit_code


# --- Content-on-STDIN mode: missing stdin filename ---
@pytest.mark.parametrize("command", [CliCmd.CHECK, CliCmd.STRIP])
def test_content_stdin_without_filename_exits_usage_error(command: str) -> None:
    """Content-on-STDIN mode without a stdin filename should exit usage error."""
    result: Result = run_cli(
        [
            command,
            "-",
        ],
        input_text="",
    )

    assert_USAGE_ERROR(result)


# --- Content-on-STDIN mode: mixed with explicit paths ---
def test_check_rejects_content_stdin_with_file(tmp_path: Path) -> None:
    """`check` should reject content-on-STDIN mode mixed with a file path."""
    (tmp_path / "x.py").write_text("print('x')\n", "utf-8")

    # Content-on-STDIN (`-`) is mutually exclusive with explicit paths.
    result: Result = run_cli_in(
        tmp_path,
        [CliCmd.CHECK, "-", "x.py"],
        input_text="print('x')\n",
    )

    assert_USAGE_ERROR(result)
    # Diagnostic should point users toward the STDIN/path conflict.
    assert_human_output_contains(
        output_format=None,
        output=result.output,
        expected="-",
    )


def test_strip_rejects_content_stdin_with_file(tmp_path: Path) -> None:
    """`strip` should reject content-on-STDIN mode mixed with a file path."""
    (tmp_path / "h.py").write_text("# topmark:header:start\n# h\n# topmark:header:end\n", "utf-8")

    result: Result = run_cli_in(
        tmp_path,
        [CliCmd.STRIP, "-", "h.py"],
        input_text="# topmark:header:start\n# h\n# topmark:header:end\n",
    )

    assert_USAGE_ERROR(result)
    assert_human_output_contains(
        output_format=None,
        output=result.output,
        expected="-",
    )


def test_check_rejects_content_stdin_with_directory(tmp_path: Path) -> None:
    """`check` should reject content-on-STDIN mode mixed with a directory path."""
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "y.py").write_text("print('y')\n", "utf-8")

    result: Result = run_cli_in(
        tmp_path,
        [CliCmd.CHECK, "-", "pkg"],
        input_text="print('y')\n",
    )

    assert_USAGE_ERROR(result)
    assert_human_output_contains(
        output_format=None,
        output=result.output,
        expected="-",
    )


def test_strip_rejects_content_stdin_with_directory(tmp_path: Path) -> None:
    """`strip` should reject content-on-STDIN mode mixed with a directory path."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "index.md").write_text("<!-- topmark:header:start -->\n", "utf-8")
    result: Result = run_cli_in(
        tmp_path,
        [CliCmd.STRIP, "-", "docs"],
        input_text="<!-- topmark:header:start -->\n",
    )
    assert_USAGE_ERROR(result)
    assert_human_output_contains(
        output_format=None,
        output=result.output,
        expected="-",
    )


# --- List/pattern-list STDIN modes: single consumer rule ---
def test_only_one_list_mode_option_may_consume_stdin(tmp_path: Path) -> None:
    """Only one list/pattern-list option may consume STDIN in a single invocation."""
    (tmp_path / "a.py").write_text("print()\n", "utf-8")
    # Both include-from and files-from try to consume `-` as STDIN.
    result: Result = run_cli_in(
        tmp_path,
        [CliCmd.CHECK, CliOpt.INCLUDE_FROM, "-", CliOpt.FILES_FROM, "-", "a.py"],
        input_text="*.py\n",
    )

    assert_USAGE_ERROR(result)
    assert_human_output_contains(
        output_format=None,
        output=result.output,
        expected="-",
    )
