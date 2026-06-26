# topmark:header:start
#
#   project      : TopMark
#   file         : test_probe_human_output.py
#   file_relpath : tests/cli/test_probe_human_output.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI probe human-output behavior tests.

This module verifies human-facing `topmark probe` output behavior:
- TEXT output changes progressively with verbosity,
- explicitly filtered inputs are reported with actionable diagnostics,
- Markdown output ignores TEXT-only verbosity and quiet controls.

These are output/rendering tests rather than pure exit-code contract tests.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner
from click.testing import Result

from tests.cli.conftest import assert_FILE_NOT_FOUND
from tests.cli.conftest import assert_human_output_contains
from tests.cli.conftest import assert_human_output_does_not_contain
from tests.cli.conftest import assert_strict_file_type_overlap_warning
from tests.cli.conftest import assert_SUCCESS
from tests.cli.conftest import assert_UNSUPPORTED_FILE_TYPE
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt
from topmark.cli.main import cli
from topmark.core.formats import OutputFormat

if TYPE_CHECKING:
    from pathlib import Path

    from pytest import MonkeyPatch


# --- TEXT output: verbosity levels ---
def test_probe_text_output_progressively_expands_with_verbosity(tmp_path: Path) -> None:
    """TEXT probe output should progressively expand from default to `-vv`."""
    file: Path = tmp_path / "example.py"
    file.write_text("print('hello')\n", encoding="utf-8")

    runner = CliRunner()

    result_default: Result = runner.invoke(
        cli,
        [
            CliCmd.PROBE,
            str(file),
        ],
    )
    result_v: Result = runner.invoke(
        cli,
        [
            CliCmd.PROBE,
            str(file),
            CliOpt.VERBOSE,
        ],
    )
    result_vv: Result = runner.invoke(
        cli,
        [
            CliCmd.PROBE,
            str(file),
            CliOpt.VERBOSE,
            CliOpt.VERBOSE,
        ],
    )

    assert_SUCCESS(result_default)
    assert_SUCCESS(result_v)
    assert_SUCCESS(result_vv)

    # Default TEXT output is a compact one-line summary.
    assert_human_output_contains(
        output_format=OutputFormat.TEXT,
        output=result_default.output,
        expected="resolved",
    )
    assert_human_output_contains(
        output_format=OutputFormat.TEXT,
        output=result_default.output,
        expected="processor=",
    )

    # `-v` adds selected file type and processor details.
    assert_human_output_contains(
        output_format=OutputFormat.TEXT,
        output=result_v.output,
        expected="selected file type",
    )
    assert_human_output_contains(
        output_format=OutputFormat.TEXT,
        output=result_v.output,
        expected="selected processor",
    )

    # `-vv` adds candidate and match details.
    assert_human_output_contains(
        output_format=OutputFormat.TEXT,
        output=result_vv.output,
        expected="candidates:",
    )
    assert_human_output_contains(
        output_format=OutputFormat.TEXT,
        output=result_vv.output,
        expected="match:",
    )

    # Each verbosity level should provide a distinct TEXT rendering.
    assert result_default.output != result_v.output
    assert result_v.output != result_vv.output


# --- TEXT output: filtered explicit inputs ---


def test_probe_text_output_reports_explicitly_filtered_input(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """TEXT probe output should explain explicit inputs filtered before resolution."""
    monkeypatch.chdir(tmp_path)
    filtered_dir: Path = tmp_path / "__pycache__"
    filtered_dir.mkdir()
    file: Path = filtered_dir / "example.cpython-312.pyc"
    file.write_bytes(b"\x00\x00\x00\x00")
    input_path: str = "__pycache__/example.cpython-312.pyc"

    runner = CliRunner()
    result: Result = runner.invoke(
        cli,
        [
            CliCmd.PROBE,
            CliOpt.EXCLUDE_PATTERNS,
            "__pycache__/",
            input_path,
        ],
    )

    assert_UNSUPPORTED_FILE_TYPE(result)

    assert_human_output_contains(
        output_format=OutputFormat.TEXT,
        output=result.output,
        expected="<filtered>",
    )
    assert_human_output_contains(
        output_format=OutputFormat.TEXT,
        output=result.output,
        expected="filtered: excluded_by_path_filter",
    )


def test_probe_text_output_omits_directory_filtered_result_when_children_selected(
    tmp_path: Path,
) -> None:
    """Expanded directories should not be reported as filtered inputs."""
    directory: Path = tmp_path / "project"
    directory.mkdir()

    python_file: Path = directory / "example.py"
    python_file.write_text("print('hello')\n", encoding="utf-8")

    markdown_file: Path = directory / "README.md"
    markdown_file.write_text("# Example\n", encoding="utf-8")

    html_file: Path = directory / "index.html"
    html_file.write_text("<h1>Example</h1>\n", encoding="utf-8")

    runner = CliRunner()
    result: Result = runner.invoke(
        cli,
        [
            CliCmd.PROBE,
            CliOpt.INCLUDE_FILE_TYPES,
            "python",
            CliOpt.INCLUDE_FILE_TYPES,
            "markdown,toml",
            CliOpt.EXCLUDE_FILE_TYPES,
            "html",
            str(directory),
        ],
    )

    assert_SUCCESS(result)

    assert_human_output_contains(
        output_format=OutputFormat.TEXT,
        output=result.output,
        expected="example.py",
    )
    assert_human_output_contains(
        output_format=OutputFormat.TEXT,
        output=result.output,
        expected="README.md",
    )
    assert_human_output_does_not_contain(
        output_format=OutputFormat.TEXT,
        output=result.output,
        expected="<filtered>",
    )


def test_probe_text_output_reports_missing_input_only_once(
    tmp_path: Path,
) -> None:
    """Missing explicit inputs should not also appear as filtered."""
    missing_directory: Path = tmp_path / "topmark-does-not-exist"
    runner = CliRunner()

    result: Result = runner.invoke(
        cli,
        [
            CliCmd.PROBE,
            str(missing_directory),
        ],
    )

    assert_FILE_NOT_FOUND(result)

    assert_human_output_contains(
        output_format=OutputFormat.TEXT,
        output=result.output,
        expected="probe-missing",
    )
    assert_human_output_does_not_contain(
        output_format=OutputFormat.TEXT,
        output=result.output,
        expected="<filtered>",
    )


# --- TEXT output: strict config diagnostics ---


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
def test_probe_text_output_reports_strict_file_type_overlap_warning(
    tmp_path: Path,
    include_file_types: str,
    exclude_file_types: str,
    expected_removed_file_types: tuple[str, ...],
) -> None:
    """TEXT probe output should include config diagnostics on strict failure.

    Strict mode escalates configuration warnings to `CONFIG_ERROR`, but the
    warning remains the actionable explanation. Probe should therefore render
    the normalized include/exclude overlap diagnostic instead of showing only
    the aggregate validation failure.
    """
    file: Path = tmp_path / "example.py"
    file.write_text("print('hello')\n", encoding="utf-8")

    runner = CliRunner()
    result: Result = runner.invoke(
        cli,
        [
            CliCmd.PROBE,
            CliOpt.STRICT,
            CliOpt.INCLUDE_FILE_TYPES,
            include_file_types,
            CliOpt.EXCLUDE_FILE_TYPES,
            exclude_file_types,
            str(file),
        ],
    )

    assert_strict_file_type_overlap_warning(
        result,
        output_format=None,
        expected_removed_file_types=expected_removed_file_types,
    )


# --- Markdown output: strict config diagnostics ---


def test_probe_markdown_output_reports_strict_file_type_overlap_warning(
    tmp_path: Path,
) -> None:
    """Markdown probe output should include config diagnostics on strict failure."""
    file: Path = tmp_path / "example.py"
    file.write_text("print('hello')\n", encoding="utf-8")

    runner = CliRunner()
    result: Result = runner.invoke(
        cli,
        [
            CliCmd.PROBE,
            CliOpt.STRICT,
            CliOpt.INCLUDE_FILE_TYPES,
            "topmark:python,topmark:markdown",
            CliOpt.EXCLUDE_FILE_TYPES,
            "python,markdown",
            CliOpt.OUTPUT_FORMAT,
            OutputFormat.MARKDOWN.value,
            str(file),
        ],
    )

    expected_removed_file_types = (
        "topmark:python",
        "topmark:markdown",
    )
    assert_strict_file_type_overlap_warning(
        result,
        output_format=None,
        expected_removed_file_types=expected_removed_file_types,
    )


# --- Markdown output: verbosity and quiet controls ---


def test_probe_markdown_output_ignores_text_verbosity(tmp_path: Path) -> None:
    """Markdown probe output should ignore TEXT-only verbosity flags."""
    file: Path = tmp_path / "example.py"
    file.write_text("print('hello')\n", encoding="utf-8")

    runner = CliRunner()

    result_default: Result = runner.invoke(
        cli,
        [
            CliCmd.PROBE,
            str(file),
            CliOpt.OUTPUT_FORMAT,
            OutputFormat.MARKDOWN.value,
        ],
    )
    result_v: Result = runner.invoke(
        cli,
        [
            CliCmd.PROBE,
            str(file),
            CliOpt.OUTPUT_FORMAT,
            OutputFormat.MARKDOWN.value,
            CliOpt.VERBOSE,
        ],
    )

    assert_SUCCESS(result_default)
    assert_SUCCESS(result_v)

    # Markdown ignores TEXT verbosity, so output should be identical.
    assert result_default.output == result_v.output

    # Basic Markdown structure checks.
    assert_human_output_contains(
        output_format=OutputFormat.MARKDOWN,
        output=result_default.output,
        expected="TopMark Resolution Probe Results",
    )
    assert_human_output_contains(
        output_format=OutputFormat.MARKDOWN,
        output=result_default.output,
        expected="## Files",
    )
    assert_human_output_contains(
        output_format=OutputFormat.MARKDOWN,
        output=result_default.output,
        expected="###",
    )


def test_probe_markdown_output_ignores_text_quiet(tmp_path: Path) -> None:
    """Markdown probe output should ignore TEXT-only quiet suppression."""
    file: Path = tmp_path / "example.py"
    file.write_text("print('hello')\n", encoding="utf-8")

    runner = CliRunner()

    result: Result = runner.invoke(
        cli,
        [
            CliCmd.PROBE,
            str(file),
            CliOpt.OUTPUT_FORMAT,
            OutputFormat.MARKDOWN.value,
            CliOpt.QUIET,
        ],
    )

    assert_SUCCESS(result)

    # Markdown should still render full document output.
    assert result.output.strip() != ""
    assert_human_output_contains(
        output_format=OutputFormat.MARKDOWN,
        output=result.output,
        expected="TopMark Resolution Probe Results",
    )
