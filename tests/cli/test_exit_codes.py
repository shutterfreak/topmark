# topmark:header:start
#
#   project      : TopMark
#   file         : test_exit_codes.py
#   file_relpath : tests/cli/test_exit_codes.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

# File path: tests/cli/test_exit_codes.py
"""CLI default command: exit codes and combined flags.

This module ensures CI/pre-commit semantics:
- clean vs changed states for `check`,
- combined flags (`--apply --summary`, `--diff --apply`),
- robust handling of `--stdin` with empty input.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from click.testing import Result

from tests.cli.conftest import assert_SUCCESS, assert_WOULD_CHANGE, run_cli
from topmark.constants import TOPMARK_START_MARKER

if TYPE_CHECKING:
    from pathlib import Path

    from click.testing import Result


def test_check_exits_would_change_when_changes_needed(tmp_path: Path) -> None:
    """`check` should exit WOULD_CHANGE (2) when headers would be added or modified."""
    f: Path = tmp_path / "x.py"
    f.write_text("print('z')\n", "utf-8")

    result: Result = run_cli(["check", str(f)])

    # Non-zero signals that changes are required.
    assert_WOULD_CHANGE(result)


def test_check_exits_success_when_clean(tmp_path: Path) -> None:
    """`check` should exit 0 when file is already compliant (after apply)."""
    f: Path = tmp_path / "x.py"
    f.write_text("print('z')\n", "utf-8")

    # Bring file to compliant state.
    result_apply: Result = run_cli(["check", "--apply", str(f)])

    assert_SUCCESS(result_apply)

    result_check: Result = run_cli(["check", str(f)])

    assert_SUCCESS(result_check)


def test_default_summary_apply_runs_apply_pipeline(tmp_path: Path) -> None:
    """`--summary --apply` should still perform apply pipeline (not dry-run only)."""
    f: Path = tmp_path / "x.py"
    f.write_text("print('z')\n", "utf-8")

    result: Result = run_cli(["check", "--summary", "--apply", str(f)])

    assert_SUCCESS(result)

    # File should now contain a header.
    assert TOPMARK_START_MARKER in f.read_text("utf-8")


def test_default_diff_with_apply_emits_patch(tmp_path: Path) -> None:
    """`--diff --apply` should apply changes and still show a patch."""
    f: Path = tmp_path / "x.py"
    f.write_text("print('z')\n", "utf-8")

    result: Result = run_cli(["check", "--diff", "--apply", str(f)])

    # Apply succeeded; unified diff printed.
    assert_SUCCESS(result)

    assert "--- " in result.output and "+++ " in result.output


def test_stdin_with_empty_input_is_noop() -> None:
    """`--stdin` with empty input should be a no-op and exit 0."""
    result: Result = run_cli(["check", "--stdin"], input_text="")

    assert_SUCCESS(result)
