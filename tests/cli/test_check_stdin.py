# topmark:header:start
#
#   file         : test_check_stdin.py
#   file_relpath : tests/cli/test_check_stdin.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Test reading file list from stdin with unified CLI semantics and dry-run behavior."""

from pathlib import Path
from typing import cast

import click
from click.testing import CliRunner

from topmark.cli.exit_codes import ExitCode
from topmark.cli.main import cli as _cli

# Type hint for the CLI command object
cli = cast(click.Command, _cli)


def test_stdin_file_list_dry_run(tmp_path: Path) -> None:
    """It should accept file paths from stdin and exit successfully.

    Args:
        tmp_path: pytest-provided temporary directory for creating a sample file.
    """
    # Create a test file
    f = tmp_path / "test.py"
    f.write_text("print('y')\n")

    # Base command reads paths from stdin when --stdin is provided (no subcommand)
    result = CliRunner().invoke(cli, ["-vv", "--stdin"], input=str(f) + "\n")

    # Dry‑run by default: exit code 2 indicates changes would be required
    assert result.exit_code == ExitCode.WOULD_CHANGE, result.output
    # Ensure the file was not modified in check mode
    assert f.read_text() == "print('y')\n"
