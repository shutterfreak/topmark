# topmark:header:start
#
#   project      : TopMark
#   file         : test_include_exclude_precedence.py
#   file_relpath : tests/cli/test_include_exclude_precedence.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI include/exclude precedence behavior tests.

This module verifies file-discovery precedence for include/exclude pattern files:
- files matched by both include and exclude patterns are excluded,
- comments and blank lines in pattern files are ignored.

These are discovery/filter behavior tests rather than pure exit-code contract tests.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from tests.cli.conftest import assert_SUCCESS
from tests.cli.conftest import run_cli_in
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt
from topmark.core.constants import TOPMARK_START_MARKER

if TYPE_CHECKING:
    from pathlib import Path

    from click.testing import Result


# --- Include/exclude precedence ---


def test_exclude_patterns_take_precedence_over_include_patterns(
    tmp_path: Path,
) -> None:
    """Files matched by both include and exclude patterns should be excluded."""
    included_target: Path = tmp_path / "keep.py"
    excluded_target: Path = tmp_path / "skip.py"

    included_target.write_text("# header\n")
    excluded_target.write_text("# header\n")

    include_patterns: Path = tmp_path / "inc.txt"
    exclude_patterns: Path = tmp_path / "exc.txt"
    # Both files included; exclude removes `skip.py`.
    include_patterns.write_text("*.py\n# comment\n\n", "utf-8")
    exclude_patterns.write_text("# exclude explicit below\nskip.py\n", "utf-8")

    result: Result = run_cli_in(
        tmp_path,
        [
            CliCmd.CHECK,
            CliOpt.INCLUDE_FROM,
            str(include_patterns.name),
            CliOpt.EXCLUDE_FROM,
            str(exclude_patterns.name),
            CliOpt.APPLY_CHANGES,
            ".",
        ],
    )

    assert_SUCCESS(result)

    # `keep.py` remains selected and should receive a header.
    assert TOPMARK_START_MARKER in included_target.read_text("utf-8")

    # `skip.py` is excluded and should remain header-less.
    assert TOPMARK_START_MARKER not in excluded_target.read_text("utf-8")
