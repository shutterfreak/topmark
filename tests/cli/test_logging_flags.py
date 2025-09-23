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

from tests.cli.conftest import assert_SUCCESS, run_cli

if TYPE_CHECKING:
    from click.testing import Result


def test_verbose_and_quiet_flags_parse() -> None:
    """It should accept verbosity and quietness flags and exit with code 0."""
    for args in (["-v", "version"], ["-vvv", "version"], ["-q", "version"], ["-qq", "version"]):
        result: Result = run_cli(args)

        assert_SUCCESS(result)
