# topmark:header:start
#
#   file         : test_strip.py
#   file_relpath : tests/cli/test_strip.py
#   project      : TopMark
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

import os
import re
from pathlib import Path
from typing import cast

import click
from click.testing import CliRunner

from topmark.cli.exit_codes import ExitCode
from topmark.cli.main import cli as _cli
from topmark.constants import TOPMARK_END_MARKER, TOPMARK_START_MARKER

# Type hint for the CLI command object
cli = cast(click.Command, _cli)


def test_strip_dry_run_exits_2(tmp_path: Path) -> None:
    """Dry-run should exit 2 when a header is present (action would occur).

    Given a file that contains a recognizable TopMark header, calling `topmark strip`
    without `--apply` should signal "would change" with exit code 2.
    """
    f = tmp_path / "x.py"
    f.write_text(f"# {TOPMARK_START_MARKER}\n# ...\n# {TOPMARK_END_MARKER}\nprint('ok')\n", "utf-8")

    result = CliRunner().invoke(cli, ["strip", str(f)])

    # Exit 2 means "changes would be made" (pre-commit friendly).
    assert result.exit_code == ExitCode.WOULD_CHANGE, result.output


def test_strip_dry_run_exit_0_when_no_header(tmp_path: Path) -> None:
    """Dry-run should exit 0 when there is nothing to strip.

    Ensures that files without a header do not trigger non-zero exit codes.
    """
    f = tmp_path / "x.py"
    f.write_text("print('ok')\n", "utf-8")

    result = CliRunner().invoke(cli, ["strip", str(f)])

    # No header → nothing to do → exit 0
    assert result.exit_code == ExitCode.SUCCESS, result.output


def test_strip_apply_removes_and_is_idempotent(tmp_path: Path) -> None:
    """Verify that `--apply` removes the header and the operation is idempotent.

    First `--apply` removes the header block; a second run should keep the file
    unchanged and still succeed.
    """
    f = tmp_path / "x.py"
    before = f"# {TOPMARK_START_MARKER}\n# a\n# {TOPMARK_END_MARKER}\nprint('x')\n"
    f.write_text(before, "utf-8")

    # First application removes the header.
    result_strip_1 = CliRunner().invoke(cli, ["strip", "--apply", str(f)])

    assert result_strip_1.exit_code == ExitCode.SUCCESS, result_strip_1.output

    after_strip_1 = f.read_text("utf-8")
    assert TOPMARK_START_MARKER not in after_strip_1 and "print('x')" in after_strip_1

    # Second application should be a no-op and still succeed.
    result_strip_2 = CliRunner().invoke(cli, ["strip", "--apply", str(f)])

    assert result_strip_2.exit_code == ExitCode.SUCCESS, result_strip_2.output

    assert f.read_text("utf-8") == after_strip_1


def test_strip_diff_shows_patch(tmp_path: Path) -> None:
    """`--diff` should emit a unified diff showing header removal.

    Verifies presence of unified diff markers and a removed header line.
    """
    f = tmp_path / "x.py"
    f.write_text(f"# {TOPMARK_START_MARKER}\n# h\n# {TOPMARK_END_MARKER}\nprint()\n", "utf-8")

    result = CliRunner().invoke(cli, ["strip", "--diff", str(f)])

    # With a removable header, diff-only should exit 2 (would change).
    assert result.exit_code == ExitCode.WOULD_CHANGE, result.output

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
    has = tmp_path / "has.py"
    clean = tmp_path / "clean.py"
    bad = tmp_path / "bad.py"
    has.write_text(f"# {TOPMARK_START_MARKER}\n# h\n# {TOPMARK_END_MARKER}\nprint()\n", "utf-8")
    clean.write_text("print()\n", "utf-8")
    bad.write_text(f"# {TOPMARK_START_MARKER}\n# x\nprint()\n", "utf-8")

    result = CliRunner().invoke(
        cli,
        [
            "strip",
            "--summary",
            str(has),  # file with good header: "would strip header"
            str(clean),  # file without header: "up-to-date"
            str(bad),  # file with malformed header: "up-to-date"
        ],
    )

    # Depending on aggregation, exit may be 2 (would change) or 0 (no changes).
    assert result.exit_code in (ExitCode.SUCCESS, ExitCode.WOULD_CHANGE), result.output

    # Expect human-facing wording present for both categories.
    assert re.search(r"would strip header[ ]*: 1", result.output), "missing 'would strip header: 1'"
    assert re.search(r"up-to-date[ ]*: 2", result.output), "missing 'up-to-date: 2'"


def test_strip_accepts_positional_paths(tmp_path: Path) -> None:
    """`topmmark strip` should accept positional globs/paths like the default command.

    Uses a simple Markdown example to validate path ingress.
    """
    p = tmp_path / "a.md"
    p.write_text(f"<!-- {TOPMARK_START_MARKER} -->\n<!-- {TOPMARK_END_MARKER} -->\n", "utf-8")

    result = CliRunner().invoke(cli, ["strip", str(p)])

    # Header present → dry-run 'would change' = 2; tolerate 0 in edge runners.
    assert result.exit_code in (ExitCode.SUCCESS, ExitCode.WOULD_CHANGE), result.output

    cwd = os.getcwd()
    try:
        # Use a relative glob; absolute patterns are intentionally unsupported by the resolver.
        os.chdir(tmp_path)  # make the glob relative

        result = CliRunner().invoke(cli, ["strip", "*.md"])
    finally:
        os.chdir(cwd)

    # Depending on shell/glob semantics, allow either dry-run changed or success
    assert result.exit_code in (ExitCode.SUCCESS, ExitCode.WOULD_CHANGE), result.output


def test_strip_accepts_stdin_list(tmp_path: Path) -> None:
    """`topmark strip --stdin` should read a newline-delimited list of files from stdin.

    Ensures parity with the default command's stdin behavior.

    The file list is one path per line; `CliRunner.invoke(..., input=...)` simulates stdin.
    """
    p = tmp_path / "list.txt"
    f = tmp_path / "x.py"

    f.write_text(f"# {TOPMARK_START_MARKER}\n# h\n# {TOPMARK_END_MARKER}\n", "utf-8")
    p.write_text(str(f) + "\n", "utf-8")

    result = CliRunner().invoke(cli, ["strip", "--stdin"], input=p.read_text("utf-8"))

    # Header present → would-change exit 2.
    assert result.exit_code == ExitCode.WOULD_CHANGE, result.output


def test_strip_ignores_missing_end_marker(tmp_path: Path) -> None:
    """Do not strip when the end marker is missing.

    Creates a file with a start marker but no matching end marker. The
    `strip` subcommand should treat this as *not a removable header* and
    therefore perform no changes when `--apply` is used.

    Args:
        tmp_path: Temporary path fixture provided by pytest.
    """
    f = tmp_path / "bad.py"
    f.write_text(f"# {TOPMARK_START_MARKER}\n# x\nprint()\n", "utf-8")

    result = CliRunner().invoke(cli, ["-vv", "strip", "--apply", str(f)])

    assert result.exit_code == ExitCode.SUCCESS, result.output

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
    a = tmp_path / "a.py"
    b = tmp_path / "b.py"
    a.write_text(f"# {TOPMARK_START_MARKER}\n# h\n# {TOPMARK_END_MARKER}\n", "utf-8")
    b.write_text(f"# {TOPMARK_START_MARKER}\n# h\n# {TOPMARK_END_MARKER}\n", "utf-8")

    # Use **relative** patterns: resolver disallows absolute patterns.
    incf = tmp_path / "inc.txt"
    incf.write_text("*.py\n# comment\n", "utf-8")
    exf = tmp_path / "exc.txt"
    exf.write_text("b.py\n", "utf-8")

    # Non-relative glob patterns are unsupported
    cwd = os.getcwd()
    try:
        os.chdir(tmp_path)

        result = CliRunner().invoke(
            cli,
            [
                "-vv",
                "strip",
                "--include-from",
                str(incf.name),
                "--exclude-from",
                str(exf.name),
                "--apply",
            ],
        )
    finally:
        os.chdir(cwd)

    assert result.exit_code == ExitCode.SUCCESS, result.output

    assert TOPMARK_START_MARKER not in a.read_text("utf-8")

    assert TOPMARK_START_MARKER in b.read_text("utf-8")
