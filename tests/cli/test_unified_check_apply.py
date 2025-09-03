# topmark:header:start
#
#   file         : test_unified_check_apply.py
#   file_relpath : tests/cli/test_unified_check_apply.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI tests for unified check/apply behavior.

The base command performs a *check/dry‑run* by default and exits with code 2
when changes would be required. With ``--apply``, it writes the changes and
exits with code 0 on success.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.cli.conftest import assert_SUCCESS, assert_WOULD_CHANGE, run_cli

if TYPE_CHECKING:
    from pathlib import Path


def test_check_mode_exits_2_when_changes_needed(tmp_path: Path) -> None:
    """Dry‑run (default) should exit with code 2 if changes are needed.

    We create a file without a header so TopMark would add one; in check mode
    it must not write and should signal the need to apply via exit code 2.
    """
    f = tmp_path / "a.py"
    f.write_text("print('x')\n", encoding="utf-8")

    result = run_cli(["check", str(f)])

    assert_WOULD_CHANGE(result)

    # Ensure the file was not modified in check mode
    assert f.read_text(encoding="utf-8") == "print('x')\n"


def test_apply_writes_and_exits_0(tmp_path: Path) -> None:
    """With ``--apply``, changes are written and exit code is 0."""
    f = tmp_path / "b.py"
    before = "print('y')\n"
    f.write_text(before, encoding="utf-8")

    result = run_cli(["check", "--apply", str(f)])

    assert_SUCCESS(result)

    after = f.read_text(encoding="utf-8")

    # File should be changed (header inserted). We only assert that content differs.
    assert after != before, "file should have been modified"
