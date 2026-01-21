# topmark:header:start
#
#   project      : TopMark
#   file         : test_check_exit_codes.py
#   file_relpath : tests/cli/test_check_exit_codes.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI test: exit codes for the `check` command.

Verifies that invoking `topmark check` with a file missing a header exits
with either 0 (SUCCESS) or 2 (WOULD_CHANGE). The behavior may be tightened
later as the CLI spec is finalized.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from tests.cli.conftest import assert_WOULD_CHANGE, run_cli_in
from topmark.cli.keys import CliCmd

if TYPE_CHECKING:
    from pathlib import Path

    from click.testing import Result


def test_check_exit_code_with_missing_header(tmp_path: Path) -> None:
    """It should exit with code `WOULD_CHANGE` (2)."""
    file_name = "foo.py"
    f: Path = tmp_path / file_name
    f.write_text("print('hi')\n")

    result: Result = run_cli_in(tmp_path, [CliCmd.CHECK, file_name])

    # When a header is missing, the default command should report WOULD_CHANGE (2).
    assert_WOULD_CHANGE(result)
