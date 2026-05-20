# topmark:header:start
#
#   project      : TopMark
#   file         : test_no_files.py
#   file_relpath : tests/cli/test_no_files.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI no-input usage-error contract tests.

This module validates that invoking CLI commands without any file inputs
results in a usage error according to the public CLI contract.

Covered commands:
  * `check`
  * `strip`
  * `probe`

Contract:
  * missing required inputs → USAGE_ERROR (64)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from click.testing import Result

from tests.cli.conftest import assert_USAGE_ERROR
from tests.cli.conftest import run_cli
from topmark.cli.keys import CliCmd

if TYPE_CHECKING:
    from click.testing import Result


# All tests in this module pin documented CLI usage-error behavior.
pytestmark: pytest.MarkDecorator = pytest.mark.exit_code

# --- Missing input arguments ---


@pytest.mark.parametrize("command", [CliCmd.CHECK, CliCmd.STRIP, CliCmd.PROBE])
def test_commands_without_files_exit_usage_error(command: str) -> None:
    """Commands without file inputs should exit with USAGE_ERROR."""
    result: Result = run_cli([command])
    assert_USAGE_ERROR(result)
