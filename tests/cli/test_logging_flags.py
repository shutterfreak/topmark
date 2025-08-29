# topmark:header:start
#
#   file         : test_logging_flags.py
#   file_relpath : tests/cli/test_logging_flags.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI test: logging verbosity and quietness flags.

Ensures that combinations of `-v`/`-vvv` and `-q`/`-qq` parse correctly
and that invoking `topmark version` with them exits successfully.
"""

from typing import cast

import click
from click.testing import CliRunner

from topmark.cli.exit_codes import ExitCode
from topmark.cli.main import cli as _cli

# Type hint for the CLI command object
cli = cast(click.Command, _cli)


def test_verbose_and_quiet_flags_parse() -> None:
    """It should accept verbosity and quietness flags and exit with code 0."""
    runner = CliRunner()

    for args in (["-v", "version"], ["-vvv", "version"], ["-q", "version"], ["-qq", "version"]):
        result = runner.invoke(cli, args)

        assert result.exit_code == ExitCode.SUCCESS, result.output
