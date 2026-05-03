# topmark:header:start
#
#   project      : TopMark
#   file         : test_probe_exit_codes.py
#   file_relpath : tests/cli/test_probe_exit_codes.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Exit-code contract tests for `topmark probe`.

These tests pin the public CLI contract for resolution outcomes:
- all inputs resolved → SUCCESS (0)
- any input unresolved/unsupported/filtered → UNSUPPORTED_FILE_TYPE (69)

Tests intentionally assert exact exit codes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner
from click.testing import Result

from tests.cli.conftest import assert_SUCCESS
from tests.cli.conftest import assert_UNSUPPORTED_FILE_TYPE
from topmark.cli.keys import CliCmd
from topmark.cli.main import cli

if TYPE_CHECKING:
    from pathlib import Path


# All tests in this module pin documented CLI exit-code behavior.
pytestmark: pytest.MarkDecorator = pytest.mark.exit_code


# --- Fully resolved inputs ---
def test_probe_exit_code_success_for_supported_file(tmp_path: Path) -> None:
    """Supported inputs should resolve fully and exit SUCCESS."""
    file: Path = tmp_path / "example.py"
    file.write_text("print('hello')\n", encoding="utf-8")
    runner = CliRunner()
    result: Result = runner.invoke(
        cli,
        [
            CliCmd.PROBE,
            str(file),
        ],
    )
    assert_SUCCESS(result)


# --- Unsupported / unresolved inputs ---
def test_probe_exit_code_unsupported_for_unknown_file(tmp_path: Path) -> None:
    """Unsupported file types should exit with the UNAVAILABLE contract code."""
    file: Path = tmp_path / "example.unknown"
    file.write_text("data\n", encoding="utf-8")
    runner = CliRunner()
    result: Result = runner.invoke(
        cli,
        [
            CliCmd.PROBE,
            str(file),
        ],
    )
    assert_UNSUPPORTED_FILE_TYPE(result)


def test_probe_exit_code_unsupported_for_mixed_files(tmp_path: Path) -> None:
    """Mixed inputs should exit UNAVAILABLE when any input is unsupported."""
    file_ok: Path = tmp_path / "example.py"
    file_ok.write_text("print('hello')\n", encoding="utf-8")
    file_bad: Path = tmp_path / "example.unknown"
    file_bad.write_text("data\n", encoding="utf-8")
    runner = CliRunner()
    result: Result = runner.invoke(
        cli,
        [
            CliCmd.PROBE,
            str(file_ok),
            str(file_bad),
        ],
    )

    assert_UNSUPPORTED_FILE_TYPE(result)
