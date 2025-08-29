# topmark:header:start
#
#   file         : test_check_exit_codes.py
#   file_relpath : tests/cli/test_check_exit_codes.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI test: exit codes for the `check` command.

Verifies that invoking `topmark check` with a file missing a header exits
with either 0 (SUCCESS) or 2 (WOULD_CHANGE). The behavior may be tightened
later as the CLI spec is finalized.
"""

from pathlib import Path
from typing import cast

import click
from click.testing import CliRunner

from topmark.cli.exit_codes import ExitCode
from topmark.cli.main import cli as _cli

# Type hint for the CLI command object
cli = cast(click.Command, _cli)


def test_check_exit_code_with_missing_header(tmp_path: Path) -> None:
    """It should exit with code 0 (SUCCESS) or 2 (WOULD_CHANGE).

    Args:
        tmp_path: pytest-provided temporary directory for creating a sample file.
    """
    f = tmp_path / "foo.py"
    f.write_text("print('hi')\n")

    result = CliRunner().invoke(cli, ["check", str(f), "--check"])

    assert result.exit_code in (
        ExitCode.SUCCESS,
        ExitCode.WOULD_CHANGE,
    )  # tighten once behavior is finalized
