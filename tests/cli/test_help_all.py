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

from typing import TYPE_CHECKING, Tuple

from click.testing import Result

from tests.cli.conftest import assert_SUCCESS, run_cli

if TYPE_CHECKING:
    from click.testing import Result

COMMANDS: list[Tuple[str, ...]] = [
    ("check",),
    ("strip",),
    ("config",),
    (
        "config",
        "init",
    ),
    (
        "config",
        "defaults",
    ),
    (
        "config",
        "dump",
    ),
    ("filetypes",),
    ("processors",),
    ("version",),
]


def test_group_help() -> None:
    """It should exit successfully (0) when running `topmark --help`."""
    result: Result = run_cli(["--help"])

    assert_SUCCESS(result)


def test_each_command_has_help() -> None:
    """It should provide a `--help` page for each known subcommand."""
    for cmd in COMMANDS:
        result: Result = run_cli(cmd + ("--help",))

        assert_SUCCESS(result)
