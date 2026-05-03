# topmark:header:start
#
#   project      : TopMark
#   file         : test_unified_check_apply.py
#   file_relpath : tests/cli/test_unified_check_apply.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI check/apply behavior tests.

This module verifies the unified `topmark check` behavior:
- default mode is a dry-run and does not write files,
- dry-run exits with WOULD_CHANGE when a header would be inserted,
- `--apply` writes changes and exits successfully.

Pure exit-code contract coverage lives in `tests/cli/test_check_exit_codes.py`;
this module focuses on the corresponding filesystem behavior.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from click.testing import Result

from tests.cli.conftest import assert_SUCCESS
from tests.cli.conftest import assert_WOULD_CHANGE
from tests.cli.conftest import run_cli
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt

if TYPE_CHECKING:
    from pathlib import Path

    from click.testing import Result


# --- Dry-run behavior ---


def test_check_dry_run_reports_would_change_without_writing(tmp_path: Path) -> None:
    """Default `check` mode should report WOULD_CHANGE without modifying the file."""
    f: Path = tmp_path / "a.py"
    f.write_text("print('x')\n", encoding="utf-8")

    result: Result = run_cli([CliCmd.CHECK, str(f)])

    assert_WOULD_CHANGE(result)

    # Dry-run mode must not modify the file.
    assert f.read_text(encoding="utf-8") == "print('x')\n"


# --- Apply behavior ---


def test_check_apply_writes_changes_and_exits_success(tmp_path: Path) -> None:
    """`check --apply` should write changes and exit SUCCESS."""
    f: Path = tmp_path / "b.py"
    before = "print('y')\n"
    f.write_text(before, encoding="utf-8")

    result: Result = run_cli([CliCmd.CHECK, CliOpt.APPLY_CHANGES, str(f)])

    assert_SUCCESS(result)

    after: str = f.read_text(encoding="utf-8")

    # The file should be changed by header insertion.
    assert after != before, "file should have been modified"
