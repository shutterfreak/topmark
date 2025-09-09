# topmark:header:start
#
#   file         : test_smoke.py
#   file_relpath : tests/cli/test_smoke.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI smoke tests for TopMark.

Provides minimal coverage that the CLI entry point is callable and that
`--help` and `version` commands succeed.
"""

from tests.cli.conftest import assert_SUCCESS, run_cli
from topmark.constants import TOPMARK_VERSION


def test_cli_entry() -> None:
    """It should show usage information and exit code SUCCESS when `--help` is passed."""
    result = run_cli(["--help"])

    assert_SUCCESS(result)

    assert "Usage" in result.output


def test_version() -> None:
    """It should show version information containing 'topmark' and exit code SUCCESS."""
    result = run_cli(["version"])

    assert_SUCCESS(result)

    assert TOPMARK_VERSION in result.output
