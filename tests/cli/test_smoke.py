# topmark:header:start
#
#   project      : TopMark
#   file         : test_smoke.py
#   file_relpath : tests/cli/test_smoke.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI smoke tests for TopMark.

Provides minimal coverage that the CLI entry point is callable and that
`--help` and `version` commands succeed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.cli.conftest import assert_SUCCESS, run_cli
from topmark.constants import TOPMARK_VERSION

if TYPE_CHECKING:
    from click.testing import Result


def test_cli_entry() -> None:
    """It should show usage information and exit code SUCCESS when `--help` is passed."""
    result: Result = run_cli(["--help"])

    assert_SUCCESS(result)

    assert "Usage" in result.output


def test_version() -> None:
    """It should show version information containing 'topmark' and exit code SUCCESS."""
    result: Result = run_cli(["version"])

    assert_SUCCESS(result)

    assert TOPMARK_VERSION in result.output
