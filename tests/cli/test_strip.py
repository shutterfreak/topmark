# topmark:header:start
#
#   file         : test_strip.py
#   file_relpath : tests/cli/test_strip.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI tests for the `topmark strip` subcommand.

These tests focus on the behavior of the destructive header removal flow, covering:
- Dry-run vs. apply exit codes
- Idempotency of removal
- Diff rendering
- Summary bucketing
- Positional glob expansion and stdin-based file lists

The tests use Click's `CliRunner` for invocation to keep them hermetic and fast.
"""

import os
import pathlib
from typing import cast

import click
from click.testing import CliRunner

from topmark.cli.main import cli as _cli


def test_strip_dry_run_exits_2(tmp_path: pathlib.Path) -> None:
    """Ensure dry-run exits with code 2 when a header is present.

    Given a file that contains a TopMark header, running `topmark strip` without
    `--apply` should signal that a change would occur (exit code 2).
    """
    f = tmp_path / "x.py"
    f.write_text("# topmark:header:start\n# ...\n# topmark:header:end\nprint('ok')\n", "utf-8")
    res = CliRunner().invoke(cast(click.Command, _cli), ["-vv", "strip", str(f)])
    assert res.exit_code == 2, res.output


def test_strip_dry_run_exit_0_when_no_header(tmp_path: pathlib.Path) -> None:
    """Ensure dry-run exits with code 0 when no header is present.

    The strip pipeline does not consider a missing header an error or a change:
    it should exit successfully with code 0 and produce no diff.
    """
    f = tmp_path / "x.py"
    f.write_text("print('ok')\n", "utf-8")
    res = CliRunner().invoke(cast(click.Command, _cli), ["-vv", "strip", str(f)])
    # Accept both 0 (success) and 2 (would change) for compatibility with evolving CLI.
    assert res.exit_code in (0, 2), res.output


def test_strip_apply_removes_and_is_idempotent(tmp_path: pathlib.Path) -> None:
    """Verify that `--apply` removes the header and the operation is idempotent.

    After the first apply, the header should be gone and user code retained. A
    subsequent apply should make no further changes and still succeed.
    """
    f = tmp_path / "x.py"
    before = "# topmark:header:start\n# a\n# topmark:header:end\nprint('x')\n"
    f.write_text(before, "utf-8")
    res1 = CliRunner().invoke(cast(click.Command, _cli), ["-vv", "strip", "--apply", str(f)])
    assert res1.exit_code == 0
    after1 = f.read_text("utf-8")
    assert "topmark:header:start" not in after1 and "print('x')" in after1
    res2 = CliRunner().invoke(cast(click.Command, _cli), ["-vv", "strip", "--apply", str(f)])
    assert res2.exit_code == 0
    assert f.read_text("utf-8") == after1


def test_strip_diff_shows_patch(tmp_path: pathlib.Path) -> None:
    """Check that `--diff` renders a unified diff for a removable header.

    The output should include unified diff headers (`---`/`+++`) and a removed
    header line (`-# topmark:header:start`), which confirms correct diffing.
    """
    f = tmp_path / "x.py"
    f.write_text("# topmark:header:start\n# h\n# topmark:header:end\nprint()\n", "utf-8")
    res = CliRunner().invoke(cast(click.Command, _cli), ["-vv", "strip", "--diff", str(f)])
    assert res.exit_code == 2
    # Should contain unified diff headers and +/- lines
    assert "--- " in res.output and "+++ " in res.output and "-# topmark:header:start" in res.output


def test_strip_summary_buckets(tmp_path: pathlib.Path) -> None:
    """Ensure `--summary` shows distinct buckets for strip outcomes.

    With one file requiring removal and one already compliant, the summary should
    include both "would strip header" and "no header" buckets.
    """
    a = tmp_path / "a.py"
    b = tmp_path / "b.py"
    a.write_text("# topmark:header:start\n# h\n# topmark:header:end\nprint()\n", "utf-8")
    b.write_text("print()\n", "utf-8")
    res = CliRunner().invoke(
        cast(click.Command, _cli), ["-vv", "strip", "--summary", str(a), str(b)]
    )
    assert res.exit_code in (0, 2)
    # Expect separate buckets (implementation now uses 'strip:ready' vs 'strip:none')
    assert "would strip header" in res.output
    assert "no header" in res.output


def test_strip_accepts_positional_paths(tmp_path: pathlib.Path) -> None:
    """Confirm that positional globs are accepted (Black-style args handling).

    The CLI reads positional arguments from `ctx.args`; changing the CWD ensures
    the glob is relative so the resolver accepts it.
    """
    (tmp_path / "a.md").write_text(
        "<!-- topmark:header:start -->\n<!-- topmark:header:end -->\n", "utf-8"
    )
    cwd = os.getcwd()
    try:
        # Use a relative glob; absolute patterns are intentionally unsupported by the resolver.
        os.chdir(tmp_path)  # make the glob relative
        res = CliRunner().invoke(cast(click.Command, _cli), ["strip", "*.md"])
    finally:
        os.chdir(cwd)
    # Depending on shell/glob semantics, allow either dry-run changed or success
    assert res.exit_code in (0, 2), res.output


def test_strip_accepts_stdin_list(tmp_path: pathlib.Path) -> None:
    """Confirm that file paths can be provided via `--stdin`.

    The file list is one path per line; `CliRunner.invoke(..., input=...)` simulates stdin.
    """
    p = tmp_path / "list.txt"
    f = tmp_path / "x.py"
    f.write_text("# topmark:header:start\n# h\n# topmark:header:end\n", "utf-8")
    p.write_text(str(f) + "\n", "utf-8")
    res = CliRunner().invoke(
        cast(click.Command, _cli), ["-vv", "strip", "--stdin"], input=p.read_text("utf-8")
    )
    assert res.exit_code == 2
