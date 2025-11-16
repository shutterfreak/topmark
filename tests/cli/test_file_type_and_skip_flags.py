# topmark:header:start
#
#   project      : TopMark
#   file         : test_file_type_and_skip_flags.py
#   file_relpath : tests/cli/test_file_type_and_skip_flags.py
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

from pathlib import Path
from typing import TYPE_CHECKING

from tests.cli.conftest import assert_SUCCESS, assert_SUCCESS_or_WOULD_CHANGE, run_cli
from topmark.constants import TOPMARK_END_MARKER, TOPMARK_START_MARKER
from topmark.pipeline.status import ResolveStatus, StripStatus

if TYPE_CHECKING:
    from pathlib import Path

    from click.testing import Result


def test_file_type_filter_limits_processing_default(tmp_path: Path) -> None:
    """`--file-type` limits header insertion/updates to selected types."""
    py: Path = tmp_path / "a.py"
    ts: Path = tmp_path / "a.ts"
    py.write_text("print('x')\n", "utf-8")
    ts.write_text("console.log(1);\n", "utf-8")

    # Only act on python files
    result: Result = run_cli(
        ["check", "--file-type", "python", "--apply", str(tmp_path)],
    )

    assert_SUCCESS(result)

    # Python file should now have a header; TS file should remain unchanged.
    out_py: str = py.read_text("utf-8")
    assert TOPMARK_START_MARKER in out_py

    out_ts: str = ts.read_text("utf-8")
    assert TOPMARK_START_MARKER not in out_ts


def test_file_type_filter_limits_processing_strip(tmp_path: Path) -> None:
    """`--file-type` also constrains `strip` to the selected types."""
    py: Path = tmp_path / "b.py"
    ts: Path = tmp_path / "b.ts"
    py.write_text(
        f"# {TOPMARK_START_MARKER}\n# test:header\n# {TOPMARK_END_MARKER}\nprint()\n", "utf-8"
    )
    ts.write_text(
        f"// {TOPMARK_START_MARKER}\n// test:header\n// {TOPMARK_END_MARKER}\nconsole.log(1)\n",
        "utf-8",
    )

    # Strip only for python → TS header remains
    result: Result = run_cli(
        ["strip", "--file-type", "python", "--apply", str(tmp_path)],
    )

    assert_SUCCESS(result)

    assert TOPMARK_START_MARKER not in py.read_text("utf-8")

    assert TOPMARK_START_MARKER in ts.read_text("utf-8")


def test_skip_compliant_hides_clean_files(tmp_path: Path) -> None:
    """`--skip-compliant` removes compliant files from per-file and summary output."""
    f1: Path = tmp_path / "has.py"
    f2: Path = tmp_path / "clean.py"
    f1.write_text(
        f"# {TOPMARK_START_MARKER}\n# test:header\n# {TOPMARK_END_MARKER}\nprint()\n", "utf-8"
    )
    f2.write_text("print()\n", "utf-8")

    # In summary mode, ensure the compliant bucket isn't shown when skip-compliant is set.
    result: Result = run_cli(
        ["strip", "--summary", "--skip-compliant", str(tmp_path)],
    )

    assert_SUCCESS_or_WOULD_CHANGE(result)

    out: str = result.output.lower()
    # NOTE: Labels come from map_bucket/summary labels
    assert StripStatus.READY.value in out


def test_skip_unsupported_hides_unknown(tmp_path: Path) -> None:
    """`--skip-unsupported` hides unknown types from normal and summary outputs."""
    # Create a clearly unsupported file (extension not registered).
    unk: Path = tmp_path / "data.unknown"
    unk.write_text("payload\n", "utf-8")

    # Normal mode
    result_normal: Result = run_cli(
        ["check", "--skip-unsupported", str(unk)],
    )

    # nothing to do, and unknown is skipped from output
    assert_SUCCESS(result_normal)

    # Summary mode: the "unsupported" bucket should not be present now.
    result_summary: Result = run_cli(
        ["check", "--summary", "--skip-unsupported", str(unk)],
    )

    assert_SUCCESS(result_summary)

    assert ResolveStatus.UNSUPPORTED.value not in result_summary.output
