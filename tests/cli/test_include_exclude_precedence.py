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

from pathlib import Path

from tests.cli.conftest import assert_SUCCESS, run_cli_in
from topmark.constants import TOPMARK_START_MARKER


def test_exclude_wins_over_include(tmp_path: Path) -> None:
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

    result = run_cli_in(
        tmp_path,
        [
            "check",
            "--include-from",
            str(incf.name),
            "--exclude-from",
            str(excf.name),
            "--apply",
            ".",
        ],
    )

    assert_SUCCESS(result)

    # `keep.py` should have a header
    assert TOPMARK_START_MARKER in target.read_text("utf-8")

    # `skip.py` should remain header-less
    assert TOPMARK_START_MARKER not in other.read_text("utf-8")
