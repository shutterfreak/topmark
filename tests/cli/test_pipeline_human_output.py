# topmark:header:start
#
#   project      : TopMark
#   file         : test_pipeline_human_output.py
#   file_relpath : tests/cli/test_pipeline_human_output.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI tests for human-facing pipeline command output."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from tests.cli.conftest import assert_SUCCESS
from tests.cli.conftest import assert_WOULD_CHANGE
from tests.cli.conftest import run_cli
from tests.conftest import parametrize
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt
from topmark.constants import TOPMARK_END_MARKER
from topmark.constants import TOPMARK_START_MARKER

if TYPE_CHECKING:
    from pathlib import Path

    from click.testing import Result


pytestmark = pytest.mark.cli


def _write_file_requiring_check_update(tmp_path: Path) -> Path:
    path: Path = tmp_path / "needs_header.py"
    path.write_text("print('needs header')\n", encoding="utf-8")
    return path


def _write_file_requiring_strip(tmp_path: Path) -> Path:
    path: Path = tmp_path / "has_header.py"
    path.write_text(
        f"# {TOPMARK_START_MARKER}\n"
        "#   project: Test\n"
        f"# {TOPMARK_END_MARKER}\n"
        "print('has header')\n",
        encoding="utf-8",
    )
    return path


@parametrize("cmd", [CliCmd.CHECK, CliCmd.STRIP])
def test_pipeline_text_quiet_suppresses_output_but_preserves_exit_status(
    tmp_path: Path,
    cmd: str,
) -> None:
    """Pipeline TEXT quiet mode should suppress output but keep meaningful exit status."""
    path: Path = (
        _write_file_requiring_check_update(tmp_path)
        if cmd == CliCmd.CHECK
        else _write_file_requiring_strip(tmp_path)
    )

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


@parametrize("cmd", [CliCmd.CHECK, CliCmd.STRIP])
def test_pipeline_markdown_ignores_quiet(
    tmp_path: Path,
    cmd: str,
) -> None:
    """Pipeline Markdown output should ignore TEXT-only quiet mode."""
    path: Path = (
        _write_file_requiring_check_update(tmp_path)
        if cmd == CliCmd.CHECK
        else _write_file_requiring_strip(tmp_path)
    )

    result: Result = run_cli(
        [
            cmd,
            CliOpt.NO_COLOR_MODE,
            CliOpt.QUIET,
            CliOpt.OUTPUT_FORMAT,
            "markdown",
            str(path),
        ]
    )

    assert_WOULD_CHANGE(result)
    assert result.output.strip() != ""


@parametrize("cmd", [CliCmd.CHECK, CliCmd.STRIP])
def test_pipeline_markdown_ignores_verbose(
    tmp_path: Path,
    cmd: str,
) -> None:
    """Pipeline Markdown output should ignore TEXT-only verbosity."""
    base_path: Path = (
        _write_file_requiring_check_update(tmp_path)
        if cmd == CliCmd.CHECK
        else _write_file_requiring_strip(tmp_path)
    )

    base: Result = run_cli(
        [
            cmd,
            CliOpt.NO_COLOR_MODE,
            CliOpt.OUTPUT_FORMAT,
            "markdown",
            str(base_path),
        ]
    )
    verbose: Result = run_cli(
        [
            cmd,
            CliOpt.NO_COLOR_MODE,
            CliOpt.VERBOSE,
            CliOpt.OUTPUT_FORMAT,
            "markdown",
            str(base_path),
        ]
    )

    assert_WOULD_CHANGE(base)
    assert_WOULD_CHANGE(verbose)
    assert verbose.output == base.output


@parametrize("cmd", [CliCmd.CHECK, CliCmd.STRIP])
def test_pipeline_markdown_always_renders_banner(
    tmp_path: Path,
    cmd: str,
) -> None:
    """Markdown output should always include a document banner."""
    path: Path = (
        _write_file_requiring_check_update(tmp_path)
        if cmd == CliCmd.CHECK
        else _write_file_requiring_strip(tmp_path)
    )

    result: Result = run_cli(
        [
            cmd,
            CliOpt.NO_COLOR_MODE,
            CliOpt.OUTPUT_FORMAT,
            "markdown",
            str(path),
        ]
    )

    assert_WOULD_CHANGE(result)
    assert "# TopMark" in result.output


def test_pipeline_markdown_shows_hints_without_verbose(tmp_path: Path) -> None:
    """Markdown should render available diagnostic hints without requiring -v."""
    path: Path = _write_file_requiring_check_update(tmp_path)

    result: Result = run_cli(
        [
            CliCmd.CHECK,
            CliOpt.NO_COLOR_MODE,
            CliOpt.OUTPUT_FORMAT,
            "markdown",
            str(path),
        ]
    )

    assert_WOULD_CHANGE(result)
    assert "Hints:" in result.output
    assert "header:missing" in result.output


@parametrize("cmd", [CliCmd.CHECK, CliCmd.STRIP])
def test_pipeline_text_verbose_changes_console_output_shape(
    tmp_path: Path,
    cmd: str,
) -> None:
    """Pipeline TEXT verbosity should still control progressive disclosure."""
    path: Path = (
        _write_file_requiring_check_update(tmp_path)
        if cmd == CliCmd.CHECK
        else _write_file_requiring_strip(tmp_path)
    )

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


@parametrize("cmd", [CliCmd.CHECK, CliCmd.STRIP])
def test_pipeline_quiet_does_not_suppress_markdown_output(
    tmp_path: Path,
    cmd: str,
) -> None:
    """--quiet must not suppress Markdown output."""
    path: Path = (
        _write_file_requiring_check_update(tmp_path)
        if cmd == CliCmd.CHECK
        else _write_file_requiring_strip(tmp_path)
    )

    result: Result = run_cli(
        [
            cmd,
            CliOpt.QUIET,
            CliOpt.OUTPUT_FORMAT,
            "markdown",
            str(path),
        ]
    )

    assert result.output.strip() != ""


def test_check_apply_quiet_writes_changes_without_text_output(tmp_path: Path) -> None:
    """`check --apply --quiet` should write changes while suppressing TEXT output."""
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
    """`strip --apply --quiet` should write changes while suppressing TEXT output."""
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
