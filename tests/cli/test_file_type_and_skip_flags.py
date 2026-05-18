# topmark:header:start
#
#   project      : TopMark
#   file         : test_file_type_and_skip_flags.py
#   file_relpath : tests/cli/test_file_type_and_skip_flags.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI tests for file-type filters and report scoping.

This module covers:
- `--file-type` filters for `check` and `strip`,
- `--report` scoping for per-file output,
- summary behavior when per-file entries are filtered.

These are behavior/reporting tests rather than pure exit-code contract tests.
Exit-code assertions are used only to verify that the command completed with
the expected high-level status.

Labels asserted in this module follow the public summary buckets documented in
`topmark.cli.utils.classify_outcome()`. Tests should match label **substrings**
rather than exact phrases to tolerate minor wording tweaks.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from tests.cli.conftest import assert_SUCCESS
from tests.cli.conftest import assert_SUCCESS_or_WOULD_CHANGE
from tests.cli.conftest import run_cli
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt
from topmark.core.constants import TOPMARK_END_MARKER
from topmark.core.constants import TOPMARK_START_MARKER
from topmark.pipeline.reporting import ReportScope
from topmark.pipeline.status import ResolveStatus
from topmark.pipeline.status import StripStatus

if TYPE_CHECKING:
    from pathlib import Path

    from click.testing import Result


# --- File-type filters ---


@pytest.mark.parametrize("file_type_id", ["python", "topmark:python"])
def test_file_type_filter_limits_check_to_selected_types(
    tmp_path: Path,
    file_type_id: str,
) -> None:
    """`check --file-type` should process only matching file types."""
    py: Path = tmp_path / "a.py"
    ts: Path = tmp_path / "a.ts"
    py.write_text("print('x')\n", "utf-8")
    ts.write_text("console.log(1);\n", "utf-8")

    # Only Python files should be selected for header insertion.
    result: Result = run_cli(
        [
            CliCmd.CHECK,
            CliOpt.INCLUDE_FILE_TYPES,
            file_type_id,
            CliOpt.APPLY_CHANGES,
            str(tmp_path),
        ],
    )

    assert_SUCCESS(result)

    # Python file should now have a header; TypeScript file should remain unchanged.
    out_py: str = py.read_text("utf-8")
    assert TOPMARK_START_MARKER in out_py

    out_ts: str = ts.read_text("utf-8")
    assert TOPMARK_START_MARKER not in out_ts


@pytest.mark.parametrize("file_type_id", ["python", "topmark:python"])
def test_file_type_filter_limits_strip_to_selected_types(
    tmp_path: Path,
    file_type_id: str,
) -> None:
    """`strip --file-type` should process only matching file types."""
    py: Path = tmp_path / "b.py"
    ts: Path = tmp_path / "b.ts"
    py.write_text(
        f"# {TOPMARK_START_MARKER}\n# test:header\n# {TOPMARK_END_MARKER}\nprint()\n", "utf-8"
    )
    ts.write_text(
        f"// {TOPMARK_START_MARKER}\n// test:header\n// {TOPMARK_END_MARKER}\nconsole.log(1)\n",
        "utf-8",
    )

    # Strip only Python files; the TypeScript header should remain.
    result: Result = run_cli(
        [
            CliCmd.STRIP,
            CliOpt.INCLUDE_FILE_TYPES,
            file_type_id,
            CliOpt.APPLY_CHANGES,
            str(tmp_path),
        ],
    )

    assert_SUCCESS(result)

    assert TOPMARK_START_MARKER not in py.read_text("utf-8")

    assert TOPMARK_START_MARKER in ts.read_text("utf-8")


# --- Report scope: actionable vs summary output ---


def test_report_all_summary_counts_ready_and_not_needed_strip_outcomes(tmp_path: Path) -> None:
    """`strip --summary --report all` should count both ready and not-needed outcomes.

    Summary output reports the distribution of all selected outcomes, including files
    that need stripping and files where stripping is not needed.
    """
    f1: Path = tmp_path / "has.py"
    f2: Path = tmp_path / "clean.py"
    f1.write_text(
        f"# {TOPMARK_START_MARKER}\n# test:header\n# {TOPMARK_END_MARKER}\nprint()\n", "utf-8"
    )
    f2.write_text("print()\n", "utf-8")

    # In summary mode with report=all, both actionable and non-actionable buckets are counted.
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
    # Labels come from summary bucket values.
    assert StripStatus.READY.value in out
    # The non-actionable "not needed" bucket should still be present in summary.
    assert StripStatus.NOT_NEEDED.value in out


def test_report_actionable_hides_unsupported_per_file_but_summary_counts_it(tmp_path: Path) -> None:
    """`--report actionable` should hide unsupported per-file entries but count summaries.

    In actionable mode, unsupported per-file entries are suppressed. Summary mode still
    reports the full outcome distribution, including unsupported inputs.
    """
    # Create a clearly unsupported file (extension not registered).
    unk: Path = tmp_path / "data.unknown"
    unk.write_text("payload\n", "utf-8")

    # Per-file actionable output should suppress unsupported entries.
    result_normal: Result = run_cli(
        [
            CliCmd.CHECK,
            CliOpt.REPORT,
            ReportScope.ACTIONABLE,  # Default
            str(unk),
        ],
    )

    # Nothing to do, and the unsupported file is hidden from per-file output.
    assert_SUCCESS(result_normal)
    assert ResolveStatus.UNSUPPORTED.value not in result_normal.output.lower()

    # Summary mode should still count the unsupported bucket.
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
