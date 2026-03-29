# topmark:header:start
#
#   project      : TopMark
#   file         : test_file_type_and_skip_flags.py
#   file_relpath : tests/cli/test_file_type_and_skip_flags.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI tests for `--file-type` and report scoping (`--report`).

Covers:
- `--file-type` filters: default and `strip` should only act on the selected type(s).
- `--report`: actionable/problematics scoping hides compliant and/or unsupported entries.

Labels asserted in this module follow the public summary buckets documented in
`topmark.cli.utils.classify_outcome()`. Tests should match label **substrings**
rather than exact phrases to tolerate minor wording tweaks.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from tests.cli.conftest import assert_SUCCESS
from tests.cli.conftest import assert_SUCCESS_or_WOULD_CHANGE
from tests.cli.conftest import run_cli
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt
from topmark.constants import TOPMARK_END_MARKER
from topmark.constants import TOPMARK_START_MARKER
from topmark.pipeline.reporting import ReportScope
from topmark.pipeline.status import ResolveStatus
from topmark.pipeline.status import StripStatus

if TYPE_CHECKING:
    from pathlib import Path

    from click.testing import Result


def test_file_type_filter_limits_check_processing(tmp_path: Path) -> None:
    """`--file-type` limits `check` processing to the selected types."""
    py: Path = tmp_path / "a.py"
    ts: Path = tmp_path / "a.ts"
    py.write_text("print('x')\n", "utf-8")
    ts.write_text("console.log(1);\n", "utf-8")

    # Only act on python files
    result: Result = run_cli(
        [
            CliCmd.CHECK,
            CliOpt.INCLUDE_FILE_TYPES,
            "python",
            CliOpt.APPLY_CHANGES,
            str(tmp_path),
        ],
    )

    assert_SUCCESS(result)

    # Python file should now have a header; TS file should remain unchanged.
    out_py: str = py.read_text("utf-8")
    assert TOPMARK_START_MARKER in out_py

    out_ts: str = ts.read_text("utf-8")
    assert TOPMARK_START_MARKER not in out_ts


def test_file_type_filter_limits_strip_processing(tmp_path: Path) -> None:
    """`--file-type` limits `strip` processing to the selected types."""
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
        [
            CliCmd.STRIP,
            CliOpt.INCLUDE_FILE_TYPES,
            "python",
            CliOpt.APPLY_CHANGES,
            str(tmp_path),
        ],
    )

    assert_SUCCESS(result)

    assert TOPMARK_START_MARKER not in py.read_text("utf-8")

    assert TOPMARK_START_MARKER in ts.read_text("utf-8")


def test_report_actionable_per_file_hides_not_needed_but_summary_counts_it(tmp_path: Path) -> None:
    """`--report actionable` filters per-file output, but summary still counts compliant files.

    In actionable mode, TopMark suppresses per-file entries that have no actionable work.
    However, `--summary` is an overview of *all* outcomes, so it still includes the
    compliant/not-needed bucket count.
    """
    f1: Path = tmp_path / "has.py"
    f2: Path = tmp_path / "clean.py"
    f1.write_text(
        f"# {TOPMARK_START_MARKER}\n# test:header\n# {TOPMARK_END_MARKER}\nprint()\n", "utf-8"
    )
    f2.write_text("print()\n", "utf-8")

    # In summary mode, ensure the compliant bucket isn't shown when actionable reporting is set.
    result: Result = run_cli(
        [
            CliCmd.STRIP,
            CliOpt.RESULTS_SUMMARY_MODE,
            CliOpt.REPORT,
            ReportScope.ALL,  # Ensure compliant files are also reported
            str(tmp_path),
        ],
    )

    assert_SUCCESS_or_WOULD_CHANGE(result)

    out: str = result.output.lower()
    # NOTE: Labels come from map_bucket/summary labels
    assert StripStatus.READY.value in out
    # The compliant ("not needed") bucket should still be present in summary
    assert StripStatus.NOT_NEEDED.value in out


def test_report_actionable_per_file_hides_unsupported_but_summary_counts_it(tmp_path: Path) -> None:
    """`--report actionable` filters per-file output, but summary still counts unsupported files.

    In actionable mode, TopMark suppresses per-file entries that are unsupported.
    However, `--summary` remains a full distribution of outcomes and still includes an
    unsupported bucket count.
    """
    # Create a clearly unsupported file (extension not registered).
    unk: Path = tmp_path / "data.unknown"
    unk.write_text("payload\n", "utf-8")

    # Normal mode
    result_normal: Result = run_cli(
        [
            CliCmd.CHECK,
            CliOpt.REPORT,
            ReportScope.ACTIONABLE,  # Default
            str(unk),
        ],
    )

    # nothing to do, and unknown is skipped from output
    assert_SUCCESS(result_normal)
    assert ResolveStatus.UNSUPPORTED.value not in result_normal.output.lower()

    # Summary mode: the "unsupported" bucket should still be present in summary.
    result_summary: Result = run_cli(
        [
            CliCmd.CHECK,
            CliOpt.RESULTS_SUMMARY_MODE,
            CliOpt.REPORT,
            ReportScope.ACTIONABLE,  # Default
            str(unk),
        ],
    )

    assert_SUCCESS(result_summary)
    assert ResolveStatus.UNSUPPORTED.value in result_summary.output.lower()
