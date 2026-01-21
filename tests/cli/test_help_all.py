# topmark:header:start
#
#   project      : TopMark
#   file         : test_help_all.py
#   file_relpath : tests/cli/test_help_all.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI tests: `--help` output for all commands.

Ensures that:

- The top-level `topmark --help` exits with code 0.
- Each registered subcommand provides a working `--help` page.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from click.testing import Result

from tests.cli.conftest import assert_SUCCESS, run_cli
from topmark.cli.keys import CliCmd, CliOpt

if TYPE_CHECKING:
    from click.testing import Result

COMMANDS: list[tuple[str, ...]] = [
    (CliCmd.CHECK,),
    (CliCmd.STRIP,),
    (CliCmd.CONFIG,),
    (
        CliCmd.CONFIG,
        CliCmd.CONFIG_INIT,
    ),
    (
        CliCmd.CONFIG,
        CliCmd.CONFIG_DEFAULTS,
    ),
    (
        CliCmd.CONFIG,
        CliCmd.CONFIG_DUMP,
    ),
    (CliCmd.FILETYPES,),
    (CliCmd.PROCESSORS,),
    (CliCmd.VERSION,),
]


def test_group_help() -> None:
    """It should exit successfully (0) when running `topmark --help`."""
    result: Result = run_cli(
        [CliOpt.HELP],
    )

    assert_SUCCESS(result)


def test_each_command_has_help() -> None:
    """It should provide a `--help` page for each known subcommand."""
    for cmd in COMMANDS:
        result: Result = run_cli(
            cmd + (CliOpt.HELP,),
        )

        assert_SUCCESS(result)
