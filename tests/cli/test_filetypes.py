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

from topmark.cli.main import cli as _cli


def test_filetypes_lists_known_types():
    """It should list supported file types and exit with code 0."""
    res = CliRunner().invoke(cast(click.Command, _cli), ["filetypes"])
    assert res.exit_code == 0
    assert "Supported file types" in res.output or res.output.strip() != ""
