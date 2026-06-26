# topmark:header:start
#
#   project      : TopMark
#   file         : test_processing_case_sensitive_fs.py
#   file_relpath : tests/cli/test_processing_case_sensitive_fs.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI regression tests for case-sensitive filesystem path handling.

These tests complement the issue #75 case-insensitive tests by asserting that
TopMark does not treat differently cased path spellings as equivalent on a
case-sensitive filesystem.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.cli.conftest import assert_FILE_NOT_FOUND
from tests.cli.conftest import assert_human_output_contains
from tests.cli.conftest import run_cli_in
from topmark.cli.keys import CliCmd

if TYPE_CHECKING:
    from pathlib import Path

    from click.testing import Result


pytestmark: list[pytest.MarkDecorator] = [pytest.mark.cli]


def test_check_does_not_resolve_mismatched_invocation_casing_on_case_sensitive_fs(
    tmp_path: Path,
) -> None:
    """A casing-only mismatch should fail on case-sensitive filesystems."""
    actual_file: Path = tmp_path / "README.md"
    actual_file.write_text("# README\n", encoding="utf-8")

    invocation_path: Path = tmp_path / "REadme.md"
    if invocation_path.exists():
        pytest.skip("test requires a case-sensitive filesystem")

    result: Result = run_cli_in(
        tmp_path,
        [
            CliCmd.CHECK,
            "REadme.md",
        ],
    )

    assert_FILE_NOT_FOUND(result)
    assert_human_output_contains(
        output_format=None,
        output=result.output,
        expected="REadme.md",
    )
