# topmark:header:start
#
#   project      : TopMark
#   file         : test_report_scope.py
#   file_relpath : tests/cli/test_report_scope.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI report-scope contract tests for path-based pipeline commands.

These tests pin which per-file results are visible for `check` and `strip` under
`--report actionable`, `--report noncompliant`, and `--report all`. They cover
known header-unsupported files, unknown unsupported files, supported files that
would change, supported files that are already compliant, and supported files
that are actionable only for stripping.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.cli.conftest import assert_human_output_contains_if
from tests.cli.conftest import run_cli_in
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt
from topmark.core.formats import OutputFormat
from topmark.pipeline.reporting import ReportScope

if TYPE_CHECKING:
    from pathlib import Path

    from click.testing import Result


OUTPUT_FORMATS: list[OutputFormat | None] = [
    None,  # Default is OutputFormat.TEXT.
    OutputFormat.TEXT,
    OutputFormat.MARKDOWN,
]
"""Human output formats covered by report-scope visibility tests."""


def _report_scope_args(
    *,
    command: str,
    report_scope: ReportScope,
    output_format: OutputFormat | None,
    path: str = ".",
) -> list[str]:
    """Build CLI args for a report-scope visibility assertion."""
    args: list[str] = [
        command,
        CliOpt.REPORT,
        report_scope,
    ]

    if output_format is not None:
        args.extend(
            [
                CliOpt.OUTPUT_FORMAT,
                output_format,
            ]
        )

    args.append(path)
    return args


@pytest.mark.parametrize(
    "command",
    [
        CliCmd.CHECK,
        CliCmd.STRIP,
    ],
)
@pytest.mark.parametrize("output_format", OUTPUT_FORMATS)
@pytest.mark.parametrize(
    ("report_scope", "expected_visible"),
    [
        (ReportScope.ACTIONABLE, False),
        (ReportScope.NONCOMPLIANT, True),
        (ReportScope.ALL, True),
    ],
)
def test_check_and_strip_report_scope_for_known_header_unsupported_file(
    command: str,
    output_format: OutputFormat | None,
    report_scope: ReportScope,
    expected_visible: bool,
    tmp_path: Path,
) -> None:
    """Known header-unsupported files are noncompliant but not actionable.

    `py.typed` is a known TopMark file type, but headers are unsupported for it.
    The default actionable report should summarize it rather than listing it;
    broader report scopes should include it in human per-file output.
    """
    filename: str = "py.typed"
    path: Path = tmp_path / filename
    path.touch()

    result: Result = run_cli_in(
        tmp_path,
        _report_scope_args(
            command=command,
            report_scope=report_scope,
            output_format=output_format,
        ),
    )

    assert_human_output_contains_if(
        output_format=output_format,
        output=result.output,
        expected=filename,
        expected_present=expected_visible,
    )


@pytest.mark.parametrize("output_format", OUTPUT_FORMATS)
@pytest.mark.parametrize(
    "command",
    [
        CliCmd.CHECK,
        CliCmd.STRIP,
    ],
)
@pytest.mark.parametrize(
    ("report_scope", "expected_visible"),
    [
        (ReportScope.ACTIONABLE, False),
        (ReportScope.NONCOMPLIANT, True),
        (ReportScope.ALL, True),
    ],
)
def test_check_and_strip_report_scope_for_unknown_unsupported_file(
    command: str,
    output_format: OutputFormat | None,
    report_scope: ReportScope,
    expected_visible: bool,
    tmp_path: Path,
) -> None:
    """Unknown unsupported files are noncompliant but not actionable.

    `random.unknown` is neither recognized nor mutable by TopMark. The default
    actionable report should summarize it rather than listing it; broader report
    scopes should include it in human per-file output.
    """
    filename: str = "random.unknown"
    path: Path = tmp_path / filename
    path.touch()

    result: Result = run_cli_in(
        tmp_path,
        _report_scope_args(
            command=command,
            report_scope=report_scope,
            output_format=output_format,
        ),
    )

    assert_human_output_contains_if(
        output_format=output_format,
        output=result.output,
        expected=filename,
        expected_present=expected_visible,
    )


@pytest.mark.parametrize("output_format", OUTPUT_FORMATS)
@pytest.mark.parametrize(
    "report_scope",
    [
        ReportScope.ACTIONABLE,
        ReportScope.NONCOMPLIANT,
        ReportScope.ALL,
    ],
)
def test_check_report_scope_lists_supported_headerless_file(
    output_format: OutputFormat | None,
    report_scope: ReportScope,
    tmp_path: Path,
) -> None:
    """`check` reports a supported headerless file for every report scope.

    A Python file without a TopMark header is actionable for `check` because
    TopMark can insert the missing generated header.
    """
    filename: str = "test.py"
    path: Path = tmp_path / filename
    path.write_text("print('Hello, World!')\n", encoding="utf-8")

    result: Result = run_cli_in(
        tmp_path,
        _report_scope_args(
            command=CliCmd.CHECK,
            report_scope=report_scope,
            output_format=output_format,
        ),
    )

    assert_human_output_contains_if(
        output_format=output_format,
        output=result.output,
        expected=filename,
        expected_present=True,
    )


@pytest.mark.parametrize("output_format", OUTPUT_FORMATS)
@pytest.mark.parametrize(
    ("report_scope", "expected_visible"),
    [
        (ReportScope.ACTIONABLE, False),
        (ReportScope.NONCOMPLIANT, False),
        (ReportScope.ALL, True),
    ],
)
def test_strip_report_scope_hides_supported_headerless_file_when_not_all(
    output_format: OutputFormat | None,
    report_scope: ReportScope,
    expected_visible: bool,
    tmp_path: Path,
) -> None:
    """`strip` treats a supported headerless file as already compliant.

    A Python file without a TopMark header has nothing for `strip` to remove.
    It should therefore be omitted from actionable and noncompliant per-file
    output and listed only by the exhaustive `all` report scope.
    """
    filename: str = "test.py"
    path: Path = tmp_path / filename
    path.write_text("print('Hello, World!')\n", encoding="utf-8")

    result: Result = run_cli_in(
        tmp_path,
        _report_scope_args(
            command=CliCmd.STRIP,
            report_scope=report_scope,
            output_format=output_format,
        ),
    )

    assert_human_output_contains_if(
        output_format=output_format,
        output=result.output,
        expected=filename,
        expected_present=expected_visible,
    )


@pytest.mark.parametrize("output_format", OUTPUT_FORMATS)
@pytest.mark.parametrize(
    ("command", "report_scope", "expected_visible"),
    [
        (CliCmd.CHECK, ReportScope.ACTIONABLE, False),
        (CliCmd.CHECK, ReportScope.NONCOMPLIANT, False),
        (CliCmd.CHECK, ReportScope.ALL, True),
        (CliCmd.STRIP, ReportScope.ACTIONABLE, True),
        (CliCmd.STRIP, ReportScope.NONCOMPLIANT, True),
        (CliCmd.STRIP, ReportScope.ALL, True),
    ],
)
def test_check_and_strip_report_scope_for_supported_headered_file(
    output_format: OutputFormat | None,
    command: str,
    report_scope: ReportScope,
    expected_visible: bool,
    tmp_path: Path,
) -> None:
    """Supported headered files invert visibility for `check` and `strip`.

    The setup first lets `check --apply` insert a valid TopMark header. The
    resulting file is compliant for `check`, but actionable for `strip` because
    the existing header can be removed.
    """
    filename: str = "test.py"
    path: Path = tmp_path / filename
    path.write_text("print('Hello, World!')\n", encoding="utf-8")

    run_cli_in(
        tmp_path,
        [
            CliCmd.CHECK,
            CliOpt.APPLY_CHANGES,
            ".",
        ],
    )

    result: Result = run_cli_in(
        tmp_path,
        _report_scope_args(
            command=command,
            report_scope=report_scope,
            output_format=output_format,
        ),
    )

    assert_human_output_contains_if(
        output_format=output_format,
        output=result.output,
        expected=filename,
        expected_present=expected_visible,
    )
