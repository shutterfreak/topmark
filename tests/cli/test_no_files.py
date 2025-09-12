# topmark:header:start
#
#   project      : TopMark
#   file         : test_no_files.py
#   file_relpath : tests/cli/test_no_files.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI test: behavior of `check` and `strip` with no file arguments.

Ensures that invoking `topmark check` and `topmark strip` without providing any files
results in ExitCode.USAGE_ERROR. The command should handle an empty file set consistently.
"""

from tests.cli.conftest import assert_USAGE_ERROR, run_cli
from tests.conftest import parametrize


@parametrize("command", ["check", "strip"])
def test_cmd_with_no_files_yields_usage_error(command: str) -> None:
    """It should exit with ExitCode.USAGE_ERROR when no files are provided."""
    result = run_cli([command])
    assert_USAGE_ERROR(result)
