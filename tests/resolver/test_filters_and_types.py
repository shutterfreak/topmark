# topmark:header:start
#
#   project      : TopMark
#   file         : test_filters_and_types.py
#   file_relpath : tests/resolver/test_filters_and_types.py
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

from pathlib import Path
from typing import TYPE_CHECKING

from tests.cli.conftest import assert_SUCCESS, assert_WOULD_CHANGE, run_cli_in
from topmark.constants import TOPMARK_END_MARKER, TOPMARK_START_MARKER

if TYPE_CHECKING:
    from pathlib import Path

    from click.testing import Result


def test_strip_honors_include_exclude(tmp_path: Path) -> None:
    """`strip` should obey include/exclude filters: only included targets change.

    Uses relative glob patterns (required) once chdir(tmp_path) is in effect.
    """
    a: Path = tmp_path / "a.py"
    b: Path = tmp_path / "b.py"
    a.write_text(f"# {TOPMARK_START_MARKER}\n# h\n# {TOPMARK_END_MARKER}\n", "utf-8")
    b.write_text(f"# {TOPMARK_START_MARKER}\n# h\n# {TOPMARK_END_MARKER}\n", "utf-8")

    # Exclude b.py via explicit relative path; only a.py should be considered.
    result_1: Result = run_cli_in(tmp_path, ["strip", "-i", "*.py", "-e", "b.py", "a.py", "b.py"])

    # Applying should remove header in a.py but keep b.py unchanged.
    result_2: Result = run_cli_in(
        tmp_path, ["strip", "--apply", "-i", "*.py", "-e", "b.py", "a.py", "b.py"]
    )

    # Run 1 would strip a.py
    assert_WOULD_CHANGE(result_1)

    # Run 2
    assert_SUCCESS(result_2)

    assert TOPMARK_START_MARKER not in a.read_text("utf-8"), "Expecting no TopMark header in 'a.py'"

    assert TOPMARK_START_MARKER in b.read_text("utf-8"), "Expecting TopMark header in 'b.py'"


def test_file_type_filter_limits_targets(tmp_path: Path) -> None:
    """`--file-type` should limit target files to selected processors.

    Creates `.py` and `.md` files but restricts processing to `python` type.

    Uses relative glob patterns (required) and passes `--file-type` to base command only.
    """
    py: Path = tmp_path / "x.py"
    md: Path = tmp_path / "y.md"
    py.write_text("print('ok')\n", "utf-8")
    md.write_text("# Title\n", "utf-8")

    result: Result = run_cli_in(tmp_path, ["--file-type", "python", "*.*"])

    # Only python files considered → x.py is eligible; since it lacks a header, the default command
    # may report WOULD_CHANGE. Accept SUCCESS (no changes) or WOULD_CHANGE (changes needed).
    assert_WOULD_CHANGE(result)
