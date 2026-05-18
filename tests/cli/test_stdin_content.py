# topmark:header:start
#
#   project      : TopMark
#   file         : test_stdin_content.py
#   file_relpath : tests/cli/test_stdin_content.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end
"""Content-on-STDIN CLI behavior tests.

This module covers the mode where a single file's content is provided on
STDIN using `-` as the input path and `--stdin-filename` for file-type
resolution.

The tests verify that `check` and `strip` behave consistently for dry-run and
`--apply` invocations. In apply mode, transformed content is written to STDOUT;
no filesystem target is written.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from click.testing import Result

from tests.cli.conftest import assert_SUCCESS
from tests.cli.conftest import assert_WOULD_CHANGE
from tests.cli.conftest import run_cli
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt
from topmark.core.constants import TOPMARK_END_MARKER
from topmark.core.constants import TOPMARK_START_MARKER

if TYPE_CHECKING:
    from pathlib import Path

    from click.testing import Result

# --- Check command: dry-run and apply ---


def test_check_content_stdin_dry_run_reports_would_change() -> None:
    """`check - --stdin-filename` should report WOULD_CHANGE in dry-run mode."""
    body = "print('x')\n"
    result: Result = run_cli(
        [CliCmd.CHECK, "-", CliOpt.STDIN_FILENAME, "x.py"],
        input_text=body,
    )
    # Header insertion would be needed, so dry-run reports WOULD_CHANGE.
    assert_WOULD_CHANGE(result)
    # Should not write to disk (it prints diagnostics only); no file exists here.


def test_check_content_stdin_apply_prints_modified_content_to_stdout(tmp_path: Path) -> None:
    """`check --apply -` should print modified STDIN content to STDOUT."""
    body = "print('x')\n"
    result: Result = run_cli(
        [CliCmd.CHECK, CliOpt.APPLY_CHANGES, "-", CliOpt.STDIN_FILENAME, "x.py"],
        input_text=body,
    )
    assert_SUCCESS(result)

    # Apply mode for content-on-STDIN writes transformed content to STDOUT.
    assert TOPMARK_START_MARKER in result.output


# --- Strip command: dry-run and apply ---


def test_strip_content_stdin_dry_run_reports_would_change() -> None:
    """`strip - --stdin-filename` should report WOULD_CHANGE when removal is needed."""
    body: str = f"# {TOPMARK_START_MARKER}\n# test:header\n# {TOPMARK_END_MARKER}\nprint()\n"
    result: Result = run_cli(
        [CliCmd.STRIP, "-", CliOpt.STDIN_FILENAME, "x.py"],
        input_text=body,
    )
    assert_WOULD_CHANGE(result)


def test_strip_content_stdin_apply_prints_stripped_content_to_stdout() -> None:
    """`strip --apply -` should print stripped STDIN content to STDOUT."""
    body: str = f"# {TOPMARK_START_MARKER}\n# test:header\n# {TOPMARK_END_MARKER}\nprint('ok')\n"
    result: Result = run_cli(
        [CliCmd.STRIP, CliOpt.APPLY_CHANGES, "-", CliOpt.STDIN_FILENAME, "x.py"],
        input_text=body,
    )
    assert_SUCCESS(result)

    # Header should be absent from transformed STDOUT content.
    assert TOPMARK_START_MARKER not in result.output
    assert "print('ok')" in result.output
