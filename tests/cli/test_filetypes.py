# topmark:header:start
#
#   file         : test_filetypes.py
#   file_relpath : tests/cli/test_filetypes.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI test: `filetypes` command output.

Ensures that invoking `topmark filetypes` exits successfully and produces
non-empty output, typically including the phrase "Supported file types".
"""

from typing import cast

import click
from click.testing import CliRunner

from topmark.cli.exit_codes import ExitCode
from topmark.cli.main import cli as _cli

# Type hint for the CLI command object
cli = cast(click.Command, _cli)


def test_filetypes_lists_known_types() -> None:
    """It should list supported file types and exit with code 0."""
    result = CliRunner().invoke(cli, ["filetypes"])

    assert result.exit_code == ExitCode.SUCCESS, result.output

    assert "Supported file types" in result.output or result.output.strip() != ""
