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

from topmark.cli.main import cli as _cli


def test_verbose_and_quiet_flags_parse():
    """It should accept verbosity and quietness flags and exit with code 0."""
    r = CliRunner()
    for args in (["-v", "version"], ["-vvv", "version"], ["-q", "version"], ["-qq", "version"]):
        res = r.invoke(cast(click.Command, _cli), args)
        assert res.exit_code == 0
