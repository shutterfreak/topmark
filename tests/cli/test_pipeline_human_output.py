# topmark:header:start
#
#   project      : TopMark
#   file         : test_pipeline_human_output.py
#   file_relpath : tests/cli/test_pipeline_human_output.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI pipeline command human-output behavior tests.

This module verifies output-control behavior for the processing commands
(`check` and `strip`):
- TEXT quiet mode suppresses output while preserving exit status,
- Markdown output ignores TEXT-only quiet/verbosity controls,
- TEXT verbosity still controls progressive disclosure,
- `--apply --quiet` mutates files without emitting TEXT output.

These are output/rendering and applicability tests rather than pure exit-code
contract tests.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.cli.conftest import assert_CONFIG_ERROR
from tests.cli.conftest import assert_SUCCESS
from tests.cli.conftest import assert_WOULD_CHANGE
from tests.cli.conftest import run_cli
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt
from topmark.core.constants import TOPMARK_END_MARKER
from topmark.core.constants import TOPMARK_START_MARKER
from topmark.core.formats import OutputFormat

if TYPE_CHECKING:
    from pathlib import Path

    from click.testing import Result


pytestmark: pytest.MarkDecorator = pytest.mark.cli


def _write_file_requiring_check_update(tmp_path: Path) -> Path:
    """Create a Python file that requires header insertion by `check`."""
    path: Path = tmp_path / "needs_header.py"
    path.write_text("print('needs header')\n", encoding="utf-8")
    return path


def _write_file_requiring_strip(tmp_path: Path) -> Path:
    """Create a Python file with a removable TopMark header."""
    path: Path = tmp_path / "has_header.py"
    path.write_text(
        f"# {TOPMARK_START_MARKER}\n"
        "#   project: Test\n"
        f"# {TOPMARK_END_MARKER}\n"
        "print('has header')\n",
        encoding="utf-8",
    )
    return path


def _write_file_requiring_pipeline_change(tmp_path: Path, cmd: str) -> Path:
    """Create an input file that requires a change for the selected command."""
    return (
        _write_file_requiring_check_update(tmp_path)
        if cmd == CliCmd.CHECK
        else _write_file_requiring_strip(tmp_path)
    )


# --- Strict config diagnostics ---


def _assert_strict_file_type_overlap_warning(
    result: Result,
    expected_removed_file_types: tuple[str, ...],
) -> None:
    """Assert strict file-type overlap output includes actionable diagnostics."""
    assert_CONFIG_ERROR(result)
    out: str = result.output.lower()
    assert "file types specified in both include and exclude filters" in out
    assert "exclusion wins" in out
    for expected_removed_file_type in expected_removed_file_types:
        assert expected_removed_file_type in out


@pytest.mark.parametrize("cmd", [CliCmd.CHECK, CliCmd.STRIP])
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
def test_pipeline_text_output_reports_strict_file_type_overlap_warning(
    tmp_path: Path,
    cmd: str,
    include_file_types: str,
    exclude_file_types: str,
    expected_removed_file_types: tuple[str, ...],
) -> None:
    """TEXT pipeline output should include config diagnostics on strict failure.

    Strict mode escalates configuration warnings to `CONFIG_ERROR`, but the
    warning remains the actionable explanation. Processing commands should
    therefore render the normalized include/exclude overlap diagnostic instead
    of showing only the aggregate validation failure.
    """
    path: Path = _write_file_requiring_pipeline_change(tmp_path, cmd)

    result: Result = run_cli(
        [
            cmd,
            CliOpt.NO_COLOR_MODE,
            CliOpt.STRICT,
            CliOpt.INCLUDE_FILE_TYPES,
            include_file_types,
            CliOpt.EXCLUDE_FILE_TYPES,
            exclude_file_types,
            str(path),
        ]
    )

    _assert_strict_file_type_overlap_warning(result, expected_removed_file_types)


@pytest.mark.parametrize("cmd", [CliCmd.CHECK, CliCmd.STRIP])
def test_pipeline_markdown_output_reports_strict_file_type_overlap_warning(
    tmp_path: Path,
    cmd: str,
) -> None:
    """Markdown pipeline output should include config diagnostics on strict failure."""
    path: Path = _write_file_requiring_pipeline_change(tmp_path, cmd)

    result: Result = run_cli(
        [
            cmd,
            CliOpt.NO_COLOR_MODE,
            CliOpt.STRICT,
            CliOpt.INCLUDE_FILE_TYPES,
            "topmark:python,topmark:markdown",
            CliOpt.EXCLUDE_FILE_TYPES,
            "python,markdown",
            CliOpt.OUTPUT_FORMAT,
            OutputFormat.MARKDOWN.value,
            str(path),
        ]
    )

    _assert_strict_file_type_overlap_warning(
        result,
        ("topmark:python", "topmark:markdown"),
    )


# --- TEXT quiet mode ---


@pytest.mark.parametrize("cmd", [CliCmd.CHECK, CliCmd.STRIP])
def test_pipeline_text_quiet_suppresses_output_but_preserves_would_change_status(
    tmp_path: Path,
    cmd: str,
) -> None:
    """TEXT quiet mode should suppress output while preserving WOULD_CHANGE."""
    path: Path = _write_file_requiring_pipeline_change(tmp_path, cmd)

    result: Result = run_cli(
        [
            cmd,
            CliOpt.NO_COLOR_MODE,
            CliOpt.QUIET,
            str(path),
        ]
    )

    assert_WOULD_CHANGE(result)
    assert result.output == ""


# --- Markdown output: quiet / verbosity controls ---


@pytest.mark.parametrize("cmd", [CliCmd.CHECK, CliCmd.STRIP])
def test_pipeline_markdown_output_ignores_text_quiet(
    tmp_path: Path,
    cmd: str,
) -> None:
    """Markdown pipeline output should ignore TEXT-only quiet mode."""
    path: Path = _write_file_requiring_pipeline_change(tmp_path, cmd)

    result: Result = run_cli(
        [
            cmd,
            CliOpt.QUIET,
            CliOpt.OUTPUT_FORMAT,
            OutputFormat.MARKDOWN.value,
            str(path),
        ]
    )

    assert_WOULD_CHANGE(result)
    assert result.output.strip() != ""


@pytest.mark.parametrize("cmd", [CliCmd.CHECK, CliCmd.STRIP])
def test_pipeline_markdown_output_ignores_text_verbosity(
    tmp_path: Path,
    cmd: str,
) -> None:
    """Markdown pipeline output should ignore TEXT-only verbosity."""
    base_path: Path = _write_file_requiring_pipeline_change(tmp_path, cmd)

    base: Result = run_cli(
        [
            cmd,
            CliOpt.NO_COLOR_MODE,
            CliOpt.OUTPUT_FORMAT,
            OutputFormat.MARKDOWN.value,
            str(base_path),
        ]
    )
    verbose: Result = run_cli(
        [
            cmd,
            CliOpt.NO_COLOR_MODE,
            CliOpt.VERBOSE,
            CliOpt.OUTPUT_FORMAT,
            OutputFormat.MARKDOWN.value,
            str(base_path),
        ]
    )

    assert_WOULD_CHANGE(base)
    assert_WOULD_CHANGE(verbose)
    assert verbose.output == base.output


@pytest.mark.parametrize("cmd", [CliCmd.CHECK, CliCmd.STRIP])
def test_pipeline_markdown_output_always_renders_document_banner(
    tmp_path: Path,
    cmd: str,
) -> None:
    """Markdown pipeline output should always include a document banner."""
    path: Path = _write_file_requiring_pipeline_change(tmp_path, cmd)

    result: Result = run_cli(
        [
            cmd,
            CliOpt.NO_COLOR_MODE,
            CliOpt.OUTPUT_FORMAT,
            OutputFormat.MARKDOWN.value,
            str(path),
        ]
    )

    assert_WOULD_CHANGE(result)
    assert "# TopMark" in result.output


def test_check_markdown_output_shows_hints_without_text_verbosity(tmp_path: Path) -> None:
    """Markdown check output should render diagnostic hints without `-v`."""
    path: Path = _write_file_requiring_check_update(tmp_path)

    result: Result = run_cli(
        [
            CliCmd.CHECK,
            CliOpt.NO_COLOR_MODE,
            CliOpt.OUTPUT_FORMAT,
            OutputFormat.MARKDOWN.value,
            str(path),
        ]
    )

    assert_WOULD_CHANGE(result)
    assert "Hints:" in result.output
    assert "header:missing" in result.output


# --- TEXT verbosity ---


@pytest.mark.parametrize("cmd", [CliCmd.CHECK, CliCmd.STRIP])
def test_pipeline_text_verbose_changes_console_output_shape(
    tmp_path: Path,
    cmd: str,
) -> None:
    """TEXT pipeline verbosity should control progressive disclosure."""
    path: Path = _write_file_requiring_pipeline_change(tmp_path, cmd)

    base: Result = run_cli(
        [
            cmd,
            CliOpt.NO_COLOR_MODE,
            str(path),
        ]
    )
    verbose: Result = run_cli(
        [
            cmd,
            CliOpt.NO_COLOR_MODE,
            CliOpt.VERBOSE,
            str(path),
        ]
    )

    assert_WOULD_CHANGE(base)
    assert_WOULD_CHANGE(verbose)
    assert verbose.output != base.output


# --- Apply with quiet mode ---


def test_check_apply_quiet_writes_changes_without_text_output(tmp_path: Path) -> None:
    """`check --apply --quiet` should mutate files without TEXT output."""
    path: Path = _write_file_requiring_check_update(tmp_path)
    before: str = path.read_text(encoding="utf-8")

    result: Result = run_cli(
        [
            CliCmd.CHECK,
            CliOpt.NO_COLOR_MODE,
            CliOpt.APPLY_CHANGES,
            CliOpt.QUIET,
            str(path),
        ]
    )

    assert_SUCCESS(result)
    assert result.output == ""
    assert path.read_text(encoding="utf-8") != before


def test_strip_apply_quiet_writes_changes_without_text_output(tmp_path: Path) -> None:
    """`strip --apply --quiet` should mutate files without TEXT output."""
    path: Path = _write_file_requiring_strip(tmp_path)

    result: Result = run_cli(
        [
            CliCmd.STRIP,
            CliOpt.NO_COLOR_MODE,
            CliOpt.APPLY_CHANGES,
            CliOpt.QUIET,
            str(path),
        ]
    )

    assert_SUCCESS(result)
    assert result.output == ""

    after: str = path.read_text(encoding="utf-8")
    assert TOPMARK_START_MARKER not in after
    assert TOPMARK_END_MARKER not in after
