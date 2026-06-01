# topmark:header:start
#
#   project      : TopMark
#   file         : test_check_exit_codes.py
#   file_relpath : tests/cli/test_check_exit_codes.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Exit-code contract tests for `topmark check`.

These tests pin the public CLI contract for dry-run changes, successful apply
runs, and clean follow-up checks. They intentionally assert exact exit codes.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from click.testing import Result

from tests.cli.conftest import assert_SUCCESS
from tests.cli.conftest import assert_WOULD_CHANGE
from tests.cli.conftest import run_cli
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt

if TYPE_CHECKING:
    from pathlib import Path

    from click.testing import Result


# All tests in this module pin documented CLI exit-code behavior.
pytestmark: pytest.MarkDecorator = pytest.mark.exit_code


# --- Dry-run contract ---
def test_check_exits_would_change_when_changes_needed(tmp_path: Path) -> None:
    """`check` should exit WOULD_CHANGE (3) when headers would be added or modified."""
    f: Path = tmp_path / "x.py"
    f.write_text("print('z')\n", "utf-8")

    result: Result = run_cli(
        [
            CliCmd.CHECK,
            str(f),
        ],
    )

    # Dry-run differences are reported with the stable WOULD_CHANGE signal.
    assert_WOULD_CHANGE(result)


# --- Apply and clean-check contract ---
def test_check_apply_exits_success_and_follow_up_check_is_clean(tmp_path: Path) -> None:
    """`check --apply` should exit 0 and make a follow-up dry-run clean."""
    f: Path = tmp_path / "x.py"
    f.write_text("print('z')\n", "utf-8")

    # Applying the planned header insertion should succeed.
    result_apply: Result = run_cli(
        [
            CliCmd.CHECK,
            CliOpt.APPLY_CHANGES,
            str(f),
        ],
    )

    assert_SUCCESS(result_apply)

    # A follow-up dry-run should now be clean and exit SUCCESS.
    result_check: Result = run_cli(
        [
            CliCmd.CHECK,
            str(f),
        ],
    )

    assert_SUCCESS(result_check)
