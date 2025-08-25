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
with either success (0) or "changes needed" (2). The behavior may be tightened
later as the CLI spec is finalized.
"""

import pathlib
from typing import cast

import click
from click.testing import CliRunner

from topmark.cli.main import cli as _cli


def test_check_exit_code_with_missing_header(tmp_path: pathlib.Path) -> None:
    """It should exit with code 0 (ok) or 2 (headers need applying).

    Args:
        tmp_path: pytest-provided temporary directory for creating a sample file.
    """
    f = tmp_path / "foo.py"
    f.write_text("print('hi')\n")
    res = CliRunner().invoke(cast(click.Command, _cli), ["check", str(f), "--check"])
    assert res.exit_code in (0, 2)  # tighten once behavior is finalized
