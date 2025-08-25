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

from topmark.cli.main import cli as _cli

COMMANDS = ["check", "apply", "dump-config", "filetypes", "init-config", "show-defaults", "version"]


def test_group_help():
    """It should exit successfully (0) when running `topmark --help`."""
    res = CliRunner().invoke(cast(click.Command, _cli), ["--help"])
    assert res.exit_code == 0


def test_each_command_has_help():
    """It should provide a `--help` page for each known subcommand."""
    r = CliRunner()
    for name in COMMANDS:
        res = r.invoke(cast(click.Command, _cli), [name, "--help"])
        assert res.exit_code == 0, f"{name} --help failed"
