# topmark:header:start
#
#   file         : test_help_all.py
#   file_relpath : tests/cli/test_help_all.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI tests: `--help` output for all commands.

Ensures that:

- The top-level `topmark --help` exits with code 0.
- Each registered subcommand provides a working `--help` page.
"""

from typing import cast

import click
from click.testing import CliRunner

from topmark.cli.exit_codes import ExitCode
from topmark.cli.main import cli as _cli

# Type hint for the CLI command object
cli = cast(click.Command, _cli)

COMMANDS = ["check", "apply", "dump-config", "filetypes", "init-config", "show-defaults", "version"]


def test_group_help() -> None:
    """It should exit successfully (0) when running `topmark --help`."""
    result = CliRunner().invoke(cli, ["--help"])

    assert result.exit_code == ExitCode.SUCCESS, result.output


def test_each_command_has_help() -> None:
    """It should provide a `--help` page for each known subcommand."""
    runner = CliRunner()

    for name in COMMANDS:
        result = runner.invoke(cli, [name, "--help"])

        assert result.exit_code == ExitCode.SUCCESS, f"{name} --help failed"
