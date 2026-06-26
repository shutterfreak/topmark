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

from typing import TYPE_CHECKING

import pytest

from tests.cli.conftest import assert_CONFIG_ERROR
from tests.cli.conftest import assert_human_output_contains
from tests.cli.conftest import assert_human_output_does_not_contain
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
    assert_human_output_does_not_contain(
        output_format=None,
        output=result_normal.output.lower(),
        expected=ResolveStatus.UNSUPPORTED.value,
    )

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
    assert_human_output_contains(
        output_format=None,
        output=result_summary.output.lower(),
        expected=ResolveStatus.UNSUPPORTED.value,
    )


# ---- Test hidden singular option aliases ----


@pytest.mark.parametrize(
    ("include_opt", "exclude_opt"),
    [
        (CliOpt.INCLUDE_FILE_TYPES, CliOpt.EXCLUDE_FILE_TYPES),
        (CliOpt.INCLUDE_FILE_TYPE, CliOpt.EXCLUDE_FILE_TYPE),
        (CliOpt.INCLUDE_FILE_TYPES, CliOpt.EXCLUDE_FILE_TYPE),
        (CliOpt.INCLUDE_FILE_TYPE, CliOpt.EXCLUDE_FILE_TYPES),
    ],
)
def test_file_type_filter_accepts_plural_and_hidden_singular_aliases(
    tmp_path: Path,
    include_opt: str,
    exclude_opt: str,
) -> None:
    """File type filter accepts plural and hidden singular aliases.

    This tests:
    - plural options;
    - hidden singular aliases;
    - mixed canonical/hidden spelling combinations;
    - CSV parsing;
    - actual filter semantics.
    """
    py: Path = tmp_path / "a.py"
    md: Path = tmp_path / "a.md"
    java: Path = tmp_path / "A.java"
    toml: Path = tmp_path / "settings.toml"

    py.write_text("print('x')\n", "utf-8")
    md.write_text("# Title\n", "utf-8")
    java.write_text("class A {}\n", "utf-8")
    toml.write_text("[project]\nname = 'x'\n", "utf-8")

    result: Result = run_cli(
        [
            CliCmd.CHECK,
            include_opt,
            "python,markdown,javascript,toml",
            exclude_opt,
            "java",
            CliOpt.APPLY_CHANGES,
            str(tmp_path),
        ],
    )

    assert_SUCCESS(result)
    assert TOPMARK_START_MARKER in py.read_text("utf-8")
    assert TOPMARK_START_MARKER in md.read_text("utf-8")
    assert TOPMARK_START_MARKER not in java.read_text("utf-8")
    assert TOPMARK_START_MARKER in toml.read_text("utf-8")


@pytest.mark.parametrize(
    (
        "include_file_types",
        "exclude_file_types",
        "expected_py_has_header",
        "expected_md_has_header",
        "expected_ts_has_header",
    ),
    [
        ("topmark:python", "python", False, False, False),
        ("python", "topmark:python", False, False, False),
        ("topmark:python", "topmark:python", False, False, False),
        ("topmark:python,topmark:markdown", "python", False, True, False),
        ("topmark:python,topmark:markdown", "python,markdown", False, False, False),
    ],
)
def test_file_type_filter_normalized_overlap_excludes_matching_types(
    tmp_path: Path,
    include_file_types: str,
    exclude_file_types: str,
    expected_py_has_header: bool,
    expected_md_has_header: bool,
    expected_ts_has_header: bool,
) -> None:
    """Overlapping include/exclude file-type filters are normalized before filtering.

    Local identifiers such as `python` and qualified identifiers such as
    `topmark:python` may resolve to the same canonical file type. When an
    include and exclude entry overlap after normalization, exclusion wins for
    the overlapping canonical type only. Non-overlapping include entries remain
    selected and should still be processed.
    """
    py: Path = tmp_path / "a.py"
    md: Path = tmp_path / "a.md"
    ts: Path = tmp_path / "a.ts"

    py.write_text("print('x')\n", "utf-8")
    md.write_text("# Title\n", "utf-8")
    ts.write_text("console.log(1);\n", "utf-8")

    result: Result = run_cli(
        [
            CliCmd.CHECK,
            CliOpt.INCLUDE_FILE_TYPES,
            include_file_types,
            CliOpt.EXCLUDE_FILE_TYPES,
            exclude_file_types,
            CliOpt.APPLY_CHANGES,
            str(tmp_path),
        ],
    )

    assert_SUCCESS(result)
    assert (TOPMARK_START_MARKER in py.read_text("utf-8")) is expected_py_has_header
    assert (TOPMARK_START_MARKER in md.read_text("utf-8")) is expected_md_has_header
    assert (TOPMARK_START_MARKER in ts.read_text("utf-8")) is expected_ts_has_header


@pytest.mark.parametrize("command", [CliCmd.CHECK, CliCmd.STRIP, CliCmd.PROBE])
@pytest.mark.parametrize(
    ("include_file_types", "exclude_file_types", "expected_removed_file_types"),
    [
        ("python", "python", ("topmark:python",)),
        ("python", "topmark:python", ("topmark:python",)),
        ("topmark:python", "python", ("topmark:python",)),
        ("topmark:python", "topmark:python", ("topmark:python",)),
        (
            "topmark:python,topmark:markdown",
            "python,markdown",
            ("topmark:python", "topmark:markdown"),
        ),
    ],
)
def test_strict_file_type_filter_overlap_reports_actionable_warning(
    tmp_path: Path,
    command: str,
    include_file_types: str,
    exclude_file_types: str,
    expected_removed_file_types: tuple[str, ...],
) -> None:
    """Strict mode fails on normalized overlap warnings and renders their cause.

    Overlapping include/exclude file-type filters are deterministic because
    exclusion wins, but the overlap is still an actionable configuration
    warning. Under strict mode, that warning should stop processing with
    `CONFIG_ERROR` while preserving the diagnostic details that explain which
    canonical file types were removed from the include set.
    """
    py: Path = tmp_path / "a.py"
    py.write_text("print('x')\n", "utf-8")

    result: Result = run_cli(
        [
            command,
            CliOpt.STRICT,
            CliOpt.INCLUDE_FILE_TYPES,
            include_file_types,
            CliOpt.EXCLUDE_FILE_TYPES,
            exclude_file_types,
            str(py),
        ],
    )

    assert_CONFIG_ERROR(result)
    assert_human_output_contains(
        output_format=None,
        output=result.output.lower(),
        expected="file types specified in both include and exclude filters",
    )
    assert_human_output_contains(
        output_format=None,
        output=result.output.lower(),
        expected="exclusion wins",
    )
    for expected_removed_file_type in expected_removed_file_types:
        assert_human_output_contains(
            output_format=None,
            output=result.output.lower(),
            expected=expected_removed_file_type,
        )


@pytest.mark.parametrize("command", [CliCmd.CHECK, CliCmd.STRIP, CliCmd.PROBE])
def test_file_type_filter_merges_repeated_plural_and_hidden_singular_aliases(
    tmp_path: Path,
    command: str,
) -> None:
    """Repeated plural and hidden singular aliases are accepted and merged.

    This test intentionally runs in dry-run mode against one selected file. It
    verifies the CLI parsing and file-type filter accumulation contract without
    depending on command-specific mutation behavior or directory probe reporting.
    """
    md: Path = tmp_path / "a.md"

    md.write_text("# Title\n", "utf-8")

    result: Result = run_cli(
        [
            command,
            CliOpt.INCLUDE_FILE_TYPE,
            "python",
            CliOpt.INCLUDE_FILE_TYPES,
            "javascript,markdown,toml",
            CliOpt.EXCLUDE_FILE_TYPE,
            "html",
            CliOpt.EXCLUDE_FILE_TYPES,
            "css,xml,svg",
            str(md),
        ],
    )

    assert_SUCCESS_or_WOULD_CHANGE(result)
