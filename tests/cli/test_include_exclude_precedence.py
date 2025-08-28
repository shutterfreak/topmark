# topmark:header:start
#
#   file         : test_include_exclude_precedence.py
#   file_relpath : tests/cli/test_include_exclude_precedence.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Include vs exclude precedence for file discovery (Black-style semantics).

Covers:
- File matched by both include and exclude → **exclude wins**.
- Comments and blank lines in pattern files are ignored.
"""

from __future__ import annotations

import os
import pathlib
from typing import cast

import click
from click.testing import CliRunner

from topmark.cli.exit_codes import ExitCode
from topmark.cli.main import cli as _cli


def test_exclude_wins_over_include(tmp_path: pathlib.Path) -> None:
    """When a file is matched by both include and exclude, exclude removes it."""
    target = tmp_path / "keep.py"
    other = tmp_path / "skip.py"
    target.write_text("print('ok')\n", "utf-8")
    other.write_text("print('skip')\n", "utf-8")

    incf = tmp_path / "inc.txt"
    excf = tmp_path / "exc.txt"
    # Both files included; exclude removes `skip.py`.
    incf.write_text("*.py\n# comment\n\n", "utf-8")
    excf.write_text("# exclude explicit below\nskip.py\n", "utf-8")

    cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        res = CliRunner().invoke(
            cast(click.Command, _cli),
            [
                "-vv",
                "--include-from",
                str(incf.name),
                "--exclude-from",
                str(excf.name),
                "--apply",
                ".",
            ],
        )
    finally:
        os.chdir(cwd)

    assert res.exit_code == ExitCode.SUCCESS, res.output
    # `keep.py` should have a header; `skip.py` should remain header-less.
    assert "topmark:header:start" in target.read_text("utf-8")
    assert "topmark:header:start" not in other.read_text("utf-8")
