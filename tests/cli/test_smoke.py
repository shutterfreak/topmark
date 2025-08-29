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

from typing import cast

import click
from click.testing import CliRunner

from topmark.cli.exit_codes import ExitCode
from topmark.cli.main import cli as _cli

# Type hint for the CLI command object
cli = cast(click.Command, _cli)


def test_cli_entry() -> None:
    """It should show usage information and exit code 0 when `--help` is passed."""
    result = CliRunner().invoke(cli, ["--help"])

    assert result.exit_code == ExitCode.SUCCESS, result.output

    assert "Usage" in result.output


def test_version() -> None:
    """It should show version information containing 'topmark' and exit code 0."""
    result = CliRunner().invoke(cli, ["version"])

    assert result.exit_code == ExitCode.SUCCESS, result.output

    assert "topmark" in result.output.lower()
