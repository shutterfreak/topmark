# topmark:header:start
#
#   file         : test_check_no_files.py
#   file_relpath : tests/cli/test_check_no_files.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI test: behavior of `check` with no file arguments.

Ensures that invoking `topmark check` without providing any files succeeds
gracefully (exit code 0) and does not crash. The command should handle an
empty file set consistently.
"""

from typing import cast

import click
from click.testing import CliRunner

from topmark.cli.exit_codes import ExitCode
from topmark.cli.main import cli as _cli

# Type hint for the CLI command object
cli = cast(click.Command, _cli)


def test_check_with_no_files_succeeds() -> None:
    """It should exit successfully (code 0) when no files are provided."""
    result = CliRunner().invoke(cli, ["check"])
    # Depending on your current behavior, assert exit code and message
    assert result.exit_code == ExitCode.SUCCESS, result.output
