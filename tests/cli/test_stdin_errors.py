# topmark:header:start
#
#   project      : TopMark
#   file         : test_stdin_errors.py
#   file_relpath : tests/cli/test_stdin_errors.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Mutual exclusion between content-on-STDIN ('-') and explicit paths.

This module ensures the CLI rejects invocations that combine `'-'` (read a
single file's *content* from STDIN) with explicit file or directory arguments.
Both the default (check/apply) command and the `strip` subcommand must exit
with `ExitCode.USAGE_ERROR (64)` and emit a helpful error message.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.cli.conftest import assert_USAGE_ERROR, run_cli_in

if TYPE_CHECKING:
    from pathlib import Path


def test_default_rejects_stdin_with_file(tmp_path: Path) -> None:
    """Default command: error if '-' (STDIN) is combined with a file path."""
    (tmp_path / "x.py").write_text("print('x')\n", "utf-8")

    # Content-on-STDIN ("-") mixed with an explicit path must error
    result = run_cli_in(tmp_path, ["check", "-", "x.py"], input_text="print('x')\n")

    assert_USAGE_ERROR(result)
    # Message should mention '-' / STDIN and path mixing
    assert "-" in result.output or "STDIN" in result.output


def test_strip_rejects_stdin_with_file(tmp_path: Path) -> None:
    """Strip subcommand: error if '-' (STDIN) is combined with a file path."""
    (tmp_path / "h.py").write_text("# topmark:header:start\n# h\n# topmark:header:end\n", "utf-8")

    result = run_cli_in(
        tmp_path,
        ["strip", "-", "h.py"],
        input_text="# topmark:header:start\n# h\n# topmark:header:end\n",
    )

    assert_USAGE_ERROR(result)
    assert "-" in result.output or "STDIN" in result.output


def test_default_rejects_stdin_with_directory(tmp_path: Path) -> None:
    """Default command: error if '-' (STDIN) is combined with a directory path."""
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "y.py").write_text("print('y')\n", "utf-8")

    result = run_cli_in(tmp_path, ["check", "-", "pkg"], input_text="print('y')\n")

    assert_USAGE_ERROR(result)
    assert "-" in result.output or "STDIN" in result.output


def test_strip_rejects_stdin_with_directory(tmp_path: Path) -> None:
    """Strip subcommand: error if '-' (STDIN) is combined with a directory path."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "index.md").write_text("<!-- topmark:header:start -->\n", "utf-8")
    result = run_cli_in(
        tmp_path, ["strip", "-", "docs"], input_text="<!-- topmark:header:start -->\n"
    )
    assert_USAGE_ERROR(result)
    assert "-" in result.output or "STDIN" in result.output


def test_only_one_from_option_may_consume_stdin(tmp_path: Path) -> None:
    """Using more than one of --files-from -, --include-from -, --exclude-from - must error."""
    (tmp_path / "a.py").write_text("print()\n", "utf-8")
    # Both include-from and files-from try to read '-' → usage error
    result = run_cli_in(
        tmp_path,
        ["check", "--include-from", "-", "--files-from", "-", "a.py"],
        input_text="*.py\n",
    )

    assert_USAGE_ERROR(result)
    assert "-" in result.output or "STDIN" in result.output
