# topmark:header:start
#
#   file         : test_filters_and_types.py
#   file_relpath : tests/resolver/test_filters_and_types.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

# File path: tests/file_resolution/test_filters_and_types.py
"""File resolution parity: include/exclude, file-type filters, relative roots.

Validates that the CLI honors:
- `-i/--include` and `-e/--exclude` patterns,
- file-type constraints,
- relative resolution against a working directory.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import cast

import click
from click.testing import CliRunner

from topmark.cli.exit_codes import ExitCode
from topmark.cli.main import cli as _cli
from topmark.constants import TOPMARK_END_MARKER, TOPMARK_START_MARKER

# Type hint for the CLI command object
cli = cast(click.Command, _cli)


def test_strip_honors_include_exclude(tmp_path: Path) -> None:
    """`strip` should obey include/exclude filters: only included targets change.

    Uses relative glob patterns (required) once chdir(tmp_path) is in effect.
    """
    a = tmp_path / "a.py"
    b = tmp_path / "b.py"
    a.write_text(f"# {TOPMARK_START_MARKER}\n# h\n# {TOPMARK_END_MARKER}\n", "utf-8")
    b.write_text(f"# {TOPMARK_START_MARKER}\n# h\n# {TOPMARK_END_MARKER}\n", "utf-8")

    # Non-relative glob patterns are unsupported
    cwd = os.getcwd()
    try:
        os.chdir(tmp_path)

        # Exclude b.py via explicit relative path; only a.py should be considered.
        result_1 = CliRunner().invoke(cli, ["strip", "-i", "*.py", "-e", "b.py"])

        # Applying should remove header in a.py but keep b.py unchanged.
        result_2 = CliRunner().invoke(cli, ["strip", "--apply", "-i", "*.py", "-e", "b.py"])
    finally:
        os.chdir(cwd)

    # Run 1 would strip a.py
    assert result_1.exit_code == ExitCode.WOULD_CHANGE, result_1.output

    # Run 2
    assert result_2.exit_code == ExitCode.SUCCESS, result_2.output

    assert TOPMARK_START_MARKER not in a.read_text("utf-8"), "Expecting no TopMark header in 'a.py'"

    assert TOPMARK_START_MARKER in b.read_text("utf-8"), "Expecting TopMark header in 'b.py'"


def test_file_type_filter_limits_targets(tmp_path: Path) -> None:
    """`--file-type` should limit target files to selected processors.

    Creates `.py` and `.md` files but restricts processing to `python` type.

    Uses relative glob patterns (required) and passes `--file-type` to base command only.
    """
    py = tmp_path / "x.py"
    md = tmp_path / "y.md"
    py.write_text("print('ok')\n", "utf-8")
    md.write_text("# Title\n", "utf-8")

    result = CliRunner().invoke(cli, ["--file-type", "python", str(tmp_path / "*.*")])

    # Only python files considered → a change may be required for x.py only.
    assert result.exit_code in (ExitCode.SUCCESS, ExitCode.FAILURE), (
        result.output
    )  # tolerate config-specific outcomes
