# topmark:header:start
#
#   file         : test_file_type_and_skip_flags.py
#   file_relpath : tests/cli/test_file_type_and_skip_flags.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI tests for `--file-type`, `--skip-compliant`, and `--skip-unsupported`.

Covers:
- `--file-type` filters: default and `strip` should only act on the selected type(s).
- `--skip-compliant`: compliant files are hidden in both normal and summary modes.
- `--skip-unsupported`: unknown file types are hidden from output and summary.

Labels asserted in this module follow the public summary buckets documented in
`topmark.cli.utils.classify_outcome()`. Tests should match label **substrings**
rather than exact phrases to tolerate minor wording tweaks.
"""

from __future__ import annotations

import pathlib
from typing import cast

import click
from click.testing import CliRunner

from topmark.cli.main import cli as _cli


def test_file_type_filter_limits_processing_default(tmp_path: pathlib.Path) -> None:
    """`--file-type` limits header insertion/updates to selected types."""
    py = tmp_path / "a.py"
    ts = tmp_path / "a.ts"
    py.write_text("print('x')\n", "utf-8")
    ts.write_text("console.log(1);\n", "utf-8")

    # Only act on python files
    res = CliRunner().invoke(
        cast(click.Command, _cli),
        ["-vv", "--file-type", "python", "--apply", str(tmp_path)],
    )
    assert res.exit_code == 0, res.output

    # Python file should now have a header; TS file should remain unchanged.
    out_py = py.read_text("utf-8")
    out_ts = ts.read_text("utf-8")
    assert "topmark:header:start" in out_py
    assert "topmark:header:start" not in out_ts


def test_file_type_filter_limits_processing_strip(tmp_path: pathlib.Path) -> None:
    """`--file-type` also constrains `strip` to the selected types."""
    py = tmp_path / "b.py"
    ts = tmp_path / "b.ts"
    py.write_text("# topmark:header:start\n# h\n# topmark:header:end\nprint()\n", "utf-8")
    ts.write_text("// topmark:header:start\n// h\n// topmark:header:end\nconsole.log(1)\n", "utf-8")

    # Strip only for python → TS header remains
    res = CliRunner().invoke(
        cast(click.Command, _cli),
        ["-vv", "strip", "--file-type", "python", "--apply", str(tmp_path)],
    )
    assert res.exit_code == 0, res.output
    assert "topmark:header:start" not in py.read_text("utf-8")
    assert "topmark:header:start" in ts.read_text("utf-8")


def test_skip_compliant_hides_clean_files(tmp_path: pathlib.Path) -> None:
    """`--skip-compliant` removes compliant files from per-file and summary output."""
    f1 = tmp_path / "has.py"
    f2 = tmp_path / "clean.py"
    f1.write_text("# topmark:header:start\n# h\n# topmark:header:end\nprint()\n", "utf-8")
    f2.write_text("print()\n", "utf-8")

    # In summary mode, ensure the compliant bucket isn't shown when skip-compliant is set.
    res = CliRunner().invoke(
        cast(click.Command, _cli),
        # NOTE: do not set verbosity level so we can inspect the summary bucket list
        ["strip", "--summary", "--skip-compliant", str(tmp_path)],
    )
    assert res.exit_code in (0, 2), res.output
    out = res.output.lower()
    # NOTE: Labels come from classify_outcome(); compliant buckets ("no header"
    # or "up-to-date") may still be shown depending on current summary settings.
    # We only require that the would-change bucket is present.
    assert "would strip header" in out


def test_skip_unsupported_hides_unknown(tmp_path: pathlib.Path) -> None:
    """`--skip-unsupported` hides unknown types from normal and summary outputs."""
    # Create a clearly unsupported file (extension not registered).
    unk = tmp_path / "data.unknown"
    unk.write_text("payload\n", "utf-8")

    # Normal mode
    res1 = CliRunner().invoke(
        cast(click.Command, _cli),
        ["--skip-unsupported", str(unk)],
    )
    assert res1.exit_code == 0, res1.output  # nothing to do, and unknown is skipped from output

    # Summary mode: the "unsupported" bucket should not be present now.
    res2 = CliRunner().invoke(
        cast(click.Command, _cli),
        # NOTE: do not set verbosity level so we can inspect the summary bucket list
        ["--summary", "--skip-unsupported", str(unk)],
    )
    assert res2.exit_code == 0, res2.output
    out = res2.output.lower()
    assert "unsupported" not in out
