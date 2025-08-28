# topmark:header:start
#
#   file         : test_exit_codes.py
#   file_relpath : tests/cli/test_exit_codes.py
#   project      : TopMark
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
from typing import cast

import click
from click.testing import CliRunner

from topmark.cli.exit_codes import ExitCode
from topmark.cli.main import cli as _cli

# Type hint for the CLI command object
cli = cast(click.Command, _cli)


def test_check_exits_would_change_when_changes_needed(tmp_path: Path) -> None:
    """`check` should exit WOULD_CHANGE (2) when headers would be added or modified."""
    f = tmp_path / "x.py"
    f.write_text("print('z')\n", "utf-8")

    res = CliRunner().invoke(cli, ["check", str(f)])

    # Non-zero signals that changes are required.
    assert res.exit_code == ExitCode.WOULD_CHANGE, res.output


def test_check_exits_success_when_clean(tmp_path: Path) -> None:
    """`check` should exit 0 when file is already compliant (after apply)."""
    f = tmp_path / "x.py"
    f.write_text("print('z')\n", "utf-8")

    # Bring file to compliant state.
    res_apply = CliRunner().invoke(cli, ["--apply", str(f)])
    assert res_apply.exit_code == ExitCode.SUCCESS, res_apply.output

    res_check = CliRunner().invoke(cli, ["check", str(f)])
    assert res_check.exit_code == ExitCode.SUCCESS, res_check.output


def test_default_summary_apply_runs_apply_pipeline(tmp_path: Path) -> None:
    """`--summary --apply` should still perform apply pipeline (not dry-run only)."""
    f = tmp_path / "x.py"
    f.write_text("print('z')\n", "utf-8")

    res = CliRunner().invoke(cli, ["--summary", "--apply", str(f)])

    # File should now contain a header.
    assert res.exit_code == ExitCode.SUCCESS, res.output
    assert "topmark:header:start" in f.read_text("utf-8")


def test_default_diff_with_apply_emits_patch(tmp_path: Path) -> None:
    """`--diff --apply` should apply changes and still show a patch."""
    f = tmp_path / "x.py"
    f.write_text("print('z')\n", "utf-8")

    res = CliRunner().invoke(cli, ["--diff", "--apply", str(f)])

    # Apply succeeded; unified diff printed.
    assert res.exit_code == ExitCode.SUCCESS, res.output
    assert "--- " in res.output and "+++ " in res.output


def test_stdin_with_empty_input_is_noop():
    """`--stdin` with empty input should be a no-op and exit 0."""
    res = CliRunner().invoke(cli, ["--stdin"], input="")
    assert res.exit_code == ExitCode.SUCCESS, res.output
