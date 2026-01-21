# topmark:header:start
#
#   project      : TopMark
#   file         : test_stdin_content.py
#   file_relpath : tests/cli/test_stdin_content.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end
"""Test reading file content from STDIN with unified CLI semantics and dry-run behavior.

This module tests the behavior when a single file's *content* is provided on
STDIN (using `'-'` as the path). The default (`check`/`apply`) command and
the `strip` subcommand should behave consistently in dry-run and `--apply`
modes. In particular, with `--apply`, the modified content should be printed
to STDOUT (not written to the filesystem).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from click.testing import Result

from tests.cli.conftest import (
    assert_SUCCESS,
    assert_WOULD_CHANGE,
    run_cli,
)
from topmark.cli.keys import CliCmd, CliOpt
from topmark.constants import TOPMARK_END_MARKER, TOPMARK_START_MARKER

if TYPE_CHECKING:
    from pathlib import Path

    from click.testing import Result


def test_check_content_stdin_dry_run() -> None:
    """Reading a single file from STDIN ('-') should behave like a real file in dry-run."""
    body = "print('x')\n"
    result: Result = run_cli(
        [CliCmd.CHECK, "-", CliOpt.STDIN_FILENAME, "x.py"],
        input_text=body,
    )
    assert_WOULD_CHANGE(result)  # header would be added
    # Should not write to disk (it prints diagnostics only); no file exists here.


def test_check_content_stdin_apply_prints_to_stdout(tmp_path: Path) -> None:
    """With --apply, content-on-STDIN writes the modified content to stdout (not the FS)."""
    body = "print('x')\n"
    result: Result = run_cli(
        [CliCmd.CHECK, CliOpt.APPLY_CHANGES, "-", CliOpt.STDIN_FILENAME, "x.py"],
        input_text=body,
    )
    assert_SUCCESS(result)
    # Heuristic: the header start marker should appear in stdout output.
    from topmark.constants import TOPMARK_START_MARKER

    assert TOPMARK_START_MARKER in result.output


def test_strip_content_stdin_dry_run() -> None:
    """Strip on content from STDIN should detect removal would occur."""
    body: str = f"# {TOPMARK_START_MARKER}\n# test:header\n# {TOPMARK_END_MARKER}\nprint()\n"
    result: Result = run_cli(
        [CliCmd.STRIP, "-", CliOpt.STDIN_FILENAME, "x.py"],
        input_text=body,
    )
    assert_WOULD_CHANGE(result)


def test_strip_content_stdin_apply_prints_to_stdout() -> None:
    """With --apply, strip prints stripped content to stdout."""
    body: str = f"# {TOPMARK_START_MARKER}\n# test:header\n# {TOPMARK_END_MARKER}\nprint('ok')\n"
    result: Result = run_cli(
        [CliCmd.STRIP, CliOpt.APPLY_CHANGES, "-", CliOpt.STDIN_FILENAME, "x.py"],
        input_text=body,
    )
    assert_SUCCESS(result)
    # Header should be gone in stdout
    assert TOPMARK_START_MARKER not in result.output
    assert "print('ok')" in result.output
