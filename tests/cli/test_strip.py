# topmark:header:start
#
#   project      : TopMark
#   file         : test_strip.py
#   file_relpath : tests/cli/test_strip.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI strip command: behavior, exit codes, diff output, and input sources.

This module hardens the `strip` subcommand behavior across:
- dry-run vs apply exit codes,
- idempotence,
- unified diff rendering,
- summary bucket text,
- positional paths and `--stdin` support.

All tests use CliRunner boundaries (no FS side effects beyond tmp_path).
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import TYPE_CHECKING

from click.testing import Result

from tests.cli.conftest import (
    assert_SUCCESS,
    assert_SUCCESS_or_WOULD_CHANGE,
    assert_WOULD_CHANGE,
    run_cli,
    run_cli_in,
)
from topmark.cli.keys import CliCmd, CliOpt
from topmark.constants import TOPMARK_END_MARKER, TOPMARK_START_MARKER
from topmark.pipeline.status import HeaderStatus, StripStatus

if TYPE_CHECKING:
    from click.testing import Result


def test_strip_dry_run_exits_2(tmp_path: Path) -> None:
    """Dry-run should exit 2 when a header is present (action would occur).

    Given a file that contains a recognizable TopMark header, calling `topmark strip`
    without `--apply` should signal "would change" with exit code 2.
    """
    f: Path = tmp_path / "x.py"
    f.write_text(
        f"# {TOPMARK_START_MARKER}\n# test:header\n# {TOPMARK_END_MARKER}\nprint('ok')\n", "utf-8"
    )

    result: Result = run_cli(
        [CliCmd.STRIP, str(f)],
    )

    # Exit 2 means "changes would be made" (pre-commit friendly).
    assert_WOULD_CHANGE(result)


def test_strip_dry_run_exit_0_when_no_header(tmp_path: Path) -> None:
    """Dry-run should exit 0 when there is nothing to strip.

    Ensures that files without a header do not trigger non-zero exit codes.
    """
    f: Path = tmp_path / "x.py"
    f.write_text("print('ok')\n", "utf-8")

    result: Result = run_cli(
        [CliCmd.STRIP, str(f)],
    )

    # No header → nothing to do → exit 0
    assert_SUCCESS(result)


def test_strip_apply_removes_and_is_idempotent(tmp_path: Path) -> None:
    """Verify that `--apply` removes the header and the operation is idempotent.

    First `--apply` removes the header block; a second run should keep the file
    unchanged and still succeed.
    """
    f: Path = tmp_path / "x.py"
    before: str = f"# {TOPMARK_START_MARKER}\n# test:header\n# {TOPMARK_END_MARKER}\nprint('x')\n"
    f.write_text(before, "utf-8")

    # First application removes the header.
    result_strip_1: Result = run_cli(
        [CliCmd.STRIP, CliOpt.APPLY_CHANGES, str(f)],
    )

    assert_SUCCESS(result_strip_1)

    after_strip_1: str = f.read_text("utf-8")
    assert TOPMARK_START_MARKER not in after_strip_1 and "print('x')" in after_strip_1

    # Second application should be a no-op and still succeed.
    result_strip_2: Result = run_cli(
        [CliCmd.STRIP, CliOpt.APPLY_CHANGES, str(f)],
    )

    assert_SUCCESS(result_strip_2)

    assert f.read_text("utf-8") == after_strip_1


def test_strip_diff_shows_patch(tmp_path: Path) -> None:
    """`--diff` should emit a unified diff showing header removal.

    Verifies presence of unified diff markers and a removed header line.
    """
    f: Path = tmp_path / "x.py"
    f.write_text(
        f"# {TOPMARK_START_MARKER}\n# test:header\n# {TOPMARK_END_MARKER}\nprint()\n", "utf-8"
    )

    result: Result = run_cli(
        [CliCmd.STRIP, CliOpt.RENDER_DIFF, str(f)],
    )

    # With a removable header, diff-only should exit 2 (would change).
    assert_WOULD_CHANGE(result)

    # Check classic unified diff headers and a removed header line.
    assert (
        "--- " in result.output
        and "+++ " in result.output
        and f"-# {TOPMARK_START_MARKER}" in result.output
    )


def test_strip_summary_buckets(tmp_path: Path) -> None:
    """`topmark strip --summary` shows correct buckets for mixed inputs.

    Ensures summary text reflects the separation of "ready to strip" and "no header".
    """
    has: Path = tmp_path / "has.py"
    clean: Path = tmp_path / "clean.py"
    bad: Path = tmp_path / "bad.py"
    has.write_text(
        f"# {TOPMARK_START_MARKER}\n# test:header\n# {TOPMARK_END_MARKER}\nprint()\n", "utf-8"
    )
    clean.write_text("print()\n", "utf-8")
    bad.write_text(f"# {TOPMARK_START_MARKER}\n# x\nprint()\n", "utf-8")

    result: Result = run_cli(
        [
            CliCmd.STRIP,
            CliOpt.RESULTS_SUMMARY_MODE,
            str(has),  # file with good header: "would strip header"
            str(clean),  # file without header: "up-to-date"
            str(bad),  # file with malformed header: "up-to-date"
        ],
    )

    # Depending on aggregation, exit may be 2 (would change) or 0 (no changes).
    assert_SUCCESS_or_WOULD_CHANGE(result)

    # Expect human-facing wording present for both categories.
    assert re.search(rf"{HeaderStatus.MALFORMED.value}[ ]*: 1", result.output), (
        f"{HeaderStatus.MALFORMED.value}: 1'"
    )
    assert re.search(rf"{StripStatus.NOT_NEEDED.value}[ ]*: 1", result.output), (
        f"{StripStatus.NOT_NEEDED.value}: 1'"
    )
    assert re.search(rf"{StripStatus.READY.value}[ ]*: 1", result.output), (
        f"{StripStatus.READY.value}: 1'"
    )


def test_strip_accepts_positional_paths(tmp_path: Path) -> None:
    """`topmmark strip` should accept positional globs/paths like the default command.

    Uses a simple Markdown example to validate path ingress.
    """
    p: Path = tmp_path / "a.md"
    p.write_text(f"<!-- {TOPMARK_START_MARKER} -->\n<!-- {TOPMARK_END_MARKER} -->\n", "utf-8")

    result: Result = run_cli(
        [CliCmd.STRIP, str(p)],
    )

    # Header present → dry-run 'would change' = 2; tolerate 0 in edge runners.
    assert_SUCCESS_or_WOULD_CHANGE(result)

    cwd: Path = Path.cwd()
    try:
        # Use a relative glob; absolute patterns are intentionally unsupported by the resolver.
        os.chdir(tmp_path)  # make the glob relative

        result = run_cli(
            [CliCmd.STRIP, "*.md"],
        )
    finally:
        os.chdir(cwd)

    # Depending on shell/glob semantics, allow either dry-run changed or success
    assert_SUCCESS_or_WOULD_CHANGE(result)


def test_strip_ignores_missing_end_marker(tmp_path: Path) -> None:
    """Do not strip when the end marker is missing.

    Creates a file with a start marker but no matching end marker. The
    `strip` subcommand should treat this as *not a removable header* and
    therefore perform no changes when `--apply` is used.

    Args:
        tmp_path: Temporary path fixture provided by pytest.
    """
    f: Path = tmp_path / "bad.py"
    f.write_text(f"# {TOPMARK_START_MARKER}\n# x\nprint()\n", "utf-8")

    result: Result = run_cli(
        [CliCmd.STRIP, CliOpt.APPLY_CHANGES, str(f)],
    )

    assert_SUCCESS(result)

    # Nothing stripped; header markers still there
    assert TOPMARK_START_MARKER in f.read_text("utf-8")


def test_strip_include_from_exclude_from(tmp_path: Path) -> None:
    """Honor include-from/exclude-from with relative patterns.

    The resolver expands patterns relative to the current working directory
    (Black-style). This test writes relative patterns to the include/exclude
    files and temporarily `chdir`s into `tmp_path` so the glob and file
    references are valid.

    Args:
        tmp_path: Temporary directory provided by pytest.
    """
    a: Path = tmp_path / "a.py"
    b: Path = tmp_path / "b.py"
    a.write_text(f"# {TOPMARK_START_MARKER}\n# test:header\n# {TOPMARK_END_MARKER}\n", "utf-8")
    b.write_text(f"# {TOPMARK_START_MARKER}\n# test:header\n# {TOPMARK_END_MARKER}\n", "utf-8")

    # Use **relative** patterns: resolver disallows absolute patterns.
    incf = "inc.txt"
    (tmp_path / incf).write_text("*.py\n# comment\n", "utf-8")
    exf = "exc.txt"
    (tmp_path / exf).write_text("b.py\n", "utf-8")

    # Non-relative glob patterns are unsupported

    result: Result = run_cli_in(
        tmp_path,
        [
            CliCmd.STRIP,
            CliOpt.INCLUDE_FROM,
            str(incf),
            CliOpt.EXCLUDE_FROM,
            str(exf),
            CliOpt.APPLY_CHANGES,
            a.name,
            b.name,
        ],
    )

    assert_SUCCESS(result)

    assert TOPMARK_START_MARKER not in a.read_text("utf-8")

    assert TOPMARK_START_MARKER in b.read_text("utf-8")
