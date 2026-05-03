# topmark:header:start
#
#   project      : TopMark
#   file         : test_unmatched_glob_exit_codes.py
#   file_relpath : tests/cli/test_unmatched_glob_exit_codes.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Exit-code contract tests for unmatched glob inputs.

These tests pin the distinction between explicit missing literal paths and glob
patterns that match no files:
- explicit missing literals are hard input errors and exit FILE_NOT_FOUND,
- unmatched glob patterns are soft discovery diagnostics for processing
  commands and do not exit FILE_NOT_FOUND,
- `probe` reports unmatched glob patterns as filtered semantic outcomes and
  exits UNSUPPORTED_FILE_TYPE.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.cli.conftest import assert_SUCCESS
from tests.cli.conftest import assert_UNSUPPORTED_FILE_TYPE
from tests.cli.conftest import run_cli_in
from tests.conftest import parametrize
from topmark.cli.keys import CliCmd

if TYPE_CHECKING:
    from pathlib import Path

    from click.testing import Result


# All tests in this module pin documented CLI exit-code behavior.
pytestmark: pytest.MarkDecorator = pytest.mark.exit_code


# --- Unmatched glob patterns ---


@parametrize("command", [CliCmd.CHECK, CliCmd.STRIP])
def test_processing_command_unmatched_glob_pattern_exits_success(
    tmp_path: Path,
    command: str,
) -> None:
    """Unmatched glob patterns should not fail processing commands."""
    result: Result = run_cli_in(
        tmp_path,
        [
            command,
            "missing/**/*.py",
        ],
    )

    assert_SUCCESS(result)


def test_probe_unmatched_glob_pattern_exits_unsupported_file_type(
    tmp_path: Path,
) -> None:
    """`probe` should report unmatched globs as filtered semantic outcomes."""
    result: Result = run_cli_in(
        tmp_path,
        [
            CliCmd.PROBE,
            "missing/**/*.py",
        ],
    )

    assert_UNSUPPORTED_FILE_TYPE(result)
