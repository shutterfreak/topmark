# topmark:header:start
#
#   project      : TopMark
#   file         : test_logging_flags.py
#   file_relpath : tests/cli/test_logging_flags.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI test: logging verbosity and quietness flags.

Ensures that combinations of `-v`/`-vvv` and `-q`/`-qq` parse correctly
and that invoking `topmark version` with them exits successfully.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.cli.conftest import assert_SUCCESS
from tests.cli.conftest import assert_USAGE_ERROR
from tests.cli.conftest import run_cli
from tests.conftest import parametrize
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt

if TYPE_CHECKING:
    from click.testing import Result


@parametrize("verbosity", ["-v", "-vv", "-vvv", "-q", "-qq", "-qqq"])
def test_verbose_and_quiet_flags_parse(verbosity: str) -> None:
    """It should accept verbosity and quietness flags for commands that support them."""
    result: Result = run_cli(
        [
            CliCmd.CONFIG,
            CliCmd.CONFIG_CHECK,
            CliOpt.NO_CONFIG,
            verbosity,
        ]
    )

    assert_SUCCESS(result)


def test_verbose_and_quiet_flags_mutex_parse() -> None:
    """It should fail when verbosity and quietness flags are combined."""
    for args in (
        [CliCmd.CONFIG, CliCmd.CONFIG_CHECK, CliOpt.NO_CONFIG, "-v", "-q"],
        [CliCmd.CONFIG, CliCmd.CONFIG_CHECK, CliOpt.NO_CONFIG, "-q", "-v"],
    ):
        result: Result = run_cli(args)

        assert "--verbose and --quiet are mutually exclusive" in result.output

        assert_USAGE_ERROR(result)
